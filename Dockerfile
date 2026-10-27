# PyTgCalls/NTgCalls publish glibc wheels; Alpine/musl is not a supported base.
# Both stages use the same digest-pinned base so that Dependabot (docker ecosystem) bumps them together.

# ── Build stage: resolve the hash-locked dependencies into a virtualenv ──────
FROM python:3.14-slim-trixie@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.lock .

# Versions and hashes come from requirements.lock (uv pip compile --generate-hashes).
# pyaes, a pure-Python Telethon dependency, is the only package published as a source archive.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --require-hashes --only-binary :all: --no-binary pyaes \
        -r requirements.lock \
    && /opt/venv/bin/python -m pip uninstall --yes pip

# ── Runtime stage: no compiler, no pip, non-root ─────────────────────────────
FROM python:3.14-slim-trixie@sha256:f85c5697265c178cc6887276c55fe16cf3d14ca35c3df6a5eab3b360534a55d2 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

# The runtime never installs anything: drop pip and its bundled wheels together with their
# vendored libraries (urllib3, certifi, msgpack), which only add CVE noise to the image.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip/_bundled

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY botlite/ ./botlite/
COPY run.py .

RUN useradd --system --no-create-home --home-dir /app --shell /usr/sbin/nologin botlite \
    && mkdir -p /data \
    && chown -R botlite:botlite /app /data

USER botlite

EXPOSE 8080
VOLUME ["/data"]
ENV DB_FILE=/data/media_bot.db \
    WEBAPP_HOST=0.0.0.0

CMD ["python", "-m", "botlite"]
