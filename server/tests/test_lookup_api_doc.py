from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def doc_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    p = tmp_path / "openapi.json"
    p.write_text(Path("tests/fixtures/openapi_sample.json").read_text(encoding="utf-8"))
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(p))
    from ai_engine.config import settings

    settings.reload()


async def test_lookup_matches_by_summary(doc_path):
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="绑定卡片")
    assert out["hits"]
    h = out["hits"][0]
    assert h["path"] == "/v2/card/bind"
    assert h["method"] == "POST"


async def test_lookup_matches_by_tag(doc_path):
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="unlock")
    assert any(h["path"] == "/v2/card/unlock" for h in out["hits"])


async def test_lookup_returns_empty_for_no_match(doc_path):
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="不存在的关键词xxx")
    assert out["hits"] == []


async def test_lookup_handles_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(tmp_path / "nope.json"))
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="anything")
    assert out["hits"] == []
    assert "openapi doc not loaded" in out.get("note", "").lower()
