# 业务查询工具正确性整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 7 个碰真实业务库的客服 AI 查询工具，从"按推测写死 SQL+枚举"改成"与真实后端表/列/枚举一致、覆盖完整、查空诚实"，消除给用户错误答案与越权风险。

**Architecture:** 每个工具用"先连真实 RDS 核对 → 假行单测锁映射 → 重写 → 真实库冒烟"四步闭环整改。新增一个共享的"诚实标签"工具函数（未映射枚举显式标注、查空带覆盖范围说明），并在系统提示词里加"禁止把单工具的空/单字段当业务事实下绝对结论"的护栏。

**Tech Stack:** Python 3.12 / aiomysql（业务只读库）/ pytest / 现有 `ai_engine.agent.tools` 框架。真实库连接串在 `/Users/sunchenglin/codes/tevau-cs-engine/server/.env`（`UNLIMITPAY_DB_URL` / `NEXUS_DB_URL`，阿里云新加坡 RDS，只读账号 nexus_test）。

**已查证的根因（执行时不要再推翻，可复核）：**
- `query_transaction` 查了 `t_tevaupay_transaction_wallet_records`（钱包流水），但 APP 首页"最近交易/奖励"实际来自 `t_tevaupay_card_recharge_records`（卡交易流水主表，type=29=奖励）。已用真实样例 id=100146 坐实。
- `query_kyc` / `query_user`：KYC 每用户仅 1 行（2427 用户全 1 行），**无多行取错问题**，纯枚举错/漏。`audit_status` 真实分布 1:1642 / 3:368 / 5:217 / 0:156 / 2:43。
- 其余见各 Task 的"审计依据"。

---

## 执行约定（所有 Task 通用）

**工作目录**：`/Users/sunchenglin/codes/tevau-cs-engine/.claude/worktrees/reliability-hardening/server`（下称 `server/`）。所有命令在此目录下用 `.venv/bin/python` / `.venv/bin/pytest`。

**真实库只读核对脚本**：已存在 `/tmp/rds_probe.py`。若不在则按 Task 0 重建。用法：
```python
import sys; sys.path.insert(0, '/tmp'); import rds_probe as R
import asyncio
async def fn(U, N):  # U=unlimitpay url, N=nexus url
    rows = await R.q(U, "SELECT ...")   # 只读 SQL；SQL 里的 % 写成 %%
    R.show("标题", rows)
asyncio.run(R.run(fn))
```
**红线**：核对只允许 `SELECT` / `SHOW` / `information_schema`，必须带 `LIMIT`，禁止任何写操作。

**单测模式**：不连真实库。monkeypatch 掉工具模块里 import 的 `get_db`，返回一个假 DB，其 `fetch_all` / `fetch_one` 吐预置行（模拟真实库的列名与枚举数值），断言 `run()` 输出的映射与覆盖正确。范式（写在每个 test 文件顶部）：
```python
import pytest
from types import SimpleNamespace

class FakeDB:
    def __init__(self, rows):
        self._rows = rows
    async def fetch_all(self, sql, params=(), limit=100):
        return list(self._rows)
    async def fetch_one(self, sql, params=()):
        return self._rows[0] if self._rows else None

def patch_db(monkeypatch, module, rows_by_call):
    # rows_by_call: 单表工具传 list；多查询工具见对应 test 说明
    import importlib
    mod = importlib.import_module(module)
    monkeypatch.setattr(mod, "get_db", lambda name: FakeDB(rows_by_call))
```

---

## Task 0: 核对脚本 + 共享"诚实标签"工具函数

**Files:**
- Create: `/tmp/rds_probe.py`（若不存在）
- Modify: `server/src/ai_engine/agent/tools/base.py`
- Test: `server/tests/test_tool_label_helpers.py`

- [ ] **Step 1: 确认/重建 `/tmp/rds_probe.py`**

若文件不存在，写入：
```python
import re, asyncio, aiomysql
from urllib.parse import urlparse
ENV = open('/Users/sunchenglin/codes/tevau-cs-engine/server/.env').read()
def url(name):
    return re.search(rf'{name}=(mysql://\S+)', ENV).group(1).strip()
async def q(dburl, sql):
    p = urlparse(dburl)
    conn = await aiomysql.connect(host=p.hostname, port=p.port, user=p.username,
        password=p.password, db=p.path.lstrip('/'), charset='utf8mb4', connect_timeout=10)
    cur = await conn.cursor(aiomysql.DictCursor)
    await cur.execute("SET SESSION MAX_EXECUTION_TIME=8000")
    await cur.execute(sql); rows = await cur.fetchall(); conn.close(); return rows
def show(title, rows):
    print(f"\n=== {title} ({len(rows)}) ===")
    for r in rows: print("  " + " | ".join(f"{k}={v}" for k, v in r.items()))
async def run(fn):
    await fn(url('UNLIMITPAY_DB_URL'), url('NEXUS_DB_URL'))
```
验证连通：`.venv/bin/python -c "import sys;sys.path.insert(0,'/tmp');import rds_probe as R,asyncio;asyncio.run(R.run(lambda U,N: R.q(U,'SELECT 1 a').__await__().__next__() if 0 else None))"` —— 简单起见直接跑 Step 任意后续核对即可。

- [ ] **Step 2: 写失败测试 `test_tool_label_helpers.py`**

