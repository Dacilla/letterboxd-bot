from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup


@dataclass
class LBEntry:
    guid: str
    username: str
    film_title: str
    film_year: Optional[int]
    rating: Optional[float]
    liked: bool
    review_text: Optional[str]
    review_url: str       # link to diary entry / review
    film_url: str         # letterboxd.com/film/<slug>/
    rss_poster_url: Optional[str]  # poster extracted from RSS description HTML


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

        liked = entry.get("letterboxd_liked", "No").lower() == "yes"

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
                review_text=review_text,
                review_url=review_url,
                film_url=film_url,
                rss_poster_url=rss_poster_url,
            )
        )

    return entries


def _parse_description(html: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract the plain-text review and poster URL from the RSS description HTML.
    The HTML typically contains an <img> (poster) followed by <p> tags (review).
    """
    soup = BeautifulSoup(html, "html.parser")
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup


@dataclass
class LBEntry:
    guid: str
    username: str
    film_title: str
    film_year: Optional[int]
    rating: Optional[float]
    liked: bool
    review_text: Optional[str]
    review_url: str       # link to diary entry / review
    film_url: str         # letterboxd.com/film/<slug>/
    rss_poster_url: Optional[str]  # poster extracted from RSS description HTML


async def fetch_user_avatar(
    username: str, session: aiohttp.ClientSession
) -> Optional[str]:
    """
    Scrape the Letterboxd profile page to find the user's avatar URL.
    Returns None if not found or the request fails.
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

    # The avatar is in a <div class="profile-avatar"> or an <img> with
    # class containing "avatar". Fall back through a few selectors.
    for selector in (
        "div.profile-avatar img",
        "img.avatar",
        "span.avatar img",
        "a.avatar img",
    ):
        img = soup.select_one(selector)
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                return src

    return None


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

        liked = entry.get("letterboxd_liked", "No").lower() == "yes"

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
                review_text=review_text,
                review_url=review_url,
                film_url=film_url,
                rss_poster_url=rss_poster_url,
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

    text = soup.get_text(separator="\n").strip()
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return (text if text else None), poster_url


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
    poster_url: Optional[str] = None
    img = soup.find("img")
    if img:
        poster_url = img.get("src") or None
        img.decompose()  # remove so it doesn't pollute the text

    text = soup.get_text(separator="\n").strip()
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return (text if text else None), poster_url


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