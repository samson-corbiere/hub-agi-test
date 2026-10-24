"""Shared fixtures: a real Postgres test database and the API behind an HTTP client.

The test database comes from TEST_DATABASE_URL (environment, or the repo-root .env).
Once per run its schema is dropped and rebuilt by the Alembic migrations, so tests
exercise the real schema. Every test then starts from empty tables.
"""

import json
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text

from capturekit.app import create_app

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
EXAMPLE_DIR = REPO_DIR / "contract" / "example-session"

load_dotenv(REPO_DIR / ".env")


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set (see .env.example).")
    # The schema is dropped on every run: refuse anything that isn't a test database.
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.fail(f"TEST_DATABASE_URL must point to a *_test database, got {database!r}.")
    return url


@pytest.fixture(scope="session")
def alembic_config():
    """Alembic, pointed at the test database."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", _test_database_url())
    return config


@pytest.fixture(scope="session")
def database_url(alembic_config):
    url = _test_database_url()
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    command.upgrade(alembic_config, "head")
    return url


@pytest.fixture(scope="session")
def engine(database_url):
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    """A connection for asserting on rows. Tables are emptied before each test."""
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars()
        names = ", ".join(f'"{name}"' for name in tables)
        if names:
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    with engine.connect() as conn:
        yield conn


@pytest.fixture
def client(database_url, db):
    app = create_app(database_url=database_url)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def example_meta():
    """The contract's example meta.json, as the app sends it."""
    return json.loads((EXAMPLE_DIR / "meta.json").read_text())