```python
from ai_engine.agent.tools.base import label, scope_note

def test_label_maps_known():
    assert label({1: "USDT", 2: "USD"}, 2) == "USD"

def test_label_marks_unknown_value():
    assert label({1: "USDT"}, 7) == "未知(7)"

def test_label_none_stays_none():
    assert label({1: "USDT"}, None) is None

def test_scope_note_for_empty():
    note = scope_note("钱包流水", covered="钱包充值/提现/转账", not_covered="卡消费/奖励")
    assert "未覆盖" in note and "卡消费" in note
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_tool_label_helpers.py -v`
Expected: FAIL（`ImportError: cannot import name 'label'`）

- [ ] **Step 4: 在 `base.py` 末尾实现**

```python
def label(mapping: dict, value):
    """枚举翻译：未命中的非空值显式标注为 未知(原值)，不静默吐裸数字。"""
    if value is None:
        return None
    return mapping.get(value, f"未知({value})")

def scope_note(source: str, covered: str, not_covered: str) -> str:
    """查空时给 AI 的边界说明，避免把'本表无'当成'用户无'。"""
    return f"本次仅查询了{source}（覆盖：{covered}）。未覆盖：{not_covered}。查不到不代表用户没有相关记录。"
```

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_tool_label_helpers.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_tool_label_helpers.py src/ai_engine/agent/tools/base.py
git commit -m "feat(tools): 新增枚举诚实标签与查空边界说明工具函数"
```

---

## Task 1: 重写 query_transaction（最高优先级：查错表）

**审计依据**：APP 首页交易来自 `t_tevaupay_card_recharge_records`，后端 `CardRecordsLogic.transPage`（`TevauPay-Service/.../logic/impl/CardRecordsLogic.java:110`）+ `CardRechargeRecordsMapper.xml:68`，过滤 `status IN(3,4,8) AND type NOT IN(25,22)`，按 `date_time_stamp DESC`。type 枚举见 `BankCardRecordTypeEnum`（29=REWARDS）。旧的钱包流水表是另一类（钱包充提），不丢，作为第二来源。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_transaction.py`
- Test: `server/tests/test_query_transaction_mapping.py`

- [ ] **Step 1: RDS 核对列名与 type 实际取值**

```python
# .venv/bin/python，sys.path 注入 /tmp 后：
# 1) 列存在性
await R.q(U, "SELECT column_name,column_type,column_comment FROM information_schema.columns WHERE table_schema='unlimitpay_test' AND table_name='t_tevaupay_card_recharge_records' AND column_name IN ('user_id','card_id','order_id','type','digest','status','currency','trade_amount','income_amount','out_amount','fee','merchant_name','remark','reward_order_id','recharge_time','create_time','date_time_stamp','pay_type') ORDER BY ordinal_position")
# 2) type/status/currency/digest/pay_type 实际出现的值
await R.q(U, "SELECT type v,COUNT(*) c FROM t_tevaupay_card_recharge_records GROUP BY type ORDER BY c DESC LIMIT 40")
```
Expected：上述列全部存在；type 含 29；status 含 3/4/8。若有列名不符，以核对结果为准修正下方 SQL。

- [ ] **Step 2: 写失败测试**

```python
import pytest
from types import SimpleNamespace

class FakeDB:
    def __init__(self, rows): self._rows = rows
    async def fetch_all(self, sql, params=(), limit=100): return list(self._rows)
    async def fetch_one(self, sql, params=()): return self._rows[0] if self._rows else None

@pytest.mark.asyncio
async def test_card_reward_mapped(monkeypatch):
    import ai_engine.agent.tools.query_transaction as m
    card_rows = [dict(type=29, digest=2, status=3, currency=2, trade_amount=10,
                      income_amount=None, out_amount=10, fee=0, merchant_name=None,
                      remark="Bonus expired", order_id="RE1", card_number="****0823",
                      recharge_time="2026-04-25 10:40:37", create_time=None, pay_type=3)]
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(card_rows))
    out = await m.run(user_id="1")
    t = out["card_transactions"][0]
    assert t["type"] == "奖励" and t["flow"] == "出账"
    assert t["status"] == "成功" and t["currency"] == "USD"
    assert t["channel"] == "reap"

@pytest.mark.asyncio
async def test_unknown_type_marked(monkeypatch):
    import ai_engine.agent.tools.query_transaction as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([dict(type=999, digest=1,
        status=3, currency=2, trade_amount=1, income_amount=1, out_amount=None, fee=0,
        merchant_name=None, remark=None, order_id="x", card_number=None,
        recharge_time=None, create_time=None, pay_type=3)]))
    out = await m.run(user_id="1")
    assert out["card_transactions"][0]["type"] == "未知(999)"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_transaction_mapping.py -v`
Expected: FAIL（输出无 `card_transactions` 键）

- [ ] **Step 4: 重写 `query_transaction.py`**

