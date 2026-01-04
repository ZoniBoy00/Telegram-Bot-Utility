"""Shared utility functions for Telegram Bot Utility using Rich and prompt_toolkit."""

import os
import sys
from typing import Optional, Callable, TypeVar, Any

from rich.console import Console
from rich.panel import Panel
from rich.align import Align
from rich.style import Style

# prompt_toolkit for robust input handling (fixes pasting issues on Windows)
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PromptStyle

# Initialize globally accessible console
console = Console()

T = TypeVar('T')

def clear_console() -> None:
    """Clears the console screen."""
    console.clear()

def validate_input(
    prompt_text: str,
    expected_type: type[T] = str,
    condition: Callable[[T], bool] = lambda x: True,
    error_msg: str = "Invalid input.",
    default: Any = None,
    password: bool = False
) -> Optional[T]:
    """
    Prompts user for input and validates it using prompt_toolkit for better interaction.
    
    Args:
        prompt_text: The prompt to display to the user
        expected_type: The expected type of the input
        condition: A function to validate the input
        error_msg: Error message to display on validation failure
        default: Default value if user presses enter
        password: If True, hides input characters
        
    Returns:
        The validated user input or None if cancelled
    """
    # Create prompt styling
    style = PromptStyle.from_dict({
        'prompt': 'bold #00ffff',  # Cyan
    })
    
    cursor_text = " > "
    formatted_prompt = HTML(f'<prompt>{prompt_text}</prompt>{cursor_text}')
    
    try:
        while True:
            # Use prompt_toolkit instead of rich.Prompt
            user_input_str = prompt(
                formatted_prompt,
                style=style,
                is_password=password,
                default=str(default) if default is not None else ""
            ).strip()

            # Handle empty input with default
            if not user_input_str:
                if default is not None:
                    user_input = default
                elif expected_type == str:
                    user_input = "" # type: ignore
                else:
                    continue
            
            # Type conversion
            try:
                if user_input_str:
                    if expected_type == int:
                        user_input = int(user_input_str)
                    elif expected_type == float:
                        user_input = float(user_input_str)
                    else:
                        user_input = user_input_str # type: ignore
                
                if condition(user_input): # type: ignore
                    return user_input # type: ignore
                
                console.print(f"[bold red]✗ {error_msg}[/]")
                
            except ValueError:
                console.print(f"[bold red]✗ Invalid input type. Expected {expected_type.__name__}.[/]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled.[/]")
        return None

def print_header(title: str, subtitle: str = "") -> None:
    """Prints a formatted header using Rich Rule."""
    console.print()
    from rich.rule import Rule
    rule = Rule(f"{title}", style="blue", align="center")
    console.print(rule)
    if subtitle:
        console.print(f"[dim cyan]{subtitle}[/]", justify="center")
    console.print()

def print_separator() -> None:
    """Prints a separator line."""
    console.rule(style="blue")

def print_success(message: str) -> None:
    """Prints a success message."""
    console.print(f"[bold green]✓ {message}[/]")

def print_error(message: str) -> None:
    """Prints an error message."""
    console.print(f"[bold red]✗ {message}[/]")

def print_warning(message: str) -> None:
    """Prints a warning message."""
    console.print(f"[bold yellow]! {message}[/]")

def print_info(message: str) -> None:
    """Prints an info message."""
    console.print(f"[bold blue]i {message}[/]")
