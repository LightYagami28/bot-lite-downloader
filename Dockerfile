# python:3.14-alpine — 0 critical/high CVEs (Docker Scout 2026-03-25)
# ncurses CVE-2025-69720 not fixable on Debian trixie; Alpine avoids it entirely.
# To refresh: docker scout recommendations botlite-downloader:dev
FROM python:3.14-alpine@sha256:faee120f7885a06fcc9677922331391fa690d911c020abb9e8025ff3d908e510

# System deps: ffmpeg for HLS muxing; upgrade zlib to fix CVE-2026-22184
RUN apk add --no-cache ffmpeg \
    && apk upgrade --no-cache zlib

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore --upgrade pip \
    && pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY bot.py config.py ./

# Create non-root user and hand ownership over
RUN adduser -D -H -s /sbin/nologin botlite \
    && mkdir -p /data \
    && chown -R botlite:botlite /app /data

USER botlite

# Data directory for session file, DB and logs
VOLUME ["/data"]

ENV DB_FILE=/data/media_bot.db

CMD ["python", "bot.py"]
