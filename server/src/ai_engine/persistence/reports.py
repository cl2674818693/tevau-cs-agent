"""自定义报表：CRUD + 安全执行引擎。

执行用白名单 source 表 / 维度列 / metric op / filter op；所有 filter value 走绑定参数。
不接受任意字符串拼接 SQL。
"""

import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_SOURCES: dict[str, set[str]] = {
    "agent_ratings": {
        "id", "conversation_id", "staff_id", "subject_id", "user_type",
        "rating", "created_at",
    },
    "qa_reviews": {
        "id", "conversation_id", "reviewer_staff_id", "scorecard_id",
        "score", "tags", "created_at",
    },
    "staff_actions": {"id", "conversation_id", "staff_id", "action", "at"},
    "daily_token_usage_by_model": {
        "subject_id", "user_type", "date", "model",
        "input_tokens", "output_tokens",
    },
    "tool_audits": {
        "id", "conversation_id", "tool_name", "rejected", "is_empty",
        "subject_id", "user_type", "created_at",
    },
    "message_feedback": {
        "id", "conversation_id", "message_id", "rating",
        "subject_id", "user_type", "created_at",
    },
}

_FILTER_OPS = {"=", "!=", ">", ">=", "<", "<=", "LIKE"}
_METRIC_OPS = {"count", "sum", "avg", "min", "max", "count_if"}


def _validate_dims(source: str, dims: list[str]) -> None:
    cols = _SOURCES.get(source)
    if cols is None:
        raise ValueError(f"unknown source: {source}")
    for d in dims:
        if d not in cols:
            raise ValueError(f"unknown dim {d} in source {source}")


def _validate_metrics(source: str, metrics: list[dict[str, Any]]) -> None:
    cols = _SOURCES.get(source, set())
    for m in metrics:
        op = m.get("op", "")
        col = m.get("col", "")
        if op not in _METRIC_OPS:
            raise ValueError(f"unknown metric op: {op}")
        if col != "*" and col not in cols:
            raise ValueError(f"unknown metric col {col} in source {source}")
        if op == "count_if":
            if "match" not in m or not isinstance(m["match"], (str, int)):
                raise ValueError("count_if requires 'match' value")


def _validate_filters(source: str, filters: list[dict[str, Any]]) -> None:
    cols = _SOURCES.get(source, set())
    for f in filters:
        col = f.get("col", "")
        op = f.get("op", "")
        if col not in cols:
            raise ValueError(f"unknown filter col {col} in source {source}")
        if op not in _FILTER_OPS:
            raise ValueError(f"unknown filter op: {op}")


async def create_definition(
    name: str,
    source: str,
    dims: list[str],
    filters: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    owner: str,
) -> int:
    _validate_dims(source, dims)
    _validate_filters(source, filters)
    _validate_metrics(source, metrics)
    return await db.insert_returning_id(
        "INSERT INTO report_definitions(name, source, dims_json, filters_json, "
        "metrics_json, owner, created_at) "
        "VALUES (:n, :s, :d, :f, :m, :o, :now) RETURNING id",
        {
            "n": name, "s": source,
            "d": json.dumps(dims, ensure_ascii=False),
            "f": json.dumps(filters, ensure_ascii=False),
            "m": json.dumps(metrics, ensure_ascii=False),
            "o": owner, "now": now_str(),
        },
    )


async def list_definitions() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, name, source, dims_json, filters_json, metrics_json, owner, created_at "
        "FROM report_definitions ORDER BY id DESC"
    )


async def get_definition(report_id: int) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, name, source, dims_json, filters_json, metrics_json, owner, created_at "
        "FROM report_definitions WHERE id = :id",
        {"id": int(report_id)},
    )


async def delete_definition(report_id: int) -> None:
    await db.execute(
        "DELETE FROM report_definitions WHERE id = :id", {"id": int(report_id)}
    )


async def execute(
    source: str,
    dims: list[str],
    filters: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    limit: int = 1000,
) -> dict[str, Any]:
    _validate_dims(source, dims)
    _validate_filters(source, filters)
    _validate_metrics(source, metrics)

    select_parts: list[str] = list(dims)
    binds: dict[str, Any] = {"_lim": int(limit)}
    for i, m in enumerate(metrics):
        op = str(m["op"]).upper()
        col = str(m["col"])
        alias = str(m.get("alias", f"{op}_{col}"))
        if not alias.replace("_", "").isalnum():
            raise ValueError(f"invalid alias: {alias}")
        if op == "COUNT_IF":
            bind_key = f"_mv{i}"
            select_parts.append(
                f"SUM(CASE WHEN {col} = :{bind_key} THEN 1 ELSE 0 END) AS {alias}"
            )
            binds[bind_key] = m["match"]
        elif col == "*":
            select_parts.append(f"{op}(*) AS {alias}")
        else:
            select_parts.append(f"{op}({col}) AS {alias}")

    where_clauses: list[str] = []
    for i, f in enumerate(filters):
        col = str(f["col"])
        op = str(f["op"])
        key = f"v{i}"
        where_clauses.append(f"{col} {op} :{key}")
        binds[key] = f["val"]

    sql = f"SELECT {', '.join(select_parts)} FROM {source}"  # noqa: S608 (白名单)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if dims:
        sql += " GROUP BY " + ", ".join(dims)
    sql += " LIMIT :_lim"

    rows = await db.fetch_all(sql, binds)
    return {"sql": sql, "rows": rows}
