# PyTgCalls/NTgCalls publish glibc wheels; Alpine/musl is not a supported base.
FROM python:3.14-slim-trixie@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY botlite/ ./botlite/
COPY run.py .

RUN useradd --system --no-create-home --home-dir /app --shell /usr/sbin/nologin botlite \
    && mkdir -p /data \
    && chown -R botlite:botlite /app /data

USER botlite

EXPOSE 8080
VOLUME ["/data"]
ENV DB_FILE=/data/media_bot.db

CMD ["python", "-m", "botlite"]
