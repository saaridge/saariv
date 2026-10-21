"""Alembic requires an explicit URL or caller-owned connection; no .env load."""
import os

from alembic import context
from sqlalchemy import create_engine, pool
from marketplace.db import Base
from marketplace.accounts import models  # noqa: F401

config = context.config


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for migrations")
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = config.attributes.get("connection")
    if connection is not None:
        migrate(connection)
    else:
        url = os.environ.get("DATABASE_URL")
        if not url or not url.startswith("postgresql+psycopg://"):
            raise RuntimeError("Explicit postgresql+psycopg DATABASE_URL is required for migrations")
        engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
        with engine.connect() as connection:
            migrate(connection)
        engine.dispose()
