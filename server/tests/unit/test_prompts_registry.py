"""Unit tests: prompts.registry

被测对象：prompt 版本注册表 + subject_id 哈希分桶灰度（spec §8）。
mock 策略：用 tmp_path 写一个完整 fake registry.yaml + 假 prompt 文件，
monkeypatch settings.prompts_dir 指向它；每个 case reload 清缓存避免相互污染。
"""

from pathlib import Path

import pytest
import yaml

from ai_engine.prompts import registry as reg


_REG_YAML_FULL = {
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
            "model": "claude-opus-4-7",
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
    "rollout": {"v2": 30},  # 30% 走 v2，其余 70% 落 default v1
}


@pytest.fixture
def fake_prompts_dir(tmp_path: Path, monkeypatch) -> Path:
    """构造完整 prompts 目录：registry.yaml + 各 prompt 占位文件。"""
    (tmp_path / "v1").mkdir()
    (tmp_path / "v2").mkdir()
    for ver_files in _REG_YAML_FULL["versions"].values():
        for rel in ver_files["files"].values():
            (tmp_path / rel).write_text(f"# content of {rel}\n", encoding="utf-8")
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(_REG_YAML_FULL), encoding="utf-8")
    monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
    reg.reload_registry()
    yield tmp_path
    reg.reload_registry()


class TestLoadAndDefault:
    def test_default_version_reads_yaml(self, fake_prompts_dir) -> None:
        assert reg.default_version() == "v1"

    def test_list_versions(self, fake_prompts_dir) -> None:
        assert sorted(reg.list_versions()) == ["v1", "v2"]

    def test_get_rollout(self, fake_prompts_dir) -> None:
        assert reg.get_rollout() == {"v2": 30}

    def test_load_registry_caches(self, fake_prompts_dir) -> None:
        a = reg.load_registry()
        b = reg.load_registry()
        assert a is b  # 同一对象 = 命中缓存

    def test_reload_clears_cache_and_loader(self, fake_prompts_dir, monkeypatch) -> None:
        """reload_registry 应同步清 loader._content_cache。"""
        from ai_engine.prompts import loader

        # 先填一点 loader 缓存
        loader._content_cache[("v1", "role")] = "stale"
        reg.reload_registry()
        assert ("v1", "role") not in loader._content_cache


class TestPickVersion:
    """按 subject_id md5 → 0-99 桶；累计到 30 走 v2，其余落 default。"""

    def test_returns_only_versions_in_registry(self, fake_prompts_dir) -> None:
        seen: set[str] = set()
        for i in range(200):
            v = reg.pick_version(f"sub-{i}")
            seen.add(v)
        assert seen.issubset({"v1", "v2"})

    def test_rollout_distribution_roughly_matches(self, fake_prompts_dir) -> None:
        """30% 桶大致达成（用 1000 样本 ±5%）。"""
        v2_count = sum(1 for i in range(1000) if reg.pick_version(f"sub-{i}") == "v2")
        # 期望 ~300；md5 分布良好，给 ±5% 容差
        assert 250 <= v2_count <= 350

    def test_same_subject_same_version_stable(self, fake_prompts_dir) -> None:
        """同一 subject_id 多次调用必须落同一版本（灰度稳定）。"""
        v1 = reg.pick_version("subject-42")
        for _ in range(50):
            assert reg.pick_version("subject-42") == v1

    def test_rollout_zero_falls_back_to_default(self, tmp_path: Path, monkeypatch) -> None:
        """rollout 总和 0 时所有桶都落 default。"""
        cfg = {
            "versions": {"v1": {"files": {"role": "v1/role.md"}}},
            "default": "v1",
            "rollout": {},
        }
        (tmp_path / "v1").mkdir()
        (tmp_path / "v1/role.md").write_text("x", encoding="utf-8")
        (tmp_path / "registry.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
        reg.reload_registry()
        for i in range(20):
            assert reg.pick_version(f"x-{i}") == "v1"

    def test_rollout_100_pct_always_picks_that_version(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        cfg = {
            "versions": {
                "v1": {"files": {"role": "v1/role.md"}},
                "v2": {"files": {"role": "v2/role.md"}},
            },
            "default": "v1",
            "rollout": {"v2": 100},
        }
        (tmp_path / "v1").mkdir()
        (tmp_path / "v2").mkdir()
        (tmp_path / "v1/role.md").write_text("x", encoding="utf-8")
        (tmp_path / "v2/role.md").write_text("y", encoding="utf-8")
        (tmp_path / "registry.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
        reg.reload_registry()
        for i in range(50):
            assert reg.pick_version(f"x-{i}") == "v2"


class TestFilePathAndModel:
    def test_file_path_resolves(self, fake_prompts_dir) -> None:
        p = reg.file_path("v1", "role")
        assert p == fake_prompts_dir / "v1/role.md"
        assert p.exists()

    def test_model_for_returns_string(self, fake_prompts_dir) -> None:
        assert reg.model_for("v1") == "claude-sonnet-4-6"
        assert reg.model_for("v2") == "claude-opus-4-7"

    def test_model_for_none_when_missing(self, tmp_path: Path, monkeypatch) -> None:
        cfg = {
            "versions": {"v1": {"files": {"role": "v1/role.md"}}},
            "default": "v1",
            "rollout": {},
        }
        (tmp_path / "v1").mkdir()
        (tmp_path / "v1/role.md").write_text("x", encoding="utf-8")
        (tmp_path / "registry.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
        reg.reload_registry()
        assert reg.model_for("v1") is None


class TestValidateVersionFiles:
    def test_validate_ok_when_all_present(self, fake_prompts_dir) -> None:
        reg.validate_version_files("v1")  # 不应抛
        reg.validate_version_files("v2")

    def test_validate_raises_on_missing(self, fake_prompts_dir) -> None:
        # 故意删一个文件
        (fake_prompts_dir / "v1/role.md").unlink()
        with pytest.raises(ValueError) as exc:
            reg.validate_version_files("v1")
        assert "role" in str(exc.value)
        assert "v1" in str(exc.value)


class TestRegistryErrors:
    def test_missing_registry_file_raises(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
        reg.reload_registry()
        with pytest.raises(FileNotFoundError):
            reg.load_registry()

    def test_invalid_yaml_raises(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "registry.yaml").write_text("default: [oops\n", encoding="utf-8")
        monkeypatch.setattr(reg.settings, "prompts_dir", str(tmp_path), raising=False)
        reg.reload_registry()
        with pytest.raises(yaml.YAMLError):
            reg.load_registry()

    def test_file_path_unknown_version_keyerror(self, fake_prompts_dir) -> None:
        with pytest.raises(KeyError):
            reg.file_path("no-such-version", "role")

    def test_file_path_unknown_key_keyerror(self, fake_prompts_dir) -> None:
        with pytest.raises(KeyError):
            reg.file_path("v1", "no_such_key")
