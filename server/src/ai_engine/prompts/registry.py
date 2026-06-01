"""Prompt 版本注册表 + 按 subject_id 哈希分桶灰度（spec §8）。"""

import hashlib
from pathlib import Path
from typing import Any

import yaml

from ai_engine.config import settings

_cache: dict[str, Any] | None = None


def _registry_path() -> Path:
    return Path(settings.prompts_dir) / "registry.yaml"


def load_registry() -> dict[str, Any]:
    global _cache
    if _cache is None:
        _cache = yaml.safe_load(_registry_path().read_text(encoding="utf-8"))
    return _cache


def reload_registry() -> None:
    """改了 registry.yaml（如灰度比例）后调用，使其重新生效。"""
    global _cache
    _cache = None
    # 同步清空 loader 的 prompt 内容缓存（延迟 import 避免与 loader 循环依赖）
    from ai_engine.prompts import loader

    loader.clear_cache()


def default_version() -> str:
    return str(load_registry()["default"])


def list_versions() -> list[str]:
    return list(load_registry()["versions"].keys())


def pick_version(subject_id: str) -> str:
    """按 subject_id md5 哈希分桶（0-99）选版本；rollout 余量回落 default。"""
    cfg = load_registry()
    digest = hashlib.md5(subject_id.encode(), usedforsecurity=False).hexdigest()
    bucket = int(digest, 16) % 100
    cumulative = 0
    for version, pct in cfg.get("rollout", {}).items():
        cumulative += int(pct)
        if bucket < cumulative:
            return str(version)
    return default_version()


def file_path(version: str, key: str) -> Path:
    rel = str(load_registry()["versions"][version]["files"][key])
    return Path(settings.prompts_dir) / rel


def model_for(version: str) -> str | None:
    model = load_registry()["versions"][version].get("model")
    return str(model) if model else None


def get_rollout() -> dict[str, int]:
    return {k: int(v) for k, v in load_registry().get("rollout", {}).items()}


def validate_version_files(version: str) -> None:
    """验证 version 声明的所有 prompt key 文件都存在，否则 raise ValueError。"""
    cfg = load_registry()
    files: dict[str, str] = cfg["versions"][version].get("files", {})
    missing = [
        key for key, rel in files.items()
        if not (Path(settings.prompts_dir) / rel).exists()
    ]
    if missing:
        raise ValueError(
            f"version {version!r} missing prompt files for keys: {sorted(missing)}"
        )


