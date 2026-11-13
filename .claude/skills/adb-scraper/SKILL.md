---
name: adb-scraper
description: Map and run-commands for the ADB CSRN NGO-notice scraper (src/adb_scraper/ — Playwright + SQLite + OpenAI relevance scoring + JSON export, Dockerized). Load this instead of re-reading the source tree for any task that runs the scraper, tunes a guardrail env var, edits classify.py keywords, changes the AI prompt/model, touches the notices schema, or works on the Dockerfile/docker-compose.
---

# ADB scraper — fast-context map

Read this file instead of opening every source file cold. It is the whole
architecture in one page; only open a specific file once you know which one
you need to change.

## Pipeline (in execution order)

```
main.py          CLI args, logging, --no-ai override
  -> scraper.py   scrape_once(): drives the browser, owns the per-row pipeline
       -> browser.py    Playwright DOM actions (goto, checkbox, extract rows, next page)
       -> classify.py   is_included() / is_excluded() — pure keyword regex, free
       -> parser.py     deadline/date parsing, location code, dedup hash
       -> db.py         notice_exists() dedup check, upsert_notice(), fetch_all_notices()
       -> ai_context.py get_ai_context() — OpenAI call, best-effort, see below
  -> json_export.py export_notices_json() — dumps the whole table to JSON after the run
retry.py          with_retry() decorator used by both browser.py calls and ai_context.py
config.py         every tunable, all read from env vars with safe defaults — see table below
__init__.py       auto-loads repo-root .env into os.environ (setdefault only) before config.py reads it
```

Per-row decision order in `scraper._process_row` (this order is deliberate,
don't reorder without checking why): keyword include -> keyword exclude ->
deadline active -> **dedup check** -> OpenAI call -> insert. The dedup check
happens *before* the OpenAI call specifically so re-running the scraper over
a listing you've already scraped never spends a token.

## Guardrails — all in config.py, all env-driven

| Env var | Guards | Default |
|---|---|---|
| `ADB_SCRAPER_RETRY_MAX_ATTEMPTS` / `ADB_SCRAPER_RETRY_BASE_DELAY_SECONDS` | browser step retries (free, generous) | 4 / 2s backoff |
| `ADB_SCRAPER_PAGE_NAV_TIMEOUT_MS` / `ADB_SCRAPER_PAGE_WAIT_TIMEOUT_MS` | Playwright navigation/action timeouts | 30000 / 15000 |
| `ADB_SCRAPER_MAX_PAGES` | pagination runaway | 50 |
| `ADB_SCRAPER_ENABLE_AI_CONTEXT` (or CLI `--no-ai`) | kill switch for the whole AI step | true |
| `ADB_SCRAPER_AI_TIMEOUT_SECONDS` | one OpenAI call hanging the run | 20s |
| `ADB_SCRAPER_AI_MAX_RETRY_ATTEMPTS` / `ADB_SCRAPER_AI_RETRY_BASE_DELAY_SECONDS` | AI retries — kept small because retries cost tokens, unlike browser retries | 2 / 2s backoff |
| `ADB_SCRAPER_AI_MAX_OUTPUT_TOKENS` / `ADB_SCRAPER_AI_MAX_INPUT_CHARS` | per-call token/cost bound | 200 / 1500 |
| `ADB_SCRAPER_AI_MAX_CALLS_PER_RUN` | hard cap on total spend per run, independent of how many new notices show up | 100 |

`ai_context.get_ai_context()` never raises — it returns `None` on any
failure, missing key, disabled flag, or exhausted budget, and the caller
stores the notice with `ai_relevance`/`ai_summary`/`ai_model` as `NULL`. This
is the one invariant to preserve when touching that module: the AI step must
never be able to fail the run or block a notice from being stored.

## Common tasks

- **Add/remove an NGO-relevance keyword** -> `classify.py`, `INCLUDE_KEYWORDS`
  or `EXCLUDE_KEYWORDS`. Pure regex, no AI involved, free to iterate on.
- **Change the AI model or prompt** -> `ai_context.py`, `_SYSTEM_PROMPT` and
  `config.OPENAI_MODEL` (env `ADB_SCRAPER_OPENAI_MODEL`, default
  `gpt-4o-mini`). Keep the reply-format instruction ("ONLY compact JSON") —
  `_call_openai` does a bare `json.loads` on the response.
- **Add a stored field** -> add the column to `db._MIGRATIONS` (not `SCHEMA`
  directly, so existing databases upgrade in place via `ALTER TABLE`), wire
  it through `scraper._process_row`'s `notice` dict and `db.upsert_notice`'s
  INSERT.
- **Change where output goes** -> `--db-path` / `--log-dir` / `--json-path`
  CLI flags, or `ADB_SCRAPER_DB_PATH` / `ADB_SCRAPER_LOG_DIR` /
  `ADB_SCRAPER_JSON_PATH` env vars (`config.py`). Docker sets these to
  `/app/data/...` / `/app/logs`; compose bind-mounts `./data` and `./logs`.
- **Run it** — bare metal (no Docker needed): `python -m venv .venv`,
  `pip install -r requirements.txt`, `pip install -e . --no-deps`,
  `playwright install chromium`, then `adb-scraper` (add `--headed` to watch
  the browser, `--no-ai` to skip OpenAI). Docker:
  `docker compose run --rm scraper` after `cp .env.example .env` and filling
  in `OPENAI_API_KEY` (leave blank for keyword-only mode). Either path reads
  the same `.env`.
- **Debug a selector/DOM change on the ADB site** -> `browser.py` only; it's
  the single file that touches page DOM (JS snippets `_FIND_CHECKBOX_JS` /
  `_EXTRACT_ROWS_JS`, plus `ensure_checked`/`extract_rows`/`click_next_page`).

## Outputs

- `data/adb_ngo_notices.db` — SQLite, table `notices`, the durable record.
- `data/notices.json` — full-table JSON array, rewritten atomically every run.
- `logs/run_<UTC timestamp>.log` — one file per run.
