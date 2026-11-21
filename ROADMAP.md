# Roadmap

Stato al 2026-11-17.

The items below summarize candidates in [SPEC.md](SPEC.md) and priorities for maintenance. They are proposals without dates or delivery commitments; confirm priorities before implementation.

## Obiettivi prioritari

1. **Codacy Grade A e Qualità del Codice**: mantenimento di 0 issue e rispetto delle convenzioni docstring D204 / D401 / CCN nei moduli `botlite/` e `tests/`.
2. **Hardening Telegram WebApp**: validazione continua dei dati di inizializzazione con finestra anti-replay HMAC-SHA256 e parsing rigoroso dei parametri.
3. **Ottimizzazione streaming audio e voice**: transcodifica ffmpeg asincrona in pipeline con buffer di memoria limitato.
4. **Isolamento Docker e sessioni**: esecuzione rootless in container e rimozione di sessioni persistenti da ambienti non fidati.

## Current scope

The project is a self-hosted Telegram download bot with a dashboard. See [README](README.md) for the current installation and usage instructions.

## Proposals recorded in SPEC

- Strengthen release checks and retain a coverage threshold.
- Add integration coverage for Telegram transport behavior.
- Consider a persistent download queue and per-user quotas.
- Revisit Python 3.15 support when compatible `ntgcalls` wheels are available.
- Improve dashboard accessibility.

## Fuori ambito

- Supporto a gruppi Telegram aperti/non approvati (policy restrittiva con allowlist esplicita).

Older test and coverage figures in `SPEC.md` are dated snapshots, not a claim about current CI. No milestones or delivery dates are committed here.

## Verifica 2026-11-21

Rianalisi senza soppressioni completata. Comandi: `.venv\Scripts\ruff.exe check .` e
`.venv\Scripts\ruff.exe format --check .` (esito 0), `.venv\Scripts\python.exe -m pytest`
(148 test superati), `.venv\Scripts\python.exe -m bandit -r botlite` (0 issue).
Rimossi i pragma di coverage e corretti i rami non sicuri nella validazione initData
e nella pubblicazione del brano audio; i test esistenti restano verdi.