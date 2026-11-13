# lightScraper — ADB NGO project scraper

Scrapes ADB's Consultant Management System (`cms.adb.org`) for consulting
notices that NGOs (as firms) could realistically take up — education/training,
health and nutrition, social welfare, forestry/rural development, community
awareness, poverty, and (environmental and) social impact work — while
filtering out capital-intensive, construction-heavy notices. Each kept notice
is additionally scored for NGO relevance by an OpenAI model. Results are
stored in SQLite (no duplicates across repeated runs) and exported to a JSON
file on every run.

## What it actually scrapes

`cms.adb.org` itself is ADB's public portal; the live consulting-opportunities
listing (Consulting Services Recruitment Notices, CSRN) lives on
`selfservice.adb.org`. The scraper drives that listing with these filters:

- **Consultant Type**: Firm only (not Individual) — the only site-side filter
  applied. NGO-relevance is decided in code, not via the site's Sector facet:
  that facet doesn't reliably tag cross-cutting notices (e.g. "poverty",
  "community awareness") under the sectors you'd expect, so restricting by it
  would silently drop relevant notices filed under an unrelated sector.
- Every Firm notice is classified in `src/adb_scraper/classify.py` by keyword
  against its title + expertise text:
  - **Included** if it mentions education/training, health/nutrition, gender/
    child/social welfare, forestry/rural development, community awareness,
    poverty, or (environmental and) social impact work.
  - **Excluded** (even if included above) if it looks capital-intensive/
    construction-heavy (construction, civil works, bridge, road, dam, etc.).
- **Active** means the notice's deadline (Manila time) has not yet passed.
- Every notice that survives all three keyword checks and isn't already in
  the database is then sent to OpenAI (`src/adb_scraper/ai_context.py`) for a
  `high`/`medium`/`low` relevance label plus a one-line rationale. This step
  is strictly additive and best-effort: if it's disabled, unconfigured, or
  fails, the notice is still stored with the keyword-only fields.

## Setup (bare metal / no Docker)

Use this path if Docker isn't available or a build is still in progress.

```bash
python -m venv .venv
.venv\Scripts\activate          # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
pip install -e . --no-deps
playwright install chromium
copy .env.example .env   # fill in OPENAI_API_KEY, or leave blank for keyword-only
```

`requirements.txt` mirrors the dependency bounds in `pyproject.toml` (kept in
sync manually); `pip install -e . --no-deps` then just registers the
`adb-scraper` console script against the already-installed deps.

`.env` at the repo root is auto-loaded on import (`src/adb_scraper/__init__.py`,
no `python-dotenv` dependency needed) — it only fills in variables that
aren't already set in your shell, so a real exported env var always wins.
This is why Docker needs no equivalent step: `docker-compose.yml`'s
`env_file: .env` sets the same variables directly, and the loader is a no-op
since there's no `.env` file inside the image.

## Run once

```bash
adb-scraper
```

Writes/updates `data/adb_ngo_notices.db` (table `notices`), exports the full
table to `data/notices.json`, and logs to `logs/run_<timestamp>.log`. Each run
appends newly found notices and skips ones already seen (dedup on title +
expertise + published date), so repeated runs accumulate rather than
overwrite. Useful flags:

- `--headed` — watch the browser while debugging.
- `--db-path` / `--log-dir` / `--json-path` / `--max-pages` — override
  default paths/limits.
- `--no-ai` — skip OpenAI enrichment for this run only.

## Run in Docker

```bash
cp .env.example .env   # fill in OPENAI_API_KEY, or leave blank for keyword-only
docker compose build
docker compose run --rm scraper
```

`./data` and `./logs` on the host are bind-mounted into the container, so the
SQLite DB, `notices.json`, and log files persist across runs. This is a
one-shot job, not a long-running service — re-run it on a schedule from the
host (cron / Task Scheduler) or any external scheduler pointed at the image.

## Guardrails (what keeps this cheap and reliable)

All of these are environment variables (see `.env.example` for the full list
with defaults) — nothing requires a code change to tune:

| Concern | Knob | Default |
|---|---|---|
| Browser step retries | `ADB_SCRAPER_RETRY_MAX_ATTEMPTS` | 4, exponential backoff |
| Page navigation timeout | `ADB_SCRAPER_PAGE_NAV_TIMEOUT_MS` | 30s |
| Page action timeout | `ADB_SCRAPER_PAGE_WAIT_TIMEOUT_MS` | 15s |
| Pagination safety cap | `ADB_SCRAPER_MAX_PAGES` | 50 |
| AI enrichment on/off | `ADB_SCRAPER_ENABLE_AI_CONTEXT` / `--no-ai` | on |
| AI call timeout | `ADB_SCRAPER_AI_TIMEOUT_SECONDS` | 20s |
| AI retries (token-costly, kept small) | `ADB_SCRAPER_AI_MAX_RETRY_ATTEMPTS` | 2 |
| AI output size cap | `ADB_SCRAPER_AI_MAX_OUTPUT_TOKENS` | 200 tokens |
| AI input size cap | `ADB_SCRAPER_AI_MAX_INPUT_CHARS` | 1500 chars |
| AI calls per run (hard cap) | `ADB_SCRAPER_AI_MAX_CALLS_PER_RUN` | 100 |

Additional guardrails that aren't tunable because they're correctness, not
policy: duplicates are checked against SQLite *before* any OpenAI call (never
re-spend tokens re-enriching a notice already stored), and a failed/disabled
AI call always degrades to keyword-only output rather than failing the run.

## Schema (`notices` table)

`dedup_hash` (unique), `project_name`, `location` (raw ADB country code, e.g.
`BAN`, `REG`), `sector`, `expertise`, `consultant_type`,
`engagement_period_months`, `published_date`, `deadline`, `related_url`,
`ai_relevance`, `ai_summary`, `ai_model`, `scraped_at`.

Dedup key is a SHA256 hash of (project title + expertise + published date).
`data/notices.json` mirrors this table as a JSON array on every run.
