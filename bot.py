#!/usr/bin/env python3
"""
Bot Lite Downloader
Open-source Telegram bot for downloading media via yt-dlp and gallery-dl.
DMs only. Configure via .env or environment variables.
"""

import os
import sys
import asyncio
import tempfile
import shutil
import glob
import logging
import signal
import sqlite3
import subprocess
import re
import time
import traceback
from urllib.parse import urlparse

import yt_dlp
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo

from config import (
    API_ID, API_HASH, BOT_TOKEN,
    SUDO_USERS, DB_FILE,
    MAX_FILE_SIZE, MAX_CONCURRENT_DOWNLOADS,
    MIN_FREE_DISK, USER_COOLDOWN,
)

VERSION = "1.1.0"
_start_time = time.time()


# ── Startup validation ────────────────────────────────────────────────────────

def _validate_config() -> None:
    errors = []
    if not API_ID:
        errors.append("API_ID is not set")
    if not API_HASH:
        errors.append("API_HASH is not set")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        print("Set these in a .env file or as environment variables.", file=sys.stderr)
        sys.exit(1)


# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("BotLite")


class _YtdlpLogger:
    """Pipe yt-dlp output into the bot logger."""
    def debug(self, msg):
        if not msg.startswith('[debug] '):
            log.debug(f"[yt-dlp] {msg}")
    def info(self, msg):    log.info(f"[yt-dlp] {msg}")
    def warning(self, msg): log.warning(f"[yt-dlp] {msg}")
    def error(self, msg):   log.error(f"[yt-dlp] {msg}")


# ── Telethon client ───────────────────────────────────────────────────────────

client = TelegramClient('bot_lite', API_ID, API_HASH)
download_semaphore: asyncio.Semaphore   # initialised in main()
active_downloads: set[int] = set()     # one active download per user
_user_cooldowns: dict[int, float] = {} # user_id → timestamp of last request

# Exclude t.me links; allow everything else
URL_RE = re.compile(r'https?://(?!t\.me/)[^\s<>"{}|\\^`\[\]]+')


# ── Disk space ────────────────────────────────────────────────────────────────

def free_disk(path: str = '.') -> int:
    """Return free disk space in bytes for the filesystem at *path*."""
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return 0


# ── Cookie resolution ─────────────────────────────────────────────────────────

def get_cookie_file(url: str) -> str | None:
    """
    Look for cookiesSiteName.txt next to bot.py.

    Examples
    --------
    https://www.youtube.com/...  → cookiesyoutube.txt
    https://www.instagram.com/.. → cookiesinstagram.txt
    https://x.com/...            → cookiesx.txt
    """
    try:
        host = urlparse(url).netloc.lower().replace('www.', '')
        for part in host.split('.'):
            if len(part) <= 2:
                continue
            candidate = f"cookies{part}.txt"
            if os.path.exists(candidate):
                log.info(f"Cookie file matched: {candidate} (host: {host})")
                return candidate
    except Exception as e:
        log.warning(f"Cookie resolution error: {e}")
    return None


# ── Database ──────────────────────────────────────────────────────────────────

