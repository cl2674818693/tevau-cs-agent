from typing import Any

from ai_engine.agent.tools.base import ALLOWED_REPOS, REPO_MAP, Tool, register
from ai_engine.integrations.sourcegraph import graphql_search

MAX_QUERY_LEN = 200
MAX_HITS_DEFAULT = 50
DEFAULT_REV = "test"  # 所有代码仓库的 test 分支


async def run(repo: str, query: str, max_hits: int = MAX_HITS_DEFAULT) -> dict[str, Any]:
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
    hits: list[dict[str, Any]] = []
    results = (data.get("data") or {}).get("search", {}).get("results", {}).get("results", []) or []
    for r in results:
        if r.get("__typename") != "FileMatch":
            continue
        path = r.get("file", {}).get("path", "")
        for lm in r.get("lineMatches", []) or []:
            hits.append(
                {
                    "path": path,
                    "line": (lm.get("lineNumber") or 0) + 1,  # SG 0-indexed → 1-indexed
                    "preview": (lm.get("preview") or "").rstrip(),
                }
            )
            if len(hits) >= max_hits:
                break
        if len(hits) >= max_hits:
            break
    return {"hits": hits}


register(
    Tool(
        name="search_code",
        description=(
            "在指定代码仓库的 test 分支上搜索（Sourcegraph 后端）。"
            "repo ∈ {app_frontend, app_backend, openapi_backend}。"
            "query 是文本/正则，遵循 Sourcegraph 语法（默认结构匹配）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "enum": sorted(ALLOWED_REPOS)},
                "query": {"type": "string", "minLength": 1, "maxLength": MAX_QUERY_LEN},
                "max_hits": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": MAX_HITS_DEFAULT,
                },
            },
            "required": ["repo", "query"],
        },
        handler=run,
    )
)
