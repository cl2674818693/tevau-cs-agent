"""单客服绩效详情聚合：复用 staff_metrics 的接管/解决/时长 + 满意度 + 质检均分。"""

from typing import Any

from ai_engine.persistence import admin_qa, agent_ratings, staff_metrics


async def compute_performance(
    staff_id: str, date_from: str | None, date_to: str | None
) -> dict[str, Any]:
    kpi_rows = await staff_metrics.compute_kpi(date_from, date_to)
    base: dict[str, Any] = {
        "staff_id": staff_id,
        "takeovers": 0,
        "releases": 0,
        "resolved": 0,
        "transfers": 0,
        "release_ratio": 0.0,
        "resolved_ratio": 0.0,
        "transfer_ratio": 0.0,
        "avg_handle_seconds": 0.0,
    }
    for row in kpi_rows:
        if row.get("staff_id") == staff_id:
            base.update(
                {
                    k: row[k]
                    for k in (
                        "takeovers",
                        "releases",
                        "resolved",
                        "transfers",
                        "release_ratio",
                        "resolved_ratio",
                        "transfer_ratio",
                        "avg_handle_seconds",
                    )
                }
            )
            break
    base["satisfaction"] = await agent_ratings.aggregate_by_staff(staff_id, date_from, date_to)
    base["qa"] = await admin_qa.avg_score_by_reviewer(staff_id, date_from, date_to)
    return base
