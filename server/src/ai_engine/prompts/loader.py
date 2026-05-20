from pathlib import Path

from ai_engine.config import settings


def _read(name: str) -> str:
    p = Path(settings.prompts_dir) / name
    return p.read_text(encoding="utf-8")


def build_system_blocks(user_type: str) -> list[dict[str, str]]:
    role = _read("role.md")
    topic_scope = _read("topic_scope.md")  # spec §6.4 话题边界第一层（MVP-1 唯一防御）
    classification = _read("classification.md")
    tools_usage = _read("tools_usage.md")
    # MVP-1 仅 B 端风格；C 端 reply_style.c.md 在 MVP-2 接入后按 user_type 切换
    style = _read("reply_style.b.md")
    self_check = _read("self_check.md")
    # 多个 system 块，每块单独缓存；topic_scope 与 reply_style 放靠前，让模型先看到约束
    return [
        {"type": "text", "text": role + "\n\n" + topic_scope},
        {"type": "text", "text": classification + "\n\n" + tools_usage},
        {"type": "text", "text": style + "\n\n" + self_check},
    ]
