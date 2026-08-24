import os
import time

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "letterboxd.db")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS followed_users (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                letterboxd_username TEXT    NOT NULL,
                guild_id            INTEGER NOT NULL,
                channel_id          INTEGER NOT NULL,
                added_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(letterboxd_username, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen_entries (
                entry_guid TEXT PRIMARY KEY,
                seen_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await _migrate_followed_users(db)
        await db.commit()


async def _migrate_followed_users(db: aiosqlite.Connection) -> None:
    """Add avatar cache columns to pre-existing databases."""
    cursor = await db.execute("PRAGMA table_info(followed_users)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "avatar_url" not in columns:
        await db.execute("ALTER TABLE followed_users ADD COLUMN avatar_url TEXT")
    if "avatar_fetched_at" not in columns:
        await db.execute(
            "ALTER TABLE followed_users ADD COLUMN avatar_fetched_at INTEGER"
        )


async def add_followed_user(
    username: str, guild_id: int, channel_id: int
) -> bool:
    """Returns True if added, False if already followed in this guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO followed_users (letterboxd_username, guild_id, channel_id)
                   VALUES (?, ?, ?)""",
                (username.lower(), guild_id, channel_id),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_followed_user(username: str, guild_id: int) -> bool:
    """Returns True if removed, False if the user wasn't followed."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM followed_users WHERE letterboxd_username = ? AND guild_id = ?",
            (username.lower(), guild_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_followed_users(guild_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM followed_users WHERE guild_id = ? ORDER BY added_at",
            (guild_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def get_all_followed_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM followed_users")
        return [dict(row) for row in await cursor.fetchall()]


async def get_avatar(username: str) -> dict:
    """
    Return the last-known avatar for a username across all guilds:
    {"url": Optional[str], "fetched_at": Optional[int]} (epoch seconds).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT avatar_url, avatar_fetched_at FROM followed_users
               WHERE letterboxd_username = ? AND avatar_url IS NOT NULL
               ORDER BY avatar_fetched_at DESC LIMIT 1""",
            (username.lower(),),
        )
        row = await cursor.fetchone()
    if not row:
        return {"url": None, "fetched_at": None}
    return {"url": row["avatar_url"], "fetched_at": row["avatar_fetched_at"]}


async def save_avatar(username: str, url: str) -> None:
    """
    Persist an avatar URL for a username, updating every guild that follows
    them and stamping when it was confirmed so refreshes can be throttled.
    """
    fetched_at = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE followed_users
               SET avatar_url = ?, avatar_fetched_at = ?
               WHERE letterboxd_username = ?""",
            (url, fetched_at, username.lower()),
        )
        await db.commit()


async def is_entry_seen(entry_guid: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM seen_entries WHERE entry_guid = ?", (entry_guid,)
        )
        return await cursor.fetchone() is not None


async def mark_entry_seen(entry_guid: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO seen_entries (entry_guid) VALUES (?)",
            (entry_guid,),
        )
        await db.commit()