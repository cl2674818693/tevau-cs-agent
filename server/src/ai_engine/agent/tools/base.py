from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ALLOWED_REPOS = {"app_frontend", "app_backend", "openapi_backend"}

# 仓库别名 → Sourcegraph 上的 repo 标识（gitlab.tevaupay.com/<group>/<project>）
REPO_MAP = {
    "app_frontend": "gitlab.tevaupay.com/tevaupay-views/app/TevauPay-Flutter",
    "app_backend": "gitlab.tevaupay.com/tevaupay/business-services/TevauPay-Service",
    "openapi_backend": "gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service",
}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]
    requires_subject_id: bool = False  # True 则 router 会强制注入 subject_id
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
