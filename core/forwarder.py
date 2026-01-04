"""Module for forwarding messages to Telegram channels and Discord webhooks."""

import asyncio
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime
import requests

from .utils import print_success, print_error

try:
    from telethon import TelegramClient
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False


class MessageForwarder:
    """Handles forwarding messages and zip files to external channels."""
    
    def __init__(self):
        """Initialize the message forwarder."""
        self.telegram_enabled = False
        self.discord_enabled = False
        self.telegram_bot = None
        self.telegram_channel_id = None
        self.discord_webhook_url = None
        
    def setup_telegram_forwarding(self, bot: 'TelegramClient', channel_id: str) -> None:
        """
        Set up Telegram channel forwarding.
        
        Args:
            bot: Authenticated Telegram bot client
            channel_id: Target channel ID (with or without -100 prefix)
        """
        self.telegram_bot = bot
        # Ensure channel ID has proper format
        if not channel_id.startswith('-100'):
            channel_id = f'-100{channel_id}'
        try:
            self.telegram_channel_id = int(channel_id)
            self.telegram_enabled = True
            print_success(f"Telegram forwarding enabled to channel: {channel_id}")
        except ValueError:
            print_error(f"Invalid channel ID format: {channel_id}")
    
    def setup_discord_forwarding(self, webhook_url: str) -> None:
        """
        Set up Discord webhook forwarding.
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.discord_webhook_url = webhook_url
        self.discord_enabled = True
        print_success("Discord forwarding enabled")
    
    async def forward_zip_to_telegram(self, zip_path: str, chat_id: str, message_count: int) -> bool:
        """
        Forward a zip file to Telegram channel.
        
        Args:
            zip_path: Path to the zip file
            chat_id: Chat ID the zip is from
            message_count: Number of messages in the zip
            
        Returns:
            True if successful, False otherwise
        """
        if not self.telegram_enabled:
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
                caption=caption
            )
            
            print_success(f"Sent zip file to Telegram: {os.path.basename(zip_path)}")
            return True
        except Exception as e:
            print_error(f"Error forwarding zip to Telegram: {str(e)}")
            return False
    
    async def forward_zip_to_discord(self, zip_path: str, chat_id: str, message_count: int) -> bool:
        """
        Forward a zip file to Discord webhook.
        
        Args:
            zip_path: Path to the zip file
            chat_id: Chat ID the zip is from
            message_count: Number of messages in the zip
            
        Returns:
            True if successful, False otherwise
        """
        if not self.discord_enabled:
            return False
        
        try:
            # Create embed
            embed = {
                "title": "📦 Chat Archive",
                "color": 0x3498db,
                "fields": [
                    {
                        "name": "Chat ID",
                        "value": f"`{chat_id}`",
                        "inline": True
                    },
                    {
                        "name": "Messages",
                        "value": str(message_count),
                        "inline": True
                    },
                    {
                        "name": "Size",
                        "value": f"{os.path.getsize(zip_path) / 1024:.2f} KB",
                        "inline": True
                    }
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Use run_in_executor to avoid blocking the asyncio loop with requests
            loop = asyncio.get_running_loop()
            
            def _send_request():
                # Re-opening file inside the thread to be safe
                with open(zip_path, 'rb') as f:
                    files = {'file': (os.path.basename(zip_path), f)}
                    payload = {'payload_json': json.dumps({"embeds": [embed]})}
                    
                    return requests.post(
                        self.discord_webhook_url,
                        files=files,
                        data=payload,
                        timeout=60 # Increased timeout for uploads
                    )

            response = await loop.run_in_executor(None, _send_request)
            
            if response.status_code == 200:
                print_success(f"Sent zip file to Discord: {os.path.basename(zip_path)}")
                return True
            else:
                print_error(f"Discord returned status {response.status_code}")
                return False
                
        except Exception as e:
            print_error(f"Error forwarding zip to Discord: {str(e)}")
            return False
    
    async def forward_zip_file(self, zip_path: str, chat_id: str, message_count: int) -> None:
        """
        Forward zip file to all enabled channels.
        
        Args:
            zip_path: Path to the zip file
            chat_id: Chat ID the zip is from
            message_count: Number of messages in the zip
        """
        tasks = []
        
        if self.telegram_enabled:
            tasks.append(self.forward_zip_to_telegram(zip_path, chat_id, message_count))
        
        if self.discord_enabled:
            tasks.append(self.forward_zip_to_discord(zip_path, chat_id, message_count))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def forward_to_telegram(self, message_data: Dict[str, Any], media_path: Optional[str] = None) -> bool:
        """
        Forward a message to Telegram channel.
        
        Args:
            message_data: Message metadata dictionary
            media_path: Optional path to media file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.telegram_enabled:
            return False
        
        try:
            # Format message
            text = self._format_telegram_message(message_data)
            
            # Send message with or without media
            if media_path:
                await self.telegram_bot.send_file(
                    self.telegram_channel_id,
                    media_path,
                    caption=text
                )
            else:
                await self.telegram_bot.send_message(
                    self.telegram_channel_id,
                    text
                )
            
            return True
        except Exception as e:
            print_error(f"Error forwarding to Telegram: {str(e)}")
            return False
    
    async def forward_to_discord(self, message_data: Dict[str, Any], media_url: Optional[str] = None) -> bool:
        """
        Forward a message to Discord webhook.
        
        Args:
            message_data: Message metadata dictionary
            media_url: Optional URL to media file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.discord_enabled:
            return False
        
        try:
            # Create Discord embed
            embed = self._create_discord_embed(message_data, media_url)
            
            payload = {
                "embeds": [embed]
            }
            
            # Use run_in_executor to avoid blocking
            loop = asyncio.get_running_loop()
            
            def _send_request():
                return requests.post(
                    self.discord_webhook_url,
                    json=payload,
                    timeout=10
                )

            response = await loop.run_in_executor(None, _send_request)
            
            return response.status_code == 204
        except Exception as e:
            print_error(f"Error forwarding to Discord: {str(e)}")
            return False
    
    def _format_telegram_message(self, message_data: Dict[str, Any]) -> str:
        """Format message for Telegram."""
        chat_type = message_data.get('chat_type', 'Unknown')
        from_id = message_data.get('from_id', 'Unknown')
        chat_id = message_data.get('chat_id', 'Unknown')
        timestamp = message_data.get('date', 'Unknown')
        text = message_data.get('text', '')
        
        formatted = f"📨 **New Message**\n\n"
        formatted += f"**Type:** {chat_type}\n"
        formatted += f"**From:** `{from_id}`\n"
        formatted += f"**Chat:** `{chat_id}`\n"
        formatted += f"**Time:** {timestamp}\n"
        
        if message_data.get('is_reply'):
            formatted += f"**Reply to:** #{message_data.get('reply_to_msg_id')}\n"
        
        if message_data.get('is_forward'):
            formatted += f"**Forwarded from:** {message_data.get('forward_from')}\n"
        
        if text:
            formatted += f"\n**Message:**\n{text}"
        
        if message_data.get('media_type'):
            formatted += f"\n\n**Media:** {message_data.get('media_type')}"
        
        return formatted
    
    def _create_discord_embed(self, message_data: Dict[str, Any], media_url: Optional[str] = None) -> Dict[str, Any]:
        """Create Discord embed for message."""
        chat_type = message_data.get('chat_type', 'Unknown')
        from_id = message_data.get('from_id', 'Unknown')
        chat_id = message_data.get('chat_id', 'Unknown')
        text = message_data.get('text', '')
        
        # Choose color based on chat type
        color_map = {
            'Private': 0x3498db,  # Blue
            'Group': 0x2ecc71,    # Green
            'Channel': 0x9b59b6   # Purple
        }
        color = color_map.get(chat_type, 0x95a5a6)
        
        embed = {
            "title": f"📨 New {chat_type} Message",
            "color": color,
            "fields": [
                {
                    "name": "From ID",
                    "value": f"`{from_id}`",
                    "inline": True
                },
                {
                    "name": "Chat ID",
                    "value": f"`{chat_id}`",
                    "inline": True
                },
                {
                    "name": "Time",
                    "value": message_data.get('date', 'Unknown'),
                    "inline": False
                }
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if text:
            # Discord embed description has a 4096 character limit
            if len(text) > 4000:
                text = text[:4000] + "..."
            embed["description"] = text
        
        if message_data.get('is_reply'):
            embed["fields"].append({
                "name": "Reply to",
                "value": f"Message #{message_data.get('reply_to_msg_id')}",
                "inline": True
            })
        
        if message_data.get('media_type'):
            embed["fields"].append({
                "name": "Media Type",
                "value": message_data.get('media_type'),
                "inline": True
            })
        
        if media_url:
            embed["image"] = {"url": media_url}
        
        return embed
    
    async def forward_message(self, message_data: Dict[str, Any], media_path: Optional[str] = None) -> None:
        """
        Forward message to all enabled channels.
        
        Args:
            message_data: Message metadata dictionary
            media_path: Optional path to media file
        """
        tasks = []
        
        if self.telegram_enabled:
            tasks.append(self.forward_to_telegram(message_data, media_path))
        
        if self.discord_enabled:
            # For Discord, we'd need a public URL for media
            # For now, just send the message without media
            tasks.append(self.forward_to_discord(message_data, None))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
