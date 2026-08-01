"""Configuration constants for Telegram Bot Utility.

All settings can be overridden via environment variables (or a .env file).
See .env.example in the project root for a template.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse an environment variable as a boolean."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    """Parse an environment variable as an int with a safe fallback."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Parse an environment variable as a float with a safe fallback."""
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Telegram API configuration
# ---------------------------------------------------------------------------
TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# Bot token read from the environment (optional convenience). When set, the
# CLI offers it instead of asking for a token on every action.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Telethon API credentials (get these from https://my.telegram.org)
# Priority: Env var > hardcoded default. The dumper requires real values.
API_ID = _env_int("API_ID", 0)
API_HASH = os.getenv("API_HASH", "")

# ---------------------------------------------------------------------------
# File type extensions
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
GIF_EXTENSION = ".gif"

# ---------------------------------------------------------------------------
# Network configuration
# ---------------------------------------------------------------------------
CHUNK_SIZE = 1024
REQUEST_TIMEOUT = _env_int("REQUEST_TIMEOUT", 30)
RETRY_COUNT = _env_int("RETRY_COUNT", 3)
RETRY_BACKOFF = _env_float("RETRY_BACKOFF", 1.5)  # multiplier between retries

# Max size for media downloaded from URLs / sent via Bot API (bytes)
# Telegram limits: photos 10 MB, documents/gifs 50 MB (Bot API).
MEDIA_MAX_SIZE = _env_int("MEDIA_MAX_SIZE", 50 * 1024 * 1024)

# ---------------------------------------------------------------------------
# History dumping configuration
# ---------------------------------------------------------------------------
HISTORY_DUMP_STEP = _env_int("HISTORY_DUMP_STEP", 100)  # messages per cycle

# How many empty batches to tolerate before assuming history end.
# A value of 0 stops at the first fully-empty batch; a higher value lets the
# dumper skip gaps caused by deleted messages.
LOOKAHEAD_STEP_COUNT = _env_int("LOOKAHEAD_STEP_COUNT", 3)

# ---------------------------------------------------------------------------
# Zip compression & forwarding configuration
# ---------------------------------------------------------------------------
ZIP_INTERVAL_MESSAGES = _env_int("ZIP_INTERVAL_MESSAGES", 50)
ZIP_INTERVAL_SECONDS = _env_int("ZIP_INTERVAL_SECONDS", 300)
ZIP_CLEANUP_AFTER_SEND = _env_bool("ZIP_CLEANUP_AFTER_SEND", True)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "telegram_bot_utility.log")
LOG_FILE_ENABLED = _env_bool("LOG_FILE_ENABLED", True)


def validate_telethon_config() -> None:
    """Raise a clear error if Telethon credentials are missing/invalid."""
    if not API_ID or not API_HASH:
        raise RuntimeError(
            "Telethon requires API_ID and API_HASH. "
            "Set them in a .env file (see .env.example) or as environment "
            "variables. Get your credentials from https://my.telegram.org"
        )
