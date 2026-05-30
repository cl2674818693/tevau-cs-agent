"""Token 成本聚合 + 模型单价 CRUD。

单价存 'per 1k tokens × 10000'（整数避浮点）。
聚合结果可选 with_cost=True 时换算成 currency 金额。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def upsert_pricing(
    model: str,
    input_price_x10000: int,
    output_price_x10000: int,
    currency: str = "USD",
) -> None:
    existing = await db.fetch_one(
        "SELECT model FROM model_pricing WHERE model = :m", {"m": model}
    )
    now = now_str()
    if existing is None:
        await db.execute(
            "INSERT INTO model_pricing(model, input_price_per_1k_x10000, "
            "output_price_per_1k_x10000, currency, updated_at) "
            "VALUES (:m, :i, :o, :c, :now)",
            {
                "m": model,
                "i": int(input_price_x10000),
                "o": int(output_price_x10000),
                "c": currency,
                "now": now,
            },
        )
    else:
        await db.execute(
            "UPDATE model_pricing SET input_price_per_1k_x10000 = :i, "
            "output_price_per_1k_x10000 = :o, currency = :c, updated_at = :now "
            "WHERE model = :m",
            {
                "m": model,
                "i": int(input_price_x10000),
                "o": int(output_price_x10000),
                "c": currency,
                "now": now,
            },
        )


async def list_pricing() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT model, input_price_per_1k_x10000, output_price_per_1k_x10000, "
        "currency, updated_at FROM model_pricing ORDER BY model"
    )


async def usage_by_model(
    date_from: str | None,
    date_to: str | None,
    user_type: str | None = None,
    with_cost: bool = False,
) -> list[dict[str, Any]]:
    # M3c: 优先读 by-model 拆分表；新表无数据时回退旧表（M2 兼容）。
    rows = await db.fetch_all(
        "SELECT model, "
        "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
        "FROM daily_token_usage_by_model "
        "WHERE (CAST(:df AS TEXT) IS NULL OR date >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR date <= :dt) "
        "AND (CAST(:ut AS TEXT) IS NULL OR user_type = :ut) "
        "GROUP BY model "
        "ORDER BY model",
        {"df": date_from, "dt": date_to, "ut": user_type},
    )
    if not rows:
        rows = await db.fetch_all(
            "SELECT COALESCE(model, '(unknown)') AS model, "
            "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
            "FROM daily_token_usage "
            "WHERE (CAST(:df AS TEXT) IS NULL OR date >= :df) "
            "AND (CAST(:dt AS TEXT) IS NULL OR date <= :dt) "
            "AND (CAST(:ut AS TEXT) IS NULL OR user_type = :ut) "
            "GROUP BY COALESCE(model, '(unknown)') "
            "ORDER BY model",
            {"df": date_from, "dt": date_to, "ut": user_type},
        )
    result = [
        {
            "model": r["model"],
            "input_tokens": int(r["input_tokens"] or 0),
            "output_tokens": int(r["output_tokens"] or 0),
        }
        for r in rows
    ]
    if not with_cost:
        return result
    pricing_rows = await list_pricing()
    pricing = {p["model"]: p for p in pricing_rows}
    for item in result:
        p = pricing.get(item["model"])
        if p is None:
            item["currency"] = None
            item["input_cost"] = 0.0
            item["output_cost"] = 0.0
            item["total_cost"] = 0.0
            continue
        in_cost = item["input_tokens"] / 1000 * int(p["input_price_per_1k_x10000"]) / 10000
        out_cost = item["output_tokens"] / 1000 * int(p["output_price_per_1k_x10000"]) / 10000
        item["currency"] = p["currency"]
        item["input_cost"] = round(in_cost, 4)
        item["output_cost"] = round(out_cost, 4)
        item["total_cost"] = round(in_cost + out_cost, 4)
    return result
