# Development Guide

This document describes the project structure, how to extend it, and the
development workflow.

## Repository Layout

```bash
telegram-bot-utility/
├── core/                    # Main package
│   ├── __init__.py          # Package metadata (__version__)
│   ├── __main__.py          # Entry point for `python -m core`
│   ├── cli.py               # Interactive menu and user flows
│   ├── config.py            # Settings (env vars + defaults)
│   ├── ui.py                # Console, prompts and display helpers
│   ├── utils.py             # Logging and retry helpers
│   ├── api.py               # Telegram Bot API client (sending, chat list, info)
│   ├── dumper.py            # Telethon-based history & media dumper
│   ├── forwarder.py         # Forwarding to Telegram channels / Discord webhooks
│   ├── launcher.py          # CLI launcher for the dumper subprocess
│   └── search.py            # Search over dumped JSONL archives
├── docs/                    # Documentation
│   ├── FORWARDING_GUIDE.md  # How to set up Telegram/Discord forwarding
│   └── DEVELOPMENT.md       # This file
├── tests/                   # Unit tests (unittest, no external test runner)
├── main.py                  # Thin wrapper: `python main.py`
├── pyproject.toml           # Package metadata, dependencies, tooling config
├── requirements.txt         # Convenience wrapper (`-e .`)
└── .env.example             # Configuration template
```

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `core/cli.py` | Interactive menu, collects user input, orchestrates features |
| `core/config.py` | All settings; env vars override defaults, `validate_telethon_config()` |
| `core/ui.py` | Rich console, `validate_input`, print helpers — no business logic |
| `core/utils.py` | `get_logger()` and `retry()` — generic, framework-agnostic |
| `core/api.py` | Telegram Bot API over HTTP (requests). Pure functions, testable |
| `core/dumper.py` | Telethon client, history dumping, media storage, live listening |
| `core/forwarder.py` | Sends messages/archives to Telegram channel or Discord webhook |
| `core/search.py` | Reads dumped JSONL archives and displays matches |

## Architecture Rules

- **`ui` is the only module allowed to talk to the terminal.** Business logic
  modules (`api`, `dumper`, `forwarder`, `search`) should receive data and
  return results; they may use `ui.console` for progress/status output but
  must not call `validate_input` (prompts belong in `cli`).
- **No circular imports.** Import order is one-directional:
  `config → ui → utils → {api, forwarder, search} → dumper → cli`.
- **Tokens are secrets.** Never store them on disk or pass them via command
  line arguments. The dumper launcher reads the token from the `TBU_TOKEN`
  environment variable.
- **Comments in code are English**; user-facing strings are English too.

## Configuration

All settings live in `core/config.py`. To add a new setting:

1. Add a default constant, reading from an env var where useful (see
   `_env_int` / `_env_bool` / `_env_float` helpers).
2. Document it in `.env.example` and in the README configuration table.

## Adding a New CLI Mode

1. Implement a `handle_*()` function that collects input (via
   `ui.validate_input`) and calls the underlying business logic.
2. Add an entry `(label, handler)` to `MENU_ITEMS` in `core/cli.py` — the
   arrow-key menu and numeric options are generated automatically.
3. The handler runs from the `main()` dispatch loop; no other wiring needed.

## Tests

Tests use the standard-library `unittest` runner, so no extra test framework
is required at runtime:

```bash
python -m unittest discover -s tests -v
```

Guidelines:

- Test pure logic (parsing, formatting, validation) — avoid network calls.
- Mock `requests` and Telethon interactions where needed.
- Keep tests independent of a real Telegram account.

## Linting & Formatting

Ruff is configured in `pyproject.toml`:

```bash
ruff check .
```

Rules: `E`, `F`, `I` (import sorting), `B`, `UP`. Auto-fix with:

```bash
ruff check . --fix
```

## Releasing a New Version

1. Bump `__version__` in `core/__init__.py` (single source of truth —
   `pyproject.toml` reads it dynamically).
2. Update the README if user-facing behavior changed.
3. Run tests + lint locally; CI runs them on push (Python 3.9–3.12).
