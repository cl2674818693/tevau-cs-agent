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
