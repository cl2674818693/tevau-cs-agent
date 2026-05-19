# Task 4: search_code + read_file 工具（Sourcegraph GraphQL）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**前置依赖**：Sourcegraph 自部署容器必须先跑起来（见 Task 14 docker-compose）。本任务的实现走 Sourcegraph，本机不再装 ripgrep；测试用 `respx` mock HTTP，不依赖真实 Sourcegraph。

**Files:**
- Create: `server/src/ai_engine/agent/__init__.py`
- Create: `server/src/ai_engine/agent/tools/__init__.py`
- Create: `server/src/ai_engine/agent/tools/base.py`
- Create: `server/src/ai_engine/integrations/sourcegraph.py`
- Create: `server/src/ai_engine/agent/tools/search_code.py`
- Create: `server/src/ai_engine/agent/tools/read_file.py`
- Create: `server/tests/test_search_code.py`
- Create: `server/tests/test_read_file.py`

- [ ] **Step 1: 写 `server/src/ai_engine/agent/__init__.py` 与 `server/src/ai_engine/agent/tools/__init__.py`（空文件）**

- [ ] **Step 2: 写 `server/src/ai_engine/agent/tools/base.py`**

```python
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ALLOWED_REPOS = {"app_frontend", "app_backend", "openapi_backend"}

# 仓库别名 → Sourcegraph 上的 repo 标识（gitlab.tevaupay.com/<group>/<project>）
REPO_MAP = {
    "app_frontend": "gitlab.tevaupay.com/tevaupay-views/app/TevauPay-Flutter",
    "app_backend": "gitlab.tevaupay.com/tevaupay/business-services/TevauPay-Service",
    "openapi_backend": "gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service",
}


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Awaitable[Any]]
    requires_subject_id: bool = False  # True 则 router 会强制注入 subject_id


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    REGISTRY[tool.name] = tool


def get(name: str) -> Tool | None:
    return REGISTRY.get(name)


def all_definitions() -> list[dict]:
    return [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in REGISTRY.values()]
```

- [ ] **Step 3: 写 `server/src/ai_engine/integrations/sourcegraph.py`**（统一 client）

```python
import httpx
from ai_engine.config import settings


_SEARCH_QUERY = """
query Search($query: String!) {
  search(query: $query, version: V3) {
    results {
      results {
        __typename
        ... on FileMatch {
          repository { name }
          file { path }
          lineMatches { lineNumber preview }
        }
      }
    }
  }
}
"""


async def graphql_search(sg_query: str) -> dict:
    """调 Sourcegraph GraphQL search。返回原始 data 字段。"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.sourcegraph_url}/.api/graphql",
            json={"query": _SEARCH_QUERY, "variables": {"query": sg_query}},
            headers={"Authorization": f"token {settings.sourcegraph_token}"},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"sourcegraph search failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


async def raw_file(repo_sg: str, rev: str, path: str) -> bytes:
    """走 Sourcegraph raw API 读文件内容。"""
    url = f"{settings.sourcegraph_url}/{repo_sg}@{rev}/-/raw/{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            url, headers={"Authorization": f"token {settings.sourcegraph_token}"},
        )
    if resp.status_code == 404:
        raise FileNotFoundError(f"{repo_sg}@{rev}:{path}")
    if resp.status_code != 200:
        raise RuntimeError(f"sourcegraph raw failed: {resp.status_code}")
    return resp.content
```

- [ ] **Step 4: 写 `server/tests/test_search_code.py`（用 respx mock）**

