import json

import pytest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """临时代码仓库 + 指向它的 code_repo_paths。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    root = tmp_path / "openapi_backend"
    (root / "handlers").mkdir(parents=True)
    (root / "handlers" / "card_bind.go").write_text(
        "package handlers\nfunc HandleCardBind() {}\n", encoding="utf-8"
    )
    (root / "x.go").write_text("L1\nL2\nL3\nL4\nL5\n", encoding="utf-8")
    monkeypatch.setenv("CODE_REPO_PATHS", json.dumps({"openapi_backend": str(root)}))
    from ai_engine.config import settings

    settings.reload()
    yield root
    settings.reload()  # 还原


async def test_read_file_returns_content(repo):
    from ai_engine.agent.tools.read_file import run

    out = await run(repo="openapi_backend", path="handlers/card_bind.go")
    assert "HandleCardBind" in out["content"]


async def test_read_file_404_raises(repo):
    from ai_engine.agent.tools.read_file import run

    with pytest.raises(ValueError):
        await run(repo="openapi_backend", path="nope.go")


async def test_read_file_rejects_unknown_repo(repo):
    from ai_engine.agent.tools.read_file import run

    with pytest.raises(ValueError):
        await run(repo="not_a_repo", path="x")


async def test_read_file_rejects_path_traversal(repo):
    from ai_engine.agent.tools.read_file import run

    with pytest.raises(ValueError):
        await run(repo="openapi_backend", path="../../etc/passwd")


async def test_read_file_line_range(repo):
    from ai_engine.agent.tools.read_file import run

    out = await run(repo="openapi_backend", path="x.go", start_line=2, end_line=3)
    assert out["content"].strip() == "L2\nL3"
