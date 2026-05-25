"""B: alembic 迁移落地。验证 alembic upgrade head 与 init_db 的 schema 一致（parity）。"""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from ai_engine.persistence.db import _path_from_url
from ai_engine.persistence.schema import metadata


def _alembic_config(db_url: str) -> Config:
    root = Path(__file__).resolve().parent.parent  # server/
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    return cfg


def _tables(path: str) -> set[str]:
    con = sqlite3.connect(path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def _expected_table_names() -> set[str]:
    return set(metadata.tables.keys())


async def test_alembic_upgrade_matches_init_db_schema(temp_db_url):
    # alembic env.py 从 settings.db_url 读 URL；temp_db_url fixture 已设好
    cfg = _alembic_config(temp_db_url)
    command.upgrade(cfg, "head")

    after_alembic = _tables(_path_from_url(temp_db_url))

    # alembic 建出的表 ⊇ SCHEMA（init_db 执行的就是 SCHEMA）声明的全部业务表
    expected = _expected_table_names()
    assert expected, "未能从 SCHEMA 解析出表名"
    assert expected <= after_alembic, f"alembic 缺表: {expected - after_alembic}"
    assert "alembic_version" in after_alembic  # 版本追踪表由框架自建


async def test_alembic_downgrade_drops_app_tables(temp_db_url):
    cfg = _alembic_config(temp_db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    path = _path_from_url(temp_db_url)
    remaining = _tables(path)
    assert _expected_table_names().isdisjoint(remaining), f"downgrade 残留: {remaining}"
