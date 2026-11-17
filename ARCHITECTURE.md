# Architecture

Bot Lite Downloader is a self-hosted Telegram bot with a web dashboard. The application code lives in `botlite/`; automated tests are under `tests/`. Its Python package and supported runtime are declared in `pyproject.toml`.

## Runtime boundaries

The bot connects to Telegram and delegates downloads to the configured integrations. The dashboard and bot share the application configuration. Deployment packaging is described by the repository's Docker configuration; no hosted service is provided by this repository.

## Sensitive data

Telegram session material and browser cookies are credentials. Keep them in local environment/configuration storage and out of commits, logs, and issue attachments. For commands and supported configuration, follow the [README](README.md) and the code's current configuration definitions.