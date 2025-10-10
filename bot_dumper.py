"""Module for dumping bot history and user information using Telethon."""

import os
import sys
import json
import asyncio
import shutil
import zipfile
from datetime import datetime
from typing import Optional, Dict, Any, List
from colorama import Fore

try:
    from telethon import TelegramClient, events
    from telethon.tl.functions.messages import GetMessagesRequest
    from telethon.tl.functions.users import GetFullUserRequest
    from telethon.tl.functions.photos import GetUserPhotosRequest
    from telethon.tl.types import (
        MessageService, MessageEmpty, PeerUser, PeerChat, PeerChannel,
        MessageMediaGeo, MessageMediaPhoto, MessageMediaDocument, MessageMediaContact,
        DocumentAttributeFilename, DocumentAttributeAudio, DocumentAttributeVideo,
        MessageActionChatEditPhoto
    )
    from telethon.errors.rpcerrorlist import AccessTokenExpiredError, RpcCallFailError
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

from config import (
    API_ID, API_HASH, HISTORY_DUMP_STEP, LOOKAHEAD_STEP_COUNT,
    ZIP_INTERVAL_MESSAGES, ZIP_INTERVAL_SECONDS, ZIP_CLEANUP_AFTER_SEND
)
from forwarder import MessageForwarder


