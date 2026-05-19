# Task 3: 重写 query_user / query_card / query_api_call（aiomysql + 真实 schema + 脱敏）

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

> **前置阻塞**：用户提供 `unlimitpay_test` 库 schema dump（`INFORMATION_SCHEMA.COLUMNS` 查询导出，见 spec §12.2 第 9 条）后才能冻结具体 SQL。**本任务先按推测 schema 实现**（注释标 `# TODO: 校对真实字段`），用户提供 schema 后改一遍。

测试用 `testcontainers[mysql]` 起一个真 MySQL 容器跑 seed.sql 做端到端测试。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_user.py`
- Modify: `server/src/ai_engine/agent/tools/query_card.py`
- Modify: `server/src/ai_engine/agent/tools/query_api_call.py`
- Create: `server/tests/fixtures/unlimitpay_seed.sql`（按推测 schema 写）
- Create: `server/tests/test_query_tools_real.py`

- [ ] **Step 1: 写 `server/tests/fixtures/unlimitpay_seed.sql`**（按你给的 schema 后修订）

```sql
CREATE TABLE IF NOT EXISTS bu (
    bu_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    status TINYINT NOT NULL DEFAULT 1,    -- 1=active 0=disabled
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS user (
    user_id VARCHAR(20) PRIMARY KEY,
    bu_id VARCHAR(20) NOT NULL,
    email VARCHAR(120),
    phone VARCHAR(20),
    status VARCHAR(20),
    INDEX idx_bu (bu_id)
);

CREATE TABLE IF NOT EXISTS card (
    card_id VARCHAR(30) PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    bu_id VARCHAR(20) NOT NULL,
    card_no VARCHAR(30),                   -- 真实卡号（必脱敏）
    status VARCHAR(20),
    lock_reason VARCHAR(200),
    INDEX idx_bu (bu_id)
);

CREATE TABLE IF NOT EXISTS api_call_log (
    uid VARCHAR(40) PRIMARY KEY,
    bu_id VARCHAR(20) NOT NULL,
    endpoint VARCHAR(200) NOT NULL,
    status_code INT NOT NULL,
    error_code VARCHAR(50),
    request_json TEXT,
    response_json TEXT,
    created_at DATETIME,
    INDEX idx_bu_created (bu_id, created_at)
);

INSERT INTO bu(bu_id, name, status) VALUES
  ('BU00243780', '示例合作伙伴', 1),
  ('BU_OTHER', '另一个 BU', 1);

INSERT INTO user(user_id, bu_id, email, phone, status) VALUES
  ('U1', 'BU00243780', 'alice@x.com', '13812345678', 'active'),
  ('U2', 'BU_OTHER',   'bob@x.com',   '13911112222', 'active');

INSERT INTO card(card_id, user_id, bu_id, card_no, status, lock_reason) VALUES
  ('C100', 'U1', 'BU00243780', '4938750672464590', 'locked', 'R-217 风控误判'),
  ('C200', 'U2', 'BU_OTHER',   '1111222233334444', 'active', NULL);

INSERT INTO api_call_log(uid, bu_id, endpoint, status_code, error_code, request_json, response_json, created_at) VALUES
  ('1765348436409', 'BU00243780', '/v2/card/bind', 500, 'DB_TIMEOUT', '{}', '{"error":"DB_TIMEOUT"}', '2026-05-18 10:00:00');
```

- [ ] **Step 2: 写 `server/tests/test_query_tools_real.py`**

```python
import pytest
from testcontainers.mysql import MySqlContainer
from pathlib import Path


@pytest.fixture(scope="module")
def mysql_url():
    with MySqlContainer("mysql:8.0") as mysql:
        url = mysql.get_connection_url().replace("mysql+pymysql://", "mysql://")
        # 加载 seed
        import pymysql
        cfg = mysql.get_connection_url()  # for pymysql
        conn = pymysql.connect(host=mysql.get_container_host_ip(),
                               port=int(mysql.get_exposed_port(3306)),
                               user="test", password="test", database="test")
        with conn.cursor() as cur:
            for stmt in Path("tests/fixtures/unlimitpay_seed.sql").read_text().split(";"):
                if stmt.strip():
                    cur.execute(stmt)
        conn.commit()
        conn.close()
        yield url


@pytest.fixture(autouse=True)
async def init_db(monkeypatch, mysql_url):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("UNLIMITPAY_DB_URL", mysql_url)
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.persistence import business_db
    await business_db.init_business_dbs(mysql_url, None)
    yield
    await business_db.close_all()


async def test_query_user_returns_masked_data():
    from ai_engine.agent.tools.query_user import run
    out = await run(bu_id="BU00243780", user_id="U1")
    u = out["user"]
    assert u["email"] == "al***@x.com"    # 脱敏
    assert u["phone"] == "138****78"
    assert u["bu_id"] == "BU00243780"


async def test_query_user_rejects_cross_bu():
    from ai_engine.agent.tools.query_user import run
    out = await run(bu_id="BU00243780", user_id="U2")  # U2 属于 BU_OTHER
    assert out["user"] is None


async def test_query_card_masks_card_no_and_lock_reason():
    from ai_engine.agent.tools.query_card import run
    out = await run(bu_id="BU00243780", card_id="C100")
    c = out["card"]
    assert "R-217" not in c["lock_reason"]   # 内部规则名移除
    assert c["card_no"] == "4938 **** **** 4590"


async def test_query_api_call_by_uid():
    from ai_engine.agent.tools.query_api_call import run
    out = await run(bu_id="BU00243780", uid="1765348436409")
    assert out["call"]["status_code"] == 500
```

- [ ] **Step 3: 重写 `server/src/ai_engine/agent/tools/query_user.py`**

```python
from ai_engine.persistence.business_db import get_db
from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_phone, mask_email


SQL = """
SELECT user_id, bu_id, email, phone, status
FROM user
WHERE user_id=%s AND bu_id=%s
"""


async def run(bu_id: str, user_id: str) -> dict:
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (user_id, bu_id))
    if not row:
        return {"user": None, "note": f"user {user_id} not in BU {bu_id}"}
    # 脱敏在 handler 内做（spec §5.4）—— LLM 看不到原文
    return {"user": {
        "user_id": row["user_id"],
        "bu_id": row["bu_id"],
        "email": mask_email(row.get("email")),
        "phone": mask_phone(row.get("phone")),
        "status": row.get("status"),
    }}


