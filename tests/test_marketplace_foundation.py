import unittest
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, Table, select

from marketplace_fixtures import PostgresTestCase, safe_test_url


class FoundationTests(unittest.TestCase):
    def test_absent_enabled_database_is_rejected(self):
        from marketplace.config import Settings
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            Settings.from_mapping({"MARKETPLACE_ENABLED": True}, environ={})

    def test_disabled_registration_does_not_require_database(self):
        from flask import Flask
        from marketplace import register_marketplace
        app = Flask(__name__)
        app.config["MARKETPLACE_ENABLED"] = False
        self.assertFalse(register_marketplace(app))
        self.assertNotIn("marketplace_db", app.extensions)

    def test_production_rejects_weak_and_default_signing_secrets(self):
        from marketplace.config import Settings
        for key in ("", "secret", "saariv-stepper-rag-secret-2025", "change-me-to-a-long-random-string", "x" * 64):
            with self.subTest(key_length=len(key)), self.assertRaises(ValueError):
                Settings.from_mapping({"MARKETPLACE_ENABLED": True, "MARKETPLACE_ENV": "production",
                                       "DATABASE_URL": "postgresql+psycopg://db/app", "SECRET_KEY": key,
                                       "MARKETPLACE_PUBLIC_BASE_URL": "https://saariv.example"}, environ={})

    def test_production_sets_secure_cookie_policy(self):
        from flask import Flask
        from marketplace import register_marketplace
        app = Flask(__name__)
        app.config.update(MARKETPLACE_ENABLED=True, MARKETPLACE_ENV="production",
                          DATABASE_URL="postgresql+psycopg://db/app",
                          SECRET_KEY="a-synthetic-signing-key-with-enough-distinct-characters-12345",
                          MARKETPLACE_PUBLIC_BASE_URL="https://saariv.example")
        register_marketplace(app)
        for key, expected in (("SESSION_COOKIE_SECURE", True), ("SESSION_COOKIE_HTTPONLY", True),
                              ("SESSION_COOKIE_SAMESITE", "Lax")):
            self.assertEqual(app.config[key], expected)
        app.extensions["marketplace_db"].engine.dispose()

    def test_secrets_are_redacted(self):
        from marketplace.config import Settings
        settings = Settings.from_mapping({"MARKETPLACE_ENABLED": True,
            "DATABASE_URL": "postgresql+psycopg://db_user:synthetic-db-password@localhost/app",
            "SECRET_KEY": "synthetic-secret", "GOOGLE_CLIENT_SECRET": "synthetic-provider-secret"}, environ={})
        for secret in ("synthetic-db-password", "synthetic-secret", "synthetic-provider-secret"):
            self.assertNotIn(secret, repr(settings))

    def test_production_requires_https_public_callback_origin(self):
        from marketplace.config import Settings
        with self.assertRaises(ValueError):
            Settings.from_mapping({"MARKETPLACE_ENABLED": True, "MARKETPLACE_ENV": "production",
                "DATABASE_URL": "postgresql+psycopg://db/app",
                "SECRET_KEY": "a-synthetic-signing-key-with-enough-distinct-characters-12345",
                "MARKETPLACE_PUBLIC_BASE_URL": "http://saariv.example"}, environ={})

    def test_guest_card_contract_has_no_content_or_author_identifier(self):
        from marketplace.contracts import ExperienceCard, Principal
        card = ExperienceCard(uuid4(), "Deposits", "What I learned", {"domain": "Work"}, 20,
                              {"user_id": str(uuid4()), "display_name": "Private name", "source": "private"},
                              {"upvotes": 1, "downvotes": 0, "ranking_score": .6}, False)
        data = card.to_dict(principal=Principal(None, frozenset()))
        self.assertEqual(set(data), {"experience_id", "title", "teaser", "taxonomy", "price_coins", "author", "rating", "unlocked"})
        self.assertIsNone(data["author"])
        self.assertFalse(data["unlocked"])
        self.assertNotIn("Private name", str(data))

    def test_dto_nested_payloads_are_allowlisted(self):
        from marketplace.contracts import ExperienceCard, Principal, SearchPage
        card = ExperienceCard(uuid4(), "Title", "Teaser", {"domain": "Work", "source": "secret"}, 10,
            {"user_id": str(uuid4()), "display_name": "Author", "source": "secret"},
            {"upvotes": 0, "downvotes": 0, "ranking_score": .5, "body": "secret"}, False)
        data = SearchPage("opaque", [card], None, False, "lexical").to_dict(principal=Principal(uuid4(), frozenset()))
        self.assertNotIn("secret", str(data))

    def test_test_database_gate_is_explicit_and_safe(self):
        for value in ("", "sqlite://", "postgresql+psycopg://localhost/production"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                safe_test_url(value)
        with self.assertRaises(RuntimeError):
            safe_test_url("postgresql+psycopg://localhost/synthetic_test", "postgresql+psycopg://other@localhost/synthetic_test")


class DatabaseTests(PostgresTestCase):
    def test_transaction_rolls_back_domain_and_projection(self):
        metadata = MetaData()
        domain = Table("synthetic_domain", metadata, Column("id", Integer, primary_key=True))
        projection = Table("synthetic_projection", metadata, Column("id", Integer, primary_key=True))
        metadata.create_all(self.db.engine)
        try:
            with self.assertRaisesRegex(RuntimeError, "cancel"):
                with self.db.transaction() as session:
                    session.execute(domain.insert().values(id=1))
                    session.execute(projection.insert().values(id=1))
                    raise RuntimeError("cancel")
            with self.db.transaction() as session:
                self.assertEqual(session.execute(select(domain)).all(), [])
                self.assertEqual(session.execute(select(projection)).all(), [])
        finally:
            metadata.drop_all(self.db.engine)

    def test_migration_upgrade_downgrade_upgrade(self):
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import inspect, text
        schema = "test_migration_" + uuid4().hex
        with self.control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = self.test_url.update_query_dict({"options": "-csearch_path=" + schema})
        from marketplace.db import Database
        database = Database(url.render_as_string(hide_password=False))
        try:
            cfg = Config("alembic.ini")
            with database.engine.connect() as connection:
                cfg.attributes["connection"] = connection
                command.upgrade(cfg, "head")
                self.assertIn("users", inspect(connection).get_table_names())
                command.downgrade(cfg, "base")
                self.assertNotIn("users", inspect(connection).get_table_names())
                command.upgrade(cfg, "head")
                self.assertIn("oauth_identities", inspect(connection).get_table_names())
                connection.commit()
        finally:
            database.engine.dispose()
            with self.control.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


if __name__ == "__main__":
    unittest.main()
