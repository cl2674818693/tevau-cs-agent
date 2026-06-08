from pathlib import Path

from ai_engine.config import settings

# prompt 文件内容缓存（key=prompt_key）。文件运行期不变（变更走部署重启），
# 缓存后避免每请求同步 read_text 阻塞事件循环。
_content_cache: dict[str, str] = {}


def clear_cache() -> None:
    _content_cache.clear()


def read_prompt(key: str) -> str:
    """读取一份 prompt 文件（按 key 直接对应 prompts/<key>.md）。"""
    cached = _content_cache.get(key)
    if cached is not None:
        return cached
    path = Path(settings.prompts_dir) / f"{key}.md"
    content = path.read_text(encoding="utf-8")
    _content_cache[key] = content
    return content


def build_system_blocks(user_type: str) -> list[dict[str, str]]:
    role = read_prompt("role")
    # spec §6.4 话题边界第一层；按受众分版：B 端含 Open API 口径，C 端/游客不暴露 Open API
    topic_scope = read_prompt("topic_scope.b") if user_type == "b" else read_prompt("topic_scope.c")
    classification = read_prompt("classification")
    tools_usage = read_prompt("tools_usage")
    # 按 user_type 切换回复风格（C 端 / 游客语言化，B 端技术化）
    style = read_prompt("reply_style.b") if user_type == "b" else read_prompt("reply_style.c")
    self_check = read_prompt("self_check")
    # 多个 system 块；topic_scope 与 reply_style 放靠前，让模型先看到约束
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
