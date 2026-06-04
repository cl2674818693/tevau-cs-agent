"""E2E 验证脚本：6 个场景，不需要浏览器。

通过 host:8000 打容器 + 直连 PG 操作测试数据。
在 host 跑：cd server && uv run python scripts/e2e_dispatch.py

依赖：httpx, PyJWT, asyncpg（项目已有）
"""

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx
import jwt

API = os.environ.get("E2E_API", "http://localhost:8000")
PG_DSN = os.environ.get(
    "E2E_PG_DSN",
    "postgres://ai:ai_local_pw@localhost:5432/ai_engine",
)
STAFF_SECRET = "bb6c10b07f40e67efde34c95dcf0db9769c5e203eec8be4112d12ddb3d7fbd05"
BU_SECRET = "b036bcedce20400508c3288a38e2b07e04f342d50382e4e306a90a44ef50c401"

TENANT = "e2e-tenant-001"
AGENT_A = "e2e-agent-A"
AGENT_B = "e2e-agent-B"


def staff_token(staff_id: str, role: str = "agent") -> str:
    return jwt.encode(
        {"typ": "staff", "sub": staff_id, "role": role, "exp": int(time.time()) + 3600},
        STAFF_SECRET,
        algorithm="HS256",
    )


def bu_session(tenant_id: str) -> str:
    return jwt.encode(
        {"typ": "b", "sub": tenant_id, "exp": int(time.time()) + 3600},
        BU_SECRET,
        algorithm="HS256",
    )


def staff_headers(staff_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {staff_token(staff_id)}"}


def bu_cookies(tenant_id: str) -> dict[str, str]:
    return {"ai_engine_session": bu_session(tenant_id)}


async def reset(pg: asyncpg.Connection) -> None:
    """清空测试残留：删除测试 staff、conversations、tickets、presence。"""
    await pg.execute(
        "DELETE FROM ticket_events WHERE external_id IN "
        "(SELECT external_id FROM tickets WHERE conversation_id IN "
        "(SELECT id FROM conversations WHERE subject_id=$1))",
        TENANT,
    )
    await pg.execute("DELETE FROM tickets WHERE conversation_id IN (SELECT id FROM conversations WHERE subject_id=$1)", TENANT)
    await pg.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE subject_id=$1)", TENANT)
    await pg.execute("DELETE FROM conversations WHERE subject_id=$1", TENANT)
    await pg.execute("DELETE FROM staff_presence WHERE staff_id = ANY($1::text[])", [AGENT_A, AGENT_B])
    await pg.execute("DELETE FROM staff WHERE staff_id = ANY($1::text[])", [AGENT_A, AGENT_B])


async def seed_staff(pg: asyncpg.Connection, staff_id: str, role: str = "agent") -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    await pg.execute(
        "INSERT INTO staff(staff_id, role, display_name, password_hash, created_at) "
        "VALUES ($1, $2, $3, '', $4) ON CONFLICT(staff_id) DO UPDATE SET role=$2",
        staff_id, role, staff_id, now,
    )


async def new_conv(pg: asyncpg.Connection) -> int:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    row = await pg.fetchrow(
        "INSERT INTO conversations(user_type, subject_id, created_at) "
        "VALUES ('b', $1, $2) RETURNING id",
        TENANT, now,
    )
    assert row is not None
    return int(row["id"])


async def http_presence(client: httpx.AsyncClient, staff_id: str, status: str) -> dict:
    r = await client.post(
        f"{API}/staff/api/v1/presence",
        headers=staff_headers(staff_id),
        json={"status": status},
    )
    r.raise_for_status()
    return r.json()


async def http_request_human(client: httpx.AsyncClient, conv_id: int) -> tuple[int, dict]:
    r = await client.post(
        f"{API}/api/v1/conversations/{conv_id}/request-human",
        cookies=bu_cookies(TENANT),
        json={"reason": "e2e"},
    )
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {})


async def http_take(client: httpx.AsyncClient, staff_id: str, conv_id: int) -> int:
    r = await client.post(
        f"{API}/staff/api/v1/conversations/{conv_id}/take",
        headers=staff_headers(staff_id),
    )
    return r.status_code


