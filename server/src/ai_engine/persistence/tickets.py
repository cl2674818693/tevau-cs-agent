import json
from datetime import UTC, datetime, timedelta

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_ticket(external_id: str, conversation_id: int, payload: dict[str, object]) -> None:
    await db.execute(
        "INSERT INTO tickets(external_id, conversation_id, payload_json, current_severity, "
        "created_at) VALUES (:eid, :cid, :payload, :sev, :now)",
        {
            "eid": external_id,
            "cid": conversation_id,
            "payload": json.dumps(payload, ensure_ascii=False),
            "sev": payload.get("severity"),
            "now": now_str(),
        },
    )


async def append_ticket_event(
    external_id: str,
    event: str,
    actor: str | None,
    comment: str | None,
    raw: dict[str, object] | None = None,
) -> None:
    await db.execute(
        "INSERT INTO ticket_events(external_id, event, actor, comment, raw_json, created_at) "
        "VALUES (:eid, :event, :actor, :comment, :raw, :now)",
        {
            "eid": external_id,
            "event": event,
            "actor": actor,
            "comment": comment,
            "raw": json.dumps(raw or {}, ensure_ascii=False),
            "now": now_str(),
        },
    )


async def find_open_ticket_for_subject(
    subject_id: str, user_type: str, within_hours: int = 24
) -> str | None:
    """spec §11 工单风暴对策：返回该 subject 在窗口内未关闭(closed)的工单 external_id。"""
    subject_key = "user_id" if user_type == "c" else "bu_id"
    # 时间窗口在 Python 算 cutoff（方言无关，替代 SQLite 专有 datetime('now','-N hours')）
    cutoff = (datetime.now(UTC) - timedelta(hours=int(within_hours))).strftime("%Y-%m-%d %H:%M:%S")
    rows = await db.fetch_all(
        """SELECT t.external_id, t.payload_json FROM tickets t
           WHERE t.created_at >= :cutoff
             AND NOT EXISTS (
                 SELECT 1 FROM ticket_events e
                 WHERE e.external_id = t.external_id AND e.event = 'closed'
             )
           ORDER BY t.created_at DESC""",
        {"cutoff": cutoff},
    )
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        if payload.get(subject_key) == subject_id and payload.get("user_type") == user_type:
            return str(row["external_id"])
    return None


async def update_ticket_severity(external_id: str, severity: str) -> None:
    """spec 7.2: 受理人在事项中心覆盖 severity -> 更新本地镜像。"""
    await db.execute(
        "UPDATE tickets SET current_severity=:sev WHERE external_id=:eid",
        {"sev": severity, "eid": external_id},
    )


async def list_tickets(
    open_only: bool = False,
    severity: str | None = None,
    category: str | None = None,
    limit: int = 50,
    before_id: str | None = None,
) -> list[dict[str, object]]:
    """运营只读工单列表（最新在前）。外部事项中心是状态真源，本地仅做只读镜像。

    - open_only: 只看未关闭（沿用 NOT EXISTS(event='closed') 现算逻辑）
    - severity: 按 current_severity 镜像列过滤
    - category: 按 payload_json.category 过滤（在 Python 侧筛，避免 JSON 方言差异）
    - before_id: 游标分页，返回 created_at 早于该游标（external_id）的工单

    返回每条含：external_id / category / severity / conversation_id / created_at / closed。
    WHERE 片段全为固定字符串，值全走绑定参数，不拼用户输入。
    """
    where = [
        "NOT EXISTS (SELECT 1 FROM ticket_events e "
        "WHERE e.external_id = t.external_id AND e.event = 'closed')"
    ] if open_only else []
    binds: dict[str, object] = {"lim": limit}
    if severity is not None:
        where.append("t.current_severity = :sev")
        binds["sev"] = severity
    if before_id is not None:
        # 游标：取该 external_id 的 created_at 之前的工单（created_at 单调递增的字符串时间戳）
        cur = await db.fetch_one(
            "SELECT created_at FROM tickets WHERE external_id = :bid", {"bid": before_id}
        )
        if cur is not None:
            where.append("t.created_at < :cur_at")
            binds["cur_at"] = cur["created_at"]
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT t.external_id, t.conversation_id, t.payload_json, t.current_severity, "
        f"t.created_at FROM tickets t{clause} "
        "ORDER BY t.created_at DESC, t.external_id DESC LIMIT :lim"
    )
    rows = await db.fetch_all(sql, binds)
    # closed 态现算：本次查询的 external_id 是否有 closed 事件
    closed_set: set[str] = set()
    if rows:
        ext_ids = [str(r["external_id"]) for r in rows]
        placeholders = ",".join(f":e{i}" for i in range(len(ext_ids)))
        ev_rows = await db.fetch_all(
            f"SELECT DISTINCT external_id FROM ticket_events "
            f"WHERE event = 'closed' AND external_id IN ({placeholders})",
            {f"e{i}": eid for i, eid in enumerate(ext_ids)},
        )
        closed_set = {str(r["external_id"]) for r in ev_rows}
    out: list[dict[str, object]] = []
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        cat = payload.get("category")
        if category is not None and cat != category:
            continue
        ext = str(row["external_id"])
        out.append(
            {
                "external_id": ext,
                "category": cat,
                "severity": row["current_severity"],
                "conversation_id": row["conversation_id"],
                "created_at": row["created_at"],
                "closed": ext in closed_set,
            }
        )
    return out


async def get_ticket(external_id: str) -> dict[str, object] | None:
    row = await db.fetch_one(
        """SELECT external_id, conversation_id, payload_json, current_severity, created_at
           FROM tickets WHERE external_id=:eid""",
        {"eid": external_id},
    )
    if not row:
        return None
    evs = await db.fetch_all(
        "SELECT event, actor, comment, created_at FROM ticket_events "
        "WHERE external_id=:eid ORDER BY id",
        {"eid": external_id},
    )
    row["events"] = evs
    return row
