import structlog
import httpx
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta
from uuid import UUID

from loggator.config import settings
from loggator.db.models import Alert, Anomaly
from loggator.observability import system_event_writer
from loggator.tenancy.constants import BOOTSTRAP_TENANT_ID

log = structlog.get_logger()

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
_THRESHOLD = _SEVERITY_ORDER.get(settings.alert_severity_threshold, 1)

# In-memory cooldown cache keyed by "{index_pattern}:{severity}"
_cooldown_cache: dict[str, datetime] = {}


def _meets_threshold(severity: str) -> bool:
    return _SEVERITY_ORDER.get(severity, 0) >= _THRESHOLD


def _is_cooling_down(tenant_id: UUID, index_pattern: str, severity: str) -> bool:
    key = f"{tenant_id}:{index_pattern}:{severity}"
    last = _cooldown_cache.get(key)
    return last is not None and datetime.utcnow() - last < timedelta(minutes=settings.alert_cooldown_minutes)


def _record_sent(tenant_id: UUID, index_pattern: str, severity: str) -> None:
    _cooldown_cache[f"{tenant_id}:{index_pattern}:{severity}"] = datetime.utcnow()


def _build_payload(anomaly) -> dict:
    return {
        "anomaly_id": str(anomaly.id),
        "severity": anomaly.severity,
        "summary": anomaly.summary,
        "root_cause_hints": anomaly.root_cause_hints,
        "detected_at": anomaly.detected_at.isoformat(),
        "index_pattern": anomaly.index_pattern,
    }


async def _send_slack(anomaly) -> tuple[bool, str]:
    if not settings.slack_webhook_url:
        return False, "SLACK_WEBHOOK_URL not configured"
    severity_emoji = {"low": ":information_source:", "medium": ":warning:", "high": ":rotating_light:"}.get(
        anomaly.severity, ":warning:"
    )
    slack_body = {
        "text": f"{severity_emoji} *Loggator Anomaly Detected* — `{anomaly.severity.upper()}`",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{severity_emoji} *{anomaly.severity.upper()} anomaly* in `{anomaly.index_pattern}`\n{anomaly.summary}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": "*Root cause hints:*\n" + "\n".join(f"• {h}" for h in anomaly.root_cause_hints[:3])},
                    {"type": "mrkdwn", "text": f"*Detected at:*\n{anomaly.detected_at.isoformat()}"},
                ],
            },
        ],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.slack_webhook_url, json=slack_body)
        resp.raise_for_status()
    return True, ""


async def _send_webhook(anomaly, url: str) -> tuple[bool, str]:
    payload = _build_payload(anomaly)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
    return True, ""


async def _send_email(anomaly, to_addr: str) -> tuple[bool, str]:
    if not settings.smtp_host:
        return False, "SMTP_HOST not configured"
    try:
        import aiosmtplib
        from email.mime.text import MIMEText

        body = (
            f"Loggator Anomaly Alert\n\n"
            f"Severity: {anomaly.severity.upper()}\n"
            f"Index: {anomaly.index_pattern}\n"
            f"Detected: {anomaly.detected_at.isoformat()}\n\n"
            f"Summary:\n{anomaly.summary}\n\n"
            f"Root cause hints:\n" + "\n".join(f"  - {h}" for h in anomaly.root_cause_hints)
        )
        msg = MIMEText(body)
        msg["Subject"] = f"[Loggator] {anomaly.severity.upper()} anomaly in {anomaly.index_pattern}"
        msg["From"] = settings.alert_from_email or settings.smtp_username
        msg["To"] = to_addr

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=True,
        )
        return True, ""
    except Exception as exc:
        return False, str(exc)


