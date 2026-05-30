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
    # spec §6.4 话题边界第一层；按受众分版：B 端含 Open API 口径，C 端/游客不暴露 Open API
    topic_scope = rd("topic_scope_b") if user_type == "b" else rd("topic_scope_c")
    classification = rd("classification")
    tools_usage = rd("tools_usage")
    # MVP-2：按 user_type 切换回复风格（C 端 / 游客语言化，B 端技术化）
    style = rd("reply_style_b") if user_type == "b" else rd("reply_style_c")
    self_check = rd("self_check")
    # 多个 system 块，每块单独缓存；topic_scope 与 reply_style 放靠前，让模型先看到约束
    blocks = [
        {"type": "text", "text": role + "\n\n" + topic_scope},
        {"type": "text", "text": classification + "\n\n" + tools_usage},
        {"type": "text", "text": style + "\n\n" + self_check},
    ]
    # 游客（未登录）追加硬约束：只答通用问题，禁止个人数据查询/转人工
    if user_type == "g":
        blocks.append(
            {
                "type": "text",
                "text": (
                    "【未登录会话】当前用户未登录。你只能解答通用问题（API 用法、APP 功能、"
                    "公开文档说明）。任何涉及该用户个人账户、卡片、余额、交易、订单的请求，"
                    "都不要调用查询工具，而是礼貌告知：需在 APP 内登录后才能查询。"
                    "也不要承诺创建工单或转人工。"
                ),
            }
        )
    return blocks


# M3b: async DB-first 入口（独立于 read_prompt 同步链路；为后续 runtime 接入做准备）。
async def load(version: str, file_name: str) -> str:
    """DB-first：优先读 prompt_drafts 已发布版本；缺失回退文件。

    设计上独立于既有同步 read_prompt：runtime 链路改造为 async 后再接入。
    M3b 阶段只为新增的 Prompt 编辑/预览路径提供。
    """
    try:
        from ai_engine.persistence.prompt_drafts import get_published

        row = await get_published(version, file_name)
        if row is not None:
            return str(row["content"])
    except Exception:
        pass
    return _read_file(version, file_name)


def _read_file(version: str, file_name: str) -> str:
    from pathlib import Path

    from ai_engine.config import settings
    return Path(settings.prompts_dir, version, file_name).read_text(encoding="utf-8")
