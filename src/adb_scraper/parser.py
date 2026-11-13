import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

MANILA = ZoneInfo("Asia/Manila")

# Matches the ADB 3-letter (occasionally 2 or 4-letter, e.g. "REG", "PRC")
# country/region code that prefixes most notice titles, e.g.
# "LOAN E-059440-001 GEO: Kobuleti Bypass Project ..." -> "GEO"
_LOCATION_RE = re.compile(r"(?:^|\s)([A-Z]{2,4}):\s")

_DATE_FMT = "%d-%b-%Y"
_DEADLINE_FMT = "%d-%b-%Y %I:%M %p"


def extract_location(title: str) -> str | None:
    match = _LOCATION_RE.search(title)
    return match.group(1) if match else None


def parse_published_date(raw: str) -> str | None:
    """Returns an ISO date string, or None if unparsable."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, _DATE_FMT).date().isoformat()
    except ValueError:
        return None


def parse_deadline(raw: str) -> datetime | None:
    """Returns a timezone-aware (Asia/Manila) datetime, or None if unparsable."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, _DEADLINE_FMT)
    except ValueError:
        return None
    return dt.replace(tzinfo=MANILA)


def is_active(deadline_dt: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(MANILA)
    return deadline_dt > now


def compute_dedup_hash(title: str, expertise: str, published_raw: str) -> str:
    key = f"{title.strip()}|{expertise.strip()}|{published_raw.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
