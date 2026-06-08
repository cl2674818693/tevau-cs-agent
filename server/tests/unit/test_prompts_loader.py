"""Unit tests: prompts.loader

被测对象：prompt 内容缓存（read_prompt / clear_cache）+ system 块组装（build_system_blocks）。
mock 策略：用 tmp_path 写 fake prompts 文件，并 monkeypatch settings.prompts_dir。
"""

from pathlib import Path

import pytest

from ai_engine.prompts import loader

_PROMPT_KEYS = [
    "role",
    "topic_scope.c",
    "topic_scope.b",
    "classification",
    "tools_usage",
    "reply_style.b",
    "reply_style.c",
    "self_check",
]


def _write_prompt_files(root: Path) -> None:
    for key in _PROMPT_KEYS:
        (root / f"{key}.md").write_text(f"[{key}]", encoding="utf-8")


@pytest.fixture
def fake_prompts(tmp_path: Path, monkeypatch) -> Path:
    _write_prompt_files(tmp_path)
    from ai_engine.config import settings

    monkeypatch.setattr(settings, "prompts_dir", str(tmp_path), raising=False)
    loader.clear_cache()
    yield tmp_path
    loader.clear_cache()


class TestReadPromptCache:
    """缓存命中：同 key 二次读不再触发磁盘 IO。"""

    def test_returns_file_content(self, fake_prompts) -> None:
        assert loader.read_prompt("role") == "[role]"

    def test_cache_hit_skips_disk(self, fake_prompts) -> None:
        first = loader.read_prompt("role")
        (fake_prompts / "role.md").unlink()
        # 二次读应仍命中缓存
        assert loader.read_prompt("role") == first == "[role]"

    def test_clear_cache_forces_reread(self, fake_prompts) -> None:
        loader.read_prompt("role")
        loader.clear_cache()
        (fake_prompts / "role.md").unlink()
        with pytest.raises(FileNotFoundError):
            loader.read_prompt("role")

    def test_missing_key_raises(self, fake_prompts) -> None:
        with pytest.raises(FileNotFoundError):
            loader.read_prompt("no_such_key")


class TestBuildSystemBlocksByUserType:
    """user_type=c/b/g 时 block 数量与构成应符合 loader 注释契约。"""

    def test_c_user_three_blocks(self, fake_prompts) -> None:
        blocks = loader.build_system_blocks("c")
        assert len(blocks) == 3
        assert "[role]" in blocks[0]["text"]
        assert "[topic_scope.c]" in blocks[0]["text"]
        assert "[classification]" in blocks[1]["text"]
        assert "[tools_usage]" in blocks[1]["text"]
        assert "[reply_style.c]" in blocks[2]["text"]
        assert "[self_check]" in blocks[2]["text"]

    def test_b_user_uses_b_variants(self, fake_prompts) -> None:
        blocks = loader.build_system_blocks("b")
        assert len(blocks) == 3
        assert "[topic_scope.b]" in blocks[0]["text"]
        assert "[reply_style.b]" in blocks[2]["text"]
        # 不应混入 c 变体
        assert "topic_scope.c" not in blocks[0]["text"]
        assert "reply_style.c" not in blocks[2]["text"]

    def test_g_user_appends_guest_constraint(self, fake_prompts) -> None:
        """游客（g）= 3 基础 + 1 未登录硬约束 = 4 块。"""
        blocks = loader.build_system_blocks("g")
        assert len(blocks) == 4
        # g 默认走 C 变体（else 分支）
        assert "[topic_scope.c]" in blocks[0]["text"]
        guest_text = blocks[3]["text"]
        assert "未登录会话" in guest_text
        assert "登录" in guest_text

    def test_block_dict_shape(self, fake_prompts) -> None:
        for ut in ("c", "b", "g"):
            for blk in loader.build_system_blocks(ut):
                assert blk["type"] == "text"
                assert isinstance(blk["text"], str)
                assert blk["text"]
