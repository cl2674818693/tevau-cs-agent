"""A3: prompt 文件内容缓存，消除每次请求的同步 read_text 阻塞事件循环。"""

from pathlib import Path

from ai_engine.prompts import loader, registry


def test_read_prompt_caches_file_content(monkeypatch):
    loader.clear_cache()
    version = registry.default_version()

    calls = {"n": 0}
    real_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        calls["n"] += 1
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    first = loader.read_prompt("role", version=version)
    second = loader.read_prompt("role", version=version)

    assert first == second
    assert first  # 非空
    assert calls["n"] == 1, "第二次应命中缓存，不再读盘"


def test_reload_registry_clears_prompt_cache():
    version = registry.default_version()
    loader.read_prompt("role", version=version)
    assert loader._content_cache  # 已有缓存

    registry.reload_registry()
    assert loader._content_cache == {}, "registry 重载应清空 prompt 内容缓存"
