import asyncio
import os
from typing import Any

from ai_engine.agent.tools.base import ALLOWED_REPOS, Tool, register
from ai_engine.config import settings

MAX_QUERY_LEN = 200
MAX_HITS_DEFAULT = 50
_TIMEOUT = 8.0
# 只搜源码，跳过依赖/构建/二进制
_INCLUDE = (
    "*.java", "*.kt", "*.dart", "*.go", "*.py", "*.ts", "*.js", "*.vue",
    "*.sql", "*.xml", "*.yml", "*.yaml", "*.properties", "*.json", "*.md",
)
_EXCLUDE_DIR = (
    ".git", "build", "target", "node_modules", "dist", ".idea", "__pycache__", ".dart_tool",
)


async def run(repo: str, query: str, max_hits: int = MAX_HITS_DEFAULT) -> dict[str, Any]:
    if repo not in ALLOWED_REPOS:
        raise ValueError(f"repo must be one of {sorted(ALLOWED_REPOS)}, got {repo!r}")
    if not query or len(query) > MAX_QUERY_LEN:
        raise ValueError(f"query length must be 1..{MAX_QUERY_LEN}")
    if max_hits < 1 or max_hits > 200:
        raise ValueError("max_hits must be 1..200")

    base = settings.code_repo_paths.get(repo)
    if not base or not os.path.isdir(base):  # noqa: ASYNC240  仅轻量目录存在性检查
        return {"hits": [], "note": f"代码仓库 {repo} 未配置或路径不存在"}

    # grep 固定字符串（-F）+ 参数传递（不走 shell）防注入；-I 跳二进制；-rn 递归带行号
    args = ["grep", "-rnI", "-F", "-e", query]
    for inc in _INCLUDE:
        args += ["--include", inc]
    for ex in _EXCLUDE_DIR:
        args += ["--exclude-dir", ex]
    args.append(base)

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT)
    except TimeoutError:
        proc.kill()
        return {"hits": [], "note": "搜索超时，请用更具体的关键词"}

    return {"hits": _parse_grep(out, base, max_hits)}


def _parse_grep(out: bytes, base: str, max_hits: int) -> list[dict[str, Any]]:
    prefix = base.rstrip("/") + "/"
    hits: list[dict[str, Any]] = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, lineno, content = parts
        hits.append(
            {
                "path": path[len(prefix):] if path.startswith(prefix) else path,
                "line": int(lineno) if lineno.isdigit() else 0,
                "preview": content.strip()[:300],
            }
        )
        if len(hits) >= max_hits:
            break
    return hits


register(
    Tool(
        name="search_code",
        description=(
            "在指定代码仓库里按关键词搜索代码（本地代码，固定字符串匹配，非正则）。"
            "repo ∈ {app_frontend(Flutter APP), app_backend(C端APP后端), "
            "admin_backend(管理后台), openapi_backend(B端OpenAPI)}。"
            "query 用具体的函数名/类名/错误码/接口路径，不超过 200 字符。"
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
