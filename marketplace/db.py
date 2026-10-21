"""Shared SQLAlchemy boundary; domain services own the transaction."""
from contextlib import contextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Database:
    def __init__(self, url: str):
        parsed = make_url(url)
        if parsed.drivername != "postgresql+psycopg":
            raise ValueError("Marketplace requires a postgresql+psycopg DATABASE_URL")
        self.engine = create_engine(parsed, pool_pre_ping=True, hide_parameters=True)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self):
        """Commit all changes once or roll them all back; always close Session."""
        with self.session_factory() as session:
            with session.begin():
                yield session
