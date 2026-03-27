from __future__ import annotations

from typing import Optional

import discord

from core.feed import LBEntry

# Letterboxd's brand green
LETTERBOXD_GREEN = 0x00C030

# Max review length before truncation. Discord embed description cap is 4096.
MAX_REVIEW_LENGTH = 900

STAR_FULL = "<:star_full:1484847326534045816>"
STAR_HALF = "<:star_half:1484847324617248871>"


def format_rating(rating: float) -> str:
    """
    Convert a numeric Letterboxd rating (0.5–5.0, increments of 0.5)
    into a custom emote string, e.g. 3.5 -> star star star star_half
    """
    full_stars = int(rating)
    has_half = (rating % 1) >= 0.5
    return STAR_FULL * full_stars + (STAR_HALF if has_half else "")


def build_embed(
    entry: LBEntry,
    tmdb_url: Optional[str],
    poster_url: Optional[str],
    avatar_url: Optional[str] = None,
) -> discord.Embed:
    """
    Build a Discord embed for a Letterboxd diary entry.

    poster_url should be the TMDB poster when available, falling back
    to the one extracted from the RSS description.
    """
    title = entry.film_title
    if entry.film_year:
        title += f" ({entry.film_year})"

    # First line: rating stars + heart indicator
    header_parts: list[str] = []
    if entry.rating is not None:
        header_parts.append(format_rating(entry.rating))
    if entry.liked:
        header_parts.append("❤️")

    description_parts: list[str] = []
    if header_parts:
        description_parts.append(" ".join(header_parts))

    if entry.spoiler:
        description_parts.append("*This review contains spoilers.*")

    if entry.review_text:
        review = entry.review_text
        if len(review) > MAX_REVIEW_LENGTH:
            review = review[:MAX_REVIEW_LENGTH].rstrip() + "…"
        if entry.spoiler:
            review = "\n".join(f"||{line}||" if line.strip() else line for line in review.split("\n"))
        description_parts.append(f"\n{review}")

    embed = discord.Embed(
        title=title,
        url=entry.film_url,
        description="\n".join(description_parts) or None,
        color=LETTERBOXD_GREEN,
    )

    embed.set_author(
        name=entry.username,
        url=f"https://letterboxd.com/{entry.username}/",
        icon_url=avatar_url or None,
    )

    if poster_url:
        embed.set_thumbnail(url=poster_url)

    # Links field: review first, then film pages
    link_parts: list[str] = [f"[Review]({entry.review_url})"]
    link_parts.append(f"[Letterboxd]({entry.film_url})")
    if tmdb_url:
        link_parts.append(f"[TMDB]({tmdb_url})")

    embed.add_field(name="Links", value=" · ".join(link_parts), inline=False)

    return embed