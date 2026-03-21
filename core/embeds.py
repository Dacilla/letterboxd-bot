from __future__ import annotations

from typing import Optional

import discord

from core.feed import LBEntry

# Letterboxd's brand green
LETTERBOXD_GREEN = 0x00C030

# Max review length before truncation. Discord embed description cap is 4096.
MAX_REVIEW_LENGTH = 900


def format_rating(rating: float) -> str:
    """
    Convert a numeric Letterboxd rating (0.5–5.0, increments of 0.5)
    into a star string, e.g. 3.5 -> ★★★½☆
    """
    full_stars = int(rating)
    has_half = (rating % 1) >= 0.5
    empty_stars = 5 - full_stars - (1 if has_half else 0)
    return "★" * full_stars + ("½" if has_half else "") + "☆" * empty_stars


def build_embed(
    entry: LBEntry,
    tmdb_url: Optional[str],
    poster_url: Optional[str],
) -> discord.Embed:
    """
    Build a Discord embed for a Letterboxd diary entry.

    poster_url should be the TMDB poster when available, falling back
    to the one extracted from the RSS description.
    """
    title = entry.film_title
    if entry.film_year:
        title += f" ({entry.film_year})"

    # First line of description: rating stars + heart indicator
    header_parts: list[str] = []
    if entry.rating is not None:
        header_parts.append(format_rating(entry.rating))
    if entry.liked:
        header_parts.append("♥")

    description_parts: list[str] = []
    if header_parts:
        description_parts.append(" ".join(header_parts))

    if entry.review_text:
        review = entry.review_text
        if len(review) > MAX_REVIEW_LENGTH:
            review = review[:MAX_REVIEW_LENGTH].rstrip() + "…"
        description_parts.append(f"\n{review}")

    embed = discord.Embed(
        title=title,
        url=entry.review_url,
        description="\n".join(description_parts) or None,
        color=LETTERBOXD_GREEN,
    )

    embed.set_author(
        name=entry.username,
        url=f"https://letterboxd.com/{entry.username}/",
    )

    if poster_url:
        embed.set_thumbnail(url=poster_url)

    # Build a tidy links field
    link_parts: list[str] = [f"[Letterboxd]({entry.film_url})"]
    if tmdb_url:
        link_parts.append(f"[TMDB]({tmdb_url})")

    embed.add_field(name="Links", value=" · ".join(link_parts), inline=False)

    return embed