# BotLite Downloader

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE.md)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Telegram](https://img.shields.io/badge/channel-LinuxBotsNews-26A5E4?logo=telegram&logoColor=white)](https://t.me/LinuxBotsNews)

Minimal, self-hosted Telegram bot that downloads media from 1 000+ sites and sends files straight to your DMs.

> Open-source lite release of [@UltimateFilesDownloaderBot](https://t.me/UltimateFilesDownloaderBot),
> originally designed by **[linuxuser825](https://t.me/LinuxBotsNews)**.

---

## Features

- **1 000+ supported sites** — YouTube, TikTok, Instagram, Twitter/X, Reddit, Pinterest, Vimeo, SoundCloud, and [many more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- **Dual engine** — yt-dlp handles video/audio; gallery-dl takes over for photo galleries and carousels
- **Cookie support** — drop a `cookiesSiteName.txt` file to unlock age-restricted or private content
- **DMs only** — ignores all group chats
- **Configurable via `.env`** — no hardcoded secrets, Docker-friendly
- **Built-in safeguards** — disk space guard, per-user cooldown, concurrent download semaphore
- **Graceful shutdown** — handles `SIGTERM` cleanly for Docker and systemd
- **Admin panel** — `/stats`, `/ban`, `/unban` commands

---

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/LightYagami28/BotLite-Downloader.git
cd BotLite-Downloader
cp .env.example .env
# fill in API_ID, API_HASH, BOT_TOKEN, SUDO_USERS in .env
docker compose up -d
```

### Manual

```bash
git clone https://github.com/LightYagami28/BotLite-Downloader.git
cd BotLite-Downloader
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python bot.py
```

> **Requires:** Python 3.10+, ffmpeg in PATH

---

## Configuration

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Default | Description |
| --- | :---: | --- | --- |
| `API_ID` | ✅ | — | From [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | — | From [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | ✅ | — | From [@BotFather](https://t.me/BotFather) |
| `SUDO_USERS` | ✅ | — | Comma-separated admin user IDs (find yours via [@userinfobot](https://t.me/userinfobot)) |
| `MAX_FILE_SIZE` | ☑️ | `2147483648` | Max upload size in bytes (2 GB Telegram limit) |
| `MAX_CONCURRENT_DOWNLOADS` | ☑️ | `3` | Global concurrent download cap |
| `MIN_FREE_DISK` | ☑️ | `524288000` | Minimum free disk before rejecting requests (500 MB) |
| `USER_COOLDOWN` | ☑️ | `5` | Seconds between requests per user (`0` = disabled) |
| `DB_FILE` | ☑️ | `media_bot.db` | SQLite database path |

---

## Cookie Setup (optional)

Some sites require authentication (age-restricted videos, private content).
Place Netscape-format cookie files next to `bot.py` using this naming scheme:

```text
cookies{sitename}.txt
```

**Examples:**

| File | Used for |
| --- | --- |
| `cookiesyoutube.txt` | youtube.com, youtu.be |
| `cookiesinstagram.txt` | instagram.com |
| `cookiestiktok.txt` | tiktok.com |
| `cookiestwitter.txt` | twitter.com, x.com |

**How to export cookies:**

1. Install [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Log in to the target site
3. Export and save the file with the correct name next to `bot.py`

> Cookie files contain sensitive session tokens — they are excluded from git by default.

---

## Commands

### User

| Command | Description |
| --- | --- |
| `/start` | Welcome message and supported sites |
| `/help` | Usage guide and cookie setup |
| `/status` | Bot uptime and disk space |

### Admin (`SUDO_USERS` only)

| Command | Description |
| --- | --- |
| `/stats` | Downloads, failures, uptime, free disk |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |

---

## Running as a systemd service

```ini
# /etc/systemd/system/botlite.service
[Unit]
Description=BotLite Downloader
After=network.target

[Service]
WorkingDirectory=/opt/BotLite-Downloader
EnvironmentFile=/opt/BotLite-Downloader/.env
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now botlite
sudo systemctl status botlite
```

---

## Project Structure

```text
BotLite-Downloader/
├── bot.py              # Main bot logic
├── config.py           # Config loader (env vars / .env)
├── requirements.txt    # Python dependencies
├── .env.example        # Configuration template
├── Dockerfile
├── docker-compose.yml
├── LICENSE.md
└── SECURITY.md
```

---

## Origin & Credits

This project is the **open-source lite release** of the private, closed-source
**[@UltimateFilesDownloaderBot](https://t.me/UltimateFilesDownloaderBot)**,
originally designed and developed by **linuxuser825**.

| Contributor | Role |
| --- | --- |
| [linuxuser825](https://t.me/LinuxBotsNews) | Original author — private closed-source version |
| [LightYagami28](https://github.com/LightYagami28) | Open-source lite release & maintainer |

Follow updates on Telegram: **[t.me/LinuxBotsNews](https://t.me/LinuxBotsNews)**

---

## License

[MIT](LICENSE.md) — do whatever you want, keep the attribution.
