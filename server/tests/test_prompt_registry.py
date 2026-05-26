import shutil

import pytest

from ai_engine.prompts import registry
from ai_engine.prompts.loader import build_system_blocks, read_prompt


def test_default_version_and_files_exist():
    registry.reload_registry()
    v = registry.default_version()
    assert v == "v1.0.0"  # 稳定基线
    # 两个版本所有 key 文件都能读
    for version in ("v1.0.0", "v1.1.0"):
        for key in ("role", "topic_scope_c", "topic_scope_b", "classification", "tools_usage", "self_check"):
            assert registry.file_path(version, key).exists()


def test_pick_version_is_deterministic():
    registry.reload_registry()
    a = registry.pick_version("BU00243780")
    b = registry.pick_version("BU00243780")
    assert a == b
    assert a in registry.list_versions()


def test_canary_rollout_splits_and_falls_back_to_default():
    registry.reload_registry()
    # registry 是 v1.1.0:20 灰度，余 80% 回落 default(v1.0.0)
    counts = {"v1.0.0": 0, "v1.1.0": 0}
    for i in range(2000):
        counts[registry.pick_version(f"user-{i}")] += 1
    # 大头落稳定版，实验版拿到一部分（宽松边界）
    assert counts["v1.0.0"] > counts["v1.1.0"]
    assert counts["v1.1.0"] > 100


def test_hash_bucketing_splits_by_ratio(monkeypatch):
    fake = {
        "versions": {
            "v1.0.0": {"model": "m0", "files": {}},
            "v1.1.0": {"model": "m1", "files": {}},
        },
        "default": "v1.0.0",
        "rollout": {"v1.1.0": 50, "v1.0.0": 50},
    }
    monkeypatch.setattr(registry, "_cache", fake)
    counts = {"v1.0.0": 0, "v1.1.0": 0}
    for i in range(2000):
        counts[registry.pick_version(f"user-{i}")] += 1
    # 50/50 灰度：两边都拿到相当份额（宽松边界，避免哈希偶然偏斜误报）
    assert counts["v1.0.0"] > 700
    assert counts["v1.1.0"] > 700


def test_model_for_reads_registry():
    registry.reload_registry()
    assert registry.model_for("v1.1.0") == "claude-sonnet-4-6"


def test_build_system_blocks_with_explicit_version():
    text = "\n".join(b["text"] for b in build_system_blocks("c", version="v1.0.0"))
    assert "大白话" in text  # C 端风格来自 v1.0.0


def test_read_prompt_by_subject_id():
    registry.reload_registry()
    content = read_prompt("role", subject_id="BU1")
    assert len(content) > 0


def test_versions_have_real_diff():
    """v1.1.0 是实验版，含 v1.0.0 没有的"复述确认"增强（灰度才有意义）。"""
    registry.reload_registry()
    base = read_prompt("self_check", version="v1.0.0")
    exp = read_prompt("self_check", version="v1.1.0")
    assert base != exp
    assert "复述" not in base
    assert "复述" in exp


# ── Task 6.1 新增测试 ────────────────────────────────────────────────────────

def test_validate_version_files_passes_for_existing_version():
    """validate_version_files 对完整版本无异常。"""
    registry.reload_registry()
    # 不 raise 即通过
    registry.validate_version_files("v1.0.0")
    registry.validate_version_files("v1.1.0")


def test_validate_version_files_raises_for_missing_file(tmp_path, monkeypatch):
    """validate_version_files 对缺文件的版本 raise ValueError。"""
    # 把 prompts 目录复制到 tmp，删掉一个文件，让 registry 指向 tmp
    import os

    src = "src/ai_engine/prompts"
    dst = tmp_path / "prompts"
    shutil.copytree(src, dst)
    # 删掉 v1.0.0/role.md
    os.remove(dst / "v1.0.0" / "role.md")

    monkeypatch.setenv("PROMPTS_DIR", str(dst))
    from ai_engine.config import settings
    settings.reload()
    registry.reload_registry()

    with pytest.raises(ValueError, match="role"):
        registry.validate_version_files("v1.0.0")

    # 恢复
    monkeypatch.undo()
    settings.reload()
    registry.reload_registry()


def test_update_rollout_rejects_version_with_missing_files(tmp_path, monkeypatch):
    """update_rollout 指向缺文件的版本时 raise ValueError，阻止写入。"""
    import os

    src = "src/ai_engine/prompts"
    dst = tmp_path / "prompts"
    shutil.copytree(src, dst)
    os.remove(dst / "v1.1.0" / "role.md")

    monkeypatch.setenv("PROMPTS_DIR", str(dst))
    from ai_engine.config import settings
    settings.reload()
    registry.reload_registry()

    with pytest.raises(ValueError):
        registry.update_rollout({"v1.1.0": 10, "v1.0.0": 90})

    monkeypatch.undo()
    settings.reload()
    registry.reload_registry()


def test_update_rollout_succeeds_when_all_files_present(tmp_path, monkeypatch):
    """update_rollout 对所有文件齐全的版本正常写入。"""
    src = "src/ai_engine/prompts"
    dst = tmp_path / "prompts"
    shutil.copytree(src, dst)

    monkeypatch.setenv("PROMPTS_DIR", str(dst))
    from ai_engine.config import settings
    settings.reload()
    registry.reload_registry()

    # 应不 raise
    registry.update_rollout({"v1.1.0": 30, "v1.0.0": 70})
    assert registry.get_rollout() == {"v1.1.0": 30, "v1.0.0": 70}

    monkeypatch.undo()
    settings.reload()
    registry.reload_registry()
