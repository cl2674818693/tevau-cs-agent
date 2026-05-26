from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(...)
    anthropic_base_url: str | None = None  # 自建 Claude 网关; None 走官方 API
    # SDK 默认 max_retries=2（指数退避，对 429/5xx/连接错误生效），显式化便于按环境调。
    anthropic_max_retries: int = 2
    # SDK 默认 timeout=600s 对聊天 UX 太长；显式收紧，单次请求超时即重试/失败。
    anthropic_timeout_seconds: float = 30.0
    db_url: str = "sqlite+aiosqlite:///./ai_engine.db"
    default_model: str = "claude-sonnet-4-6"
    heavy_model: str = "claude-opus-4-7"
    summary_model: str = "claude-haiku-4-5"  # 会话总结/压缩用轻量模型（spec §8 会话治理）
    sourcegraph_url: str = "http://localhost:7080"  # deprecated（search_code 改本地代码）
    sourcegraph_token: str = ""
    # 代码仓库本地路径（search_code/read_file 直接搜读本地代码）。
    # 别名 → 绝对路径；从 env CODE_REPO_PATHS（JSON）读。开发=本地 clone，生产=服务器代码副本。
    code_repo_paths: dict[str, str] = Field(default_factory=dict)
    # B/C 端 OpenAPI 文档目录：放多份独立文件（如 pay.openapi.json / nexus.openapi.json），
    # 各自对应一个 Apifox 项目，独立维护。目录不存在/为空时回退到单文件 openapi_doc_path。
    openapi_docs_dir: str = "./repos/api-docs"
    openapi_doc_path: str = "./repos/api-docs/openapi.json"  # 单文件兼容（deprecated，优先用目录）
    prompts_dir: str = "./src/ai_engine/prompts"
    lark_webhook_url: str | None = None
    # 事项中心推送地址。默认空：未配置时工单推送失败→走 Lark 兜底（安全可见），
    # 而不是静默打到一个不存在的 localhost mock。生产必配；本地 dev 用 mock 时设为
    # http://localhost:8000/_mock/event-center 并开 MOCK_EVENT_CENTER=true。
    event_center_url: str = ""
    event_center_secret: str = ""  # deprecated（MVP-3 用 _current/_previous）
    event_center_secret_current: str = ""  # HMAC 双 key 轮换（spec §7.4）；必填，空则拒所有回调
    event_center_secret_previous: str | None = None
    mock_event_center: bool = False  # 仅本地 dev 挂 /_mock/event-center receiver
    staff_jwt_secret: str = ""  # 客服 JWT 签名密钥（HS256）；空则拒签发/验签（防空密钥伪造）
    bu_session_secret: str = ""  # B 端 session cookie 签名密钥（HS256）；空则拒签发/验签
    # 仅内网/联调用：信任客户端 X-BU-ID header 直接当 B 端身份（生产必须 False，否则可伪造身份）
    dev_trust_bu_header: bool = False
    metrics_auth_token: str = ""  # /metrics Bearer 鉴权令牌；空=不鉴权（需配合网络层限制）
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    unlimitpay_db_url: str | None = None  # 业务只读库（MVP-2 必填；MVP-1 测试时 None）
    nexus_db_url: str | None = None
    # C 端身份：APP 经 JS Bridge 注入 Sa-Token（不透明 UUID，非 JWT），本服务拿它调下面的
    # gateway getCurrentUserInfo 换用户身份（userCode）。原 RS256 JWT 验签方案已作废。
    c_app_api_base: str = "https://test2.tevaupay.com/gateway"  # C 端 OpenAPI 网关；按环境配
    c_app_api_version: str = "2.0.002"  # 部分网关校验 version header
    c_identity_cache_ttl: int = 300  # token→userCode 缓存秒数，避免每请求一次远程校验
    c_identity_timeout_seconds: float = 5.0
    daily_token_limit: int = 500_000  # 单 BU/单 user 单日 token 硬阈值（spec §8 成本治理）
    chat_rate_limit_per_min: int = 30  # 单 subject 每分钟消息上限（spec §6.4 兜底层）
    # 限流共享存储；配置后多副本全局精确计数，未配则回退进程内（单副本/测试）
    redis_url: str | None = None
    # 图片附件对象存储（S3 兼容：dev=MinIO，生产=OSS/S3）。多实例需共享存储，故不用本地卷。
    object_store_endpoint: str = "http://localhost:9000"
    object_store_bucket: str = "cs-attachments"
    object_store_access_key: str = ""
    object_store_secret_key: str = ""
    object_store_region: str = "us-east-1"  # MinIO 任意值即可
    attachment_max_bytes: int = 5 * 1024 * 1024  # 单图 5MB
    attachment_max_per_message: int = 4
    attachment_url_ttl_seconds: int = 300  # 预签名 URL 时效
    topic_classifier_enabled: bool = False  # spec §6.4 第二层 haiku 前置分类（MVP-2 起，按需开启）
    max_tool_depth: int = 12
    max_tool_result_bytes: int = 262_144
    # 回合处理中(status=processing)超过此时长视为僵尸（服务崩溃/卡死），后台标 failed
    stale_turn_timeout_seconds: int = 120
    stale_sweep_interval_seconds: int = 60  # 后台清理扫描间隔；<=0 关闭后台任务
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _default_mock_event_center_url(self) -> "Settings":
        # 本地 dev 开了 mock 但没显式配 URL 时，自动指向本地 mock receiver，
        # 省去手动配 EVENT_CENTER_URL；生产（mock 关）保持空 → Lark 兜底。
        if self.mock_event_center and not self.event_center_url:
            self.event_center_url = "http://localhost:8000/_mock/event-center"
        return self


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
