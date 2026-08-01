"""Console, input and display helpers for the terminal UI."""

import sys
from typing import Any, Callable, Optional

# prompt_toolkit for robust input handling (fixes pasting issues on Windows)
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PromptStyle
from rich.console import Console
from rich.rule import Rule

# Initialize globally accessible console
console = Console()

# Windows legacy consoles (cp1252) cannot encode emojis/symbols like ✓ and ✗.
# Reconfigure stdout to UTF-8 with a safe fallback so Rich never crashes.
try:
    if hasattr(console.file, "reconfigure"):
        console.file.reconfigure(encoding="utf-8", errors="replace")
except (OSError, AttributeError, ValueError):
    pass

# Per-field input histories, kept for the lifetime of the process so arrow
# keys recall previous values within a session.
_HISTORIES: dict[str, InMemoryHistory] = {}


def _get_history(key: str) -> InMemoryHistory:
    """Return the shared InMemoryHistory instance for a field key."""
    history = _HISTORIES.get(key)
    if history is None:
        history = InMemoryHistory()
        _HISTORIES[key] = history
    return history


def clear_console() -> None:
    """Clears the console screen."""
    console.clear()


def set_window_title(title: str) -> None:
    """Set the terminal window title (Unicode-safe on Windows)."""
    import platform

    if platform.system() == "Windows":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except (AttributeError, OSError):
            import os

            os.system(f"title {title}")
    else:
        # Standard ANSI sequence for window title
        sys.stdout.write(f"\x1b]2;{title}\x07")


def validate_input(
    prompt_text: str,
    expected_type: type = str,
    condition: Callable[[Any], bool] = lambda x: True,
    error_msg: str = "Invalid input.",
    default: Any = None,
    password: bool = False,
    history_key: Optional[str] = None,
) -> Optional[Any]:
    """
    Prompts user for input and validates it using prompt_toolkit for better interaction.

    Args:
        prompt_text: The prompt to display to the user
        expected_type: The expected type of the input
        condition: A function to validate the input
        error_msg: Error message to display on validation failure
        default: Default value if user presses enter
        password: If True, hides input characters
        history_key: Optional key for per-field input history (arrow keys)

    Returns:
        The validated user input or None if cancelled
    """
    # Create prompt styling
    style = PromptStyle.from_dict({
        'prompt': 'bold #00ffff',  # Cyan
    })

    history = _get_history(history_key) if history_key else None
    cursor_text = " > "
    formatted_prompt = HTML(f'<prompt>{prompt_text}</prompt>{cursor_text}')

    try:
        while True:
            user_input_str = prompt(
                formatted_prompt,
                style=style,
                is_password=password,
                default=str(default) if default is not None else "",
                history=history,
            ).strip()

            # Handle empty input with default
            if not user_input_str:
                if default is not None:
                    user_input = default
                elif expected_type is str:
                    user_input = ""  # type: ignore[assignment]
                else:
                    continue

            # Type conversion
            try:
                if user_input_str:
                    if expected_type is int:
                        user_input = int(user_input_str)
                    elif expected_type is float:
                        user_input = float(user_input_str)
                    else:
                        user_input = user_input_str  # type: ignore[assignment]

                if condition(user_input):  # type: ignore[arg-type]
                    return user_input  # type: ignore[return-value]

                console.print(f"[bold red]✗ {error_msg}[/]")

            except ValueError:
                console.print(
                    f"[bold red]✗ Invalid input type. Expected {expected_type.__name__}.[/]"
                )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled.[/]")
        return None


def select_menu(
    options: list[str],
    title: str = "Select an option",
    help_text: str = "",
) -> Optional[int]:
    """
    Show an arrow-key navigable menu.

    Args:
        options: List of option labels
        title: Menu title
        help_text: Optional help block toggled with the '?' key

    Returns:
        Selected option index, or None if cancelled (Ctrl+C).
    """
    selected = 0
    show_help = False
    kb = KeyBindings()

    @kb.add("up")
    def _up(event) -> None:
        nonlocal selected
        selected = (selected - 1) % len(options)
        event.app.invalidate()

    @kb.add("down")
    def _down(event) -> None:
        nonlocal selected
        selected = (selected + 1) % len(options)
        event.app.invalidate()

    @kb.add("k")
    def _vim_up(event) -> None:
        nonlocal selected
        selected = (selected - 1) % len(options)
        event.app.invalidate()

    @kb.add("j")
    def _vim_down(event) -> None:
        nonlocal selected
        selected = (selected + 1) % len(options)
        event.app.invalidate()

    @kb.add("?")
    def _toggle_help(event) -> None:
        nonlocal show_help
        show_help = not show_help
        event.app.invalidate()

    @kb.add("enter")
    def _confirm(event) -> None:
        event.app.exit(result=selected)

    @kb.add("c-c")
    def _cancel(event) -> None:
        event.app.exit(result=None)

    def render_prompt() -> list[HTML]:
        lines: list[HTML] = [HTML(f"<b>{title}</b>"), HTML("")]
        for i, option in enumerate(options):
            marker = "▸" if i == selected else " "
            lines.append(HTML(f"<ansicyan>{marker} {i + 1}.</ansicyan> {option}"))
        lines.append(HTML(""))
        if show_help and help_text:
            lines.append(HTML("<ansiyellow>Help:</ansiyellow>"))
            for line in help_text.splitlines():
                lines.append(HTML(f"<dim>{line}</dim>"))
            lines.append(HTML(""))
        lines.append(HTML("<dim>↑/↓ move · Enter select · ? help · Ctrl+C cancel</dim>"))
        return lines

    try:
        return prompt(render_prompt, key_bindings=kb)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Operation cancelled.[/]")
        return None


def print_header(title: str, subtitle: str = "") -> None:
    """Prints a formatted header using Rich Rule."""
    console.print()
    rule = Rule(f"{title}", style="blue", align="center")
    console.print(rule)
    if subtitle:
        console.print(f"[dim cyan]{subtitle}[/]", justify="center")
    console.print()


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
