# Task 7: lookup_api_doc 工具（读 Apifox 导出的 OpenAPI 3.0 JSON）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

`api-docs.tevau.io` 后端是 Apifox 项目，可导出标准 **OpenAPI 3.0 JSON**。本工具读这个 JSON 做检索（不爬 HTML、不维护自定义 JSON 索引）。

**Files:**
- Create: `tests/fixtures/openapi_sample.json`
- Create: `src/ai_engine/agent/tools/lookup_api_doc.py`
- Create: `tests/test_lookup_api_doc.py`

- [ ] **Step 1: 写 `tests/fixtures/openapi_sample.json`**（OpenAPI 3.0 最小样例）

```json
{
  "openapi": "3.0.0",
  "info": { "title": "Tevau Open API", "version": "1.0.0" },
  "paths": {
    "/v2/card/bind": {
      "post": {
        "summary": "绑定卡片",
        "description": "绑定卡片到用户。返回卡片 ID 与状态。",
        "tags": ["卡片", "card"],
        "operationId": "bindCard",
        "responses": { "200": { "description": "ok" }, "500": { "description": "DB_TIMEOUT" } }
      }
    },
    "/v2/card/unlock": {
      "post": {
        "summary": "解锁卡片",
        "description": "解锁被风控锁定的卡片（受限调用）。",
        "tags": ["卡片", "card", "unlock"],
        "operationId": "unlockCard",
        "responses": { "200": { "description": "ok" } }
      }
    }
  }
}
```

- [ ] **Step 2: 写 `tests/test_lookup_api_doc.py`**

```python
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def doc_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    p = tmp_path / "openapi.json"
    p.write_text(Path("tests/fixtures/openapi_sample.json").read_text())
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(p))
    from ai_engine.config import settings
    settings.reload()


async def test_lookup_matches_by_summary(doc_path):
    from ai_engine.agent.tools.lookup_api_doc import run
    out = await run(query="绑定卡片")
    assert out["hits"]
    h = out["hits"][0]
    assert h["path"] == "/v2/card/bind"
    assert h["method"] == "POST"


async def test_lookup_matches_by_tag(doc_path):
    from ai_engine.agent.tools.lookup_api_doc import run
    out = await run(query="unlock")
    assert any(h["path"] == "/v2/card/unlock" for h in out["hits"])


async def test_lookup_returns_empty_for_no_match(doc_path):
    from ai_engine.agent.tools.lookup_api_doc import run
    out = await run(query="不存在的关键词xxx")
    assert out["hits"] == []


async def test_lookup_handles_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAPI_DOC_PATH", str(tmp_path / "nope.json"))
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.agent.tools.lookup_api_doc import run
    out = await run(query="anything")
    assert out["hits"] == []
    assert "openapi doc not loaded" in out.get("note", "").lower()
```

- [ ] **Step 3: 写 `src/ai_engine/agent/tools/lookup_api_doc.py`**

```python
import json
from pathlib import Path
from ai_engine.config import settings
from ai_engine.agent.tools.base import Tool, register


def _load() -> dict | None:
    p = Path(settings.openapi_doc_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_operations(doc: dict):
    """yield (path, method, op_dict)。"""
    for path, methods in (doc.get("paths") or {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() in {"get", "post", "put", "delete", "patch", "head", "options"}:
                yield path, method.upper(), op or {}


def _score(q: str, path: str, method: str, op: dict) -> int:
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


async def run(query: str, limit: int = 5) -> dict:
    if not query or len(query) > 200:
        raise ValueError("query length 1..200")
    doc = _load()
    if doc is None:
        return {"hits": [], "note": "openapi doc not loaded (file missing or invalid)"}

    scored = []
    for path, method, op in _iter_operations(doc):
        s = _score(query, path, method, op)
        if s > 0:
            scored.append((s, {
                "path": path,
                "method": method,
                "summary": op.get("summary") or "",
                "tags": op.get("tags") or [],
                "operationId": op.get("operationId") or "",
            }))
    scored.sort(key=lambda x: -x[0])
    return {"hits": [d for _, d in scored[:limit]]}


register(Tool(
    name="lookup_api_doc",
    description=("检索 Tevau Open API 文档（来源：Apifox 导出的 OpenAPI 3.0 JSON）。"
                 "按 path / summary / description / tags / operationId 加权匹配。"
                 "返回 path、method、summary、tags、operationId。"),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
        "required": ["query"],
    },
    handler=run,
))
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_lookup_api_doc.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/openapi_sample.json src/ai_engine/agent/tools/lookup_api_doc.py tests/test_lookup_api_doc.py
git commit -m "feat: lookup_api_doc 工具（读 Apifox 导出 OpenAPI 3.0 JSON）"
```

> **联调说明**：MVP-1 上线前，用户从 Apifox 项目导出 OpenAPI 3.0 JSON 放到 `repos/api-docs/openapi.json`（或 `.env` 的 `OPENAPI_DOC_PATH` 指向的路径）。MVP-2 可以接 Apifox 的 Open API（如有）做实时同步，否则定期手动导出即可。

---
