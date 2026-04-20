import json
import structlog
import httpx
from uuid import UUID

from loggator.config import settings
from loggator.db.models import Alert, Anomaly

log = structlog.get_logger()

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}
_THRESHOLD = _SEVERITY_ORDER.get(settings.alert_severity_threshold, 1)


def _meets_threshold(severity: str) -> bool:
    return _SEVERITY_ORDER.get(severity, 0) >= _THRESHOLD


def _build_payload(anomaly: Anomaly) -> dict:
    return {
        "anomaly_id": str(anomaly.id),
        "severity": anomaly.severity,
        "summary": anomaly.summary,
        "root_cause_hints": anomaly.root_cause_hints,
        "detected_at": anomaly.detected_at.isoformat(),
        "index_pattern": anomaly.index_pattern,
    }


async def _send_slack(anomaly: Anomaly) -> tuple[bool, str]:
    if not settings.slack_webhook_url:
        return False, "SLACK_WEBHOOK_URL not configured"
    payload = _build_payload(anomaly)
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
                    {"type": "mrkdwn", "text": f"*Root cause hints:*\n" + "\n".join(f"• {h}" for h in anomaly.root_cause_hints[:3])},
                    {"type": "mrkdwn", "text": f"*Detected at:*\n{anomaly.detected_at.isoformat()}"},
                ],
            },
        ],
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.slack_webhook_url, json=slack_body)
        resp.raise_for_status()
    return True, ""


async def _send_webhook(anomaly: Anomaly, url: str) -> tuple[bool, str]:
    payload = _build_payload(anomaly)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
    return True, ""


async def _send_email(anomaly: Anomaly, to_addr: str) -> tuple[bool, str]:
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


async def dispatch(anomaly: Anomaly, session) -> list[Alert]:
    """
    Dispatch alerts for an anomaly if it meets the severity threshold.
    Returns list of Alert rows created.
    """
    if not _meets_threshold(anomaly.severity):
        log.debug("dispatcher.below_threshold", severity=anomaly.severity, threshold=settings.alert_severity_threshold)
        return []

    alerts_created: list[Alert] = []
    payload = _build_payload(anomaly)

    async def _record(channel: str, destination: str, ok: bool, error: str) -> Alert:
        alert = Alert(
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
        return alert

    # Slack
    if settings.slack_webhook_url:
        try:
            ok, err = await _send_slack(anomaly)
        except Exception as exc:
            ok, err = False, str(exc)
        alert = await _record("slack", settings.slack_webhook_url[:40], ok, err)
        alerts_created.append(alert)
        log.info("dispatcher.slack", ok=ok, anomaly_id=str(anomaly.id))

    if alerts_created:
        # mark anomaly as alerted after first successful dispatch
        if any(a.status == "sent" for a in alerts_created):
            anomaly.alerted = True
            await session.commit()

    return alerts_created
