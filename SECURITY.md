# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security fixes.

| Version | Supported |
| --- | --- |
| latest (`main`) | ✅ |
| older commits | ❌ |

---

## Reporting a Vulnerability

If you discover a security vulnerability, **please do not open a public GitHub issue.**

Report it privately via Telegram: **[@linuxuser825](https://t.me/LinuxBotsNews)**

Please include:

- A clear description of the vulnerability
- Steps to reproduce (or a proof-of-concept)
- Potential impact

You can expect an acknowledgement within **48 hours** and a patch within **7 days** for confirmed issues.

---

## Security Notes for Self-Hosters

- **Never commit `.env` or `cookies*.txt`** — both are excluded by `.gitignore` by default
- **Keep dependencies up to date** — Dependabot is configured to open PRs automatically
- **Run as a non-root user** — especially important in Docker; the bot does not require elevated privileges
- **Restrict file system access** — mount only the volumes the bot needs (`/data` for DB/session)
- **Use a dedicated bot token** — do not reuse tokens across projects
