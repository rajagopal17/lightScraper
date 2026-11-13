import json
import logging
from pathlib import Path

from . import db

logger = logging.getLogger(__name__)


def export_notices_json(conn, json_path: Path) -> int:
    """Writes the full notices table to json_path as a JSON array, atomically
    (write to a temp file, then replace). Best-effort: a failure here is
    logged and returns 0 rather than failing the whole scrape run, since the
    SQLite DB is already the durable record at that point."""
    try:
        records = db.fetch_all_notices(conn)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = json_path.with_suffix(json_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        tmp_path.replace(json_path)
        return len(records)
    except Exception as exc:  # noqa: BLE001 - JSON export must not crash the run
        logger.warning("Failed to export notices JSON to %s: %s", json_path, exc)
        return 0
