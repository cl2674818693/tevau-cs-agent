import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ai_engine.agent.tools.base import Tool, register

# B 端 Open API 错误码知识库（来源：TevauNexus-Service 后端常量类，见 JSON _meta）
_DOC = Path(__file__).resolve().parents[2] / "knowledge" / "nexus_error_codes.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(_DOC.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data.get("codes", {})


def _entry(code: str, v: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "message": v.get("cn")}
    if v.get("en"):
        out["message_en"] = v["en"]
    if v.get("reason"):
        out["reason"] = v["reason"]
    if v.get("reap"):
        out["reap_code"] = v["reap"]  # 卡组织(Reap)原始拒付码
    return out


async def run(
    code: str | None = None, keyword: str | None = None, locale: str = "zh"  # noqa: ARG001
) -> dict[str, Any]:
    """按错误码 code 查含义/原因，或按关键词搜消息。locale 保留兼容签名（KB 已下线）。"""
    codes = _load()
    if not codes:
        return {"hits": [], "note": "错误码知识库未加载"}
    if code:
        # 从输入里抠出数字串（用户常把 code 嵌在句子/JSON 里）
        digits = re.findall(r"\d{3,8}", str(code))
        for d in digits:
            if d in codes:
                return {"hits": [_entry(d, codes[d])]}
        # 没精确命中时，回退把整串当 key 试一次
        if str(code) in codes:
            return {"hits": [_entry(str(code), codes[str(code)])]}
        return {"hits": [], "note": f"未收录该错误码：{code}"}
    if keyword:
        kw = keyword.lower()
        hits = [
            _entry(c, v)
            for c, v in codes.items()
            if kw in (v.get("cn") or "").lower() or kw in (v.get("en") or "").lower()
        ]
        return {"hits": hits[:10], "count": len(hits)}
    return {"hits": [], "note": "需提供 code 或 keyword"}


register(
    Tool(
        name="lookup_error_code",
        description=(
            "查询 Tevau B 端 Open API 错误码（code）的含义与处理建议。"
            "覆盖网关签名、卡申请/激活/绑定、KYC、交易授权/拒付(含 Reap 原始码)、查询、Webhook。"
            "用户报'接口返回 2020003 / 10010003 / 2040002 是什么意思''为什么报这个错'时用；"
            "也可用 keyword 按中文/英文关键词搜（如 '库存''签名''PIN'）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "错误码，如 2020003；可直接粘含 code 的报文",
                },
                "keyword": {"type": "string", "description": "可选，按消息关键词搜索"},
            },
            "required": [],
        },
        handler=run,
    )
)
