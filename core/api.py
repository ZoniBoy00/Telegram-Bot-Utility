"""Telegram Bot API client: sending, chat discovery and bot info."""

import os
import tempfile
import time
from typing import Any, Optional

import requests
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from .config import (
    CHUNK_SIZE,
    GIF_EXTENSION,
    IMAGE_EXTENSIONS,
    MEDIA_MAX_SIZE,
    REQUEST_TIMEOUT,
    TELEGRAM_API_BASE,
)
from .ui import console, print_error, print_success, print_warning
from .utils import get_logger

logger = get_logger(__name__)

# Maximum retry attempts for Bot API requests
API_RETRY_ATTEMPTS = 3
# Telegram Bot API flood-wait response parameter name
RETRY_AFTER_KEY = "retry_after"

# Where URL-downloaded media is stored before being sent. Kept out of the
# working directory so the project folder stays clean and read-only friendly.
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "telegram-bot-utility")


def extract_error_details(response: requests.Response) -> str:
    """Extract a human-readable error message from a Bot API response."""
    try:
        data = response.json()
        return data.get("description", response.text)
    except ValueError:
        return response.text


def handle_rate_limit(response: requests.Response) -> Optional[float]:
    """
    Inspect a Bot API response for flood-wait (HTTP 429) conditions.

    Returns:
        Seconds to wait before retrying, or None if the response is not a
        rate-limit response.
    """
    if response.status_code == 429:
        try:
            data = response.json()
            return float(data.get(RETRY_AFTER_KEY, data.get("retry_after", 0)))
        except (ValueError, TypeError):
            return 5.0
    return None


def request_with_retry(method: str, url: str, **kwargs: Any) -> requests.Response:
    """
    Perform an HTTP request to the Telegram Bot API with automatic retry on
    network errors and flood-wait (429) handling.

    Args:
        method: HTTP method ("GET" or "POST")
        url: Full API endpoint URL
        **kwargs: Extra arguments passed to requests.request (data, files, ...)

    Returns:
        The final HTTP response object (a 429 response is returned as-is once
        retries are exhausted so callers can report it accurately).

    Raises:
        requests.exceptions.RequestException: After retries on network errors.
    """
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)

    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.exceptions.RequestException as exc:
            logger.warning("Network error on attempt %d: %s", attempt + 1, exc)
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise

        wait = handle_rate_limit(response)
        if wait is not None:
            if attempt < API_RETRY_ATTEMPTS - 1:
                logger.warning(
                    "Flood wait: sleeping %.1fs before retry (attempt %d/%d)",
                    wait, attempt + 2, API_RETRY_ATTEMPTS,
                )
                time.sleep(min(wait, 30))
                continue
            # Give up retrying, return the rate-limit response so the caller
            # can report it accurately.
            return response

        return response

    raise RuntimeError("Unreachable: retry loop exhausted")


def api_get(url: str, **kwargs: Any) -> requests.Response:
    """GET a Telegram Bot API endpoint with retry and flood-wait handling."""
    return request_with_retry("GET", url, **kwargs)


def api_post(url: str, **kwargs: Any) -> requests.Response:
    """POST to a Telegram Bot API endpoint with retry and flood-wait handling."""
    return request_with_retry("POST", url, **kwargs)


def parse_chat_target(target: str) -> str:
    """
    Normalize a chat target for the Bot API getChat call.

    Accepts @username, a numeric ID, or a t.me/username link.

    Args:
        target: Raw user input

    Returns:
        A normalized target string (may be empty if input was blank).
    """
    target = target.strip()
    for prefix in ("https://t.me/", "t.me/"):
        if target.startswith(prefix):
            target = target[len(prefix):]
    # Strip query params from links (e.g. ?start=...)
    target = target.split("?")[0].split("/")[0]
    return target


