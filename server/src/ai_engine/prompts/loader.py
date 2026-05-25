from ai_engine.prompts import registry

# prompt 文件内容缓存（key=(version, prompt_key)）。文件运行期不变（变更走部署重启），
# 缓存后避免每请求同步 read_text 阻塞事件循环。registry 重载时清空。
_content_cache: dict[tuple[str, str], str] = {}


def clear_cache() -> None:
    _content_cache.clear()


def _resolve_version(version: str | None, subject_id: str | None) -> str:
    if version is not None:
        return version
    return registry.pick_version(subject_id) if subject_id else registry.default_version()


def read_prompt(key: str, version: str | None = None, subject_id: str | None = None) -> str:
    """读取某版本的 prompt 文件。version 优先；否则按 subject_id 灰度；都缺省取 default。"""
    v = _resolve_version(version, subject_id)
    cache_key = (v, key)
    cached = _content_cache.get(cache_key)
    if cached is not None:
        return cached
    content = registry.file_path(v, key).read_text(encoding="utf-8")
    _content_cache[cache_key] = content
    return content


def build_system_blocks(
    user_type: str, subject_id: str | None = None, version: str | None = None
) -> list[dict[str, str]]:
    v = _resolve_version(version, subject_id)

    def rd(key: str) -> str:
        return read_prompt(key, version=v)

    role = rd("role")
    topic_scope = rd("topic_scope")  # spec §6.4 话题边界第一层（MVP-1 唯一防御）
    classification = rd("classification")
    tools_usage = rd("tools_usage")
    # MVP-2：按 user_type 切换回复风格（C 端语言化 / B 端技术化）
    style = rd("reply_style_c") if user_type == "c" else rd("reply_style_b")
    self_check = rd("self_check")
    # 多个 system 块，每块单独缓存；topic_scope 与 reply_style 放靠前，让模型先看到约束
    return [
        {"type": "text", "text": role + "\n\n" + topic_scope},
        {"type": "text", "text": classification + "\n\n" + tools_usage},
        {"type": "text", "text": style + "\n\n" + self_check},
    ]
