---
titolo: Revisione finding Codacy
aggiornato: 2026-11-22
---

# Revisione finding Codacy — bot-lite-downloader

## Metodo

Rilevazione del 2026-11-22 tramite Codacy API v3:

- `POST .../issues/overview`
- `POST .../issues/search` con corpo
  `{"levels":["Error","High","Warning","Info"],"pageSize":100}`.

Gli endpoint sono sotto
`/api/v3/analysis/organizations/gh/LightYagami28/repositories/bot-lite-downloader`.
La paginazione della search è **cursor-based** (`?cursor=N`): il campo `page`
nel corpo viene ignorato
e restituisce sempre la prima pagina. Somma dei 13 cursor: 1244 issue, tutte
`belowThreshold`.

## Conteggi prima

| Livello | Totale |
| --- | --- |
| Error | 1 |
| High | 437 |
| Warning | 219 |
| Info | 587 |
| **Totale** | **1244** |

## Falsi positivi dimostrati — Error

| Pattern | N | File/riga | Evidenza |
| --- | --- | --- | --- |
| `Semgrep_codacy.yaml.security.hard-coded-tokens` | 1 | `.github/workflows/docker-scout.yml:28` | La riga segnalata è `id-token: write`, dentro il blocco `permissions:` del job. È la parola chiave GitHub Actions che concede il permesso OIDC; non contiene alcun valore di token. I soli segreti usati nel workflow sono riferimenti `${{ secrets.DOCKER_SCOUT_USER }}`, `${{ secrets.DOCKER_SCOUT_PAT }}` e `${{ secrets.GITHUB_TOKEN }}`. Nessuna credenziale letterale presente. |

## Falsi positivi dimostrati — High

| Pattern | N | Evidenza |
| --- | --- | --- |
| `Prospector_bandit` (B101) | 266 | Tutte le occorrenze sono in `tests/**` (es. `tests/test_app.py:39`, `tests/test_ytdlp.py:23`). Bandit segnala l'uso di `assert`; in codice di test l'assert è il meccanismo di verifica di pytest. I test non vengono eseguiti con bytecode ottimizzato (`python -O`), quindi la premessa del rule non si applica. |
| `Semgrep_python_assert_rule-assert-used` | 86 | Il messaggio afferma «assert in non-test code», ma le righe segnalate sono tutte in file `tests/test_*.py` (es. `tests/test_db.py:20`, `tests/test_voice.py:96`). La classificazione del file fatta dal rule è incoerente con il percorso. |
| `Oxlint_eslint_no-undef` | 12 | `document`/`window` sono globali del browser. `botlite/webapp/static/app.js` viene servito come `application/javascript` e caricato da `index.html:229` con `<script type="module" src="/app.js">`. L'analisi Oxlint non ha il globale browser configurato. |
| `Semgrep_yaml.semgrep.duplicate-id.duplicate-id` | 11 | `k8s/ingress.yaml` non contiene **alcun campo `id:`**. Le segnalazioni (righe 15-25) cadono sul blocco `rules[].http.paths[]`. Il rule sta interpretando chiavi ripetute di sequenze YAML come `id`. |
| `ESLint8_@lwc_lwc_no-restricted-browser-globals-during-ssr` | 7 | Rule specifico Lightning Web Components/SSR applicato a JavaScript browser vanilla. Non esiste codice LWC né rendering SSR nel repo. |
| `ESLint8_fp_no-nil` | 4 | `toast()`, `setText()`, `setBadge()` e `let toastTimer` in `app.js` sono helper void: non devono restituire un valore. La funzione `setBadge` termina con `wrapper.replaceChildren(badge)`. |
| `ESLint8_es-x_no-top-level-await` | 4 | `app.js:30,32,65,69` usano `await` di primo livello, sintassi valida perché lo script è caricato come modulo (`index.html:229`). |
| `ESLint8_flowtype_require-parameter-type` | 3 | Rule Flowtype applicato a JavaScript senza annotazioni Flow. |
| `ESLint8_n_no-unsupported-features_node-builtins` | 2 | `fetch` in `app.js` viene eseguito nel browser, non in Node.js; la versione `>=16` citata dal rule è irrilevante per il runtime effettivo. |
| `ESLint8_es-x_no-arrow-functions`, `ESLint8_es-x_no-default-parameters` | 2 | Rule ES5-only applicati a un modulo ES2022 caricato con `type="module"`. |

## Da verificare / correggere nel codice (lotti successivi)

| Pattern | N | Natura |
| --- | --- | --- |
| `Prospector_pyright` | 40 | Misto: import di dipendenze opzionali/dev non risolte nell'ambiente Codacy (`dotenv`, `pytest`, `pytgcalls`, `telethon`) e alcuni typecheck reali. Richiede verifica singola. |
| `PyLintPython3_C0103` | 83 | Nomi di funzioni test superiori a 30 caratteri: correggibile con rename, da valutare contro la leggibilità. |
| `Prospector_vulture` | 55 | Codice/import non usati: parte reale, parte artefatto dei mock dei test. |
| `PyLintPython3_W0212` | 49 | Accesso a membri protetti: quasi tutti in test, da valutare. |
| Altri pattern Warning/Info | 245 | Formattazione, docstring, lunghezza righe, complessità: correzioni meccaniche per lotti dedicati. |

Nessuna soppressione, ignored path, baseline o abbassamento di soglia è stato
introdotto.
