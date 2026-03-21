import os
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
        await db.commit()


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