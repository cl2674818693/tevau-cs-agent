"""会话客户端信息 DAO：H5 上报 platform/app_version/user_agent，admin 详情卡读取。

单会话单行（conversation_id 主键），APP 升级 / 切端 / 重新上报走 upsert。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

# 单条原子 upsert：避免 DELETE+INSERT 在并发（React StrictMode 双 mount / 重连重发）下撞主键报 500。
# 方言分发：SQLite 用 ON CONFLICT(col) DO UPDATE SET col=excluded.col；MySQL 用 ON DUPLICATE KEY UPDATE col=VALUES(col)
_UPSERT_SQL_SQLITE = (
    "INSERT INTO conversation_client_info"
    "(conversation_id, platform, app_version, user_agent, updated_at) "
    "VALUES (:id, :p, :v, :ua, :at) "
    "ON CONFLICT (conversation_id) DO UPDATE SET "
    "platform = excluded.platform, "
    "app_version = excluded.app_version, "
    "user_agent = excluded.user_agent, "
    "updated_at = excluded.updated_at"
)
_UPSERT_SQL_MYSQL = (
    "INSERT INTO conversation_client_info"
    "(conversation_id, platform, app_version, user_agent, updated_at) "
    "VALUES (:id, :p, :v, :ua, :at) "
    "ON DUPLICATE KEY UPDATE "
    "platform = VALUES(platform), "
    "app_version = VALUES(app_version), "
    "user_agent = VALUES(user_agent), "
    "updated_at = VALUES(updated_at)"
)


async def upsert_client_info(
    conversation_id: int,
    platform: str | None,
    app_version: str | None,
    user_agent: str | None,
) -> None:
    sql = _UPSERT_SQL_MYSQL if db.dialect_name() == "mysql" else _UPSERT_SQL_SQLITE
    await db.execute(
        sql,
        {
            "id": conversation_id,
            "p": platform,
            "v": app_version,
            "ua": user_agent,
            "at": now_str(),
        },
    )


async def get_client_info(conversation_id: int) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT platform, app_version, user_agent, updated_at "
        "FROM conversation_client_info WHERE conversation_id=:id",
        {"id": conversation_id},
    )
