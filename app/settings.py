# app/settings.py
from __future__ import annotations

import os
from dotenv import load_dotenv

# Load .env automatically (safe if file not present)
load_dotenv()


def _get_env(name: str, default: str | None = None) -> str:
    """
    Fetch environment variable.
    Strips whitespace.
    Returns default if provided and var is missing.
    """
    value = os.getenv(name)
    if value is None:
        if default is not None:
            return default
        return ""
    return value.strip()


def require_env(name: str, value: str) -> None:
    """
    Raise a clear error if an env var is missing.
    Designed for use inside Supabase/LLM initializers.
    """
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}\n\n"
            f"Add it to your .env file or environment before running the app."
        )


# ---- Supabase ----
SUPABASE_URL: str = _get_env("SUPABASE_URL")
SUPABASE_SERVICE_KEY: str = _get_env("SUPABASE_SERVICE_KEY")


# ---- Optional Grok / xAI ----
XAI_API_KEY: str = _get_env("XAI_API_KEY")
GROK_API_KEY: str = _get_env("GROK_API_KEY")
GROK_MODEL: str = _get_env("GROK_MODEL", "grok-4-1-fast-reasoning")
GROK_MAX_TOKENS: int = int(_get_env("GROK_MAX_TOKENS", "4000"))
