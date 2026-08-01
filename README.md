# Telegram Bot Utility

![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)

A terminal-based utility for managing, monitoring, and analyzing Telegram bots. It combines a sleek **Rich** text interface with the powerful **Telethon** library to offer capabilities far beyond standard bot management.

---

## Features

### 1. Message Broadcasting
- **Universal Targeting**: Send messages to any chat ID (User, Group, or Channel).
- **Rich Media Support**:
  - Photos (JPG, PNG)
  - Videos (MP4, AVI)
  - Documents (PDF, ZIP, TXT)
  - GIFs
- **Smart Automation**:
  - **Auto-Download**: Paste a URL to an image/file, and the bot downloads and sends it (with content-type and size validation). Downloads go to a temporary folder, never the working directory, and are deleted after sending.
  - **Looping**: Configurable message counts and delays.
  - **Flood-Wait Handling**: HTTP 429 responses are detected and the retry time is honored automatically.

### 2. Bot Analysis
- **Token Verification**: Instantly validate bot tokens.
- **Capability Audit**: View permissions (Group status, Privacy mode, Inline capabilities).
- **Identity Check**: Retrieve Bot IDs and Usernames.

### 3. Chat Discovery
- **Active Session Listing**: Fetch a list of all chats where the bot is active.
- **Type Sorting**: Distinguishes between Private DMs, Groups, and Channels.
- **Send From List**: Pick a discovered chat and send a message to it right from the list.
- **Chat ID Finder**: Look up a chat by numeric ID, `@username` or `t.me` link
  and get its ID in a copyable form (works for channels/supergroups the bot
  has joined; users are resolved by numeric ID from List Chats).

### 4. The Dumper (History & Media)
- **History Extraction**: Bots cannot fetch full chat history via MTProto
  (Telegram restriction), so the dumper saves recent messages from the Bot API
  update queue and then monitors live. For full history, use the tool with a
  user account (Telethon supports it — the `--chat` path tries MTProto first).
- **Live Monitoring**: Watch messages arrive in real-time with a color-coded feed:
  - Green: Direct Messages
  - Cyan: Group/Supergroup Activity
  - Magenta: Channel Broadcasts
- **Smart Media Sorter**: Automatically categorizes downloads:
  - `media/photos/`, `media/videos/`, `media/documents/`
  - `media/voice/`, `media/gifs/`, `media/stickers/`, `media/audio/`
- **Metadata Archival**: Saves user profiles, IDs, names, and profile photos (downloaded in the background so the event loop stays responsive).
- **Deduplication**: The same message is never saved twice, and edits are recorded as separate `edited` events.
- **Storage**: Messages are appended to `messages.jsonl` (one JSON object per line) — fast and scalable for large archives.

### 5. Forwarding & Backup
- **Cross-Platform Relaying**:
  - **Discord Webhooks**: Stream text and media events directly to a Discord channel.
  - **Telegram Mirroring**: Forward messages (and archives) to a backup channel on Telegram.
- **Archive Compression**: Creates incremental zip archives (only new/changed files) every 50 messages or 5 minutes and uploads them to your backup destinations.
- **Non-Blocking Performance**: Heavy uploads run in background threads/tasks so the bot never misses a message.

### 6. History Search
- Search all dumped archives for a term and get instant, colored results across bots and chats.

---

## Installation & Setup

### Prerequisites
- Python 3.9 or higher
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Step 1: Install
```bash
git clone https://github.com/yourusername/Telegram-Bot-Utility.git
cd Telegram-Bot-Utility

# Option A: editable install (recommended)
pip install -e .

# Option B: just the requirements
pip install -r requirements.txt
```

### Step 2: Configure
Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

**Required for the Dumper** — get your personal API credentials from [my.telegram.org](https://my.telegram.org):

```
API_ID=123456
API_HASH=your_api_hash_here
```

All settings in `.env` override the defaults in `core/config.py` (see `.env.example` for the full list).

---

## Usage

```bash
python main.py
```

Or, if installed as a package:

```bash
telegram-bot-utility
```

### The Interface
- **Menu navigation**: use the ↑/↓ arrow keys (or `j`/`k`) and Enter to select, or press the option number directly. Press `?` to toggle inline help.
- **Tokens are masked** while typing, and previously used tokens are offered from memory during the session (never written to disk).
- **Input history**: arrow keys recall previous values for chat targets, messages, counts and search terms.
- **Chat targets** accept numeric IDs *or* `@usernames`.
- **Confirmation dialog**: every mass send shows a summary and asks for confirmation first.
- Exit with option `7` or press `Ctrl+C`.

> For detailed setup instructions on message forwarding (Telegram channel and
> Discord webhook), see [docs/FORWARDING_GUIDE.md](docs/FORWARDING_GUIDE.md).

### Mode Specifics

#### Dump Bot History
When launched (in a separate window):
1. The tool initializes a **Telethon** client.
2. It asks for a target Chat ID — or you can dump **all** dialogs.
3. It creates a session file in the bot's data folder.
4. An **access report** shows what history the bot can actually read in each
   dialog (admin = full history, member = messages after join only).
5. A **live dashboard** shows statistics (messages, chats, media) and a live feed.
6. Data is saved continuously to `messages.jsonl` and `history.txt`.

**Live dashboard commands** (type the letter and press Enter):

| Key | Action |
|-----|--------|
| `P` | Pause / resume processing of new messages |
| `C` | Clear the on-screen feed |
| `S` | Show detailed per-chat statistics |
| `Q` | Quit the dumper cleanly |

Command-line launcher for advanced use:
```bash
python -m core.launcher <token> --chat -100123 --history-limit 1000 --listen-only
python -m core.launcher <token> --proxy 127.0.0.1:1080
```
> The token can also be passed via the `TBU_TOKEN` environment variable so it never appears on the command line.

---

## Data Structure

The tool keeps your workspace clean by organizing data hierarchically:

```bash
Telegram-Bot-Utility/
├── <Bot_ID>/                   # Main folder for the specific bot
│   ├── bot.json                # Bot details (no token stored!)
│   ├── statistics.json         # Global message counters
│   ├── zips/                   # Archives created by the forwarder
│   └── <Chat_ID>/              # Folder for a specific chat/user
│       ├── <chat_id>_history.txt   # Human-readable log
│       ├── <chat_id>_messages.jsonl # Machine-readable dump (append-only JSONL)
│       ├── chat_info.json      # Chat metadata
│       ├── <user_id>.json      # User profile data
│       ├── <photo_id>.jpg      # User profile picture
│       └── media/              # Downloaded media
│           ├── photos/
│           ├── videos/
│           ├── stickers/       # .webp files
│           └── ...
```

> Legacy `messages.json` files are migrated to JSONL automatically on first save.

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `API_ID` | — | Telethon API ID (required for dumper) |
| `API_HASH` | — | Telethon API hash (required for dumper) |
| `BOT_TOKEN` | — | Optional bot token; when set the CLI uses it automatically |
| `REQUEST_TIMEOUT` | 30 | HTTP timeout in seconds |
| `RETRY_COUNT` | 3 | API retry attempts |
| `RETRY_BACKOFF` | 1.5 | Backoff multiplier between retries |
| `MEDIA_MAX_SIZE` | 52428800 | Max downloaded media size (bytes, 50 MB) |
| `HISTORY_DUMP_STEP` | 100 | Messages fetched per history cycle |
| `LOOKAHEAD_STEP_COUNT` | 3 | Empty batches tolerated before assuming history end (handles gaps from deleted messages) |
| `ZIP_INTERVAL_MESSAGES` | 50 | Create zip after this many messages per chat |
| `ZIP_INTERVAL_SECONDS` | 300 | Or after this many seconds (5 minutes) |
| `ZIP_CLEANUP_AFTER_SEND` | true | Delete zip files after successful send |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | telegram_bot_utility.log | Log file path |
| `LOG_FILE_ENABLED` | true | Write logs to file |

---

## Troubleshooting & FAQ

**Q: "No chats found" in List Chats mode?**
> A: The bot can only see chats where it has received at least one message since its last reboot/update or where it is an active admin. Send a message to the bot and try again.

**Q: Group messages are not appearing in the Dumper?**
> A: **Privacy Mode** is likely enabled.
> 1. Go to @BotFather.
> 2. Select your bot > Bot Settings > Group Privacy.
> 3. Turn it **OFF**.
> 4. Alternatively, make the bot an **Admin** in the group.

**Q: Discord forwarding isn't working?**
> A: Check the webhook URL you entered. The bot machine must have internet access and be able to reach Discord.

**Q: I get a "Session" error?**
> A: Delete the `<bot_id>.session` file in the bot's folder and restart the tool to re-authenticate.

**Q: The dumper says history is restricted for bots?**
> A: Telegram forbids bot accounts from fetching message history via MTProto
> (`GetHistoryRequest`). The dumper saves recent messages from the update queue
> and monitors live instead. Full history requires a user account or an admin
> bot in channels where permitted.

**Q: Dumper asks for API_ID/API_HASH?**
> A: The dumper needs Telethon credentials. Set `API_ID` and `API_HASH` in your `.env` file (get them from [my.telegram.org](https://my.telegram.org)).

**Q: I get a "409 Conflict" from getUpdates?**
> A: Telegram only allows **one** getUpdates consumer at a time. Either the bot
> uses a webhook, or another process (the real bot, another tool instance) is
> already polling. Stop the other consumer or switch to a webhook. The dumper
> and List Chats show a clear warning instead of failing silently.

**Q: Where did my downloaded image go?**
> A: URL downloads are stored in the system temp folder
> (`telegram-bot-utility/` under the OS temp dir) and deleted automatically
> after the message is sent. The project folder is never written to.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m unittest discover -s tests -v

# Lint
ruff check .

# CI runs tests on Python 3.9-3.12 (see .github/workflows/ci.yml)
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the project structure and
contribution guidelines.

---

## Disclaimer

This tool is intended for **educational and administrative purposes only**. You are responsible for ensuring that your use of this tool (including message dumping and spamming) complies with Telegram's Terms of Service and applicable privacy laws in your jurisdiction.

---

## License

MIT License. Free for personal and commercial use.
