import asyncio
from pathlib import Path
from typing import Any

from ai_engine.agent.tools.base import ALLOWED_REPOS, Tool, register
from ai_engine.config import settings
from ai_engine.integrations.redact import mask_vendor_names

MAX_BYTES = 256 * 1024


def _validate_path(path: str) -> None:
    """禁止路径越权 / 绝对路径 / 反斜杠。"""
    if not path or len(path) > 512:
        raise ValueError("path length must be 1..512")
    if ".." in path.split("/") or path.startswith("/") or "\\" in path:
        raise ValueError("path must be relative and not contain '..' segments")


def _read_sync(
    base: str, path: str, start_line: int | None, end_line: int | None
) -> dict[str, Any]:
    if not Path(base).is_dir():
        raise ValueError("代码仓库未配置或路径不存在")
    base_resolved = Path(base).resolve()
    full = (base_resolved / path).resolve()
    # 二次越权防护：解析后必须仍在仓库目录内
    if full != base_resolved and base_resolved not in full.parents:
        raise ValueError("path 越权")
    if not full.is_file():
        raise ValueError("file not found")
    raw = full.read_bytes()
    truncated = len(raw) > MAX_BYTES
    text = raw[:MAX_BYTES].decode("utf-8", errors="replace")
    if start_line or end_line:
        lines = text.splitlines(keepends=True)
        s = (start_line - 1) if start_line else 0
        e = end_line if end_line else len(lines)
        text = "".join(lines[s:e])
    # 防上游供应商品牌名泄漏：AI 看到的源码内容已脱敏，类名结构保留（ReapXxx→UpstreamXxx）
    text = mask_vendor_names(text)
    return {"content": text, "truncated": truncated}


async def run(
    repo: str, path: str, start_line: int | None = None, end_line: int | None = None
) -> dict[str, Any]:
    if repo not in ALLOWED_REPOS:
        raise ValueError(f"repo must be one of {sorted(ALLOWED_REPOS)}")
    _validate_path(path)
    base = settings.code_repo_paths.get(repo)
    if not base:
        raise ValueError(f"代码仓库 {repo} 未配置")
    return await asyncio.to_thread(_read_sync, base, path, start_line, end_line)


register(
    Tool(
        name="read_file",
        description="读取代码仓库里某个文件内容（可选行号区间）。配合 search_code 定位后读上下文。",
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
