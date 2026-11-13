"""Loads a repo-root .env file into the process environment, if present, so
bare-metal runs (`adb-scraper`) behave the same as Docker's `env_file: .env`
without needing python-dotenv as a dependency. Real environment variables
always win -- this only fills in what isn't already set, and never raises,
since a missing or malformed .env must not block import.

Runs once, here, because importing any submodule (config, scraper, ...)
first runs this package's __init__.py, which must happen before config.py
reads os.environ at its own module level.
"""

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _REPO_ROOT / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv(_ENV_PATH)