async def get_assignment(pg: asyncpg.Connection, conv_id: int) -> tuple[str, str | None]:
    row = await pg.fetchrow(
        "SELECT mode, assigned_staff_id FROM conversations WHERE id=$1", conv_id
    )
    assert row is not None
    return row["mode"], row["assigned_staff_id"]


# ---- 场景 ----

async def scenario_1_least_loaded(client: httpx.AsyncClient, pg: asyncpg.Connection) -> str:
    """3 次 request-human → 应按最少在聊算法分发。预期：第 1 次和第 2 次各派一人；第 3 次按 tiebreaker。"""
    # A 和 B 都已 online（在 setup 里 heartbeat 过）
    convs = [await new_conv(pg) for _ in range(3)]
    assignments = []
    for cid in convs:
        code, body = await http_request_human(client, cid)
        if code != 200:
            return f"FAIL: request-human returned {code} body={body}"
        await asyncio.sleep(0.1)  # 防止时间戳 tiebreaker 让两次都派给同一个人
        _, sid = await get_assignment(pg, cid)
        assignments.append(sid)
    distinct = set(filter(None, assignments))
    if not distinct.issubset({AGENT_A, AGENT_B}):
        return f"FAIL: assignments contain unknown staff: {assignments}"
    if len(distinct) < 2:
        return f"WARN: 3 次派单全派给同一人，未发挥均衡: {assignments}"
    return f"PASS: 派单分布 = {assignments}"


async def scenario_2_timeout_release(client: httpx.AsyncClient, pg: asyncpg.Connection) -> str:
    """派给某人后等 60s+，watcher 应清空 assigned_staff_id。"""
    cid = await new_conv(pg)
    code, _ = await http_request_human(client, cid)
    if code != 200:
        return f"FAIL: request-human returned {code}"
    mode, sid_before = await get_assignment(pg, cid)
    if sid_before not in {AGENT_A, AGENT_B}:
        return f"FAIL: 未派给已知 staff: {sid_before}"
    # 加速：直接把 assigned_at 改成 70s 前，省 60 秒等待。Watcher 10s 一次。
    past = (datetime.now(UTC) - timedelta(seconds=70)).strftime("%Y-%m-%d %H:%M:%S")
    await pg.execute("UPDATE conversations SET assigned_at=$1 WHERE id=$2", past, cid)
    # 等 watcher 跑一次（最多 12 秒）
    for _ in range(12):
        await asyncio.sleep(1)
        _, sid = await get_assignment(pg, cid)
        if sid is None:
            return f"PASS: 派单被 watcher 清空，回开放池（前任 {sid_before}）"
    return f"FAIL: 12s 内 watcher 未清空派单（前任 {sid_before}）"


async def scenario_3_offline_releases_pending(client: httpx.AsyncClient, pg: asyncpg.Connection) -> str:
    """staff_a 关开关 → 派给 a 的未接管会话自动释放。"""
    # 先把 A B 都重新拉 online（前面场景里可能改变状态）
    await http_presence(client, AGENT_A, "online")
    await http_presence(client, AGENT_B, "online")
    cid = await new_conv(pg)
    # 手动派给 AGENT_A（避免随机派给 B）
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    await pg.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id=$1, assigned_at=$2 WHERE id=$3",
        AGENT_A, now, cid,
    )
    body = await http_presence(client, AGENT_A, "offline")
    if body.get("released_count", 0) < 1:
        return f"FAIL: released_count = {body.get('released_count')}"
    _, sid = await get_assignment(pg, cid)
    if sid is not None:
        return f"FAIL: assigned_staff_id 未清空: {sid}"
    return f"PASS: released_count={body['released_count']}, 派单已回开放池"


