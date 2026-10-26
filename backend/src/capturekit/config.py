"""Configuration from the environment, with the repo-root .env as a fallback."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parents[3]

load_dotenv(REPO_DIR / ".env")


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set (see .env.example).")
    return url


def data_dir() -> Path:
    """Where received session files are stored. A relative path is relative to the cwd."""
    return Path(os.environ.get("DATA_DIR") or "data")
