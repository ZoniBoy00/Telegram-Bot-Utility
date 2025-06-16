import os
import requests
import time
import sys
from colorama import init, Fore, Style

# Initialize colorama for colored console output
init(autoreset=True)

def clear_console():
    """Clears the console screen based on the operating system."""
    os.system('cls' if os.name == 'nt' else 'clear')

def download_image(image_url):
    """
    Downloads an image or GIF from the provided URL.
    Returns the filename if successful, otherwise None.
    """
    try:
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            filename = image_url.split("/")[-1].split("?")[0]
            with open(filename, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            return filename
        else:
            print(f"{Fore.RED}Failed to download image. Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error downloading image: {e}")
    return None

def spam_with_token(token, chat_id, message, count, delay, image_path=None):
    """
    Sends a spam of messages or media (photo or animation) to the specified chat.
    Parameters:
        token - Bot token
        chat_id - Target chat ID
        message - Message text or caption
        count - Number of times to send
        delay - Delay between messages (seconds)
        image_path - Optional path to image/GIF to send
    """
    base_url = f"https://api.telegram.org/bot{token}/"

    # Detect file type for correct Telegram API method
    def is_gif(filename):
        return filename.lower().endswith('.gif')

    def is_image(filename):
        return any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp'])

    for i in range(count):
        try:
            if image_path:
                with open(image_path, 'rb') as f:
                    if is_gif(image_path):
                        # Send as animation (GIF)
                        files = {'animation': f}
                        payload = {'chat_id': chat_id, 'caption': message}
                        response = requests.post(base_url + "sendAnimation", data=payload, files=files)
                    elif is_image(image_path):
                        # Send as photo
                        files = {'photo': f}
                        payload = {'chat_id': chat_id, 'caption': message}
                        response = requests.post(base_url + "sendPhoto", data=payload, files=files)
                    else:
                        # Unknown file type, fallback to sendDocument
                        files = {'document': f}
                        payload = {'chat_id': chat_id, 'caption': message}
                        response = requests.post(base_url + "sendDocument", data=payload, files=files)
            else:
                payload = {'chat_id': chat_id, 'text': message}
                response = requests.post(base_url + "sendMessage", data=payload)

            if response.status_code == 200:
                print(f"{Fore.GREEN}Message {i+1}/{count} sent.")
            else:
                print(f"{Fore.RED}Failed to send message {i+1}/{count}. Status: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"{Fore.RED}Error sending message {i+1}: {e}")

        time.sleep(delay)

    # Delete downloaded image/GIF file after sending
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
            print(f"{Fore.GREEN}Image/GIF deleted.")
        except Exception as e:
            print(f"{Fore.RED}Could not delete file: {e}")

def delete_bot_token(token):
    """
    Attempts to delete the bot webhook and invalidate the bot token.
    Note: Telegram API does not support invalidating tokens via API.
    """
    try:
        response = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
        if response.status_code == 200:
            print(f"{Fore.GREEN}Bot webhook successfully deleted.")
        else:
            print(f"{Fore.RED}Failed to delete bot webhook. Status Code: {response.status_code}")

        response = requests.get(f"https://api.telegram.org/bot{token}/getMe")
        if response.status_code == 200:
            print(f"{Fore.GREEN}Bot token is still valid.")
        else:
            print(f"{Fore.RED}Failed to validate bot token. Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error: {e}")

def list_chats(token):
    """
    Lists all chats where the bot has been active or present.
    """
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            updates = response.json().get('result', [])
            chats = {}
            for update in updates:
                message = update.get('message') or update.get('channel_post')
                if message:
                    chat = message.get('chat', {})
                    chat_id = chat.get('id')
                    chat_title = chat.get('title', chat.get('username'))
                    chats[chat_id] = chat_title
            if chats:
                print(f"{Fore.GREEN}Chats where the bot is present:")
                for chat_id, chat_title in chats.items():
                    print(f"{Fore.WHITE}ID: {chat_id}, Name: {chat_title}")
            else:
                print(f"{Fore.RED}No chats found.")
        else:
            print(f"{Fore.RED}Failed to retrieve chat list. Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error retrieving chat list: {e}")

def get_bot_info(token):
    """
    Retrieves and displays information about the bot associated with the token.
    """
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe")
        if response.status_code == 200:
            bot = response.json()['result']
            print(f"\n{Style.BRIGHT}{Fore.GREEN}Bot Info:")
            print(f"{Fore.WHITE}Username: {bot.get('username')}")
            print(f"First Name: {bot.get('first_name')}")
            print(f"ID: {bot.get('id')}")
            print(f"Is Bot: {bot.get('is_bot')}")
            print(f"Can Join Groups: {bot.get('can_join_groups')}")
            print(f"Can Read All Group Messages: {bot.get('can_read_all_group_messages')}")
            print(f"Supports Inline Queries: {bot.get('supports_inline_queries')}")
        else:
            print(f"{Fore.RED}Failed to retrieve bot info. Status Code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error retrieving bot info: {e}")

def validate_input(prompt, expected_type, condition=lambda x: True, error_msg="Invalid input."):
    """
    Prompts user for input and validates it against expected type and condition.
    Repeats until valid input is entered.
    """
    while True:
        try:
            user_input = input(prompt)
            if expected_type != str:
                user_input = expected_type(user_input)
            if condition(user_input):
                return user_input
            print(f"{Fore.RED}{error_msg}")
        except ValueError:
            print(f"{Fore.RED}Invalid input type.")

def main():
    """
    Main program loop showing menu and executing selected actions.
    """
    while True:
        clear_console()
        print(f"{Style.BRIGHT}{Fore.CYAN}Telegram Bot Utility")
        print(f"{Style.BRIGHT}{Fore.CYAN}======================")
        print(f"{Fore.YELLOW}1. Spam with Bot Token (provide chat ID directly)")
        print(f"{Fore.YELLOW}2. Delete Bot Token (Not Working)")
        print(f"{Fore.YELLOW}3. Get Bot Info")
        print(f"{Fore.YELLOW}4. List Chats")
        print(f"{Fore.YELLOW}5. Exit")

        choice = validate_input(f"{Fore.YELLOW}Choose (1-5): ", int, lambda x: x in [1, 2, 3, 4, 5])

        if choice == 1:
            token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0)
            chat_id = validate_input("Enter chat ID (number): ", int, lambda c: True)
            message = input("Enter message to spam: ").strip()
            count = validate_input("How many times to spam: ", int, lambda x: x > 0)
            delay = validate_input("Delay between messages (seconds): ", float, lambda x: x >= 1)
            image_url = input("Image/GIF URL (leave blank for none): ").strip()
            image_path = download_image(image_url) if image_url else None
            spam_with_token(token, chat_id, message, count, delay, image_path)
        elif choice == 2:
            token = validate_input("Enter bot token to delete: ", str, lambda t: len(t) > 0)
            delete_bot_token(token)
        elif choice == 3:
            token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0)
            get_bot_info(token)
        elif choice == 4:
            token = validate_input("Enter bot token: ", str, lambda t: len(t) > 0)
            list_chats(token)
        elif choice == 5:
            print(f"{Fore.GREEN}Goodbye!")
            sys.exit(0)

        input(f"{Fore.YELLOW}Press Enter to return to the menu...")

if __name__ == "__main__":
    main()