```python
from typing import Any
from ai_engine.agent.tools.base import Tool, register, label
from ai_engine.persistence.business_db import get_db

# 主源：APP 首页"最近交易/奖励"实际来自卡交易流水主表
CARD_SQL = """
SELECT r.type, r.digest, r.status, r.currency, r.trade_amount, r.income_amount,
       r.out_amount, r.fee, r.merchant_name, r.remark, r.order_id, r.pay_type,
       COALESCE(r.recharge_time, r.create_time) AS tx_time,
       c.card_number
FROM t_tevaupay_card_recharge_records r
LEFT JOIN t_tevaupay_bank_card_user c ON c.three_card_id = r.card_id
WHERE r.user_id=%s AND r.status IN (3,4,8) AND r.type NOT IN (25,22)
ORDER BY r.date_time_stamp DESC
"""
# 第二源：钱包层充值/提现/转账（与卡交易不同域，保留）
WALLET_SQL = """
SELECT type, transaction_status, fund_flow, trade_amount, fee, currency, create_time
FROM t_tevaupay_transaction_wallet_records
WHERE user_id=%s ORDER BY create_time DESC
"""

_CARD_TYPE = {1:"充值卡",2:"提现卡",3:"申请卡",4:"卡消费",5:"ATM取款",6:"卡销户",
    7:"开卡充值手续费",8:"销卡",9:"卡冻结",10:"卡解冻",11:"退款",12:"卡消费处理费",
    13:"授权查询",14:"冲正",15:"交易处理费冲正",16:"交易",17:"交易处理费",18:"网上支付",
    19:"刷卡支付",20:"非接触支付",21:"TXN已退款",22:"TXN退款处理",23:"未知交易",
    24:"拒付(ChargeBack)",25:"卡激活剩余余额充值",26:"其他交易",27:"未知卡交易",
    28:"平台卡扣费",29:"奖励",30:"拒付",31:"不活跃扣费"}
_CARD_STATUS = {-1:"未知",1:"待处理",2:"处理中",3:"成功",4:"失败",5:"待退款",
    6:"三方失败",7:"流水生成异常",8:"退款",9:"欠费",10:"审核中"}
_CURRENCY = {1:"USDT",2:"USD",3:"ARB_ETH",4:"BNB",5:"TRX",6:"EUR",7:"BTCW",
    8:"HKD",9:"CNY",12:"IDR",15:"XUSD"}
_DIGEST = {1:"入账",2:"出账"}
_PAY_TYPE = {1:"宝付",2:"easyeuro",3:"reap",4:"sx"}
_WALLET_TYPE = {1:"充币",2:"提币",3:"转账",4:"调账",5:"归集",6:"开卡",7:"卡充值",9:"转账(收)"}
_WALLET_STATUS = {1:"待处理",2:"处理中",3:"成功",4:"失败"}
_FLOW = {1:"入账",2:"出账"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户的卡交易流水（消费/奖励/退款等，APP首页"最近交易"同源）与钱包充提流水。"""
    db = get_db("unlimitpay")
    card_rows = await db.fetch_all(CARD_SQL, (user_id,), limit=20)
    wallet_rows = await db.fetch_all(WALLET_SQL, (user_id,), limit=20)
    cards = [{
        "type": label(_CARD_TYPE, r.get("type")),
        "flow": label(_DIGEST, r.get("digest")),
        "status": label(_CARD_STATUS, r.get("status")),
        "currency": label(_CURRENCY, r.get("currency")),
        "amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
        "fee": str(r["fee"]) if r.get("fee") is not None else None,
        "merchant": r.get("merchant_name"),
        "remark": r.get("remark"),
        "order_id": r.get("order_id"),
        "channel": label(_PAY_TYPE, r.get("pay_type")),
        "card_number": r.get("card_number"),
        "time": str(r["tx_time"]) if r.get("tx_time") else None,
    } for r in card_rows]
    wallets = [{
        "type": label(_WALLET_TYPE, r.get("type")),
        "status": label(_WALLET_STATUS, r.get("transaction_status")),
        "flow": label(_FLOW, r.get("fund_flow")),
        "amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
        "currency": label(_CURRENCY, r.get("currency")),
        "time": str(r["create_time"]) if r.get("create_time") else None,
    } for r in wallet_rows]
    return {
        "card_transactions": cards, "card_count": len(cards),
        "wallet_flows": wallets, "wallet_count": len(wallets),
        "note": "card_transactions 是 APP 首页可见的卡交易（消费/奖励/退款）；"
                "wallet_flows 是钱包充提。两者都为空才说明该用户暂无交易。",
    }


register(Tool(
    name="query_transaction",
    description="查询当前用户的卡交易流水（消费/奖励/退款/不活跃扣费等，与 APP 首页'最近交易'同源）"
                "及钱包充提流水。用户问'我的交易/流水/奖励''为什么扣款''转账到账没'时用。",
    input_schema={"type":"object","properties":{"user_id":{"type":"string"}},"required":[]},
    handler=run, requires_subject_id=True, subject_field="user_id", supports_unmask=False,
))
```

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_transaction_mapping.py -v`
Expected: PASS

- [ ] **Step 6: 真实库冒烟**（取一个有卡交易的真实 user_id）

```python
# 先找一个有卡交易的 user_id：
await R.q(U, "SELECT user_id,COUNT(*) c FROM t_tevaupay_card_recharge_records WHERE type=29 GROUP BY user_id ORDER BY c DESC LIMIT 3")
# 用其 user_id 跑工具：
# .venv/bin/python -c "import asyncio,os; os.environ['UNLIMITPAY_DB_URL']=...; from ai_engine.persistence.business_db import init_business_dbs; import ai_engine.agent.tools.query_transaction as m; ..."
```
Expected：`card_transactions` 非空且含"奖励"等中文类型，无"未知(数字)"。

- [ ] **Step 7: Commit**

```bash
git add tests/test_query_transaction_mapping.py src/ai_engine/agent/tools/query_transaction.py
git commit -m "fix(tools): query_transaction 改查卡交易流水主表(覆盖消费/奖励)+保留钱包流水"
```

---

## Task 2: 修 query_user 的 KYC 枚举（最坑：未认证被显示成审核中）

**审计依据**：`User.kycStatus` 受 `KycStatusEnum` 管辖 = `{0:未认证,1:已认证,2:认证失败,3:审核中}`（`TevauPay-Service/.../enums/KycStatusEnum.java:11`）。工具现写 `{0:审核中,1:认证通过,2:未通过,5:未认证}`，0 错成"审核中"、3 缺失、5 不存在。user_status/open_card_status 已正确。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_user.py`
- Test: `server/tests/test_query_user_mapping.py`

