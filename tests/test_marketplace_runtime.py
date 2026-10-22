"""Exercise marketplace registration through the real application entry point."""
import os
import runpy
from unittest.mock import patch

from marketplace_fixtures import PostgresTestCase


class RuntimeTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        config = {
            "MARKETPLACE_ENABLED": "true",
            "MARKETPLACE_ENV": "test",
            "DATABASE_URL": self.scoped_url.render_as_string(hide_password=False),
            "MARKETPLACE_PUBLIC_BASE_URL": "http://localhost",
            "FLASK_SECRET_KEY": "synthetic-runtime-test-signing-secret-only",
        }
        with patch.dict(os.environ, config), patch("dotenv.load_dotenv", return_value=False):
            self.app = runpy.run_path("app.py", run_name="saariv_runtime_test")["app"]
        self.app.config.update(TESTING=True)
        self.addCleanup(lambda: self.app.extensions.get("marketplace_db") and self.app.extensions["marketplace_db"].engine.dispose())
        self.client = self.app.test_client()

    def test_real_homepage_mounts_new_query_and_dictation_screen(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data-marketplace-home", response.data)
        self.assertIn(b"query-dictation-toggle", response.data)
        self.assertIn(b"csrf-token", response.data)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_plus_redirects_guest_to_the_real_social_login_page(self):
        response = self.client.get("/experiences/new")
        self.assertEqual(response.status_code, 302)
        login = self.client.get(response.headers["Location"])
        self.assertEqual(login.status_code, 200)
        for provider in (b"Google", b"LinkedIn", b"Facebook"):
            self.assertIn(provider, login.data)

    def test_unimplemented_search_is_honest_and_never_returns_fake_results(self):
        response = self.client.post("/api/search", json={"query": "synthetic query"})
        self.assertEqual(response.status_code, 503)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], "feature_unavailable")
        self.assertNotIn("items", data)

    def test_existing_try_page_remains_available(self):
        response = self.client.get("/try")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"story-dictation.js", response.data)

    def test_signed_in_editor_is_private_and_uses_server_principal(self):
        from marketplace.accounts.service import ProviderIdentity
        service = self.app.extensions["marketplace_accounts"]
        user = service.identity_login(ProviderIdentity("google", "synthetic-runtime-user"))
        ticket = service.issue_session(user.id)
        self.client.set_cookie("marketplace_session", ticket.token)
        response = self.client.get("/experiences/new")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"data-marketplace-editor", response.data)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn(b"0 coins", response.data)
