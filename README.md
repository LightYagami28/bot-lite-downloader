# Media Downloader Bot — Lite

A minimal, open-source Telegram bot that downloads media from hundreds of websites
and sends the files directly to you in chat. Built on **yt-dlp** and **gallery-dl**.

---

## Features

- **Video, audio & photo** downloads via yt-dlp (YouTube, TikTok, Twitter/X, Instagram, Vimeo, SoundCloud, Reddit, and [many more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md))
- **Photo gallery** support via gallery-dl (Instagram carousels, Pinterest boards, Reddit galleries, etc.)
- **Cookie support** — drop a `cookiesSiteName.txt` file next to `bot.py` to access age-restricted or private content
- **HLS streams** handled automatically via ffmpeg
- **DMs only** — the bot ignores group chats
- Minimal SQLite database (ban list + counters only)
- Admin commands: `/ban`, `/unban`, `/stats`

---

## Requirements

| Dependency | Purpose | Install |
|---|---|---|
| Python 3.10+ | Runtime | [python.org](https://python.org) |
| yt-dlp | Primary downloader | via pip |
| gallery-dl | Gallery / album fallback | via pip or package manager |
| ffmpeg | HLS stream muxing | via package manager |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourname/media-downloader-bot-lite.git
cd media-downloader-bot-lite
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install gallery-dl

```bash
pip install gallery-dl
```

> gallery-dl must be available as a command in your PATH.
> Verify with: `gallery-dl --version`

### 4. Install ffmpeg

**Ubuntu / Debian:**
```bash
sudo apt install ffmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

---

## Configuration

Open `config.py` and fill in your values:

```python
# Get from https://my.telegram.org → API development tools
API_ID   = 12345678
API_HASH = "your_api_hash_here"

# Get from @BotFather on Telegram
BOT_TOKEN = "1234567890:AAFxxxxxxx"

# Your Telegram user ID (find it via @userinfobot)
SUDO_USERS = [123456789]
```

---

## Cookies (optional)

Some sites (Instagram, YouTube age-restricted videos, etc.) require you to be
logged in. You can provide your browser cookies to the bot.

### Cookie file naming

Place Netscape-format cookie files in the **same folder as `bot.py`**:

```
bot.py
config.py
cookiesyoutube.txt       ← used for youtube.com and youtu.be
cookiesinstagram.txt     ← used for instagram.com
cookiestwitter.txt       ← used for twitter.com and x.com
cookiespinterest.txt     ← used for pinterest.com and pin.it
cookiestiktok.txt        ← used for tiktok.com
```

The pattern is always: `cookies` + the site name (lowercase) + `.txt`

### How to export cookies

1. Install the [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) Chrome extension (or equivalent for Firefox)
2. Log in to the site in your browser
3. Click the extension and export — save the file with the correct name next to `bot.py`

> **Security note:** Cookie files contain sensitive session tokens.
> Keep them private and never commit them to version control.
> Add `cookies*.txt` to your `.gitignore`.

---

## Running

```bash
python bot.py
```

The bot will create `media_bot.db` and `bot.log` on first run.

### Running as a service (Linux systemd)

Create `/etc/systemd/system/mediabot.service`:

```ini
[Unit]
Description=Media Downloader Bot
After=network.target

[Service]
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable --now mediabot
sudo systemctl status mediabot
```

---

## Commands

### User commands

| Command | Description |
|---|---|
| `/start` | Introduction and supported sites |
| `/help` | Usage tips and cookie setup guide |

### Admin commands (SUDO_USERS only)

| Command | Description |
|---|---|
| `/ban USER_ID` | Ban a user |
| `/unban USER_ID` | Unban a user |
| `/stats` | Show download counts and DB size |

---

## How it works

1. You send a URL in a DM
2. The bot looks for a matching `cookiesSiteName.txt` file
3. **yt-dlp** is tried first (best video/audio quality up to 1080p)
4. If yt-dlp fails, **gallery-dl** is used as a fallback (great for photo galleries)
5. Files are uploaded to Telegram and temp directories are cleaned up

---

## .gitignore

```gitignore
# Credentials
config.py
cookies*.txt
*.session
*.session-journal

# Runtime files
bot.log
media_bot.db
__pycache__/
```

---

## License

MIT — do whatever you want, just keep the attribution.