class BotDumper:
    """Handles bot history dumping and user information extraction."""
    
    AUTO_SAVE_INTERVAL = 30  # Save buffered messages every 30 seconds
    
    def __init__(self, bot_token: str, proxy: Optional[tuple] = None):
        """
        Initialize the BotDumper.
        
        Args:
            bot_token: Telegram bot token
            proxy: Optional proxy configuration (type, host, port)
        """
        if not TELETHON_AVAILABLE:
            raise ImportError("Telethon library is required for bot dumping. Install with: pip install telethon")
        
        self.bot_token = bot_token
        self.bot_id = bot_token.split(':')[0]
        self.base_path = self.bot_id
        self.proxy = proxy
        self.bot: Optional[TelegramClient] = None
        
        # Storage for chats, users, and messages
        self.all_chats: Dict[int, Any] = {}
        self.all_users: Dict[int, Any] = {}
        self.messages_by_chat: Dict[str, Dict[str, Any]] = {}
        
        self.stats: Dict[str, Dict[str, int]] = {}
        
        self.total_messages_processed = 0
        self.last_save_time = datetime.now()
        
        self.last_zip_time: Dict[str, datetime] = {}
        self.messages_since_zip: Dict[str, int] = {}
        self.zip_task = None
        
        self.forwarder = MessageForwarder()

    def setup_directories(self) -> None:
        """Set up the directory structure for storing bot data."""
        if os.path.exists(self.base_path):
            import time
            new_path = f'{self.base_path}_{str(int(time.time()))}'
            
            try:
                # Use shutil.move() which is more robust than os.rename()
                shutil.move(self.base_path, new_path)
                print(f"{Fore.YELLOW}Existing directory renamed to: {new_path}")
            except (PermissionError, OSError) as e:
                # If move fails, just use a timestamped directory name instead
                print(f"{Fore.YELLOW}Could not rename existing directory: {str(e)}")
                print(f"{Fore.YELLOW}Using timestamped directory name instead...")
                self.base_path = new_path
            
            # Create the directory
            if not os.path.exists(self.base_path):
                os.mkdir(self.base_path)
            
            # Copy existing session file if it exists and we successfully moved the old directory
            if os.path.exists(new_path):
                old_session = f'{new_path}/{self.bot_id}.session'
                if os.path.exists(old_session):
                    try:
                        shutil.copyfile(old_session, f'{self.base_path}/{self.bot_id}.session')
                    except Exception as e:
                        print(f"{Fore.YELLOW}Could not copy session file: {str(e)}")
        else:
            os.mkdir(self.base_path)
    
    def setup_media_directories(self, chat_id: str) -> None:
        """Create organized media directories for a chat."""
        user_dir = os.path.join(self.base_path, chat_id)
        media_dir = os.path.join(user_dir, 'media')
        
        if not os.path.exists(user_dir):
            os.mkdir(user_dir)
        
        if not os.path.exists(media_dir):
            os.mkdir(media_dir)
        
        # Create subdirectories for different media types
        for subdir in ['photos', 'videos', 'documents', 'audio', 'voice']:
            subdir_path = os.path.join(media_dir, subdir)
            if not os.path.exists(subdir_path):
                os.mkdir(subdir_path)
    
    async def authenticate(self) -> TelegramClient:
        """
        Authenticate with Telegram using the bot token.
        
        Returns:
            Authenticated TelegramClient instance
        """
        self.setup_directories()
        
        try:
            session_path = os.path.join(self.base_path, self.bot_id)
            self.bot = await TelegramClient(session_path, API_ID, API_HASH, proxy=self.proxy).start(bot_token=self.bot_token)
            self.bot.id = self.bot_id
        except AccessTokenExpiredError:
            print(f"{Fore.RED}Token has expired!")
            sys.exit(1)
        
        me = await self.bot.get_me()
        self._print_bot_info(me)
        
        user = await self.bot(GetFullUserRequest(me))
        self.all_users[me.id] = user
        
        user_info = me.to_dict()
        user_info['token'] = self.bot_token
        
        with open(os.path.join(self.bot_id, 'bot.json'), 'w') as bot_info_file:
            json.dump(user_info, bot_info_file, indent=2)
        
        return self.bot
    
    @staticmethod
    def _print_bot_info(bot_info: Any) -> None:
        """Print bot information."""
        from utils import print_header
        print_header("Bot Information:")
        print(f"ID: {bot_info.id}")
        print(f"Name: {bot_info.first_name}")
        print(f"Username: @{bot_info.username} - https://t.me/{bot_info.username}")
    
    @staticmethod
    def _print_user_info(user_info: Any) -> None:
        """Print user information."""
        print("="*20 + f"\nNEW USER DETECTED: {user_info.id}")
        print(f"First name: {user_info.first_name}")
        print(f"Last name: {user_info.last_name}")
        if user_info.username:
            print(f"Username: @{user_info.username} - https://t.me/{user_info.username}")
        else:
            print("User has no username")
    
    def save_user_info(self, user: Any) -> None:
        """Save user information to disk."""
        user_id = str(user.id)
        self.setup_media_directories(user_id)
        
        user_file = os.path.join(self.base_path, user_id, f'{user_id}.json')
        json.dump(user.to_dict(), open(user_file, 'w'), indent=2)
    
    async def safe_api_request(self, coroutine, comment: str) -> Optional[Any]:
        """
        Safely execute an API request with error handling.
        
        Args:
            coroutine: The async operation to execute
            comment: Description of the operation for error messages
            
        Returns:
            Result of the operation or None on error
        """
        try:
            return await coroutine
        except RpcCallFailError as e:
            print(f"{Fore.RED}Telegram API error, {comment}: {str(e)}")
        except Exception as e:
            print(f"{Fore.RED}Error, {comment}: {str(e)}")
        return None
    
    async def save_user_photos(self, user: Any) -> None:
        """Save all photos from a user's profile."""
        user_id = str(user.id)
        user_dir = os.path.join(self.base_path, user_id)
        
        result = await self.safe_api_request(
            self.bot(GetUserPhotosRequest(user_id=user.id, offset=0, max_id=0, limit=100)),
            'get user photos'
        )
        
        if not result:
            return
        
        for photo in result.photos:
            print(f"Saving photo {photo.id}...")
            await self.safe_api_request(
                self.bot.download_file(photo, os.path.join(user_dir, f'{photo.id}.jpg')),
                'download user photo'
            )
    
    async def save_media_photo(self, chat_id: str, photo: Any) -> str:
        """Save a photo from a message."""
        photos_dir = os.path.join(self.base_path, chat_id, 'media', 'photos')
        filename = os.path.join(photos_dir, f'{photo.id}.jpg')
        await self.safe_api_request(
            self.bot.download_file(photo, filename),
            'download media photo'
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
                return f'{document.id}.{document.mime_type.split("/")[1]}'
        return f'{document.id}'
    
    async def save_media_document(self, chat_id: str, document: Any) -> str:
        """Save a document from a message."""
        # Determine document type
        doc_type = 'documents'
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeAudio):
                doc_type = 'voice' if attr.voice else 'audio'
            elif isinstance(attr, DocumentAttributeVideo):
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
            self.bot.download_file(document, full_path),
            'download file'
        )
        return f'media/{doc_type}/{filename}'
    
    def save_text_history(self, chat_id: str, messages: List[str]) -> None:
        """Append messages to text history file."""
        user_dir = os.path.join(self.base_path, str(chat_id))
        
        if not os.path.exists(user_dir):
            self.setup_media_directories(str(chat_id))
        
        history_filename = os.path.join(user_dir, f'{chat_id}_history.txt')
        with open(history_filename, 'a', encoding='utf-8') as text_file:
            text_file.write('\n'.join(messages) + '\n')
    
    def save_json_messages(self, chat_id: str, messages: List[Dict[str, Any]]) -> None:
        """Append messages to JSON history file."""
        user_dir = os.path.join(self.base_path, str(chat_id))
        json_filename = os.path.join(user_dir, f'{chat_id}_messages.json')
        
        # Load existing messages
        existing_messages = []
        if os.path.exists(json_filename):
            try:
                with open(json_filename, 'r', encoding='utf-8') as f:
                    existing_messages = json.load(f)
            except:
                existing_messages = []
        
        # Append new messages
        existing_messages.extend(messages)
        
        # Save back to file
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_messages, f, indent=2, ensure_ascii=False, default=str)
    
    def save_chats_text_history(self, immediate: bool = False) -> None:
        """Save all buffered chat histories."""
        current_time = datetime.now()
        time_since_save = (current_time - self.last_save_time).total_seconds()
        
        # Only save if immediate or enough time has passed
        if not immediate and time_since_save < self.AUTO_SAVE_INTERVAL:
            return
        
        for m_chat_id, messages_dict in self.messages_by_chat.items():
            if not messages_dict['buf']:
                continue
            
            print(f"{Fore.CYAN}Saving {len(messages_dict['buf'])} new messages for chat {m_chat_id}...")
            
            # Save text format
            text_messages = messages_dict['buf_text']
            self.save_text_history(m_chat_id, text_messages)
            
            # Save JSON format
            json_messages = messages_dict['buf_json']
            self.save_json_messages(m_chat_id, json_messages)
            
            # Update history and clear buffer
            messages_dict['history'].extend(text_messages)
            messages_dict['buf'] = []
            messages_dict['buf_text'] = []
            messages_dict['buf_json'] = []
        
        self.last_save_time = current_time
        
        self.save_statistics()
    
    def save_statistics(self) -> None:
        """Save chat statistics to file."""
        stats_file = os.path.join(self.base_path, 'statistics.json')
        
        # Calculate statistics
        total_stats = {
            'total_chats': len(self.messages_by_chat),
            'total_users': len(self.all_users),
            'total_messages': self.total_messages_processed,
            'chats': {}
        }
        
        for chat_id, data in self.messages_by_chat.items():
            chat_stats = self.stats.get(chat_id, {
                'messages': 0,
                'photos': 0,
                'videos': 0,
                'documents': 0,
                'audio': 0,
                'voice': 0,
                'locations': 0
            })
            total_stats['chats'][chat_id] = chat_stats
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(total_stats, f, indent=2)
    
    def update_stats(self, chat_id: str, media_type: str = 'messages') -> None:
        """Update statistics for a chat."""
        if chat_id not in self.stats:
            self.stats[chat_id] = {
                'messages': 0,
                'photos': 0,
                'videos': 0,
                'documents': 0,
                'audio': 0,
                'voice': 0,
                'locations': 0
            }
        
        self.stats[chat_id][media_type] = self.stats[chat_id].get(media_type, 0) + 1
    
    @staticmethod
    def get_chat_id(message: Any, bot_id: str) -> str:
        """Extract chat ID from a message."""
        m = message
        m_chat_id = "0"
        
        if isinstance(m.peer_id, PeerUser):
            if not m.to_id or not m.from_id:
                m_chat_id = str(m.peer_id.user_id)
            else:
                if m.from_id and int(m.from_id.user_id) == int(bot_id):
                    m_chat_id = str(m.to_id.user_id)
                else:
                    m_chat_id = str(m.from_id)
        elif isinstance(m.peer_id, PeerChat):
            m_chat_id = str(m.peer_id.chat_id)
        elif isinstance(m.peer_id, PeerChannel):
            m_chat_id = str(m.peer_id.channel_id)
        
        return m_chat_id
    
    @staticmethod
    def get_from_id(message: Any, bot_id: str) -> str:
        """Extract sender ID from a message."""
        m = message
        from_id = "0"
        
        if isinstance(m.peer_id, PeerUser):
            if not m.from_id:
                from_id = str(m.peer_id.user_id)
            else:
                from_id = str(m.from_id.user_id)
        elif isinstance(m.peer_id, PeerChat):
            from_id = str(m.from_id.user_id) if m.from_id else "0"
        elif isinstance(m.peer_id, PeerChannel):
            from_id = str(m.from_id.user_id) if m.from_id else "0"
        
        return from_id
    
    async def process_message(self, m: Any, empty_message_counter: int = 0) -> bool:
        """
        Process a single message.
        
        Args:
            m: Message object
            empty_message_counter: Counter for empty messages
            
        Returns:
            True if message is empty, False otherwise
        """
        m_chat_id = self.get_chat_id(m, self.bot.id)
        m_from_id = self.get_from_id(m, self.bot.id)
        is_from_user = m_chat_id == m_from_id
        
        if isinstance(m, MessageEmpty):
            return True
        
        # Ensure chat is initialized
        if m_chat_id not in self.messages_by_chat:
            self.messages_by_chat[m_chat_id] = {
                'buf': [],
                'buf_text': [],
                'buf_json': [],
                'history': []
            }
            self.setup_media_directories(m_chat_id)
            self.messages_since_zip[m_chat_id] = 0
            self.last_zip_time[m_chat_id] = datetime.now()
        
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
                message_text = f'Vcard: phone {m.media.phone_number}, {m.media.first_name} {m.media.last_name}'
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
        timestamp = m.date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create text format
        text = f'[{chat_type}][{m.id}][{m_from_id}→{m_chat_id}][{timestamp}] {message_text}'
        print(f"{Fore.GREEN if chat_type == 'Private' else Fore.CYAN if chat_type == 'Group' else Fore.MAGENTA}{text}")
        
        # Create JSON format with more metadata
        json_message = {
            'id': m.id,
            'from_id': m_from_id,
            'chat_id': m_chat_id,
            'chat_type': chat_type,
            'date': timestamp,
            'timestamp': int(m.date.timestamp()),
            'text': m.message if m.message else '',
            'media_type': media_type,
            'media_path': media_path,
            'is_reply': bool(m.reply_to),
            'reply_to_msg_id': m.reply_to.reply_to_msg_id if m.reply_to else None,
            'is_forward': bool(m.fwd_from),
            'forward_from': str(m.fwd_from) if m.fwd_from else None,
            'edit_date': m.edit_date.strftime('%Y-%m-%d %H:%M:%S') if m.edit_date else None
        }
        
        # Add to buffers
        self.messages_by_chat[m_chat_id]['buf'].append(m)
        self.messages_by_chat[m_chat_id]['buf_text'].append(text)
        self.messages_by_chat[m_chat_id]['buf_json'].append(json_message)
        
        # Update statistics
        self.update_stats(m_chat_id, media_type if media_type else 'messages')
        self.total_messages_processed += 1
        
        self.messages_since_zip[m_chat_id] = self.messages_since_zip.get(m_chat_id, 0) + 1
        
        # Save user info if new user
        if is_from_user and m_from_id and m_from_id not in self.all_users:
            try:
                user = await self.bot.get_entity(int(m_from_id))
                self._print_user_info(user)
                self.save_user_info(user)
                await self.save_user_photos(user)
                self.all_users[m_from_id] = user
            except Exception as e:
                print(f"{Fore.RED}Error getting user info for {m_from_id}: {str(e)}")
        
        self.save_chats_text_history()
        
        return False
    
    async def get_chat_history(self, from_id: int = 0, to_id: int = 0, lookahead: int = 0) -> None:
        """
        Recursively dump chat history.
        
        Args:
            from_id: Starting message ID
            to_id: Ending message ID
            lookahead: Additional cycles to process
        """
        print(f'{Fore.YELLOW}Dumping history from {from_id} to {to_id}... (Total processed: {self.total_messages_processed})')
        
        messages = await self.bot(GetMessagesRequest(list(range(to_id, from_id))))
        empty_message_counter = 0
        history_tail = True
        
        for m in messages.messages:
            is_empty = await self.process_message(m, empty_message_counter)
            if is_empty:
                empty_message_counter += 1
            else:
                history_tail = False
        
        if empty_message_counter:
            print(f'Empty messages x{empty_message_counter}')
            history_tail = True
        
        # Force save after each batch
        self.save_chats_text_history(immediate=True)
        
        if not history_tail:
            return await self.get_chat_history(from_id + HISTORY_DUMP_STEP, to_id + HISTORY_DUMP_STEP, lookahead)
        else:
            if lookahead:
                return await self.get_chat_history(from_id + HISTORY_DUMP_STEP, to_id + HISTORY_DUMP_STEP, lookahead - 1)
            else:
                print(f"{Fore.GREEN}History was fully dumped. Total messages: {self.total_messages_processed}")
                self.print_final_statistics()
                return None
    
    def print_final_statistics(self) -> None:
        """Print final statistics after dumping."""
        print(f"\n{Fore.CYAN}{'='*50}")
        print(f"{Fore.CYAN}DUMP STATISTICS")
        print(f"{Fore.CYAN}{'='*50}")
        print(f"{Fore.GREEN}Total Chats: {len(self.messages_by_chat)}")
        print(f"{Fore.GREEN}Total Users: {len(self.all_users)}")
        print(f"{Fore.GREEN}Total Messages: {self.total_messages_processed}")
        
        for chat_id, stats in self.stats.items():
            print(f"\n{Fore.YELLOW}Chat {chat_id}:")
            for key, value in stats.items():
                if value > 0:
                    print(f"  {key}: {value}")
        
        print(f"{Fore.CYAN}{'='*50}\n")
    
    def setup_message_listener(self) -> None:
        """Set up event listener for new messages."""
        @self.bot.on(events.NewMessage)
        async def save_new_user_history(event):
            try:
                # Get chat and user info
                chat_id = str(event.chat_id) if event.chat_id else self.get_chat_id(event.message, self.bot.id)
                user = event.message.sender
                
                # Determine chat type
                chat_type = 'Private'
                if isinstance(event.message.peer_id, PeerChat):
                    chat_type = 'Group'
                elif isinstance(event.message.peer_id, PeerChannel):
                    chat_type = 'Channel'
                
                # Initialize chat if new
                if chat_id not in self.all_chats:
                    self.all_chats[chat_id] = event.message.input_chat
                    self.messages_by_chat[chat_id] = {
                        'history': [],
                        'buf': [],
                        'buf_text': [],
                        'buf_json': []
                    }
                    self.messages_since_zip[chat_id] = 0
                    self.last_zip_time[chat_id] = datetime.now()
                    
                    print('='*50)
                    print(f'{Fore.GREEN}NEW {chat_type.upper()} DETECTED: {chat_id}')
                    
                    # Save chat info to JSON
                    chat_info = {
                        'chat_id': chat_id,
                        'chat_type': chat_type,
                        'detected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    # Try to get chat entity for more info
                    try:
                        chat_entity = await self.bot.get_entity(int(chat_id))
                        if hasattr(chat_entity, 'title'):
                            chat_info['title'] = chat_entity.title
                            print(f'{Fore.YELLOW}Chat Title: {chat_entity.title}')
                        if hasattr(chat_entity, 'username'):
                            chat_info['username'] = chat_entity.username
                            print(f'{Fore.YELLOW}Chat Username: @{chat_entity.username}')
                    except:
                        pass
                    
                    # Save chat info
                    self.setup_media_directories(chat_id)
                    chat_info_file = os.path.join(self.base_path, chat_id, 'chat_info.json')
                    with open(chat_info_file, 'w', encoding='utf-8') as f:
                        json.dump(chat_info, f, indent=2)
                    
                    print('='*50)
                    
                    # Save user info if new
                    if user and user.id not in self.all_users:
                        self._print_user_info(user)
                        self.save_user_info(user)
                        await self.save_user_photos(user)
                        self.all_users[user.id] = user
                
                # Process and immediately save the message
                await self.process_message(event.message)
                self.save_chats_text_history(immediate=True)
                
            except Exception as e:
                print(f"{Fore.RED}Error in message handler: {str(e)}")
                import traceback
                traceback.print_exc()
        
        @self.bot.on(events.MessageEdited)
        async def handle_message_edit(event):
            try:
                chat_id = str(event.chat_id) if event.chat_id else self.get_chat_id(event.message, self.bot.id)
                print(f"{Fore.MAGENTA}[EDIT] Message {event.message.id} in chat {chat_id} was edited")
                
                # Save the edited version
                await self.process_message(event.message)
                self.save_chats_text_history(immediate=True)
            except Exception as e:
                print(f"{Fore.RED}Error handling message edit: {str(e)}")
    
    def create_chat_zip(self, chat_id: str) -> Optional[str]:
        """
        Create a zip file containing all data for a specific chat.
        
        Args:
            chat_id: Chat ID to create zip for
            
        Returns:
            Path to created zip file or None on error
        """
        try:
            chat_dir = os.path.join(self.base_path, chat_id)
            if not os.path.exists(chat_dir):
                return None
            
            # Create zips directory if it doesn't exist
            zips_dir = os.path.join(self.base_path, 'zips')
            if not os.path.exists(zips_dir):
                os.makedirs(zips_dir)
            
            # Create zip filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            zip_filename = f'chat_{chat_id}_{timestamp}.zip'
            zip_path = os.path.join(zips_dir, zip_filename)
            
            # Create zip file
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Walk through chat directory and add all files
                for root, dirs, files in os.walk(chat_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.base_path)
                        zipf.write(file_path, arcname)
            
            file_size = os.path.getsize(zip_path) / 1024  # KB
            print(f"{Fore.CYAN}✓ Created zip archive: {zip_filename} ({file_size:.2f} KB)")
            
            return zip_path
            
        except Exception as e:
            print(f"{Fore.RED}Error creating zip for chat {chat_id}: {str(e)}")
            return None
    
    async def check_and_create_zips(self) -> None:
        """Check if any chats need zip creation and forward them."""
        current_time = datetime.now()
        
        for chat_id in list(self.messages_by_chat.keys()):
            should_create_zip = False
            
            # Check message count threshold
            if self.messages_since_zip.get(chat_id, 0) >= ZIP_INTERVAL_MESSAGES:
                should_create_zip = True
                print(f"{Fore.YELLOW}Chat {chat_id} reached {ZIP_INTERVAL_MESSAGES} messages, creating zip...")
            
            # Check time threshold
            last_zip = self.last_zip_time.get(chat_id)
            if last_zip:
                seconds_since_zip = (current_time - last_zip).total_seconds()
                if seconds_since_zip >= ZIP_INTERVAL_SECONDS:
                    should_create_zip = True
                    print(f"{Fore.YELLOW}Chat {chat_id} reached time threshold, creating zip...")
            elif self.messages_since_zip.get(chat_id, 0) > 0:
                # First zip for this chat
                should_create_zip = True
            
            if should_create_zip:
                # Create zip file
                zip_path = self.create_chat_zip(chat_id)
                
                if zip_path:
                    # Forward to configured channels
                    message_count = self.messages_since_zip.get(chat_id, 0)
                    await self.forwarder.forward_zip_file(zip_path, chat_id, message_count)
                    
                    # Clean up zip file if configured
                    if ZIP_CLEANUP_AFTER_SEND:
                        try:
                            os.remove(zip_path)
                            print(f"{Fore.CYAN}✓ Cleaned up zip file: {os.path.basename(zip_path)}")
                        except Exception as e:
                            print(f"{Fore.YELLOW}Could not delete zip file: {str(e)}")
                    
                    # Reset counters
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
                print(f"{Fore.RED}Error in zip creation loop: {str(e)}")


async def dump_bot_history(
    bot_token: str, 
    listen_only: bool = False, 
    lookahead: int = LOOKAHEAD_STEP_COUNT, 
    proxy: Optional[tuple] = None,
    forward_to_telegram: Optional[str] = None,
    forward_to_discord: Optional[str] = None
) -> None:
    """
    Main function to dump bot history and listen for new messages.
    
    Args:
        bot_token: Telegram bot token
        listen_only: If True, skip history dumping and only listen for new messages
        lookahead: Additional cycles to skip empty messages
        proxy: Optional proxy configuration
        forward_to_telegram: Optional Telegram channel ID to forward messages to
        forward_to_discord: Optional Discord webhook URL to forward messages to
    """
    dumper = BotDumper(bot_token, proxy)
    bot = await dumper.authenticate()
    
    if forward_to_telegram:
        dumper.forwarder.setup_telegram_forwarding(bot, forward_to_telegram)
    
    if forward_to_discord:
        dumper.forwarder.setup_discord_forwarding(forward_to_discord)
    
    if listen_only:
        print(f"{Fore.YELLOW}Bot history dumping disabled, switching to listen mode...")
    else:
        await dumper.get_chat_history(from_id=HISTORY_DUMP_STEP, to_id=0, lookahead=lookahead)
    
    dumper.setup_message_listener()
    
    dumper.zip_task = asyncio.create_task(dumper.zip_creation_loop())
    
    print(f"{Fore.GREEN}{'='*50}")
    print(f"{Fore.GREEN}Listening for new messages in real-time...")
    print(f"{Fore.GREEN}All messages will be saved immediately.")
    if dumper.forwarder.telegram_enabled or dumper.forwarder.discord_enabled:
        print(f"{Fore.CYAN}Zip archives will be created and forwarded:")
        print(f"{Fore.CYAN}  - Every {ZIP_INTERVAL_MESSAGES} messages")
        print(f"{Fore.CYAN}  - Every {ZIP_INTERVAL_SECONDS} seconds ({ZIP_INTERVAL_SECONDS // 60} minutes)")
        if dumper.forwarder.telegram_enabled:
            print(f"{Fore.CYAN}  - To Telegram channel")
        if dumper.forwarder.discord_enabled:
            print(f"{Fore.CYAN}  - To Discord webhook")
    print(f"{Fore.YELLOW}")
    print(f"{Fore.YELLOW}IMPORTANT: For group messages to be captured, the bot must:")
    print(f"{Fore.YELLOW}1. Be added to the group as a member")
    print(f"{Fore.YELLOW}2. Have 'Privacy Mode' disabled in @BotFather")
    print(f"{Fore.YELLOW}   (Use /setprivacy command in BotFather)")
    print(f"{Fore.YELLOW}")
    print(f"{Fore.GREEN}Press Ctrl+C to stop.")
    print(f"{Fore.GREEN}{'='*50}\n")
    
    try:
        await bot.run_until_disconnected()
    finally:
        if dumper.zip_task:
            dumper.zip_task.cancel()
            try:
                await dumper.zip_task
            except asyncio.CancelledError:
                pass
