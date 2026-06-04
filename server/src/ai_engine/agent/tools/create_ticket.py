"""create_ticket：AI 无法当场解决时建工单 + 推事项中心。

事项中心契约（事项中心团队提供，see docs/event-center-onboarding.md）：
- POST {event_center_url}/api/tasks
- Authorization: Bearer {event_center_token}
- body 字段：event_id / action_type / source_module=ticket / event_type=new_ticket /
  context / priority(1-4) / entities[] / source_ref / callback_url
- 响应 2xx 表示接收，body 含 task_id / assignee 等（cs-engine 仅记录，不依赖）。
"""

import secrets
from datetime import UTC, datetime
from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.event_center_client import create_task
from ai_engine.integrations.lark_webhook import send as _notify_lark
from ai_engine.observability import metrics
from ai_engine.persistence.tickets import append_ticket_event as _append_event
from ai_engine.persistence.tickets import create_ticket as _save_local
from ai_engine.persistence.tickets import find_open_ticket_for_subject as _find_open

VALID_CATEGORIES = {"bug", "事务", "CQ", "无信息", "人工介入"}
VALID_SEVERITIES = {"p0", "p1", "p2", "p3"}

# category → 事项中心 action_type 映射。
# task=需要人处理；notify=仅记录无需操作。"无信息"=AI 收集到信息不够无需推动客服，
# 其他四类都需要人跟进。
_CATEGORY_TO_ACTION_TYPE: dict[str, str] = {
    "bug": "task",
    "事务": "task",
    "人工介入": "task",
    "CQ": "task",
    "无信息": "notify",
}

# severity p0/p1/p2/p3 → 事项中心 priority 1-4。
# cs-engine：p0 最高；事项中心：4 最高 → 反向数字映射。
_SEVERITY_TO_PRIORITY: dict[str, int] = {
    "p0": 4,   # 紧急
    "p1": 3,   # 高
    "p2": 2,   # 普通（事项中心默认值）
    "p3": 1,   # 低
}


def _new_external_id() -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"AI-{ts}-{secrets.token_hex(3)}"


# 已抽到 entities 数组的 evidence 键，不再重复塞进 context 文本
_ENTITY_KEYS = {
    "card_id", "cardId", "card_number", "cardNumber",
    "transaction_id", "txn_id", "order_id", "orderId", "trade_no", "tradeNo",
}


def _format_code_ref(ref: Any) -> str:
    """code_evidence 元素的开发者可读格式化。

    AI 可能写成纯字符串（"Foo.java:42 — note"）也可能写成 dict
    （{'file': 'Foo.java', 'line': 42, 'note': '...'} 或 {'file':..., 'lines': '115-123'}）。
    统一输出 "{file}:{line} — {note}" 形式，开发者直接 IDE 跳转；非预期形态
    fallback 到 repr，至少不丢信息。
    """
    if isinstance(ref, str):
        return ref
    if isinstance(ref, dict):
        file = ref.get("file") or ref.get("path") or ""
        line = ref.get("line") or ref.get("lines") or ""
        note = ref.get("note") or ref.get("desc") or ref.get("comment") or ""
        head = f"{file}:{line}" if file and line else (file or "")
        if head and note:
            return f"{head} — {note}"
        return head or note or str(ref)
    return str(ref)


