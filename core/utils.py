"""Generic helpers: logging setup and retry logic."""

import logging
import time
from typing import Any, Callable, Optional, TypeVar

from .config import LOG_FILE, LOG_FILE_ENABLED, LOG_LEVEL, RETRY_BACKOFF, RETRY_COUNT
from .ui import console

T = TypeVar("T")


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger that mirrors output to console and a file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if LOG_FILE_ENABLED:
        try:
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as e:
            console.print(f"[yellow]Could not open log file {LOG_FILE}: {e}[/]")

    logger.propagate = False
    return logger


def retry(
    func: Callable[..., T],
    *args: Any,
    retries: int = RETRY_COUNT,
    backoff: float = RETRY_BACKOFF,
    base_delay: float = 1.0,
    log: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> T:
    """
    Execute ``func`` with retries and exponential backoff.

    Args:
        func: Callable to execute.
        retries: Number of retry attempts after the first failure.
        backoff: Multiplier applied to the delay after each failure.
        base_delay: Initial delay in seconds before the first retry.
        log: Optional logger for failure messages.

    Returns:
        The result of the first successful call.

    Raises:
        The last exception raised by ``func`` if all attempts fail.
    """
    delay = base_delay
    last_exc: Optional[BaseException] = None

    for attempt in range(retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - we intentionally retry broadly
            last_exc = exc
            if attempt >= retries:
                break
            if log:
                log.warning("Attempt %d/%d failed: %s. Retrying in %.1fs...",
                            attempt + 1, retries + 1, exc, delay)
            time.sleep(delay)
            delay *= backoff

    if log:
        log.error("Giving up after %d attempts: %s", retries + 1, last_exc)
    assert last_exc is not None
    raise last_exc
