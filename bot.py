import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from core.database import init_db

load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Guilds: {len(bot.guilds)}")


async def main() -> None:
    async with bot:
        await init_db()
        await bot.load_extension("cogs.letterboxd")
        # Sync slash commands globally.
        # On first deploy this can take up to an hour to propagate;
        # for faster testing, use tree.sync(guild=discord.Object(id=YOUR_GUILD_ID)).
        await bot.tree.sync()
        await bot.start(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())