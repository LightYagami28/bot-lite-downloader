# Architecture

Bot Lite Downloader is a self-hosted Telegram bot with a web dashboard. The application code lives in `botlite/`; automated tests are under `tests/`. Its Python package and supported runtime are declared in `pyproject.toml`.

```text
                     +----------------------------------+
                     |         Telegram Client          |
                     |      (Telethon Events Loop)      |
                     +-----------------+----------------+
                                       |
                   +-------------------+-------------------+
                   v                                       v
+--------------------------------------+   +----------------------------------+
|           botlite.handlers           |   |           botlite.webapp         |
|  - access.py (Allowlist & Auth)      |   |  - server.py (aiohttp MiniApp)   |
|  - commands.py (Dispatcher comandi)  |   |  - auth.py (HMAC-SHA256 Verify)  |
|  - url.py (Download routing)         |   +----------------------------------+
+------------------+-------------------+
                   |
                   v
+--------------------------------------+
|          botlite.downloader          |
|  - ytdlp.py (Estrazione media)       |
|  - gallery.py (Scraper album)        |
|  - voice.py (Transcodifica audio)    |
+--------------------------------------+
```

| Modulo | Percorso | Ruolo |
| --- | --- | --- |
| Handlers | `botlite/handlers/` | Filtraggio accessi (`access.py`), elaborazione comandi `/start`, `/help` e intercettazione link media. |
| Downloader | `botlite/downloader/` | Motore di download via `yt-dlp`, gestione playlist, rotazione user-agent e normalizzazione audio. |
| WebApp | `botlite/webapp/` | Server aiohttp interno per Telegram MiniApp con autenticazione crittografica sicura. |
| Config & DB | `botlite/config.py`, `db.py` | Caricamento configurazioni `.env` tipizzate e persistenza metadati SQLite. |

## Runtime boundaries

The bot connects to Telegram and delegates downloads to the configured integrations. The dashboard and bot share the application configuration. Deployment packaging is described by the repository's Docker configuration; no hosted service is provided by this repository.

## Sensitive data

Telegram session material and browser cookies are credentials. Keep them in local environment/configuration storage and out of commits, logs, and issue attachments. For commands and supported configuration, follow the [README](README.md) and the code's current configuration definitions.
