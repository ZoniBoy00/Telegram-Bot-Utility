"""Shared utility functions for Telegram Bot Utility."""

import os
import sys
from typing import Optional, Callable, TypeVar
from colorama import Fore, Style

T = TypeVar('T')


def clear_console() -> None:
    """Clears the console screen based on the operating system."""
    os.system('cls' if os.name == 'nt' else 'clear')


def validate_input(
    prompt: str,
    expected_type: type[T],
    condition: Callable[[T], bool] = lambda x: True,
    error_msg: str = "Invalid input."
) -> Optional[T]:
    """
    Prompts user for input and validates it.
    
    Args:
        prompt: The prompt to display to the user
        expected_type: The expected type of the input
        condition: A function to validate the input
        error_msg: Error message to display on validation failure
        
    Returns:
        The validated user input or None if cancelled
    """
    while True:
        try:
            user_input = input(f"{Fore.CYAN}{prompt}")
            
            if expected_type != str:
                user_input = expected_type(user_input)
            
            if condition(user_input):
                return user_input
            
            print(f"{Fore.RED}{error_msg}")
            
        except ValueError:
            print(f"{Fore.RED}Invalid input type. Expected {expected_type.__name__}.")
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Operation cancelled.")
            return None


def print_header(title: str) -> None:
    """Prints a formatted header."""
    print(f"\n{Style.BRIGHT}{Fore.GREEN}{title}")
    print(f"{Fore.WHITE}{'='*50}")


def print_separator() -> None:
    """Prints a separator line."""
    print(f"{Fore.CYAN}{'='*50}")