```python
import pytest
import respx
from httpx import Response


@pytest.fixture(autouse=True)
def sg_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SOURCEGRAPH_URL", "http://sg")
    monkeypatch.setenv("SOURCEGRAPH_TOKEN", "tok")
    from ai_engine.config import settings
    settings.reload()


@respx.mock
async def test_search_code_finds_handler():
    respx.post("http://sg/.api/graphql").mock(return_value=Response(200, json={
        "data": {"search": {"results": {"results": [
            {"__typename": "FileMatch",
             "repository": {"name": "gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service"},
             "file": {"path": "handlers/card_bind.go"},
             "lineMatches": [{"lineNumber": 119, "preview": "func HandleCardBind("}]}
        ]}}}
    }))
    from ai_engine.agent.tools.search_code import run
    out = await run(repo="openapi_backend", query="HandleCardBind")
    assert out["hits"]
    assert any("card_bind.go" in h["path"] for h in out["hits"])
    assert out["hits"][0]["line"] == 120  # SG 0-indexed → 我们 1-indexed


async def test_search_code_rejects_unknown_repo():
    from ai_engine.agent.tools.search_code import run
    with pytest.raises(ValueError) as e:
        await run(repo="anything_else", query="x")
    assert "repo" in str(e.value)


async def test_search_code_rejects_long_query():
    from ai_engine.agent.tools.search_code import run
    with pytest.raises(ValueError):
        await run(repo="openapi_backend", query="a" * 1024)


@respx.mock
async def test_search_code_propagates_sg_error():
    respx.post("http://sg/.api/graphql").mock(return_value=Response(500, text="boom"))
    from ai_engine.agent.tools.search_code import run
    with pytest.raises(RuntimeError):
        await run(repo="openapi_backend", query="x")
```

- [ ] **Step 5: 跑确认失败**

```bash
pytest tests/test_search_code.py -v
```
Expected: ImportError / FAIL（工具还没写）

- [ ] **Step 6: 写 `server/src/ai_engine/agent/tools/search_code.py`**

```python
from ai_engine.agent.tools.base import ALLOWED_REPOS, REPO_MAP, Tool, register
from ai_engine.integrations.sourcegraph import graphql_search


MAX_QUERY_LEN = 200
MAX_HITS_DEFAULT = 50
DEFAULT_REV = "test"  # 所有代码仓库的 test 分支


async def run(repo: str, query: str, max_hits: int = MAX_HITS_DEFAULT) -> dict:
    if repo not in ALLOWED_REPOS:
        raise ValueError(f"repo must be one of {sorted(ALLOWED_REPOS)}, got {repo!r}")
    if not query or len(query) > MAX_QUERY_LEN:
        raise ValueError(f"query length must be 1..{MAX_QUERY_LEN}")
    if max_hits < 1 or max_hits > 200:
        raise ValueError("max_hits must be 1..200")

    repo_sg = REPO_MAP[repo]
    # Sourcegraph 查询语法：限定 repo + rev + count
    sg_query = f"repo:^{repo_sg}$ rev:{DEFAULT_REV} count:{max_hits} {query}"
    data = await graphql_search(sg_query)
    hits = []
    for r in (data.get("data") or {}).get("search", {}).get("results", {}).get("results", []) or []:
        if r.get("__typename") != "FileMatch":
            continue
        path = r.get("file", {}).get("path", "")
        for lm in r.get("lineMatches", []) or []:
            hits.append({
                "path": path,
                "line": (lm.get("lineNumber") or 0) + 1,  # SG 0-indexed → 1-indexed
                "preview": (lm.get("preview") or "").rstrip(),
            })
            if len(hits) >= max_hits:
                break
        if len(hits) >= max_hits:
            break
    return {"hits": hits}


register(Tool(
    name="search_code",
    description=("在指定代码仓库的 test 分支上搜索（Sourcegraph 后端）。"
                 "repo ∈ {app_frontend, app_backend, openapi_backend}。"
                 "query 是文本/正则，遵循 Sourcegraph 语法（默认结构匹配）。"),
    input_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "enum": sorted(ALLOWED_REPOS)},
            "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_LEN},
            "max_hits": {"type": "integer", "minimum": 1, "maximum": 200, "default": MAX_HITS_DEFAULT},
        },
        "required": ["repo", "query"],
    },
    handler=run,
))
```

- [ ] **Step 7: 跑 search_code 测试**

```bash
pytest tests/test_search_code.py -v
```
Expected: 4 passed

- [ ] **Step 8: 写 `server/tests/test_read_file.py`**

