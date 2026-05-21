import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.config import settings

_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _doc_files() -> list[Path]:
    """优先用 openapi_docs_dir 目录下所有 *.json（多份独立文档）；
    目录不存在/无 json 时回退到单文件 openapi_doc_path。"""
    d = Path(settings.openapi_docs_dir)
    if d.is_dir():
        files = sorted(d.glob("*.json"))
        if files:
            return files
    single = Path(settings.openapi_doc_path)
    return [single] if single.exists() else []


def _source_of(p: Path) -> str:
    """来源标记取文件名第一段：pay.openapi.json -> pay, nexus.json -> nexus。"""
    return p.name.split(".")[0]


def _load_one(p: Path) -> dict[str, Any] | None:
    try:
        data: Any = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_docs() -> list[tuple[str, dict[str, Any]]]:
    """yield (source, doc)。坏文件跳过。"""
    docs: list[tuple[str, dict[str, Any]]] = []
    for f in _doc_files():
        doc = _load_one(f)
        if doc is not None:
            docs.append((_source_of(f), doc))
    return docs


def _iter_operations(doc: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """yield (path, method, op_dict)。"""
    for path, methods in (doc.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() in _HTTP_METHODS:
                yield path, method.upper(), op or {}


def _score(q: str, path: str, method: str, op: dict[str, Any]) -> int:
    score = 0
    q_low = q.lower()
    if q_low in path.lower():
        score += 4
    summary = (op.get("summary") or "").lower()
    description = (op.get("description") or "").lower()
    if q_low in summary:
        score += 3
    if q_low in description:
        score += 2
    for tag in op.get("tags") or []:
        if q_low in tag.lower() or tag.lower() in q_low:
            score += 1
    op_id = (op.get("operationId") or "").lower()
    if q_low in op_id:
        score += 2
    return score


async def run(query: str, limit: int = 5) -> dict[str, Any]:
    if not query or len(query) > 200:
        raise ValueError("query length 1..200")
    docs = _load_docs()
    if not docs:
        return {"hits": [], "note": "openapi doc not loaded (file missing or invalid)"}

    scored: list[tuple[int, dict[str, Any]]] = []
    for source, doc in docs:
        for path, method, op in _iter_operations(doc):
            s = _score(query, path, method, op)
            if s > 0:
                scored.append(
                    (
                        s,
                        {
                            "source": source,
                            "path": path,
                            "method": method,
                            "summary": op.get("summary") or "",
                            "tags": op.get("tags") or [],
                            "operationId": op.get("operationId") or "",
                        },
                    )
                )
    scored.sort(key=lambda x: -x[0])
    return {"hits": [d for _, d in scored[:limit]]}


register(
    Tool(
        name="lookup_api_doc",
        description=(
            "检索 Tevau Open API 文档（来源：Apifox 导出的 OpenAPI 3.0 JSON，C 端/B 端各一份）。"
            "按 path / summary / description / tags / operationId 加权匹配。"
            "返回 source（pay=C端APP / nexus=B端OpenAPI）、"
            "path、method、summary、tags、operationId。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 200},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["query"],
        },
        handler=run,
    )
)
