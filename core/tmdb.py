from __future__ import annotations

from typing import Optional

import aiohttp

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


async def search_movie(
    title: str,
    year: Optional[int],
    session: aiohttp.ClientSession,
    api_key: str,
) -> Optional[dict]:
    """
    Search TMDB for a film by title and optional year.

    Returns a dict with keys:
        'url'        - https://www.themoviedb.org/movie/{id}
        'poster_url' - full poster image URL, or None

    Returns None if no result is found or the request fails.
    """
    params: dict = {
        "api_key": api_key,
        "query": title,
        "language": "en-US",
        "include_adult": "false",
        "page": "1",
    }
    if year:
        params["year"] = str(year)

    try:
        async with session.get(
            f"{TMDB_API_BASE}/search/movie",
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None

    results = data.get("results")
    if not results:
        return None

    movie = results[0]
    movie_id = movie.get("id")
    poster_path = movie.get("poster_path")

    return {
        "url": f"https://www.themoviedb.org/movie/{movie_id}",
        "poster_url": f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None,
    }