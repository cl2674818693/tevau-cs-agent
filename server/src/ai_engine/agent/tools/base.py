from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

# 代码仓库别名（本地路径见 settings.code_repo_paths；各别名含义见 search_code 工具说明）
ALLOWED_REPOS = {"app_frontend", "app_backend", "openapi_backend"}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]
    requires_subject_id: bool = False  # True 则 router 会强制注入身份
    subject_field: str = "subject_id"  # 身份值注入到 handler 的哪个参数（C=user_id/B=tenant_id…）
    supports_unmask: bool = False  # True 则 engineer 代查时可解锁部分脱敏（spec §13.3）


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    REGISTRY[tool.name] = tool


def get(name: str) -> Tool | None:
    return REGISTRY.get(name)


def all_definitions() -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in REGISTRY.values()
    ]


def label(mapping: dict, value):
    """枚举翻译：未命中的非空值显式标注为 未知(原值)，不静默吐裸数字。"""
    if value is None:
        return None
    return mapping.get(value, f"未知({value})")


def scope_note(source: str, covered: str, not_covered: str) -> str:
    """查空时给 AI 的边界说明，避免把'本表无'当成'用户无'。"""
    return f"本次仅查询了{source}（覆盖：{covered}）。未覆盖：{not_covered}。查不到不代表用户没有相关记录。"


_HIDDEN_PLACEHOLDER = "[hidden — 内部细节不向用户暴露；engineer 可 unmask 代查]"


def gated(value: Any, unmasked: bool, placeholder: str = _HIDDEN_PLACEHOLDER) -> Any:
    """敏感原文字段门控：unmasked=False 且字段有值时返回占位字符串；无值返回 None；unmasked=True 透传。
    用于决策原因 / 风控原因 / 三方失败明细等"内部细节"字段——AI 看到占位串应只翻译业务结论给用户。"""
    if value is None or value == "":
        return None
    return value if unmasked else placeholder
