"""Resolve a Netscape cookie file for a given URL."""

# Naming convention: cookies{sitename}.txt
# Examples:
#   youtube.com     -> cookiesyoutube.txt
#   instagram.com   -> cookiesinstagram.txt

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

log = logging.getLogger("botlite.cookies")

# Skip empty fragments and TLD-like bits such as "co" or "uk".
_MIN_HOST_PART_LENGTH = 3


def resolve(url: str) -> str | None:
    """Return the path to a matching cookie file, or None."""
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        for part in host.split("."):
            if len(part) < _MIN_HOST_PART_LENGTH:
                continue
            candidate = f"cookies{part}.txt"
            if os.path.exists(candidate):
                log.info("Cookie file matched: %s (host: %s)", candidate, host)
                return candidate
    except ValueError as exc:
        log.warning("Cookie resolution error: %s", exc)
    return None
