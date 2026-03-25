FROM python:3.12-slim

# System deps: ffmpeg for HLS muxing, gallery-dl binary
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py config.py ./

# Data directory for session file, DB and logs
VOLUME ["/data"]

ENV DB_FILE=/data/media_bot.db

# Cookies are mounted at runtime: -v /host/cookies:/app/cookies
# and referenced as cookiesyoutube.txt etc. in /app

CMD ["python", "bot.py"]
