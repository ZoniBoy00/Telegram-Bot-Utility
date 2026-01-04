"""Configuration constants for Telegram Bot Utility."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Telegram API Configuration
TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# Telethon API Configuration (Get these from my.telegram.org)
# Priority: Env Var > Hardcoded Default
API_ID = int(os.getenv('API_ID', 123456))
API_HASH = os.getenv('API_HASH', 'your_api_hash_here')

# File Type Extensions
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')
GIF_EXTENSION = '.gif'

# Network Configuration
CHUNK_SIZE = 1024
REQUEST_TIMEOUT = 30

# History Dumping Configuration
HISTORY_DUMP_STEP = 200  # Messages count per cycle
LOOKAHEAD_STEP_COUNT = 0  # Additional cycles to skip empty messages

# Zip Compression Configuration
ZIP_INTERVAL_MESSAGES = 50  # Create zip after this many messages per chat
ZIP_INTERVAL_SECONDS = 300  # Or create zip after this many seconds (5 minutes)
ZIP_CLEANUP_AFTER_SEND = True  # Delete zip files after successful send
