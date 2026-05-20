import pytest
import respx
from httpx import Response

_BASE = "http://sg/gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service@test/-/raw"


@pytest.fixture(autouse=True)
def sg_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SOURCEGRAPH_URL", "http://sg")
    monkeypatch.setenv("SOURCEGRAPH_TOKEN", "tok")
    from ai_engine.config import settings

    settings.reload()


@respx.mock
async def test_read_file_returns_content():
    respx.get(f"{_BASE}/handlers/card_bind.go").mock(
        return_value=Response(200, text="package handlers\nfunc HandleCardBind() {}\n")
    )
    from ai_engine.agent.tools.read_file import run

    out = await run(repo="openapi_backend", path="handlers/card_bind.go")
    assert "HandleCardBind" in out["content"]


@respx.mock
async def test_read_file_404_raises():
    respx.get(f"{_BASE}/nope.go").mock(return_value=Response(404))
    from ai_engine.agent.tools.read_file import run

    with pytest.raises(ValueError):
        await run(repo="openapi_backend", path="nope.go")


async def test_read_file_rejects_unknown_repo():
    from ai_engine.agent.tools.read_file import run

    with pytest.raises(ValueError):
        await run(repo="not_a_repo", path="x")


async def test_read_file_rejects_path_traversal():
    from ai_engine.agent.tools.read_file import run

    with pytest.raises(ValueError):
        await run(repo="openapi_backend", path="../../etc/passwd")


@respx.mock
async def test_read_file_line_range():
    respx.get(f"{_BASE}/x.go").mock(return_value=Response(200, text="L1\nL2\nL3\nL4\nL5\n"))
    from ai_engine.agent.tools.read_file import run

    out = await run(repo="openapi_backend", path="x.go", start_line=2, end_line=3)
    assert out["content"].strip() == "L2\nL3"
