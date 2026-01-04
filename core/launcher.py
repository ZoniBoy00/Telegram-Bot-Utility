"""Launcher script for running bot dumper in a separate window."""

import sys
import asyncio
from .dumper import dump_bot_history

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python -m core.launcher <bot_token> [listen_only] [telegram_channel] [discord_webhook]")
        sys.exit(1)
    
    bot_token = sys.argv[1]
    listen_only = sys.argv[2].lower() == 'true' if len(sys.argv) > 2 else False
    telegram_channel = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'None' else None
    discord_webhook = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'None' else None
    
    # Run the dumper
    # Run the dumper
    try:
        asyncio.run(dump_bot_history(
            bot_token=bot_token,
            listen_only=listen_only,
            forward_to_telegram=telegram_channel,
            forward_to_discord=discord_webhook
        ))
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"Error: {e}")