```python
import pytest
import respx
from httpx import Response


@pytest.fixture(autouse=True)
def sg_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SOURCEGRAPH_URL", "http://sg")
    monkeypatch.setenv("SOURCEGRAPH_TOKEN", "tok")
    from ai_engine.config import settings
    settings.reload()


@respx.mock
async def test_read_file_returns_content():
    respx.get(
        "http://sg/gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service@test/-/raw/handlers/card_bind.go"
    ).mock(return_value=Response(200, text="package handlers\nfunc HandleCardBind() {}\n"))
    from ai_engine.agent.tools.read_file import run
    out = await run(repo="openapi_backend", path="handlers/card_bind.go")
    assert "HandleCardBind" in out["content"]


@respx.mock
async def test_read_file_404_raises():
    respx.get(
        "http://sg/gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service@test/-/raw/nope.go"
    ).mock(return_value=Response(404))
    from ai_engine.agent.tools.read_file import run
    with pytest.raises(ValueError):
        await run(repo="openapi_backend", path="nope.go")


async def test_read_file_rejects_unknown_repo():
    from ai_engine.agent.tools.read_file import run
    with pytest.raises(ValueError):
        await run(repo="not_a_repo", path="x")


async def test_read_file_rejects_path_traversal():
    from ai_engine.agent.tools.read_file import run
    with pytest.raises(ValueError):
        await run(repo="openapi_backend", path="../../etc/passwd")


@respx.mock
async def test_read_file_line_range():
    respx.get(
        "http://sg/gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service@test/-/raw/x.go"
    ).mock(return_value=Response(200, text="L1\nL2\nL3\nL4\nL5\n"))
    from ai_engine.agent.tools.read_file import run
    out = await run(repo="openapi_backend", path="x.go", start_line=2, end_line=3)
    assert out["content"].strip() == "L2\nL3"
```

- [ ] **Step 9: 写 `server/src/ai_engine/agent/tools/read_file.py`**

```python
from ai_engine.agent.tools.base import ALLOWED_REPOS, REPO_MAP, Tool, register
from ai_engine.integrations.sourcegraph import raw_file


MAX_BYTES = 256 * 1024
DEFAULT_REV = "test"


def _validate_path(path: str) -> None:
    """禁止路径越权 / 绝对路径 / 反斜杠。"""
    if not path or len(path) > 512:
        raise ValueError("path length must be 1..512")
    if ".." in path.split("/") or path.startswith("/") or "\\" in path:
        raise ValueError("path must be relative and not contain '..' segments")


async def run(repo: str, path: str, start_line: int | None = None, end_line: int | None = None) -> dict:
    if repo not in ALLOWED_REPOS:
        raise ValueError(f"repo must be one of {sorted(ALLOWED_REPOS)}")
    _validate_path(path)

    try:
        raw = await raw_file(REPO_MAP[repo], DEFAULT_REV, path)
    except FileNotFoundError:
        raise ValueError("file not found")

    truncated = False
    if len(raw) > MAX_BYTES:
        raw = raw[:MAX_BYTES]
        truncated = True
    text = raw.decode("utf-8", errors="replace")
    if start_line or end_line:
        lines = text.splitlines(keepends=True)
        s = (start_line - 1) if start_line else 0
        e = end_line if end_line else len(lines)
        text = "".join(lines[s:e])
    return {"content": text, "truncated": truncated}


register(Tool(
    name="read_file",
    description="读取代码仓库 test 分支上一个文件（可选行号区间）。来源 Sourcegraph raw API。",
    input_schema={
        "type": "object",
        "properties": {
            "repo": {"type": "string", "enum": sorted(ALLOWED_REPOS)},
            "path": {"type": "string", "minLength": 1, "maxLength": 512},
            "start_line": {"type": "integer", "minimum": 1},
            "end_line": {"type": "integer", "minimum": 1},
        },
        "required": ["repo", "path"],
    },
    handler=run,
))
```

- [ ] **Step 10: 跑测试**

```bash
pytest tests/test_read_file.py -v
```
Expected: 5 passed

- [ ] **Step 11: Commit**

```bash
git add server/src/ai_engine/agent server/src/ai_engine/integrations/sourcegraph.py server/tests/test_search_code.py server/tests/test_read_file.py
git commit -m "feat: search_code 与 read_file 工具（Sourcegraph GraphQL + raw API；respx mock 测试）"
```

> **Sourcegraph 联调说明**：单元测试用 respx mock，不需要 Sourcegraph 在跑。但实际联调（Task 13 e2e、手动测试）需要 Sourcegraph 容器在跑、admin token 在 `.env`、3 个仓库已索引（见 Task 14 部署说明）。

---
