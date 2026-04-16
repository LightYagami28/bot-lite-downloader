# Bot Lite Downloader — CLAUDE.md

Guidance for Claude Code when working on the BotLite Downloader project.

## Panoramica

**BotLite Downloader** è un Telegram bot self-hosted che scarica media da 1000+ siti e li invia direttamente ai DM dell'utente.

- **Versione**: 1.2.0
- **License**: MIT
- **Upstream**: github.com/LightYagami28/BotLite-Downloader (cloned locally)
- **Tech**: Python 3.12+, Telethon, yt-dlp, gallery-dl, aiohttp, SQLite
- **Deploy**: Docker (recommended) or manual systemd service

---

## Stack Tecnologico

| Componente | Tech | Motivo |
|------------|------|--------|
| **Telegram client** | Telethon | Client API for user-level bot interaction |
| **Download engine** | yt-dlp + gallery-dl | yt-dlp for videos/audio; gallery-dl fallback for carousels |
| **Web server** | aiohttp | Lightweight async web server for dashboard |
| **Database** | SQLite | Ban list + download statistics |
| **Container** | Docker + Alpine | Lightweight, secure, production-ready |
| **Signals** | systemd/Docker | Graceful shutdown handling |

---

## Struttura del progetto

```
Bot Lite Downloader/
├── botlite/                    # Main package
│   ├── __init__.py             # Package root, VERSION constant
│   ├── __main__.py             # Entry point: python -m botlite
│   ├── app.py                  # Bootstrap: wires all modules, starts bot
│   ├── client.py               # Telethon singleton + shared runtime state
│   ├── config.py               # Env var + .env loader
│   ├── db.py                   # SQLite: ban list, download stats
│   ├── downloader/
│   │   ├── __init__.py         # Public download() API
│   │   ├── ytdlp.py            # yt-dlp engine implementation
│   │   ├── gallery.py          # gallery-dl fallback engine
│   │   └── cookies.py          # Cookie file resolver (auth for private content)
│   ├── handlers/
│   │   ├── __init__.py         # Registers all handlers
│   │   ├── commands.py         # /start /help /status /stats /ban /unban
│   │   └── url.py              # URL detection + upload pipeline
│   ├── utils/
│   │   ├── format.py           # fmt_size, fmt_dur, build_caption
│   │   └── system.py           # free_disk, cleanup_old_temps, setup_signals
│   └── webapp/
│       ├── __init__.py         # start_webapp / stop_webapp
│       ├── auth.py             # Telegram initData HMAC validation
│       ├── server.py           # aiohttp routes: /api/status /api/stats /api/ban
│       └── static/
│           └── index.html      # Dashboard SPA
├── run.py                      # Alternate entry point (legacy)
├── requirements.txt            # Python dependencies
├── .env.example                # Template for config vars
├── Dockerfile                  # Alpine-based image
├── docker-compose.yml          # One-command deployment
├── LICENSE.md
├── SECURITY.md
└── README.md
```

---

## Setup & Dipendenze

### Prerequisiti
- **Python 3.12+** (or Docker)
- **ffmpeg** in PATH (for audio extraction)
- **Telegram account** + API credentials

### Option 1: Docker (Recommended)
```bash
cd "Bot Lite Downloader"
cp .env.example .env
# Edit .env: fill API_ID, API_HASH, BOT_TOKEN, SUDO_USERS
docker compose up -d
docker compose logs -f  # Watch startup
```

### Option 2: Manual (Venv)
```bash
cd "Bot Lite Downloader"
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env
python -m botlite
```

### Config Variables (Required)
| Var | Source | Note |
|-----|--------|------|
| `API_ID` | https://my.telegram.org/apps | User account API ID |
| `API_HASH` | https://my.telegram.org/apps | User account API hash |
| `BOT_TOKEN` | @BotFather (Telegram) | Bot token (not user token) |
| `SUDO_USERS` | @userinfobot (Telegram) | Comma-separated user IDs with admin access |

### Optional Config
- `MAX_FILE_SIZE`: Default 2GB (Telegram hard limit)
- `MAX_CONCURRENT_DOWNLOADS`: Default 3
- `MIN_FREE_DISK`: Default 500MB
- `USER_COOLDOWN`: Seconds between requests per user (0 = disabled)
- `WEBAPP_PUBLIC_URL`: HTTPS URL for dashboard (enables WebApp feature)

---

## Convenzioni & Patterns

### Module Organization
- **`downloader/`**: Pure download engines. No Telegram dependencies. Testable.
- **`handlers/`**: Telegram event handlers. Calls `downloader.download()`.
- **`webapp/`**: Separate aiohttp server. Auth via Telegram `initData` HMAC.
- **`utils/`**: No business logic. Only formatting and system utilities.

