"""Interactive command-line interface for Telegram Bot Utility."""

import os
import platform
import shlex
import subprocess
import sys

from rich.align import Align
from rich.panel import Panel
from rich.table import Table

from .api import download_image, get_bot_info, get_chat_info, list_chats, resolve_chat_id, spam_with_token
from .config import BOT_TOKEN
from .dumper import TELETHON_AVAILABLE
from .search import search_history
from .ui import (
    clear_console,
    console,
    print_header,
    print_success,
    print_warning,
    select_menu,
    set_window_title,
    validate_input,
)

# Environment variable used to pass the bot token to the child dumper process
# without exposing it on the command line.
TOKEN_ENV_VAR = "TBU_TOKEN"

# Bot tokens seen during this session (kept in memory only, never persisted)
_session_tokens: list[str] = []

MENU_HELP = """\
  Select a mode with the ↑/↓ arrow keys (or j/k) and press Enter.
  You can also press the number of the option.
  Press ? to toggle this help, Ctrl+C to cancel."""


def display_menu() -> None:
    """Display the main menu and return the selected option index (or None)."""
    clear_console()
    options = [label for label, _ in MENU_ITEMS]
    return select_menu(options, title="[bold cyan]Telegram Bot Utility[/]", help_text=MENU_HELP)


def ask_token() -> str:
    """
    Prompt for a bot token, offering previously used tokens from this session.

    Tokens are stored in memory only and never written to disk. If a token is
    configured via the BOT_TOKEN environment variable, it is used directly.
    """
    if BOT_TOKEN:
        console.print(f"[cyan]Using bot token from .env[/] [dim](…{BOT_TOKEN[-8:]})[/]")
        return BOT_TOKEN

    if _session_tokens:
        console.print("\n[bold cyan]Previous tokens (this session):[/]")
        for i, token in enumerate(_session_tokens, 1):
            console.print(f"  [cyan]{i}.[/] …{token[-8:]}")
        choice = validate_input(
            "Use a previous token (1-N), or 0 for a new one [0]:",
            int,
            lambda x: 0 <= x <= len(_session_tokens),
            f"Please enter a number between 0 and {len(_session_tokens)}.",
            default=0,
            history_key="token_choice",
        )
        if choice is None:
            return None
        if 1 <= choice <= len(_session_tokens):
            return _session_tokens[choice - 1]

    token = validate_input(
        "Enter bot token:",
        str,
        lambda t: len(t) > 0,
        "Token cannot be empty.",
        password=True,
    )
    if token and token not in _session_tokens:
        _session_tokens.insert(0, token)
        del _session_tokens[5:]  # keep at most 5
    return token


def ask_target_chat(token: str) -> int:
    """Prompt for a chat ID or @username and resolve it to a numeric ID."""
    target = validate_input("Enter chat ID or @username:", str, history_key="chat_target")
    if target is None:
        return None
    chat_id = resolve_chat_id(token, target)
    if chat_id is None:
        print_warning("Could not resolve the target chat.")
    return chat_id


def ask_message_composition(token: str, chat_name: str, chat_id: int) -> None:
    """Collect message, count, delay and optional media; confirm and send."""
    print_header(f"Send to: {chat_name} ({chat_id})")

    message = validate_input("Enter message to send:", str, history_key="message_text")
    if message is None:
        return

    count = validate_input(
        "How many times to send:",
        int,
        lambda x: x > 0,
        "Count must be greater than 0.",
        default=1,
        history_key="message_count",
    )
    if count is None:
        return

    delay = validate_input(
        "Delay between messages (seconds, min 0.1):",
        float,
        lambda x: x >= 0.1,
        "Delay must be at least 0.1 second.",
        default=1.0,
        history_key="message_delay",
    )
    if delay is None:
        return

    image_url = validate_input("Image/GIF URL (leave empty to skip):", str)
    image_path = download_image(image_url) if image_url else None

    # Confirmation dialog before the mass send
    console.print("\n[bold yellow]Summary:[/]")
    console.print(f"  [cyan]Target:[/] {chat_name} ({chat_id})")
    console.print(f"  [cyan]Message:[/] {message[:80]}{'…' if len(message) > 80 else ''}")
    console.print(f"  [cyan]Count:[/] {count}   [cyan]Delay:[/] {delay}s   "
                  f"[cyan]Media:[/] {'yes' if image_path else 'no'}")
    confirm = validate_input(
        "Send? (y/N):",
        str,
        lambda x: x.lower() in ("y", "yes", "n", "no", ""),
        "Please answer y or n.",
        default="n",
    )
    if confirm is None or confirm.lower() not in ("y", "yes"):
        print_warning("Cancelled.")
        return

    console.print("\n[bold yellow]Starting sequence...[/]")
    spam_with_token(token, chat_id, message, count, delay, image_path)


