from ai_engine.prompts import registry


def _resolve_version(version: str | None, subject_id: str | None) -> str:
    if version is not None:
        return version
    return registry.pick_version(subject_id) if subject_id else registry.default_version()


def read_prompt(key: str, version: str | None = None, subject_id: str | None = None) -> str:
    """读取某版本的 prompt 文件。version 优先；否则按 subject_id 灰度；都缺省取 default。"""
    v = _resolve_version(version, subject_id)
    return registry.file_path(v, key).read_text(encoding="utf-8")


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
