"""2026-06-04 migration: drop staff_shifts table + collapse away→offline.

Run: cd server && uv run python scripts/migrate_2026_06_04_drop_shifts.py
"""

import asyncio

from ai_engine.persistence import db


async def main() -> None:
    try:
        await db.execute("DROP TABLE IF EXISTS staff_shifts")
        print("dropped staff_shifts table")
    except Exception as e:
        print(f"drop staff_shifts failed: {e}")

    affected = await db.execute_rowcount(
        "UPDATE staff_presence SET status='offline' WHERE status='away'"
    )
    print(f"collapsed away→offline: {affected} rows")


if __name__ == "__main__":
    asyncio.run(main())
