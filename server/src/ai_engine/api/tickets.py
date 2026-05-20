import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request

from ai_engine.config import settings
from ai_engine.persistence.tickets import append_ticket_event, update_ticket_severity

router = APIRouter()


def _verify(raw: bytes, sig: str) -> bool:
    expected = hmac.new(settings.event_center_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@router.post("/api/v1/tickets/{external_id}/events")
async def receive_event(
    external_id: str, request: Request, x_signature: str = Header(default="")
) -> dict[str, bool]:
    raw = await request.body()
    if not _verify(raw, x_signature):
        raise HTTPException(401, "bad signature")
    body = json.loads(raw)
    await append_ticket_event(
        external_id=external_id,
        event=body.get("event", ""),
        actor=body.get("actor"),
        comment=body.get("comment"),
        raw=body,
    )
    # spec §7.2 修订：event=in_progress 时可带 severity（受理人在事项中心覆盖）
    if body.get("event") == "in_progress" and body.get("severity"):
        await update_ticket_severity(external_id=external_id, severity=body["severity"])
    return {"ok": True}
