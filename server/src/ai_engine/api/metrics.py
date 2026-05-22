from fastapi import APIRouter, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ai_engine.config import settings

router = APIRouter()


@router.get("/metrics")
async def metrics(authorization: str = Header(default="")) -> Response:
    # 配置了 METRICS_AUTH_TOKEN 时要求 Bearer 鉴权，防公网泄露 staff_id/业务量等运营指标。
    # 未配置时放行（向后兼容现有 prometheus 抓取），生产应配 token 或用网络层限制。
    token = settings.metrics_auth_token
    if token and authorization != f"Bearer {token}":
        raise HTTPException(401, "unauthorized")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
