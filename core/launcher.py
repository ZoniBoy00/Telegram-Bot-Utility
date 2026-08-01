"""Launcher script for running bot dumper in a separate window.

Usage:
    python -m core.launcher <bot_token> [options]

Options:
    --listen-only            Skip history dump, only listen for new messages
    --telegram-channel ID    Forward archives to a Telegram channel
    --discord-webhook URL    Forward archives to a Discord webhook
    --chat ID                Only dump history for this chat entity
    --history-limit N        Max messages to fetch per chat (default: all)
    --proxy host:port        SOCKS5 proxy for the Telegram connection
"""

import argparse
import asyncio
import os
import sys

try:
    import socks
    SOCKS_AVAILABLE = True
except ImportError:
    socks = None
    SOCKS_AVAILABLE = False


def parse_args(argv: list) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Telegram Bot Utility dumper")
    # Token is optional on the CLI so it can be passed securely via the
    # TBU_TOKEN environment variable instead of the process command line.
    parser.add_argument("bot_token", nargs="?", default=None,
                        help="Telegram bot token (or set TBU_TOKEN env var)")
    parser.add_argument("--listen-only", action="store_true",
                        help="Skip history dump, only listen for new messages")
    parser.add_argument("--telegram-channel", default=None,
                        help="Telegram channel ID to forward archives to")
    parser.add_argument("--discord-webhook", default=None,
                        help="Discord webhook URL to forward archives to")
    parser.add_argument("--chat", default=None,
                        help="Only dump history for this chat entity ID")
    parser.add_argument("--history-limit", type=int, default=None,
                        help="Max messages to fetch per chat (default: all)")
    parser.add_argument("--proxy", default=None,
                        help="SOCKS5 proxy as host:port")
    return parser.parse_args(argv)


def parse_proxy(proxy_str: str):
    """Parse a host:port string into a SOCKS5 proxy tuple."""
    if not SOCKS_AVAILABLE:
        print("PySocks is required for proxy support: pip install PySocks")
        return None
    try:
        host, port = proxy_str.rsplit(":", 1)
        return (socks.SOCKS5, host, int(port))
    except (ValueError, TypeError):
        print(f"Invalid proxy format (expected host:port): {proxy_str}")
        return None


async def main(args: argparse.Namespace) -> None:
    """Run the dumper with the given arguments."""
    from .dumper import dump_bot_history

    # Resolve the token: CLI arg first, then TBU_TOKEN environment variable.
    bot_token = args.bot_token or os.getenv("TBU_TOKEN")
    if not bot_token:
        print("Error: no bot token provided (pass it as an argument or set TBU_TOKEN).")
        sys.exit(1)

    proxy = parse_proxy(args.proxy) if args.proxy else None

    # Run the dumper
    try:
        await dump_bot_history(
            bot_token=bot_token,
            listen_only=args.listen_only,
            forward_to_telegram=args.telegram_channel,
            forward_to_discord=args.discord_webhook,
            target_chat_id=args.chat,
            history_limit=args.history_limit,
            proxy=proxy,
        )
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)
