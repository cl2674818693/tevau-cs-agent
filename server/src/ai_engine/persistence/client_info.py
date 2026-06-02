"""会话客户端信息 DAO：H5 上报 platform/app_version/user_agent，admin 详情卡读取。

单会话单行（conversation_id 主键），APP 升级 / 切端 / 重新上报走 upsert。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def upsert_client_info(
    conversation_id: int,
    platform: str | None,
    app_version: str | None,
    user_agent: str | None,
) -> None:
    """写入或覆盖一条客户端信息。SQLite/Postgres 通用：先 DELETE 再 INSERT，
    避免方言差异（PG 用 ON CONFLICT，SQLite 用 INSERT OR REPLACE）。"""
    await db.execute(
        "DELETE FROM conversation_client_info WHERE conversation_id=:id",
        {"id": conversation_id},
    )
    await db.execute(
        "INSERT INTO conversation_client_info"
        "(conversation_id, platform, app_version, user_agent, updated_at) "
        "VALUES (:id, :p, :v, :ua, :at)",
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
