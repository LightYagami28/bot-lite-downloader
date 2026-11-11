# SPEC: BotLite Downloader

## Obiettivo

Il progetto è finito quando il bot Telegram self-hosted scarica in modo
affidabile i contenuti multimediali dai link pubblici (yt-dlp, con gallery-dl
come ripiego) e li rimanda alla chat che li ha richiesti, con dashboard WebApp
opzionale e voce opzionale, coverage 100%, SonarCloud A/A/A, zero avvisi in
lint, test e audit, e immagine Docker riproducibile.

## Stato attuale verificato

Letto dai file il 2026-11-11, ramo `main`. Versione del progetto 1.2.0, licenza
MIT, repo pubblico, derivato da BotLite (vedi README, «Origin & Credits»).

| Componente | Versione | File |
| --- | --- | --- |
| Python | immagine `python:3.14-slim-trixie` (digest fissato); `requires-python >=3.12`; CI su 3.14 | `Dockerfile`, `pyproject.toml`, `sonarqube-linux.yml` |
| Telethon | 1.45.0 | `requirements.txt` |
| yt-dlp | 2026.10.26 | `requirements.txt` |
| gallery-dl | 1.32.19 | `requirements.txt` |
| aiohttp | 3.14.5 | `requirements.txt` |
| py-tgcalls | 3.0.0 | `requirements.txt` |
| ntgcalls | 3.0.6 | `requirements.txt` |
| python-dotenv | 1.2.4 | `requirements.txt` |
| pytest / pytest-cov | 9.2.0 / 7.1.0 | `requirements-dev.txt` |
| ruff | 0.17.4 | `requirements-dev.txt` |
| pip-audit | 2.10.1 | `requirements-dev.txt` |

Le dipendenze sono bloccate con hash (`requirements.lock`,
`requirements-dev.lock`, `uv.lock`); la CI verifica che i lock siano allineati
ai file `requirements*.txt`. Dependabot: `pip`, `docker`, `github-actions`,
`uv`.

Moduli e test: `botlite/` (app, client, config, db, errors, voice, `handlers/`,
`downloader/`, `utils/`, `webapp/`), 20 file di test in `tests/`. `pytest` è
configurato con `filterwarnings = ["error"]`.

CI: `sonarqube-linux.yml` esegue installazione, controllo dei lock, `pytest -W
error::DeprecationWarning --cov=botlite`, `ruff check .`, regole di sicurezza
`ruff check botlite --select S`, `pip-audit -r requirements-dev.lock`, build
dell'immagine, scansione SonarQube (solo con `SONAR_TOKEN`). Esistono anche
`sonarqube-macos.yml`, `sonarqube-windows.yml` e `docker-scout.yml` (servono
segreti).

Incongruenze trovate:

- Il vecchio SPEC indicava ntgcalls 3.0.5 e ruff 0.17.3; i file dei requisiti
  hanno 3.0.6 e 0.17.4.
- `README.md` rimanda a `LICENSE.md` nel badge, il file nel repo è `LICENSE`.
- `CLAUDE.md` e `README.md` sono in lingue diverse (italiano e inglese); lo SPEC
  è la fonte di verità.
- Esito delle verifiche locali: vedi «Verifica eseguita» in fondo a «Come
  verificare».

## Architettura

```text
Telegram <-> client Telethon (botlite/client.py)
               |-- handlers/commands.py   /start /help /status /stats /ban /unban /play ...
               |-- handlers/url.py        rilevamento URL -> download -> upload
               |-- handlers/access.py     autorizzazioni (ban, gruppi, sudo)
               |-- downloader/            ytdlp.py, gallery.py (ripiego), cookies.py
               |-- voice.py               riproduzione nella chat vocale di gruppo
               |-- db.py                  SQLite
               `-- webapp/                server aiohttp + auth.py (HMAC di initData) + interfaccia statica
