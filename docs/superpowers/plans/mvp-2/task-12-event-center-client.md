# Task 12: 事项中心客户端封装（push closed/reopen 用）

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `src/ai_engine/integrations/event_center_client.py`
- Create: `tests/test_event_center_client.py`

- [ ] **Step 1: 写 `src/ai_engine/integrations/event_center_client.py`**

```python
import hmac
import hashlib
import json
import httpx
from ai_engine.config import settings


def _sign(body: bytes) -> str:
    return hmac.new(settings.event_center_secret.encode(), body, hashlib.sha256).hexdigest()


async def push_event_center(payload: dict) -> bool:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-Signature": _sign(body), "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{settings.event_center_url}/events", content=body, headers=headers,
            )
        return 200 <= resp.status_code < 300
    except Exception:
        return False
```

- [ ] **Step 2: 测试 + Commit**

```bash
pytest tests/test_event_center_client.py -v
git add src/ai_engine/integrations/event_center_client.py tests/test_event_center_client.py
git commit -m "feat(mvp-2): 事项中心客户端（HMAC 签名推送 closed/reopen/确认事件）"
```

---
