# BotLite Downloader - Specification

## Purpose

Self-hosted Telegram bot that downloads media from public links (yt-dlp, with gallery-dl as
fallback) and sends the file back to the requesting chat. An optional Telegram WebApp
dashboard shows status and statistics and lets admins ban or unban users. An optional voice
feature plays audio in the voice chat of allowlisted groups.

## Features

- Link detection in private chats (and in allowlisted groups when `ALLOW_GROUPS` is on).
- Video/audio download via yt-dlp; image carousels via gallery-dl.
- Per-user cooldown, global concurrency cap, file-size cap, minimum free disk check.
- Ban list and counters stored in SQLite.
- Admin commands restricted to `SUDO_USERS`.
- Optional dashboard (aiohttp) authenticated with Telegram WebApp `initData`.
- Optional `/play`, `/pause`, `/resume`, `/voice_stop` in group voice chats (py-tgcalls).

## Architecture

```
Telegram <-> Telethon client (botlite/client.py)
                 |-- handlers/commands.py   /start /help /status /stats /ban /unban /play ...
                 |-- handlers/url.py        URL detection -> download -> upload pipeline
                 |-- handlers/access.py     authorization (ban list, groups, sudo)
                 |-- downloader/            ytdlp.py, gallery.py (fallback), cookies.py
                 |-- voice.py               group voice-chat playback
                 |-- db.py                  SQLite
                 `-- webapp/                aiohttp server + auth.py (initData HMAC) + static UI
```

`botlite/app.py` wires the modules and starts the client; `python -m botlite` is the entry
point. `config.py` reads environment variables (and `.env`) and `validate()` aborts at start-up
on invalid or missing settings.

## Main flow (URL download)

1. A message with a URL arrives; access checks run (ban, group allowlist, cooldown).
2. A slot is acquired from the global concurrency limit; free disk space is checked.
3. The yt-dlp engine downloads into a temporary directory; if it fails, gallery-dl is tried.
4. The file is checked against `MAX_FILE_SIZE`, uploaded to Telegram, temp files removed.
5. Counters (`total_downloads`, `failed_downloads`) are updated.

## Data

SQLite file (`DB_FILE`):

| Table | Columns |
| --- | --- |
| `banned_users` | `user_id` (PK), `banned_at` |
| `stats` | `name` (PK), `value` |

Telegram sessions (`*.session`) and cookie files are secrets and must never be committed.

## Interfaces

- Bot commands: see README.
- HTTP (only when `WEBAPP_PUBLIC_URL` is set): `GET /`, `GET /app.js`, `GET /api/status`,
  `GET /api/me`, `GET /api/stats`, `POST /api/ban`, `POST /api/unban`. API calls require valid,
  recent `initData`; ban/unban require a user in `SUDO_USERS`.
- Configuration: environment variables listed in README and `.env.example`.

## Stack and versions (checked 2026-10-31)

| Component | Version |
| --- | --- |
| Python | 3.14 (image `python:3.14-slim-trixie`); `requires-python >= 3.12` |
| Telethon | 1.45.0 |
| yt-dlp | 2026.10.26 |
| gallery-dl | 1.32.19 |
| aiohttp | 3.14.5 |
| py-tgcalls / ntgcalls | 3.0.0 / 3.0.5 |
| python-dotenv | 1.2.4 |
| Dev: pytest, pytest-cov, ruff, pip-audit | 9.2.0, 7.1.0, 0.17.3, 2.10.1 |

Python 3.15 is released but not adopted: ntgcalls 3.0.5 publishes no wheels for it.
Dependencies are pinned with hashes (`requirements*.lock`, `uv.lock`); CI checks that locks are
in sync with `requirements*.txt`.

## Security

- WebApp requests are validated server-side (HMAC of `initData`, maximum age); dashboard binds
  to loopback by default; strict CSP.
- Groups and voice are opt-in with explicit allowlists; downloads are size- and rate-limited.
- Docker image: digest-pinned base, hash-locked dependencies, no pip in runtime, non-root user.
- CI: Ruff + Bandit rules (`--select S`), `pip-audit`, Docker Scout (needs secrets, skipped
  without them), SonarQube/SonarCloud (needs `SONAR_TOKEN`, skipped without it).
- Reports: see `SECURITY.md`.

## Limits

- Upload cap 2 GB (Telegram); no persistent queue (restart drops in-flight downloads).
- Site support depends on yt-dlp/gallery-dl; private content needs user-provided cookies.
- Single-instance, SQLite only.

## Roadmap

- Python 3.15 as soon as ntgcalls publishes compatible wheels.
- Persistent download queue and per-user quotas.
- Integration test against a mocked Telegram transport.
