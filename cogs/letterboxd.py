from __future__ import annotations

import os
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from core import database, embeds
from core.feed import fetch_feed
from core.tmdb import search_movie

POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", 10))


class LetterboxdCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.tmdb_key: Optional[str] = os.getenv("TMDB_API_KEY")
        self.session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        self.poll_loop.start()

    async def cog_unload(self) -> None:
        self.poll_loop.cancel()
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # Polling task
    # ------------------------------------------------------------------

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_loop(self) -> None:
        await self._scan_all()

    @poll_loop.before_loop
    async def _before_poll(self) -> None:
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Core scan logic (shared between the task and the /scan command)
    # ------------------------------------------------------------------

    async def _scan_all(self, guild_id: Optional[int] = None) -> None:
        """
        Scan followed accounts and post new reviews.
        If guild_id is given, only scan that guild's followed accounts.
        """
        if guild_id is not None:
            followed = await database.get_followed_users(guild_id)
        else:
            followed = await database.get_all_followed_users()

        for user in followed:
            await self._scan_user(user)

    async def _scan_user(self, user: dict) -> None:
        username: str = user["letterboxd_username"]
        channel_id: int = user["channel_id"]

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        entries = await fetch_feed(username, self.session)

        # Reverse so we post oldest-new entry first (chronological order).
        for entry in reversed(entries):
            if await database.is_entry_seen(entry.guid):
                continue

            # Mark seen before posting so a crash mid-send doesn't cause double-posts.
            await database.mark_entry_seen(entry.guid)

            tmdb_url: Optional[str] = None
            poster_url: Optional[str] = entry.rss_poster_url

            if self.tmdb_key:
                result = await search_movie(
                    entry.film_title, entry.film_year, self.session, self.tmdb_key
                )
                if result:
                    tmdb_url = result["url"]
                    # Prefer the TMDB poster; it's usually higher quality.
                    poster_url = result["poster_url"] or poster_url

            embed = embeds.build_embed(entry, tmdb_url, poster_url)
            await channel.send(embed=embed)

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @app_commands.command(
        name="follow",
        description="Follow a Letterboxd user and post their reviews to a channel.",
    )
    @app_commands.describe(
        username="Letterboxd username to follow",
        channel="Channel to post reviews in (defaults to the current channel)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def follow(
        self,
        interaction: discord.Interaction,
        username: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        username = username.strip().lower()
        target_channel = channel or interaction.channel
        await interaction.response.defer(ephemeral=True)

        added = await database.add_followed_user(
            username, interaction.guild_id, target_channel.id
        )

        if not added:
            await interaction.followup.send(
                f"**{username}** is already being followed in this server."
            )
            return

        # Seed all current RSS entries as seen so we don't flood the channel
        # with the user's entire history on first follow.
        entries = await fetch_feed(username, self.session)
        for entry in entries:
            await database.mark_entry_seen(entry.guid)

        await interaction.followup.send(
            f"Now following **{username}** on Letterboxd. "
            f"New reviews will be posted to {target_channel.mention}.\n"
            f"({len(entries)} existing {'entry' if len(entries) == 1 else 'entries'} "
            f"seeded — only future reviews will be posted.)"
        )

    @app_commands.command(
        name="unfollow",
        description="Stop following a Letterboxd user.",
    )
    @app_commands.describe(username="Letterboxd username to unfollow")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def unfollow(self, interaction: discord.Interaction, username: str) -> None:
        username = username.strip().lower()
        removed = await database.remove_followed_user(username, interaction.guild_id)

        if removed:
            await interaction.response.send_message(
                f"No longer following **{username}**.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"**{username}** wasn't being followed in this server.", ephemeral=True
            )

    @app_commands.command(
        name="following",
        description="List all Letterboxd accounts followed in this server.",
    )
    async def following(self, interaction: discord.Interaction) -> None:
        users = await database.get_followed_users(interaction.guild_id)

        if not users:
            await interaction.response.send_message(
                "No Letterboxd accounts are being followed in this server.",
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for u in users:
            channel = self.bot.get_channel(u["channel_id"])
            channel_str = channel.mention if channel else f"*(deleted channel)*"
            lines.append(f"**{u['letterboxd_username']}** → {channel_str}")

        embed = discord.Embed(
            title="Followed Letterboxd Accounts",
            description="\n".join(lines),
            color=embeds.LETTERBOXD_GREEN,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="scan",
        description="Force an immediate scan of all followed Letterboxd accounts.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def scan(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Scanning followed accounts...", ephemeral=True
        )
        await self._scan_all(guild_id=interaction.guild_id)
        await interaction.edit_original_response(content="Scan complete.")

    @app_commands.command(
        name="preview",
        description="Post a sample review embed so you can see what it looks like.",
    )
    async def preview(self, interaction: discord.Interaction) -> None:
        from core.feed import LBEntry

        dummy_entry = LBEntry(
            guid="preview-dummy-guid",
            username=interaction.user.display_name,
            film_title="Mulholland Drive",
            film_year=2001,
            rating=4.5,
            liked=True,
            review_text=(
                "Lynch at his most hypnotic. The first two acts build an almost "
                "unbearable sense of dread and longing, and then the rug pull in "
                "the third recontextualises everything you thought you understood. "
                "Naomi Watts is extraordinary. One of those films that gets stranger "
                "and richer every time you watch it."
            ),
            review_url="https://letterboxd.com/",
            film_url="https://letterboxd.com/film/mulholland-drive/",
            rss_poster_url=None,
        )

        tmdb_url = "https://www.themoviedb.org/movie/1018"
        poster_url = "https://image.tmdb.org/t/p/w500/56cph0HsTQXGEQEKoZTSAJyGMbO.jpg"

        embed = embeds.build_embed(dummy_entry, tmdb_url, poster_url)
        embed.set_footer(text="This is a preview — not a real review.")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You need the **Manage Server** permission to use that command.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"An error occurred: {error}", ephemeral=True
            )
            raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LetterboxdCog(bot))