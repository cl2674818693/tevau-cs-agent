import json
from pathlib import Path

import pytest

_SAMPLE = Path("tests/fixtures/openapi_sample.json").read_text(encoding="utf-8")

_NEXUS = json.dumps(
    {
        "openapi": "3.0.0",
        "info": {"title": "Tevau Nexus Open API", "version": "1.0.0"},
        "paths": {
            "/v1/openapi/transfer": {
                "post": {
                    "summary": "发起转账",
                    "description": "B 端合作伙伴发起跨境转账。",
                    "tags": ["转账", "transfer"],
                    "operationId": "createTransfer",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    },
    ensure_ascii=False,
)


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")


@pytest.fixture
def docs_dir(monkeypatch, tmp_path):
    """目录模式：repos/api-docs 下放多份独立文档。"""
    d = tmp_path / "api-docs"
    d.mkdir()
    (d / "pay.openapi.json").write_text(_SAMPLE, encoding="utf-8")
    monkeypatch.setenv("OPENAPI_DOCS_DIR", str(d))
    # 单文件指向不存在的路径，确保走目录模式
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(tmp_path / "single-none.json"))
    from ai_engine.config import settings

    settings.reload()
    return d


async def test_lookup_matches_by_summary(docs_dir):
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="绑定卡片")
    assert out["hits"]
    h = out["hits"][0]
    assert h["path"] == "/v2/card/bind"
    assert h["method"] == "POST"


async def test_lookup_matches_by_tag(docs_dir):
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="unlock")
    assert any(h["path"] == "/v2/card/unlock" for h in out["hits"])


async def test_lookup_returns_empty_for_no_match(docs_dir):
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="不存在的关键词xxx")
    assert out["hits"] == []


async def test_lookup_hit_carries_source(docs_dir):
    """每条命中带来源标记（文件名第一段）。"""
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="绑定卡片")
    assert out["hits"][0]["source"] == "pay"


async def test_lookup_searches_across_multiple_docs(docs_dir):
    """目录下多份文档各自独立、都参与检索，source 正确区分。"""
    (docs_dir / "nexus.openapi.json").write_text(_NEXUS, encoding="utf-8")

    from ai_engine.agent.tools.lookup_api_doc import run

    pay = await run(query="绑定卡片")
    assert pay["hits"][0]["source"] == "pay"

    nexus = await run(query="发起转账")
    assert nexus["hits"][0]["path"] == "/v1/openapi/transfer"
    assert nexus["hits"][0]["source"] == "nexus"


async def test_lookup_single_file_backward_compat(monkeypatch, tmp_path):
    """旧的单文件 OPENAPI_DOC_PATH 仍可用（目录不存在时回退）。"""
    single = tmp_path / "openapi.json"
    single.write_text(_SAMPLE, encoding="utf-8")
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(single))
    monkeypatch.setenv("OPENAPI_DOCS_DIR", str(tmp_path / "no-such-dir"))
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="绑定卡片")
    assert out["hits"]
    assert out["hits"][0]["path"] == "/v2/card/bind"
    assert out["hits"][0]["source"] == "openapi"


async def test_lookup_handles_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(tmp_path / "nope.json"))
    monkeypatch.setenv("OPENAPI_DOCS_DIR", str(tmp_path / "no-such-dir"))
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent.tools.lookup_api_doc import run

    out = await run(query="anything")
    assert out["hits"] == []
    assert "openapi doc not loaded" in out.get("note", "").lower()
