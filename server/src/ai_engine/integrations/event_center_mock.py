from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()
INBOX: list[dict[str, Any]] = []


@router.post("/_mock/event-center")
async def receive(request: Request) -> dict[str, Any]:
    body = await request.json()
    INBOX.append(body)
    return {"ok": True, "internal_ticket_id": f"EC-MOCK-{len(INBOX):05d}", "received_at": "now"}
