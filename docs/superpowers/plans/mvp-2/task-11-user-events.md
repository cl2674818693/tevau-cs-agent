# Task 11: 反向 webhook —— /request-human + /user-events

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `server/src/ai_engine/api/user_events.py`
- Create: `server/tests/test_request_human.py`
- Create: `server/tests/test_user_events.py`

- [ ] **Step 1: 写 `server/src/ai_engine/api/user_events.py`**

```python
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from ai_engine.api.chat import resolve_identity
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import tickets as ticket_dao
from ai_engine.integrations.event_center_client import push_event_center  # 见下面 Task 12


router = APIRouter()


class RequestHumanIn(BaseModel):
    reason: str | None = None


@router.post("/api/v1/conversations/{conv_id}/request-human")
async def request_human(conv_id: int, body: RequestHumanIn, request: Request):
    user_type, subject_id = await resolve_identity(request)
    mode, _ = await conv_dao.get_mode(conv_id)
    if mode == "human_takeover":
        return {"ok": True, "note": "already human-handled"}
    await conv_dao.set_mode(conv_id, "human_pending")
    # 同时建一张工单（category=人工介入）让事项中心通知值班
    from ai_engine.agent.tools.create_ticket import run as create_ticket_run
    out = await create_ticket_run(
        bu_id=subject_id if user_type == "b" else "",  # router 会处理 C 端
        conversation_id=conv_id,
        category="人工介入",
        summary=f"用户请求人工：{body.reason or '(no reason)'}",
        severity="p2",
        evidence={"conversation_id": conv_id, "reason": body.reason},
    )
    from ai_engine.api.staff_conversations import _publish
    _publish(conv_id, {"type": "request_human", "ticket_id": out["external_ticket_id"]})
    return {"ok": True, "ticket_id": out["external_ticket_id"]}


class UserEventIn(BaseModel):
    event: str  # "user_confirmed_resolved" | "user_rejected_resolved"
    reason: str | None = None


@router.post("/api/v1/tickets/{external_id}/user-events")
async def user_events(external_id: str, body: UserEventIn, request: Request):
    user_type, subject_id = await resolve_identity(request)

    # 校验工单属于当前身份
    t = await ticket_dao.get_ticket(external_id)
    if not t:
        raise HTTPException(404, "ticket not found")
    payload = __import__("json").loads(t["payload_json"])
    payload_subject = payload.get("bu_id") if user_type == "b" else payload.get("user_id")
    if payload_subject != subject_id:
        raise HTTPException(403, "not your ticket")

    if body.event == "user_confirmed_resolved":
        await ticket_dao.append_ticket_event(external_id, "closed", "user",
                                             "用户确认已解决", raw={"source": "user"})
        await push_event_center({"external_ticket_id": external_id,
                                  "event_type": "closed", "actor": "user"})
        return {"ok": True}

    if body.event == "user_rejected_resolved":
        await ticket_dao.append_ticket_event(external_id, "reopen", "user",
                                             body.reason or "用户表示未解决",
                                             raw={"source": "user", "reason": body.reason})
        await push_event_center({"external_ticket_id": external_id,
                                  "event_type": "reopen", "actor": "user",
                                  "reason": body.reason})
        return {"ok": True}

    raise HTTPException(400, "unknown event")
```

- [ ] **Step 2: 写测试 `server/tests/test_request_human.py` + `server/tests/test_user_events.py`**

(测试代码省略 — 模式与上面类似，覆盖：成功路径、跨身份访问 403、未知事件 400)

- [ ] **Step 3: Commit**

```bash
git add server/src/ai_engine/api/user_events.py server/tests/test_request_human.py server/tests/test_user_events.py
git commit -m "feat(mvp-2): 反向 webhook /request-human + /user-events（含身份二次校验）"
```

---
