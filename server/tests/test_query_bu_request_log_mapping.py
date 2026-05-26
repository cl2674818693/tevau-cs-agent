"""Task 7: query_bu_request_log 改用真实表 t_nexus_transaction_issuer_log。

真实库核对（tevau_nexus_test）+ 后端佐证：
- 真实表：t_nexus_transaction_issuer_log（交易三方发卡方请求日志，243286 行真实数据）。
  实体类 TransactionIssuerLog.java（@TableName("t_nexus_transaction_issuer_log")）。
- 旧版本查的 t_nexus_third_request_log 在库中也存在（5319 行），但其"四报文"模型
  （tenant 请求/响应 + third 请求/响应）描述的不是发卡方请求日志，列与本工具语义不符；
  本工具按计划重写为真实的发卡方请求日志表。
- 真实列（information_schema 核对）：transaction_order_no / url / transaction_status /
  transaction_time / create_time / response_body / transaction_type / pay_type / risk_flag / tenant_id。
- transaction_status 枚举以 LogEnum.java 为准（写入方 CardProviderHandlerLogServiceImpl 用 LogEnum）：
  1 成功 / 2 失败 / 3 请求中。与列注释及数据分布（1 占 235423/243286）一致。
  注意：不要误用 TransactionStatusEnum（那是另一套 1待处理/2处理中/3成功…，本表不用）。
- 隔离列 tenant_id（varchar(32)，存在 NULL 脏数据），WHERE tenant_id=%s 严格等值，NULL 行不匹配。
- response_body 含发卡方返回报文（可能有卡号/金额/客户信息），放 unmask 分支。
"""

import pytest


class FakeDB:
    def __init__(self, rows):
        self._rows = rows
        self.calls = []

    async def fetch_all(self, sql, params=(), limit=100):
        self.calls.append((sql, params, limit))
        return list(self._rows)


def _row(**kw):
    base = dict(
        transaction_order_no="T1",
        url="https://issuer/x",
        transaction_status=1,
        transaction_type=1,
        transaction_time=None,
        create_time=None,
        response_body="{}",
    )
    base.update(kw)
    return base


def test_uses_real_table_not_fake():
    import ai_engine.agent.tools.query_bu_request_log as m

    assert "t_nexus_transaction_issuer_log" in m.SQL
    assert "t_nexus_third_request_log" not in m.SQL


def test_isolation_strict_tenant():
    import ai_engine.agent.tools.query_bu_request_log as m

    # 严格等值隔离，防 NULL 脏数据跨租户泄露
    assert "tenant_id=%s" in m.SQL


@pytest.mark.asyncio
async def test_maps_real_columns(monkeypatch):
    import ai_engine.agent.tools.query_bu_request_log as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_row(transaction_order_no="T1")]))
    out = await m.run(tenant_id="t1")
    assert out["logs"][0]["transaction_order_no"] == "T1"
    assert out["logs"][0]["url"] == "https://issuer/x"


@pytest.mark.asyncio
async def test_transaction_status_translated_logenum(monkeypatch):
    import ai_engine.agent.tools.query_bu_request_log as m

    # LogEnum: 1 成功 / 2 失败 / 3 请求中（本表权威映射）
    assert m._STATUS[1] == "成功"
    assert m._STATUS[2] == "失败"
    assert m._STATUS[3] == "请求中"

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_row(transaction_status=2)]))
    out = await m.run(tenant_id="t1")
    assert out["logs"][0]["transaction_status"] == "失败"


@pytest.mark.asyncio
async def test_response_body_only_when_unmask(monkeypatch):
    import ai_engine.agent.tools.query_bu_request_log as m

    rows = [_row(response_body="SECRET-BODY")]
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(rows))

    masked = await m.run(tenant_id="t1", unmask=False)
    assert "response_body" not in masked["logs"][0]

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_row(response_body="SECRET-BODY")]))
    unmasked = await m.run(tenant_id="t1", unmask=True)
    assert "SECRET-BODY" in (unmasked["logs"][0].get("response_body") or "")


@pytest.mark.asyncio
async def test_empty_tenant_returns_empty(monkeypatch):
    import ai_engine.agent.tools.query_bu_request_log as m

    out = await m.run(tenant_id="")
    assert out["logs"] == []
    assert out["count"] == 0


@pytest.mark.asyncio
async def test_query_params_isolated_by_tenant(monkeypatch):
    import ai_engine.agent.tools.query_bu_request_log as m

    fake = FakeDB([_row()])
    monkeypatch.setattr(m, "get_db", lambda name: fake)
    await m.run(tenant_id="t1")
    assert fake.calls, "应执行查询"
    sql, params, limit = fake.calls[0]
    assert "t1" in params
    assert limit == 20
