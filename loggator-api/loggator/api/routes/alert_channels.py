from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.alert_registry import (
    list_channels,
    create_channel,
    update_channel,
    delete_channel,
    get_channel_raw,
    AlertChannelNotFound,
)
from loggator.alerts.dispatcher import _FakeAnomaly, _send_slack, _send_telegram, _send_email, _send_webhook

router = APIRouter(tags=["alert-channels"])


@router.get("/alert-channels")
async def get_alert_channels(session: AsyncSession = Depends(get_session)):
    return await list_channels(session)


@router.post("/alert-channels", status_code=201)
async def post_alert_channel(body: dict, session: AsyncSession = Depends(get_session)):
    return await create_channel(session, body)


@router.put("/alert-channels/{id}")
async def put_alert_channel(id: str, body: dict, session: AsyncSession = Depends(get_session)):
    try:
        return await update_channel(session, id, body)
    except AlertChannelNotFound:
        raise HTTPException(status_code=404, detail="Channel not found")


@router.delete("/alert-channels/{id}", status_code=204)
async def del_alert_channel(id: str, session: AsyncSession = Depends(get_session)):
    try:
        await delete_channel(session, id)
    except AlertChannelNotFound:
        raise HTTPException(status_code=404, detail="Channel not found")


@router.post("/alert-channels/{id}/test")
async def test_alert_channel(id: str, session: AsyncSession = Depends(get_session)):
    try:
        ch = await get_channel_raw(session, id)
    except AlertChannelNotFound:
        raise HTTPException(status_code=404, detail="Channel not found")

    a = _FakeAnomaly()
    cfg = ch.get("config", {})
    ch_type = ch.get("type", "")

    try:
        if ch_type == "slack":
            webhook_url = cfg.get("webhook_url", "")
            if not webhook_url:
                return {"ok": False, "error": "webhook_url not configured"}
            import httpx
            from loggator.alerts.dispatcher import _build_payload
            severity_emoji = {"low": ":information_source:", "medium": ":warning:", "high": ":rotating_light:"}.get(a.severity, ":warning:")
            slack_body = {
                "text": f"{severity_emoji} *Loggator Test Alert* — `{a.severity.upper()}`",
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"{severity_emoji} *Test alert from Loggator*\n{a.summary}"}},
                ],
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=slack_body)
                resp.raise_for_status()
            ok, err = True, ""
        elif ch_type == "telegram":
            bot_token = cfg.get("bot_token", "")
            chat_id = cfg.get("chat_id", "")
            if not bot_token or not chat_id:
                return {"ok": False, "error": "bot_token or chat_id not configured"}
            import httpx
            text = f"\u2139\ufe0f Loggator Test Alert\n{a.summary}\nDetected: {a.detected_at.isoformat()}"
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={"chat_id": chat_id, "text": text})
                resp.raise_for_status()
            ok, err = True, ""
        elif ch_type == "email":
            to_addr = cfg.get("to", "")
            if not to_addr:
                return {"ok": False, "error": "to address not configured"}
            ok, err = await _send_email(a, to_addr.split(",")[0].strip())
        elif ch_type == "webhook":
            url = cfg.get("url", "")
            if not url:
                return {"ok": False, "error": "url not configured"}
            ok, err = await _send_webhook(a, url)
        else:
            return {"ok": False, "error": f"Unknown channel type: {ch_type}"}
    except Exception as exc:
        ok, err = False, str(exc)

    return {"ok": ok, "error": err if not ok else None}
