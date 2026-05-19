# Task 1: 事项中心真实对接 + HMAC 双 key 轮换

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `server/src/ai_engine/integrations/event_center_client.py`
- Modify: `server/.env.example` / `config.py`（加 `_CURRENT` / `_PREVIOUS`）
- Modify: `server/src/ai_engine/api/tickets.py`（验签接受双 key）
- Create: `server/tests/test_event_center_dual_key.py`

- [ ] **Step 1: 配置加双 key**

```ini
EVENT_CENTER_URL=https://event-center.tevau.internal/api/v1
EVENT_CENTER_SECRET_CURRENT=
EVENT_CENTER_SECRET_PREVIOUS=
```

`config.py`:
```python
event_center_secret_current: str = ""
event_center_secret_previous: str | None = None
# 兼容 MVP-2 的 event_center_secret 字段：仍保留但 deprecated
```

- [ ] **Step 2: 重写 client 用 `_CURRENT` 签名，验签时两 key 都试**

```python
# integrations/event_center_client.py
def _sign(body: bytes) -> str:
    return hmac.new(settings.event_center_secret_current.encode(), body, hashlib.sha256).hexdigest()

# api/tickets.py 接收回调时:
def _verify(raw: bytes, sig: str) -> bool:
    for key in (settings.event_center_secret_current, settings.event_center_secret_previous):
        if not key: continue
        expected = hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, sig):
            return True
    return False
```

- [ ] **Step 3: 写双 key 测试**（生成两个签名分别用 current / previous，都应通过；都不匹配的 401）

- [ ] **Step 4: 删除 mock event center receiver**

```python
# main.py 移除 event_center_mock router 注册（生产环境不挂这个）
# 保留 mock 文件但通过 env flag MOCK_EVENT_CENTER=1 才挂载
```

- [ ] **Step 5: Commit**

```bash
git add ...
git commit -m "feat(mvp-3): 事项中心真实对接 + HMAC 双 key 热轮换"
```

---