def _build_rich_context(summary: str, evidence: dict[str, Any]) -> str:
    """合并 summary + evidence 富信息为完整 context，让事项中心拿到的开发人员能定位代码。

    现状（修复前）：只推 summary 一句话，开发人员拿到"3DS Webhook txnCurrency 为 null"
    后无任何定位线索（文件行号 / 复现 payload / 关键 ID 全在 evidence 里被丢弃）。

    修复后 context 结构：
      <summary>

      —— 关键证据 ——
      代码定位:
        · Notify3dsDTO.java:29
        · UpstreamAuthNotificationReceivedLogic.java:158
      复现 payload: {...}
      auth_id: xxx
      涉及接口: 8.4 3DS Webhook
      其他: merchant=Shopee, txnAmount=6900, ...

    事项中心 AI 仍能据此生成 title（基于首段 summary），开发人员翻 context 全文能直接
    跳到代码。entities 数组里已抽出的 card_id/transaction_id 不重复展开。
    """
    if not evidence:
        return summary
    parts: list[str] = [summary, "", "—— 关键证据 ——"]

    code_refs = evidence.get("code_evidence") or evidence.get("code_refs")
    if code_refs:
        parts.append("代码定位:")
        items = code_refs if isinstance(code_refs, list) else [code_refs]
        for ref in items:
            parts.append(f"  · {_format_code_ref(ref)}")

    for key, label in [
        ("repro_payload", "复现 payload"),
        ("auth_id", "auth_id"),
        ("request_id", "request_id"),
        ("order_no", "order_no"),
        ("api_ref", "涉及接口"),
        ("symptom", "现象"),
        ("error_code", "错误码"),
        ("error_message", "错误信息"),
    ]:
        val = evidence.get(key)
        if val:
            parts.append(f"{label}: {val}")

    # 兜底：其余字段（除已展开/已进 entities 的）打成 "key=value" 列表
    consumed = _ENTITY_KEYS | {
        "code_evidence", "code_refs", "repro_payload", "auth_id", "request_id",
        "order_no", "api_ref", "symptom", "error_code", "error_message",
    }
    extras = [f"{k}={v}" for k, v in evidence.items() if k not in consumed and v is not None]
    if extras:
        parts.append("其他: " + ", ".join(extras))

    return "\n".join(parts)


def _extract_entities(
    user_type: str, subject_id: str, evidence: dict[str, Any]
) -> list[dict[str, str]]:
    """把 evidence dict 抽成事项中心要求的 entities 数组 [{type, id, name?}]。

    约定提取规则（按事项中心 entity type 命名）：
    - subject_id 永远作为第一条：C 端 type=customer / B 端 type=partner
    - evidence 里常见字段名（card_id / cardId / cardNumber → card；
      transaction_id / orderId / tradeNo → transaction；
      user_id / userCode → 跳过避免与 subject 重复）

    未知字段忽略而非抛错——evidence 是 AI 任意写的，提取容错。
    """
    entities: list[dict[str, str]] = []
    # 1) 永远带的主体身份
    if subject_id:
        entities.append({
            "type": "customer" if user_type == "c" else "partner",
            "id": str(subject_id),
        })
    # 2) 卡片
    for key in ("card_id", "cardId", "card_number", "cardNumber"):
        val = evidence.get(key)
        if val:
            entities.append({"type": "card", "id": str(val)})
            break  # 同一 ticket 只挂一张卡，多卡场景在 evidence 文本里描述
    # 3) 交易/订单
    for key in ("transaction_id", "txn_id", "order_id", "orderId", "trade_no", "tradeNo"):
        val = evidence.get(key)
        if val:
            entities.append({"type": "transaction", "id": str(val)})
            break
    return entities


