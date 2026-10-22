"""Local demo acceptance with actual PostgreSQL and isolated synthetic data."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from marketplace.config import Settings
from marketplace_fixtures import PostgresTestCase


class MockConfigurationTests(unittest.TestCase):
    def test_mock_auth_cannot_be_enabled_in_production(self):
        with self.assertRaisesRegex(ValueError, "Mock"):
            Settings.from_mapping({"MARKETPLACE_ENABLED": True, "MARKETPLACE_MOCK_MODE": True,
                "MARKETPLACE_ENV": "production", "DATABASE_URL": "postgresql+psycopg://localhost/saariv_mock",
                "SECRET_KEY": "synthetic-production-signing-key-for-tests-only-123",
                "MARKETPLACE_PUBLIC_BASE_URL": "https://example.test"}, environ={})

    def test_mock_auth_rejects_the_normal_application_database(self):
        with self.assertRaisesRegex(ValueError, "Mock"):
            Settings.from_mapping({"MARKETPLACE_ENABLED": True, "MARKETPLACE_MOCK_MODE": True,
                "DATABASE_URL": "postgresql+psycopg://localhost/saariv_marketplace_dev"}, environ={})

    def test_mock_rejects_disabled_marketplace_and_remote_database_or_origin(self):
        base = {"MARKETPLACE_ENABLED": True, "MARKETPLACE_MOCK_MODE": True,
            "DATABASE_URL": "postgresql+psycopg://localhost/saariv_mock"}
        for change in ({"MARKETPLACE_ENABLED": False},
                {"DATABASE_URL": "postgresql+psycopg://example.test/saariv_mock"},
                {"MARKETPLACE_PUBLIC_BASE_URL": "http://example.test"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "Mock"):
                Settings.from_mapping({**base, **change}, environ={})

    def test_mock_database_connection_overrides_cannot_bypass_isolation(self):
        for suffix in ("?host=example.test", "?hostaddr=203.0.113.10", "?dbname=normal_application",
                "?service=production", "?servicefile=/tmp/service.conf"):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "Mock"):
                Settings.from_mapping({"MARKETPLACE_ENABLED": True, "MARKETPLACE_MOCK_MODE": True,
                    "DATABASE_URL": "postgresql+psycopg://localhost/saariv_mock"+suffix}, environ={})
        with self.assertRaisesRegex(ValueError, "Mock"):
            Settings.from_mapping({"MARKETPLACE_ENABLED": True, "MARKETPLACE_MOCK_MODE": True,
                "DATABASE_URL": "postgresql+psycopg://localhost/saariv_mock", "PGHOSTADDR": ""},
                environ={"PGHOSTADDR": "203.0.113.10"})


class MockFlowTests(PostgresTestCase):
    def setUp(self):
        from marketplace.mock.models import MockBase
        MockBase.metadata.create_all(self.db.engine)
        with self.db.engine.begin() as connection:
            for table in reversed(MockBase.metadata.sorted_tables):
                connection.execute(table.delete())
        super().setUp()
        self.app = self.make_app(MARKETPLACE_MOCK_MODE=True)
        self.demo = self.app.extensions["marketplace_mock"]
        self.demo.bootstrap()
        self.client = self.app.test_client()
        self.client.get("/login")

    def csrf(self):
        token = self.client.get_cookie("marketplace_session").value
        return self.app.extensions["marketplace_accounts"].session_record(token).csrf_token

    def post(self, path, data=None, status=200):
        response = self.client.post(path, json=data or {}, headers={"X-CSRF-Token": self.csrf()})
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def login(self, persona, next_path="/", query_id=None):
        token = self.client.get_cookie("marketplace_session").value
        intent = self.app.extensions["marketplace_accounts"].create_resume(
            token, next_path=next_path, query_id=query_id)
        response = self.client.post("/auth/mock/google", data={"persona": persona,
            "intent": intent, "csrf_token": self.csrf()})
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True)[:300])
        return response.headers["Location"]

    def credit_reader(self, coins=200):
        self.login("reader")
        funding = self.post("/api/wallet/recharges", {"coins": coins})
        self.post(f"/api/wallet/recharges/{funding['request_id']}/submitted")
        self.login("admin")
        self.post(f"/api/admin/recharges/{funding['request_id']}/approve")
        self.login("reader")
        return funding

    def test_guest_cards_are_limited_and_login_restores_exact_selection(self):
        page = self.post("/api/search", {"query": "moving", "limit": 999})
        self.assertEqual(len(page["items"]), 4)
        self.assertIsNone(page["next_cursor"])
        self.assertTrue(all(card["author"] is None and "body" not in card for card in page["items"]))
        selected = "/experiences/" + page["items"][0]["experience_id"]
        returned = self.login("reader", selected, page["query_id"])
        self.assertEqual(returned, selected + "?query_id=" + page["query_id"])

    def test_login_banner_persona_switch_preserves_pending_selection(self):
        page = self.post("/api/search", {"query": "moving"})
        selected = "/experiences/" + page["items"][0]["experience_id"]
        token = self.client.get_cookie("marketplace_session").value
        intent = self.app.extensions["marketplace_accounts"].create_resume(token,
            next_path=selected, query_id=page["query_id"])
        response = self.client.post("/demo/persona/reader", data={"next": "/", "intent": intent,
            "csrf_token": self.csrf()})
        self.assertEqual(response.location, selected + "?query_id=" + page["query_id"])

    def test_home_persona_switch_preserves_the_guest_query(self):
        page = self.post("/api/search", {"query": "moving"})
        response = self.client.post("/demo/persona/reader", data={"next": "/", "query_id": page["query_id"],
            "csrf_token": self.csrf()})
        self.assertEqual(response.location, "/?query_id="+page["query_id"])
        restored = self.client.get("/demo?query_id="+page["query_id"])
        self.assertEqual(restored.status_code, 200)
        self.assertIn("6 experiences to explore", restored.text)

    def test_all_three_mock_provider_choices_sign_in_and_rotate_the_session(self):
        from marketplace.mock.service import PERSONAS
        for provider in ("google", "linkedin", "facebook"):
            with self.subTest(provider=provider):
                token = self.client.get_cookie("marketplace_session").value
                intent = self.app.extensions["marketplace_accounts"].create_resume(token, next_path="/")
                response = self.client.post("/auth/mock/"+provider, data={"intent": intent,
                    "persona": "reader", "csrf_token": self.csrf()})
                self.assertEqual(response.status_code, 302)
                self.assertNotEqual(self.client.get_cookie("marketplace_session").value, token)
                self.assertIsNone(self.app.extensions["marketplace_accounts"].session_record(token))
                self.assertEqual(self.client.get("/test/principal").json["user_id"], str(PERSONAS["reader"]["id"]))

    def test_recharge_unlock_vote_and_reopen_do_not_charge_twice(self):
        self.login("reader")
        card = self.post("/api/search", {"query": "moving"})["items"][0]
        experience = card["experience_id"]
        self.assertEqual(self.client.get(f"/api/experiences/{experience}/content").status_code, 403)
        quote = self.post(f"/api/experiences/{experience}/quote")
        self.post(f"/api/experiences/{experience}/unlock", quote, status=402)
        funding = self.credit_reader()
        self.login("admin")
        self.post(f"/api/admin/recharges/{funding['request_id']}/approve")
        self.login("reader")
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 200)
        self.post(f"/api/experiences/{experience}/unlock", quote)
        repeat = self.post(f"/api/experiences/{experience}/unlock", quote)
        self.assertEqual(repeat["charged_coins"], 0)
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 200-card["price_coins"])
        self.assertIn("body", self.client.get(f"/api/experiences/{experience}/content").json)
        response = self.client.put(f"/api/experiences/{experience}/vote", json={"value": 1},
            headers={"X-CSRF-Token": self.csrf()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["upvotes"], 1)

    def test_draft_review_rewards_ten_once_and_blocks_duplicate_reward(self):
        self.login("author")
        payload = {"title": "My moving checklist", "teaser": "What I considered before moving.",
            "body": "I asked about housing deposits and planned my city move. I had not signed a lease.",
            "taxonomy": ["Housing"], "price_coins": 25}
        draft = self.post("/api/experiences/drafts", payload, status=201)
        draft = self.post(f"/api/experiences/drafts/{draft['draft_id']}/submit", {"version": draft["version"]})
        self.assertEqual(draft["status"], "submitted")
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 0)
        self.login("admin")
        self.post(f"/api/admin/experiences/{draft['draft_id']}/approve")
        self.post(f"/api/admin/experiences/{draft['draft_id']}/approve")
        self.login("author")
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 10)
        duplicate = self.post("/api/experiences/drafts", payload, status=201)
        self.post(f"/api/experiences/drafts/{duplicate['draft_id']}/submit", {"version": duplicate["version"]})
        self.login("admin")
        self.post(f"/api/admin/experiences/{duplicate['draft_id']}/approve", status=409)

    def test_withdrawal_reserves_and_settles_purchased_coins_once(self):
        self.credit_reader(100)
        self.post("/api/wallet/withdrawals", {"coins": 100}, status=400)
        self.credit_reader(10)
        funding = self.post("/api/wallet/withdrawals", {"coins": 100}, status=201)
        balance = self.client.get("/api/wallet").json
        self.assertEqual((balance["available_coins"], balance["reserved_coins"]), (10, 100))
        self.login("admin")
        self.post(f"/api/admin/withdrawals/{funding['request_id']}/start")
        self.post(f"/api/admin/withdrawals/{funding['request_id']}/settle")
        self.post(f"/api/admin/withdrawals/{funding['request_id']}/settle")
        self.login("reader")
        balance = self.client.get("/api/wallet").json
        self.assertEqual((balance["available_coins"], balance["reserved_coins"]), (10, 0))

    def test_parallel_unlocks_only_transfer_once(self):
        self.credit_reader()
        card = self.post("/api/search", {"query": "moving"})["items"][0]
        from marketplace.mock.service import PERSONAS
        reader = PERSONAS["reader"]["id"]
        quote = self.post(f"/api/experiences/{card['experience_id']}/quote")["quote_token"]
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda _: self.demo.unlock(reader, card["experience_id"], quote), range(5)))
        self.assertEqual(sum(row["charged_coins"] for row in results), card["price_coins"])
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 200-card["price_coins"])

    def test_mock_routes_require_loopback_csrf_and_admin_role(self):
        self.assertEqual(self.client.get("/login").headers["Referrer-Policy"], "same-origin")
        denied = self.client.post("/auth/mock/google", data={"persona": "admin"})
        self.assertEqual(denied.status_code, 403)
        for origin in ("null", "http://example.test"):
            denied = self.client.post("/auth/mock/google", data={"persona": "admin", "csrf_token": self.csrf()},
                headers={"Origin": origin})
            self.assertEqual(denied.status_code, 403)
        self.login("reader")
        self.post("/api/admin/recharges/00000000-0000-0000-0000-000000000000/approve", status=403)
        response = self.client.get("/login", environ_overrides={"REMOTE_ADDR": "203.0.113.10"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/login", base_url="http://example.test").status_code, 404)

    def test_mock_routes_cannot_start_a_real_provider_or_legacy_api(self):
        manager = self.app.extensions["marketplace_oauth"]
        with patch.object(manager, "client", return_value=object()), \
                patch.object(manager, "begin", side_effect=AssertionError("No real OAuth")) as begin:
            self.assertEqual(self.client.get("/auth/login/google").status_code, 503)
            begin.assert_not_called()
        self.assertEqual(self.client.post("/api/onboarding/step1", json={}).status_code, 503)

    def test_native_forms_preserve_selected_experience_and_never_auto_purchase(self):
        page = self.post("/api/search", {"query": "moving"})
        card = page["items"][0]
        eid, qid = card["experience_id"], page["query_id"]
        path = "/experiences/"+eid
        target = self.login("reader", path, qid)
        locked = self.client.get(target)
        self.assertEqual(locked.status_code, 200)
        self.assertNotIn('class="exact-story purchased-story"', locked.text)
        quote = self.post(path.replace("/experiences/", "/api/experiences/")+"/quote")
        response = self.client.post("/demo/experiences/"+eid+"/unlock", data={
            "quote_token": quote["quote_token"], "query_id": qid, "csrf_token": self.csrf()})
        self.assertIn("return_experience_id="+eid, response.location)
        self.assertEqual(self.client.get(response.location).status_code, 200)
        response = self.client.post("/demo/recharges", data={"coins": "200",
            "return_experience_id": eid, "query_id": qid, "csrf_token": self.csrf()})
        request_path = response.location
        rid = request_path.rsplit("/", 1)[1]
        self.assertEqual(self.client.get(request_path).status_code, 200)
        self.client.post("/demo/requests/"+rid+"/submitted", data={"csrf_token": self.csrf()})
        self.login("admin")
        self.client.post("/demo/admin/requests/"+rid+"/approve", data={"csrf_token": self.csrf()})
        self.login("reader")
        request_page = self.client.get(request_path)
        self.assertIn("Return to your experience", request_page.text)
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 200)
        self.assertEqual(self.client.get("/api/experiences/"+eid+"/content").status_code, 403)
        response = self.client.post("/demo/experiences/"+eid+"/unlock", data={
            "quote_token": quote["quote_token"], "query_id": qid, "csrf_token": self.csrf()})
        self.assertEqual(response.location, target)
        self.assertIn('class="exact-story purchased-story"', self.client.get(target).text)

    def test_private_queries_drafts_and_quotes_are_bound_to_the_persona(self):
        self.credit_reader()
        page = self.post("/api/search", {"query": "moving"})
        eid = next(card["experience_id"] for card in page["items"] if card["author"]["display_name"] == "Jordan Guide")
        quote = self.post("/api/experiences/"+eid+"/quote")
        draft = self.post("/api/experiences/drafts", {"body": "Private canary story.", "price_coins": 10}, status=201)
        self.login("author")
        self.post("/api/experiences/"+eid+"/unlock", quote, status=409)
        self.post("/api/search", {"query": "moving", "cursor": page["query_id"]+":0"}, status=403)
        self.assertEqual(self.client.get("/experiences/"+draft["draft_id"]+"/edit").status_code, 403)
        self.post("/api/experiences/drafts", {"body": "Cannot choose owner.", "price_coins": 10,
            "author_id": "00000000-0000-0000-0000-000000000000"}, status=403)

    def test_withdrawal_cancel_and_reject_release_the_reservation_once(self):
        self.credit_reader()
        funding = self.post("/api/wallet/withdrawals", {"coins": 100}, status=201)
        for _ in range(2):
            self.post("/api/wallet/withdrawals/"+funding["id"]+"/cancel")
        self.assertEqual(self.client.get("/api/wallet").json["available_coins"], 200)
        second = self.post("/api/wallet/withdrawals", {"coins": 100}, status=201)
        self.login("admin")
        self.post("/api/admin/withdrawals/"+second["id"]+"/settle", status=409)
        for _ in range(2):
            self.post("/api/admin/withdrawals/"+second["id"]+"/reject")
        self.login("reader")
        balance = self.client.get("/api/wallet").json
        self.assertEqual((balance["available_coins"], balance["reserved_coins"]), (200, 0))

    def test_parallel_duplicate_publications_award_one_reward(self):
        from marketplace.contracts import MarketplaceError
        from marketplace.mock.service import PERSONAS
        author, admin = PERSONAS["author"]["id"], PERSONAS["admin"]["id"]
        body = {"title": "Same story", "teaser": "A submitted story.", "body": "I planned a unique parallel moving story.",
            "taxonomy": ["Moving"], "price_coins": 10}
        drafts = [self.demo.save_draft(author, body) for _ in range(2)]
        for row in drafts:
            self.demo.submit(author, row["draft_id"], row["version"])
        def approve(row):
            try:
                return self.demo.review(admin, row["draft_id"])["reward_coins"]
            except MarketplaceError as error:
                self.assertEqual(error.code, "duplicate_experience")
                return 0
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sum(executor.map(approve, drafts)), 10)
        self.assertEqual(self.demo.wallet(author)["available_coins"], 10)


if __name__ == "__main__":
    unittest.main()