- [ ] **Step 1: RDS 核对 kyc_status 实际取值**

```python
await R.q(U, "SELECT kyc_status v,COUNT(*) c FROM t_tevaupay_user GROUP BY kyc_status ORDER BY c DESC")
```
Expected：取值落在 {0,1,2,3}（可能含 NULL）。确认无 5。

- [ ] **Step 2: 写失败测试**

```python
import pytest
class FakeDB:
    def __init__(self, row): self._row = row
    async def fetch_one(self, sql, params=()): return self._row

@pytest.mark.asyncio
async def test_kyc_status_correct(monkeypatch):
    import ai_engine.agent.tools.query_user as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(
        dict(id=1, user_code="C1", email_address=None, mobile_phone=None, nick_name="n",
             user_status=0, kyc_status=0, open_card_status=0,
             registration_time=None, last_login_time=None)))
    out = await m.run(user_id="1")
    assert out["user"]["kyc_status"] == "未认证"   # 旧代码会错成"审核中"

@pytest.mark.asyncio
async def test_kyc_status_3_is_reviewing(monkeypatch):
    import ai_engine.agent.tools.query_user as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(
        dict(id=1, user_code="C1", email_address=None, mobile_phone=None, nick_name="n",
             user_status=0, kyc_status=3, open_card_status=0,
             registration_time=None, last_login_time=None)))
    out = await m.run(user_id="1")
    assert out["user"]["kyc_status"] == "审核中"   # 旧代码会吐裸 "3"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_user_mapping.py -v`
Expected: FAIL（assert "未认证" 实得 "审核中"）

- [ ] **Step 4: 改 `query_user.py`**

把 `_KYC_STATUS` 字典改为：
```python
_KYC_STATUS = {0: "未认证", 1: "已认证", 2: "认证失败", 3: "审核中"}
```
并把对 kyc_status 的翻译改用 `label(_KYC_STATUS, ...)`（从 `ai_engine.agent.tools.base` import `label`），其余 user_status/open_card_status 同样改用 `label(...)` 以统一"未知(值)"行为。

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_user_mapping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_query_user_mapping.py src/ai_engine/agent/tools/query_user.py
git commit -m "fix(tools): query_user 修正 KYC 状态枚举(0=未认证非审核中)"
```

---

## Task 3: 修 query_kyc 枚举 + 交叉用户主表状态

**审计依据**：KYC 单行/用户，无取错行。`audit_status` 用 `AuditStatusEnum`={0审核中,1认证通过,2未通过,3未提审,4活体完成,5未认证}，工具缺 3/4/5（585 个用户中招）。面向用户"我实名通过了吗"的权威口径是 `t_tevaupay_user.kyc_status`（APP 同源），KYC 表 audit_status 是审核流水细节——两者可能不一致，应同时给出避免自相矛盾。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_kyc.py`
- Test: `server/tests/test_query_kyc_mapping.py`

- [ ] **Step 1: RDS 核对 audit_status 取值 + 是否存在 user.kyc_status 与 kyc.audit_status 冲突样例**

```python
await R.q(U, "SELECT audit_status v,COUNT(*) c FROM t_tevaupay_user_kyc WHERE del=0 GROUP BY audit_status ORDER BY c DESC")
await R.q(U, "SELECT u.kyc_status, k.audit_status, COUNT(*) c FROM t_tevaupay_user u JOIN t_tevaupay_user_kyc k ON k.user_id=u.id AND k.del=0 GROUP BY u.kyc_status,k.audit_status ORDER BY c DESC LIMIT 30")
```
Expected：确认 audit_status 含 3/5；记录两表状态的对应/冲突分布，作为话术依据。

- [ ] **Step 2: 写失败测试**

```python
import pytest
class FakeOne:
    def __init__(self, row): self._row = row
    async def fetch_one(self, sql, params=()): return self._row

@pytest.mark.asyncio
async def test_audit_status_5_uncertified(monkeypatch):
    import ai_engine.agent.tools.query_kyc as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeOne(
        dict(audit_status=5, identity_failer_reason=None, certification_status=0,
             country_area="SG", live_country="SG", identity_card_type=2,
             first_name="A", last_name="B", identity_card="X", birthday=None,
             phone_code="65", phone_number="123", address=None, city=None,
             post_code=None, request_time=None, audit_pass_time=None, user_kyc_status=0)))
    out = await m.run(user_id="1")
    assert out["kyc"]["audit_status"] == "未认证"        # 旧代码吐裸 "5"

@pytest.mark.asyncio
async def test_audit_status_3_not_submitted(monkeypatch):
    import ai_engine.agent.tools.query_kyc as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeOne(
        dict(audit_status=3, identity_failer_reason=None, certification_status=0,
             country_area=None, live_country=None, identity_card_type=2,
             first_name="A", last_name="B", identity_card="X", birthday=None,
             phone_code=None, phone_number=None, address=None, city=None,
             post_code=None, request_time=None, audit_pass_time=None, user_kyc_status=0)))
    out = await m.run(user_id="1")
    assert out["kyc"]["audit_status"] == "未提审"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_kyc_mapping.py -v`
