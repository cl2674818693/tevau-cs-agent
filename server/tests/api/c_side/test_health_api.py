"""C 端 health 端点测试。

被测：/healthz —— 唯一一条健康检查路由（注意：源码里挂的是 /healthz 而非 /health，
PRD 里说的 /health 在当前 source 不存在；测试按真实路由覆盖，并断言 /health 404）。
"""

from httpx import AsyncClient


class TestHealthz:
    async def test_returns_ok_true(self, client: AsyncClient) -> None:
        r = await client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    async def test_no_auth_required(self, client: AsyncClient) -> None:
        # 健康检查不应带身份就 401；客户端裸 GET 应直接通过
        r = await client.get("/healthz")
        assert r.status_code == 200

    async def test_alias_health_not_mounted(self, client: AsyncClient) -> None:
        """记录差异：spec 提到 /health，但 source 实际是 /healthz。访问 /health 应 404。"""
        r = await client.get("/health")
        assert r.status_code == 404

    async def test_method_post_not_allowed(self, client: AsyncClient) -> None:
        r = await client.post("/healthz")
        assert r.status_code == 405

    async def test_returns_json_content_type(self, client: AsyncClient) -> None:
        r = await client.get("/healthz")
        assert r.headers["content-type"].startswith("application/json")
