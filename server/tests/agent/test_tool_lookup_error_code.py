"""Tool: lookup_error_code（B 端 Open API 错误码 KB）

被测对象：tools.lookup_error_code.run + _entry
- code 精确命中（含从句子里抠数字）。
- code 未收录 → note。
- keyword 大小写不敏感搜索；hits 截断到 10。
- KB 未加载（监控 _DOC 不存在）→ note。
- 无 code 无 keyword → 引导提示。
- _entry 字段映射：cn→message；en→message_en；reap→reap_code。
"""

import json

import pytest

from ai_engine.agent.tools import lookup_error_code as le


@pytest.fixture(autouse=True)
def _clear_lru():
    le._load.cache_clear()
    yield
    le._load.cache_clear()


@pytest.fixture
def _patch_kb(monkeypatch, tmp_path):
    """临时 KB 文件 + monkeypatch _DOC 指向它。"""

    def _make(codes: dict) -> None:
        p = tmp_path / "codes.json"
        p.write_text(json.dumps({"codes": codes}))
        monkeypatch.setattr(le, "_DOC", p)
        le._load.cache_clear()

    return _make


class TestEntryMapping:
    def test_basic_cn_only(self) -> None:
        out = le._entry("1001", {"cn": "失败"})
        assert out == {"code": "1001", "message": "失败"}

    def test_with_en_and_reason_and_reap(self) -> None:
        out = le._entry(
            "1002",
            {"cn": "拒付", "en": "Chargeback", "reason": "do thing", "reap": "R123"},
        )
        assert out["message"] == "拒付"
        assert out["message_en"] == "Chargeback"
        assert out["reason"] == "do thing"
        assert out["reap_code"] == "R123"


class TestRunByCode:
    async def test_exact_match(self, _patch_kb) -> None:
        _patch_kb({"2020003": {"cn": "卡库存不足"}})
        out = await le.run(code="2020003")
        assert out["hits"][0]["message"] == "卡库存不足"

    async def test_digit_extracted_from_sentence(self, _patch_kb) -> None:
        _patch_kb({"2020003": {"cn": "卡库存不足"}})
        out = await le.run(code="接口返回 2020003 不开心")
        assert out["hits"][0]["message"] == "卡库存不足"

    async def test_not_present_note(self, _patch_kb) -> None:
        _patch_kb({"1001": {"cn": "x"}})
        out = await le.run(code="99999")
        assert out["hits"] == []
        assert "未收录" in out["note"]

    async def test_full_string_fallback(self, _patch_kb) -> None:
        """无 \\d{3,8} 命中但整串本身是 code key 时，回退把整串当 key。"""
        _patch_kb({"X1": {"cn": "x"}})
        out = await le.run(code="X1")
        assert out["hits"] and out["hits"][0]["message"] == "x"


class TestRunByKeyword:
    async def test_keyword_match_cn(self, _patch_kb) -> None:
        _patch_kb({
            "100": {"cn": "卡库存不足"},
            "101": {"cn": "余额不足"},
            "102": {"cn": "签名错误"},
        })
        out = await le.run(keyword="不足")
        codes = [h["code"] for h in out["hits"]]
        assert set(codes) == {"100", "101"}
        assert out["count"] == 2

    async def test_keyword_match_en_case_insensitive(self, _patch_kb) -> None:
        _patch_kb({
            "200": {"cn": "签名", "en": "Bad Signature"},
            "201": {"cn": "其它"},
        })
        out = await le.run(keyword="signature")
        assert [h["code"] for h in out["hits"]] == ["200"]

    async def test_keyword_hits_truncated_to_10(self, _patch_kb) -> None:
        _patch_kb({str(i): {"cn": "卡库存"} for i in range(1, 21)})
        out = await le.run(keyword="卡库存")
        assert len(out["hits"]) == 10
        assert out["count"] == 20  # 总数仍记 20


class TestRunMisc:
    async def test_kb_missing_returns_note(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(le, "_DOC", tmp_path / "not-exist.json")
        le._load.cache_clear()
        out = await le.run(code="100")
        assert out["hits"] == []
        assert "未加载" in out["note"]

    async def test_no_code_no_keyword_prompts(self, _patch_kb) -> None:
        _patch_kb({"100": {"cn": "x"}})
        out = await le.run()
        assert out["hits"] == []
        assert "需提供" in out["note"]