async def scenario_4_no_one_online(client: httpx.AsyncClient, pg: asyncpg.Connection) -> str:
    """全员 offline → request-human 响应 no_one_online=true。"""
    await http_presence(client, AGENT_A, "offline")
    await http_presence(client, AGENT_B, "offline")
    cid = await new_conv(pg)
    code, body = await http_request_human(client, cid)
    if code != 200:
        return f"FAIL: status={code} body={body}"
    if body.get("no_one_online") is not True:
        return f"FAIL: no_one_online != True，body={body}"
    if "off_hours" in body or "next_shift_start" in body:
        return f"FAIL: 旧字段未删干净: {body}"
    return "PASS: no_one_online=true，无 off_hours/next_shift_start 残留"


async def scenario_5_takeover_not_released(client: httpx.AsyncClient, pg: asyncpg.Connection) -> str:
    """接管后关开关，已 human_takeover 的会话不应释放。"""
    await http_presence(client, AGENT_A, "online")
    cid = await new_conv(pg)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    await pg.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id=$1, assigned_at=$2 WHERE id=$3",
        AGENT_A, now, cid,
    )
    code = await http_take(client, AGENT_A, cid)
    if code != 200:
        return f"FAIL: take returned {code}"
    mode, sid = await get_assignment(pg, cid)
    if mode != "human_takeover":
        return f"FAIL: mode={mode} after take"
    # 现在关开关
    body = await http_presence(client, AGENT_A, "offline")
    # 已 takeover 的不该被算到 released_count，也不该被清空
    mode2, sid2 = await get_assignment(pg, cid)
    if mode2 != "human_takeover" or sid2 != AGENT_A:
        return f"FAIL: 已接管会话被错误释放：mode={mode2}, sid={sid2}"
    return f"PASS: 已接管会话保留 (mode={mode2}, sid={sid2}), released_count={body['released_count']}"


async def scenario_6_response_fields(client: httpx.AsyncClient, pg: asyncpg.Connection) -> str:
    """/request-human 响应字段断言：包含 no_one_online，不含 off_hours/next_shift_start。"""
    await http_presence(client, AGENT_A, "online")
    cid = await new_conv(pg)
    code, body = await http_request_human(client, cid)
    if code != 200:
        return f"FAIL: status={code}"
    if "no_one_online" not in body:
        return f"FAIL: no_one_online 字段缺失: {body}"
    if "off_hours" in body or "next_shift_start" in body:
        return f"FAIL: 旧字段残留: {body}"
    return f"PASS: 字段正确 no_one_online={body['no_one_online']}, 无 off_hours/next_shift_start"


async def main() -> None:
    pg = await asyncpg.connect(PG_DSN)
    async with httpx.AsyncClient(timeout=15.0) as client:
        # setup
        print("=== setup ===")
        await reset(pg)
        await seed_staff(pg, AGENT_A)
        await seed_staff(pg, AGENT_B)
        await http_presence(client, AGENT_A, "online")
        await http_presence(client, AGENT_B, "online")
        print(f"  seeded {AGENT_A} + {AGENT_B}, both online\n")

        scenarios = [
            ("场景 1 — 最少在聊派单", scenario_1_least_loaded),
            ("场景 2 — 60s 超时回退（加速）", scenario_2_timeout_release),
            ("场景 3 — 关开关释放未接管", scenario_3_offline_releases_pending),
            ("场景 4 — 全员 offline → no_one_online", scenario_4_no_one_online),
            ("场景 5 — 已接管不释放", scenario_5_takeover_not_released),
            ("场景 6 — 响应字段正确", scenario_6_response_fields),
        ]
        results: list[tuple[str, str]] = []
        for name, fn in scenarios:
            try:
                result = await fn(client, pg)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
            print(f"{name}: {result}")
            results.append((name, result))

        # cleanup
        await reset(pg)
    await pg.close()

    print("\n=== 总结 ===")
    pass_n = sum(1 for _, r in results if r.startswith("PASS"))
    for n, r in results:
        mark = "✅" if r.startswith("PASS") else ("⚠️" if r.startswith("WARN") else "❌")
        print(f"  {mark} {n}: {r}")
    print(f"\n{pass_n}/{len(results)} PASS")


if __name__ == "__main__":
    asyncio.run(main())
