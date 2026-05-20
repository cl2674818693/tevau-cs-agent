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


def update_rollout(rollout: dict[str, int]) -> None:
    """改灰度比例并写回 registry.yaml + 热加载。键必须是已声明版本，值之和 ≤ 100。"""
    cfg = load_registry()
    known = set(cfg["versions"].keys())
    unknown = set(rollout) - known
    if unknown:
        raise ValueError(f"unknown versions: {sorted(unknown)}")
    if any(v < 0 for v in rollout.values()) or sum(rollout.values()) > 100:
        raise ValueError("rollout percentages must be >=0 and sum <= 100")
    cfg = dict(cfg)
    cfg["rollout"] = {k: int(v) for k, v in rollout.items()}
    _registry_path().write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    reload_registry()
