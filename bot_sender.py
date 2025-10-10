"""Module for sending messages and media via Telegram Bot API."""

import os
import time
import requests
from typing import Optional
from colorama import Fore

from config import TELEGRAM_API_BASE, IMAGE_EXTENSIONS, GIF_EXTENSION, CHUNK_SIZE, REQUEST_TIMEOUT


def download_image(image_url: str) -> Optional[str]:
    """
    Downloads an image or GIF from the provided URL.
    
    Args:
        image_url: The URL of the image to download
        
    Returns:
        The filename if successful, otherwise None
    """
    try:
        response = requests.get(image_url, stream=True, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        filename = image_url.split("/")[-1].split("?")[0]
        if not filename:
            filename = "downloaded_media"
            
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:
                    file.write(chunk)
        
        print(f"{Fore.GREEN}Downloaded: {filename}")
        return filename
        
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error downloading image: {e}")
        return None


def is_gif(filename: str) -> bool:
    """Check if the file is a GIF."""
    return filename.lower().endswith(GIF_EXTENSION)


def is_image(filename: str) -> bool:
    """Check if the file is a standard image format."""
    return any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)


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
    with open(image_path, 'rb') as f:
        payload = {'chat_id': chat_id, 'caption': message}
        
        if is_gif(image_path):
            files = {'animation': f}
            return requests.post(f"{base_url}sendAnimation", data=payload, files=files, timeout=REQUEST_TIMEOUT)
        elif is_image(image_path):
            files = {'photo': f}
            return requests.post(f"{base_url}sendPhoto", data=payload, files=files, timeout=REQUEST_TIMEOUT)
        else:
            files = {'document': f}
            return requests.post(f"{base_url}sendDocument", data=payload, files=files, timeout=REQUEST_TIMEOUT)


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
    return requests.post(f"{base_url}sendMessage", data=payload, timeout=REQUEST_TIMEOUT)


def spam_with_token(
    token: str,
    chat_id: int,
    message: str,
    count: int,
    delay: float,
    image_path: Optional[str] = None
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

    for i in range(count):
        try:
            if image_path and os.path.exists(image_path):
                response = send_media_message(base_url, chat_id, message, image_path)
            else:
                response = send_text_message(base_url, chat_id, message)

            if response.status_code == 200:
                print(f"{Fore.GREEN}Message {i+1}/{count} sent successfully.")
            else:
                error_data = response.json()
                error_msg = error_data.get('description', response.text)
                print(f"{Fore.RED}Failed to send message {i+1}/{count}. Error: {error_msg}")
                
        except requests.exceptions.Timeout:
            print(f"{Fore.RED}Timeout sending message {i+1}/{count}.")
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Error sending message {i+1}/{count}: {e}")
        except Exception as e:
            print(f"{Fore.RED}Unexpected error sending message {i+1}/{count}: {e}")

        if i < count - 1:  # Don't delay after the last message
            time.sleep(delay)

    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
            print(f"{Fore.GREEN}Temporary file deleted: {image_path}")
        except OSError as e:
            print(f"{Fore.RED}Could not delete file {image_path}: {e}")


def list_chats(token: str) -> None:
    """
    Lists all chats where the bot has received messages.
    
    Args:
        token: Bot token
    """
    url = f"{TELEGRAM_API_BASE}{token}/getUpdates"
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        updates = response.json().get('result', [])
        chats = {}
        
        for update in updates:
            message = update.get('message') or update.get('channel_post')
            if message:
                chat = message.get('chat', {})
                chat_id = chat.get('id')
                chat_title = chat.get('title') or chat.get('username') or chat.get('first_name', 'Unknown')
                chat_type = chat.get('type', 'unknown')
                chats[chat_id] = {'title': chat_title, 'type': chat_type}
        
        if chats:
            from utils import print_header
            print_header("Chats where the bot has received messages:")
            for chat_id, info in chats.items():
                print(f"{Fore.WHITE}ID: {chat_id} | Name: {info['title']} | Type: {info['type']}")
        else:
            print(f"{Fore.YELLOW}No chats found. The bot needs to receive at least one message first.")
            
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error retrieving chat list: {e}")


def get_bot_info(token: str) -> None:
    """
    Retrieves and displays information about the bot.
    
    Args:
        token: Bot token
    """
    try:
        response = requests.get(f"{TELEGRAM_API_BASE}{token}/getMe", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        bot = response.json().get('result', {})
        
        from utils import print_header
        print_header("Bot Information:")
        print(f"Username: @{bot.get('username', 'N/A')}")
        print(f"First Name: {bot.get('first_name', 'N/A')}")
        print(f"ID: {bot.get('id', 'N/A')}")
        print(f"Is Bot: {bot.get('is_bot', False)}")
        print(f"Can Join Groups: {bot.get('can_join_groups', False)}")
        print(f"Can Read All Group Messages: {bot.get('can_read_all_group_messages', False)}")
        print(f"Supports Inline Queries: {bot.get('supports_inline_queries', False)}")
        from utils import print_separator
        print_separator()
        
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error retrieving bot info: {e}")
