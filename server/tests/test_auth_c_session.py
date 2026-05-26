"""C 端身份解析：拿 APP 注入的 Sa-Token 调 gateway getCurrentUserInfo 换 userCode。

替代原 RS256 JWT 验签（已作废）。远程调用用假 client 打桩，不打真实网络。
"""


def _setup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("C_APP_API_BASE", "https://test2.example.com/gateway")
    from ai_engine.config import settings

    settings.reload()


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._resp


def _patch_client(monkeypatch, resp):
    from ai_engine.auth import c_session

    c_session._cache.clear()
    client = _FakeClient(resp)
    monkeypatch.setattr(c_session.httpx, "AsyncClient", lambda *a, **k: client)
    return client


async def test_resolve_c_user_success(monkeypatch):
    _setup(monkeypatch)
    from ai_engine.auth.c_session import resolve_c_user

    client = _patch_client(monkeypatch, _FakeResp(200, {"code": 0, "data": {"userCode": "U777"}}))
    assert await resolve_c_user("df90-token") == "U777"
    # 裸 token 放 Authorization（不加 Bearer），打到 getCurrentUserInfo
    assert client.calls[0]["headers"]["Authorization"] == "df90-token"
    assert client.calls[0]["url"].endswith("/user/getCurrentUserInfo")


async def test_resolve_c_user_invalid_token(monkeypatch):
    _setup(monkeypatch)
    from ai_engine.auth.c_session import resolve_c_user

    _patch_client(monkeypatch, _FakeResp(200, {"code": 401, "msg": "not login"}))
    assert await resolve_c_user("bad") is None


async def test_resolve_c_user_network_failure(monkeypatch):
    _setup(monkeypatch)
    from ai_engine.auth import c_session

    c_session._cache.clear()

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(c_session.httpx, "AsyncClient", _boom)
    assert await c_session.resolve_c_user("any") is None


async def test_resolve_identity_c_end(monkeypatch):
    """resolve_identity：带 C 端 Bearer Sa-Token → ('c', userCode)。"""
    _setup(monkeypatch)
    from starlette.requests import Request

    from ai_engine.auth import bu_session

    async def fake_resolve(token):
        assert token == "df90-token"
        return "U777"

    monkeypatch.setattr(bu_session, "resolve_c_user", fake_resolve)
    scope = {"type": "http", "headers": [(b"authorization", b"Bearer df90-token")]}
    ut, sid = await bu_session.resolve_identity(Request(scope))
    assert ut == "c" and sid == "U777"


async def test_resolve_identity_c_invalid_falls_to_guest(monkeypatch):
    """C 端 token 校验失败（无 B 端 cookie）→ 降级游客。"""
    _setup(monkeypatch)
    from starlette.requests import Request

    from ai_engine.auth import bu_session

    async def fake_resolve(token):
        return None

    monkeypatch.setattr(bu_session, "resolve_c_user", fake_resolve)
    scope = {
        "type": "http",
        "headers": [(b"authorization", b"Bearer bad"), (b"x-guest-id", b"g-1")],
    }
    ut, sid = await bu_session.resolve_identity(Request(scope))
    assert ut == "g" and sid == "guest:g-1"
