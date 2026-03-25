# python:3.14-alpine — 0 critical/high CVEs (Docker Scout 2026-03-25)
# Debian trixie has 87 CVEs (incl. ncurses 9.8 unfixable); Alpine avoids them entirely.
# To refresh digest: docker scout recommendations botlite-downloader:dev
FROM python:3.14-alpine@sha256:faee120f7885a06fcc9677922331391fa690d911c020abb9e8025ff3d908e510

# System deps + full package upgrade to clear all fixable CVEs
RUN apk add --no-cache ffmpeg \
    && apk upgrade --no-cache

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore --upgrade pip \
    && pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY botlite/ ./botlite/
COPY run.py .

# Create non-root user and hand ownership over
RUN adduser -D -H -s /sbin/nologin botlite \
    && mkdir -p /data \
    && chown -R botlite:botlite /app /data

USER botlite

# Data directory for session file, DB and logs
VOLUME ["/data"]

ENV DB_FILE=/data/media_bot.db

CMD ["python", "-m", "botlite"]
