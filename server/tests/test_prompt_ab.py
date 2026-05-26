"""Task 6.2：按 prompt_version 的 A/B 效果对比（失败率 / 差评率）。

测试覆盖：
- 按版本分组的 assistant_turns / failed / failed_rate 正确聚合
- downvote 通过 message_id join messages 关联到版本
- 除零安全（如果某版无 turn 则 rate=0.0）
- prompt_version IS NULL 的 assistant 行不计入任何版本桶
- 时间窗过滤
"""

import pytest


async def test_ab_stats_basic(seeded_db):
    """v1.0.0 两条正常 assistant，v1.1.0 一条正常 + 一条 failed。断言分组聚合正确。"""
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.insights import prompt_ab_stats

    cid = await c.create_conversation("c", "U1")

    # v1.0.0：2 条 assistant，都正常
    await c.append_message(cid, "assistant", "回答1", "v1.0.0")
    await c.append_message(cid, "assistant", "回答2", "v1.0.0")

    # v1.1.0：1 条正常 + 1 条 failed
    await c.append_message(cid, "assistant", "回答3", "v1.1.0")
    # failed 的 assistant 消息需要手动 INSERT（append_message 写 done 状态）
    from ai_engine.persistence import db
    from ai_engine.persistence.schema import now_str

    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, prompt_version, status, created_at) "
        "VALUES (:cid, 'assistant', '崩了', 'v1.1.0', 'failed', :now)",
        {"cid": cid, "now": now_str()},
    )

    stats = await prompt_ab_stats(None, None)
    by_version = {r["version"]: r for r in stats}

    assert "v1.0.0" in by_version
    assert "v1.1.0" in by_version

    v100 = by_version["v1.0.0"]
    assert v100["assistant_turns"] == 2
    assert v100["failed"] == 0
    assert v100["failed_rate"] == 0.0

    v110 = by_version["v1.1.0"]
    assert v110["assistant_turns"] == 2
    assert v110["failed"] == 1
    assert abs(v110["failed_rate"] - 0.5) < 1e-9


async def test_ab_stats_null_version_excluded(seeded_db):
    """prompt_version IS NULL 的 assistant 消息不计入任何版本桶。"""
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.insights import prompt_ab_stats

    cid = await c.create_conversation("c", "U2")

    # NULL 版本（老数据）
    await c.append_message(cid, "assistant", "旧消息_无版本")  # prompt_version=None
    # 正常版本
    await c.append_message(cid, "assistant", "新消息", "v1.0.0")

    stats = await prompt_ab_stats(None, None)
    by_version = {r["version"]: r for r in stats}

    # 无 None 键
    assert None not in by_version
    assert "null" not in by_version
    # v1.0.0 只有1条
    assert "v1.0.0" in by_version
    assert by_version["v1.0.0"]["assistant_turns"] == 1


async def test_ab_stats_downvote(seeded_db):
    """downvote 通过 message_id join messages 关联到版本，分组正确。"""
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import feedback as fb
    from ai_engine.persistence.insights import prompt_ab_stats

    cid = await c.create_conversation("c", "U3")

    mid_v100 = await c.append_message(cid, "assistant", "v100回答", "v1.0.0")
    mid_v110 = await c.append_message(cid, "assistant", "v110回答", "v1.1.0")

    # 对 v1.1.0 的消息差评
    await fb.add_feedback(cid, mid_v110, "down", "不准", "U3", "c")

    stats = await prompt_ab_stats(None, None)
    by_version = {r["version"]: r for r in stats}

    v100 = by_version["v1.0.0"]
    assert v100["downvote"] == 0
    assert v100["downvote_rate"] == 0.0

    v110 = by_version["v1.1.0"]
    assert v110["downvote"] == 1
    assert v110["downvote_rate"] == 1.0

    # mid_v100 差评不影响 v1.1.0
    await fb.add_feedback(cid, mid_v100, "down", "差", "U3", "c")
    stats2 = await prompt_ab_stats(None, None)
    by2 = {r["version"]: r for r in stats2}
    assert by2["v1.0.0"]["downvote"] == 1
    assert by2["v1.1.0"]["downvote"] == 1


async def test_ab_stats_zero_division_safe(seeded_db):
    """版本只有0条 turns 不会除零（理论上不出现，但确保 rate=0.0 而非异常）。
    实际场景：某版本有 feedback 但 assistant turn 为0 不可能，
    这里用只有1条 turn 无 failed/downvote 的情况验证 rate 都是 0.0。
    """
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.insights import prompt_ab_stats

    cid = await c.create_conversation("c", "U4")
    await c.append_message(cid, "assistant", "安全", "v2.0.0")

    stats = await prompt_ab_stats(None, None)
    by_version = {r["version"]: r for r in stats}
    v200 = by_version.get("v2.0.0")
    assert v200 is not None
    assert v200["failed_rate"] == 0.0
    assert v200["downvote_rate"] == 0.0


async def test_ab_stats_date_window(seeded_db):
    """时间窗过滤：to 比数据都早，结果为空。"""
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.insights import prompt_ab_stats

    cid = await c.create_conversation("c", "U5")
    await c.append_message(cid, "assistant", "消息", "v1.0.0")

    stats = await prompt_ab_stats("2099-01-01", "2099-12-31")
    assert stats == []


# ─── HTTP 端点测试 ─────────────────────────────────────────────────────────────


@pytest.fixture
async def ab_admin_env(seeded_db, monkeypatch):
    import shutil
    from pathlib import Path

    src = Path("src/ai_engine/prompts")
    dst = Path("/tmp/prompts_ab_test")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    monkeypatch.setenv("PROMPTS_DIR", str(dst))
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.prompts import registry

    registry.reload_registry()

    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("ABAD1", "管理员", "admin", "x")
    await create_staff("ABAG1", "客服", "agent", "x")
    yield {
        "admin": issue_staff_token("ABAD1", "admin"),
        "agent": issue_staff_token("ABAG1", "agent"),
    }
    monkeypatch.undo()
    settings.reload()
    registry.reload_registry()


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_ab_stats_endpoint_returns_versions(ab_admin_env):
    """GET /admin/api/v1/prompts/ab-stats 返回 {from, to, versions:[...]}。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence import conversations as c

    from httpx import ASGITransport, AsyncClient

    cid = await c.create_conversation("c", "EP1")
    await c.append_message(cid, "assistant", "v100消息", "v1.0.0")

    from ai_engine.persistence import db
    from ai_engine.persistence.schema import now_str

    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, prompt_version, status, created_at) "
        "VALUES (:cid, 'assistant', '崩了', 'v1.1.0', 'failed', :now)",
        {"cid": cid, "now": now_str()},
    )

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            "/admin/api/v1/prompts/ab-stats",
            headers=_h(ab_admin_env["admin"]),
        )
    assert r.status_code == 200
    body = r.json()
    assert "versions" in body
    assert "from" in body
    assert "to" in body
    versions = {v["version"]: v for v in body["versions"]}
    assert "v1.0.0" in versions
    assert "v1.1.0" in versions
    assert versions["v1.1.0"]["failed"] == 1


async def test_ab_stats_endpoint_agent_forbidden(ab_admin_env):
    """非 admin 无法访问 ab-stats。"""
    from ai_engine import main as main_mod

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            "/admin/api/v1/prompts/ab-stats",
            headers=_h(ab_admin_env["agent"]),
        )
    assert r.status_code == 403
