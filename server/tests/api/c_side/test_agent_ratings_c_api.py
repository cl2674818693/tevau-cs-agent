"""C 端客服评分：/api/v1/conversations/{cid}/agent-rating[/eligibility]。

源码 `agent_ratings.py::_resolve_subject` 解析顺序：
1) 若开启 DEV_TRUST_BU_HEADER 且带 X-BU-ID → 取 BU 身份 (user_type='b')。
2) 否则尝试 Authorization: Bearer <Sa-Token> → c_session.resolve_c_user → C 端身份 (user_type='c')。
3) 都不行 → 401。

本测试用 X-BU-ID 头模拟用户（端点视角 user_type='b'）覆盖核心矩阵：
- eligibility：未指派 / 已指派 / 已评过
- submit：成功 / 重复 409 / 越界 422 / 无客服 400 / 越权 403
- 401：完全不带身份头
末尾 TestCSideSaToken 正向验证 C 端 Sa-Token 通道（Bug #12 修复后已接通）。
"""

from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_engine.main import app
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db


# ────────── 通用 fixture：B 端身份（X-BU-ID）+ 自有 conversation ──────────


BU_ID = "BU-RATER-1"


@pytest_asyncio.fixture
async def bu_client(db_ready: str) -> AsyncClient:
    """带 X-BU-ID 头的 client（与 C 侧普通 client 隔开）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"X-BU-ID": BU_ID}
    ) as c:
        yield c


@pytest_asyncio.fixture
async def my_conv(bu_client: AsyncClient) -> int:
    """X-BU-ID 用户起一条会话；该端点 _conv_belongs_to 按 (subject_id, user_type='b') 校验。"""
    cid = await conv_dao.create_conversation("b", BU_ID)
    return cid


async def _seed_staff(staff_id: str = "S100") -> None:
    """直接落 staff 表，避免走 admin 创建路径。"""
    from ai_engine.persistence.schema import now_str
    await db.execute(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, created_at) "
        "VALUES (:sid, :dn, 'agent', 'x', :now)",
        {"sid": staff_id, "dn": "客服A", "now": now_str()},
    )


# ────────── eligibility ──────────


class TestEligibility:
    async def test_returns_false_when_no_staff_assigned(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        r = await bu_client.get(
            f"/api/v1/conversations/{my_conv}/agent-rating/eligibility"
        )
        assert r.status_code == 200
        body = r.json()
        assert body == {"eligible": False, "already_rated": False, "staff_id": None}

    async def test_returns_true_with_assigned_staff(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        await _seed_staff()
        await conv_dao.set_mode(my_conv, "human_takeover", assigned_staff_id="S100")
        r = await bu_client.get(
            f"/api/v1/conversations/{my_conv}/agent-rating/eligibility"
        )
        body = r.json()
        assert body["eligible"] is True
        assert body["already_rated"] is False
        assert body["staff_id"] == "S100"

    async def test_already_rated_flag(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        await _seed_staff()
        await conv_dao.set_mode(my_conv, "human_takeover", assigned_staff_id="S100")
        await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating", json={"rating": 5}
        )
        r = await bu_client.get(
            f"/api/v1/conversations/{my_conv}/agent-rating/eligibility"
        )
        assert r.json()["already_rated"] is True

    async def test_fallback_to_last_take_when_assigned_cleared(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        """assigned_staff_id 被释放后，端点回退到最近一次 take 的 staff_id。"""
        await _seed_staff()
        # 模拟：曾接管再释放（staff_actions 留痕 take + 释放后 assigned 清空）
        from ai_engine.persistence.staff_metrics import log_staff_action

        await conv_dao.set_mode(my_conv, "human_takeover", assigned_staff_id="S100")
        await log_staff_action(my_conv, "S100", "take")
        await conv_dao.set_mode(my_conv, "ai", assigned_staff_id=None)
        r = await bu_client.get(
            f"/api/v1/conversations/{my_conv}/agent-rating/eligibility"
        )
        body = r.json()
        assert body["eligible"] is True
        assert body["staff_id"] == "S100"

    async def test_unauth_returns_401(
        self, client: AsyncClient, my_conv: int
    ) -> None:
        # 不带 X-BU-ID 且 c_session 接不通 → 401
        r = await client.get(
            f"/api/v1/conversations/{my_conv}/agent-rating/eligibility"
        )
        assert r.status_code == 401

    async def test_other_user_forbidden(
        self, db_ready: str
    ) -> None:
        # 用 BU-OTHER 去查 BU_ID 的会话
        cid = await conv_dao.create_conversation("b", BU_ID)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers={"X-BU-ID": "BU-OTHER"}
        ) as other:
            r = await other.get(f"/api/v1/conversations/{cid}/agent-rating/eligibility")
            assert r.status_code == 403


# ────────── submit ──────────


class TestSubmit:
    async def test_success(self, bu_client: AsyncClient, my_conv: int) -> None:
        await _seed_staff()
        await conv_dao.set_mode(my_conv, "human_takeover", assigned_staff_id="S100")
        r = await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating",
            json={"rating": 5, "comment": "服务好"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["id"], int)

    async def test_duplicate_returns_409(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        await _seed_staff()
        await conv_dao.set_mode(my_conv, "human_takeover", assigned_staff_id="S100")
        await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating", json={"rating": 5}
        )
        r = await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating", json={"rating": 4}
        )
        assert r.status_code == 409

    async def test_no_staff_assigned_returns_400(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        r = await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating", json={"rating": 5}
        )
        assert r.status_code == 400

    @pytest.mark.parametrize("bad_rating", [0, 6, -1, 100])
    async def test_out_of_range_rating_returns_400(
        self, bu_client: AsyncClient, my_conv: int, bad_rating: int
    ) -> None:
        await _seed_staff()
        await conv_dao.set_mode(my_conv, "human_takeover", assigned_staff_id="S100")
        r = await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating",
            json={"rating": bad_rating},
        )
        # ValueError → 400（端点 catch ValueError 后 raise HTTPException(400)）
        assert r.status_code == 400

    async def test_missing_rating_returns_422(
        self, bu_client: AsyncClient, my_conv: int
    ) -> None:
        r = await bu_client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating", json={}
        )
        assert r.status_code == 422

    async def test_other_user_forbidden(
        self, db_ready: str
    ) -> None:
        cid = await conv_dao.create_conversation("b", BU_ID)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers={"X-BU-ID": "BU-OTHER"}
        ) as other:
            r = await other.post(
                f"/api/v1/conversations/{cid}/agent-rating", json={"rating": 5}
            )
            assert r.status_code == 403

    async def test_unauth_returns_401(
        self, client: AsyncClient, my_conv: int
    ) -> None:
        r = await client.post(
            f"/api/v1/conversations/{my_conv}/agent-rating", json={"rating": 5}
        )
        assert r.status_code == 401

    async def test_nonexistent_conversation_returns_403(
        self, bu_client: AsyncClient
    ) -> None:
        r = await bu_client.post(
            "/api/v1/conversations/9999999/agent-rating", json={"rating": 5}
        )
        assert r.status_code == 403


# ────────── C 端 Sa-Token 通道（Bug #12 修复后正向验证） ──────────


class TestCSideSaToken:
    """Bug #12 修复后，C 端用户用 Authorization: Bearer <Sa-Token> 调评分端点应能走通。

    c_side conftest 已 monkeypatch `c_session.resolve_c_user`：TOKEN_A → USER_CODE_A。
    端点解析出 (USER_CODE_A, 'c') 后按 (subject_id=user_code, user_type='c') 校验会话归属。
    """

    async def test_c_user_with_bearer_token_can_query_eligibility(
        self, c_client: AsyncClient, db_ready: str
    ) -> None:
        from .conftest import USER_CODE_A

        # c_client 默认带 Authorization: Bearer TOKEN_A → c_session.resolve_c_user 解 USER_CODE_A
        cid = await conv_dao.create_conversation("c", USER_CODE_A)
        r = await c_client.get(f"/api/v1/conversations/{cid}/agent-rating/eligibility")
        assert r.status_code == 200, r.text
        body = r.json()
        # 未指派客服：eligible=False；关键是不再 401
        assert body == {"eligible": False, "already_rated": False, "staff_id": None}

    async def test_c_user_with_bearer_token_can_submit_rating(
        self, c_client: AsyncClient, db_ready: str
    ) -> None:
        from .conftest import USER_CODE_A

        await _seed_staff()
        cid = await conv_dao.create_conversation("c", USER_CODE_A)
        await conv_dao.set_mode(cid, "human_takeover", assigned_staff_id="S100")
        r = await c_client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 5, "comment": "ok"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
