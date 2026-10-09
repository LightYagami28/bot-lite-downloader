# BotLite Downloader

<!-- ── Row 1 — Identity ─────────────────────────────────────────────────── -->
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Version](https://img.shields.io/badge/version-1.2.0-f97316?logo=git&logoColor=white)](https://github.com/LightYagami28/BotLite-Downloader/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?logo=opensourceinitiative&logoColor=white)](LICENSE.md)
[![Telegram](https://img.shields.io/badge/channel-LinuxBotsNews-26A5E4?logo=telegram&logoColor=white)](https://t.me/LinuxBotsNews)

<!-- ── Row 2 — CI ────────────────────────────────────────────────────────── -->
[![SonarCloud Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=LightYagami28_BotLite-Downloader&metric=alert_status)](https://sonarcloud.io/project/overview?id=LightYagami28_BotLite-Downloader)
[![SonarCloud Security](https://sonarcloud.io/api/project_badges/measure?project=LightYagami28_BotLite-Downloader&metric=security_rating)](https://sonarcloud.io/project/overview?id=LightYagami28_BotLite-Downloader)
[![SonarCloud Maintainability](https://sonarcloud.io/api/project_badges/measure?project=LightYagami28_BotLite-Downloader&metric=sqale_rating)](https://sonarcloud.io/project/overview?id=LightYagami28_BotLite-Downloader)
[![SonarCloud Reliability](https://sonarcloud.io/api/project_badges/measure?project=LightYagami28_BotLite-Downloader&metric=reliability_rating)](https://sonarcloud.io/project/overview?id=LightYagami28_BotLite-Downloader)

<!-- ── Row 3 — Security & deps ──────────────────────────────────────────── -->
[![Snyk](https://snyk.io/test/github/LightYagami28/BotLite-Downloader/badge.svg)](https://snyk.io/test/github/LightYagami28/BotLite-Downloader)
[![Snyk CI](https://github.com/LightYagami28/BotLite-Downloader/actions/workflows/snyk.yml/badge.svg)](https://github.com/LightYagami28/BotLite-Downloader/actions/workflows/snyk.yml)
[![SonarCloud CI](https://github.com/LightYagami28/BotLite-Downloader/actions/workflows/sonarcloud.yml/badge.svg)](https://github.com/LightYagami28/BotLite-Downloader/actions/workflows/sonarcloud.yml)
[![Dependabot](https://img.shields.io/badge/dependabot-enabled-0366d6?logo=dependabot&logoColor=white)](https://github.com/LightYagami28/BotLite-Downloader/network/updates)

<!-- ── Row 4 — Stack ────────────────────────────────────────────────────── -->
[![yt-dlp](https://img.shields.io/badge/engine-yt--dlp-FF0000?logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Telethon](https://img.shields.io/badge/library-Telethon-26A5E4?logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![Docker](https://img.shields.io/badge/base-Debian%20slim-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![aiohttp](https://img.shields.io/badge/webapp-aiohttp-2C5BB4?logo=aiohttp&logoColor=white)](https://docs.aiohttp.org)

---

Minimal, self-hosted Telegram bot that downloads media from 1 000+ sites
and sends files straight to your DMs — with an optional **WebApp dashboard**
accessible directly inside Telegram.

> **Maintenance note:** the repository had gone several months without a
> meaningful update. Light has taken the project back into active maintenance,
> refreshed its dependencies, restored automated checks and is progressively
> modernising the Telegram WebApp and group-safety model. The original project
> and contributors remain credited below.

> Open-source lite release of **[@UltimateFilesDownloaderBot](https://t.me/UltimateFilesDownloaderBot)**,
> originally designed by **[linuxuser825](https://t.me/LinuxBotsNews)**.

---

## Features

- **1 000+ sites** — YouTube, TikTok, Instagram, Twitter/X, Reddit, Pinterest, Vimeo, SoundCloud, and [many more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- **Dual download engine** — yt-dlp for video/audio, gallery-dl as fallback for photo carousels
- **Telegram WebApp dashboard** — full-screen admin panel openable inside Telegram (status, stats, ban/unban)
- **Inline keyboard buttons** — `/start`, `/status`, `/stats` all show a **📊 Open Dashboard** button when the webapp is enabled
- **Cookie support** — drop a `cookiesSiteName.txt` to unlock age-restricted or private content
- **Private chats by default** — group handling is opt-in through `ALLOW_GROUPS`
  and remains subject to the same limits and permissions
- **Config via `.env`** — no hardcoded secrets, Docker-friendly
- **Built-in safeguards** — disk space guard, per-user cooldown, concurrent download semaphore
- **Graceful shutdown** — handles `SIGTERM` cleanly for Docker and systemd
- **Hardened Docker image** — digest-pinned Debian slim, non-root user, minimal runtime packages
- **Optional voice-chat playback** — bounded audio streaming in explicitly allowlisted groups

---

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/LightYagami28/BotLite-Downloader.git
cd BotLite-Downloader
cp .env.example .env
# Fill in API_ID, API_HASH, BOT_TOKEN, SUDO_USERS
docker compose up -d
```

### Manual

```bash
git clone https://github.com/LightYagami28/BotLite-Downloader.git
cd BotLite-Downloader
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python -m botlite
```

> **Requires:** Python 3.12+, ffmpeg in PATH

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

### Required

| Variable | Description |
| --- | --- |
| `API_ID` | From [my.telegram.org](https://my.telegram.org) → API development tools |
| `API_HASH` | From [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `SUDO_USERS` | Comma-separated admin Telegram user IDs (find yours via [@userinfobot](https://t.me/userinfobot)) |

### Optional

| Variable | Default | Description |
| --- | --- | --- |
| `MAX_FILE_SIZE` | `2147483648` | Max upload size in bytes (2 GB = Telegram hard limit) |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Global concurrent download cap |
| `MIN_FREE_DISK` | `524288000` | Min free disk before rejecting requests (500 MB) |
| `USER_COOLDOWN` | `5` | Seconds between requests per user (`0` = disabled) |
| `ALLOW_GROUPS` | `false` | Enable downloads and basic commands in Telegram groups |
| `ALLOWED_GROUP_IDS` | _(empty)_ | Comma-separated allowlist of Telegram group IDs; required when groups are enabled |
| `VOICE_ENABLED` | `false` | Enable `/play`, `/pause`, `/resume` and `/voice_stop` in allowlisted groups |
| `VOICE_MAX_DURATION` | `1800` | Maximum audio duration in seconds for voice playback |
| `VOICE_MAX_FILE_SIZE` | `104857600` | Maximum downloaded voice audio size in bytes (100 MiB) |
| `DB_FILE` | `media_bot.db` | SQLite database path |
| `WEBAPP_PUBLIC_URL` | _(empty)_ | Public HTTPS URL of the dashboard — enables the WebApp feature |
| `WEBAPP_HOST` | `0.0.0.0` | Bind address for the embedded web server |
| `WEBAPP_PORT` | `8080` | Listen port for the embedded web server |
| `WEBAPP_INIT_DATA_MAX_AGE` | `3600` | Maximum age of Telegram WebApp `initData` in seconds |

---

## WebApp Dashboard

When `WEBAPP_PUBLIC_URL` is set, BotLite starts an embedded **aiohttp** web server and
adds a **📊 Open Dashboard** button to every command reply.

The dashboard opens full-screen inside Telegram and provides:

| Panel | Available to |
| --- | --- |
| Bot status (uptime, active downloads, free disk) | Everyone |
| Download statistics (succeeded / failed / success rate) | `SUDO_USERS` only |
| Ban / Unban by User ID | `SUDO_USERS` only |

Access is authenticated via Telegram's **WebApp `initData`** (HMAC-SHA256 signature verified server-side).

Group downloads are disabled by default. To enable them safely, set `ALLOW_GROUPS=true`
and provide only the required IDs in `ALLOWED_GROUP_IDS`; an empty allowlist is rejected
by configuration validation.

Voice playback is opt-in and requires `ALLOW_GROUPS=true`, an explicit
`ALLOWED_GROUP_IDS` list, and `VOICE_ENABLED=true`. Install the bot in an
allowlisted group and start a Telegram voice chat manually before issuing
`/play https://…`; BotLite will not create a call automatically. Playback uses
PyTgCalls/NTgCalls over the existing Telethon client. `/pause`, `/resume` and
`/voice_stop` control the current track. Unknown-duration media, playlists, and
tracks exceeding the configured duration/size are rejected. The local audio
file remains until playback ends or is stopped, then is removed. Test this with
a dedicated bot and private test group before production use.

The native NTgCalls wheels target glibc, so the Docker image uses Debian slim
instead of Alpine/musl. `ffmpeg` is installed for media decoding. The CI workflow
builds the image to catch dependency and native-library integration failures.

### HTTPS requirement

Telegram only opens WebApp URLs over HTTPS. For self-hosted setups, expose the
embedded server with one of:

```bash
# Cloudflare Tunnel (zero-config, free)
cloudflared tunnel --url http://localhost:8080

# Or nginx + Let's Encrypt (permanent setup)
certbot --nginx -d bot.example.com
```

Then set `WEBAPP_PUBLIC_URL=https://your-domain-or-tunnel.com` in `.env`.

---

## Cookie Setup (optional)

Some sites require authentication for age-restricted or private content.
Place Netscape-format cookie files next to `run.py`:

```text
cookies{sitename}.txt
```

| File | Used for |
| --- | --- |
| `cookiesyoutube.txt` | youtube.com, youtu.be |
| `cookiesinstagram.txt` | instagram.com |
| `cookiestiktok.txt` | tiktok.com |
| `cookiestwitter.txt` | twitter.com, x.com |

**How to export:**

1. Install [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Log in to the target site in Chrome
3. Export → save the file with the correct name next to `run.py`

> Cookie files contain sensitive session tokens — they are excluded from git by default.

---

## Commands

### User

| Command | Description |
| --- | --- |
| `/start` | Welcome message and supported sites |
| `/help` | Usage guide, limits, and cookie setup |
| `/status` | Bot uptime, active downloads, and free disk |

### Admin (`SUDO_USERS` only)

| Command | Description |
| --- | --- |
| `/stats` | Download counters, uptime, disk, DB size |
| `/ban <user_id>` | Ban a user from the bot |
| `/unban <user_id>` | Unban a user |

## Maintenance and release policy

Dependencies are tracked with Dependabot and reviewed against the current
Python/Telegram ecosystem. Changes must pass the test suite, static checks and
dependency validation before release. Releases are tagged semantically and
published only after the generated artifact and checksum have been verified.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution workflow and
[`SECURITY.md`](SECURITY.md) for vulnerability reports and deployment guidance.

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
ExecStart=/usr/bin/python3 -m botlite
Restart=always
RestartSec=5
User=botlite

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
├── botlite/
│   ├── __init__.py          # Package root, VERSION constant
│   ├── __main__.py          # python -m botlite entry point
│   ├── app.py               # Bootstrap: wires all modules, starts bot
│   ├── client.py            # Telethon singleton + shared runtime state
│   ├── config.py            # Env var / .env loader
│   ├── db.py                # SQLite: ban list + download counters
│   ├── downloader/
│   │   ├── __init__.py      # Public download() API
│   │   ├── ytdlp.py         # yt-dlp engine
│   │   ├── gallery.py       # gallery-dl fallback engine
│   │   └── cookies.py       # Cookie file resolver
│   ├── handlers/
│   │   ├── __init__.py      # Registers all handlers
│   │   ├── access.py        # Shared private-chat/group allowlist checks
│   │   ├── commands.py      # /start /help /status /stats /ban /unban
│   │   └── url.py           # URL detection + upload pipeline
│   ├── utils/
│   │   ├── format.py        # fmt_size, fmt_dur, build_caption
│   │   └── system.py        # free_disk, cleanup_old_temps, setup_signals
│   └── webapp/
│       ├── __init__.py      # start_webapp / stop_webapp
│       ├── auth.py          # Telegram initData HMAC validation
│       ├── server.py        # aiohttp routes: /api/status /api/stats /api/ban
│       └── static/
│           └── index.html   # Telegram WebApp dashboard (single-page)
├── run.py                   # Alternate entry point
├── requirements.txt         # Runtime dependencies
├── requirements-dev.txt     # Test, lint and dependency-audit tools
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── LICENSE
└── SECURITY.md
```

---

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting and self-hosting hardening notes.

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