def get_chat_info(token: str, target: str) -> Optional[dict]:
    """
    Fetch chat information (id, type, title, username) via the Bot API getChat.

    The bot must be a member of (or have received a message from) the chat.

    Args:
        token: Bot token
        target: @username, numeric ID, or t.me link

    Returns:
        The chat result dict, or None on failure.
    """
    chat_param = parse_chat_target(target)
    if not chat_param:
        print_error("Chat target cannot be empty.")
        return None

    # getChat accepts either a numeric ID or a bare username — the @-prefix
    # causes "400 Bad Request", so strip it if the user included one.
    if chat_param.startswith("@"):
        chat_param = chat_param[1:]

    try:
        response = api_get(
            f"{TELEGRAM_API_BASE}{token}/getChat",
            params={"chat_id": chat_param},
        )
        response.raise_for_status()
        result = response.json().get("result")
        if not result:
            print_error(f"Chat not found: {target}. The bot must be a member of the chat.")
            return None
        return result
    except requests.exceptions.RequestException as e:
        # getChat only resolves numeric IDs, or channels/supergroups the bot
        # is a member of. Users cannot be looked up by username at all.
        print_error(
            f"Could not resolve '{target}': {e}. "
            f"getChat works with numeric IDs, or @channels the bot has joined. "
            f"For users, use the numeric ID from List Chats (mode 3)."
        )
        return None


def resolve_chat_id(token: str, target: str) -> Optional[int]:
    """
    Resolve a chat ID or @username to a numeric chat ID.

    Args:
        token: Bot token
        target: Numeric ID, @username, or plain username

    Returns:
        The numeric chat ID, or None if it could not be resolved.
    """
    target = target.strip()
    if not target:
        print_error("Chat target cannot be empty.")
        return None

    # Numeric IDs pass straight through (including negative group IDs)
    if target.lstrip("-").isdigit():
        return int(target)

    info = get_chat_info(token, target)
    if info is None:
        return None
    return info.get("id")


def is_gif(filename: str) -> bool:
    """Check if the file is a GIF."""
    return filename.lower().endswith(GIF_EXTENSION)


def is_image(filename: str) -> bool:
    """Check if the file is a standard image format."""
    return any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)