def handle_send_messages() -> None:
    """Handle the send messages option."""
    print_header("Send Messages Mode")

    token = ask_token()
    if token is None:
        return

    chat_id = ask_target_chat(token)
    if chat_id is None:
        return

    ask_message_composition(token, f"chat {chat_id}", chat_id)


def handle_get_bot_info() -> None:
    """Handle the get bot info option."""
    token = ask_token()
    if token is None:
        return
    get_bot_info(token)


def handle_list_chats() -> None:
    """Handle the list chats option with the ability to send to a found chat."""
    token = ask_token()
    if token is None:
        return

    chats = list_chats(token)
    if not chats:
        return

    send_choice = validate_input(
        "Send a message to one of these chats? (enter number, or 0 to skip):",
        int,
        lambda x: 0 <= x <= len(chats),
        f"Please enter a number between 0 and {len(chats)}.",
        default=0,
    )
    if send_choice is None or send_choice == 0:
        return

    selected_id = list(chats.keys())[send_choice - 1]
    selected_info = chats[selected_id]
    ask_message_composition(token, selected_info['title'], selected_id)


def handle_dump_history() -> None:
    """Handle the dump bot history option."""
    print_header("Dump History Mode")

    if not TELETHON_AVAILABLE:
        console.print("[bold red]Telethon library is required for this feature.[/]")
        console.print("[yellow]Install it with: pip install telethon[/]")
        return

    token = ask_token()
    if token is None:
        return

    # Modern selection for dump options
    console.print(Panel(
        "[bold cyan]1.[/] Dump full history and listen for new messages\n"
        "[bold cyan]2.[/] Listen for new messages only [dim](skip history)[/]",
        title="Dump Options",
        border_style="cyan",
    ))

    option = validate_input(
        "Choose option (1-2):",
        int,
        lambda x: 1 <= x <= 2,
        "Please enter 1 or 2.",
        default=1,
    )
    if option is None:
        return
    listen_only = (option == 2)

    # Target chat selection
    console.print("\n[bold cyan]Target Chat (Optional):[/]")
    console.print("[dim]Enter a chat ID to dump only that chat, or leave empty to dump all dialogs.[/]")
    target_chat = validate_input("Target chat ID (leave empty for all):", str)
    if target_chat is None:
        return
    target_chat = target_chat.strip()

    history_limit = validate_input(
        "Max messages per chat (leave empty for all):",
        int,
        lambda x: x > 0,
        "Limit must be greater than 0.",
    )

    # Proxy support
    console.print("\n[bold cyan]Proxy (Optional):[/]")
    console.print("[dim]Format: host:port (SOCKS5). Leave empty for no proxy.[/]")
    proxy = validate_input("Proxy (host:port):", str)
    if proxy is None:
        return
    proxy = proxy.strip()

    console.print("\n[bold cyan]Message Forwarding (Optional):[/]")
    console.print("[dim]Forward all messages to a Telegram channel or Discord webhook.[/]")

    forward_telegram = validate_input(
        "Telegram channel ID to forward to (leave empty to skip):", str
    )
    if forward_telegram is None:
        return
    forward_telegram = forward_telegram.strip()

    forward_discord = validate_input(
        "Discord webhook URL to forward to (leave empty to skip):", str
    )
    if forward_discord is None:
        return
    forward_discord = forward_discord.strip()

    console.print("\n[bold yellow]Launching standalone dumper...[/]")
    console.print("[green]You can continue using this menu while the dumper runs.[/]")

    # Build command line arguments
    args = []
    if listen_only:
        args.append("--listen-only")
    if target_chat:
        args.extend(["--chat", target_chat])
    if history_limit:
        args.extend(["--history-limit", str(history_limit)])
    if proxy:
        args.extend(["--proxy", proxy])
    if forward_telegram:
        args.extend(["--telegram-channel", forward_telegram])
    if forward_discord:
        args.extend(["--discord-webhook", forward_discord])

    # Pass the token via environment variable, not the command line
    env = os.environ.copy()
    env[TOKEN_ENV_VAR] = token

    # Detect OS and launch in appropriate way
    system = platform.system()

    # Launcher argv passed as a list so the shell never interprets user input
    # (avoids command injection via chat IDs / webhook URLs etc).
    launcher_argv = [sys.executable, "-m", "core.launcher", *args]

    try:
        if system == 'Windows':
            # New console window that stays open after the dumper exits so
            # errors remain visible. CREATE_NEW_CONSOLE + a plain argv list
            # replaces the old `start ... & cmd /k ...` with shell=True.
            subprocess.Popen(
                ["cmd", "/k", *launcher_argv],
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif system == 'Darwin':  # macOS
            quoted = " ".join(shlex.quote(a) for a in launcher_argv)
            script = f'tell app "Terminal" to do script "{quoted}"'
            subprocess.Popen(["osascript", "-e", script], env=env)
        else:  # Linux and others
            quoted = " ".join(shlex.quote(a) for a in launcher_argv)
            terminals = [
                ['gnome-terminal', '--', 'bash', '-c', f'{quoted}; exec bash'],
                ['xterm', '-e', f'{quoted}; exec bash'],
                ['konsole', '-e', f'{quoted}; exec bash'],
                ['xfce4-terminal', '-e', f'{quoted}; exec bash'],
            ]

            launched = False
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd, env=env)
                    launched = True
                    break
                except FileNotFoundError:
                    continue

            if not launched:
                console.print("[red]Could not find a suitable terminal emulator.[/]")
                console.print(
                    f"[yellow]Please run manually:\n"
                    f"  set {TOKEN_ENV_VAR}=<your_token>\n"
                    f"  {sys.executable} -m core.launcher {' '.join(args)}[/]"
                )
                return

        print_success("Dumper successfully launched!")
    except Exception as e:
        console.print(f"[bold red]Error launching dumper: {str(e)}[/]")