Expected: FAIL（实得 "5" / "3"）

- [ ] **Step 4: 改 `query_kyc.py`**

- `_AUDIT` 改为完整：
```python
_AUDIT = {0:"审核中",1:"认证通过",2:"未通过",3:"未提审",4:"活体检测已完成",5:"未认证"}
```
- 用 `label(_AUDIT, ...)`（import 自 base）。
- SQL 增加联表取用户主表权威状态，并在输出加 `user_kyc_status` 字段（用 `_KYC_STATUS` 翻译，复用 query_user 同款 `{0:未认证,1:已认证,2:认证失败,3:审核中}`，可在 base 里集中定义后两个工具共享）：
```python
SQL = """
SELECT k.audit_status, k.identity_failer_reason, k.certification_status, k.country_area,
       k.live_country, k.identity_card_type, k.first_name, k.last_name, k.identity_card,
       k.birthday, k.phone_code, k.phone_number, k.address, k.city, k.post_code,
       k.request_time, k.audit_pass_time, u.kyc_status AS user_kyc_status
FROM t_tevaupay_user_kyc k
LEFT JOIN t_tevaupay_user u ON u.id = k.user_id
WHERE k.user_id=%s AND k.del=0
ORDER BY k.id DESC
"""
```
- 输出里加：`"user_kyc_status": label(_KYC_STATUS, row.get("user_kyc_status"))`，并在返回 dict 顶层加 `"note": "user_kyc_status 是用户中心展示的实名状态(权威口径)；audit_status 是 KYC 审核记录状态。若两者不一致，以 user_kyc_status 为准向用户解释。"`

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_kyc_mapping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_query_kyc_mapping.py src/ai_engine/agent/tools/query_kyc.py src/ai_engine/agent/tools/base.py
git commit -m "fix(tools): query_kyc 补全审核状态枚举(3/4/5)+联表给出用户中心权威实名状态"
```

---

## Task 4: 修 query_balance 币种枚举 + platSource 维度

**审计依据**：`CurrencyEnum` 共 11 值（工具只 2 个）；`AccountStatusEnum`={0正常,1冻结}（工具写"锁定"）；定位一条账户的键含 `plat_source`（`AccountCurrencyUserServiceImpl.queryByUserId`），工具未取/未返回，多平台用户会出无法区分的重复行。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_balance.py`
- Test: `server/tests/test_query_balance_mapping.py`

- [ ] **Step 1: RDS 核对**

```python
await R.q(U, "SELECT column_name FROM information_schema.columns WHERE table_schema='unlimitpay_test' AND table_name='t_tevaupay_account_currency_user' AND column_name IN ('plat_source','currency','money_type','status','account_type')")
await R.q(U, "SELECT currency v,COUNT(*) c FROM t_tevaupay_account_currency_user GROUP BY currency ORDER BY c DESC")
```
Expected：`plat_source` 存在；currency 出现的值都在下方 _CURRENCY 内。

- [ ] **Step 2: 写失败测试**

```python
import pytest
class FakeDB:
    def __init__(self, rows): self._rows = rows
    async def fetch_all(self, sql, params=(), limit=100): return list(self._rows)

@pytest.mark.asyncio
async def test_eur_and_status_and_plat(monkeypatch):
    import ai_engine.agent.tools.query_balance as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([
        dict(currency=6, money_type=1, total_count=5, status=1, account_no="A", plat_source=2)]))
    out = await m.run(user_id="1")
    b = out["balances"][0]
    assert b["currency"] == "EUR" and b["status"] == "冻结" and b["plat_source"] == "unlimitpay"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_balance_mapping.py -v`
Expected: FAIL（currency 实得 "未知(6)"/旧码吐 6；无 plat_source 键）

- [ ] **Step 4: 改 `query_balance.py`**

- `_CURRENCY` 补全为 Task 1 同款 11 值字典（建议在 base 里集中定义 `CURRENCY` 共享，避免再次漂移）。
- `_STATUS` 改 `{0:"正常",1:"冻结"}`。
- 新增 `_PLAT = {1:"tevaupay",2:"unlimitpay",3:"skydao"}`。
- SQL 的 SELECT 增加 `plat_source`；输出每行增加 `"plat_source": label(_PLAT, r.get("plat_source"))`。
- 所有枚举翻译改用 `label(...)`。

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_balance_mapping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_query_balance_mapping.py src/ai_engine/agent/tools/query_balance.py src/ai_engine/agent/tools/base.py
git commit -m "fix(tools): query_balance 补全币种枚举(11值)+冻结措辞+platSource 区分"
```

---

## Task 5: 修 query_card 卡状态枚举 + 接入冻结原因表

**审计依据**：`CardStatusEnum` 漏 13添加中/14待激活（14 是用户能持有的活跃态）；币种 code 3 应为 ARB_ETH；工具承诺答"卡为什么被冻结"，但真实冻结原因在独立表 `t_tevaupay_bank_card_freeze_history`（`freeze_reason` 编码 + `reason_desc` + 自动解冻时间），主表 `card_status_description` 只是卡方状态串。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_card.py`
- Test: `server/tests/test_query_card_mapping.py`

