"""Module for forwarding messages to Telegram channels and Discord webhooks."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from .ui import print_error, print_success
from .utils import get_logger, retry

logger = get_logger(__name__)

try:
    from telethon import TelegramClient
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False


class MessageForwarder:
    """Handles forwarding messages and zip files to external channels."""

    def __init__(self) -> None:
        """Initialize the message forwarder."""
        self.telegram_enabled = False
        self.discord_enabled = False
        self.telegram_bot: Optional[TelegramClient] = None
        self.telegram_channel_id: Optional[int] = None
        self.discord_webhook_url: Optional[str] = None

    def setup_telegram_forwarding(self, bot: TelegramClient, channel_id: str) -> None:
        """
        Set up Telegram channel forwarding.

        Args:
            bot: Authenticated Telegram bot client
            channel_id: Target channel ID (with or without -100 prefix)
        """
        self.telegram_bot = bot
        # Channels always use the -100 prefix; add it for bare numeric ids.
        # Full IDs that already include the prefix (e.g. "-100123") pass through.
        raw = channel_id.strip()
        if raw.isdigit():
            raw = f'-100{raw}'
        try:
            self.telegram_channel_id = int(raw)
            self.telegram_enabled = True
            print_success(f"Telegram forwarding enabled to channel: {raw}")
        except ValueError:
            print_error(f"Invalid channel ID format: {channel_id}")

    def setup_discord_forwarding(self, webhook_url: str) -> None:
        """
        Set up Discord webhook forwarding.

        Args:
            webhook_url: Discord webhook URL
        """
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            print_error("Invalid Discord webhook URL.")
            return
        self.discord_webhook_url = webhook_url
        self.discord_enabled = True
        print_success("Discord forwarding enabled")

    # ------------------------------------------------------------------
    # ZIP file forwarding
    # ------------------------------------------------------------------
    async def forward_zip_to_telegram(self, zip_path: str, chat_id: str, message_count: int) -> bool:
        """
        Forward a zip file to the Telegram channel.

        Args:
            zip_path: Path to the zip file
            chat_id: Chat ID the zip is from
            message_count: Number of messages in the zip

        Returns:
            True if successful, False otherwise
        """
        if not self.telegram_enabled or not self.telegram_bot or not self.telegram_channel_id:
            return False

        try:
            caption = (
                f"📦 **Chat Archive**\n\n"
                f"**Chat ID:** `{chat_id}`\n"
                f"**Messages:** {message_count}\n"
                f"**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**Size:** {os.path.getsize(zip_path) / 1024:.2f} KB"
            )

            await self.telegram_bot.send_file(
                self.telegram_channel_id,
                zip_path,
                caption=caption,
                parse_mode="markdown",
            )

            print_success(f"Sent zip file to Telegram: {os.path.basename(zip_path)}")
            return True
        except Exception as e:
            logger.exception("Error forwarding zip to Telegram")
            print_error(f"Error forwarding zip to Telegram: {str(e)}")
            return False

    async def forward_zip_to_discord(self, zip_path: str, chat_id: str, message_count: int) -> bool:
        """
        Forward a zip file to a Discord webhook.

        Args:
            zip_path: Path to the zip file
            chat_id: Chat ID the zip is from
            message_count: Number of messages in the zip

        Returns:
            True if successful, False otherwise
        """
        if not self.discord_enabled or not self.discord_webhook_url:
            return False

        try:
            # Create embed
            embed = {
                "title": "📦 Chat Archive",
                "color": 0x3498db,
                "fields": [
                    {"name": "Chat ID", "value": f"`{chat_id}`", "inline": True},
                    {"name": "Messages", "value": str(message_count), "inline": True},
                    {"name": "Size", "value": f"{os.path.getsize(zip_path) / 1024:.2f} KB", "inline": True},
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Use run_in_executor to avoid blocking the asyncio loop with requests
            loop = asyncio.get_running_loop()
            webhook_url = self.discord_webhook_url

            def _send_request():
                with open(zip_path, 'rb') as f:
                    files = {'file': (os.path.basename(zip_path), f)}
                    payload = {'payload_json': json.dumps({"embeds": [embed]})}
                    return retry(
                        requests.post,
                        webhook_url,
                        files=files,
                        data=payload,
                        timeout=60,
                        retries=2,
                        log=logger,
                    )

            response = await loop.run_in_executor(None, _send_request)

            if response.status_code == 200:
                print_success(f"Sent zip file to Discord: {os.path.basename(zip_path)}")
                return True
            else:
                print_error(f"Discord returned status {response.status_code}")
                return False

        except Exception as e:
            logger.exception("Error forwarding zip to Discord")
            print_error(f"Error forwarding zip to Discord: {str(e)}")
            return False

    async def forward_zip_file(self, zip_path: str, chat_id: str, message_count: int) -> bool:
        """
        Forward zip file to all enabled channels.

        Args:
            zip_path: Path to the zip file
            chat_id: Chat ID the zip is from
            message_count: Number of messages in the zip

        Returns:
            True if every enabled destination accepted the archive, False
            otherwise (so callers can decide whether it is safe to delete).
        """
        tasks = []

        if self.telegram_enabled:
            tasks.append(self.forward_zip_to_telegram(zip_path, chat_id, message_count))

        if self.discord_enabled:
            tasks.append(self.forward_zip_to_discord(zip_path, chat_id, message_count))

        if not tasks:
            return False

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return all(isinstance(r, bool) and r for r in results)

    # ------------------------------------------------------------------
    # Per-message forwarding
    # ------------------------------------------------------------------
    async def forward_to_telegram(self, message_data: dict[str, Any], media_path: Optional[str] = None) -> bool:
        """
        Forward a single message to the Telegram channel.

        Args:
            message_data: Message metadata dictionary
            media_path: Optional path to a media file

        Returns:
            True if successful, False otherwise
        """
        if not self.telegram_enabled or not self.telegram_bot or not self.telegram_channel_id:
            return False

        try:
            text = self._format_telegram_message(message_data)

            if media_path and os.path.exists(media_path):
                await self.telegram_bot.send_file(
                    self.telegram_channel_id,
                    media_path,
                    caption=text,
                    parse_mode="markdown",
                )
            else:
                await self.telegram_bot.send_message(
                    self.telegram_channel_id,
                    text,
                    parse_mode="markdown",
                )

            return True
        except Exception as e:
            logger.warning("Error forwarding message to Telegram: %s", e)
            return False

    async def forward_to_discord(self, message_data: dict[str, Any], media_url: Optional[str] = None) -> bool:
        """
        Forward a single message to a Discord webhook.

        Args:
            message_data: Message metadata dictionary
            media_url: Optional URL for media preview

        Returns:
            True if successful, False otherwise
        """
        if not self.discord_enabled or not self.discord_webhook_url:
            return False

        try:
            embed = self._create_discord_embed(message_data, media_url)

            payload = {"embeds": [embed]}

            loop = asyncio.get_running_loop()
            webhook_url = self.discord_webhook_url

            def _send_request():
                return retry(
                    requests.post,
                    webhook_url,
                    json=payload,
                    timeout=10,
                    retries=2,
                    log=logger,
                )

            response = await loop.run_in_executor(None, _send_request)

            if response.status_code not in (200, 204):
                logger.warning("Discord webhook returned status %d", response.status_code)
                return False
            return True
        except Exception as e:
            logger.warning("Error forwarding message to Discord: %s", e)
            return False

    async def forward_message(self, message_data: dict[str, Any], media_path: Optional[str] = None) -> None:
        """
        Forward a message to all enabled channels.

        Args:
            message_data: Message metadata dictionary
            media_path: Optional path to a media file
        """
        tasks = []

        if self.telegram_enabled:
            tasks.append(self.forward_to_telegram(message_data, media_path))

        if self.discord_enabled:
            # Discord cannot receive local files without a public URL, so we
            # only send the message metadata and text.
            tasks.append(self.forward_to_discord(message_data, None))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------
    def _format_telegram_message(self, message_data: dict[str, Any]) -> str:
        """Format message for Telegram (Markdown)."""
        chat_type = message_data.get('chat_type', 'Unknown')
        from_id = message_data.get('from_id', 'Unknown')
        chat_id = message_data.get('chat_id', 'Unknown')
        timestamp = message_data.get('date', 'Unknown')
        text = message_data.get('text', '')

        formatted = "📨 **New Message**\n\n"
        formatted += f"**Type:** {chat_type}\n"
        formatted += f"**From:** `{from_id}`\n"
        formatted += f"**Chat:** `{chat_id}`\n"
        formatted += f"**Time:** {timestamp}\n"

        if message_data.get('is_reply'):
            formatted += f"**Reply to:** #{message_data.get('reply_to_msg_id')}\n"

        if message_data.get('is_forward'):
            formatted += f"**Forwarded from:** {message_data.get('forward_from')}\n"

        if text:
            formatted += f"\n**Message:**\n{self._escape_markdown(text)}"

        if message_data.get('media_type'):
            formatted += f"\n\n**Media:** {message_data.get('media_type')}"

        return formatted

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """
        Escape characters with meaning in Telegram Markdown v1.

        User content can contain * _ [ ] etc. which would otherwise break
        markdown parsing and make the send fail.
        """
        for ch in ("\\", "_", "*", "[", "]", "`"):
            text = text.replace(ch, f"\\{ch}")
        return text

    def _create_discord_embed(self, message_data: dict[str, Any], media_url: Optional[str] = None) -> dict[str, Any]:
        """Create a Discord embed for a message."""
        chat_type = message_data.get('chat_type', 'Unknown')
        from_id = message_data.get('from_id', 'Unknown')
        chat_id = message_data.get('chat_id', 'Unknown')
        text = message_data.get('text', '')

        # Choose color based on chat type
        color_map = {
            'Private': 0x3498db,   # Blue
            'Group': 0x2ecc71,     # Green
            'Channel': 0x9b59b6,   # Purple
        }
        color = color_map.get(chat_type, 0x95a5a6)

        embed = {
            "title": f"📨 New {chat_type} Message",
            "color": color,
            "fields": [
                {"name": "From ID", "value": f"`{from_id}`", "inline": True},
                {"name": "Chat ID", "value": f"`{chat_id}`", "inline": True},
                {"name": "Time", "value": message_data.get('date', 'Unknown'), "inline": False},
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if text:
            # Discord embed description has a 4096 character limit
            embed["description"] = text[:4000] + ("..." if len(text) > 4000 else "")

        if message_data.get('is_reply'):
            embed["fields"].append({
                "name": "Reply to",
                "value": f"Message #{message_data.get('reply_to_msg_id')}",
                "inline": True,
            })

        if message_data.get('media_type'):
            embed["fields"].append({
                "name": "Media Type",
                "value": str(message_data.get('media_type')),
                "inline": True,
            })

        if media_url:
            embed["image"] = {"url": media_url}

        return embed
