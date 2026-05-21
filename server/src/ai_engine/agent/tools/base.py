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
