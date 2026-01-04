"""Main entry point for Telegram Bot Utility."""

import sys
import os
import subprocess
import platform
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.padding import Padding
from rich import box

from core.utils import clear_console, validate_input, print_header, console
from core.sender import spam_with_token, download_image, list_chats, get_bot_info
from core.dumper import TELETHON_AVAILABLE


def set_window_title(title: str):
    if platform.system() == "Windows":
        os.system(f"title {title}")
    else:
        # Standard ANSI sequence for window title
        sys.stdout.write(f"\x1b]2;{title}\x07")

def display_menu() -> None:
    """Displays the main menu with a modern layout."""
    clear_console()
    
    menu_table = Table(
        box=None, 
        show_header=False, 
        show_edge=False, 
        padding=(0, 2),
        pad_edge=False
    )
    
    menu_table.add_column("No.", justify="right", style="cyan bold", width=5)
    menu_table.add_column("Description", justify="left", style="white")

    # Add rows without emojis for consistent terminal rendering
    menu_table.add_row("1", "Send Messages (Spam)")
    menu_table.add_row("2", "Get Bot Info")
    menu_table.add_row("3", "List Chats")
    menu_table.add_row("4", "Dump Bot History [dim](Advanced)[/]")
    menu_table.add_row("5", "Exit")

    main_panel = Panel(
        menu_table,
        title="[bold cyan]Telegram Bot Utility[/]",
        subtitle="[dim]Select an option[/]",
        border_style="blue",
        padding=(1, 4),
        width=60
    )

    # Center the panel on screen
    console.print(Align.center(main_panel))
    console.print()

def handle_send_messages() -> None:
    """Handle the send messages option."""
    print_header("Send Messages Mode")
    
    token = validate_input("Enter bot token:", str, lambda t: len(t) > 0, "Token cannot be empty.")
    if token is None: return
    
    chat_id = validate_input("Enter chat ID (number):", int)
    if chat_id is None: return
    
    message = validate_input("Enter message to send:", str)
    if message is None: return
    
    count = validate_input("How many times to send:", int, lambda x: x > 0, "Count must be greater than 0.", default=1)
    if count is None: return
    
    delay = validate_input("Delay between messages (seconds, min 0.1):", float, lambda x: x >= 0.1, "Delay must be at least 0.1 second.", default=1.0)
    if delay is None: return
    
    image_url = validate_input("Image/GIF URL (leave empty to skip):", str, lambda x: True, "")
    image_path = None
    if image_url:
        image_path = download_image(image_url)
    
    console.print(f"\n[bold yellow]🚀 Starting sequence...[/]")
    spam_with_token(token, chat_id, message, count, delay, image_path)


def handle_get_bot_info() -> None:
    """Handle the get bot info option."""
    print_header("Bot Info Mode")
    token = validate_input("Enter bot token:", str, lambda t: len(t) > 0, "Token cannot be empty.")
    if token is None: return
    get_bot_info(token)


def handle_list_chats() -> None:
    """Handle the list chats option."""
    print_header("List Chats Mode")
    token = validate_input("Enter bot token:", str, lambda t: len(t) > 0, "Token cannot be empty.")
    if token is None: return
    list_chats(token)


def handle_dump_history() -> None:
    """Handle the dump bot history option."""
    print_header("Dump History Mode")
    
    try:
        if not TELETHON_AVAILABLE:
            console.print("[bold red]Telethon library is required for this feature.[/]")
            console.print("[yellow]Install it with: pip install telethon[/]")
            return
        
        token = validate_input("Enter bot token:", str, lambda t: len(t) > 0, "Token cannot be empty.")
        if token is None: return
        
        # Modern selection for dump options
        console.print(Panel(
            "[bold cyan]1.[/] Dump full history and listen for new messages\n"
            "[bold cyan]2.[/] Listen for new messages only [dim](skip history)[/]",
            title="Dump Options",
            border_style="cyan"
        ))
        
        option = validate_input("Choose option (1-2):", int, lambda x: 1 <= x <= 2, "Please enter 1 or 2.", default=1)
        if option is None: return
        
        listen_only = (option == 2)
        
        console.print("\n[bold cyan]Message Forwarding (Optional):[/]")
        console.print("[dim]You can forward all messages to a Telegram channel or Discord webhook.[/]")
        
        forward_telegram = validate_input("Telegram channel ID to forward to (leave empty to skip):", str)
        forward_discord = validate_input("Discord webhook URL to forward to (leave empty to skip):", str)
        
        console.print(f"\n[bold yellow]🚀 Launching standalone dumper...[/]")
        console.print("[green]You can continue using this menu while the dumper runs.[/]")
        
        # Prepare command line arguments
        listen_arg = 'true' if listen_only else 'false'
        telegram_arg = forward_telegram if forward_telegram else 'None'
        discord_arg = forward_discord if forward_discord else 'None'
        
        # Detect OS and launch in appropriate way
        system = platform.system()
        
        if system == 'Windows':
            # Windows: Use 'start' command to open new CMD window
            cmd = f'start "Bot Dumper" cmd /k python -m core.launcher "{token}" {listen_arg} "{telegram_arg}" "{discord_arg}"'
            subprocess.Popen(cmd, shell=True)
        elif system == 'Darwin':  # macOS
            # macOS: Use 'open' with Terminal.app
            script = f'python -m core.launcher "{token}" {listen_arg} "{telegram_arg}" "{discord_arg}"'
            cmd = ['osascript', '-e', f'tell app "Terminal" to do script "{script}"']
            subprocess.Popen(cmd)
        else:  # Linux and others
            # Linux: Try common terminal emulators
            script = f'python -m core.launcher "{token}" {listen_arg} "{telegram_arg}" "{discord_arg}"'
            terminals = [
                ['gnome-terminal', '--', 'bash', '-c', f'{script}; exec bash'],
                ['xterm', '-e', f'{script}; exec bash'],
                ['konsole', '-e', f'{script}; exec bash'],
                ['xfce4-terminal', '-e', f'{script}; exec bash']
            ]
            
            launched = False
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            
            if not launched:
                console.print("[red]Could not find a suitable terminal emulator.[/]")
                console.print(f"[yellow]Please run manually: python -m core.launcher \"{token}\" {listen_arg} \"{telegram_arg}\" \"{discord_arg}\"[/]")
                return
        
        console.print("[bold green]✓ Dumper successfully launched![/]")
        
    except ImportError:
        console.print("[bold red]Telethon library is required for this feature.[/]")
        console.print("[yellow]Install it with: pip install telethon[/]")
    except Exception as e:
        console.print(f"[bold red]Error launching dumper: {str(e)}[/]")

def main() -> None:
    """Main program loop showing menu and executing selected actions."""
    set_window_title("Telegram Bot Utility")
    while True:
        display_menu()

        choice = validate_input("Choose an option:", int, lambda x: 1 <= x <= 5, "Please enter a number between 1 and 5.")
        
        if choice is None:  # User cancelled
            continue

        if choice == 1:
            handle_send_messages()
        elif choice == 2:
            handle_get_bot_info()
        elif choice == 3:
            handle_list_chats()
        elif choice == 4:
            handle_dump_history()
        elif choice == 5:
            console.print("[bold green]Goodbye! 👋[/]")
            sys.exit(0)

        # Pause before clearing screen again
        console.input(f"\n[bold yellow]Press Enter to return to the menu...[/]")


if __name__ == "__main__":
    from rich.padding import Padding # Needs local import here if used in main block or just use top level
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold green]Program terminated by user. Goodbye![/]")
        sys.exit(0)
