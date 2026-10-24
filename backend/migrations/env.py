"""Alembic environment: runs migrations online against the configured database."""

from alembic import context
from sqlalchemy import create_engine

from capturekit.config import database_url

config = context.config


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or database_url()
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
