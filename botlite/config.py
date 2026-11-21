"""Load and validate all bot configuration from environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final

log: Final[logging.Logger] = logging.getLogger(__name__)


def _load_environment() -> None:
    """Populate the process environment from a ``.env`` file when available.

    The dependency is optional: deployments may inject secrets directly as
    environment variables, so a missing ``python-dotenv`` must not abort startup.

    Returns:
        None.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        log.info("python-dotenv is not installed; using process environment only")
        return
    load_dotenv()


_load_environment()

DEFAULT_MAX_FILE_SIZE: Final[int] = 2 * 1024 * 1024 * 1024
DEFAULT_MAX_CONCURRENT_DOWNLOADS: Final[int] = 3
DEFAULT_MIN_FREE_DISK: Final[int] = 500 * 1024 * 1024
DEFAULT_USER_COOLDOWN: Final[int] = 5
DEFAULT_VOICE_MAX_DURATION: Final[int] = 1800
DEFAULT_VOICE_MAX_FILE_SIZE: Final[int] = 100 * 1024 * 1024
DEFAULT_WEBAPP_INIT_DATA_MAX_AGE: Final[int] = 3600

# Kubernetes/Docker secrets are mounted as files, not injected as environment
# variables. Each file contains a single credential value. The constant below
# is only the mount path, not a credential.
_CREDENTIAL_FILES_DIR: Final[str] = "/etc/botlite-secrets"


def _secret(name: str) -> str:
    """Read a credential from a mounted secret file, then from the environment.

    Args:
        name: Credential name, also used as the file name.

    Returns:
        The credential value, or an empty string when it is not configured.
    """
    path = Path(_CREDENTIAL_FILES_DIR) / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return os.getenv(name, "")
    except OSError as exc:
        log.warning("Cannot read secret file for %s: %s", name, exc)
        return os.getenv(name, "")


def _secret_int(name: str, default: int) -> int:
    """Read an integer credential from a secret file or the environment.

    Args:
        name: Credential name.
        default: Value used when the credential is missing or invalid.

    Returns:
        The parsed integer value.
    """
    try:
        return int(_secret(name) or str(default), 10)
    except ValueError:
        log.warning("Invalid integer for %s, using default %d", name, default)
        return default


def _secret_id_set(name: str) -> set[int]:
    """Parse a comma-separated set of identifiers from a secret file.

    Args:
        name: Credential name.

    Returns:
        Non-zero identifiers, ignoring malformed items.
    """
    values: set[int] = set()
    for item in _secret(name).split(","):
        stripped = item.strip()
        if not stripped:
            continue
        try:
            parsed = int(stripped, 10)
        except ValueError:
            continue
        if parsed:
            values.add(parsed)
    return values


def _safe_int(key: str, default: int) -> int:
    """Read an integer environment variable, falling back to the default.

    Args:
        key: Environment variable name.
        default: Value returned when the variable is unset or invalid.

    Returns:
        Parsed integer value.
    """
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        log.warning("Invalid integer for %s, using default %d", key, default)
        return default


def _int(key: str, default: int) -> int:
    """Read an integer environment variable with a default fallback.

    Args:
        key: Environment variable name.
        default: Value returned when the variable is unset or invalid.

    Returns:
        Parsed integer value.
    """
    return _safe_int(key, default)


def _int_list(key: str) -> list[int]:
    """Read a comma-separated integer list from the environment.

    Args:
        key: Environment variable name.

    Returns:
        List of parsed integers (empty list when unset or fully invalid).
    """
    raw = os.getenv(key, "")
    values: list[int] = []
    for item in raw.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        try:
            values.append(int(stripped, 10))
        except ValueError:
            continue
    return values


def _nonzero_int_list(key: str) -> set[int]:
    """Read a comma-separated integer list keeping only non-zero identifiers.

    Args:
        key: Environment variable name.

    Returns:
        Set of parsed non-zero integers.
    """
    return {value for value in _int_list(key) if value}