def download_image(image_url: str) -> Optional[str]:
    """
    Downloads an image or GIF from the provided URL with content-type and
    size validation.

    Args:
        image_url: The URL of the image to download

    Returns:
        The filename if successful, otherwise None
    """
    filename = None
    try:
        # Validate the URL scheme first
        if not image_url.lower().startswith(("http://", "https://")):
            print_error(f"Invalid URL scheme: {image_url[:50]}...")
            return None

        base_name = image_url.split("/")[-1].split("?")[0]
        if not base_name or "." not in base_name:
            base_name = "downloaded_media.bin"

        # Download into a dedicated temp folder, never the working directory.
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        filename = os.path.join(DOWNLOAD_DIR, base_name)

        with console.status(f"[bold cyan]Downloading media: {base_name}...[/]", spinner="dots"):
            response = requests.get(image_url, stream=True, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            # Validate content type is media, not HTML/etc.
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "text/html" in content_type and not filename.lower().endswith(".html"):
                print_error("URL returned HTML, not a media file.")
                return None

            # Validate content length when the server provides it
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MEDIA_MAX_SIZE:
                        print_error(
                            f"File too large ({int(content_length) // 1024 // 1024} MB, "
                            f"max {MEDIA_MAX_SIZE // 1024 // 1024} MB)."
                        )
                        return None
                except ValueError:
                    pass

            # Stream download with a running byte count to enforce the limit
            total_bytes = 0
            with open(filename, 'wb') as file:
                for chunk in response.iter_content(CHUNK_SIZE):
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > MEDIA_MAX_SIZE:
                        file.close()
                        os.remove(filename)
                        print_error(
                            f"File exceeded max size ({MEDIA_MAX_SIZE // 1024 // 1024} MB), aborted."
                        )
                        return None
                    file.write(chunk)

        print_success(f"Downloaded: {base_name} ({total_bytes // 1024} KB)")
        return filename

    except requests.exceptions.RequestException as e:
        print_error(f"Error downloading media: {e}")
        # Clean up any partial download
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError:
                pass
        return None


def send_media_message(base_url: str, chat_id: int, message: str, image_path: str) -> requests.Response:
    """
    Sends a media message (photo, animation, or document) to the specified chat.

    Args:
        base_url: The Telegram API base URL with bot token
        chat_id: Target chat ID
        message: Caption for the media
        image_path: Path to the media file

    Returns:
        Response object from the API call
    """
    # Enforce the size limit early for a clear error message
    file_size = os.path.getsize(image_path)
    if file_size > MEDIA_MAX_SIZE:
        raise ValueError(
            f"File too large to send ({file_size // 1024 // 1024} MB, "
            f"max {MEDIA_MAX_SIZE // 1024 // 1024} MB)."
        )

    with open(image_path, 'rb') as f:
        payload: dict[str, Any] = {'chat_id': chat_id, 'caption': message}

        if is_gif(image_path):
            return api_post(f"{base_url}sendAnimation", data=payload, files={'animation': f})
        elif is_image(image_path):
            return api_post(f"{base_url}sendPhoto", data=payload, files={'photo': f})
        else:
            return api_post(f"{base_url}sendDocument", data=payload, files={'document': f})


def send_text_message(base_url: str, chat_id: int, message: str) -> requests.Response:
    """
    Sends a text message to the specified chat.

    Args:
        base_url: The Telegram API base URL with bot token
        chat_id: Target chat ID
        message: Message text

    Returns:
        Response object from the API call
    """
    payload = {'chat_id': chat_id, 'text': message}
    return api_post(f"{base_url}sendMessage", data=payload)


def spam_with_token(
    token: str,
    chat_id: int,
    message: str,
    count: int,
    delay: float,
    image_path: Optional[str] = None,
) -> None:
    """
    Sends multiple messages or media to the specified chat.

    Args:
        token: Bot token
        chat_id: Target chat ID
        message: Message text or caption
        count: Number of times to send
        delay: Delay between messages in seconds
        image_path: Optional path to image/GIF to send
    """
    base_url = f"{TELEGRAM_API_BASE}{token}/"
    success_count = 0
    failures: list[str] = []

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Sending {count} messages...", total=count)

            for i in range(count):
                try:
                    if image_path and os.path.exists(image_path):
                        response = send_media_message(base_url, chat_id, message, image_path)
                    else:
                        response = send_text_message(base_url, chat_id, message)

                    if response.status_code == 200:
                        success_count += 1
                    else:
                        error_msg = extract_error_details(response)
                        failures.append(f"#{i + 1}: {error_msg}")

                except ValueError as e:
                    # e.g. file too large — stop the whole sequence
                    print_error(f"Aborting: {e}")
                    failures.append(f"#{i + 1}: {e}")
                    break
                except requests.exceptions.Timeout:
                    failures.append(f"#{i + 1}: timeout")
                except requests.exceptions.RequestException as e:
                    failures.append(f"#{i + 1}: {e}")
                except Exception as e:
                    logger.exception("Unexpected error sending message %d", i + 1)
                    failures.append(f"#{i + 1}: {e}")

                progress.advance(task)

                if i < count - 1:  # Don't delay after the last message
                    time.sleep(delay)
    except KeyboardInterrupt:
        print_warning("\nStopped by user before the sequence finished.")

    # Summary
    console.print(
        f"\n[bold]Result:[/] [green]{success_count}[/]/{count} sent, "
        f"[red]{len(failures)}[/] failed."
    )
    if failures:
        for line in failures[:10]:
            console.print(f"  [dim]{line}[/]")
        if len(failures) > 10:
            console.print(f"  [dim]... and {len(failures) - 10} more[/]")

    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
            print_success(f"Temporary file deleted: {image_path}")
        except OSError as e:
            print_error(f"Could not delete file {image_path}: {e}")


def fetch_updates(
    token: str,
    limit: int = 100,
    timeout: int = 0,
    offset: Optional[int] = None,
) -> list[dict]:
    """
    Fetch raw updates from the Bot API getUpdates queue.

    Args:
        token: Bot token
        limit: Max updates to fetch
        timeout: Long-poll timeout in seconds (0 = no long polling)
        offset: Telegram update_id to start from (last processed + 1). Passing
            it prevents re-reading the same batch.

    Returns:
        A list of raw update dictionaries, or [] on failure.
    """
    params: dict[str, Any] = {"limit": limit, "timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    try:
        response = api_get(f"{TELEGRAM_API_BASE}{token}/getUpdates", params=params)
        if response.status_code == 409:
            # Telegram allows only one getUpdates consumer at a time. Either a
            # webhook is configured or another process is polling this bot.
            print_warning(
                "getUpdates returned 409 Conflict: a webhook or another "
                "process is already consuming updates for this bot."
            )
            return []
        response.raise_for_status()
        return response.json().get("result", [])
    except requests.exceptions.RequestException as e:
        logger.warning("getUpdates failed: %s", e)
        return []


def confirm_updates(token: str, updates: list[dict]) -> Optional[int]:
    """
    Acknowledge received updates so they leave the getUpdates queue.

    Args:
        token: Bot token
        updates: The update dicts that were just processed

    Returns:
        The next offset (max update_id + 1), or None if there is nothing to
        confirm or the confirmation failed.
    """
    if not updates:
        return None

    offset = max((u.get("update_id", 0) for u in updates), default=0) + 1
    try:
        api_get(f"{TELEGRAM_API_BASE}{token}/getUpdates", params={"offset": offset, "limit": 1})
        return offset
    except requests.exceptions.RequestException as e:
        logger.warning("Could not confirm updates (offset=%s): %s", offset, e)
        return None


def list_chats(token: str) -> Optional[dict[int, dict[str, str]]]:
    """
    Lists all chats where the bot has received messages.

    Uses a single getUpdates call. Note: bots using webhooks, or chats with
    updates older than 24 hours, will not appear here — use the dumper
    (Telethon) for the full picture.

    Args:
        token: Bot token

    Returns:
        A dict mapping chat IDs to their info, or None on failure.
    """
    try:
        updates = fetch_updates(token)
        chats: dict[int, dict[str, str]] = {}

        for update in updates:
            message = update.get('message') or update.get('channel_post')
            if message:
                chat = message.get('chat', {})
                chat_id = chat.get('id')
                chat_title = (
                    chat.get('title')
                    or chat.get('username')
                    or chat.get('first_name', 'Unknown')
                )
                chat_type = chat.get('type', 'unknown')
                if chat_id is not None:
                    chats[chat_id] = {'title': chat_title, 'type': chat_type}

        if chats:
            table = Table(title="Chats where the bot has received messages")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name", style="magenta")
            table.add_column("Type", style="green")

            for chat_id, info in chats.items():
                table.add_row(str(chat_id), info['title'], info['type'])

            console.print(table)
        else:
            print_warning("No chats found. The bot needs to receive at least one message first.")

        return chats or None

    except requests.exceptions.RequestException as e:
        print_error(f"Error retrieving chat list: {e}")
        return None


def get_bot_info(token: str) -> None:
    """
    Retrieves and displays information about the bot.

    Args:
        token: Bot token
    """
    try:
        with console.status("[bold cyan]Fetching bot info...[/]", spinner="dots"):
            response = api_get(f"{TELEGRAM_API_BASE}{token}/getMe")
            response.raise_for_status()

        bot = response.json().get('result', {})

        table = Table(title="Bot Information", show_header=False)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Username", f"@{bot.get('username', 'N/A')}")
        table.add_row("First Name", bot.get('first_name', 'N/A'))
        table.add_row("ID", str(bot.get('id', 'N/A')))
        table.add_row("Is Bot", str(bot.get('is_bot', False)))
        table.add_row("Can Join Groups", str(bot.get('can_join_groups', False)))
        table.add_row("Can Read Groups", str(bot.get('can_read_all_group_messages', False)))
        table.add_row("Supports Inline", str(bot.get('supports_inline_queries', False)))

        console.print(table)

    except requests.exceptions.RequestException as e:
        print_error(f"Error retrieving bot info: {e}")