def handle_chat_finder() -> None:
    """Handle the chat ID finder option."""
    print_header("Chat ID Finder")

    token = ask_token()
    if token is None:
        return

    console.print("[dim]Enter a @username, numeric ID, or t.me link of a chat the bot can access.[/]")
    target = validate_input("Chat (@username / ID / t.me link):", str, history_key="chat_target")
    if target is None:
        return

    info = get_chat_info(token, target)
    if not info:
        return

    chat_id = info.get("id")
    chat_type = info.get("type", "unknown")
    title = info.get("title") or info.get("first_name") or info.get("username") or "Unknown"

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Field", style="cyan bold", justify="right")
    table.add_column("Value", style="white")

    table.add_row("ID", str(chat_id))
    table.add_row("Type", chat_type)
    table.add_row("Name", title)
    if info.get("username"):
        table.add_row("Username", f"@{info['username']}")
    if info.get("description"):
        table.add_row("Description", str(info["description"])[:120])
    if info.get("member_count") is not None:
        table.add_row("Members", str(info["member_count"]))

    console.print(Align.center(table))
    console.print()
    console.print(f"[bold cyan]Copy this chat ID:[/] [bold yellow]{chat_id}[/]")
    console.print("[dim]Use it as the chat target in Send Messages, the dumper, or forwarding.[/]")


def handle_search_history() -> None:
    """Handle the search history option."""
    print_header("Search History Mode")
    query = validate_input("Enter search term:", str, history_key="search_query")
    if not query:
        return
    search_history(query)


# Menu definition: (label, handler). Order matters for the numeric index.
MENU_ITEMS: list[tuple[str, callable]] = [
    ("Send Messages (Spam)", handle_send_messages),
    ("Get Bot Info", handle_get_bot_info),
    ("List Chats", handle_list_chats),
    ("Chat ID Finder", handle_chat_finder),
    ("Dump Bot History (Advanced)", handle_dump_history),
    ("Search History", handle_search_history),
    ("Exit", lambda: sys.exit(0)),
]


def main() -> None:
    """Main program loop showing menu and executing selected actions."""
    set_window_title("Telegram Bot Utility")
    while True:
        choice = display_menu()
        if choice is None:  # User cancelled
            continue

        handler = MENU_ITEMS[choice][1]
        handler()

        # Pause before clearing screen again
        console.input("\n[bold yellow]Press Enter to return to the menu...[/]")


def run() -> None:
    """Entry point wrapper with top-level KeyboardInterrupt handling."""
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold green]Program terminated by user. Goodbye![/]")
        sys.exit(0)


if __name__ == "__main__":
    run()