- [ ] **Step 1: RDS 核对冻结表列 + freeze_reason 取值 + 后端枚举**

```python
await R.q(U, "SELECT column_name,column_comment FROM information_schema.columns WHERE table_schema='unlimitpay_test' AND table_name='t_tevaupay_bank_card_freeze_history' ORDER BY ordinal_position")
await R.q(U, "SELECT freeze_reason v,COUNT(*) c FROM t_tevaupay_bank_card_freeze_history GROUP BY freeze_reason ORDER BY c DESC")
```
并 grep 后端 `FreezeReasonEnum`（`TevauPay-Service` 内）确认编码含义。记录隔离列（`user_id` + `target_id`/`target_type`=1卡2账户）与时间列名，据此填实下方 FREEZE_SQL 与 `_FREEZE_REASON`。

- [ ] **Step 2: 写失败测试**

```python
import pytest
class FakeDB:
    def __init__(self, cards, freezes): self.cards=cards; self.freezes=freezes; self.calls=0
    async def fetch_all(self, sql, params=(), limit=100):
        self.calls += 1
        return list(self.cards) if "t_tevaupay_bank_card_user" in sql else list(self.freezes)

@pytest.mark.asyncio
async def test_card_status_14_pending_activate(monkeypatch):
    import ai_engine.agent.tools.query_card as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(
        [dict(id=1, card_number="****0823", card_status=14, card_status_description=None,
              card_balance=0, card_currency=2, card_type=1, expiry_date=None,
              reject_reason=None, cancel_card_reason=None, card_alias_name=None,
              active_time=None, create_time=None, three_card_id="T1")], []))
    out = await m.run(user_id="1")
    assert out["cards"][0]["card_status"] == "待激活"   # 旧代码吐 "未知(14)"

@pytest.mark.asyncio
async def test_frozen_card_attaches_reason(monkeypatch):
    import ai_engine.agent.tools.query_card as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(
        [dict(id=1, card_number="****0823", card_status=9, card_status_description="x",
              card_balance=0, card_currency=2, card_type=1, expiry_date=None,
              reject_reason=None, cancel_card_reason=None, card_alias_name=None,
              active_time=None, create_time=None, three_card_id="T1")],
        [dict(freeze_reason=1, reason_desc="黑名单商户交易", create_time="2026-05-01 00:00:00")]))
    out = await m.run(user_id="1")
    assert out["cards"][0]["freeze_reason"] == "黑名单商户交易"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_card_mapping.py -v`
Expected: FAIL

- [ ] **Step 4: 改 `query_card.py`**

- `_CARD_STATUS` 补 `13:"添加中",14:"待激活"`，并核对 1/9/10 措辞与 `CardStatusEnum` 一致。
- 币种字典改用 base 的共享 `CURRENCY`（3=ARB_ETH）。
- 新增 `_FREEZE_REASON`（按 Step 1 核对结果，形如 `{1:"黑名单商户交易",2:"超额消费负数",3:"不活跃扣费不足",4:"人工冻结"}`）。
- 对 `card_status` 处于冻结态（如 9）的卡，按 user_id+卡定位查冻结表最新一条，给出 `freeze_reason`/`reason_desc`/自动解冻时间：
```python
FREEZE_SQL = """
SELECT freeze_reason, reason_desc, create_time
FROM t_tevaupay_bank_card_freeze_history
WHERE user_id=%s
ORDER BY id DESC LIMIT 5
"""  # 字段名以 Step 1 核对为准；如有 target_id/target_type 需按卡进一步过滤
```
- 全部枚举翻译改 `label(...)`。

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_card_mapping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_query_card_mapping.py src/ai_engine/agent/tools/query_card.py src/ai_engine/agent/tools/base.py
git commit -m "fix(tools): query_card 补卡状态13/14+币种对齐+接入冻结原因表"
```

---

## Task 6: 修 query_bu_order 枚举（删捏造值）+ 失败原因覆盖

**审计依据**：`OrderTypeEnum` 工具捏造 25/26、漏 9 个真实类型；status 捏造 6"审核中"（订单域无此值）；失败原因在 `t_nexus_trans_exception`（`reason`/`error_trans_code`/`exception_type`），工具没查。隔离 `tenant_id=%s` 本身安全。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_bu_order.py`
- Test: `server/tests/test_query_bu_order_mapping.py`

- [ ] **Step 1: RDS(nexus) 核对 order_type/status 实际取值 + 异常表列**

```python
async def fn(U, N):
    R.show("order_type", await R.q(N, "SELECT order_type v,COUNT(*) c FROM t_nexus_order_info GROUP BY order_type ORDER BY c DESC"))
    R.show("status", await R.q(N, "SELECT status v,COUNT(*) c FROM t_nexus_order_info GROUP BY status ORDER BY c DESC"))
    R.show("trans_exception列", await R.q(N, "SELECT column_name FROM information_schema.columns WHERE table_schema='tevau_nexus_test' AND table_name='t_nexus_trans_exception' ORDER BY ordinal_position"))
```
Expected：status 无 6；order_type 不含 25/26（确认捏造）；异常表存在 reason 等列。以 `OrderTypeEnum`（`TevauNexus-Service`）为准建表。

