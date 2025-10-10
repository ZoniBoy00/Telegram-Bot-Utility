"""Main entry point for Telegram Bot Utility."""

import sys
import asyncio
from colorama import init, Fore, Style

from utils import clear_console, validate_input, print_separator
from bot_sender import spam_with_token, download_image, list_chats, get_bot_info
from bot_dumper import dump_bot_history, TELETHON_AVAILABLE

# Initialize colorama for colored console output
init(autoreset=True)


def display_menu() -> None:
    """Displays the main menu."""
    print(f"\n{Style.BRIGHT}{Fore.CYAN}{'='*50}")
    print(f"{Style.BRIGHT}{Fore.CYAN}Telegram Bot Utility")
    print(f"{Style.BRIGHT}{Fore.CYAN}{'='*50}")
    print(f"{Fore.YELLOW}1. Send Messages (Spam)")
    print(f"{Fore.YELLOW}2. Get Bot Info")
    print(f"{Fore.YELLOW}3. List Chats")
    print(f"{Fore.YELLOW}4. Dump Bot History (Advanced)")
    print(f"{Fore.YELLOW}5. Exit")
    print_separator()


def handle_send_messages() -> None:
    """Handle the send messages option."""
    token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0, "Token cannot be empty.")
    if token is None:
        return
    
    chat_id = validate_input("Enter chat ID (number): ", int)
    if chat_id is None:
        return
    
    message = input(f"{Fore.CYAN}Enter message to send: ").strip()
    
    count = validate_input("How many times to send: ", int, lambda x: x > 0, "Count must be greater than 0.")
    if count is None:
        return
    
    delay = validate_input("Delay between messages (seconds, min 1): ", float, lambda x: x >= 1.0, "Delay must be at least 1 second.")
    if delay is None:
        return
    
    image_url = input(f"{Fore.CYAN}Image/GIF URL (press Enter to skip): ").strip()
    image_path = download_image(image_url) if image_url else None
    
    print(f"\n{Fore.YELLOW}Starting to send messages...")
    spam_with_token(token, chat_id, message, count, delay, image_path)


def handle_get_bot_info() -> None:
    """Handle the get bot info option."""
    token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0, "Token cannot be empty.")
    if token is None:
        return
    get_bot_info(token)


def handle_list_chats() -> None:
    """Handle the list chats option."""
    token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0, "Token cannot be empty.")
    if token is None:
        return
    list_chats(token)


def handle_dump_history() -> None:
    """Handle the dump bot history option."""
    try:
        if not TELETHON_AVAILABLE:
            print(f"{Fore.RED}Telethon library is required for this feature.")
            print(f"{Fore.YELLOW}Install it with: pip install telethon")
            return
        
        token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0, "Token cannot be empty.")
        if token is None:
            return
        
        print(f"\n{Fore.CYAN}Options:")
        print(f"{Fore.YELLOW}1. Dump full history and listen for new messages")
        print(f"{Fore.YELLOW}2. Listen for new messages only (skip history)")
        
        option = validate_input("Choose option (1-2): ", int, lambda x: 1 <= x <= 2, "Please enter 1 or 2.")
        if option is None:
            return
        
        listen_only = (option == 2)
        
        print(f"\n{Fore.CYAN}Message Forwarding (Optional):")
        print(f"{Fore.YELLOW}You can forward all messages to a Telegram channel or Discord webhook.")
        
        forward_telegram = input(f"{Fore.CYAN}Telegram channel ID to forward to (press Enter to skip): ").strip()
        forward_discord = input(f"{Fore.CYAN}Discord webhook URL to forward to (press Enter to skip): ").strip()
        
        print(f"\n{Fore.YELLOW}Starting bot history dumper...")
        print(f"{Fore.YELLOW}This will create a folder with the bot ID containing all data.")
        print(f"{Fore.YELLOW}Press Ctrl+C to stop.\n")
        
        # Run the async function
        asyncio.run(dump_bot_history(
            token, 
            listen_only=listen_only,
            forward_to_telegram=forward_telegram if forward_telegram else None,
            forward_to_discord=forward_discord if forward_discord else None
        ))
        
    except ImportError:
        print(f"{Fore.RED}Telethon library is required for this feature.")
        print(f"{Fore.YELLOW}Install it with: pip install telethon")
    except KeyboardInterrupt:
        print(f"\n{Fore.GREEN}Bot history dumper stopped.")


def main() -> None:
    """Main program loop showing menu and executing selected actions."""
    while True:
        clear_console()
        display_menu()

        choice = validate_input("Choose an option (1-5): ", int, lambda x: 1 <= x <= 5, "Please enter a number between 1 and 5.")
        
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
            print(f"{Fore.GREEN}Thank you for using Telegram Bot Utility. Goodbye!")
            sys.exit(0)

        input(f"\n{Fore.YELLOW}Press Enter to return to the menu...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.GREEN}Program terminated by user. Goodbye!")
        sys.exit(0)
