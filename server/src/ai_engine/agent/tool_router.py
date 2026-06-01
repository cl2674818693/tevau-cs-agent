import json
import time
from typing import Any

from ai_engine.agent.tools import base
from ai_engine.auth.bu_session import USER_TYPE_C, USER_TYPE_GUEST
from ai_engine.observability import metrics
from ai_engine.persistence.audit import log_tool_call
from ai_engine.persistence.business_db import get_db

NEEDS_CONVERSATION_ID = {"create_ticket"}
NEEDS_USER_TYPE = {"create_ticket"}


def _result_count(data: object) -> int:
    """从工具返回推断有效结果条数：优先 *count* 整数键之和；否则 list 值长度之和；
    否则按非空记录算(排除 note/unmasked/pii_note 等元字段)，非空记 1。"""
    if not isinstance(data, dict):
        return 1 if data else 0
    count_vals = [v for k, v in data.items() if k.endswith("count") and isinstance(v, int)]
    if count_vals:
        return sum(count_vals)
    lists = [v for v in data.values() if isinstance(v, list)]
    if lists:
        return sum(len(v) for v in lists)
    records = [v for k, v in data.items()
               if k not in ("note", "unmasked", "pii_note") and v not in (None, {}, [], "")]
    return 1 if records else 0

# C 端会话身份是 gateway 的 userCode（如 U43825474），但业务库各表按数字 user_id 隔离。
# 注入工具前必须把 userCode 翻成数字 id，否则 WHERE user_id='U...' 永远查空（KYC/流水全查不到）。
_c_user_id_cache: dict[str, str] = {}


async def _c_user_id(user_code: str) -> str | None:
    """C 端 userCode → 业务库数字 user_id（t_tevaupay_user.id）；缓存避免每次打库。"""
    cached = _c_user_id_cache.get(user_code)
    if cached is not None:
        return cached
    row = await get_db("unlimitpay").fetch_one(
        "SELECT id FROM t_tevaupay_user WHERE user_code=%s", (user_code,)
    )
    if not row or row.get("id") is None:
        return None
    uid = str(row["id"])
    _c_user_id_cache[user_code] = uid
    return uid

# 游客（未登录）拒绝个人数据工具时给 AI 的回执，引导其提示用户登录
_GUEST_BLOCKED = (
    "用户未登录，无法查询其个人账户/卡片/余额/交易/订单等数据。"
    "请提示用户在 APP 内登录后再查询；通用问题（API 用法、APP 功能、文档）可正常解答。"
)


async def _resolve_ai_unmask(unmask: bool | None, tool_name: str) -> bool:  # noqa: ARG001
    """unmask=None → 默认 False（安全保留：AI 自动调用工具不解锁脱敏字段）。
    客服代查端点显式传 True/False，不走本函数路径。"""
    if unmask is not None:
        return unmask
    return False


async def dispatch(
    *,
    tool_name: str,
    params: dict[str, object],
    user_type: str,
    subject_id: str,
    conversation_id: int,
    unmask: bool | None = None,
) -> dict[str, Any]:
    """unmask=None → 默认 False（AI 自动调用不解锁脱敏）；客服代查端点显式传 True/False。"""
    unmask = await _resolve_ai_unmask(unmask, tool_name)
    tool = base.get(tool_name)
    if tool is None:
        await log_tool_call(
            conversation_id, tool_name, params, 0, 0, True, "unknown tool",
            result_count=0, is_empty=True, subject_id=subject_id, user_type=user_type,
        )
        metrics.tool_calls.labels(tool=tool_name, ok="false").inc()
        return {"ok": False, "error": f"unknown tool: {tool_name}"}

    # 游客降级：未登录用户禁用一切需要身份隔离的工具（含 create_ticket），返回引导登录回执。
    if user_type == USER_TYPE_GUEST and tool.requires_subject_id:
        await log_tool_call(
            conversation_id, tool_name, params, 0, 0, True, "guest not allowed",
            result_count=0, is_empty=True, subject_id=subject_id, user_type=user_type,
        )
        metrics.tool_calls.labels(tool=tool_name, ok="false").inc()
        return {"ok": False, "error": _GUEST_BLOCKED}

    # 身份注入：把会话身份强写入工具声明的 subject_field（覆盖 AI 传值）。
    # 工具内部按自身语义用该值查对应列（C 端 user_id / B 端 tenant_id / 工单 bu_id）。
    safe_params = dict(params)
    safe_params.pop("unmask", None)
    if tool.requires_subject_id:
        inject_value: str | None = subject_id
        # C 端会话身份是 gateway 的 userCode（字母前缀，如 U43825474），业务库按数字 user_id
        # 隔离，需翻译；若 subject_id 已是纯数字（即已是 user_id）则直接用，不打业务库。
        if user_type == USER_TYPE_C and not subject_id.isdigit():
            # C 端：userCode → 数字 user_id；映射不到则明确报错，不静默查空误导用户
            inject_value = await _c_user_id(subject_id)
            if inject_value is None:
                await log_tool_call(
                    conversation_id, tool_name, params, 0, 0, True, "c user_code unmapped",
                    result_count=0, is_empty=True, subject_id=subject_id, user_type=user_type,
                )
                metrics.tool_calls.labels(tool=tool_name, ok="false").inc()
                return {
                    "ok": False,
                    "error": f"无法将当前用户身份({subject_id})映射到业务用户ID，请转人工核实身份",
                }
        safe_params[tool.subject_field] = inject_value
    # 个别工具需要 conversation_id（如 create_ticket）；统一注入
    if tool_name in NEEDS_CONVERSATION_ID:
        safe_params["conversation_id"] = conversation_id
    # create_ticket 需按 user_type 决定填 user_id(C) 还是 bu_id(B)；注入会话身份类型
    if tool_name in NEEDS_USER_TYPE:
        safe_params["user_type"] = user_type
    # spec §13.3：engineer 代查时解锁部分脱敏；仅对声明支持的工具注入
    if tool.supports_unmask and unmask:
        safe_params["unmask"] = True

    started = time.perf_counter()
    try:
        data = await tool.handler(**safe_params)
        duration_ms = int((time.perf_counter() - started) * 1000)
        payload = json.dumps(data, ensure_ascii=False)
        rc = _result_count(data)
        await log_tool_call(
            conversation_id,
            tool_name,
            safe_params,
            len(payload.encode("utf-8")),
            duration_ms,
            False,
            None,
            result_count=rc,
            is_empty=(rc == 0),
            subject_id=subject_id,
            user_type=user_type,
        )
        _observe(tool_name, duration_ms, ok=True)
        return {"ok": True, "data": data}
    except ValueError as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_tool_call(
            conversation_id, tool_name, safe_params, 0, duration_ms, True, str(e),
            result_count=0, is_empty=True, subject_id=subject_id, user_type=user_type,
        )
        _observe(tool_name, duration_ms, ok=False)
        return {"ok": False, "error": f"invalid args: {e}"}
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_tool_call(
            conversation_id, tool_name, safe_params, 0, duration_ms, True, f"internal: {e}",
            result_count=0, is_empty=True, subject_id=subject_id, user_type=user_type,
        )
        _observe(tool_name, duration_ms, ok=False)
        return {"ok": False, "error": "internal error"}


def _observe(tool_name: str, duration_ms: int, ok: bool) -> None:
    metrics.tool_calls.labels(tool=tool_name, ok=str(ok).lower()).inc()
    metrics.tool_duration.labels(tool=tool_name).observe(duration_ms / 1000)