- [ ] **Step 2: 写失败测试**

```python
import pytest
class FakeDB:
    def __init__(self, rows): self._rows = rows
    async def fetch_all(self, sql, params=(), limit=100): return list(self._rows)

@pytest.mark.asyncio
async def test_real_order_type_and_no_fake_status(monkeypatch):
    import ai_engine.agent.tools.query_bu_order as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([
        dict(order_sn="O1", trade_order_sn="T1", order_type=11, status=4,
             trade_amount=1, fee=0, channel_amount=1, channel_fee=0, currency=2,
             create_time=None, end_time=None, remark=None)]))
    out = await m.run(tenant_id="t1")
    o = out["orders"][0]
    assert o["order_type"] == "开卡订单(CID)"   # 旧代码吐 "未知(11)"
    # 确认 status 字典里没有捏造的 6
    assert 6 not in m._STATUS
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_bu_order_mapping.py -v`
Expected: FAIL

- [ ] **Step 4: 改 `query_bu_order.py`**

- 按 `OrderTypeEnum` 重建 `_ORDER_TYPE`（删 25/26，补 11开卡CID/12开卡BAC/13企业ENT/17KYC月费/20 3DS次数扣费/21 3DS月费/22物流费用/23批量出卡/24ChargeBack，保留 18交易/19预付款充值；其余以 Step1 枚举为准）。
- `_STATUS` 删除 `6`，保留 `{0:待处理,1:已完成,2:已取消,3:已退款,4:失败,5:部分退款}`。
- 枚举翻译改 `label(...)`。
- 失败订单（status=4）附原因：查 `t_nexus_trans_exception`（带 `tenant_id=%s` 隔离 + 按 order_sn 关联），输出 `failure_reason`。具体列名/关联键以 Step 1 核对为准。

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_bu_order_mapping.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_query_bu_order_mapping.py src/ai_engine/agent/tools/query_bu_order.py
git commit -m "fix(tools): query_bu_order 按真实枚举重建order_type/status+接入失败原因"
```

---

## Task 7: 重写 query_bu_request_log（整表/整列都是臆造的）

**审计依据**：表名 `t_nexus_third_request_log` 后端不存在；9 个 select 列里 8 个不存在；四报文模型臆造（真实只有单个 `response_body`）；channel `1` 应为 Reap 非 rampable。真实表为 `t_nexus_transaction_issuer_log`（`TransactionIssuerLog`，含 `transaction_order_no/url/response_body/transaction_status/transaction_time/create_time/tenant_id` 等）。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_bu_request_log.py`
- Test: `server/tests/test_query_bu_request_log_mapping.py`

- [ ] **Step 1: RDS(nexus) 核对真实表与列**

```python
async def fn(U, N):
    R.show("表是否存在", await R.q(N, "SELECT table_name FROM information_schema.tables WHERE table_schema='tevau_nexus_test' AND table_name IN ('t_nexus_third_request_log','t_nexus_transaction_issuer_log')"))
    R.show("真实列", await R.q(N, "SELECT column_name,column_comment FROM information_schema.columns WHERE table_schema='tevau_nexus_test' AND table_name='t_nexus_transaction_issuer_log' ORDER BY ordinal_position"))
```
Expected：`t_nexus_third_request_log` 不存在；`t_nexus_transaction_issuer_log` 存在。以真实列名填实下方 SQL。

- [ ] **Step 2: 写失败测试**

```python
import pytest
class FakeDB:
    def __init__(self, rows): self._rows = rows
    async def fetch_all(self, sql, params=(), limit=100): return list(self._rows)

@pytest.mark.asyncio
async def test_uses_real_table_and_columns(monkeypatch):
    import ai_engine.agent.tools.query_bu_request_log as m
    assert "t_nexus_transaction_issuer_log" in m.SQL
    assert "t_nexus_third_request_log" not in m.SQL
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([
        dict(transaction_order_no="T1", url="https://issuer/x", transaction_status=1,
             transaction_time=None, create_time=None, response_body="{}")]))
    out = await m.run(tenant_id="t1")
    assert out["logs"][0]["transaction_order_no"] == "T1"
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_query_bu_request_log_mapping.py -v`
Expected: FAIL（旧 SQL 含 third_request_log）

- [ ] **Step 4: 重写 `query_bu_request_log.py`**

