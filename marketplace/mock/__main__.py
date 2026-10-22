"""Explicit initialization: python -m marketplace.mock init."""
import sys

from marketplace.config import Settings
from marketplace.db import Database
from .service import DemoService


def main():
    if sys.argv[1:] != ["init"]:
        raise SystemExit("Usage: python -m marketplace.mock init")
    settings = Settings.from_mapping({})
    if not settings.mock_mode:
        raise SystemExit("Set MARKETPLACE_ENABLED=true and MARKETPLACE_MOCK_MODE=true with a dedicated local _mock database.")
    db = Database(settings.database_url)
    try:
        DemoService(db, settings.secret_key or "local-demo-initialization").bootstrap()
        print("Local demo initialized: Reader, Author, Admin and six synthetic experiences. No real payments.")
    finally:
        db.engine.dispose()


if __name__ == "__main__":
    main()