async def run(
    subject_id: str,
    user_type: str,
    conversation_id: int,
    category: str,
    summary: str,
    severity: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}")
    if user_type not in ("c", "b"):
        raise ValueError("user_type must be 'c' or 'b'")

    # spec §11 工单风暴对策：同 subject 24h 内已有未关闭工单 → 追加证据，不新建。
    existing = await _find_open(subject_id, user_type)
    if existing:
        await _append_event(
            existing,
            event="evidence_added",
            actor="ai",
            comment=summary,
            raw={"category": category, "severity": severity, "evidence": evidence},
        )
        ret_existing: dict[str, Any] = {
            "external_ticket_id": existing, "appended_to_existing": True
        }
        # 复用路径也要补 off_hours/next_shift_start，否则 AI 走"追加现有工单"分支时
        # 看不到班外信息，会回到默认"客服会尽快联系"话术，多语言用户得不到正确说明。
        if category == "人工介入" and conversation_id:
            off_hours_info = await _ensure_human_pending(conversation_id)
            ret_existing.update(off_hours_info)
        return ret_existing

    ext_id = _new_external_id()
    # 本地审计 payload 仍保留 cs-engine 内部 schema（external_ticket_id/category/severity/evidence），
    # 给 admin 后台展示用；推事项中心的是另一份按对方契约重塑的 payload。
    local_payload: dict[str, object] = {
        "source": "ai_engine",
        "external_ticket_id": ext_id,
        "user_type": user_type,
        ("user_id" if user_type == "c" else "bu_id"): subject_id,
        "category": category,
        "summary": summary,
        "severity": severity,
        "evidence": evidence,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # 1. 本地落库（兜底，确保引擎自有记录；事项中心推失败也能在 admin 看到）
    await _save_local(external_id=ext_id, conversation_id=conversation_id, payload=local_payload)
    metrics.tickets_created.labels(category=category, severity=severity, user_type=user_type).inc()

    # 2. 按事项中心契约推送（共享 client：event_center_client.create_task）
    pushed = await create_task(
        event_id=ext_id,
        context=_build_rich_context(summary, evidence),  # 合并 evidence，开发者能定位代码
        priority=_SEVERITY_TO_PRIORITY.get(severity, 2),
        action_type=_CATEGORY_TO_ACTION_TYPE.get(category, "task"),
        entities=_extract_entities(user_type, subject_id, evidence),
        source_ref=ext_id,
    )

    # 3. 如失败，触发 Lark 兜底
    if not pushed:
        text = f"[兜底] 工单 {ext_id} 推事项中心失败：{category} / {severity} / {summary[:80]}"
        await _notify_lark({"text": text})

    # 4. 人工介入类工单：同步切 mode=human_pending，与 /request-human 端点行为对齐。
    #    否则会话仍是 mode='ai'，admin "会话" 列表筛 mode!=ai 看不到这个待接管会话。
    #    已经在 human_takeover/human_pending 的不重切（避免 mode_change 抖动 + 重复 SSE）。
    #    返回 off_hours 信息让 AI 据此调整措辞（"已为您接通"  vs  "客服班外，已留工单"）。
    ret: dict[str, Any] = {"external_ticket_id": ext_id, "pushed_to_event_center": pushed}
    if category == "人工介入" and conversation_id:
        off_hours_info = await _ensure_human_pending(conversation_id)
        ret.update(off_hours_info)

    return ret


async def _ensure_human_pending(conversation_id: int) -> dict[str, Any]:
    """当前 mode=ai 时切到 human_pending 并广播 mode_change，然后触发派单。
    返回 {no_one_online: bool} 让上层 AI 据此措辞（True 则提示"客服当前不在线"）。"""
    info: dict[str, Any] = {"no_one_online": False}
    try:
        from ai_engine.api.staff_conversations import publish_conversation_event
        from ai_engine.persistence import conversations as conv_dao
        from ai_engine.persistence.staff_metrics import refresh_human_pending
        from ai_engine.services.dispatch import dispatch_to_human_pending

        mode, _ = await conv_dao.get_mode(conversation_id)
        if mode == "ai":
            await conv_dao.set_mode(conversation_id, "human_pending")
            await refresh_human_pending()
            publish_conversation_event(
                conversation_id, {"type": "mode_change", "to": "human_pending"}
            )

        result = await dispatch_to_human_pending(conversation_id)
        info["no_one_online"] = bool(result.get("no_one_online"))
    except Exception:
        # 派单失败不阻断工单创建——工单已经入库，事项中心已推送
        pass
    return info


register(
    Tool(
        name="create_ticket",
        description=(
            "当 AI 无法当场解决时，创建工单并推送到事项中心。"
            "category ∈ {bug,事务,CQ,无信息,人工介入}，severity ∈ {p0..p3}。"
            "**不指定分派人**（分派由事项中心按规则决定，见 spec §7.3）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": sorted(VALID_CATEGORIES)},
                "summary": {"type": "string", "minLength": 5, "maxLength": 500},
                "severity": {"type": "string", "enum": sorted(VALID_SEVERITIES)},
                "evidence": {"type": "object"},
            },
            "required": ["category", "summary", "severity", "evidence"],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="subject_id",
    )
)