### Error Handling
- **Network errors**: Graceful retries in yt-dlp (built-in). Gallery-dl as fallback.
- **Disk full**: Check `system.free_disk()` before download. Reject if below `MIN_FREE_DISK`.
- **Per-user cooldown**: Enforced in `handlers/url.py` before calling downloader.
- **Ban list**: Check `db.is_banned()` in every handler.

### Logging
TBD (check for logging setup in `app.py` or `config.py`). If none exists, consider adding structured logging.

### Database
SQLite is embedded. No migrations framework — schema is created on-demand in `db.py`.

---

## Decisioni Architetturali

### 1. Dual Download Engine (yt-dlp + gallery-dl)
**Decisione**: yt-dlp for videos/audio; gallery-dl as fallback for photo carousels.

**Motivo**: 
- yt-dlp covers 90% of use cases (YouTube, TikTok, etc.)
- gallery-dl excels at Instagram carousels and similar
- Fallback strategy increases reliability

**When to change**: If one engine becomes unmaintained or incompatible with Telegram API.

### 2. Embedded SQLite (not PostgreSQL)
**Decisione**: SQLite for ban list and statistics.

**Motivo**:
- Self-hosted bot. No external DB infrastructure needed.
- Small dataset (ban list, counters). SQLite is sufficient.
- Easier deployment (no DB container).

**When to migrate**: If scaling to thousands of concurrent users or multiple bot instances.

### 3. Separate aiohttp WebApp (not integrated in bot)
**Decisione**: Dashboard runs in a separate aiohttp process.

**Motivo**:
- Bot core stays lightweight and responsive
- Dashboard can be disabled (no `WEBAPP_PUBLIC_URL`)
- Easier to test and maintain separately

**When to merge**: If dashboard becomes mission-critical and you want a single process.

### 4. Graceful Shutdown with systemd/Docker Signals
**Decisione**: Handle `SIGTERM` cleanly. Complete active downloads before exiting.

**Motivo**:
- Prevents corrupted partial files
- Safe for rolling deployments
- Docker/systemd expect signal handlers

**Never skip**: This is why `setup_signals()` exists.

---

## WebApp Dashboard (Optional)

If `WEBAPP_PUBLIC_URL` is set:

- Bot adds a **📊 Open Dashboard** button to all command replies
- Telegram opens the dashboard in full-screen WebApp
- Authentication: Telegram `initData` HMAC-SHA256 validation
- Routes:
  - `GET /api/status` — Bot uptime, active downloads, free disk
  - `GET /api/stats` — Success/fail counts (SUDO_USERS only)
  - `POST /api/ban` — Ban/unban users (SUDO_USERS only)

### HTTPS Requirement
Telegram WebApps only work over HTTPS. Options:
- **Cloudflare Tunnel** (zero-config, free): `cloudflared tunnel --url http://localhost:8080`
- **nginx + Let's Encrypt**: `certbot --nginx -d yourdomain.com`

---

## Cookie Setup (Optional)

For age-restricted or private content, drop Netscape-format cookie files:

```
cookiesyoutube.txt
cookiesinstagram.txt
cookiestiktok.txt
cookiestwitter.txt
```

These are gitignored (security). Export via [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/).

---

## Debugging & Monitoring

### View Logs
```bash
# Docker
docker compose logs -f botlite

# Systemd
journalctl -u botlite -f

# Manual (stdout)
# Already printing to console
```

### Check Bot Status
Send `/status` in Telegram DM. Response shows:
- Uptime
- Active downloads
- Free disk space

### Database Inspection
```bash
sqlite3 media_bot.db
> .tables
> SELECT * FROM ban_list;
```

---

## Conocimientos para Claude

### Cuando edites el código:
1. **Downloader engines** (`downloader/*.py`) son independientes. Testables sin Telegram.
2. **Handlers** llaman a `downloader.download()`. No modifiques la signature sin actualizar todas las calls.
3. **WebApp auth** usa HMAC-SHA256. Si tocas `webapp/auth.py`, verifica que signature validation siga siendo correcto.
4. **Signals** en `utils/system.py` son críticos. No los remuevas sin entender el graceful shutdown.

### Best Practices para este proyecto:
- **Test downloads localmente** antes de cambiar `downloader/*.py`
- **No hardcodear secrets** en código. Usa `.env`.
- **Cookie files** no deben committirse. `.gitignore` las bloquea.
- **yt-dlp updates** pueden cambiar comportamiento. Prueba después de actualizar.

### Qué no hacer:
- No remuevas el manejo de señales (SIGTERM)
- No simplifiques el fallback engine — es crítico para reliability
- No stores secrets en git (API keys, tokens, cookies)

---

## Recursos

- **Original Repo**: github.com/LightYagami28/BotLite-Downloader
- **yt-dlp docs**: github.com/yt-dlp/yt-dlp
- **gallery-dl docs**: github.com/mikf/gallery-dl
- **Telethon docs**: docs.telethon.dev
- **Telegram WebApp docs**: core.telegram.org/bots/webapps

---

**Last updated**: 2026-04-16
