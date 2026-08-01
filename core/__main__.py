"""Module entry point: allows running via `python -m core`."""

import os
import sys

# Ensure the repository root is importable when running from a checkout
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cli import run  # noqa: E402

if __name__ == "__main__":
    run()
