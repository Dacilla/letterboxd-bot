from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass
class LBEntry:
    guid: str
    username: str
    film_title: str
    film_year: Optional[int]
    rating: Optional[float]
    liked: bool
    rewatch: bool
    review_text: Optional[str]
    spoiler: bool
    review_url: str         # link to diary entry / review
    film_url: str           # letterboxd.com/film/<slug>/
    rss_poster_url: Optional[str]  # poster extracted from RSS description HTML
    tmdb_id: Optional[str]  # TMDB movie ID if present in feed


async def get_avatar_url(
    username: str, session: aiohttp.ClientSession
) -> Optional[str]:
    """
    Scrape the Letterboxd profile page and return the user's avatar URL.
    Uses the og:image meta tag which reliably points to the avatar.
    Returns None on any failure.
    """
    url = f"https://letterboxd.com/{username}/"
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return og_image["content"]
    return None


async def fetch_feed(
    username: str, session: aiohttp.ClientSession
) -> list[LBEntry]:
    """
    Fetch and parse a Letterboxd RSS feed.
    Returns entries newest-first (RSS order); caller reverses for posting.
    Returns an empty list on any error so callers can skip gracefully.
    """
    url = f"https://letterboxd.com/{username}/rss/"
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            if resp.status != 200:
                return []
            content = await resp.text()
    except Exception:
        return []

    feed = feedparser.parse(content)
    entries: list[LBEntry] = []

    for entry in feed.entries:
        # Only handle diary/review entries, which carry a film title.
        film_title: str = (
            entry.get("letterboxd_filmtitle") or entry.get("title", "")
        ).strip()
        if not film_title:
            continue

        film_year_raw = entry.get("letterboxd_filmyear")
        film_year = int(film_year_raw) if film_year_raw else None

        rating_raw = entry.get("letterboxd_memberrating")
        rating = float(rating_raw) if rating_raw else None

        # The correct field name is letterboxd_memberlike (not letterboxd_liked)
        liked = entry.get("letterboxd_memberlike", "No").strip().lower() == "yes"
        rewatch = entry.get("letterboxd_rewatch", "No").strip().lower() == "yes"

        tmdb_id: Optional[str] = entry.get("tmdb_movieid") or None

        spoiler = (
            entry.get("letterboxd_containsspoilers", "No").strip().lower() == "yes"
        )

        description_html: str = entry.get("description") or entry.get("summary") or ""
        review_text, rss_poster_url = _parse_description(description_html)

        review_url: str = entry.get("link", "")
        film_url = _derive_film_url(review_url)

        # Use the entry id/guid as the dedup key, fall back to the URL.
        guid: str = entry.get("id") or entry.get("guid") or review_url

        entries.append(
            LBEntry(
                guid=guid,
                username=username,
                film_title=film_title,
                film_year=film_year,
                rating=rating,
                liked=liked,
                rewatch=rewatch,
                review_text=review_text,
                spoiler=spoiler,
                review_url=review_url,
                film_url=film_url,
                rss_poster_url=rss_poster_url,
                tmdb_id=tmdb_id,
            )
        )

    return entries


def _parse_description(html: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract the plain-text review and poster URL from the RSS description HTML.
    The HTML typically contains an <img> (poster) followed by <p> tags (review).
    """
    soup = BeautifulSoup(html, "html.parser")

    poster_url: Optional[str] = None
    img = soup.find("img")
    if img:
        poster_url = img.get("src") or None
        img.decompose()  # remove so it doesn't pollute the text

    text = _html_to_discord_markdown(soup)

    return (text if text else None), poster_url


def _html_to_discord_markdown(soup: BeautifulSoup) -> str:
    """
    Convert Letterboxd review HTML into Discord-friendly Markdown.

    BeautifulSoup.get_text(separator="\n") treats inline formatting tags as
    separator boundaries, so "a <i>movie</i>" becomes three lines. Keep block
    spacing at block tags instead.
    """
    blocks: list[str] = []

    for child in soup.contents:
        if isinstance(child, NavigableString):
            text = _normalize_inline_text(str(child)).strip()
        elif isinstance(child, Tag):
            text = _format_html_block(child).strip()
        else:
            continue

        if text:
            blocks.append(text)

    text = "\n\n".join(blocks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _format_html_block(tag: Tag) -> str:
    name = tag.name.lower()
    text = _format_html_inline_children(tag)

    if name == "blockquote":
        return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())

    if name in {"ul", "ol"}:
        items: list[str] = []
        for index, item in enumerate(tag.find_all("li", recursive=False), start=1):
            item_text = _format_html_inline_children(item).strip()
            if item_text:
                marker = f"{index}." if name == "ol" else "-"
                items.append(f"{marker} {item_text}")
        return "\n".join(items)

    return text


def _format_html_inline_children(tag: Tag) -> str:
    return "".join(_format_html_inline(child) for child in tag.children)


def _format_html_inline(node: object) -> str:
    if isinstance(node, NavigableString):
        return _normalize_inline_text(str(node))
    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    if name == "br":
        return "\n"

    text = _format_html_inline_children(node)
    if not text:
        return ""

    if name in {"i", "em"}:
        return _wrap_discord_markdown(text, "*")
    if name in {"b", "strong"}:
        return _wrap_discord_markdown(text, "**")
    if name in {"s", "strike", "del"}:
        return _wrap_discord_markdown(text, "~~")
    if name == "a":
        href = node.get("href")
        if href:
            return f"[{text}]({href})"

    return text


def _wrap_discord_markdown(text: str, marker: str) -> str:
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    core = text.strip()
    if not core:
        return text
    return f"{leading}{marker}{core}{marker}{trailing}"


def _normalize_inline_text(text: str) -> str:
    return text.replace("\xa0", " ")


def _derive_film_url(review_url: str) -> str:
    """
    Derive the Letterboxd film page from a diary/review URL.

    Review URL:  https://letterboxd.com/{user}/film/{slug}/
    Film page:   https://letterboxd.com/film/{slug}/
    """
    if "/film/" in review_url:
        after_film = review_url.split("/film/", 1)[1]
        slug = after_film.strip("/").split("/")[0]
        return f"https://letterboxd.com/film/{slug}/"
    return review_url
