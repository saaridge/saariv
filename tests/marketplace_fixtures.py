"""Synthetic PostgreSQL fixtures. Never fall back to an application database."""
import os
import re
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def safe_test_url(value=None, application_url=None):
    value = value if value is not None else os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise RuntimeError("TEST_DATABASE_URL is required; PostgreSQL gate cannot be skipped")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not re.search(r"(^|_)test($|_)", url.database or ""):
        raise RuntimeError("Use a dedicated PostgreSQL test database")
    application_url = application_url or os.environ.get("DATABASE_URL")
    if application_url:
        app_url = make_url(application_url)
        if (url.host, url.port or 5432, url.database) == (app_url.host, app_url.port or 5432, app_url.database):
            raise RuntimeError("Test and application databases must be different")
    return url


class PostgresTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from marketplace.db import Base, Database
        cls.test_url = safe_test_url()
        cls.schema = "test_mpf_" + uuid4().hex
        cls.control = create_engine(cls.test_url)
        with cls.control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{cls.schema}"'))
        cls.scoped_url = cls.test_url.update_query_dict({"options": "-csearch_path=" + cls.schema})
        cls.db = Database(cls.scoped_url.render_as_string(hide_password=False))
        # Model registration is explicit; migration tests exercise DDL separately.
        from marketplace.accounts import models  # noqa: F401
        Base.metadata.create_all(cls.db.engine)

    @classmethod
    def tearDownClass(cls):
        cls.db.engine.dispose()
        with cls.control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{cls.schema}" CASCADE'))
        cls.control.dispose()

    def setUp(self):
        from marketplace.db import Base
        with self.db.engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())

    def make_app(self, **config):
        from flask import Flask, jsonify
        from marketplace import register_marketplace
        from marketplace.security import current_principal, csrf_token, require_role
        app = Flask("marketplace-tests", template_folder=os.path.abspath("templates"))
        app.config.update(TESTING=True, SECRET_KEY="synthetic-test-signing-secret-with-48-characters-only",
                          MARKETPLACE_ENABLED=True, MARKETPLACE_ENV="test",
                          DATABASE_URL=self.scoped_url.render_as_string(hide_password=False),
                          MARKETPLACE_PUBLIC_BASE_URL="http://localhost")
        app.config.update(config)
        register_marketplace(app)
        self.addCleanup(app.extensions["marketplace_db"].engine.dispose)

        @app.get("/test/principal")
        def who():
            principal = current_principal()
            return jsonify(user_id=str(principal.user_id) if principal.user_id else None,
                           roles=sorted(principal.roles), csrf_token=csrf_token())

        @app.post("/test/admin")
        @require_role("admin")
        def admin():
            return jsonify(ok=True)
        return app
