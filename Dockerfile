# Playwright needs matching browser binaries + OS deps for whatever version
# is pinned in pyproject.toml; python:3.11-slim + `playwright install --with-deps`
# keeps that pairing explicit instead of depending on a separately-tagged base image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

WORKDIR /app

# playwright's CLI is itself a Node binary that needs libatomic1 just to
# start -- install it up front so `playwright install --with-deps` (which
# shells out to apt-get for the rest of Chromium's runtime deps) can run.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e . \
    && playwright install --with-deps chromium

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV ADB_SCRAPER_DB_PATH=/app/data/adb_ngo_notices.db \
    ADB_SCRAPER_LOG_DIR=/app/logs \
    ADB_SCRAPER_JSON_PATH=/app/data/notices.json

VOLUME ["/app/data", "/app/logs"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD []
