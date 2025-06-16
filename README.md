# Telegram Bot Utility

**Telegram Bot Utility** is a command-line based application that provides several useful features for managing and interacting with a Telegram bot. You can send spam messages with or without images/GIFs, retrieve bot info, list active chats, and delete bot webhooks.

---

## 🔧 Features

- 📤 Send text, image, or GIF spam to a chat using your bot token
- ⏱ Adjustable delay between messages
- 🌄 Download image or GIF from a URL for sending
- 💬 List chats where the bot has been active
- 👤 Fetch and display bot account information
- 🧹 Automatically clears the console (Windows/Linux/macOS)
- 🎨 Colored terminal output using Colorama

---

## 📦 Requirements

- Python 3.6 or higher
- Required libraries:

```bash
pip install requests colorama
```

---

## 🚀 Installation

1. **Clone the repository:**

```bash
git clone https://github.com/ZoniBoy00/Telegram-Bot-Utility.git
cd Telegram-Bot-Utility
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing, use:

```bash
pip install requests colorama
```

3. **Run the script:**

```bash
python telegram_bot_utility.py
```

---

## 💡 Usage

Once launched, the program displays a menu:

```
1. Spam with Bot Token (provide chat ID directly)
2. Delete Bot Token (Not Working)
3. Get Bot Info
4. List Chats
5. Exit
```

Follow the prompts to use each feature.

### 🖼 Example: Spamming with an image or GIF

You will be asked to provide:

- **Bot Token**
- **Chat ID**
- **Message text**
- **Number of repetitions**
- **Delay between messages (in seconds)**
- **Optional Image/GIF URL** (leave blank to send only text)

---

## 📘 API Overview

### `spam_with_token(token, chat_id, message, count, delay, image_path=None)`

Sends a repeated message or media file to a Telegram chat using the bot token.

### `download_image(image_url)`

Downloads an image or GIF from the provided URL and returns the filename.

### `get_bot_info(token)`

Fetches and displays detailed information about the Telegram bot.

### `list_chats(token)`

Lists all chats where the bot has been active by reading Telegram updates.

### `delete_bot_token(token)`

Attempts to delete the bot’s webhook. (Note: Token invalidation is not supported via Telegram API.)

### `clear_console()`

Clears the console screen, compatible with Windows, macOS, and Linux.

---

## 🛠 Troubleshooting

- Ensure the bot is a member of the target chat and has permission to send messages.
- If spamming fails, verify that the bot token and chat ID are correct.
- Telegram may limit repeated requests — respect rate limits to avoid restrictions.

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## 🙏 Acknowledgments

- [`requests`](https://docs.python-requests.org): Used for HTTP requests
- [`colorama`](https://pypi.org/project/colorama/): Provides cross-platform colored output in terminal
