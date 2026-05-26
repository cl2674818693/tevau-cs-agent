import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def admin_env(seeded_db, monkeypatch, tmp_path):
    # 把 prompts 目录复制到 tmp，避免测试写坏仓库里的 registry.yaml
    src = Path("src/ai_engine/prompts")
    dst = tmp_path / "prompts"
    shutil.copytree(src, dst)
    monkeypatch.setenv("PROMPTS_DIR", str(dst))
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.prompts import registry

    registry.reload_registry()

    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AD1", "管理员", "admin", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "admin": issue_staff_token("AD1", "admin"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    # 还原全局状态，避免临时 registry 泄漏到其它测试
    monkeypatch.undo()
    settings.reload()
    registry.reload_registry()


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_list_versions(admin_env):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/admin/api/v1/prompts/versions", headers=_h(admin_env["admin"]))
    assert r.status_code == 200
    body = r.json()
    assert "v1.1.0" in body["versions"]
    assert body["default"] == "v1.0.0"
    assert body["rollout"]["v1.1.0"] == 20


async def test_agent_forbidden(admin_env):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/admin/api/v1/prompts/versions", headers=_h(admin_env["agent"]))
    assert r.status_code == 403


async def test_set_rollout_persists_and_hot_reloads(admin_env):
    from ai_engine import main as main_mod
    from ai_engine.prompts import registry

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/admin/api/v1/prompts/rollout",
            json={"rollout": {"v1.1.0": 50, "v1.0.0": 50}},
            headers=_h(admin_env["admin"]),
        )
    assert r.status_code == 200
    assert r.json()["rollout"] == {"v1.1.0": 50, "v1.0.0": 50}
    # 热加载生效：内存里的 rollout 已更新
    assert registry.get_rollout() == {"v1.1.0": 50, "v1.0.0": 50}


async def test_set_rollout_rejects_unknown_version(admin_env):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/admin/api/v1/prompts/rollout",
            json={"rollout": {"v9.9.9": 100}},
            headers=_h(admin_env["admin"]),
        )
    assert r.status_code == 400


async def test_set_rollout_rejects_over_100(admin_env):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/admin/api/v1/prompts/rollout",
            json={"rollout": {"v1.1.0": 80, "v1.0.0": 80}},
            headers=_h(admin_env["admin"]),
        )
    assert r.status_code == 400


# ── Task 6.1 新增测试 ────────────────────────────────────────────────────────

async def test_set_rollout_creates_audit_record(admin_env):
    """灰度变更成功后 prompt_changes 表新增一行，包含 actor/old/new/created_at。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence import prompt_changes as pc_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/admin/api/v1/prompts/rollout",
            json={"rollout": {"v1.1.0": 30, "v1.0.0": 70}},
            headers=_h(admin_env["admin"]),
        )
    assert r.status_code == 200

    rows = await pc_mod.list_prompt_changes(limit=10)
    assert len(rows) >= 1
    last = rows[0]
    assert last["actor"] == "AD1"  # JWT sub = staff_id
    assert "v1.1.0" in last["new_json"]
    assert last["created_at"] is not None


async def test_get_prompt_changes_endpoint(admin_env):
    """GET /admin/api/v1/prompts/changes 返回变更列表（admin 鉴权）。"""
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # 先写一条
        await client.post(
            "/admin/api/v1/prompts/rollout",
            json={"rollout": {"v1.1.0": 25}},
            headers=_h(admin_env["admin"]),
        )
        r = await client.get(
            "/admin/api/v1/prompts/changes",
            headers=_h(admin_env["admin"]),
        )
    assert r.status_code == 200
    body = r.json()
    assert "changes" in body
    assert len(body["changes"]) >= 1
    first = body["changes"][0]
    assert "actor" in first
    assert "old_json" in first
    assert "new_json" in first
    assert "created_at" in first


async def test_get_prompt_changes_agent_forbidden(admin_env):
    """非 admin 不能查看变更记录。"""
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            "/admin/api/v1/prompts/changes",
            headers=_h(admin_env["agent"]),
        )
    assert r.status_code == 403
