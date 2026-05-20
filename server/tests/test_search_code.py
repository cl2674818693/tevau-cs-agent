import pytest
import respx
from httpx import Response

_NEXUS = "gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service"


@pytest.fixture(autouse=True)
def sg_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SOURCEGRAPH_URL", "http://sg")
    monkeypatch.setenv("SOURCEGRAPH_TOKEN", "tok")
    from ai_engine.config import settings

    settings.reload()


@respx.mock
async def test_search_code_finds_handler():
    respx.post("http://sg/.api/graphql").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "search": {
                        "results": {
                            "results": [
                                {
                                    "__typename": "FileMatch",
                                    "repository": {"name": _NEXUS},
                                    "file": {"path": "handlers/card_bind.go"},
                                    "lineMatches": [
                                        {"lineNumber": 119, "preview": "func HandleCardBind("}
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
        )
    )
    from ai_engine.agent.tools.search_code import run

    out = await run(repo="openapi_backend", query="HandleCardBind")
    assert out["hits"]
    assert any("card_bind.go" in h["path"] for h in out["hits"])
    assert out["hits"][0]["line"] == 120  # SG 0-indexed → 我们 1-indexed


async def test_search_code_rejects_unknown_repo():
    from ai_engine.agent.tools.search_code import run

    with pytest.raises(ValueError) as e:
        await run(repo="anything_else", query="x")
    assert "repo" in str(e.value)


async def test_search_code_rejects_long_query():
    from ai_engine.agent.tools.search_code import run

    with pytest.raises(ValueError):
        await run(repo="openapi_backend", query="a" * 1024)


@respx.mock
async def test_search_code_propagates_sg_error():
    respx.post("http://sg/.api/graphql").mock(return_value=Response(500, text="boom"))
    from ai_engine.agent.tools.search_code import run

    with pytest.raises(RuntimeError):
        await run(repo="openapi_backend", query="x")
