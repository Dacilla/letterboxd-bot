# letterboxd-bot

A Discord bot that monitors Letterboxd RSS feeds and posts reviews as rich embeds.

## Features

- Polls followed accounts on a configurable interval (default: 10 minutes)
- Posts star ratings, heart/liked indicator, review text, poster, film title and year
- Links to the Letterboxd review, Letterboxd film page, and TMDB
- Seeding on first follow — no history flood when you add someone new
- Slash commands to manage followed accounts without touching any config files
- Per-user channel targeting — each followed account can post to a different channel

## Commands

| Command | Permission | Description |
|---|---|---|
| `/follow <username> [channel]` | Manage Server | Follow a Letterboxd user; posts to the specified channel, or the current one if not given |
| `/unfollow <username>` | Manage Server | Stop following a user |
| `/following` | Everyone | List all followed accounts in this server |
| `/scan` | Manage Server | Force an immediate scan, bypassing the timer |

## Setup

### 1. Prerequisites

- Python 3.11+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- A TMDB API key (free at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api))

### 2. Install dependencies

```bash
cd letterboxd-bot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
DISCORD_TOKEN=your_discord_bot_token_here
TMDB_API_KEY=your_tmdb_api_key_here
POLL_INTERVAL_MINUTES=10
```

### 4. Discord bot settings

In the Developer Portal, under your bot's settings:
- **Privileged Gateway Intents**: none required
- **OAuth2 scopes**: `bot`, `applications.commands`
- **Bot permissions**: `Send Messages`, `Embed Links`

### 5. Run

```bash
python bot.py
```

To keep it running persistently, a systemd service works well on Linux:

```ini
# /etc/systemd/system/letterboxd-bot.service
[Unit]
Description=Letterboxd Discord Bot
After=network.target

[Service]
User=youruser
WorkingDirectory=/path/to/letterboxd-bot
ExecStart=/path/to/letterboxd-bot/venv/bin/python bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now letterboxd-bot
```

Alternatively, just run it in a `screen` or `tmux` session if you don't want to deal with systemd.

## Notes

- Slash commands are synced globally on startup. Global sync can take up to an hour
  to propagate on first deploy. For faster testing, replace the `tree.sync()` call in
  `bot.py` with `tree.sync(guild=discord.Object(id=YOUR_GUILD_ID))` temporarily.
- The poll interval can't realistically go below ~5 minutes without risking Letterboxd
  rate-limiting or blocking requests. 10 minutes is a sensible default.
- Letterboxd's own RSS refresh lag adds a few minutes on top of the poll interval,
  so expect reviews to appear within roughly 5–15 minutes of being posted.
- The `liked`/heart field is absent for some accounts depending on their privacy
  settings — this is handled gracefully and the heart is just omitted.