```python
from typing import Any
from ai_engine.agent.tools.base import Tool, register, label
from ai_engine.persistence.business_db import get_db

# 真实表：交易三方发卡方请求日志（列名以 Task7-Step1 核对结果为准）
SQL = """
SELECT transaction_order_no, url, transaction_status, transaction_time,
       create_time, response_body
FROM t_nexus_transaction_issuer_log
WHERE tenant_id=%s
ORDER BY create_time DESC
"""

async def run(tenant_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前 BU 的三方发卡方请求日志（下游 issuer 调用记录），排查下游交易请求用。"""
    db = get_db("nexus")
    rows = await db.fetch_all(SQL, (tenant_id,), limit=20)
    logs = []
    for r in rows:
        item = {
            "transaction_order_no": r.get("transaction_order_no"),
            "url": r.get("url"),
            "status": r.get("transaction_status"),
            "transaction_time": str(r["transaction_time"]) if r.get("transaction_time") else None,
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
        }
        if unmask:
            item["response_body"] = r.get("response_body")
        logs.append(item)
    return {"logs": logs, "count": len(logs)}

register(Tool(
    name="query_bu_request_log",
    description="查询当前 BU 的三方发卡方请求日志（下游 issuer 调用），排查某笔下游交易请求时用。",
    input_schema={"type":"object","properties":{"tenant_id":{"type":"string"}},"required":[]},
    handler=run, requires_subject_id=True, subject_field="tenant_id", supports_unmask=True,
))
```
（若 Step 1 显示需要的列名不同，按真实列名调整 SELECT 与 item。）

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_query_bu_request_log_mapping.py -v`
Expected: PASS

- [ ] **Step 6: 真实库冒烟（验证不再报"表不存在"）**

用一个真实 tenant_id 跑工具，确认返回结构正常、无 SQL 错误。

- [ ] **Step 7: Commit**

```bash
git add tests/test_query_bu_request_log_mapping.py src/ai_engine/agent/tools/query_bu_request_log.py
git commit -m "fix(tools): query_bu_request_log 改用真实表 t_nexus_transaction_issuer_log"
```

---

## Task 8: 系统提示词加"工具边界自觉"护栏

**目的**：即使个别工具仍有覆盖盲区，AI 也不把"某工具查空/某字段"当成业务事实下绝对结论，尤其涉及钱、实名。

**Files:**
- Modify: 系统提示词文件（执行时先定位：`grep -rln "你是.*客服\|系统提示\|system" server/src/ai_engine/prompts/` 或 prompts 目录）
- Test: `server/tests/test_prompts_c_style.py`（在现有断言里加一条）

- [ ] **Step 1: 定位 C 端系统提示词文件**

Run: `grep -rln "客服\|交易\|实名" server/src/ai_engine/prompts/`
记录承载 C 端 system prompt 的文件路径。

- [ ] **Step 2: 写失败测试**

在 `test_prompts_c_style.py` 增加：
```python
def test_prompt_has_tool_boundary_guardrail():
    from ai_engine.prompts... import <load_c_prompt>   # 按现有加载方式
    text = <load_c_prompt>()
    assert "查不到不代表" in text or "不要把工具查空当作" in text
```

- [ ] **Step 3: 运行确认失败**

Run: `.venv/bin/pytest tests/test_prompts_c_style.py -k boundary -v`
Expected: FAIL

- [ ] **Step 4: 在提示词中加入一段**

```
工具结果使用纪律：
- 工具查不到记录，只代表"该工具覆盖的范围内没查到"，不代表用户没有相关业务。不要对用户说"您没有交易/没有记录"这类绝对结论；应说"我在X范围内没查到，可能在其它范围，帮您进一步核实或转人工"。
- 涉及金额、实名(KYC)、卡状态等高敏判断，若工具返回的字段含"未知(数字)"或多个状态字段相互矛盾，不要替用户下结论，如实说明并建议核实/转人工。
- KYC 以 user_kyc_status（用户中心口径）为准向用户解释，audit_status 仅作内部细节参考。
```

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/pytest tests/test_prompts_c_style.py -k boundary -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_prompts_c_style.py src/ai_engine/prompts/...
git commit -m "feat(prompt): 加工具边界自觉护栏(查空非绝对/高敏不替用户下结论)"
```

---

## Task 9: 全量回归 + 部署生效

- [ ] **Step 1: 全量单测**

Run: `.venv/bin/pytest -q`
Expected: 全绿（含新增 7 个映射测试 + label/prompt 测试）。

- [ ] **Step 2: 真实库逐工具冒烟清单**（取真实 user_id / tenant_id 各跑一次，眼检无"未知(数字)"、无 SQL 错误、覆盖正确）：query_transaction / query_kyc / query_user / query_balance / query_card / query_bu_order / query_bu_request_log。

- [ ] **Step 3: 重建后端容器生效**（按项目惯例，改后端必须 rebuild，restart 不够）

Run: `docker compose up -d --build api`
确认启动日志无异常后，在 APP 内复测最初两个场景：查流水应能看到卡交易/奖励；查 KYC 状态应与用户中心一致。

---

## Self-Review 记录

- **Spec 覆盖**：7 个工具各一个修复 Task（1=transaction,2=user,3=kyc,4=balance,5=card,6=bu_order,7=bu_request_log）+ 结构性 Task 0(诚实标签)/Task 8(提示词护栏)/Task 9(回归)。两个用户实测场景分别由 Task 1 与 Task 2/3 覆盖。
- **占位符**：枚举字典与 SQL 均给出真实值；少数列名/枚举（freeze_reason、nexus 异常表与 issuer_log 列、提示词文件路径）标注"以对应 Step 的 RDS/grep 核对结果为准"——这是有意的"先核对后填实"步骤，非 TODO。
- **类型一致**：`label` / `scope_note` 在 Task 0 定义，后续 Task 统一引用；共享 `CURRENCY` 字典建议集中在 base（Task1/4/5 复用）。
- **风险**：B 端(nexus)两表的列名以后端代码推导为主，Task6/7 的 Step1 强制连真实 nexus 库核对后再落地，避免二次漂移。
