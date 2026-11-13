import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_hash TEXT NOT NULL UNIQUE,
    project_name TEXT NOT NULL,
    location TEXT,
    sector TEXT,
    expertise TEXT,
    consultant_type TEXT,
    engagement_period_months TEXT,
    published_date TEXT,
    deadline TEXT,
    related_url TEXT,
    scraped_at TEXT NOT NULL
);
"""

# Columns added after the initial release. Added via ALTER TABLE rather than
# baked into SCHEMA so a database created by an earlier version of this tool
# upgrades in place instead of needing to be deleted.
_MIGRATIONS = [
    "ALTER TABLE notices ADD COLUMN ai_relevance TEXT",
    "ALTER TABLE notices ADD COLUMN ai_summary TEXT",
    "ALTER TABLE notices ADD COLUMN ai_model TEXT",
]


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    for stmt in _MIGRATIONS:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists from a previous run
    conn.commit()


def notice_exists(conn: sqlite3.Connection, dedup_hash: str) -> bool:
    """Checked before any OpenAI call is made, so repeat runs never spend
    tokens re-enriching a notice we already stored."""
    cur = conn.execute("SELECT 1 FROM notices WHERE dedup_hash = ? LIMIT 1", (dedup_hash,))
    return cur.fetchone() is not None


def upsert_notice(conn: sqlite3.Connection, notice: dict) -> bool:
    """Inserts the notice if its dedup_hash is new. Returns True if inserted,
    False if it was already present (duplicate)."""
    try:
        conn.execute(
            """
            INSERT INTO notices (
                dedup_hash, project_name, location, sector, expertise,
                consultant_type, engagement_period_months, published_date,
                deadline, related_url, ai_relevance, ai_summary, ai_model,
                scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                notice["dedup_hash"],
                notice["project_name"],
                notice["location"],
                notice["sector"],
                notice["expertise"],
                notice["consultant_type"],
                notice["engagement_period_months"],
                notice["published_date"],
                notice["deadline"],
                notice["related_url"],
                notice.get("ai_relevance"),
                notice.get("ai_summary"),
                notice.get("ai_model"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def fetch_all_notices(conn: sqlite3.Connection) -> list[dict]:
    """Returns every stored notice as a plain dict, for JSON export."""
    previous_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT * FROM notices ORDER BY scraped_at ASC")
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.row_factory = previous_factory
