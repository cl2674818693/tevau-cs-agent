"""Task 6: query_bu_order 真实枚举 + 失败原因接入。

枚举核对来源（双重）：
- 真实库 tevau_nexus_test.t_nexus_order_info 的列注释 + GROUP BY 取值
- 后端 OrderTypeEnum.java（TevauNexus-Service）

关键事实（与计划假设冲突，以真实库为准）：
- order_type 25/26 是真实类型（提币订单/币种兑换订单），有真实数据，不删。
  捏造的应删值在真实库中并不存在（计划误以为 25/26 是捏造）。
- status 6（审核中）是真实状态（列注释 + 10 行真实数据），不删。
- 异常表 t_nexus_trans_exception 无 order_sn / trade_order_sn 关联键；
  其 trans_id 是卡网 txId（tid_xxx），与订单 order_sn(CD/CT...) 不匹配（JOIN=0）。
  唯一可用的隔离关联是 tenant_id + card_id，其中订单侧用 third_card_id（UUID）
  对应异常表 card_id（UUID）。因此失败原因为"该卡近期异常"卡级线索，非订单级精确归因。
"""

import pytest


class FakeDB:
    def __init__(self, orders, excs=None):
        self.orders = orders
        self.excs = excs or []
        self.calls = []

    async def fetch_all(self, sql, params=(), limit=100):
        self.calls.append((sql, params))
        if "t_nexus_trans_exception" in sql:
            return list(self.excs)
        return list(self.orders)

    async def fetch_one(self, sql, params=()):
        self.calls.append((sql, params))
        if "t_nexus_trans_exception" in sql:
            return self.excs[0] if self.excs else None
        return self.orders[0] if self.orders else None


def _order(**kw):
    base = dict(
        order_sn="O1", trade_order_sn="T1", order_type=11, status=4,
        third_card_id="card-uuid-1",
        trade_amount=1, fee=0, channel_amount=1, channel_fee=0, currency="USD",
        create_time=None, end_time=None, remark=None,
    )
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_real_order_type_translated(monkeypatch):
    import ai_engine.agent.tools.query_bu_order as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_order(order_type=11)]))
    out = await m.run(tenant_id="t1")
    o = out["orders"][0]
    # 11 在真实 OrderTypeEnum 是"开卡订单CID"，必须有中文，不得"未知"
    assert "未知" not in str(o["order_type"])
    assert o["order_type"] == "开卡订单CID"


@pytest.mark.asyncio
async def test_real_enums_present_and_no_fabricated(monkeypatch):
    import ai_engine.agent.tools.query_bu_order as m

    # 真实库存在的类型必须有映射
    for t in (1, 2, 3, 4, 11, 12, 13, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26):
        assert t in m._ORDER_TYPE, f"order_type {t} 应存在于真实枚举"
    # status 6（审核中）是真实状态，必须保留
    assert 6 in m._STATUS
    assert m._STATUS[6] == "审核中"
    # 真实订单 status 取值齐全
    for s in (0, 1, 2, 3, 4, 5, 6):
        assert s in m._STATUS


@pytest.mark.asyncio
async def test_failed_order_attaches_failure_reason(monkeypatch):
    import ai_engine.agent.tools.query_bu_order as m

    fake = FakeDB(
        orders=[_order(order_type=18, status=4, third_card_id="card-uuid-X")],
        excs=[
            dict(reason="[404] cardAccounting Not Found", error_trans_code="500",
                 trans_type="authorization", exception_type=2,
                 card_id="card-uuid-X", create_time=None),
        ],
    )
    monkeypatch.setattr(m, "get_db", lambda name: fake)
    out = await m.run(tenant_id="t1")
    o = out["orders"][0]
    assert o.get("failure_reason"), "失败订单应附 failure_reason"
    # 异常查询必须按 tenant_id 隔离
    exc_calls = [c for c in fake.calls if "t_nexus_trans_exception" in c[0]]
    assert exc_calls, "应查询异常表"
    for sql, params in exc_calls:
        assert "tenant_id=%s" in sql, "异常表查询必须带 tenant_id 隔离"
        assert "t1" in params, "tenant_id 必须作为参数传入"


@pytest.mark.asyncio
async def test_non_failed_order_no_exception_query(monkeypatch):
    import ai_engine.agent.tools.query_bu_order as m

    fake = FakeDB(orders=[_order(status=1)])  # 已完成
    monkeypatch.setattr(m, "get_db", lambda name: fake)
    out = await m.run(tenant_id="t1")
    o = out["orders"][0]
    assert o.get("failure_reason") in (None, "")
    exc_calls = [c for c in fake.calls if "t_nexus_trans_exception" in c[0]]
    assert not exc_calls, "非失败订单不应查异常表"
