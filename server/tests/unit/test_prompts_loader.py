"""Unit tests: prompts.loader

被测对象：prompt 内容缓存（read_prompt / clear_cache）+ system 块组装（build_system_blocks）。
mock 策略：用 tmp_path 写 fake prompts，reload_registry 重置 registry 缓存。
"""

from pathlib import Path

import pytest
import yaml

from ai_engine.prompts import loader, registry as reg


_BASE_CFG = {
    "versions": {
        "v1": {
            "model": "claude-sonnet-4-6",
            "files": {
                "role": "v1/role.md",
                "topic_scope_c": "v1/topic_c.md",
                "topic_scope_b": "v1/topic_b.md",
                "classification": "v1/classification.md",
                "tools_usage": "v1/tools.md",
                "reply_style_b": "v1/style_b.md",
                "reply_style_c": "v1/style_c.md",
                "self_check": "v1/self_check.md",
            },
        },
        "v2": {
            "files": {
                "role": "v2/role.md",
                "topic_scope_c": "v2/topic_c.md",
                "topic_scope_b": "v2/topic_b.md",
                "classification": "v2/classification.md",
                "tools_usage": "v2/tools.md",
                "reply_style_b": "v2/style_b.md",
                "reply_style_c": "v2/style_c.md",
                "self_check": "v2/self_check.md",
            },
        },
    },
    "default": "v1",
    "rollout": {"v2": 100},  # 让 pick_version 全走 v2，便于断言灰度路径
}


def _write_prompt_files(root: Path) -> None:
    for ver in ("v1", "v2"):
        (root / ver).mkdir(exist_ok=True)
        for key, suffix in [
            ("role", "role"),
            ("topic_c", "topic_c"),
            ("topic_b", "topic_b"),
            ("classification", "classification"),
            ("tools", "tools"),
            ("style_b", "style_b"),
            ("style_c", "style_c"),
            ("self_check", "self_check"),
        ]:
            (root / ver / f"{suffix}.md").write_text(f"[{ver}/{key}]", encoding="utf-8")


@pytest.fixture
def fake_prompts(tmp_path: Path, monkeypatch) -> Path:
    _write_prompt_files(tmp_path)
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(_BASE_CFG), encoding="utf-8")
    monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
    reg.reload_registry()  # 同步清 loader._content_cache
    yield tmp_path
    reg.reload_registry()


class TestReadPromptCache:
    """缓存命中：同 key 二次读不再触发磁盘 IO。"""

    def test_returns_file_content(self, fake_prompts) -> None:
        text = loader.read_prompt("role", version="v1")
        assert text == "[v1/role]"

    def test_cache_hit_skips_disk(self, fake_prompts) -> None:
        # 第一次读填入缓存
        first = loader.read_prompt("role", version="v1")
        # 物理删除文件
        (fake_prompts / "v1/role.md").unlink()
        # 二次读应仍命中缓存
        second = loader.read_prompt("role", version="v1")
        assert first == second == "[v1/role]"

    def test_clear_cache_forces_reread(self, fake_prompts) -> None:
        loader.read_prompt("role", version="v1")
        loader.clear_cache()
        # 删文件后清缓存：再读应抛
        (fake_prompts / "v1/role.md").unlink()
        with pytest.raises(FileNotFoundError):
            loader.read_prompt("role", version="v1")

    def test_missing_key_raises_keyerror(self, fake_prompts) -> None:
        with pytest.raises(KeyError):
            loader.read_prompt("no_such_key", version="v1")

    def test_version_priority_over_subject(self, fake_prompts) -> None:
        """显式 version 优先于 subject_id 灰度。"""
        # rollout=100 → subject 应走 v2；但 version=v1 必须强制 v1
        text = loader.read_prompt("role", version="v1", subject_id="any")
        assert text == "[v1/role]"

    def test_subject_picks_via_rollout(self, fake_prompts) -> None:
        """无显式 version + 有 subject_id → 走 pick_version（这里 100% v2）。"""
        text = loader.read_prompt("role", subject_id="x")
        assert text == "[v2/role]"

    def test_no_args_returns_default(self, fake_prompts) -> None:
        text = loader.read_prompt("role")
        assert text == "[v1/role]"  # default=v1


class TestBuildSystemBlocksByUserType:
    """user_type=c/b/g 时 block 数量与构成应符合 loader 注释契约。"""

    def test_c_user_three_blocks(self, fake_prompts) -> None:
        blocks = loader.build_system_blocks("c", version="v1")
        assert len(blocks) == 3
        # 块 0：role + topic_scope_c
        assert "[v1/role]" in blocks[0]["text"]
        assert "[v1/topic_c]" in blocks[0]["text"]
        # 块 1：classification + tools_usage
        assert "[v1/classification]" in blocks[1]["text"]
        assert "[v1/tools]" in blocks[1]["text"]
        # 块 2：reply_style_c + self_check
        assert "[v1/style_c]" in blocks[2]["text"]
        assert "[v1/self_check]" in blocks[2]["text"]

    def test_b_user_uses_b_variants(self, fake_prompts) -> None:
        blocks = loader.build_system_blocks("b", version="v1")
        assert len(blocks) == 3
        assert "[v1/topic_b]" in blocks[0]["text"]
        assert "[v1/style_b]" in blocks[2]["text"]
        # 不应混入 c 变体
        assert "topic_c" not in blocks[0]["text"]
        assert "style_c" not in blocks[2]["text"]

    def test_g_user_appends_guest_constraint(self, fake_prompts) -> None:
        """游客（g）= 3 基础 + 1 未登录硬约束 = 4 块。"""
        blocks = loader.build_system_blocks("g", version="v1")
        assert len(blocks) == 4
        # g 默认走 C 变体（else 分支）
        assert "[v1/topic_c]" in blocks[0]["text"]
        # 末块为未登录约束
        guest_text = blocks[3]["text"]
        assert "未登录会话" in guest_text
        assert "登录" in guest_text

    def test_block_dict_shape(self, fake_prompts) -> None:
        """每个 block 都是 {'type': 'text', 'text': ...}。"""
        for ut in ("c", "b", "g"):
            for blk in loader.build_system_blocks(ut, version="v1"):
                assert blk["type"] == "text"
                assert isinstance(blk["text"], str)
                assert blk["text"]  # 非空


class TestBuildSystemBlocksVersionResolution:
    def test_explicit_version_wins(self, fake_prompts) -> None:
        # rollout 100 → subject 走 v2，但显式 version=v1 应优先
        blocks = loader.build_system_blocks("c", subject_id="any", version="v1")
        assert "[v1/role]" in blocks[0]["text"]

    def test_subject_grayscale_when_no_version(self, fake_prompts) -> None:
        blocks = loader.build_system_blocks("c", subject_id="any")
        assert "[v2/role]" in blocks[0]["text"]

    def test_default_when_no_subject(self, fake_prompts) -> None:
        blocks = loader.build_system_blocks("c")
        assert "[v1/role]" in blocks[0]["text"]