register(Tool(
    name="query_user",
    description="查询某个 user 的基本信息（仅限当前 BU 下，敏感字段已脱敏）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},   # router 强制注入
            "user_id": {"type": "string"},
        },
        "required": ["user_id"],
    },
    handler=run,
    requires_subject_id=True,
))
```

- [ ] **Step 4: 重写 `server/src/ai_engine/agent/tools/query_card.py`**

```python
from ai_engine.persistence.business_db import get_db
from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_card_no


SQL = """
SELECT card_id, user_id, bu_id, card_no, status, lock_reason
FROM card
WHERE card_id=%s AND bu_id=%s
"""

# 内部风控规则名 → 业务原因翻译（不让 LLM 看到 R-xxx）
def _translate_lock_reason(raw: str | None) -> str | None:
    if not raw:
        return raw
    import re
    return re.sub(r"R-\d{2,4}", "风控规则命中", raw)


async def run(bu_id: str, card_id: str) -> dict:
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (card_id, bu_id))
    if not row:
        return {"card": None, "note": f"card {card_id} not in BU {bu_id}"}
    return {"card": {
        "card_id": row["card_id"],
        "user_id": row["user_id"],
        "bu_id": row["bu_id"],
        "card_no": mask_card_no(row.get("card_no")),
        "status": row.get("status"),
        "lock_reason": _translate_lock_reason(row.get("lock_reason")),
    }}


register(Tool(
    name="query_card",
    description="查询卡片状态与锁定原因（仅限当前 BU 下；卡号脱敏，内部风控规则名已替换为业务原因）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},
            "card_id": {"type": "string"},
        },
        "required": ["card_id"],
    },
    handler=run,
    requires_subject_id=True,
))
```

- [ ] **Step 5: 重写 `server/src/ai_engine/agent/tools/query_api_call.py`**

```python
from ai_engine.persistence.business_db import get_db
from ai_engine.agent.tools.base import Tool, register


SQL = """
SELECT uid, bu_id, endpoint, status_code, error_code, request_json, response_json, created_at
FROM api_call_log
WHERE uid=%s AND bu_id=%s
"""


async def run(bu_id: str, uid: str) -> dict:
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (uid, bu_id))
    if not row:
        return {"call": None, "note": f"uid {uid} not found for BU {bu_id}"}
    # request/response_json 可能含敏感字段；MVP-2 先原样返回，后续接 schema 时按字段脱敏
    # TODO: 接到真实 schema 后明确哪些字段要从 request_json / response_json 里挖出来脱敏
    return {"call": dict(row)}


register(Tool(
    name="query_api_call",
    description="按 uid（请求唯一 ID）查询一次 API 调用的日志（仅限当前 BU）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},
            "uid": {"type": "string"},
        },
        "required": ["uid"],
    },
    handler=run,
    requires_subject_id=True,
))
```

- [ ] **Step 6: 跑测试**

```bash
pytest tests/test_query_tools_real.py -v
```
Expected: 4 passed（需要 docker 在跑，testcontainers 自动起 mysql:8.0）

- [ ] **Step 7: Commit**

```bash
git add server/tests/fixtures/unlimitpay_seed.sql server/src/ai_engine/agent/tools/query_user.py server/src/ai_engine/agent/tools/query_card.py server/src/ai_engine/agent/tools/query_api_call.py server/tests/test_query_tools_real.py
git commit -m "feat(mvp-2): query_* 工具切换 aiomysql + 工具层脱敏（手机/卡号/邮箱/规则名）"
```

> **schema 校对清单（用户给真实 schema 后）**：表名是否真叫 `user` / `card` / `api_call_log` / `bu`？字段名是否一致？是否有额外字段需要脱敏（如身份证 / 地址 / 银行卡支付密码）？

---
