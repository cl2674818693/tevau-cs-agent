from typing import Any

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


async def run(
    repo: str, path: str, start_line: int | None = None, end_line: int | None = None
) -> dict[str, Any]:
    if repo not in ALLOWED_REPOS:
        raise ValueError(f"repo must be one of {sorted(ALLOWED_REPOS)}")
    _validate_path(path)

    try:
        raw = await raw_file(REPO_MAP[repo], DEFAULT_REV, path)
    except FileNotFoundError:
        raise ValueError("file not found") from None

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


register(
    Tool(
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
    )
)
