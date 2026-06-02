"""Tool: lookup_api_doc（本地 OpenAPI JSON 检索）

被测对象：tools.lookup_api_doc.run + _iter_operations / _score / _source_of / _load_docs
- query 长度 1..200。
- 目录优先：openapi_docs_dir 下多份 *.json 全加载，source=文件名第一段。
- 目录不存在 / 空时回退到单文件 openapi_doc_path。
- 加权矩阵：path>summary>operationId>description>tag。
- 坏 JSON 跳过、空文档返回 {hits:[], note:...}。
"""

import json

import pytest

from ai_engine.agent.tools import lookup_api_doc as la


def _write_openapi(path, ops: list[dict]):
    """构造一份最小 OpenAPI 文档，含若干 op。"""
    paths = {}
    for op in ops:
        method = op.pop("method", "get")
        url = op.pop("path", "/x")
        paths.setdefault(url, {})[method] = op
    path.write_text(json.dumps({"openapi": "3.0.0", "paths": paths}))


class TestArgValidation:
    async def test_empty_query(self) -> None:
        with pytest.raises(ValueError, match="query length"):
            await la.run("")

    async def test_too_long_query(self) -> None:
        with pytest.raises(ValueError, match="query length"):
            await la.run("x" * 201)


class TestSourceOf:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("pay.openapi.json", "pay"),
            ("nexus.json", "nexus"),
            ("multi.dot.name.json", "multi"),
        ],
    )
    def test_source_extraction(self, name: str, expected: str) -> None:
        from pathlib import Path

        assert la._source_of(Path(name)) == expected


class TestLoadOneAndDocs:
    def test_load_one_bad_json_returns_none(self, tmp_path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not json")
        assert la._load_one(p) is None

    def test_load_one_non_dict_returns_none(self, tmp_path) -> None:
        p = tmp_path / "list.json"
        p.write_text("[1,2,3]")
        assert la._load_one(p) is None

    def test_load_docs_uses_dir_when_present(self, monkeypatch, tmp_path) -> None:
        d = tmp_path / "docs"
        d.mkdir()
        _write_openapi(d / "pay.json", [{"path": "/x", "method": "get", "summary": "x"}])
        _write_openapi(d / "nexus.json", [{"path": "/y", "method": "get", "summary": "y"}])
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "openapi_docs_dir", str(d))
        monkeypatch.setattr(_settings, "openapi_doc_path", str(tmp_path / "nope.json"))
        out = la._load_docs()
        assert sorted(src for src, _ in out) == ["nexus", "pay"]

    def test_load_docs_fallback_single_file(
        self, monkeypatch, tmp_path
    ) -> None:
        single = tmp_path / "openapi.json"
        _write_openapi(single, [{"path": "/x", "method": "get", "summary": "x"}])
        from ai_engine.config import settings as _settings

        # docs_dir 不存在
        monkeypatch.setattr(_settings, "openapi_docs_dir", str(tmp_path / "no-such"))
        monkeypatch.setattr(_settings, "openapi_doc_path", str(single))
        out = la._load_docs()
        assert len(out) == 1


class TestScore:
    """加权矩阵：path=4, summary=3, operationId=2, description=2, tag=1。"""

    def test_path_match_highest(self) -> None:
        s = la._score("card", "/v2/card/bind", "POST", {"summary": "Other"})
        assert s == 4

    def test_summary_match(self) -> None:
        s = la._score("kyc", "/x", "GET", {"summary": "submit kyc"})
        assert s == 3

    def test_op_id_match(self) -> None:
        s = la._score(
            "bindcard", "/x", "GET", {"operationId": "BindCardForUser"}
        )
        assert s == 2

    def test_description_match(self) -> None:
        s = la._score("retry", "/x", "GET", {"description": "Can be retry-safe"})
        assert s == 2

    def test_tag_match(self) -> None:
        s = la._score("kyc", "/x", "GET", {"tags": ["KYC"]})
        assert s == 1

    def test_no_match_zero(self) -> None:
        s = la._score("foobar", "/x", "GET", {})
        assert s == 0


class TestRunIntegration:
    @pytest.fixture
    def _docs_dir(self, monkeypatch, tmp_path):
        d = tmp_path / "docs"
        d.mkdir()
        _write_openapi(
            d / "pay.json",
            [
                {
                    "path": "/v2/card/bind",
                    "method": "post",
                    "summary": "Bind card",
                    "operationId": "BindCard",
                    "tags": ["card"],
                },
                {
                    "path": "/v2/card/unbind",
                    "method": "post",
                    "summary": "Unbind card",
                    "operationId": "UnbindCard",
                    "tags": ["card"],
                },
            ],
        )
        _write_openapi(
            d / "nexus.json",
            [
                {
                    "path": "/v1/order/list",
                    "method": "get",
                    "summary": "List orders",
                    "operationId": "ListOrders",
                    "tags": ["order"],
                }
            ],
        )
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "openapi_docs_dir", str(d))
        return d

    async def test_query_hits_with_source_tag(self, _docs_dir) -> None:
        out = await la.run("bind")
        assert out["hits"]
        first = out["hits"][0]
        assert first["source"] == "pay"
        assert first["path"] == "/v2/card/bind"
        assert first["method"] == "POST"

    async def test_query_across_sources(self, _docs_dir) -> None:
        out = await la.run("list", limit=10)
        # 必有 nexus 的 /v1/order/list 命中
        sources = [h["source"] for h in out["hits"]]
        assert "nexus" in sources

    async def test_no_docs_returns_note(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "openapi_docs_dir", "/nope")
        monkeypatch.setattr(_settings, "openapi_doc_path", "/nope/x.json")
        out = await la.run("any")
        assert out["hits"] == []
        assert "note" in out

    async def test_limit_applied(self, _docs_dir) -> None:
        out = await la.run("card", limit=1)
        assert len(out["hits"]) == 1

    async def test_unknown_query_returns_empty_hits(self, _docs_dir) -> None:
        out = await la.run("totally-not-present-keyword")
        assert out["hits"] == []
