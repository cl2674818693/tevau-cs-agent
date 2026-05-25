"""Alembic 环境：从 settings.db_url 读取目标库，把 async 驱动转成 sync URL。

迁移用原生 SQL（op.execute），不依赖 SQLAlchemy ORM 模型，因此 target_metadata=None，
autogenerate 不可用——迁移手写。这样同一套 alembic 既管 SQLite 也管将来的 Postgres。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ai_engine.config import settings

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False：否则进程内跑 alembic 会静默掉所有 ai_engine.* logger
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = None


def _sync_url() -> str:
    """把应用的 async DB URL 转成 alembic 用的 sync URL。"""
    url = settings.db_url
    return url.replace("+aiosqlite", "").replace("+asyncpg", "").replace("+aiomysql", "")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
