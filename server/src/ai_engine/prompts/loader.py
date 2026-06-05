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
                    "也不要承诺创建工单或转人工。\n\n"
                    "**重要：query_user / query_card / query_balance / query_transaction /"
                    " query_kyc / query_financing / query_stock / query_bu_* / create_ticket 等所有需要身份的工具，runtime"
                    " 会硬拒（返回 'guest not allowed'）——调了等于白白浪费一个 turn 且把"
                    "'被拒'结果灌给你自己当上下文。所以宁可不调也不要试探，直接用文字答用户：'"
                    "您还没登录，无法查询您的账户信息，请在 APP 内登录后再发起咨询'。"
                ),
            }
        )
    return blocks
