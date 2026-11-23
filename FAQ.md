# Domande frequenti

## Quali formati e piattaforme sono supportati?

Il bot utilizza `yt-dlp` e scraper interni per scaricare video, tracce audio ed
estratti da centinaia di piattaforme compatibili.

## Quali sono i requisiti di sistema?

- Python 3.12, 3.13, 3.14 o 3.15. Per CI e immagine Docker è usato 3.14.
- `ffmpeg` installato e disponibile nel PATH di sistema (necessario per
  estrazione e transcodifica audio).

## Come si avviano i test?

```bash
python -m pytest tests/
```

## Come viene gestita la sicurezza nei gruppi?

Per impostazione predefinita, il bot ignora i messaggi provenienti dai gruppi a
meno che l'ID del gruppo non sia esplicitamente inserito nella variabile
`ALLOWED_GROUP_IDS`.
