#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$(dirname "${ADB_SCRAPER_DB_PATH:-/app/data/adb_ngo_notices.db}")"
mkdir -p "${ADB_SCRAPER_LOG_DIR:-/app/logs}"

exec adb-scraper "$@"