def _bool(key: str, default: bool = False) -> bool:
    """Read a boolean environment variable.

    Args:
        key: Environment variable name.
        default: Value returned when the variable is unset.

    Returns:
        ``True`` when the value is a truthy string, ``False`` otherwise.
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


API_ID: int = _secret_int("API_ID", 0)
API_HASH: str = _secret("API_HASH")
BOT_TOKEN: str = _secret("BOT_TOKEN")
SUDO_USERS: list[int] = sorted(_secret_id_set("SUDO_USERS"))

MAX_FILE_SIZE: int = _int("MAX_FILE_SIZE", DEFAULT_MAX_FILE_SIZE)
MAX_CONCURRENT_DOWNLOADS: int = _int("MAX_CONCURRENT_DOWNLOADS", DEFAULT_MAX_CONCURRENT_DOWNLOADS)
MIN_FREE_DISK: int = _int("MIN_FREE_DISK", DEFAULT_MIN_FREE_DISK)
USER_COOLDOWN: int = _int("USER_COOLDOWN", DEFAULT_USER_COOLDOWN)
ALLOW_GROUPS: bool = _bool("ALLOW_GROUPS", False)
ALLOWED_GROUP_IDS: set[int] = _nonzero_int_list("ALLOWED_GROUP_IDS")
VOICE_ENABLED: bool = _bool("VOICE_ENABLED", False)
VOICE_MAX_DURATION: int = _int("VOICE_MAX_DURATION", DEFAULT_VOICE_MAX_DURATION)
VOICE_MAX_FILE_SIZE: int = _int("VOICE_MAX_FILE_SIZE", DEFAULT_VOICE_MAX_FILE_SIZE)

DB_FILE: str = os.getenv("DB_FILE", "media_bot.db")
WEBAPP_PUBLIC_URL: str = os.getenv("WEBAPP_PUBLIC_URL", "")
WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "127.0.0.1")
WEBAPP_PORT: int = _int("WEBAPP_PORT", 8080)
WEBAPP_INIT_DATA_MAX_AGE: int = _int("WEBAPP_INIT_DATA_MAX_AGE", DEFAULT_WEBAPP_INIT_DATA_MAX_AGE)


def _credential_errors() -> list[str]:
    """Collect missing credential errors.

    Returns:
        List of error messages (empty when all credentials are configured).
    """
    missing = (
        ("API_ID", API_ID),
        ("API_HASH", API_HASH),
        ("BOT_TOKEN", BOT_TOKEN),
    )
    return [f"{name} is not set" for name, value in missing if not value]


def _group_errors() -> list[str]:
    """Collect group-policy related configuration errors.

    Returns:
        List of error messages (empty when the policy is consistent).
    """
    errors: list[str] = []
    if ALLOW_GROUPS and not ALLOWED_GROUP_IDS:
        errors.append(
            "ALLOW_GROUPS requires at least one non-zero ALLOWED_GROUP_IDS entry",
        )
    return errors + _voice_errors()


def _voice_errors() -> list[str]:
    """Collect voice-playback related configuration errors.

    Returns:
        List of error messages (empty when voice playback is properly configured).
    """
    if VOICE_ENABLED and not (ALLOW_GROUPS and ALLOWED_GROUP_IDS):
        return [
            "VOICE_ENABLED requires ALLOW_GROUPS and an explicit ALLOWED_GROUP_IDS allowlist",
        ]
    return []


def _limit_errors() -> list[str]:
    """Collect numeric limit validation errors.

    Returns:
        List of error messages (empty when all limits are positive).
    """
    limits = (
        ("VOICE_MAX_DURATION", VOICE_MAX_DURATION),
        ("VOICE_MAX_FILE_SIZE", VOICE_MAX_FILE_SIZE),
    )
    return [f"{name} must be greater than zero" for name, value in limits if value <= 0]


def _config_errors() -> list[str]:
    """Collect every configuration error of the bot.

    Returns:
        List of human-readable error messages (empty when the config is valid).
    """
    errors = _credential_errors()
    if WEBAPP_PUBLIC_URL and not WEBAPP_PUBLIC_URL.lower().startswith("https://"):
        errors.append("WEBAPP_PUBLIC_URL must use HTTPS")
    return errors + _group_errors() + _limit_errors()


def validate() -> None:
    """Abort startup with a clear message when the configuration is invalid.

    Raises:
        SystemExit: When at least one configuration error is found.
    """
    errors = _config_errors()
    if errors:
        for error in errors:
            log.error("[CONFIG ERROR] %s", error)
        log.error("Set these in a .env file or as environment variables.")
        raise SystemExit(1)
