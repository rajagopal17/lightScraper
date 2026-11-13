import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


CSRN_URL = "https://selfservice.adb.org/OA_HTML/OA.jsp?OAFunc=XXCRS_CSRN_HOME_PAGE"

# Consultant Type facet: NGOs apply as organizations, not individual consultants.
# This is the only site-side facet filter applied; NGO-relevance itself is
# decided in code (see classify.py) rather than via the site's Sector facet,
# since that facet doesn't reliably tag cross-cutting notices (e.g. "poverty",
# "community awareness") under the sectors you'd expect.
CONSULTANT_TYPE_LABELS = ["Firm"]

DEFAULT_DB_PATH = Path(
    os.environ.get("ADB_SCRAPER_DB_PATH", str(REPO_ROOT / "data" / "adb_ngo_notices.db"))
)
DEFAULT_LOG_DIR = Path(os.environ.get("ADB_SCRAPER_LOG_DIR", str(REPO_ROOT / "logs")))
DEFAULT_JSON_PATH = Path(
    os.environ.get("ADB_SCRAPER_JSON_PATH", str(REPO_ROOT / "data" / "notices.json"))
)

# Safety cap on pagination loops regardless of what the site reports.
MAX_PAGES = int(os.environ.get("ADB_SCRAPER_MAX_PAGES", "50"))

# --- Browser-step guardrails (retries / backoff / timeouts) ---
RETRY_MAX_ATTEMPTS = int(os.environ.get("ADB_SCRAPER_RETRY_MAX_ATTEMPTS", "4"))
RETRY_BASE_DELAY_SECONDS = float(os.environ.get("ADB_SCRAPER_RETRY_BASE_DELAY_SECONDS", "2"))

# Politeness delay after each filter click / pagination click, letting the
# page's AJAX partial-page-render settle before we read the table.
ACTION_SETTLE_SECONDS = float(os.environ.get("ADB_SCRAPER_ACTION_SETTLE_SECONDS", "1.5"))

PAGE_NAV_TIMEOUT_MS = int(os.environ.get("ADB_SCRAPER_PAGE_NAV_TIMEOUT_MS", "30000"))
PAGE_WAIT_TIMEOUT_MS = int(os.environ.get("ADB_SCRAPER_PAGE_WAIT_TIMEOUT_MS", "15000"))

# --- OpenAI context-enrichment guardrails ---
# All of these exist to bound token/dollar burn and keep a flaky/slow OpenAI
# call from ever stalling or failing the scrape run: AI enrichment is always
# best-effort and the pipeline must produce identical rows (minus the ai_*
# fields) when it is disabled or fails.
ENABLE_AI_CONTEXT = _bool_env("ADB_SCRAPER_ENABLE_AI_CONTEXT", True)
# Stripped defensively: a stray leading/trailing space or wrapping quote from
# pasting into a .env file silently turns into an invalid key otherwise, with
# OpenAI's 401 giving no hint that whitespace is the cause.
_raw_openai_key = os.environ.get("OPENAI_API_KEY")
OPENAI_API_KEY = _raw_openai_key.strip().strip("'\"") or None if _raw_openai_key else None
OPENAI_MODEL = os.environ.get("ADB_SCRAPER_OPENAI_MODEL", "gpt-4o-mini")

# Per-call network timeout; a hung call must not hang the whole run.
AI_TIMEOUT_SECONDS = float(os.environ.get("ADB_SCRAPER_AI_TIMEOUT_SECONDS", "20"))

# AI retries are deliberately much smaller than browser retries (which are
# free) because every retry here costs real tokens/money.
AI_MAX_RETRY_ATTEMPTS = int(os.environ.get("ADB_SCRAPER_AI_MAX_RETRY_ATTEMPTS", "2"))
AI_RETRY_BASE_DELAY_SECONDS = float(os.environ.get("ADB_SCRAPER_AI_RETRY_BASE_DELAY_SECONDS", "2"))

# Bounds on a single call's cost: cap output tokens and truncate the input
# text we send (title + expertise is normally well under this).
AI_MAX_OUTPUT_TOKENS = int(os.environ.get("ADB_SCRAPER_AI_MAX_OUTPUT_TOKENS", "200"))
AI_MAX_INPUT_CHARS = int(os.environ.get("ADB_SCRAPER_AI_MAX_INPUT_CHARS", "1500"))

# Hard cap on how many AI calls a single run may make at all, independent of
# how many new notices are found, so a scrape that turns up an unusually
# large batch of new notices cannot run away with API spend.
AI_MAX_CALLS_PER_RUN = int(os.environ.get("ADB_SCRAPER_AI_MAX_CALLS_PER_RUN", "100"))
