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

Bandit rule B101 (reported as `Prospector_bandit`) flags 14 `assert` statements
in the pytest suite: `tests/test_config.py` (lines 77, 78, 85, 86, 87, 88, 95)
and `tests/test_gallery.py` (lines 114, 115, 116, 117, 126, 133, 143).

These are **pytest assertions, not runtime checks**. The suite is run by pytest
without `python -O`, so the optimiser never removes them; `assert` is the
assertion mechanism pytest itself uses. Rewriting them as `if ...: raise` would
only restate the same checks less readably, and deleting them would delete the
tests. No suppressions are added and the assertions stay unchanged. This is a
documented false positive limited to test code.

### Credential-looking log messages

A logger call that contains a word such as "secret", "token" or "password"
together with a `%s` placeholder is flagged by
`python-logger-credential-disclosure`. The message in `botlite/config.py` was
reworded to describe the failing operation without credential-like wording.
It logs only the credential **name** and the `OSError` from reading the mounted
file: never the credential value. No logging rule was disabled.

### Docker Scout workflow token

Codacy rule `hard-coded-tokens` flags `id-token: write` in
`.github/workflows/docker-scout.yml`. That line is a GitHub Actions permission
scope, not a credential: it lets the attestation step fetch a short-lived OIDC
token (see <https://docs.github.com/en/actions/concepts/security/oidc>). No token
value is stored in the repository; Docker Hub and GHCR credentials come from
the `DOCKER_SCOUT_USER`, `DOCKER_SCOUT_PAT` and `GITHUB_TOKEN` secrets. This
finding is a false positive and the permission must stay for attestations.

### Kubernetes credentials

No Secret manifest with credential values is committed. Create the
`bot-lite-downloader-secrets` Secret from the local `.env` file or a secret
manager, as described in `k8s/README.md`. Credentials are mounted as read-only
files and read by the application directly.

### Stato analisi statica (2026-11-21)

Prima degli interventi Codacy riportava 806 finding:
1 Error, 218 Warning, 587 Info. Non sono state aggiunte
soppressioni ne' rimossi assert dei test.

- `hard-coded-tokens` (1 Error): il falso positivo OIDC e'
  descritto sopra. `id-token: write` e' un permesso, non un
  valore: nessun secret puo' sostituirlo.
- `Prospector_pydocstyle` (322): regole D213/D413/D406,
  convenzioni di formattazione delle docstring.
- `PyLintPython3_C0103` (83): nomi di funzioni di test
  piu' lunghi di 30 caratteri.
- `Prospector_vulture` (54): simboli usati solo dalle
  fixture pytest, non codice morto di produzione.
- `PyLintPython3_W0212` (49): i test ispezionano membri
  protetti per verificare lo stato interno.
- `markdownlint_MD013` (25): righe di documentazione
  oltre 80 caratteri.
- I restanti finding sono regole di stile JS/Python
  (`one-var`, `no-magic-numbers`, `sort-keys`) e
  complessita' Lizard sotto soglia: richiedono una
  riscrittura di massa, non correzioni di sicurezza.
