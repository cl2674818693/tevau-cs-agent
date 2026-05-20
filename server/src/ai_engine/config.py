from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(...)
    anthropic_base_url: str | None = None  # 自建 Claude 网关; None 走官方 API
    db_url: str = "sqlite+aiosqlite:///./ai_engine.db"
    default_model: str = "claude-sonnet-4-6"
    heavy_model: str = "claude-opus-4-7"
    summary_model: str = "claude-haiku-4-5"  # 会话总结/压缩用轻量模型（spec §8 会话治理）
    sourcegraph_url: str = "http://localhost:7080"
    sourcegraph_token: str = ""
    openapi_doc_path: str = "./repos/api-docs/openapi.json"
    prompts_dir: str = "./src/ai_engine/prompts"
    lark_webhook_url: str | None = None
    event_center_url: str = "http://localhost:8000/_mock/event-center"
    event_center_secret: str = "mvp1-shared-secret"  # deprecated（MVP-3 用 _current/_previous）
    event_center_secret_current: str = "mvp1-shared-secret"  # HMAC 双 key 轮换（spec §7.4）
    event_center_secret_previous: str | None = None
    mock_event_center: bool = False  # 仅本地 dev 挂 /_mock/event-center receiver
    staff_jwt_secret: str = ""  # 客服 JWT 签名密钥（HS256，本服务签发本服务验证）
    unlimitpay_db_url: str | None = None  # 业务只读库（MVP-2 必填；MVP-1 测试时 None）
    nexus_db_url: str | None = None
    app_jwt_public_key: str = ""  # C 端 APP JWT 验签公钥（APP 后端签发，本服务只验签）
    app_jwt_algorithm: str = "RS256"
    max_tool_depth: int = 12
    max_tool_result_bytes: int = 262_144
    log_level: str = "INFO"


_instance: Settings | None = None


class _SettingsProxy:
    def __getattr__(self, item: str) -> Any:  # 代理转发, 类型由 Settings 字段决定
        global _instance
        if _instance is None:
            _instance = Settings()  # type: ignore[call-arg]  # pydantic-settings 从 env 读
        return getattr(_instance, item)

    def reload(self) -> None:
        global _instance
        _instance = Settings()  # type: ignore[call-arg]  # pydantic-settings 从 env 读


settings = _SettingsProxy()
