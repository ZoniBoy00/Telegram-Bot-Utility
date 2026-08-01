"""Module for dumping bot history and user information using Telethon."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import zipfile
from collections import deque
from datetime import datetime
from typing import Any, Optional

try:
    from telethon import TelegramClient, events
    from telethon.errors.rpcerrorlist import AccessTokenExpiredError
    from telethon.tl.functions.photos import GetUserPhotosRequest
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.tl.types import (
        DocumentAttributeAnimated,
        DocumentAttributeAudio,
        DocumentAttributeFilename,
        DocumentAttributeSticker,
        DocumentAttributeVideo,
        MessageActionChatEditPhoto,
        MessageEmpty,
        MessageMediaContact,
        MessageMediaDocument,
        MessageMediaGeo,
        MessageMediaPhoto,
        PeerChannel,
        PeerChat,
    )
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from .config import (
    API_HASH,
    API_ID,
    HISTORY_DUMP_STEP,
    LOOKAHEAD_STEP_COUNT,
    ZIP_CLEANUP_AFTER_SEND,
    ZIP_INTERVAL_MESSAGES,
    ZIP_INTERVAL_SECONDS,
    validate_telethon_config,
)
from .forwarder import MessageForwarder
from .ui import console, print_error, print_info, print_success, print_warning
from .utils import get_logger

logger = get_logger(__name__)


class BotDumper:
    """Handles bot history dumping and user information extraction."""

    AUTO_SAVE_INTERVAL = 10  # Save buffered messages every 10 seconds
    AUTO_SAVE_MESSAGE_COUNT = 25  # ...or after this many buffered messages
    LOG_VISIBLE_LINES = 30   # Lines shown in the live feed panel

    def __init__(self, bot_token: str, proxy: Optional[tuple] = None, lookahead: int = LOOKAHEAD_STEP_COUNT):
        """
        Initialize the BotDumper.

        Args:
            bot_token: Telegram bot token
            proxy: Optional proxy configuration (type, host, port)
            lookahead: Empty batches to tolerate before assuming history end
        """
        if not TELETHON_AVAILABLE:
            raise ImportError(
                "Telethon library is required for bot dumping. "
                "Install it with: pip install telethon"
            )
        validate_telethon_config()

        self.lookahead = lookahead
        self.bot_token = bot_token
        self.bot_id = bot_token.split(':')[0]
        self.base_path = self.bot_id
        self.proxy = proxy
        self.bot: Optional[TelegramClient] = None

        # Set when Telegram rejects history fetching for bot accounts, so the
        # history loop breaks immediately instead of retrying a permanent error.
        self._history_restricted = False

        # Storage for chats, users, and messages
        self.all_chats: dict[int, Any] = {}
        self.all_users: dict[int, Any] = {}
        self.messages_by_chat: dict[str, dict[str, Any]] = {}

        # Deduplication: set of (chat_id, message_id) already processed
        self.seen_message_ids: set[tuple] = set()

        self.stats: dict[str, dict[str, int]] = {}

        self.total_messages_processed = 0
        self.last_save_time = datetime.now()

        self.last_zip_time: dict[str, datetime] = {}
        self.messages_since_zip: dict[str, int] = {}
        self.zip_task: Optional[asyncio.Task] = None

        self.forwarder = MessageForwarder()

        # Background queue for user profile photo downloads
        self.user_photo_queue: Optional[asyncio.Queue] = None
        self._photo_worker_task: Optional[asyncio.Task] = None
        self._queued_photo_users: set[int] = set()

        # Live dashboard state
        self.live: Optional[Live] = None
        self.log_buffer: deque[str] = deque(maxlen=self.LOG_VISIBLE_LINES)
        self._paused = asyncio.Event()
        self._paused.set()
        self._keyboard_task: Optional[asyncio.Task] = None

        # getUpdates offset: last processed update_id + 1, so the queue is
        # consumed exactly once instead of re-reading the same batch.
        self._updates_offset: Optional[int] = None

    # ------------------------------------------------------------------
    # Live dashboard
    # ------------------------------------------------------------------
    def _log(self, line: str) -> None:
        """Append a line to the live feed (or print directly if no Live is active)."""
        self.log_buffer.append(line)
        if self.live is not None:
            self.live.update(self._render_live())
        else:
            console.print(line)

    def _build_stats_table(self) -> Table:
        """Build the live statistics table."""
        media_totals = {
            'photos': 0, 'videos': 0, 'documents': 0, 'audio': 0,
            'voice': 0, 'gifs': 0, 'stickers': 0, 'locations': 0,
        }
        for stats in self.stats.values():
            for key in media_totals:
                media_totals[key] += stats.get(key, 0)

        table = Table(box=None, show_header=False, padding=(0, 2))
        table.add_column(style="bold cyan", justify="right")
        table.add_column(style="white")

        table.add_row("Messages", str(self.total_messages_processed))
        table.add_row("Chats", str(len(self.messages_by_chat)))
        table.add_row("Users", str(len(self.all_users)))

        media_str = "  ".join(f"{k}={v}" for k, v in media_totals.items() if v)
        if media_str:
            table.add_row("Media", media_str)

        for chat_id in list(self.stats.keys())[:5]:
            chat_stats = self.stats[chat_id]
            parts = ", ".join(f"{k}={v}" for k, v in chat_stats.items() if v)
            table.add_row(f"  {chat_id}", parts or "no activity")

        if len(self.stats) > 5:
            table.add_row("  …", f"{len(self.stats) - 5} more chats")

        return table

    def _render_live(self) -> Panel:
        """Render the full live dashboard (stats + recent feed)."""
        stats_panel = Panel(
            self._build_stats_table(),
            title="[bold cyan]Statistics[/]",
            border_style="cyan",
        )
        log_text = "\n".join(self.log_buffer) if self.log_buffer else "[dim]No messages yet.[/]"
        feed_panel = Panel(
            log_text,
            title="[bold cyan]Live Feed[/]",
            border_style="cyan",
        )
        return Panel(
            Group(stats_panel, feed_panel),
            title=f"[bold green]Bot Dumper — {self.bot_id}[/]",
            subtitle="[dim]P+Enter pause · C+Enter clear · S+Enter stats · Q+Enter quit[/]",
            border_style="green",
        )

    def start_live(self) -> None:
        """Start the Rich Live dashboard."""
        if self.live is not None:
            return
        self.live = Live(
            self._render_live(),
            console=console,
            refresh_per_second=4,
            auto_refresh=False,
        )
        self.live.start()
        self.live.update(self._render_live())

    def stop_live(self) -> None:
        """Stop the Rich Live dashboard."""
        if self.live is not None:
            self.live.stop()
            self.live = None

    def _format_stats_text(self) -> str:
        """Return a detailed statistics block (for the 's' command)."""
        lines = ["[bold yellow]────────── Statistics ──────────[/]"]
        lines.append(f"Messages: {self.total_messages_processed}")
        lines.append(f"Chats: {len(self.messages_by_chat)}")
        lines.append(f"Users: {len(self.all_users)}")
        for chat_id, chat_stats in self.stats.items():
            parts = ", ".join(f"{k}={v}" for k, v in chat_stats.items() if v)
            lines.append(f"[cyan]{chat_id}:[/] {parts or 'no activity'}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Keyboard commands (P/C/S/Q)
    # ------------------------------------------------------------------
    async def start_keyboard_listener(self) -> None:
        """Start the background task that reads keyboard commands."""
        if self._keyboard_task is None:
            self._keyboard_task = asyncio.create_task(self._keyboard_loop())

    async def _keyboard_loop(self) -> None:
        """Read command lines from stdin without blocking the event loop."""
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except (EOFError, OSError):
                break
            if not line:
                break
            await self.handle_command(line.strip().lower())

    async def handle_command(self, cmd: str) -> None:
        """Handle a keyboard command."""
        if cmd in ("p", "pause"):
            if self._paused.is_set():
                self._paused.clear()
                self._log("[yellow]⏸ Paused — new messages will wait until resumed.[/]")
            else:
                self._paused.set()
                self._log("[green]▶ Resumed.[/]")
        elif cmd in ("c", "clear"):
            self.log_buffer.clear()
            if self.live is not None:
                self.live.update(self._render_live())
        elif cmd in ("s", "stats"):
            self._log(self._format_stats_text())
        elif cmd in ("q", "quit", "exit", "stop"):
            self._log("[red]Quit requested — shutting down.[/]")
            if self.bot is not None:
                await self.bot.disconnect()

    # ------------------------------------------------------------------
    # Directory setup
    # ------------------------------------------------------------------
    def setup_directories(self) -> None:
        """Set up the directory structure for storing bot data."""
        if os.path.exists(self.base_path):
            new_path = f'{self.base_path}_{int(datetime.now().timestamp())}'

            try:
                # Use shutil.move() which is more robust than os.rename()
                shutil.move(self.base_path, new_path)
                print_warning(f"Existing directory renamed to: {new_path}")
            except (PermissionError, OSError) as e:
                # If move fails, just use a timestamped directory name instead
                print_warning(f"Could not rename existing directory: {str(e)}")
                print_warning("Using timestamped directory name instead...")
                self.base_path = new_path

            # Create the directory
            os.makedirs(self.base_path, exist_ok=True)

            # Copy existing session file if it exists and we successfully
            # moved the old directory
            if os.path.exists(new_path):
                old_session = os.path.join(new_path, f'{self.bot_id}.session')
                if os.path.exists(old_session):
                    try:
                        shutil.copyfile(old_session, os.path.join(self.base_path, f'{self.bot_id}.session'))
                    except Exception as e:
                        print_warning(f"Could not copy session file: {str(e)}")
        else:
            os.makedirs(self.base_path, exist_ok=True)

    def setup_media_directories(self, chat_id: str) -> None:
        """Create organized media directories for a chat."""
        user_dir = os.path.join(self.base_path, chat_id)
        media_dir = os.path.join(user_dir, 'media')

        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)

        # Create subdirectories for different media types
        for subdir in ['photos', 'videos', 'documents', 'audio', 'voice', 'gifs', 'stickers']:
            os.makedirs(os.path.join(media_dir, subdir), exist_ok=True)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    async def authenticate(self) -> TelegramClient:
        """
        Authenticate with Telegram using the bot token.

        Returns:
            Authenticated TelegramClient instance
        """
        self.setup_directories()

        try:
            session_path = os.path.join(self.base_path, self.bot_id)
            self.bot = await TelegramClient(session_path, API_ID, API_HASH, proxy=self.proxy).start(
                bot_token=self.bot_token
            )
        except AccessTokenExpiredError:
            print_error("Token has expired!")
            raise
        except Exception as e:
            print_error(f"Authentication failed: {e}")
            raise

        me = await self.bot.get_me()
        self._print_bot_info(me)

        user = await self.bot(GetFullUserRequest(me))
        self.all_users[me.id] = user

        # Persist bot metadata, but NEVER the bot token itself.
        user_info = me.to_dict()
        user_info.pop('token', None)

        bot_file = os.path.join(self.base_path, 'bot.json')
        with open(bot_file, 'w', encoding='utf-8') as f:
            json.dump(user_info, f, indent=2, ensure_ascii=False)

        return self.bot

    def _print_bot_info(self, bot_info: Any) -> None:
        """Print bot information (called before the live dashboard starts)."""
        console.rule("[bold cyan]Bot Information[/]", style="blue")

        info_table = Table(box=None, show_header=False, padding=(0, 2))
        info_table.add_column("Key", style="cyan bold", justify="right")
        info_table.add_column("Value", style="white")

        info_table.add_row("ID", str(bot_info.id))
        info_table.add_row("Name", bot_info.first_name)
        info_table.add_row("Username", f"@{bot_info.username}" if bot_info.username else "None")
        info_table.add_row("Link", f"https://t.me/{bot_info.username}" if bot_info.username else "-")

        console.print(Align.center(info_table))

    def _print_user_info(self, user_info: Any) -> None:
        """Log a new user detected event into the live feed."""
        self._log(f"[bold green]NEW USER DETECTED: {user_info.id}[/]")
        self._log(" " + " | ".join(
            f"[green]{key}:[/] {value}"
            for key, value in (
                ("First", user_info.first_name),
                ("Last", user_info.last_name or "-"),
                ("User", f"@{user_info.username}" if user_info.username else "-"),
            )
        ))

    # ------------------------------------------------------------------
    # User info & photos
    # ------------------------------------------------------------------
    def save_user_info(self, user: Any) -> None:
        """Save user information to disk."""
        user_id = str(user.id)
        self.setup_media_directories(user_id)

        user_file = os.path.join(self.base_path, user_id, f'{user_id}.json')
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user.to_dict(), f, indent=2, ensure_ascii=False, default=str)

    async def safe_api_request(self, coro_factory, comment: str, retries: int = 3) -> Optional[Any]:
        """
        Safely execute an API request with error handling and retries.

        Args:
            coro_factory: Zero-argument callable that returns a fresh coroutine
                (a coroutine can only be awaited once, so a new one is created
                per attempt)
            comment: Description of the operation for error messages
            retries: Number of retry attempts

        Returns:
            Result of the operation or None on error
        """
        delay = 1.0

        for attempt in range(retries + 1):
            try:
                return await coro_factory()
            except Exception as e:  # noqa: BLE001 - intentional broad retry
                # Some methods are permanently forbidden for bot users;
                # retrying them would only waste time.
                if self._is_bot_restricted_error(e):
                    logger.error("API error (%s): %s", comment, e)
                    self._log(f"[red]Error, {comment}: {str(e)}[/]")
                    self._history_restricted = True
                    return None
                if attempt < retries:
                    logger.warning("API error (%s): %s. Retry %d/%d in %.1fs",
                                   comment, e, attempt + 1, retries, delay)
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    logger.error("API error (%s): %s", comment, e)
                    self._log(f"[red]Error, {comment}: {str(e)}[/]")
        return None

    def start_photo_worker(self) -> None:
        """Start the background worker that downloads user profile photos."""
        if self._photo_worker_task is not None:
            return
        self.user_photo_queue = asyncio.Queue()
        self._photo_worker_task = asyncio.create_task(self._photo_worker())

    async def _photo_worker(self) -> None:
        """Consume the user photo queue so the event loop stays responsive."""
        assert self.user_photo_queue is not None
        while True:
            user = await self.user_photo_queue.get()
            try:
                await self.save_user_photos(user)
            except Exception as e:
                logger.exception("Failed to download photos for user %s", getattr(user, 'id', '?'))
                self._log(f"[red]Error downloading photos for user {getattr(user, 'id', '?')}: {e}[/]")
            finally:
                self.user_photo_queue.task_done()
                self._queued_photo_users.discard(getattr(user, 'id', 0))

    async def enqueue_user_photos(self, user: Any) -> None:
        """Queue profile photo downloads for a user (deduplicated)."""
        if self.user_photo_queue is None:
            return
        user_id = getattr(user, 'id', 0)
        if user_id in self._queued_photo_users:
            return
        self._queued_photo_users.add(user_id)
        await self.user_photo_queue.put(user)

    async def save_user_photos(self, user: Any) -> None:
        """Save all photos from a user's profile."""
        user_id = str(user.id)
        user_dir = os.path.join(self.base_path, user_id)

        result = await self.safe_api_request(
            lambda: self.bot(GetUserPhotosRequest(user_id=user.id, offset=0, max_id=0, limit=100)),
            'get user photos',
        )

        if not result:
            return

        for photo in result.photos:
            self._log(f"[dim]Saving photo {photo.id}...[/]")
            await self.safe_api_request(
                # Bind the loop variable so retries use the same photo
                lambda photo=photo: self.bot.download_file(photo, os.path.join(user_dir, f'{photo.id}.jpg')),
                'download user photo',
            )

    # ------------------------------------------------------------------
    # Media saving
    # ------------------------------------------------------------------
    async def save_media_photo(self, chat_id: str, photo: Any) -> str:
        """Save a photo from a message."""
        photos_dir = os.path.join(self.base_path, chat_id, 'media', 'photos')
        filename = os.path.join(photos_dir, f'{photo.id}.jpg')
        await self.safe_api_request(
            lambda: self.bot.download_file(photo, filename),
            'download media photo',
        )
        return f'media/photos/{photo.id}.jpg'

    @staticmethod
    def get_document_filename(document: Any) -> str:
        """Extract filename from a document."""
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
            # Voice & round video
            if isinstance(attr, (DocumentAttributeAudio, DocumentAttributeVideo)):
                try:
                    return f'{document.id}.{document.mime_type.split("/")[1]}'
                except (IndexError, AttributeError):
                    return f'{document.id}'
        return f'{document.id}'

    async def save_media_document(self, chat_id: str, document: Any) -> str:
        """Save a document from a message."""
        # Determine document type
        doc_type = 'documents'

        # Check attributes
        is_video = False
        is_audio = False
        is_voice = False
        is_animated = False
        is_sticker = False

        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeAudio):
                is_audio = True
                if attr.voice:
                    is_voice = True
            elif isinstance(attr, DocumentAttributeVideo):
                is_video = True
            elif isinstance(attr, DocumentAttributeAnimated):
                is_animated = True
            elif isinstance(attr, DocumentAttributeSticker):
                is_sticker = True

        # Prioritize categorization
        if is_sticker or (document.mime_type or '') == 'image/webp':
            doc_type = 'stickers'
        elif is_animated or (document.mime_type or '') == 'image/gif':
            doc_type = 'gifs'
        elif is_voice:
            doc_type = 'voice'
        elif is_audio:
            doc_type = 'audio'
        elif is_video:
            doc_type = 'videos'

        media_dir = os.path.join(self.base_path, chat_id, 'media', doc_type)
        filename = self.get_document_filename(document)
        full_path = os.path.join(media_dir, filename)

        # Handle duplicate filenames
        if os.path.exists(full_path):
            name, ext = os.path.splitext(filename)
            filename = f'{name}_{document.id}{ext}'
            full_path = os.path.join(media_dir, filename)

        await self.safe_api_request(
            lambda: self.bot.download_file(document, full_path),
            'download file',
        )
        return f'media/{doc_type}/{filename}'

    # ------------------------------------------------------------------
    # History persistence (text + JSONL)
    # ------------------------------------------------------------------
    def _migrate_legacy_json(self, chat_id: str) -> None:
        """
        One-time migration: convert an existing messages.json dump into the
        append-only JSONL format used from now on.
        """
        user_dir = os.path.join(self.base_path, str(chat_id))
        json_path = os.path.join(user_dir, f'{chat_id}_messages.json')
        jsonl_path = os.path.join(user_dir, f'{chat_id}_messages.jsonl')

        if not os.path.exists(json_path) or os.path.exists(jsonl_path):
            return

        try:
            with open(json_path, encoding='utf-8') as f:
                messages = json.load(f)

            if not isinstance(messages, list):
                messages = [messages]

            with open(jsonl_path, 'a', encoding='utf-8') as out:
                for msg in messages:
                    out.write(json.dumps(msg, ensure_ascii=False, default=str) + '\n')

            # Keep a backup of the legacy file instead of deleting it
            legacy_backup = json_path + '.legacy'
            os.replace(json_path, legacy_backup)
            self._log(f"[cyan]Migrated legacy messages.json to JSONL for chat {chat_id}[/]")
        except (OSError, ValueError) as e:
            logger.warning("Could not migrate legacy JSON for chat %s: %s", chat_id, e)

    def save_text_history(self, chat_id: str, messages: list[str]) -> None:
        """Append messages to the text history file."""
        user_dir = os.path.join(self.base_path, str(chat_id))

        if not os.path.exists(user_dir):
            self.setup_media_directories(str(chat_id))

        history_filename = os.path.join(user_dir, f'{chat_id}_history.txt')
        with open(history_filename, 'a', encoding='utf-8') as text_file:
            text_file.write('\n'.join(messages) + '\n')

    def save_jsonl_messages(self, chat_id: str, messages: list[dict[str, Any]]) -> None:
        """Append messages to the JSONL history file (one JSON object per line)."""
        user_dir = os.path.join(self.base_path, str(chat_id))
        jsonl_filename = os.path.join(user_dir, f'{chat_id}_messages.jsonl')

        self._migrate_legacy_json(chat_id)

        with open(jsonl_filename, 'a', encoding='utf-8') as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False, default=str) + '\n')

    def save_chats_text_history(self, immediate: bool = False) -> None:
        """Save all buffered chat histories."""
        current_time = datetime.now()
        time_since_save = (current_time - self.last_save_time).total_seconds()

        buffered = sum(len(m['buf_json']) for m in self.messages_by_chat.values())

        # Only save if immediate or enough time has passed or enough messages
        # have accumulated (smaller data-loss window than a pure timer).
        if not immediate and time_since_save < self.AUTO_SAVE_INTERVAL and buffered < self.AUTO_SAVE_MESSAGE_COUNT:
            return

        for m_chat_id, messages_dict in self.messages_by_chat.items():
            if not messages_dict['buf_text']:
                continue

            self._log(f"[cyan]Saving {len(messages_dict['buf_text'])} new messages for chat {m_chat_id}...[/]")

            # Save text format
            self.save_text_history(m_chat_id, messages_dict['buf_text'])

            # Save JSONL format
            self.save_jsonl_messages(m_chat_id, messages_dict['buf_json'])

            # Clear buffers
            messages_dict['buf_text'] = []
            messages_dict['buf_json'] = []

        self.last_save_time = current_time

        self.save_statistics()

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    @staticmethod
    def _default_stats() -> dict[str, int]:
        """Return the canonical per-chat statistics dictionary."""
        return {
            'messages': 0,
            'photos': 0,
            'videos': 0,
            'documents': 0,
            'audio': 0,
            'voice': 0,
            'gifs': 0,
            'stickers': 0,
            'locations': 0,
        }

    def save_statistics(self) -> None:
        """Save chat statistics to file."""
        stats_file = os.path.join(self.base_path, 'statistics.json')

        total_stats = {
            'total_chats': len(self.messages_by_chat),
            'total_users': len(self.all_users),
            'total_messages': self.total_messages_processed,
            'chats': {},
        }

        for chat_id in self.messages_by_chat:
            chat_stats = self.stats.get(chat_id, self._default_stats())
            total_stats['chats'][chat_id] = chat_stats

        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(total_stats, f, indent=2, ensure_ascii=False)

    def update_stats(self, chat_id: str, media_type: str = 'messages') -> None:
        """Update statistics for a chat."""
        if chat_id not in self.stats:
            self.stats[chat_id] = self._default_stats()

        self.stats[chat_id][media_type] = self.stats[chat_id].get(media_type, 0) + 1

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_bot_restricted_error(exc: Exception) -> bool:
        """Check if an API error means the method is forbidden for bot users."""
        msg = str(exc)
        return "cannot be executed as a bot" in msg or "access for bot users is restricted" in msg

    @staticmethod
    def get_chat_id(message: Any, bot_id: str = "") -> str:
        """Extract chat ID from a message using Telethon's built-in property."""
        chat_id = getattr(message, "chat_id", None)
        return str(chat_id) if chat_id is not None else "0"

    @staticmethod
    def get_from_id(message: Any, bot_id: str = "") -> str:
        """Extract sender ID from a message using Telethon's built-in property."""
        from_id = getattr(message, "sender_id", None)
        return str(from_id) if from_id is not None else "0"

    # ------------------------------------------------------------------
    # Message processing
    # ------------------------------------------------------------------
    def _init_chat(self, chat_id: str) -> None:
        """Initialize storage structures for a chat."""
        if chat_id not in self.messages_by_chat:
            self.messages_by_chat[chat_id] = {
                'buf_text': [],
                'buf_json': [],
            }
            self.setup_media_directories(chat_id)
            self.messages_since_zip[chat_id] = 0
            self.last_zip_time[chat_id] = datetime.now()

    async def process_message(self, m: Any) -> bool:
        """
        Process a single message (deduplicated).

        Args:
            m: Message object

        Returns:
            True if the message was skipped (empty or duplicate), False otherwise
        """
        m_chat_id = self.get_chat_id(m)
        m_from_id = self.get_from_id(m)

        if isinstance(m, MessageEmpty):
            return True

        self._init_chat(m_chat_id)

        # Deduplicate by (chat_id, message_id)
        dedup_key = (m_chat_id, m.id)
        if dedup_key in self.seen_message_ids:
            return True
        self.seen_message_ids.add(dedup_key)

        chat_type = 'Private'
        if isinstance(m.peer_id, PeerChat):
            chat_type = 'Group'
        elif isinstance(m.peer_id, PeerChannel):
            chat_type = 'Channel'

        message_text = ''
        media_path = None
        media_type = None

        # Process media with improved organization
        if m.media:
            if isinstance(m.media, MessageMediaGeo):
                message_text = f'Geoposition: {m.media.geo.long}, {m.media.geo.lat}'
                media_type = 'locations'
            elif isinstance(m.media, MessageMediaPhoto):
                media_path = await self.save_media_photo(m_chat_id, m.media.photo)
                message_text = f'Photo: {media_path}'
                media_type = 'photos'
            elif isinstance(m.media, MessageMediaContact):
                message_text = (
                    f'Vcard: phone {m.media.phone_number}, '
                    f'{m.media.first_name} {m.media.last_name}'
                )
            elif isinstance(m.media, MessageMediaDocument):
                media_path = await self.save_media_document(m_chat_id, m.media.document)
                message_text = f'Document: {media_path}'

                # Determine media type for stats
                if 'videos' in media_path:
                    media_type = 'videos'
                elif 'audio' in media_path:
                    media_type = 'audio'
                elif 'voice' in media_path:
                    media_type = 'voice'
                elif 'gifs' in media_path:
                    media_type = 'gifs'
                elif 'stickers' in media_path:
                    media_type = 'stickers'
                else:
                    media_type = 'documents'
        else:
            if isinstance(m.action, MessageActionChatEditPhoto):
                media_path = await self.save_media_photo(m_chat_id, m.action.photo)
                message_text = f'Photo of chat was changed: {media_path}'
                media_type = 'photos'
            elif m.action:
                message_text = str(m.action)

        if m.message:
            message_text = '\n'.join([message_text, m.message]).strip()

        # Format timestamp for better readability
        timestamp = m.date.strftime('%Y-%m-%d %H:%M:%S') if m.date else 'unknown'

        # Create text format for file
        text = f'[{chat_type}][{m.id}][{m_from_id}→{m_chat_id}][{timestamp}] {message_text}'

        # Style logging for console
        log_style = "green" if chat_type == 'Private' else "cyan" if chat_type == 'Group' else "magenta"
        log_chat_id = f"[{log_style}]{chat_type}[/]"
        log_ids = f"[dim]{m_from_id}→{m_chat_id}[/]"
        self._log(f"[dim]{timestamp}[/] {log_chat_id} {log_ids}: {message_text}")

        # Create JSON format with more metadata
        json_message = {
            'id': m.id,
            'from_id': m_from_id,
            'chat_id': m_chat_id,
            'chat_type': chat_type,
            'date': timestamp,
            'timestamp': int(m.date.timestamp()) if m.date else None,
            'text': m.message if m.message else '',
            'media_type': media_type,
            'media_path': media_path,
            'is_reply': bool(m.reply_to),
            'reply_to_msg_id': m.reply_to.reply_to_msg_id if m.reply_to else None,
            'is_forward': bool(m.fwd_from),
            'forward_from': str(m.fwd_from) if m.fwd_from else None,
            'edit_date': m.edit_date.strftime('%Y-%m-%d %H:%M:%S') if m.edit_date else None,
        }

        # Add to buffers
        self.messages_by_chat[m_chat_id]['buf_text'].append(text)
        self.messages_by_chat[m_chat_id]['buf_json'].append(json_message)

        # Update statistics
        self.update_stats(m_chat_id, media_type if media_type else 'messages')
        self.total_messages_processed += 1

        self.messages_since_zip[m_chat_id] = self.messages_since_zip.get(m_chat_id, 0) + 1

        # Forward the message to configured channels (non-blocking)
        if self.forwarder.telegram_enabled or self.forwarder.discord_enabled:
            asyncio.create_task(
                self.forwarder.forward_message(json_message, media_path)
            )

        # Save user info if new user (photo downloads run in background)
        is_from_user = m_chat_id == m_from_id
        if is_from_user and m_from_id and int(m_from_id) not in self.all_users:
            try:
                user = await self.bot.get_entity(int(m_from_id))
                self._print_user_info(user)
                self.save_user_info(user)
                await self.enqueue_user_photos(user)
                self.all_users[int(m_from_id)] = user
            except Exception as e:
                logger.warning("Error getting user info for %s: %s", m_from_id, e)

        self.save_chats_text_history()

        return False

    async def process_edited_message(self, m: Any) -> None:
        """
        Handle an edited message without creating a duplicate history entry.

        The edit is appended to the JSONL archive as an 'edited' event so the
        audit trail is preserved.
        """
        m_chat_id = self.get_chat_id(m)
        m_from_id = self.get_from_id(m)

        if isinstance(m, MessageEmpty):
            return

        self._init_chat(m_chat_id)

        chat_type = 'Private'
        if isinstance(m.peer_id, PeerChat):
            chat_type = 'Group'
        elif isinstance(m.peer_id, PeerChannel):
            chat_type = 'Channel'

        timestamp = m.date.strftime('%Y-%m-%d %H:%M:%S') if m.date else 'unknown'
        text = m.message or ''
        edit_date = m.edit_date.strftime('%Y-%m-%d %H:%M:%S') if m.edit_date else timestamp

        self._log(f"[magenta][EDIT] Message {m.id} in chat {m_chat_id} edited[/]")

        edit_entry = {
            'event': 'edited',
            'id': m.id,
            'from_id': m_from_id,
            'chat_id': m_chat_id,
            'chat_type': chat_type,
            'date': timestamp,
            'edit_date': edit_date,
            'timestamp': int(m.date.timestamp()) if m.date else None,
            'text': text,
        }

        user_dir = os.path.join(self.base_path, str(m_chat_id))
        if not os.path.exists(user_dir):
            self.setup_media_directories(str(m_chat_id))
        self._migrate_legacy_json(m_chat_id)

        jsonl_filename = os.path.join(user_dir, f'{m_chat_id}_messages.jsonl')
        with open(jsonl_filename, 'a', encoding='utf-8') as f:
            f.write(json.dumps(edit_entry, ensure_ascii=False, default=str) + '\n')

        # Also append a text log line
        history_filename = os.path.join(user_dir, f'{m_chat_id}_history.txt')
        with open(history_filename, 'a', encoding='utf-8') as f:
            f.write(f'[EDIT][{chat_type}][{m.id}][{m_from_id}→{m_chat_id}][{edit_date}] {text}\n')

    # ------------------------------------------------------------------
    # Bot API update processing (bots cannot fetch MTProto history)
    # ------------------------------------------------------------------
    def process_bot_api_update(self, update: dict) -> None:
        """
        Store a message from the Bot API update queue.

        Bots cannot fetch history via MTProto (GetHistoryRequest is
        forbidden), so the update queue is the only source of past messages.
        """
        message = update.get('message') or update.get('channel_post')
        if not message:
            return

        chat = message.get('chat', {})
        chat_id = str(chat.get('id', '0'))
        chat_type = {
            'private': 'Private',
            'group': 'Group',
            'supergroup': 'Group',
            'channel': 'Channel',
        }.get(chat.get('type', ''), 'Private')

        sender = message.get('from', {})
        from_id = str(sender.get('id', '0')) if sender else '0'

        text = message.get('text') or message.get('caption') or ''
        timestamp = datetime.fromtimestamp(message.get('date', 0)).strftime('%Y-%m-%d %H:%M:%S')

        media_type = None
        for key, mapped in (
            ('photo', 'photos'),
            ('video', 'videos'),
            ('document', 'documents'),
            ('animation', 'gifs'),
            ('voice', 'voice'),
            ('audio', 'audio'),
            ('sticker', 'stickers'),
        ):
            if key in message:
                media_type = mapped
                break

        media_path = None
        message_text = text
        if media_type and not message_text:
            message_text = f"[{media_type.strip('s') or media_type}]"

        self._init_chat(chat_id)

        # Deduplicate by (chat_id, message_id)
        dedup_key = (chat_id, message.get('message_id'))
        if dedup_key in self.seen_message_ids:
            return
        self.seen_message_ids.add(dedup_key)

        json_message = {
            'id': message.get('message_id'),
            'from_id': from_id,
            'chat_id': chat_id,
            'chat_type': chat_type,
            'date': timestamp,
            'timestamp': message.get('date'),
            'text': text,
            'media_type': media_type,
            'media_path': media_path,
            'is_reply': bool(message.get('reply_to_message')),
            'reply_to_msg_id': message.get('reply_to_message', {}).get('message_id') if message.get('reply_to_message') else None,
            'is_forward': bool(message.get('forward_origin')),
            'forward_from': str(message.get('forward_origin', {}).get('sender_user', {}).get('id', '')) or None,
            'edit_date': None,
        }

        text_line = f'[{chat_type}][{json_message["id"]}][{from_id}→{chat_id}][{timestamp}] {message_text}'
        log_style = "green" if chat_type == 'Private' else "cyan" if chat_type == 'Group' else "magenta"
        self._log(f"[dim]{timestamp}[/] [{log_style}]{chat_type}[/] "
                  f"[dim]{from_id}→{chat_id}[/]: {message_text}")

        self.messages_by_chat[chat_id]['buf_text'].append(text_line)
        self.messages_by_chat[chat_id]['buf_json'].append(json_message)

        self.update_stats(chat_id, media_type if media_type else 'messages')
        self.total_messages_processed += 1
        self.messages_since_zip[chat_id] = self.messages_since_zip.get(chat_id, 0) + 1

        self.save_chats_text_history()

    # ------------------------------------------------------------------
    # History dumping
    # ------------------------------------------------------------------
    async def dump_chat_history(
        self,
        entity: Any,
        chat_label: str,
        limit_per_chat: Optional[int] = None,
    ) -> None:
        """
        Dump history for a single chat using client.get_messages.

        Args:
            entity: Chat entity to dump
            chat_label: Human-readable label for console output
            limit_per_chat: Maximum number of messages to fetch (None = all)
        """
        assert self.bot is not None
        self._log(f'[yellow]Dumping history for {chat_label}...[/]')

        offset_id = 0
        fetched = 0
        empty_batches = 0

        while True:
            messages = await self.safe_api_request(
                # Bind the loop variable so retries use the same offset
                lambda offset_id=offset_id: self.bot.get_messages(
                    entity, limit=HISTORY_DUMP_STEP, offset_id=offset_id
                ),
                f'get history for {chat_label}',
            )

            if not messages:
                # Bots cannot fetch history via MTProto (Telegram restriction).
                # The update queue is processed separately by dump_all_history,
                # so stop as soon as Telegram rejects the request.
                if self._history_restricted:
                    self._log(
                        f"[yellow]Cannot fetch full history for {chat_label}: "
                        f"bot accounts are restricted from GetHistoryRequest. "
                        f"Only recent updates are saved.[/]"
                    )
                    break

                # Empty batch: tolerate a few consecutive gaps caused by
                # deleted messages before assuming the history has ended.
                empty_batches += 1
                if empty_batches > self.lookahead:
                    self._log(f"[yellow]End of history for {chat_label}.[/]")
                    break
                continue

            empty_batches = 0

            for m in messages:
                if m is None:
                    continue
                await self.process_message(m)
                fetched += 1

            offset_id = messages[-1].id

            # Force save after each batch
            self.save_chats_text_history(immediate=True)

            if limit_per_chat is not None and fetched >= limit_per_chat:
                break

            if len(messages) < HISTORY_DUMP_STEP:
                break

            self._log(
                f'[dim]... fetched {fetched} messages so far for {chat_label}[/]'
            )

        self._log(
            f"[bold green]History dump complete for {chat_label}. "
            f"Total messages: {self.total_messages_processed}[/]"
        )

    async def dump_all_history(
        self,
        target_chat_id: Optional[str] = None,
        history_limit: Optional[int] = None,
    ) -> None:
        """
        Dump history for all accessible dialogs or a single target chat.

        Args:
            target_chat_id: If set, only dump history for this chat entity
            history_limit: Maximum messages per chat to fetch
        """
        assert self.bot is not None

        # Bots cannot fetch message history via MTProto (GetHistoryRequest is
        # forbidden). The Bot API update queue is the only source of past
        # messages for bot accounts; live monitoring continues afterwards.
        updates = self.fetch_updates(self._updates_offset)
        chats = self.discover_chats_from_updates(updates)

        if target_chat_id:
            # Try MTProto for the target (works for user accounts / admin bots
            # in channels where permitted), fall back to updates otherwise.
            try:
                entity = await self.bot.get_entity(int(target_chat_id))
            except Exception as e:
                self._log(f"[red]Could not resolve chat ID {target_chat_id}: {e}[/]")
            else:
                await self.dump_chat_history(entity, str(target_chat_id), history_limit)
            if not self.total_messages_processed:
                self._process_updates(updates, only_chat=str(target_chat_id))
            self.confirm_updates(updates)
            self.print_final_statistics()
            return

        if not chats:
            self._log("[yellow]No chats found in the update queue. "
                      "Message the bot first (e.g. /start), or use --chat <ID>.[/]")
            self.print_final_statistics()
            return

        self._log(f"[cyan]Found {len(chats)} chats (from update queue).[/]")
        self._log_access_report(chats)
        self._process_updates(updates)

        self.confirm_updates(updates)
        self.print_final_statistics()

    def fetch_updates(self, offset: Optional[int] = None) -> list[dict]:
        """Fetch raw updates from the Bot API queue (honoring our offset)."""
        try:
            from .api import fetch_updates as api_fetch_updates
        except ImportError:
            return []
        return api_fetch_updates(self.bot_token, offset=offset)

    def confirm_updates(self, updates: list[dict]) -> None:
        """Acknowledge processed updates and advance the offset."""
        try:
            from .api import confirm_updates as api_confirm_updates
        except ImportError:
            return
        next_offset = api_confirm_updates(self.bot_token, updates)
        if next_offset is not None:
            self._updates_offset = next_offset

    def _process_updates(self, updates: list[dict], only_chat: Optional[str] = None) -> int:
        """Store update-queue messages (optionally for one chat only)."""
        saved = 0
        for update in updates:
            message = update.get('message') or update.get('channel_post')
            if not message:
                continue
            chat_id = str(message.get('chat', {}).get('id', ''))
            if only_chat and chat_id != only_chat:
                continue
            self.process_bot_api_update(update)
            saved += 1
        if saved:
            self._log(f"[cyan]Saved {saved} recent message(s) from the update queue.[/]")
        return saved

    def discover_chats_from_updates(self, updates: Optional[list[dict]] = None) -> dict[int, dict[str, str]]:
        """
        Discover chats the bot has interacted with via the Bot API getUpdates
        queue (bots cannot use Telethon's get_dialogs).
        """
        if updates is None:
            updates = self.fetch_updates()

        chats: dict[int, dict[str, str]] = {}
        for update in updates:
            message = update.get('message') or update.get('channel_post')
            if not message:
                continue
            chat = message.get('chat', {})
            chat_id = chat.get('id')
            if chat_id is None:
                continue
            title = (
                chat.get('title')
                or chat.get('username')
                or chat.get('first_name', 'Unknown')
            )
            chat_type = chat.get('type', 'unknown')
            chats.setdefault(chat_id, {'title': title, 'type': chat_type})

        return chats

    # ------------------------------------------------------------------
    # Access report
    # ------------------------------------------------------------------
    @staticmethod
    def _access_summary(chat_type: str) -> tuple[str, str]:
        """
        Classify a chat type and estimate the bot's history access.

        Returns:
            A (chat_type_label, access) tuple for display.
        """
        mapping = {
            "private": ("DM", "[green]full history[/]"),
            "group": ("Group", "[yellow]messages after join (privacy off)[/]"),
            "supergroup": ("Supergroup", "[yellow]messages after join (privacy off)[/]"),
            "channel": ("Channel", "[red]needs admin for history[/]"),
        }
        return mapping.get(chat_type, (chat_type or "Unknown", "[dim]unknown access[/]"))

    def _log_access_report(self, chats: dict) -> None:
        """Log a per-chat access summary before dumping starts."""
        lines = ["[bold cyan]────────── Access Report ──────────[/]"]
        lines.append("[dim]Bot history access is limited by Telegram bot rules:[/]")
        lines.append("[dim]  private → full history · group → after join · channel → admin needed[/]")
        for chat_id, info in chats.items():
            chat_type, access = self._access_summary(info.get('type', 'unknown'))
            lines.append(
                f"  [cyan]{chat_type}:[/] {info.get('title', chat_id)} "
                f"[dim]({chat_id})[/] — {access}"
            )
        lines.append("[dim]─────────────────────────────────────[/]")
        for line in lines:
            self._log(line)

    def print_final_statistics(self) -> None:
        """Log final statistics after dumping."""
        self._log(self._format_stats_text())

    # ------------------------------------------------------------------
    # Live listening
    # ------------------------------------------------------------------
    def setup_message_listener(self) -> None:
        """Set up event listeners for new and edited messages."""
        assert self.bot is not None

        @self.bot.on(events.NewMessage)
        async def save_new_user_history(event) -> None:
            try:
                await self._paused.wait()  # hold new messages while paused
                chat_id = str(event.chat_id) if event.chat_id else self.get_chat_id(event.message)

                if chat_id not in self.all_chats:
                    self.all_chats[chat_id] = event.message.input_chat
                    self._init_chat(chat_id)

                    self._log(f"[bold green]NEW CHAT DETECTED: {chat_id}[/]")

                    chat_info = {
                        'chat_id': chat_id,
                        'detected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    }

                    # Try to get chat entity for more info
                    try:
                        chat_entity = await self.bot.get_entity(int(chat_id))
                        if hasattr(chat_entity, 'title') and chat_entity.title:
                            chat_info['title'] = chat_entity.title
                            self._log(f'[yellow]Chat Title: {chat_entity.title}[/]')
                        if hasattr(chat_entity, 'username') and chat_entity.username:
                            chat_info['username'] = chat_entity.username
                            self._log(f'[yellow]Chat Username: @{chat_entity.username}[/]')
                    except Exception as e:
                        logger.debug("Could not resolve chat entity %s: %s", chat_id, e)

                    chat_info_file = os.path.join(self.base_path, chat_id, 'chat_info.json')
                    with open(chat_info_file, 'w', encoding='utf-8') as f:
                        json.dump(chat_info, f, indent=2, ensure_ascii=False)

                    # Save user info if new (photos in background)
                    user = event.message.sender
                    if user and user.id not in self.all_users:
                        self._print_user_info(user)
                        self.save_user_info(user)
                        await self.enqueue_user_photos(user)
                        self.all_users[user.id] = user

                # Process and immediately save the message
                await self.process_message(event.message)
                self.save_chats_text_history(immediate=True)

            except Exception as e:
                logger.exception("Error in message handler")
                self._log(f"[red]Error in message handler: {str(e)}[/]")

        @self.bot.on(events.MessageEdited)
        async def handle_message_edit(event) -> None:
            try:
                await self._paused.wait()  # hold edits while paused
                await self.process_edited_message(event.message)
            except Exception as e:
                logger.exception("Error handling message edit")
                self._log(f"[red]Error handling message edit: {str(e)}[/]")

    # ------------------------------------------------------------------
    # Incremental zip archiving
    # ------------------------------------------------------------------
    def create_chat_zip(self, chat_id: str) -> Optional[str]:
        """
        Create an incremental zip archive containing only files that changed
        since the previous archive for this chat.

        Args:
            chat_id: Chat ID to create zip for

        Returns:
            Path to created zip file or None on error
        """
        try:
            chat_dir = os.path.join(self.base_path, chat_id)
            if not os.path.exists(chat_dir):
                return None

            zips_dir = os.path.join(self.base_path, 'zips')
            os.makedirs(zips_dir, exist_ok=True)

            last_time = self.last_zip_time.get(chat_id) or datetime.min

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f'chat_{chat_id}_{timestamp}.zip'
            zip_path = os.path.join(zips_dir, zip_filename)

            added_files = 0
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _dirs, files in os.walk(chat_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        except OSError:
                            continue
                        # Only archive files modified since the last zip
                        if mtime < last_time:
                            continue
                        arcname = os.path.relpath(file_path, self.base_path)
                        zipf.write(file_path, arcname)
                        added_files += 1

            if added_files == 0:
                os.remove(zip_path)
                return None

            file_size = os.path.getsize(zip_path) / 1024  # KB
            self._log(
                f"[green]Created incremental zip: {zip_filename} "
                f"({added_files} files, {file_size:.2f} KB)[/]"
            )

            return zip_path

        except Exception as e:
            logger.exception("Error creating zip for chat %s", chat_id)
            self._log(f"[red]Error creating zip for chat {chat_id}: {str(e)}[/]")
            return None

    async def check_and_create_zips(self) -> None:
        """Check if any chats need zip creation and forward them."""
        current_time = datetime.now()

        for chat_id in list(self.messages_by_chat.keys()):
            should_create_zip = False

            # Check message count threshold
            if self.messages_since_zip.get(chat_id, 0) >= ZIP_INTERVAL_MESSAGES:
                should_create_zip = True
                self._log(f"[yellow]Chat {chat_id} reached {ZIP_INTERVAL_MESSAGES} messages, creating zip...[/]")

            # Check time threshold
            last_zip = self.last_zip_time.get(chat_id)
            if last_zip:
                seconds_since_zip = (current_time - last_zip).total_seconds()
                if seconds_since_zip >= ZIP_INTERVAL_SECONDS and self.messages_since_zip.get(chat_id, 0) > 0:
                    should_create_zip = True
                    self._log(f"[yellow]Chat {chat_id} reached time threshold, creating zip...[/]")

            if not should_create_zip:
                continue

            # Create zip file (incremental: only new/changed files)
            zip_path = self.create_chat_zip(chat_id)

            if zip_path:
                message_count = self.messages_since_zip.get(chat_id, 0)
                success = await self.forwarder.forward_zip_file(zip_path, chat_id, message_count)

                if success and ZIP_CLEANUP_AFTER_SEND:
                    try:
                        os.remove(zip_path)
                        self._log(f"[green]Cleaned up zip file: {os.path.basename(zip_path)}[/]")
                    except OSError as e:
                        self._log(f"[yellow]Could not delete zip file: {str(e)}[/]")
                elif not success:
                    # Keep the archive so nothing is lost; the user can upload
                    # it manually once the destination is reachable again.
                    self._log(
                        f"[yellow]Archive delivery failed; keeping "
                        f"{os.path.basename(zip_path)} for manual upload.[/]"
                    )

                # Reset counters either way so we never regenerate (and
                # duplicate) the same archive window while a destination is down.
                self.last_zip_time[chat_id] = current_time
                self.messages_since_zip[chat_id] = 0

    async def zip_creation_loop(self) -> None:
        """Background task that periodically checks and creates zips."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.check_and_create_zips()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in zip creation loop")
                self._log(f"[red]Error in zip creation loop: {str(e)}[/]")

    async def shutdown(self) -> None:
        """Gracefully flush buffers and stop background tasks."""
        print_info("Shutting down dumper...")

        # Resume any paused handlers so pending work can finish
        self._paused.set()

        # Stop the keyboard command listener
        if self._keyboard_task is not None:
            self._keyboard_task.cancel()
            try:
                await self._keyboard_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

        # Flush any pending history
        self.save_chats_text_history(immediate=True)

        # Wait briefly for pending photo downloads
        if self._photo_worker_task is not None:
            self._photo_worker_task.cancel()
            try:
                await self._photo_worker_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

        if self.zip_task is not None:
            self.zip_task.cancel()
            try:
                await self.zip_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

        print_success("Dumper shut down cleanly.")


async def dump_bot_history(
    bot_token: str,
    listen_only: bool = False,
    lookahead: int = LOOKAHEAD_STEP_COUNT,
    proxy: Optional[tuple] = None,
    forward_to_telegram: Optional[str] = None,
    forward_to_discord: Optional[str] = None,
    target_chat_id: Optional[str] = None,
    history_limit: Optional[int] = None,
) -> None:
    """
    Main function to dump bot history and listen for new messages.

    Args:
        bot_token: Telegram bot token
        listen_only: If True, skip history dumping and only listen for new messages
        lookahead: Additional empty batches to tolerate before assuming history end
        proxy: Optional proxy configuration
        forward_to_telegram: Optional Telegram channel ID to forward messages to
        forward_to_discord: Optional Discord webhook URL to forward messages to
        target_chat_id: Optional chat entity ID to dump (None = all dialogs)
        history_limit: Optional max messages per chat to fetch (None = all)
    """
    dumper = BotDumper(bot_token, proxy, lookahead=lookahead)
    bot = await dumper.authenticate()
    if forward_to_telegram:
        dumper.forwarder.setup_telegram_forwarding(bot, forward_to_telegram)

    if forward_to_discord:
        dumper.forwarder.setup_discord_forwarding(forward_to_discord)

    dumper.start_photo_worker()
    dumper.start_live()
    await dumper.start_keyboard_listener()

    try:
        if listen_only:
            dumper._log("[yellow]Bot history dumping disabled, switching to listen mode...[/]")
        else:
            await dumper.dump_all_history(target_chat_id=target_chat_id, history_limit=history_limit)

        dumper.setup_message_listener()

        dumper.zip_task = asyncio.create_task(dumper.zip_creation_loop())

        dumper._log("[bold green]Dumper Active — listening for new messages in real-time[/]")
        dumper._log("[yellow]For group messages to be captured, the bot must:\n"
                    "  1. Be added to the group as a member\n"
                    "  2. Have 'Privacy Mode' disabled in @BotFather[/]")

        if dumper.forwarder.telegram_enabled or dumper.forwarder.discord_enabled:
            info_text = (
                f"Zip archives will be created and forwarded:\n"
                f"  - Every {ZIP_INTERVAL_MESSAGES} messages\n"
                f"  - Every {ZIP_INTERVAL_SECONDS} seconds ({ZIP_INTERVAL_SECONDS // 60} minutes)\n"
            )
            if dumper.forwarder.telegram_enabled:
                info_text += "  - To Telegram channel\n"
            if dumper.forwarder.discord_enabled:
                info_text += "  - To Discord webhook\n"
            info_text += "Individual messages are forwarded in real-time as well."
            dumper._log(f"[bold cyan]Forwarding Active[/]\n{info_text}")

        await bot.run_until_disconnected()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        dumper._log("[yellow]Stopped by user.[/]")
    finally:
        dumper.stop_live()
        await dumper.shutdown()
