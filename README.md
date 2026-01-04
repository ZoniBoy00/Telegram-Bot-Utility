# Telegram Bot Utility 

![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)

A professional-grade, terminal-based utility for managing, monitoring, and analyzing Telegram bots. Designed for developers and power users, this tool combines a sleek **Rich** text interface with the powerful **Telethon** library to offer capabilities far beyond standard bot management.

---

## ✨ Key Features

### 📡 1. Advanced Message Broadcasting (Spam)
*   **Universal Targeting**: Send messages to any chat ID (User, Group, or Channel).
*   **Rich Media Support**: unparalleled support for sending:
    *   📸 **Photos** (JPG, PNG)
    *   🎥 **Videos** (MP4, AVI)
    *   📄 **Documents** (PDF, ZIP, TXT)
    *   🎞️ **GIFs**
*   **Smart Automation**:
    *   **Auto-Download**: Paste a URL to an image/file, and the bot will automatically download and send it.
    *   **Looping**: Configurable message counts and delays to bypass flood waits.

### 🔍 2. Deep Bot Analysis
*   **Token Verification**: Instantly validate bot tokens.
*   **Capability Audit**: View permissions (Group status, Privacy mode, Inline capabilities).
*   **Identity Check**: Retrieve absolute Bot IDs and Usernames.

### 📂 3. Intelligent Chat Discovery
*   **Active Session Listing**: Instantly fetch a list of all chats where the bot is currently active or has received messages.
*   **Type Sorting**: Clearly distinguishes between Private DMs, Groups, and Channels.

### 💾 4. The Ultimate Dumper (History & Media)
Turn your bot into a surveillance and archiving machine.
*   **Full History Extraction**: Scrapes every accessible message from target chats.
*   **Live Monitoring Dashboard**: Watch messages arrive in real-time with a color-coded feed:
    *   🟢 **Green**: Direct Messages
    *   🔵 **Blue**: Group/Supergroup Activity
    *   🟣 **Magenta**: Channel Broadcasts
    *   🟡 **Yellow**: System Events
*   **Smart Media Sorter**: Automatically categorizes downloads into specific folders:
    *   `media/photos/`
    *   `media/videos/`
    *   `media/documents/`
    *   `media/voice/`
    *   `media/gifs/` (Auto-detected)
    *   `media/stickers/` (Auto-detected)
*   **Metadata Archival**: Saves user profiles, IDs, names, and profile photos for every interaction.

### 🚀 5. Automated Forwarding & Backup
*   **Cross-Platform Relaying**:
    *   **Discord Webhooks**: Stream text and media events directly to a Discord channel.
    *   **Telegram Mirroring**: Forward all incoming content to a secure "Backup Channel" on Telegram.
*   **Archive Compression**: Regularly zips chat logs and media (every 50 messages or 5 minutes) and uploads them to your backup destinations.
*   **Non-Blocking Performance**: Heavy uploads are handled in background threads to ensure the bot never misses a message while uploading.

---

## �️ Installation & Setup

### Prerequisites
*   Python 3.9 or higher
*   A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Step 1: Clone & Install
```bash
# Clone the repository
git clone https://github.com/yourusername/Telegram-Bot-Utility.git
cd Telegram-Bot-Utility

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configuration
You can run the tool immediately, but for **Advanced Features** (Dumping/Forwarding), you need to configure your environment.

1.  Open `core/config.py` (or create a `.env` file).
2.  **Required for Dumper**: Get your personal API credentials from [my.telegram.org](https://my.telegram.org).
    ```python
    # In core/config.py
    API_ID = 123456
    API_HASH = 'your_api_hash_here'
    ```
3.  **Optional for Forwarding**:
    ```python
    DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/...'
    FORWARD_CHANNEL_ID = -100123456789  # Your backup channel ID
    ```

---

## �️ Usage Guide

Run the application:
```bash
python main.py
```

### The Interface
The tool features a new **Premium Dashboard** UI:
*   **Navigation**: Use number keys `1-5` to select modes.
*   **Inputs**: Paste tokens and IDs freely. The input fields are validated and visible (no asterisk masking) for easier verification.
*   **Exit**: Use option `5` or press `Ctrl+C` to quit safely.

### Mode Specifics

#### ➤ Mode 4: Dump Bot History
This is the most powerful feature. When launched:
1.  The bot initializes a **Telethon** client.
2.  It asks for the target Chat ID (or `all` to monitor everything).
3.  It creates a session file `bot_session.session`.
4.  It begins listening. **New messages appear instantly** in the console.
5.  Data is auto-saved every 30 seconds to `stats.json`.

---

## 📂 Data Structure
The tool keeps your workspace clean by organizing data hierarchically:

```bash
Telegram-Bot-Utility/
├── <Bot_ID>/                   # Main folder for the specific bot
│   ├── bot.json                # Bot details
│   ├── statistics.json         # Global message counters
│   ├── zips/                   # Archives created by the forwarder
│   └── <Chat_ID>/              # Folder for a specific chat/user
│       ├── chat_history.txt    # Human-readable log
│       ├── messages.json       # Machine-readable JSON dump
│       ├── <user_id>.json      # User profile data
│       ├── <photo_id>.jpg      # User profile picture
│       └── media/              # Downloaded media
│           ├── photos/
│           ├── videos/
│           ├── stickers/       # .webp files
│           └── ...
```

---

## ❓ Troubleshooting & FAQ

**Q: "No chats found" in List Chats mode?**
> A: The bot can only see chats where it has received at least one message since its last reboot/update or where it is an active admin. Send a message to the bot and try again.

**Q: Group messages are not appearing in the Dumper?**
> A: **Privacy Mode** is likely enabled.
> 1. Go to @BotFather.
> 2. Select your bot > Bot Settings > Group Privacy.
> 3. Turn it **OFF**.
> 4. Alternatively, make the bot an **Admin** in the group.

**Q: Discord forwarding isn't working?**
> A: Check your `DISCORD_WEBHOOK_URL` in `config.py`. Ensure the bot machine has internet access and isn't blocking outgoing requests to Discord.

**Q: I get a "Session" error?**
> A: Delete the `<bot_id>.session` file in the bot's folder and restart the tool to re-authenticate.

---

## ⚠️ Disclaimer
This tool is intended for **educational and administrative purposes only**. You are responsible for ensuring that your use of this tool (including message dumping and spamming) complies with Telegram's Terms of Service and applicable privacy laws in your jurisdiction.

---

## � License
MIT License. Free for personal and commercial use.
