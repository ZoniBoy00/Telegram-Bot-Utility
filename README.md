# Telegram Bot Utility

A comprehensive Python utility for managing, monitoring, and interacting with Telegram bots. This tool provides advanced features for message sending, history dumping, real-time monitoring, and automatic forwarding to external channels.

## ✨ Features

### 1. 📤 Send Messages (Spam)
- Send text messages to any chat
- Send images, GIFs, or documents with captions
- Configurable message count and delay
- Automatic media download from URLs
- Support for multiple media types

### 2. 🤖 Get Bot Info
- Display detailed bot information
- View bot capabilities and permissions
- Check bot username and ID
- Verify bot configuration

### 3. 💬 List Chats
- View all chats where the bot has received messages
- Display chat IDs, names, and types
- Useful for finding chat IDs for messaging
- Quick and simple (no additional setup required)

### 4. 📊 Dump Bot History (Advanced)
- **Complete Message History**: Extract all messages from bot conversations
- **Real-Time Monitoring**: Listen for new messages with color-coded console output
  - 🟢 Green: Private messages
  - 🔵 Cyan: Group messages
  - 🟣 Magenta: Channel messages
- **User Profiles**: Save user information and profile photos
- **Media Download**: Automatically download photos, documents, and videos
- **Organized Storage**: Separate directories for different media types
- **JSON Export**: All data exported in JSON format for easy parsing
- **Statistics Tracking**: Message counts, media counts, and user analytics
- **Auto-Save**: Periodic automatic saving every 30 seconds
- **Message Metadata**: Track edits, replies, forwards, and deletions

### 5. 🚀 Message Forwarding (NEW!)
- **Telegram Channel Forwarding**: Send all captured messages to your Telegram channel
- **Discord Webhook Integration**: Forward messages to Discord channels
- **Zip Compression**: Automatically compress and send chat archives
  - Configurable thresholds (every 50 messages or 5 minutes)
  - Includes messages, media, and metadata
  - Optional automatic cleanup after forwarding
- **Real-Time Updates**: Messages forwarded as they arrive
- **Flexible Configuration**: Enable/disable forwarding per session

## 📦 Installation

1. **Clone or download this repository**

2. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API credentials** (for advanced features):
   - See [Configuration](#configuration) section below

## ⚙️ Configuration

### For Basic Features (Options 1-3)
No additional configuration needed. Just have your bot token ready.

### For Advanced Features (Options 4-5)

#### Telegram API Credentials
Required for bot history dumping and monitoring:

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Navigate to "API development tools"
4. Create a new application
5. Copy your `API_ID` and `API_HASH`
6. Update these values in `config.py`:

```python
API_ID = your_api_id_here
API_HASH = 'your_api_hash_here'
```

#### Message Forwarding Setup (Optional)
See [FORWARDING_GUIDE.md](FORWARDING_GUIDE.md) for detailed instructions on:
- Setting up Telegram channel forwarding
- Configuring Discord webhooks
- Customizing zip compression settings

## 🚀 Usage

Run the main script:

```bash
python telegram_bot_utility.py
```

Follow the interactive menu to select your desired operation.

### Menu Options

```
1. Send Messages (Spam)           - Send messages/media to chats
2. Get Bot Info                   - Display bot information
3. List Chats                     - View all accessible chats
4. Dump Bot History (Advanced)    - Monitor and save all messages
5. Exit                           - Close the application
```

## 📁 Project Structure

```
TelegramBotUtility/
├── telegram_bot_utility.py  # Main entry point with interactive menu
├── config.py                # Configuration constants and settings
├── utils.py                 # Shared utility functions
├── bot_sender.py            # Message/media sending functionality
├── bot_dumper.py            # History dumping and real-time monitoring
├── forwarder.py             # Message forwarding to external channels
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── CHANGELOG.md            # Version history and updates
├── FORWARDING_GUIDE.md     # Detailed forwarding setup guide
└── LICENSE                 # License information
```

## 📂 Output Structure (History Dumping)

When dumping bot history, the tool creates the following structure:

```
<bot_id>/
├── bot.json                           # Bot information and metadata
├── <bot_id>.session                   # Telethon session file
├── statistics.json                    # Overall statistics
├── zips/                              # Compressed archives (if forwarding enabled)
│   └── chat_<chat_id>_<timestamp>.zip
└── <chat_id>/
    ├── <chat_id>.json                 # Chat information
    ├── <chat_id>_history.txt          # Human-readable chat history
    ├── <chat_id>_messages.json        # Machine-readable message data
    ├── <chat_id>_statistics.json      # Chat-specific statistics
    ├── <user_id>.json                 # User information
    ├── <photo_id>.jpg                 # User profile photos
    └── media/
        ├── photos/                    # Downloaded photos
        ├── videos/                    # Downloaded videos
        └── documents/                 # Downloaded documents
```

## 🔧 Module Breakdown

### `config.py`
Configuration constants including:
- API endpoints and credentials
- File extensions and paths
- Forwarding settings
- Zip compression thresholds
- Auto-save intervals

### `utils.py`
Shared utility functions:
- Console management (clearing, colors)
- Input validation
- Formatting helpers
- Cross-platform compatibility

### `bot_sender.py`
Message and media sending operations:
- Text message sending with retry logic
- Media upload and sending
- Image/GIF download from URLs
- Chat listing via Bot API
- Bot info retrieval

### `bot_dumper.py`
Advanced monitoring and dumping:
- Complete message history extraction
- Real-time message listening with color-coded output
- User profile and photo saving
- Media file downloading with organization
- JSON export of all data
- Statistics tracking and reporting
- Auto-save mechanism
- Zip compression for forwarding

### `forwarder.py`
External channel forwarding:
- Telegram channel message forwarding
- Discord webhook integration
- Zip file creation and sending
- Automatic cleanup management
- Error handling and retry logic

### `telegram_bot_utility.py`
Main application:
- Interactive menu system
- User input handling
- Module coordination
- Error handling and logging

## 📋 Requirements

- Python 3.7+
- requests
- colorama
- telethon (for history dumping)
- PySocks (optional, for proxy support)
- discord-webhook (for Discord forwarding)

## 💡 How to Get Chat IDs

Use **Option 3: List Chats** to get chat IDs where your bot is active:
- Uses the basic Bot API (no additional setup required)
- Shows chats where the bot has received at least one message
- Displays chat IDs, names, and types
- Quick and simple way to find chat IDs for messaging

**Note:** The bot must have received at least one message in a chat for it to appear in the list.

## ⚠️ Important Notes

### Privacy Mode for Group Messages
For the bot to receive **all messages** in groups (not just mentions and commands):
1. Open BotFather in Telegram
2. Send `/mybots`
3. Select your bot
4. Go to "Bot Settings" → "Group Privacy"
5. **Disable** Privacy Mode

Without this, the bot will only receive:
- Direct messages
- Messages that mention the bot (@botname)
- Commands (starting with /)

### Rate Limits
- Respect Telegram's rate limits when sending messages
- The tool includes automatic delays to prevent rate limiting
- Adjust delays in `config.py` if needed

### Data Security
- Keep your bot token secure
- Never commit API credentials to version control
- Store dumped data securely (contains sensitive information)
- Be cautious when forwarding messages to external channels

## 🐛 Troubleshooting

### "No chats found" when using List Chats
- The bot needs to receive at least one message in a chat to detect it
- Make sure you're using the correct bot token
- Try sending a message to the bot first

### Group messages not being captured
- Check if Privacy Mode is disabled in BotFather (see Important Notes)
- Verify the bot is actually a member of the group
- Check console output for error messages

### AttributeError with Telethon
- Make sure you have the latest version: `pip install --upgrade telethon`
- Check that API_ID and API_HASH are correctly set in `config.py`

### Permission errors on Windows
- Run the script with administrator privileges if needed
- Close any programs that might be accessing the bot's directory
- Check antivirus software isn't blocking file operations

### Zip files not being sent
- Check file size limits (Telegram: 50MB, Discord: 8MB free/25MB Nitro)
- Verify forwarding credentials are correct
- Check console output for specific error messages

## 📄 License

See LICENSE file for details.

## 🙏 Credits

- Built with [Telethon](https://github.com/LonamiWebs/Telethon)
- Inspired by various Telegram bot analysis tools
- Community contributions and feedback

## 📞 Support

For issues, questions, or contributions:
1. Review the [FORWARDING_GUIDE.md](FORWARDING_GUIDE.md) for forwarding setup
2. Check existing issues on GitHub
3. Create a new issue with detailed information
