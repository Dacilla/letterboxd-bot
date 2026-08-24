# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A Discord bot that monitors Letterboxd RSS feeds and posts user reviews as rich Discord embeds. It polls feeds on a configurable interval, tracks what's been posted in SQLite, and integrates with TMDB for movie poster images.

## Setup & Running

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in DISCORD_TOKEN and TMDB_API_KEY
python bot.py
```

**Required env vars:** `DISCORD_TOKEN`, `TMDB_API_KEY`
**Optional:** `POLL_INTERVAL_MINUTES` (default: 10), `DB_PATH` (default: `letterboxd.db`)

**Persistent hosting (systemd):**
```bash
sudo systemctl enable --now letterboxd-bot
sudo systemctl status letterboxd-bot
journalctl -u letterboxd-bot -f
```

There is no test suite.

## Architecture

```
bot.py              → Entry point: init DB, load cog, sync slash commands
cogs/letterboxd.py  → Discord cog: slash commands + polling loop
core/feed.py        → RSS parsing, LBEntry dataclass, avatar scraping
core/embeds.py      → Discord embed construction, star formatting
core/tmdb.py        → TMDB API lookups (poster images, movie URLs)
core/database.py    → SQLite operations (followed_users, seen_entries tables)
```

**Data flow for polling:**
1. `poll_loop()` fires every N minutes
2. `_scan_all()` fetches all followed users from DB
3. For each user: parse RSS → check `seen_entries` → mark seen → fetch TMDB data → build embed → `channel.send()`
4. Entries are marked seen *before* posting to prevent duplicates on crash
5. On `/follow`, all current feed entries are seeded as seen to avoid flooding history

**Slash commands** (require Manage Server except `/following` and `/preview`):
- `/follow <username> [channel]` — start following a Letterboxd user
- `/unfollow <username>` — stop following
- `/following` — list followed accounts in this server
- `/scan` — force immediate poll
- `/preview` — post a sample embed

## Key Implementation Notes

- `cog_load()` creates the `aiohttp.ClientSession` and starts the `poll_loop` task; `cog_unload()` cancels and closes
- Avatars are persisted in `followed_users` (`avatar_url`, `avatar_fetched_at`) per Letterboxd user, shared across guilds. `_get_avatar` in the cog only scrapes when nothing is stored or the stored URL is older than `AVATAR_REFRESH_HOURS` (default 24); on scrape failure it reuses the stored URL, so placeholders only appear for users never successfully scraped
- Avatar scraping uses `curl_cffi` with Chrome impersonation: Letterboxd's Cloudflare protection TLS-fingerprints clients and 403-challenges plain Python HTTP stacks (aiohttp/requests) on HTML pages, even with browser headers. RSS endpoints are not protected this way
- TMDB lookup uses the `tmdb_id` field from RSS if present (fast path via `get_movie_by_id()`), else falls back to `search_movie()` by title+year
- Custom Discord emote IDs for star ratings are hardcoded in `core/embeds.py` — if moving to a new server, these need updating
- Global slash command sync (`tree.sync()`) can take up to 1 hour to propagate; for testing, sync to a specific guild ID instead
- `seen_entries` tracks by RSS `entry_guid` globally (not per-guild), so the same review won't be posted twice even if multiple guilds follow the same user
