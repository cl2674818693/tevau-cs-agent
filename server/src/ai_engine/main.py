from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_engine.api.chat import router as chat_router
from ai_engine.api.conversations import router as conversations_router
from ai_engine.api.health import router as health_router
from ai_engine.api.staff_auth import router as staff_auth_router
from ai_engine.api.staff_conversations import router as staff_conv_router
from ai_engine.api.tickets import router as tickets_router
from ai_engine.api.user_events import router as user_events_router
from ai_engine.integrations.event_center_mock import router as mock_ec_router
from ai_engine.persistence.db import init_db

app = FastAPI(title="Tevau 客服工单 AI 引擎 (MVP-1)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Last-Event-ID"],  # SSE 重连支持，spec §3.3
)
app.include_router(health_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(tickets_router)
app.include_router(staff_auth_router)
app.include_router(staff_conv_router)
app.include_router(user_events_router)
app.include_router(mock_ec_router)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()
