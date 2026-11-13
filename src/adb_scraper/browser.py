import logging
import time

from . import config

logger = logging.getLogger(__name__)

_FIND_CHECKBOX_JS = """
(labelPrefix) => {
  const spans = Array.from(document.querySelectorAll('span'));
  const match = spans.find(
    el => el.children.length === 0 && el.textContent.trim().startsWith(labelPrefix)
  );
  if (!match) return null;
  let el = match;
  while (el && el.tagName !== 'BODY') {
    const cb = el.querySelector ? el.querySelector('input[type=checkbox]') : null;
    if (cb) return cb.id;
    el = el.parentElement;
  }
  return null;
}
"""

_EXTRACT_ROWS_JS = """
() => {
  const tables = Array.from(document.querySelectorAll('table'));
  const table = tables.find(t => t.id && t.id.endsWith('atResults:Content'));
  if (!table) return [];
  const rows = Array.from(table.querySelectorAll('tbody > tr'));
  return rows.map(tr => {
    const tds = Array.from(tr.querySelectorAll(':scope > td'));
    if (tds.length < 6) return null;
    const link = tds[0].querySelector('a');
    return {
      title: tds[0].textContent.trim(),
      href: link ? link.href : null,
      expertise: tds[1].textContent.trim(),
      consultantType: tds[2].textContent.trim(),
      engagementMonths: tds[3].textContent.trim(),
      published: tds[4].textContent.trim(),
      deadline: tds[5].textContent.trim(),
    };
  }).filter(Boolean);
}
"""


def find_checkbox_id(page, label_prefix: str) -> str | None:
    return page.evaluate(_FIND_CHECKBOX_JS, label_prefix)


def ensure_section_expanded(page, section_label: str) -> None:
    """Facet sections like 'Sector' are collapsed by default; 'Consultant Type'
    is expanded by default. No-op if already expanded or not found."""
    try:
        locator = page.get_by_text(section_label, exact=True)
        if locator.count() > 0:
            locator.first.click()
            time.sleep(1)
    except Exception as exc:  # noqa: BLE001 - best-effort UI nudge, not fatal
        logger.debug("ensure_section_expanded(%s) no-op: %s", section_label, exc)


def ensure_checked(page, label_prefix: str, section_label: str | None = None) -> bool:
    """Finds the checkbox whose label text starts with label_prefix and clicks
    it if not already checked. Returns True if the checkbox was found (checked
    or already-checked), False if it could not be located at all."""
    cb_id = find_checkbox_id(page, label_prefix)
    if cb_id is None and section_label is not None:
        ensure_section_expanded(page, section_label)
        cb_id = find_checkbox_id(page, label_prefix)
    if cb_id is None:
        logger.warning("Could not find checkbox for label %r", label_prefix)
        return False

    locator = page.locator(f"#{cb_id}")
    if locator.is_checked():
        return True

    locator.click()
    page.wait_for_load_state("networkidle", timeout=config.PAGE_WAIT_TIMEOUT_MS)
    time.sleep(config.ACTION_SETTLE_SECONDS)
    return True


def extract_rows(page) -> list[dict]:
    return page.evaluate(_EXTRACT_ROWS_JS)


def click_next_page(page) -> bool:
    """Clicks the 'Next 25' pagination control if present. Returns False (no
    exception) once the control is gone, which signals the last page."""
    locator = page.get_by_text("Next 25", exact=True)
    if locator.count() == 0:
        return False

    locator.first.click()
    page.wait_for_load_state("networkidle", timeout=config.PAGE_WAIT_TIMEOUT_MS)
    time.sleep(config.ACTION_SETTLE_SECONDS)
    return True
