from datetime import timedelta
from html import unescape
import json
import re
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from joserfc import jwt
from joserfc.jwk import RSAKey
import requests
from sqlalchemy import select, func, event, MetaData, Table, Column, Integer

from marketplace_fixtures import PostgresTestCase


class OAuthTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.key = RSAKey.generate_key(2048, {"kid": "synthetic-provider-key"})
        cls.wrong_key = RSAKey.generate_key(2048, {"kid": "synthetic-provider-key"})

    def setUp(self):
        super().setUp()
        self.app = self.make_app(GOOGLE_CLIENT_ID="synthetic-google-client", GOOGLE_CLIENT_SECRET="synthetic-google-secret",
            LINKEDIN_CLIENT_ID="synthetic-linkedin-client", LINKEDIN_CLIENT_SECRET="synthetic-linkedin-secret",
            FACEBOOK_CLIENT_ID="synthetic-facebook-client", FACEBOOK_CLIENT_SECRET="synthetic-facebook-secret",
            FACEBOOK_GRAPH_VERSION="v26.0", MARKETPLACE_QUERY_OWNER_CHECK=lambda **data: data["query_id"] == "opaque-query-id")
        self.client = self.app.test_client()
        self.overrides = {}
        self.omit = set()
        self.invalid_signature = False
        self.facebook_debug = {}
        self.facebook_profile = {}
        self.subject = "synthetic-provider-subject"
        self.with_email = True
        self.during_exchange = None
        self.requests_seen = []
        owner = self
        self.transport = patch("requests.sessions.Session.send", new=lambda session, request, **kwargs: owner.http(request, **kwargs))
        self.transport.start()
        self.addCleanup(self.transport.stop)

    def http(self, prepared, **kwargs):
        """Only network I/O is replaced; Authlib runs its real JWT checks."""
        url = urlsplit(prepared.url)
        self.requests_seen.append((prepared.method, url.hostname, url.path))
        google = "google" in url.hostname or "googleapis" in url.hostname
        provider = "google" if google else "linkedin"
        issuer = "https://accounts.google.com" if google else "https://www.linkedin.com/oauth"
        if "openid-configuration" in url.path:
            data = {"issuer": issuer,
                "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth" if google else "https://www.linkedin.com/oauth/v2/authorization",
                "token_endpoint": "https://oauth2.googleapis.com/token" if google else "https://www.linkedin.com/oauth/v2/accessToken",
                "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs" if google else "https://www.linkedin.com/oauth/openid/jwks",
                "id_token_signing_alg_values_supported": ["RS256"], "response_types_supported": ["code"]}
        elif url.path.endswith(("/certs", "/jwks")):
            data = {"keys": [self.key.as_dict()]}
        elif url.hostname == "graph.facebook.com" and url.path.endswith("/oauth/access_token"):
            data = {"access_token": "synthetic-facebook-token", "token_type": "Bearer", "expires_in": 3600}
        elif url.hostname == "graph.facebook.com" and url.path.endswith("/debug_token"):
            data = {"data": {"is_valid": True, "app_id": "synthetic-facebook-client", "type": "USER",
                "user_id": self.subject, "expires_at": int(time.time()) + 3600,
                "data_access_expires_at": int(time.time()) + 7200, **self.facebook_debug}}
        elif url.hostname == "graph.facebook.com" and url.path.endswith("/me"):
            data = {"id": self.subject, "name": "Synthetic Person", **self.facebook_profile}
            if self.with_email:
                data["email"] = "synthetic@example.invalid"
        elif url.path in {"/token", "/oauth/v2/accessToken"}:
            if self.during_exchange:
                self.during_exchange()
            claims = {"iss": issuer, "aud": "synthetic-" + provider + "-client", "sub": self.subject,
                "iat": int(time.time()) - 1, "exp": int(time.time()) + 600,
                "nonce": self.nonce, "name": "Synthetic Person", **self.overrides}
            if self.with_email:
                claims["email"] = "synthetic@example.invalid"
            for field in self.omit:
                claims.pop(field, None)
            signed = jwt.encode({"alg": "RS256", "kid": "synthetic-provider-key"}, claims,
                                self.wrong_key if self.invalid_signature else self.key)
            data = {"access_token": "synthetic-access-token", "token_type": "Bearer", "expires_in": 3600,
                    "id_token": signed}
            if "id_token" in self.omit:
                data.pop("id_token")
        else:
            raise AssertionError("Unexpected external OAuth request")
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(data).encode()
        response.headers["Content-Type"] = "application/json"
        response.request = prepared
        response.url = prepared.url
        return response

    def begin(self, provider="google", next_path="/", query_id=None, client=None):
        client = client or self.client
        params = {"next": next_path}
        if query_id:
            params["query_id"] = query_id
        page = client.get("/login?" + urlencode(params))
        self.assertEqual(page.status_code, 200)
        links = [unescape(link) for link in re.findall(r'href="([^"]+)"', page.get_data(as_text=True))]
        target = next(link for link in links if "/auth/login/" + provider + "?" in link)
        response = client.get(target)
        self.assertEqual(response.status_code, 302)
        data = parse_qs(urlsplit(response.location).query)
        self.state = data["state"][0]
        self.nonce = data.get("nonce", [None])[0]
        self.provider_url = response.location
        self.callback_path = "/auth/callback/" + provider
        return data

    def callback(self, **params):
        return self.client.get(self.callback_path + "?" + urlencode({"state": self.state, "code": "synthetic-code", **params}))

    def authenticated_sessions(self):
        from marketplace.accounts.models import ServerSession
        with self.db.transaction() as session:
            return session.scalar(select(func.count()).select_from(ServerSession).where(ServerSession.user_id.is_not(None)))

    def begin_link(self):
        from marketplace.accounts.service import ProviderIdentity
        service = self.app.extensions["marketplace_accounts"]
        user = service.identity_login(ProviderIdentity("google", "initial-link-user"))
        ticket = service.issue_session(user.id)
        self.client.set_cookie("marketplace_session", ticket.token)
        response = self.client.post("/auth/link/linkedin", headers={"X-CSRF-Token": ticket.csrf_token})
        self.assertEqual(response.status_code, 302)
        data = parse_qs(urlsplit(response.location).query)
        self.state, self.nonce, self.callback_path = data["state"][0], data["nonce"][0], "/auth/callback/linkedin"
        return service, user, ticket

    def fail_authenticated_session_flush(self):
        from marketplace.accounts.models import ServerSession
        def fail(session, flush_context, instances):
            if any(isinstance(row, ServerSession) and row.user_id for row in session.new):
                raise RuntimeError("synthetic session-store failure")
        factory = self.app.extensions["marketplace_db"].session_factory
        event.listen(factory, "before_flush", fail)
        self.addCleanup(event.remove, factory, "before_flush", fail)

    def test_linkedin_without_email_signs_in_by_subject_and_resumes(self):
        self.with_email = False
        path = "/experiences/" + str(uuid4())
        self.begin("linkedin", path, "opaque-query-id")
        old_cookie = self.client.get_cookie("marketplace_session").value
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, path + "?query_id=opaque-query-id")
        self.assertEqual(self.authenticated_sessions(), 1)
        self.assertNotEqual(self.client.get_cookie("marketplace_session").value, old_cookie)
        self.assertIsNone(self.app.extensions["marketplace_accounts"].principal(old_cookie).user_id)
        from marketplace.accounts.models import User, ResumeIntent
        with self.db.transaction() as session:
            self.assertIsNone(session.scalar(select(User)).email)
            self.assertIsNotNone(session.scalar(select(ResumeIntent)).consumed_at)

    def test_callback_with_wrong_state_creates_no_session(self):
        self.begin()
        self.assertEqual(self.callback(state="wrong-state").status_code, 400)
        self.assertEqual(self.authenticated_sessions(), 0)

    def test_google_accepts_both_documented_issuer_forms(self):
        self.begin()
        self.overrides = {"iss": "accounts.google.com"}
        self.assertEqual(self.callback().status_code, 302)
        self.assertEqual(self.authenticated_sessions(), 1)

    def test_oidc_rejects_nonce_signature_issuer_audience_expiry_and_missing_claims(self):
        cases = (({"nonce": "wrong"}, set(), False), ({"iss": "https://evil.invalid"}, set(), False),
                 ({"aud": "another-client"}, set(), False), ({"exp": int(time.time()) - 10}, set(), False),
                 ({}, set(), True), ({}, {"nonce"}, False), ({}, {"sub"}, False), ({}, {"id_token"}, False))
        for overrides, omit, signature in cases:
            with self.subTest(overrides=overrides, omit=omit, signature=signature):
                self.client = self.app.test_client()
                self.begin()
                self.overrides, self.omit, self.invalid_signature = overrides, omit, signature
                response = self.callback()
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.authenticated_sessions(), 0)

    def test_consent_denial_consumes_flow_without_authentication(self):
        self.begin()
        response = self.callback(error="access_denied", error_description="<script>untrusted</script>")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("<script>", response.get_data(as_text=True))
        self.assertEqual(self.authenticated_sessions(), 0)
        self.assertEqual(self.callback().status_code, 400)

    def test_callback_replay_cannot_create_second_session(self):
        self.begin()
        self.assertEqual(self.callback().status_code, 302)
        self.assertEqual(self.callback().status_code, 400)
        self.assertEqual(self.authenticated_sessions(), 1)

    def test_callback_is_bound_to_original_browser_session(self):
        self.begin()
        other = self.app.test_client()
        response = other.get(self.callback_path + "?" + urlencode({"state": self.state, "code": "synthetic-code"}))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.authenticated_sessions(), 0)

    def test_revocation_during_provider_exchange_cannot_resurrect_session(self):
        self.begin()
        token = self.client.get_cookie("marketplace_session").value
        service = self.app.extensions["marketplace_accounts"]
        self.during_exchange = lambda: service.revoke_session(token)
        response = self.callback()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.authenticated_sessions(), 0)
        from marketplace.accounts.models import OAuthIdentity
        with self.db.transaction() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(OAuthIdentity)), 0)

    def test_expired_intent_does_not_commit_identity_link(self):
        from marketplace.accounts.models import ResumeIntent, OAuthIdentity, AuditEvent, utcnow
        self.begin_link()
        with self.db.transaction() as session:
            session.scalar(select(ResumeIntent)).expires_at = utcnow() - timedelta(seconds=1)
        self.assertEqual(self.callback().status_code, 400)
        with self.db.transaction() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(OAuthIdentity).where(OAuthIdentity.provider == "linkedin")), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "identity_linked")), 0)
        self.assertEqual(self.authenticated_sessions(), 1)  # original signed-in session only
        self.assertEqual(self.callback().json["error"]["code"], "invalid_oauth_state")

    def test_rotation_failure_rolls_back_identity_link_and_intent(self):
        from marketplace.accounts.models import OAuthIdentity, ResumeIntent
        service, user, ticket = self.begin_link()
        self.fail_authenticated_session_flush()
        with self.assertRaisesRegex(RuntimeError, "synthetic session-store failure"):
            self.callback()
        with self.db.transaction() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(OAuthIdentity).where(OAuthIdentity.provider == "linkedin")), 0)
            self.assertIsNone(session.scalar(select(ResumeIntent)).consumed_at)
        self.assertEqual(self.authenticated_sessions(), 1)
        self.assertEqual(service.principal(ticket.token).user_id, user.id)
        self.assertEqual(self.callback().json["error"]["code"], "invalid_oauth_state")

    def test_query_ownership_write_rolls_back_with_failed_authentication(self):
        metadata = MetaData()
        query_owners = Table("synthetic_query_owners", metadata, Column("id", Integer, primary_key=True))
        metadata.create_all(self.db.engine)
        self.addCleanup(metadata.drop_all, self.db.engine)
        self.begin(query_id="opaque-query-id")
        def verify(**data):
            # The current independent-hook behavior reproduces the premature commit.
            shared = data.get("session")
            if shared is None:
                with self.db.transaction() as other:
                    other.execute(query_owners.insert().values(id=1))
            else:
                shared.execute(query_owners.insert().values(id=1))
            return True
        self.app.config["MARKETPLACE_QUERY_OWNER_CHECK"] = verify
        self.fail_authenticated_session_flush()
        with self.assertRaisesRegex(RuntimeError, "synthetic session-store failure"):
            self.callback()
        with self.db.transaction() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(query_owners)), 0)
        self.assertEqual(self.authenticated_sessions(), 0)

    def test_expired_flow_cannot_authenticate(self):
        from marketplace.accounts.models import OAuthFlow, utcnow
        self.begin()
        with self.db.transaction() as session:
            session.scalar(select(OAuthFlow)).expires_at = utcnow() - timedelta(seconds=1)
        self.assertEqual(self.callback().status_code, 400)
        self.assertEqual(self.authenticated_sessions(), 0)

    def test_authorization_url_contains_only_oauth_data_and_google_pkce(self):
        data = self.begin(next_path="/experiences/new", query_id="opaque-query-id")
        self.assertEqual(data["code_challenge_method"], ["S256"])
        self.assertIn("code_challenge", data)
        for private in ("opaque-query-id", "/experiences/new", "synthetic-google-secret", "knowledge_owner"):
            self.assertNotIn(private, self.provider_url)
        self.assertIsNone(self.client.get_cookie("session"))

    def test_unknown_provider_and_open_redirect_are_rejected(self):
        self.assertEqual(self.client.get("/auth/login/unknown").status_code, 404)
        self.assertEqual(self.client.get("/auth/callback/unknown?state=opaque").status_code, 404)
        self.assertEqual(self.client.get("/login?next=https://evil.invalid").status_code, 400)

    def test_unconfigured_provider_is_honest_and_has_no_fake_login(self):
        app = self.make_app()
        client = app.test_client()
        page = client.get("/login")
        text = page.get_data(as_text=True)
        for name in ("Google", "LinkedIn", "Facebook"):
            self.assertIn(name, text)
        self.assertIn("Not configured", text)
        self.assertNotIn("/auth/login/google?", text)
        self.assertEqual(client.get("/auth/login/google").status_code, 503)
        self.assertEqual(self.authenticated_sessions(), 0)

    def test_explicit_link_requires_authenticated_csrf_action_and_fresh_proof(self):
        from marketplace.accounts.service import ProviderIdentity
        self.assertEqual(self.client.post("/auth/link/linkedin").status_code, 401)
        service = self.app.extensions["marketplace_accounts"]
        user = service.identity_login(ProviderIdentity("google", "initial-user"))
        ticket = service.issue_session(user.id)
        self.client.set_cookie("marketplace_session", ticket.token)
        self.assertEqual(self.client.post("/auth/link/linkedin").status_code, 403)
        response = self.client.post("/auth/link/linkedin", headers={"X-CSRF-Token": ticket.csrf_token})
        self.assertEqual(response.status_code, 302)
        data = parse_qs(urlsplit(response.location).query)
        self.state, self.nonce, self.callback_path = data["state"][0], data["nonce"][0], "/auth/callback/linkedin"
        self.assertEqual(self.callback().status_code, 302)
        self.assertEqual(service.identity_login(ProviderIdentity("linkedin", self.subject)).id, user.id)
        self.assertIsNone(service.principal(ticket.token).user_id)

    def test_facebook_validates_app_subject_and_expiry_with_optional_email(self):
        self.with_email = False
        self.begin("facebook")
        self.assertEqual(self.callback().status_code, 302)
        self.assertEqual(self.authenticated_sessions(), 1)

    def test_facebook_invalid_debug_proofs_never_sign_in(self):
        for changes in ({"is_valid": False}, {"app_id": "wrong-app"}, {"expires_at": 1},
                        {"data_access_expires_at": 1}, {"type": "APP"}):
            with self.subTest(changes=changes):
                self.client = self.app.test_client()
                self.facebook_debug = changes
                self.begin("facebook")
                self.assertEqual(self.callback().status_code, 400)
                self.assertEqual(self.authenticated_sessions(), 0)

    def test_facebook_profile_subject_must_match_debug_proof(self):
        self.facebook_profile = {"id": "different-subject"}
        self.begin("facebook")
        self.assertEqual(self.callback().status_code, 400)
        self.assertEqual(self.authenticated_sessions(), 0)


if __name__ == "__main__":
    unittest.main()
