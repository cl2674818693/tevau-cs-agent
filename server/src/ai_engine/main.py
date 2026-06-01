import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_engine.api.admin_dashboard import router as admin_dashboard_router
from ai_engine.api.admin_guardrails import router as admin_guardrails_router
from ai_engine.api.admin_knowledge import router as admin_knowledge_router
from ai_engine.api.admin_prompt_editor import router as admin_prompt_editor_router
from ai_engine.api.admin_prompts import router as admin_prompts_router
from ai_engine.api.admin_rbac import router as admin_rbac_router
from ai_engine.api.admin_routing_rules import router as admin_routing_rules_router
from ai_engine.api.admin_shifts import router as admin_shifts_router
from ai_engine.api.admin_sla import router as admin_sla_router
from ai_engine.api.admin_staff import router as admin_staff_router
from ai_engine.api.admin_staff_groups import router as admin_staff_groups_router
from ai_engine.api.admin_tool_policies import router as admin_tool_policies_router
from ai_engine.api.agent_ratings import router as agent_ratings_router
from ai_engine.api.attachments import router as attachments_router
from ai_engine.api.auth_bu import router as auth_bu_router
from ai_engine.api.chat import router as chat_router
from ai_engine.api.conversation_stream import router as conversation_stream_router
from ai_engine.api.conversations import router as conversations_router
from ai_engine.api.feedback import router as feedback_router
from ai_engine.api.health import router as health_router
from ai_engine.api.insights import router as insights_router
from ai_engine.api.metrics import router as metrics_router
from ai_engine.api.staff_auth import router as staff_auth_router
from ai_engine.api.staff_conversations import router as staff_conv_router
from ai_engine.api.staff_kpi import router as staff_kpi_router
from ai_engine.api.staff_logs import router as staff_logs_router
from ai_engine.api.staff_presence import router as staff_presence_router
from ai_engine.api.ticket_events_sse import router as ticket_sse_router
from ai_engine.api.tickets import router as tickets_router
from ai_engine.api.user_events import router as user_events_router
from ai_engine.config import settings
from ai_engine.integrations.event_center_mock import router as mock_ec_router
from ai_engine.persistence.business_db import init_business_dbs
from ai_engine.persistence.db import init_db
from ai_engine.persistence.maintenance import sweep_loop

logger = logging.getLogger(__name__)

app = FastAPI(title="Tevau 客服工单 AI 引擎 (MVP-1)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,  # 生产经 CORS_ALLOW_ORIGINS 配真实域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Last-Event-ID"],  # SSE 重连支持，spec §3.3
)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(auth_bu_router)
app.include_router(conversations_router)
app.include_router(conversation_stream_router)
app.include_router(chat_router)
app.include_router(tickets_router)
app.include_router(ticket_sse_router)
app.include_router(staff_auth_router)
app.include_router(staff_conv_router)
app.include_router(staff_presence_router)
app.include_router(staff_kpi_router)
app.include_router(staff_logs_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_guardrails_router)
app.include_router(admin_knowledge_router)
app.include_router(admin_prompt_editor_router)
app.include_router(admin_prompts_router)
app.include_router(admin_rbac_router)
app.include_router(admin_routing_rules_router)
app.include_router(admin_shifts_router)
app.include_router(admin_sla_router)
app.include_router(admin_staff_router)
app.include_router(admin_staff_groups_router)
app.include_router(admin_tool_policies_router)
app.include_router(agent_ratings_router)
app.include_router(user_events_router)
app.include_router(feedback_router)
app.include_router(insights_router)
app.include_router(attachments_router)
if settings.mock_event_center:  # 仅本地 dev；生产连真实事项中心
    app.include_router(mock_ec_router)


_sweep_task: asyncio.Task[None] | None = None


@app.on_event("startup")
async def _startup() -> None:
    await init_db()
    # 幂等建对象存储 bucket（缺桶时上传图片会 500）。失败不阻断启动，只记日志。
    try:
        from ai_engine.storage.object_store import ensure_bucket

        await ensure_bucket()
    except Exception:
        logger.exception("ensure object-store bucket failed")
    # 业务只读库（URL 未配时跳过，MVP-1 模式不连）
    await init_business_dbs(settings.unlimitpay_db_url, settings.nexus_db_url)
    # 配置 REDIS_URL 时拉起会话事件跨副本订阅桥（多副本实时事件互通）
    from ai_engine.api.staff_conversations import start_redis_bridge

    await start_redis_bridge()
    # 后台清理僵尸回合（processing 超时）；interval<=0 时不启动
    global _sweep_task
    if settings.stale_sweep_interval_seconds > 0:
        _sweep_task = asyncio.create_task(sweep_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _sweep_task
    if _sweep_task:
        _sweep_task.cancel()
        _sweep_task = None
