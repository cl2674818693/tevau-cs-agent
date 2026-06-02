"""Prometheus /metrics 端点。

被测：metrics.metrics handler。
覆盖：
- METRICS_AUTH_TOKEN 未配置（默认）：免鉴权 200（兼容现有 prometheus 抓取）。
- 配 token：Bearer 正确 200；错误 token 401；空 Authorization 401；
  非 Bearer 前缀 401；带 token 但写成 lowercase bearer 401（严格匹配）。
- 返回 Content-Type 是 prometheus 文本格式 + 包含至少一个常见指标名。
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.metrics import router as metrics_router
from ai_engine.config import settings


def _fresh_app() -> FastAPI:
    app = FastAPI()
    app.include_router(metrics_router)
    return app


async def _get(client: AsyncClient, headers: dict[str, str] | None = None):
    return await client.get("/metrics", headers=headers or {})


@pytest.fixture
async def metrics_client():
    app = _fresh_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMetricsNoTokenConfigured:
    """METRICS_AUTH_TOKEN 默认空：放行，不要 401。"""

    async def test_no_token_configured_returns_200(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", "")
        settings.reload()
        r = await _get(metrics_client)
        assert r.status_code == 200

    async def test_response_is_prometheus_text(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", "")
        settings.reload()
        r = await _get(metrics_client)
        # prometheus_client 默认 Content-Type: text/plain; version=0.0.4
        assert r.headers["content-type"].startswith("text/plain")
        # generate_latest 输出至少包含 python_info / process_* 类内置指标的注释行
        body = r.text
        assert "# HELP" in body or "# TYPE" in body

    async def test_no_token_configured_ignores_authorization_header(
        self, monkeypatch, metrics_client
    ) -> None:
        """token 未配时无视任何 Authorization 头，避免误把生产配置漏接的环境踩坑。"""
        monkeypatch.setenv("METRICS_AUTH_TOKEN", "")
        settings.reload()
        r = await _get(metrics_client, headers={"Authorization": "Bearer whatever"})
        assert r.status_code == 200


class TestMetricsTokenRequired:
    """METRICS_AUTH_TOKEN 已配：严格 Bearer 鉴权。"""

    _TOK = "s3cret-metrics-token-xyz"

    async def test_no_header_returns_401(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(metrics_client)
        assert r.status_code == 401

    async def test_wrong_token_returns_401(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(
            metrics_client, headers={"Authorization": "Bearer wrong-token"}
        )
        assert r.status_code == 401

    async def test_correct_token_returns_200(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(
            metrics_client, headers={"Authorization": f"Bearer {self._TOK}"}
        )
        assert r.status_code == 200

    async def test_non_bearer_prefix_returns_401(
        self, monkeypatch, metrics_client
    ) -> None:
        """source 用 == 严格比对完整字符串；非 'Bearer ' 前缀必失败。"""
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(
            metrics_client, headers={"Authorization": f"Token {self._TOK}"}
        )
        assert r.status_code == 401

    async def test_lowercase_bearer_returns_401(
        self, monkeypatch, metrics_client
    ) -> None:
        """大小写敏感（== 比对）：'bearer xxx' 与 'Bearer xxx' 不等。"""
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(
            metrics_client, headers={"Authorization": f"bearer {self._TOK}"}
        )
        assert r.status_code == 401

    async def test_empty_string_token_returns_401(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(metrics_client, headers={"Authorization": ""})
        assert r.status_code == 401

    async def test_token_with_extra_whitespace_returns_401(
        self, monkeypatch, metrics_client
    ) -> None:
        """严格匹配：多余空格也算不等。"""
        monkeypatch.setenv("METRICS_AUTH_TOKEN", self._TOK)
        settings.reload()
        r = await _get(
            metrics_client,
            headers={"Authorization": f"Bearer  {self._TOK}"},  # 双空格
        )
        assert r.status_code == 401


class TestMetricsContent:
    """指标内容应包含被本测试触发产生的至少一个序列。"""

    async def test_emits_expected_metric_families(
        self, monkeypatch, metrics_client
    ) -> None:
        monkeypatch.setenv("METRICS_AUTH_TOKEN", "")
        settings.reload()
        # 触发一次指标以确保非空（直接操作 observability.metrics 注册的 counter）
        from ai_engine.observability import metrics as obs

        # 选个无副作用的 counter / gauge 触发；human_pending 是 Gauge，直接 set 0
        obs.human_pending.set(0)

        r = await _get(metrics_client)
        assert r.status_code == 200
        body = r.text
        # human_pending 我们刚 set 过，必然出现
        assert "human_pending" in body
