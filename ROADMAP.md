# Roadmap

Stato al 2026-11-17.

The items below summarize candidates in [SPEC.md](SPEC.md) and priorities for maintenance. They are proposals without dates or delivery commitments; confirm priorities before implementation.

## Obiettivi prioritari

1. **Codacy Grade A e Qualità del Codice**: mantenimento di 0 issue e rispetto delle convenzioni docstring D204 / D401 / CCN nei moduli `botlite/` e `tests/`.
2. **Hardening Telegram WebApp**: validazione continua dei dati di inizializzazione con finestra anti-replay HMAC-SHA256 e parsing rigoroso dei parametri.
3. **Ottimizzazione streaming audio e voice**: transcodifica ffmpeg asincrona in pipeline con buffer di memoria limitato.
4. **Isolamento Docker e sessioni**: esecuzione rootless in container e rimozione di sessioni persistenti da ambienti non fidati.

## Current scope & Proposals from SPEC

- Strengthen release checks and retain a coverage threshold.
- Add integration coverage for Telegram transport behavior.
- Consider a persistent download queue and per-user quotas.
- Revisit Python 3.15 support when compatible `ntgcalls` wheels are available.
- Improve dashboard accessibility.

## Fuori ambito

- Supporto a gruppi Telegram aperti/non approvati (policy restrittiva con allowlist esplicita).
