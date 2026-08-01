"""Search module for querying dumped JSONL history archives."""

import json
import os
from collections.abc import Iterator
from typing import Any

from rich.panel import Panel
from rich.table import Table

from .ui import console, print_error
from .utils import get_logger

logger = get_logger(__name__)

SEARCH_LIMIT = 100  # Max results to display per search


def iter_bot_directories(base_dir: str = ".") -> Iterator[str]:
    """
    Yield directories that look like bot output folders (contain bot.json).

    Args:
        base_dir: Directory to scan

    Yields:
        Paths to bot data folders.
    """
    if os.path.isfile(os.path.join(base_dir, 'bot.json')):
        yield base_dir
        return

    for entry in os.listdir(base_dir):
        full = os.path.join(base_dir, entry)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, 'bot.json')):
            yield full


def iter_jsonl_messages(bot_dir: str) -> Iterator[tuple]:
    """
    Yield (chat_id, message_dict) pairs from all JSONL archives in a bot folder.

    Args:
        bot_dir: Bot data folder path

    Yields:
        Tuples of (chat_id, message dict).
    """
    for root, _dirs, files in os.walk(bot_dir):
        for filename in files:
            if not filename.endswith('_messages.jsonl'):
                continue
            chat_id = filename.replace('_messages.jsonl', '')
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield chat_id, json.loads(line)
                        except json.JSONDecodeError:
                            continue
            except OSError as e:
                logger.warning("Could not read %s: %s", filepath, e)


def search_history(query: str, limit: int = SEARCH_LIMIT) -> None:
    """
    Search all dumped history archives for a term and display matches.

    Args:
        query: Search term
        limit: Maximum number of results to display
    """
    query_lower = query.lower().strip()
    if not query_lower:
        print_error("Search term cannot be empty.")
        return

    results: list[dict[str, Any]] = []
    bot_dirs = list(iter_bot_directories())

    if not bot_dirs:
        console.print("[yellow]No bot data folders found. Run the dumper first.[/]")
        return

    with console.status("[bold cyan]Searching history archives...[/]", spinner="dots"):
        for bot_dir in bot_dirs:
            for chat_id, msg in iter_jsonl_messages(bot_dir):
                text = msg.get('text', '') or ''
                media = msg.get('media_path', '') or ''
                haystack = f"{text} {media}".lower()

                if query_lower in haystack:
                    entry = {
                        'bot': os.path.basename(bot_dir),
                        'chat_id': chat_id,
                        'msg_id': msg.get('id'),
                        'date': msg.get('date', ''),
                        'from_id': msg.get('from_id', ''),
                        'text': text,
                        'media': media,
                    }
                    results.append(entry)
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                break

    if not results:
        console.print(f"[yellow]No matches found for '{query}'.[/]")
        return

    table = Table(title=f"Search results for '{query}' ({len(results)} shown)")
    table.add_column("Bot", style="cyan", no_wrap=True)
    table.add_column("Chat", style="magenta", no_wrap=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Date", style="green", no_wrap=True)
    table.add_column("From", style="yellow", no_wrap=True)
    table.add_column("Message", style="white", overflow="fold", max_width=60)

    for r in results:
        preview = r['text'][:120].replace('\n', ' ')
        if r['media']:
            preview = f"[Media: {r['media']}] {preview}"
        table.add_row(
            r['bot'],
            r['chat_id'],
            str(r['msg_id']),
            r['date'],
            r['from_id'],
            preview or "(no text)",
        )

    console.print(Panel(table, border_style="cyan"))
    console.print(f"[dim]Total matches found: {len(results)}[/]")