```

`botlite/app.py` collega i moduli e avvia il client; il punto d'ingresso è
`python -m botlite` (anche `run.py`). `config.py` legge le variabili d'ambiente
(e `.env`) e `validate()` interrompe l'avvio se le impostazioni mancano o non
sono valide.

Flusso di download:

1. Arriva un messaggio con un URL; si applicano i controlli di accesso (ban,
   gruppi ammessi, cooldown).
2. Si acquisisce uno slot dal limite globale di concorrenza e si controlla lo
   spazio libero su disco.
3. yt-dlp scarica in una cartella temporanea; se fallisce si prova gallery-dl.
4. Il file è confrontato con `MAX_FILE_SIZE`, caricato su Telegram e i file
   temporanei sono rimossi.
5. I contatori (`total_downloads`, `failed_downloads`) sono aggiornati.

Dati: file SQLite (`DB_FILE`, predefinito `media_bot.db`).

| Tabella | Colonne |
| --- | --- |
| `banned_users` | `user_id` (PK), `banned_at` |
| `stats` | `name` (PK), `value` |

Le sessioni Telegram (`*.session`) e i file dei cookie sono segreti e non vanno
mai committati.

Interfacce:

- Comandi utente: `/start`, `/help`, `/status`. Comandi admin (solo
  `SUDO_USERS`): `/stats`, `/ban <user_id>`, `/unban <user_id>`. Comandi voce
  nei gruppi ammessi: `/play`, `/pause`, `/resume`, `/voice_stop`.
- HTTP, solo se `WEBAPP_PUBLIC_URL` è impostato: `GET /`, `GET /app.js`, `GET
  /api/status`, `GET /api/me`, `GET /api/stats`, `POST /api/ban`, `POST
  /api/unban`. Le chiamate API richiedono `initData` valido e recente; ban e
  unban richiedono un utente in `SUDO_USERS`.
- Configurazione: variabili d'ambiente in `README.md` e `.env.example`. Valori
  predefiniti letti da `botlite/config.py`: `MAX_FILE_SIZE` 2 GiB,
  `MAX_CONCURRENT_DOWNLOADS` 3, `MIN_FREE_DISK` 500 MiB, `USER_COOLDOWN` 5 s,
  `VOICE_MAX_DURATION` 1800 s, `VOICE_MAX_FILE_SIZE` 100 MiB, `WEBAPP_HOST`
  `127.0.0.1`, `WEBAPP_PORT` 8080, `WEBAPP_INIT_DATA_MAX_AGE` 3600 s.

## Requisiti funzionali

1. Il bot rileva URL nelle chat private e, con `ALLOW_GROUPS` attivo, nei gruppi
   ammessi. Accettazione: `tests/test_url_handler.py` e `tests/test_access.py`
   passano.
2. Scarica video e audio con yt-dlp e le gallerie di immagini con gallery-dl
   come ripiego. Accettazione: `tests/test_ytdlp.py`, `test_ytdlp_audio.py`,
   `test_gallery.py`, `test_downloader.py` passano.
3. Cooldown per utente, tetto globale di download, limite di dimensione e
   controllo dello spazio libero. Accettazione: i test di `test_url_handler.py`
   e `test_config.py` coprono ciascun limite.
4. Elenco degli utenti bannati e contatori in SQLite. Accettazione:
   `tests/test_db.py` passa.
5. Comandi di amministrazione riservati a `SUDO_USERS`. Accettazione:
   `tests/test_commands.py` passa; un utente non in elenco non può usare
   `/stats`, `/ban`, `/unban`.
6. Dashboard WebApp autenticata con `initData` di Telegram. Accettazione:
   `tests/test_webapp_auth.py` e `test_webapp_server.py` passano; richieste
   senza `initData` valido o scadute sono rifiutate.
7. Voce opzionale nei gruppi in elenco. Accettazione: `tests/test_voice.py` e
   `test_voice_commands.py` passano.
8. Supporto dei cookie forniti dall'utente per i contenuti con restrizioni.
   Accettazione: `tests/test_cookies.py` passa.
9. Chiusura ordinata su `SIGTERM`. Accettazione: `tests/test_shutdown.py` passa.
10. Avvio rifiutato con configurazione mancante o non valida. Accettazione:
    `tests/test_config.py` passa.

## Requisiti non funzionali

- Sicurezza: le richieste WebApp sono validate lato server (HMAC di `initData`,
  età massima); la dashboard ascolta su loopback per impostazione predefinita;
  CSP rigorosa; gruppi e voce solo con elenchi espliciti; immagine con base
  fissata per digest, dipendenze con hash, nessun pip a runtime, utente non
  root; regole Ruff `S` (equivalenti a Bandit) e `pip-audit` in CI; nessun
  segreto nel repo (`.env.example` ha solo nomi). Segnalazioni: `SECURITY.md`.
- Prestazioni: concorrenza limitata da `MAX_CONCURRENT_DOWNLOADS`; nessuna coda
  persistente (limite noto).
- Accessibilità: la dashboard WebApp (`botlite/webapp/static`) rispetta WCAG 2.2
  AA (etichette, contrasto, tastiera, `lang`). Verifica: da confermare.
- Privacy/GDPR: il database contiene solo ID utente Telegram dei bannati e
  contatori; i file scaricati sono temporanei. Informativa per chi gestisce
  un'istanza pubblica: da definire.
- Qualità: coverage 100% (`--cov=botlite`, `botlite/__main__.py` escluso),
  SonarCloud A/A/A e hotspot A, zero avvisi in `ruff check .`, test e
  `pip-audit`, dipendenze all'ultima versione.

## Limiti noti

- Tetto di caricamento di 2 GB (limite di Telegram); nessuna coda persistente
  (un riavvio perde i download in corso).
- Il supporto dei siti dipende da yt-dlp e gallery-dl; i contenuti privati
  richiedono cookie forniti dall'utente.
- Istanza singola, solo SQLite.
- Python 3.15 non adottato finché ntgcalls non pubblica ruote compatibili (da
  riconfermare sulla versione corrente).

## Roadmap

1. Misurare lo stato: `ruff check .`, `pytest --cov`, `pip-audit`, e annotare lo
   scarto dal 100% di coverage.
2. Impostare una soglia minima nel comando di coverage (`--cov-fail-under=100`)
   dopo aver raggiunto il 100%.
3. Test di integrazione con trasporto Telegram simulato.
4. Coda di download persistente e quote per utente.
5. Passare a Python 3.15 quando ntgcalls pubblica ruote compatibili.
6. Verifica di accessibilità della dashboard.

## Fuori ambito

- Scaricare contenuti protetti da DRM o dietro autenticazione senza cookie
  dell'utente.
- Multi-istanza o database diversi da SQLite.
- Archiviazione permanente dei file scaricati.

## Decisioni aperte per il proprietario

- Soglia di coverage obbligatoria in CI (oggi non impostata).
- Introdurre una coda persistente e le quote per utente.
- Informativa privacy per le istanze pubbliche.
- Correggere il riferimento `LICENSE.md` nel badge del README (il file è
  `LICENSE`).

## Come verificare

```bash
python -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt   # su Windows: .venv\Scripts\python
.venv/bin/ruff check .
.venv/bin/ruff check botlite --select S
.venv/bin/python -m pytest -W error::DeprecationWarning --cov=botlite --cov-report=term-missing
.venv/bin/pip-audit -r requirements-dev.lock
docker build --tag botlite-downloader:ci .
```

Per usare i lock con hash: `pip install --require-hashes -r
requirements-dev.lock`.

### Verifica eseguita

Il 2026-11-11 con Python 3.14.10 su Windows, in un ambiente nuovo da
`requirements-dev.txt`: `ruff check .` riporta «All checks passed!»; `pytest -W
error::DeprecationWarning --cov=botlite` riporta 144 test passati e coverage del
100% (1010 istruzioni, 0 non coperte). `pip-audit` e `docker build` non sono
stati eseguiti in questa revisione (da confermare in CI).
