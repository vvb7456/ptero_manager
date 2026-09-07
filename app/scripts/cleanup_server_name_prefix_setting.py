"""One-off cleanup: drop the obsolete ``SERVER_NAME_PREFIX`` runtime setting.

The ``SERVER_NAME_PREFIX`` spec was removed from ``runtime_settings.SETTINGS_SPECS``
(server names are now always auto-filled as ``username-<random 6-char suffix>``),
so the row left in ``manager_system_settings`` is dead data. This script deletes
it. Safe to re-run (no-op when the row is absent).

Usage:
    venv/bin/python -m app.scripts.cleanup_server_name_prefix_setting
"""
from __future__ import annotations

import asyncio

from sqlalchemy import delete

from app.core.settings_store import get_settings_store
from app.db.models.manager import SystemSetting
from app.db.session import get_session_factory

KEY = "SERVER_NAME_PREFIX"


async def main() -> None:
    Session = get_session_factory()
    async with Session() as db:
        result = await db.execute(delete(SystemSetting).where(SystemSetting.key == KEY))
        await db.commit()
        get_settings_store().invalidate(KEY)
        print(f"deleted {result.rowcount} row(s) for key={KEY!r}")


if __name__ == "__main__":
    asyncio.run(main())
