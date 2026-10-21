from datetime import datetime, timedelta, timezone
import unittest
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from marketplace_fixtures import PostgresTestCase


class AccountTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        from marketplace.accounts.service import AccountService, ProviderIdentity
        self.service = AccountService(self.db)
        self.Proof = ProviderIdentity

    def user(self, provider="google", subject="synthetic-subject", email=None):
        return self.service.identity_login(self.Proof(provider, subject, email, "Synthetic Author"))

    def test_same_email_does_not_link_provider_subjects(self):
        first = self.user(email="synthetic@example.invalid")
        second = self.user("linkedin", "other-subject", "synthetic@example.invalid")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(self.user().id, first.id)

    def test_provider_subject_uniqueness_is_enforced_in_postgresql(self):
        from marketplace.accounts.models import OAuthIdentity
        first, second = self.user(), self.user("facebook", "second")
        with self.assertRaises(IntegrityError):
            with self.db.transaction() as session:
                session.add(OAuthIdentity(user_id=second.id, provider="google", subject="synthetic-subject"))
        with self.db.transaction() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(OAuthIdentity)), 2)

    def test_session_rotation_revokes_old_token_and_rotates_csrf(self):
        ticket = self.service.issue_session()
        user = self.user()
        signed_in = self.service.issue_session(user.id, previous_token=ticket.token)
        self.assertNotEqual(signed_in.token, ticket.token)
        self.assertNotEqual(signed_in.csrf_token, ticket.csrf_token)
        self.assertIsNone(self.service.principal(ticket.token).user_id)
        self.assertEqual(self.service.principal(signed_in.token).user_id, user.id)
        from marketplace.accounts.models import ServerSession
        with self.db.transaction() as session:
            saved = session.scalars(select(ServerSession)).all()
            self.assertNotIn(ticket.token, repr([row.digest for row in saved]))

    def test_revoked_expired_and_disabled_user_sessions_are_guests(self):
        from marketplace.accounts.models import ServerSession, User
        from marketplace.accounts.service import token_digest
        user = self.user()
        revoked = self.service.issue_session(user.id)
        self.service.revoke_session(revoked.token)
        self.assertIsNone(self.service.principal(revoked.token).user_id)
        expired = self.service.issue_session(user.id)
        with self.db.transaction() as session:
            session.get(ServerSession, token_digest(expired.token)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertIsNone(self.service.principal(expired.token).user_id)
        disabled = self.service.issue_session(user.id)
        with self.db.transaction() as session:
            session.get(User, user.id).is_active = False
        self.assertIsNone(self.service.principal(disabled.token).user_id)

    def test_explicit_identity_link_requires_login_and_rejects_conflicts(self):
        from marketplace.contracts import Principal, MarketplaceError
        first, second = self.user(), self.user("linkedin", "other")
        proof = self.Proof("linkedin", "other", None, None)
        for actor in (Principal(), Principal(first.id, frozenset())):
            with self.subTest(actor=actor.user_id), self.assertRaises(MarketplaceError):
                self.service.link_identity(principal=actor, proof=proof)
        self.service.link_identity(principal=Principal(first.id, frozenset()),
                                   proof=self.Proof("facebook", "new-link", None, None))
        self.assertEqual(self.user("facebook", "new-link").id, first.id)
        self.assertNotEqual(second.id, first.id)

    def test_request_ids_and_roles_cannot_spoof_server_principal(self):
        app = self.make_app()
        client = app.test_client()
        response = client.get("/test/principal?user_id=" + str(uuid4()), headers={"X-User-Id": str(uuid4()), "X-Roles": "admin"})
        self.assertIsNone(response.json["user_id"])
        self.assertEqual(response.json["roles"], [])
        self.assertEqual(client.post("/test/admin", json={"user_id": str(uuid4()), "roles": ["admin"]}).status_code, 401)

    def test_roles_are_loaded_from_server_account(self):
        app = self.make_app()
        user = self.user()
        ticket = self.service.issue_session(user.id)
        client = app.test_client()
        client.set_cookie("marketplace_session", ticket.token)
        self.assertEqual(client.post("/test/admin", headers={"X-CSRF-Token": ticket.csrf_token}).status_code, 403)
        from marketplace.accounts.models import User
        with self.db.transaction() as session:
            session.get(User, user.id).roles = ["admin"]
        self.assertEqual(client.post("/test/admin", headers={"X-CSRF-Token": ticket.csrf_token}).status_code, 200)

    def test_logout_requires_csrf_and_same_origin_then_revokes(self):
        app = self.make_app()
        user = self.user()
        ticket = self.service.issue_session(user.id)
        client = app.test_client()
        client.set_cookie("marketplace_session", ticket.token)
        self.assertEqual(client.post("/auth/logout").status_code, 403)
        self.assertEqual(client.post("/auth/logout", headers={"X-CSRF-Token": "wrong"}).status_code, 403)
        self.assertEqual(client.post("/auth/logout", headers={"X-CSRF-Token": ticket.csrf_token, "Origin": "https://evil.invalid"}).status_code, 403)
        self.assertEqual(self.service.principal(ticket.token).user_id, user.id)
        self.assertEqual(client.post("/auth/logout", headers={"X-CSRF-Token": ticket.csrf_token}).status_code, 200)
        self.assertIsNone(self.service.principal(ticket.token).user_id)

    def test_arbitrary_owner_id_cannot_claim_private_data(self):
        from marketplace.accounts.models import PrivateAvatarOwner
        app = self.make_app()
        ticket = self.service.issue_session(self.user().id)
        client = app.test_client()
        client.set_cookie("marketplace_session", ticket.token)
        response = client.post("/auth/claim-owner", json={"owner_id": "victim-owner"}, headers={"X-CSRF-Token": ticket.csrf_token})
        self.assertEqual(response.status_code, 403)
        with self.db.transaction() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(PrivateAvatarOwner)), 0)

    def test_signed_legacy_cookie_claim_is_single_use(self):
        from marketplace.accounts.models import PrivateAvatarOwner
        app = self.make_app()
        user = self.user()
        ticket = self.service.issue_session(user.id)
        client = app.test_client()
        client.set_cookie("marketplace_session", ticket.token)
        with client.session_transaction() as legacy:
            legacy["knowledge_owner"] = "synthetic-private-owner"
        headers = {"X-CSRF-Token": ticket.csrf_token}
        self.assertEqual(client.post("/auth/claim-owner", json={}, headers=headers).status_code, 200)
        self.assertEqual(client.post("/auth/claim-owner", json={}, headers=headers).status_code, 409)
        with self.db.transaction() as session:
            link = session.scalar(select(PrivateAvatarOwner))
            self.assertEqual(link.owner_id, "synthetic-private-owner")
            self.assertEqual(link.user_id, user.id)

    def test_forged_legacy_cookie_is_rejected(self):
        app = self.make_app()
        ticket = self.service.issue_session(self.user().id)
        client = app.test_client()
        client.set_cookie("marketplace_session", ticket.token)
        client.set_cookie("session", "eyJrbm93bGVkZ2Vfb3duZXIiOiJ2aWN0aW0ifQ.bad-signature")
        self.assertEqual(client.post("/auth/claim-owner", json={}, headers={"X-CSRF-Token": ticket.csrf_token}).status_code, 403)

    def test_resume_intent_restores_experience_and_verified_query_once(self):
        from marketplace.contracts import Principal, MarketplaceError
        guest = self.service.issue_session()
        path = "/experiences/" + str(uuid4())
        intent = self.service.create_resume(guest.token, next_path=path, query_id="opaque-query-id")
        principal = Principal(self.user().id, frozenset())
        seen = []
        def verify(**data):
            seen.append(data)
            return data["query_id"] == "opaque-query-id"
        target = self.service.consume_resume(intent, guest.token, principal=principal, query_owner_check=verify)
        self.assertEqual(target.next_path, path)
        self.assertEqual(target.query_id, "opaque-query-id")
        self.assertEqual(seen[0]["principal"], principal)
        self.assertNotIn("opaque-query-id", intent)
        with self.assertRaises(MarketplaceError):
            self.service.consume_resume(intent, guest.token, principal=principal, query_owner_check=verify)

    def test_resume_rejects_foreign_session_and_expiry(self):
        from marketplace.contracts import Principal, MarketplaceError
        from marketplace.accounts.models import ResumeIntent
        from marketplace.accounts.service import token_digest
        guest, foreign = self.service.issue_session(), self.service.issue_session()
        intent = self.service.create_resume(guest.token, next_path="/experiences/new")
        with self.assertRaises(MarketplaceError):
            self.service.consume_resume(intent, foreign.token, principal=Principal(self.user().id, frozenset()))
        with self.db.transaction() as session:
            session.get(ResumeIntent, token_digest(intent)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaises(MarketplaceError):
            self.service.consume_resume(intent, guest.token, principal=Principal(self.user().id, frozenset()))

    def test_unverified_or_foreign_query_id_never_becomes_authority(self):
        from marketplace.contracts import Principal
        guest = self.service.issue_session()
        principal = Principal(self.user().id, frozenset())
        for verifier in (None, lambda **kwargs: False):
            intent = self.service.create_resume(guest.token, next_path="/", query_id="foreign-query-id")
            target = self.service.consume_resume(intent, guest.token, principal=principal, query_owner_check=verifier)
            self.assertIsNone(target.query_id)

    def test_return_paths_reject_open_redirects_and_query_payloads(self):
        from marketplace.contracts import MarketplaceError
        guest = self.service.issue_session()
        for path in ("https://evil.invalid", "//evil.invalid", "/\\evil.invalid", "/%2f%2fevil.invalid",
                     "/auth/login/google", "/?story=private", "/experiences/new#secret", "/\r\nLocation:bad"):
            with self.subTest(path=repr(path)), self.assertRaises(MarketplaceError):
                self.service.create_resume(guest.token, next_path=path)


if __name__ == "__main__":
    unittest.main()
