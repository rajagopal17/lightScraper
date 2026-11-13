import logging
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from . import ai_context, browser, classify, config, db, json_export, parser
from .retry import with_retry

logger = logging.getLogger(__name__)

_goto = with_retry(
    lambda page: page.goto(config.CSRN_URL, wait_until="networkidle", timeout=config.PAGE_NAV_TIMEOUT_MS)
)
_ensure_checked = with_retry(browser.ensure_checked)
_extract_rows = with_retry(browser.extract_rows)
_click_next_page = with_retry(browser.click_next_page)


def _process_row(conn, row: dict) -> str:
    title = row["title"]
    expertise = row["expertise"]

    if not classify.is_included(title, expertise):
        return "not_relevant"

    if classify.is_excluded(title, expertise):
        return "excluded"

    deadline_dt = parser.parse_deadline(row["deadline"])
    if deadline_dt is not None and not parser.is_active(deadline_dt):
        return "inactive"

    dedup_hash = parser.compute_dedup_hash(title, expertise, row["published"])

    # Guardrail: check for a duplicate *before* touching OpenAI, so repeat
    # runs over the same listing never spend a token on a notice we already
    # have stored.
    if db.notice_exists(conn, dedup_hash):
        return "duplicate"

    ai = ai_context.get_ai_context(title, expertise)

    notice = {
        "dedup_hash": dedup_hash,
        "project_name": title,
        "location": parser.extract_location(title),
        "sector": None,  # not exposed per-row by the site; only as a filter facet
        "expertise": expertise,
        "consultant_type": row["consultantType"],
        "engagement_period_months": row["engagementMonths"],
        "published_date": parser.parse_published_date(row["published"]),
        "deadline": deadline_dt.isoformat() if deadline_dt else row["deadline"],
        "related_url": row["href"],
        "ai_relevance": ai.relevance if ai else None,
        "ai_summary": ai.summary if ai else None,
        "ai_model": ai.model if ai else None,
    }
    inserted = db.upsert_notice(conn, notice)
    return "inserted" if inserted else "duplicate"


def scrape_once(
    db_path: Path,
    headless: bool = True,
    max_pages: int = config.MAX_PAGES,
    json_path: Optional[Path] = None,
) -> dict:
    conn = db.get_connection(db_path)
    db.init_db(conn)
    ai_context.reset_call_budget()

    counts = {
        "inserted": 0,
        "duplicate": 0,
        "excluded": 0,
        "inactive": 0,
        "not_relevant": 0,
        "pages": 0,
        "json_records": 0,
    }

    try:
        with sync_playwright() as p:
            pw_browser = p.chromium.launch(headless=headless)
            page = pw_browser.new_page()
            page.set_default_timeout(config.PAGE_WAIT_TIMEOUT_MS)
            try:
                _goto(page)

                for label in config.CONSULTANT_TYPE_LABELS:
                    _ensure_checked(page, label)

                page_num = 1
                while True:
                    rows = _extract_rows(page)
                    for row in rows:
                        outcome = _process_row(conn, row)
                        counts[outcome] += 1
                    counts["pages"] = page_num

                    if page_num >= max_pages:
                        logger.warning(
                            "Hit max_pages safety cap (%d); stopping pagination", max_pages
                        )
                        break

                    has_next = _click_next_page(page)
                    if not has_next:
                        break
                    page_num += 1
            finally:
                pw_browser.close()
    finally:
        if json_path is not None:
            counts["json_records"] = json_export.export_notices_json(conn, json_path)
        conn.close()

    logger.info(
        "Run complete: inserted=%d duplicate=%d excluded=%d inactive=%d not_relevant=%d "
        "pages=%d json_records=%d",
        counts["inserted"],
        counts["duplicate"],
        counts["excluded"],
        counts["inactive"],
        counts["not_relevant"],
        counts["pages"],
        counts["json_records"],
    )
    return counts
