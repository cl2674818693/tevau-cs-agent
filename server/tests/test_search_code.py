import json

import pytest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """临时代码仓库 + 指向它的 code_repo_paths。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    root = tmp_path / "openapi_backend"
    (root / "handlers").mkdir(parents=True)
    (root / "handlers" / "card_bind.go").write_text(
        "package handlers\n\nfunc HandleCardBind() {\n    // bind logic\n}\n", encoding="utf-8"
    )
    monkeypatch.setenv("CODE_REPO_PATHS", json.dumps({"openapi_backend": str(root)}))
    from ai_engine.config import settings

    settings.reload()
    yield root
    settings.reload()


async def test_search_code_finds_handler(repo):
    from ai_engine.agent.tools.search_code import run

    out = await run(repo="openapi_backend", query="HandleCardBind")
    assert out["hits"]
    assert any("card_bind.go" in h["path"] for h in out["hits"])
    assert out["hits"][0]["line"] == 3  # 命中所在行


async def test_search_code_missing_path_graceful(repo, monkeypatch):
    monkeypatch.setenv("CODE_REPO_PATHS", json.dumps({"app_backend": "/no/such/dir/xyz"}))
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent.tools.search_code import run

    # 配了路径但目录不存在（如生产没放代码副本）→ 优雅返回，不报错
    out = await run(repo="app_backend", query="anything")
    assert out["hits"] == [] and "note" in out


async def test_search_code_rejects_unknown_repo(repo):
    from ai_engine.agent.tools.search_code import run

    with pytest.raises(ValueError) as e:
        await run(repo="anything_else", query="x")
    assert "repo" in str(e.value)


async def test_search_code_rejects_long_query(repo):
    from ai_engine.agent.tools.search_code import run

    with pytest.raises(ValueError):
        await run(repo="openapi_backend", query="a" * 1024)


async def test_search_code_no_match_returns_empty(repo):
    from ai_engine.agent.tools.search_code import run

    out = await run(repo="openapi_backend", query="ThisStringDoesNotExistAnywhere12345")
    assert out["hits"] == []