def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id   INTEGER PRIMARY KEY,
                banned_at TEXT    DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS stats (
                name  TEXT    PRIMARY KEY,
                value INTEGER DEFAULT 0
            );
            INSERT OR IGNORE INTO stats (name, value) VALUES
                ('total_downloads',  0),
                ('failed_downloads', 0);
        """)


def _db(query: str, params: tuple = (), *, fetch: bool = False):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute(query, params)
        if fetch:
            return cur.fetchall()
        conn.commit()


def is_banned(uid: int) -> bool:
    return bool(_db("SELECT 1 FROM banned_users WHERE user_id=?", (uid,), fetch=True))

def ban_user(uid: int) -> None:
    _db("INSERT OR REPLACE INTO banned_users (user_id) VALUES (?)", (uid,))

def unban_user(uid: int) -> None:
    _db("DELETE FROM banned_users WHERE user_id=?", (uid,))

def _inc(name: str) -> None:
    _db("UPDATE stats SET value=value+1 WHERE name=?", (name,))

def _get_stat(name: str) -> int:
    rows = _db("SELECT value FROM stats WHERE name=?", (name,), fetch=True)
    return rows[0][0] if rows else 0


# ── Utilities ─────────────────────────────────────────────────────────────────

def fmt_size(n: float | None) -> str:
    if n is None:
        return "Unknown"
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_dur(secs: int | None) -> str:
    if not secs:
        return ""
    s = int(secs)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_uptime(secs: float) -> str:
    s = int(secs)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}h {m}m {sec}s"


def build_caption(mtype: str, title: str | None, uploader: str | None = None,
                  duration: int | None = None, size: int | None = None) -> str:
    icon  = {'video': '🎬', 'audio': '🎵', 'photo': '📸'}.get(mtype, '📎')
    lines = [f"{icon} **{title or 'Media'}**"]
    if uploader:
        lines.append(f"👤 {uploader}")
    meta  = []
    if duration:
        meta.append(f"⏱ {fmt_dur(duration)}")
    if size:
        meta.append(f"📦 {fmt_size(size)}")
    if meta:
        lines.append("  ".join(meta))
    return "\n".join(lines)


def is_sudo(uid: int) -> bool:
    return uid in SUDO_USERS


async def safe_edit(msg, text: str) -> None:
    """Edit a message, silently ignore if it was already deleted."""
    try:
        await msg.edit(text, parse_mode='md')
    except Exception:
        pass


def cleanup_old_temps() -> None:
    """Remove stale temp dirs older than 1 hour left by crashes."""
    tmp_root = tempfile.gettempdir()
    pattern  = os.path.join(tmp_root, 'botlite_*')
    for d in glob.glob(pattern):
        try:
            if os.path.isdir(d) and (time.time() - os.path.getmtime(d)) > 3600:
                shutil.rmtree(d, ignore_errors=True)
                log.info(f"Cleaned stale temp dir: {d}")
        except Exception:
            pass


def check_cooldown(user_id: int) -> float:
    """Return remaining cooldown seconds (0 if ready)."""
    if USER_COOLDOWN <= 0:
        return 0
    last = _user_cooldowns.get(user_id, 0)
    remaining = USER_COOLDOWN - (time.time() - last)
    return max(0.0, remaining)


# ── yt-dlp downloader ─────────────────────────────────────────────────────────

_VIDEO_EXTS = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.flv', '.m4v'}
_AUDIO_EXTS = {'.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac'}
_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'}
_ALL_EXTS   = _VIDEO_EXTS | _AUDIO_EXTS | _IMAGE_EXTS


def _guess_mtype(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in _VIDEO_EXTS: return 'video'
    if ext in _AUDIO_EXTS: return 'audio'
    if ext in _IMAGE_EXTS: return 'photo'
    return 'video'


def _mtype_from_info(fp: str, vcodec: str, acodec: str) -> str:
    """Determine media type using codec info, falling back to extension."""
    ext = os.path.splitext(fp)[1].lower()
    if ext in _IMAGE_EXTS:
        return 'photo'
    if vcodec and vcodec != 'none':
        return 'video'
    if acodec and acodec != 'none':
        return 'audio'
    return _guess_mtype(fp)


def _scan_ytdlp_files(tmpdir: str, before: set, meta: dict,
                      vcodec: str, acodec: str) -> list[tuple[str, dict, str]]:
    """Filter new files and build result tuples for dl_ytdlp."""
    new_files = [
        os.path.join(tmpdir, f)
        for f in sorted(set(os.listdir(tmpdir)) - before)
        if os.path.getsize(os.path.join(tmpdir, f)) > 100
    ]
    if not new_files:
        raise RuntimeError("yt-dlp finished but no file was written")

    results = []
    for fp in new_files:
        if os.path.splitext(fp)[1].lower() not in _ALL_EXTS:
            continue
        mtype = _mtype_from_info(fp, vcodec, acodec)
        results.append((fp, {**meta, 'size': os.path.getsize(fp)}, mtype))
    return results


def _scan_gallery_files(tmpdir: str, stderr: str) -> list[tuple[str, dict, str]]:
    """Collect usable media files produced by gallery-dl."""
    results = []
    for fname in sorted(os.listdir(tmpdir)):
        fp  = os.path.join(tmpdir, fname)
        ext = os.path.splitext(fname)[1].lower()
        if not os.path.isfile(fp) or os.path.getsize(fp) < 100:
            continue
        if ext in _VIDEO_EXTS:    mtype = 'video'
        elif ext in _IMAGE_EXTS:  mtype = 'photo'
        elif ext in _AUDIO_EXTS:  mtype = 'audio'
        else:                     continue
        results.append((fp, {'size': os.path.getsize(fp)}, mtype))
    if not results:
        raise RuntimeError(f"gallery-dl produced no usable files.\n{stderr[:200]}")
    return results


async def dl_ytdlp(url: str, tmpdir: str) -> list[tuple[str, dict, str]]:
    """Download via yt-dlp. Returns [(filepath, meta, mediatype), ...]."""
    cookie_file = get_cookie_file(url)

    ydl_opts = {
        'format': (
            'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]'
            '/best[ext=mp4][height<=1080]'
            '/bestvideo+bestaudio/best'
        ),
        'merge_output_format': 'mp4',
        'outtmpl':             os.path.join(tmpdir, '%(id)s.%(ext)s'),
        'noplaylist':          True,
        'quiet':               True,
        'no_warnings':         False,
        'logger':              _YtdlpLogger(),
        'socket_timeout':      30,
        'retries':             3,
        'max_filesize':        MAX_FILE_SIZE,
        'writeinfojson':       False,
        'writethumbnail':      False,
        'postprocessors':      [],
    }
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    loop = asyncio.get_running_loop()

    def _run() -> list[tuple[str, dict, str]]:
        before = set(os.listdir(tmpdir))

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if info is None:
            raise RuntimeError("yt-dlp returned no info")

        meta = {
            'title':    info.get('title'),
            'uploader': info.get('uploader') or info.get('channel'),
            'duration': info.get('duration'),
            'width':    info.get('width'),
            'height':   info.get('height'),
        }
        return _scan_ytdlp_files(
            tmpdir, before, meta,
            info.get('vcodec', ''),
            info.get('acodec', ''),
        )

    return await loop.run_in_executor(None, _run)


# ── gallery-dl downloader ─────────────────────────────────────────────────────

async def dl_gallery(url: str, tmpdir: str) -> list[tuple[str, dict, str]]:
    """Download via gallery-dl. Returns [(filepath, meta, mediatype), ...]."""
    cookie_file = get_cookie_file(url)

    cmd = [
        'gallery-dl',
        '--directory', tmpdir,
        '--filename',  '{num:>03}_{id}.{extension}',
        '--no-part',
    ]
    if cookie_file:
        cmd += ['--cookies', cookie_file]
    cmd.append(url)

    loop = asyncio.get_running_loop()

    def _run() -> list[tuple[str, dict, str]]:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        # exit code 1 = partial success — still usable
        if proc.returncode not in (0, 1):
            raise RuntimeError(
                f"gallery-dl exited {proc.returncode}: {proc.stderr[:300]}"
            )
        return _scan_gallery_files(tmpdir, proc.stderr)

    return await loop.run_in_executor(None, _run)


# ── Combined download logic ───────────────────────────────────────────────────

async def download(url: str, tmpdir: str) -> list[tuple[str, dict, str]]:
    """Try yt-dlp first, fall back to gallery-dl. Raises RuntimeError if both fail."""
    ytdir = os.path.join(tmpdir, 'yt')
    os.makedirs(ytdir, exist_ok=True)
    try:
        results = await dl_ytdlp(url, ytdir)
        if results:
            return results
    except Exception as e:
        log.warning(f"[yt-dlp] failed ({url}): {e}")

    gddir = os.path.join(tmpdir, 'gd')
    os.makedirs(gddir, exist_ok=True)
    try:
        results = await dl_gallery(url, gddir)
        if results:
            return results
    except Exception as e:
        log.warning(f"[gallery-dl] failed ({url}): {e}")

    raise RuntimeError(
        "Both yt-dlp and gallery-dl could not extract media from this URL.\n"
        "The site may require cookies, or the content may be unavailable."
    )


# ── Telegram helpers ──────────────────────────────────────────────────────────

async def send_media(event, fp: str, meta: dict, mtype: str) -> None:
    size    = os.path.getsize(fp)
    caption = build_caption(mtype, meta.get('title'), meta.get('uploader'),
                             meta.get('duration'), size)
    kwargs: dict = {'caption': caption, 'parse_mode': 'md', 'reply_to': event.message.id}

    if mtype == 'video':
        kwargs['attributes'] = [DocumentAttributeVideo(
            duration          = int(meta.get('duration') or 0),
            w                 = int(meta.get('width')    or 0),
            h                 = int(meta.get('height')   or 0),
            supports_streaming= True,
        )]
    elif mtype == 'audio':
        kwargs['attributes'] = [DocumentAttributeAudio(
            duration  = int(meta.get('duration') or 0),
            title     = meta.get('title')    or '',
            performer = meta.get('uploader') or '',
        )]

    await client.send_file(event.chat_id, fp, **kwargs)


# ── Command handlers ──────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    if not event.is_private:
        return
    await event.reply(
        "👋 **Bot Lite Downloader**\n\n"
        "Send me any media link and I'll download it for you.\n\n"
        "**Supported sites:** YouTube, Instagram, TikTok, Twitter/X, Reddit, "
        "Pinterest, Vimeo, SoundCloud, and [hundreds more]"
        "(https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).\n\n"
        "**Commands:** `/help`",
        parse_mode='md', link_preview=False,
    )


@client.on(events.NewMessage(pattern='/help'))
async def cmd_help(event):
    if not event.is_private:
        return
    cooldown_line = f"• Cooldown between requests: {USER_COOLDOWN}s\n" if USER_COOLDOWN else ""
    await event.reply(
        "**📖 Usage**\n\n"
        "Just send a link — no commands needed.\n\n"
        "**🍪 Cookies (optional)**\n"
        "Place a `cookiesSiteName.txt` file (Netscape format) next to `bot.py` "
        "to access age-restricted or private content.\n"
        "Examples: `cookiesyoutube.txt`, `cookiesinstagram.txt`\n\n"
        "Export with the "
        "[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) "
        "extension.\n\n"
        "**⚠️ Limits**\n"
        f"• Max file size: {fmt_size(MAX_FILE_SIZE)}\n"
        f"{cooldown_line}"
        "• Some sites actively block bots",
        parse_mode='md', link_preview=False,
    )


@client.on(events.NewMessage(pattern=r'/ban( \d+)?'))
async def cmd_ban(event):
    if not event.is_private or not is_sudo(event.sender_id):
        return
    match = event.pattern_match.group(1)
    if not match:
        await event.reply("Usage: `/ban USER_ID`", parse_mode='md')
        return
    uid = int(match.strip())
    ban_user(uid)
    log.info(f"Admin {event.sender_id} banned {uid}")
    await event.reply(f"🚫 User `{uid}` banned.", parse_mode='md')


@client.on(events.NewMessage(pattern=r'/unban( \d+)?'))
async def cmd_unban(event):
    if not event.is_private or not is_sudo(event.sender_id):
        return
    match = event.pattern_match.group(1)
    if not match:
        await event.reply("Usage: `/unban USER_ID`", parse_mode='md')
        return
    uid = int(match.strip())
    unban_user(uid)
    log.info(f"Admin {event.sender_id} unbanned {uid}")
    await event.reply(f"✅ User `{uid}` unbanned.", parse_mode='md')


@client.on(events.NewMessage(pattern='/stats'))
async def cmd_stats(event):
    if not event.is_private or not is_sudo(event.sender_id):
        return
    total  = _get_stat('total_downloads')
    failed = _get_stat('failed_downloads')
    db_sz  = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
    await event.reply(
        f"**📊 Stats**\n\n"
        f"✅ Succeeded: `{total}`\n"
        f"❌ Failed:    `{failed}`\n"
        f"💾 DB size:   `{fmt_size(db_sz)}`\n"
        f"⏱ Uptime:    `{fmt_uptime(time.time() - _start_time)}`\n"
        f"🔄 Active:    `{len(active_downloads)}/{MAX_CONCURRENT_DOWNLOADS}`\n"
        f"💿 Free disk: `{fmt_size(free_disk())}`",
        parse_mode='md',
    )


@client.on(events.NewMessage(pattern='/status'))
async def cmd_status(event):
    if not event.is_private:
        return
    disk = free_disk()
    disk_warn = " ⚠️" if disk < MIN_FREE_DISK * 2 else ""
    await event.reply(
        f"**🤖 Bot Lite Downloader v{VERSION}**\n\n"
        f"⏱ Uptime: `{fmt_uptime(time.time() - _start_time)}`\n"
        f"🔄 Active downloads: `{len(active_downloads)}`\n"
        f"💿 Free disk: `{fmt_size(disk)}`{disk_warn}",
        parse_mode='md',
    )


# ── URL handler ───────────────────────────────────────────────────────────────

async def _check_guards(event, user_id: int) -> bool:
    """Return True if the request should be rejected (guard fired)."""
    if is_banned(user_id):
        await event.reply("🚫 You are banned from using this bot.")
        return True
    if user_id in active_downloads:
        await event.reply("⏳ Your previous download is still running. Please wait.")
        return True
    wait = check_cooldown(user_id)
    if wait > 0:
        await event.reply(f"⏳ Please wait **{wait:.0f}s** before the next request.", parse_mode='md')
        return True
    if free_disk() < MIN_FREE_DISK:
        log.warning(f"Disk space low ({fmt_size(free_disk())}), rejecting download")
        await event.reply("⚠️ The server is running low on disk space. Try again later.")
        return True
    return False


async def _upload_results(event, status, results: list) -> int:
    """Upload all results; returns number of files successfully sent."""
    total = len(results)
    await safe_edit(status, f"📤 **Uploading {total} file{'s' if total > 1 else ''}…**")

    sent = 0
    for i, (fp, meta, mtype) in enumerate(results, 1):
        size = os.path.getsize(fp)
        if size > MAX_FILE_SIZE:
            await event.reply(
                f"⚠️ File {i}/{total} skipped — too large ({fmt_size(size)}).",
                parse_mode='md',
            )
            continue
        if total > 1:
            await safe_edit(status, f"📤 **Uploading {i}/{total}…**")
        try:
            await send_media(event, fp, meta, mtype)
            sent += 1
        except Exception as e:
            log.error(f"Send failed for {fp}: {e}")
            await event.reply(f"❌ Failed to send file {i}: `{str(e)[:150]}`", parse_mode='md')
        finally:
            try:
                os.remove(fp)
            except Exception:
                pass
    return sent


@client.on(events.NewMessage())
async def url_handler(event):
    if not event.is_private:
        return

    text = event.message.text or event.message.caption or ''
    urls = URL_RE.findall(text)
    if not urls:
        return

    url     = urls[0]
    user_id = event.sender_id

    if await _check_guards(event, user_id):
        return

    _user_cooldowns[user_id] = time.time()
    active_downloads.add(user_id)
    status = await event.reply("⏳ **Fetching…**", parse_mode='md')
    tmpdir = tempfile.mkdtemp(prefix='botlite_')

    try:
        async with download_semaphore:
            results = await download(url, tmpdir)

        if not results:
            await safe_edit(status, "❌ No media found at that URL.")
            _inc('failed_downloads')
            return

        sent = await _upload_results(event, status, results)

        if sent > 0:
            _inc('total_downloads')
            try:
                await status.delete()
            except Exception:
                pass
        else:
            await safe_edit(status, "❌ Could not send any files.")
            _inc('failed_downloads')

    except Exception as e:
        log.error(f"Error for {url}:\n{traceback.format_exc()}")
        await safe_edit(status, f"❌ **Download failed.**\n\n`{str(e)[:300]}`")
        _inc('failed_downloads')

    finally:
        active_downloads.discard(user_id)
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Graceful shutdown ─────────────────────────────────────────────────────────

def _setup_signals() -> None:
    """Handle SIGTERM/SIGINT for clean Docker/systemd shutdown."""
    def _handler(signum, frame):
        log.info(f"Received signal {signum}, shutting down…")
        client.disconnect()
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT,  _handler)
    except (OSError, ValueError):
        pass  # Windows may not support all signals


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global download_semaphore

    _validate_config()
    _setup_signals()

    download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    cleanup_old_temps()
    init_db()

    client.start(bot_token=BOT_TOKEN)
    log.info(f"Bot Lite Downloader v{VERSION} started. Max concurrent: {MAX_CONCURRENT_DOWNLOADS}")
    client.run_until_disconnected()


if __name__ == '__main__':
    main()
