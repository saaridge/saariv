"""Authlib provider adapters with SQL-owned, one-time state and nonce.

Never use Authlib's signed-cookie state storage here. Only its authorization,
token exchange and OIDC signature/claim validation machinery is used.
"""
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import re
import secrets
import time

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from joserfc.errors import JoseError
from requests import RequestException

from marketplace.contracts import MarketplaceError, Principal
from .models import OAuthFlow, ServerSession, User, utcnow
from .service import ProviderIdentity, ResumeTarget, SessionTicket, token_digest

PROVIDERS = {"google": "Google", "linkedin": "LinkedIn", "facebook": "Facebook"}
OIDC = {
    "google": ("https://accounts.google.com/.well-known/openid-configuration", "https://accounts.google.com"),
    "linkedin": ("https://www.linkedin.com/oauth/.well-known/openid-configuration", "https://www.linkedin.com/oauth"),
}


@dataclass(frozen=True)
class OAuthResult:
    ticket: SessionTicket
    target: ResumeTarget


class OAuthManager:
    def __init__(self, app, settings, accounts):
        self.settings, self.accounts, self.db = settings, accounts, accounts.db
        self.oauth = OAuth(app)
        for provider in PROVIDERS:
            if not settings.provider_configured(provider):
                continue
            client_id, client_secret = settings.provider_credentials[provider]
            options = {"scope": "openid profile email", "token_endpoint_auth_method": "client_secret_post", "timeout": 10}
            if provider == "google":
                options["code_challenge_method"] = "S256"
            if provider in OIDC:
                self.oauth.register(provider, client_id=client_id, client_secret=client_secret,
                    server_metadata_url=OIDC[provider][0], client_kwargs=options)
            else:
                version = settings.facebook_graph_version
                self.oauth.register(provider, client_id=client_id, client_secret=client_secret,
                    authorize_url=f"https://www.facebook.com/{version}/dialog/oauth",
                    access_token_url=f"https://graph.facebook.com/{version}/oauth/access_token",
                    api_base_url=f"https://graph.facebook.com/{version}/",
                    client_kwargs={"scope": "public_profile email", "token_endpoint_auth_method": "client_secret_post", "timeout": 10})

    def client(self, provider):
        if provider not in PROVIDERS:
            raise MarketplaceError("unknown_provider", "Unknown sign-in provider.", 404)
        if not self.settings.provider_configured(provider):
            raise MarketplaceError("provider_unavailable", "This sign-in provider is not configured.", 503)
        return self.oauth.create_client(provider)

    def begin(self, provider, token, intent, *, link_user_id=None):
        client = self.client(provider)
        self.accounts.check_resume(intent, token)
        record = self.accounts.session_record(token)
        if not record:
            raise MarketplaceError("invalid_session", "Start sign-in again.", 400)
        if link_user_id and record.user_id != link_user_id:
            raise MarketplaceError("login_required", "Sign in before linking identities.", 401)
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32) if provider in OIDC else None
        verifier = secrets.token_urlsafe(48) if provider == "google" else None
        redirect_uri = self.settings.public_base_url + "/auth/callback/" + provider
        params = {"state": state}
        if nonce:
            params["nonce"] = nonce
        if verifier:
            params["code_verifier"] = verifier
        try:
            authorization = client.create_authorization_url(redirect_uri, **params)
        except (OAuthError, RequestException, ValueError):
            raise MarketplaceError("provider_unavailable", "The sign-in provider is unavailable. Try again later.", 503) from None
        with self.db.transaction() as session:
            session.add(OAuthFlow(digest=token_digest(state), session_digest=record.digest, provider=provider,
                intent_digest=token_digest(intent), nonce=nonce, code_verifier=verifier,
                redirect_uri=redirect_uri, link_user_id=link_user_id,
                expires_at=utcnow() + timedelta(seconds=self.settings.oauth_ttl)))
        return authorization["url"]

    def _consume_flow(self, provider, token, state):
        if not isinstance(state, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", state) or not self.accounts.session_record(token):
            raise MarketplaceError("invalid_oauth_state", "Sign-in expired or belongs to another browser. Start again.", 400)
        with self.db.transaction() as session:
            flow = session.get(OAuthFlow, token_digest(state), with_for_update=True)
            if not flow or flow.provider != provider or flow.session_digest != token_digest(token) or flow.consumed_at or flow.expires_at <= utcnow():
                raise MarketplaceError("invalid_oauth_state", "Sign-in expired or belongs to another browser. Start again.", 400)
            flow.consumed_at = utcnow()
            return flow

    def _oidc_identity(self, provider, client, token, nonce):
        if not token.get("id_token") or not nonce:
            raise MarketplaceError("invalid_provider_proof", "The provider did not return a valid identity token.", 400)
        client.load_server_metadata()
        # Both registered providers publish RS256; do not accept none or HS algorithms.
        client.server_metadata["id_token_signing_alg_values_supported"] = ["RS256"]
        issuers = [OIDC[provider][1]]
        if provider == "google":
            issuers.append("accounts.google.com")
        claims = client.parse_id_token(token, nonce=nonce, leeway=0,
            claims_options={"iss": {"essential": True, "values": issuers},
                            "aud": {"essential": True, "value": client.client_id}})
        return ProviderIdentity(provider, claims["sub"], claims.get("email"), claims.get("name"))

    def _facebook_identity(self, client, token):
        access = token.get("access_token")
        if not isinstance(access, str) or not access:
            raise MarketplaceError("invalid_provider_proof", "Facebook did not return a valid access token.", 400)
        client_id, secret = self.settings.provider_credentials["facebook"]
        response = client.get("debug_token", params={"input_token": access},
                              token={"access_token": client_id + "|" + secret, "token_type": "Bearer"})
        response.raise_for_status()
        data = response.json().get("data", {})
        expires = data.get("expires_at")
        data_expires = data.get("data_access_expires_at")
        if (data.get("is_valid") is not True or str(data.get("app_id")) != client_id
                or data.get("type") != "USER" or not isinstance(data.get("user_id"), str)
                or not isinstance(expires, (float, int)) or expires <= time.time()
                or (data_expires is not None and (not isinstance(data_expires, (int, float)) or data_expires <= time.time()))):
            raise MarketplaceError("invalid_provider_proof", "Facebook returned an invalid or expired identity proof.", 400)
        proof = hmac.new(secret.encode(), access.encode(), hashlib.sha256).hexdigest()
        profile_response = client.get("me", params={"fields": "id,name,email", "appsecret_proof": proof}, token=token)
        profile_response.raise_for_status()
        profile = profile_response.json()
        if profile.get("id") != data["user_id"]:
            raise MarketplaceError("invalid_provider_proof", "Facebook identity proofs do not match.", 400)
        return ProviderIdentity("facebook", profile["id"], profile.get("email"), profile.get("name"))

    def finish(self, provider, token, *, state, code=None, error=None, query_owner_check=None):
        client = self.client(provider)
        flow = self._consume_flow(provider, token, state)
        if error:
            raise MarketplaceError("provider_denied", "Sign-in was not completed. You can try again.", 400)
        if not isinstance(code, str) or not code or len(code) > 4096:
            raise MarketplaceError("invalid_provider_proof", "The provider did not return a valid authorization code.", 400)
        params = {"code": code}
        if flow.code_verifier:
            params["code_verifier"] = flow.code_verifier
        try:
            provider_token = client.fetch_access_token(redirect_uri=flow.redirect_uri, **params)
            proof = (self._oidc_identity(provider, client, provider_token, flow.nonce) if provider in OIDC
                     else self._facebook_identity(client, provider_token))
        except (OAuthError, JoseError, RequestException, ValueError, KeyError, TypeError):
            # Provider errors may contain tokens, authorization codes or client secrets.
            raise MarketplaceError("invalid_provider_proof", "The provider identity could not be verified. Start sign-in again.", 400) from None
        # No external provider call occurs under this lock. All remaining effects,
        # including a newly linked login identity, commit or roll back together.
        with self.db.transaction() as session:
            original = session.get(ServerSession, flow.session_digest, with_for_update=True)
            if not original or original.revoked_at or original.expires_at <= utcnow():
                raise MarketplaceError("invalid_session", "The original browser session expired or was revoked. Start sign-in again.", 403)
            original_user = session.get(User, original.user_id, with_for_update=True) if original.user_id else None
            if original.user_id and (not original_user or not original_user.is_active):
                raise MarketplaceError("access_denied", "The original account is unavailable.", 403)
            if flow.link_user_id:
                if not original_user or original_user.id != flow.link_user_id:
                    raise MarketplaceError("access_denied", "The original account session is required to link an identity.", 403)
                principal = Principal(original_user.id, frozenset(original_user.roles))
                user = self.accounts.link_identity(principal=principal, proof=proof, session=session)
            else:
                user = self.accounts.identity_login(proof, session=session)
            principal = Principal(user.id, frozenset(user.roles))
            # Intent digest is already server-owned, never a private ID in the URL.
            target = self._consume_bound_intent(flow, token, principal, query_owner_check, session=session)
            ticket = self.accounts.issue_session(user.id, previous_token=token, session=session)
            return OAuthResult(ticket, target)

    def _consume_bound_intent(self, flow, token, principal, query_owner_check, *, session):
        from .models import ResumeIntent
        row = session.get(ResumeIntent, flow.intent_digest, with_for_update=True)
        if (not row or row.session_digest != token_digest(token) or row.consumed_at or row.expires_at <= utcnow()
                or (row.user_id and row.user_id != principal.user_id)):
            raise MarketplaceError("expired_intent", "This return link expired. Start sign-in again.", 400)
        query_id = row.query_id
        if query_id and (query_owner_check is None or not query_owner_check(
                principal=principal, query_id=query_id, session_digest=row.session_digest, session=session)):
            query_id = None
        row.consumed_at, row.user_id = utcnow(), principal.user_id
        return ResumeTarget(row.next_path, query_id)