async def _send_telegram(anomaly) -> tuple[bool, str]:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False, "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured"
    icon = {"low": "\u2139\ufe0f", "medium": "\u26a0\ufe0f", "high": "\U0001f6a8"}.get(anomaly.severity, "\u26a0\ufe0f")
    hints = "\n".join(f"  \u2022 {h}" for h in anomaly.root_cause_hints[:3])
    text = (
        f"{icon} Loggator Alert \u2014 {anomaly.severity.upper()}\n"
        f"Index: {anomaly.index_pattern}\n"
        f"{anomaly.summary}\n\n"
        f"Root cause hints:\n{hints}\n"
        f"Detected: {anomaly.detected_at.isoformat()}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"chat_id": settings.telegram_chat_id, "text": text})
        resp.raise_for_status()
    return True, ""


async def dispatch(anomaly: Anomaly, session) -> list[Alert]:
    """Dispatch alerts for an anomaly if it meets the severity threshold."""
    if not _meets_threshold(anomaly.severity):
        log.debug("dispatcher.below_threshold", severity=anomaly.severity, threshold=settings.alert_severity_threshold)
        return []

    if _is_cooling_down(anomaly.tenant_id, anomaly.index_pattern, anomaly.severity):
        log.info(
            "dispatcher.cooldown",
            index_pattern=anomaly.index_pattern,
            severity=anomaly.severity,
            cooldown_minutes=settings.alert_cooldown_minutes,
        )
        return []

    alerts_created: list[Alert] = []
    payload = _build_payload(anomaly)

    async def _record(channel: str, destination: str, ok: bool, error: str) -> Alert:
        alert = Alert(
            tenant_id=anomaly.tenant_id,
            anomaly_id=anomaly.id,
            channel=channel,
            destination=destination,
            payload=payload,
            status="sent" if ok else "failed",
            error=error if not ok else None,
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        await system_event_writer.write(
            service="alerts",
            event_type="alert_dispatched",
            severity="info" if ok else "error",
            message=f"Alert {channel} to {destination}: {'sent' if ok else 'failed'}",
            details={
                "channel": channel,
                "destination": destination,
                "ok": ok,
                "error": error or None,
                "anomaly_id": str(anomaly.id),
                "severity": anomaly.severity,
            },
        )
        return alert

    # Slack
    if settings.slack_webhook_url:
        try:
            ok, err = await _send_slack(anomaly)
        except Exception as exc:
            ok, err = False, str(exc)
        alerts_created.append(await _record("slack", settings.slack_webhook_url[:40], ok, err))
        log.info("dispatcher.slack", ok=ok, anomaly_id=str(anomaly.id))

    # Email
    if settings.smtp_host and settings.alert_email_to:
        for addr in [a.strip() for a in settings.alert_email_to.split(",") if a.strip()]:
            try:
                ok, err = await _send_email(anomaly, addr)
            except Exception as exc:
                ok, err = False, str(exc)
            alerts_created.append(await _record("email", addr, ok, err))
            log.info("dispatcher.email", ok=ok, to=addr, anomaly_id=str(anomaly.id))

    # Telegram
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            ok, err = await _send_telegram(anomaly)
        except Exception as exc:
            ok, err = False, str(exc)
        alerts_created.append(await _record("telegram", f"tg:{settings.telegram_chat_id}", ok, err))
        log.info("dispatcher.telegram", ok=ok, anomaly_id=str(anomaly.id))

    # Webhook
    if settings.alert_webhook_url:
        try:
            ok, err = await _send_webhook(anomaly, settings.alert_webhook_url)
        except Exception as exc:
            ok, err = False, str(exc)
        alerts_created.append(await _record("webhook", settings.alert_webhook_url[:40], ok, err))
        log.info("dispatcher.webhook", ok=ok, anomaly_id=str(anomaly.id))

    # Registry-based channels
    try:
        from loggator.db.alert_registry import list_enabled_channels_raw
        reg_channels = await list_enabled_channels_raw(session, anomaly.tenant_id)
    except Exception:
        reg_channels = []

    for ch in reg_channels:
        ch_type = ch.get("type", "")
        ch_label = ch.get("label", ch_type)
        cfg = ch.get("config", {})
        try:
            if ch_type == "slack":
                webhook_url = cfg.get("webhook_url", "")
                if not webhook_url:
                    continue
                import httpx as _httpx
                severity_emoji = {"low": ":information_source:", "medium": ":warning:", "high": ":rotating_light:"}.get(anomaly.severity, ":warning:")
                slack_body = {
                    "text": f"{severity_emoji} *Loggator Anomaly Detected* — `{anomaly.severity.upper()}`",
                    "blocks": [
                        {"type": "section", "text": {"type": "mrkdwn",
                            "text": f"{severity_emoji} *{anomaly.severity.upper()} anomaly* in `{anomaly.index_pattern}`\n{anomaly.summary}"}},
                        {"type": "section", "fields": [
                            {"type": "mrkdwn", "text": "*Root cause hints:*\n" + "\n".join(f"• {h}" for h in anomaly.root_cause_hints[:3])},
                            {"type": "mrkdwn", "text": f"*Detected at:*\n{anomaly.detected_at.isoformat()}"},
                        ]},
                    ],
                }
                async with _httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(webhook_url, json=slack_body)
                    resp.raise_for_status()
                ok, err = True, ""
                dest = webhook_url[:40]
            elif ch_type == "telegram":
                bot_token = cfg.get("bot_token", "")
                chat_id = cfg.get("chat_id", "")
                if not bot_token or not chat_id:
                    continue
                icon = {"low": "\u2139\ufe0f", "medium": "\u26a0\ufe0f", "high": "\U0001f6a8"}.get(anomaly.severity, "\u26a0\ufe0f")
                hints = "\n".join(f"  \u2022 {h}" for h in anomaly.root_cause_hints[:3])
                text = (f"{icon} Loggator Alert \u2014 {anomaly.severity.upper()}\n"
                        f"Index: {anomaly.index_pattern}\n{anomaly.summary}\n\nRoot cause hints:\n{hints}\n"
                        f"Detected: {anomaly.detected_at.isoformat()}")
                import httpx as _httpx
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                async with _httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, json={"chat_id": chat_id, "text": text})
                    resp.raise_for_status()
                ok, err = True, ""
                dest = f"tg:{chat_id}"
            elif ch_type == "email":
                to_addr = cfg.get("to", "")
                if not to_addr:
                    continue
                for addr in [a.strip() for a in to_addr.split(",") if a.strip()]:
                    try:
                        ok, err = await _send_email(anomaly, addr)
                    except Exception as exc:
                        ok, err = False, str(exc)
                    alerts_created.append(await _record(f"email:{ch_label}", addr, ok, err))
                    log.info("dispatcher.registry_email", label=ch_label, ok=ok, to=addr, anomaly_id=str(anomaly.id))
                continue
            elif ch_type == "webhook":
                url = cfg.get("url", "")
                if not url:
                    continue
                ok, err = await _send_webhook(anomaly, url)
                dest = url[:40]
            else:
                continue
        except Exception as exc:
            ok, err = False, str(exc)
            dest = ch_label
        alerts_created.append(await _record(f"{ch_type}:{ch_label}", dest, ok, err))
        log.info("dispatcher.registry_channel", type=ch_type, label=ch_label, ok=ok, anomaly_id=str(anomaly.id))

    if alerts_created:
        _record_sent(anomaly.tenant_id, anomaly.index_pattern, anomaly.severity)
        if any(a.status == "sent" for a in alerts_created):
            anomaly.alerted = True
            await session.commit()

    return alerts_created


# ── Test dispatch (bypasses cooldown, DB, threshold) ─────────────────────────

@dataclass
class _FakeAnomaly:
    """Minimal stand-in for Anomaly used only in test dispatches."""
    id: str = "00000000-0000-0000-0000-000000000000"
    tenant_id: UUID = BOOTSTRAP_TENANT_ID
    severity: str = "high"
    summary: str = "This is a test alert from Loggator."
    root_cause_hints: list = dc_field(default_factory=lambda: ["Test hint 1", "Test hint 2"])
    index_pattern: str = "test-*"
    detected_at: object = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.utcnow()


async def dispatch_test(channel: str) -> tuple[bool, str]:
    """Send a single test alert on the given channel. No DB writes, no cooldown."""
    a = _FakeAnomaly()
    if channel == "slack":
        return await _send_slack(a)
    elif channel == "email":
        if not settings.alert_email_to:
            return False, "ALERT_EMAIL_TO not configured"
        return await _send_email(a, settings.alert_email_to.split(",")[0].strip())
    elif channel == "telegram":
        return await _send_telegram(a)
    elif channel == "webhook":
        if not settings.alert_webhook_url:
            return False, "ALERT_WEBHOOK_URL not configured"
        return await _send_webhook(a, settings.alert_webhook_url)
    raise ValueError(f"Unknown channel: {channel!r}")
