# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security fixes.

| Version | Supported |
| --- | --- |
| latest (`main`) | ✅ |
| older commits | ❌ |

---

## Reporting a Vulnerability

If you discover a security vulnerability, **please do not open a public GitHub
issue.**

Report it privately via Telegram:
**[@lightyagami28](https://t.me/LightYagami28)**

Please include:

- A clear description of the vulnerability
- Steps to reproduce (or a proof-of-concept)
- Potential impact

You can expect an acknowledgement within **48 hours** and a patch within **7
days** for confirmed issues.

---

## Security Notes for Self-Hosters

- **Keep `.env` and `cookies*.txt` out of commits** — both are excluded by
  `.gitignore`
- **Keep dependencies up to date** — Dependabot is configured to open PRs
  automatically
- **Run as a non-root user** — especially important in Docker; the bot does not
  require elevated privileges
- **Restrict file system access** — mount only the volumes the bot needs
  (`/data` for DB/session)
- **Use a dedicated bot token** — do not reuse tokens across projects

---

## Static Analysis Notes

### Assertions in tests

Bandit rule B101 flags the `assert` statements in `tests/test_*.py`. These are
pytest assertions, not runtime checks: the suite runs without `python -O`, so
the optimiser never removes them. Deleting them would delete the tests; no
suppressions are added. This finding is a documented false positive and the
test code stays unchanged.

### Docker Scout workflow token

Codacy rule `hard-coded-tokens` flags `id-token: write` in
`.github/workflows/docker-scout.yml`. That line is a GitHub Actions permission
scope, not a credential: it lets the attestation step fetch a short-lived OIDC
token (see https://docs.github.com/en/actions/concepts/security/oidc). No token
value is stored in the repository; Docker Hub and GHCR credentials come from
the `DOCKER_SCOUT_USER`, `DOCKER_SCOUT_PAT` and `GITHUB_TOKEN` secrets. This
finding is a false positive and the permission must stay for attestations.

### Kubernetes credentials

No Secret manifest with credential values is committed. Create the
`bot-lite-downloader-secrets` Secret from the local `.env` file or a secret
manager, as described in `k8s/README.md`. Credentials are mounted as read-only
files and read by the application directly.
