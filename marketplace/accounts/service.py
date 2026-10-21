"""Authentication operations accept only server-validated provider proofs."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import re
import secrets
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from marketplace.contracts import GUEST, MarketplaceError, Principal
from .models import AuditEvent, OAuthIdentity, PrivateAvatarOwner, ResumeIntent, ServerSession, User, utcnow


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_next_path(path):
    # A narrow route allowlist also rejects encoded separators, redirects and payloads.
    if not isinstance(path, str) or len(path) > 255:
        raise MarketplaceError("invalid_return", "Choose an internal return destination.")
    allowed = {"/", "/experiences/new", "/wallet"}
    if path in allowed:
        return path
    match = re.fullmatch(r"/(experiences|wallet/requests)/([0-9a-fA-F-]{36})(/edit)?", path)
    if match and (not match[3] or match[1] == "experiences"):
        try:
            UUID(match[2])
            return path
        except ValueError:
            pass
    raise MarketplaceError("invalid_return", "Choose an internal return destination.")


@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    subject: str
    email: str | None = None
    display_name: str | None = None

    def __post_init__(self):
        if self.provider not in {"google", "linkedin", "facebook"} or not isinstance(self.subject, str) or not self.subject.strip() or len(self.subject) > 255:
            raise MarketplaceError("invalid_identity", "The provider returned an invalid identity.")
        if self.email is not None and (not isinstance(self.email, str) or len(self.email) > 320):
            raise MarketplaceError("invalid_identity", "The provider returned invalid profile data.")


@dataclass(frozen=True)
class SessionTicket:
    token: str = field(repr=False)
    csrf_token: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class ResumeTarget:
    next_path: str
    query_id: str | None = None


class AccountService:
    def __init__(self, db, *, session_ttl=86400, intent_ttl=900):
        self.db, self.session_ttl, self.intent_ttl = db, session_ttl, intent_ttl

    @staticmethod
    def _identity_lock(session, proof):
        # Serializes first sign-ins for the same subject without merging by email.
        lock = int.from_bytes(hashlib.sha256((proof.provider + "\0" + proof.subject).encode()).digest()[:8], "big", signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock(:identity_lock)"), {"identity_lock": lock})

    def identity_login(self, proof: ProviderIdentity):
        with self.db.transaction() as session:
            self._identity_lock(session, proof)
            identity = session.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == proof.provider, OAuthIdentity.subject == proof.subject))
            if identity:
                user = session.get(User, identity.user_id)
                if not user.is_active:
                    raise MarketplaceError("access_denied", "This account is disabled.", 403)
                return user
            user = User(display_name=(proof.display_name or "Reader")[:200], email=proof.email)
            session.add(user)
            session.flush()
            session.add(OAuthIdentity(user_id=user.id, provider=proof.provider, subject=proof.subject, email=proof.email))
            session.add(AuditEvent(actor_id=user.id, action="account_created", details={"provider": proof.provider}))
            return user

    def link_identity(self, *, principal: Principal, proof: ProviderIdentity):
        if not principal.authenticated:
            raise MarketplaceError("login_required", "Sign in before linking an identity.", 401)
        with self.db.transaction() as session:
            self._identity_lock(session, proof)
            user = session.get(User, principal.user_id)
            if not user or not user.is_active:
                raise MarketplaceError("access_denied", "This account is unavailable.", 403)
            identity = session.scalar(select(OAuthIdentity).where(OAuthIdentity.provider == proof.provider, OAuthIdentity.subject == proof.subject))
            if identity:
                if identity.user_id != principal.user_id:
                    raise MarketplaceError("identity_conflict", "This identity already belongs to another account.", 409)
                return user
            session.add(OAuthIdentity(user_id=user.id, provider=proof.provider, subject=proof.subject, email=proof.email))
            session.add(AuditEvent(actor_id=user.id, action="identity_linked", details={"provider": proof.provider}))
            return user

    def issue_session(self, user_id=None, *, previous_token=None):
        ticket = SessionTicket(secrets.token_urlsafe(32), secrets.token_urlsafe(32), utcnow() + timedelta(seconds=self.session_ttl))
        with self.db.transaction() as session:
            if user_id:
                user = session.get(User, user_id)
                if not user or not user.is_active:
                    raise MarketplaceError("access_denied", "This account is unavailable.", 403)
            if previous_token:
                previous = session.get(ServerSession, token_digest(previous_token), with_for_update=True)
                if not previous or previous.revoked_at or previous.expires_at <= utcnow():
                    raise MarketplaceError("invalid_session", "The original browser session expired or was revoked. Start sign-in again.", 403)
                previous.revoked_at = utcnow()
            session.add(ServerSession(digest=token_digest(ticket.token), user_id=user_id,
                                      csrf_token=ticket.csrf_token, expires_at=ticket.expires_at))
            if user_id:
                session.add(AuditEvent(actor_id=user_id, action="session_started"))
        return ticket

    def session_record(self, token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            return None
        with self.db.transaction() as session:
            record = session.get(ServerSession, token_digest(token))
            if not record or record.revoked_at or record.expires_at <= utcnow():
                return None
            if record.user_id:
                user = session.get(User, record.user_id)
                if not user or not user.is_active:
                    return None
            return record

    def principal(self, token):
        record = self.session_record(token)
        if not record or not record.user_id:
            return GUEST
        with self.db.transaction() as session:
            user = session.get(User, record.user_id)
            return Principal(user.id, frozenset(user.roles)) if user and user.is_active else GUEST

    def revoke_session(self, token):
        if not isinstance(token, str):
            return
        with self.db.transaction() as session:
            record = session.get(ServerSession, token_digest(token), with_for_update=True)
            if record and not record.revoked_at:
                record.revoked_at = utcnow()
                session.add(AuditEvent(actor_id=record.user_id, action="session_revoked"))

    def create_resume(self, token, *, next_path, query_id=None):
        next_path = validate_next_path(next_path)
        if query_id is not None and (not isinstance(query_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", query_id)):
            raise MarketplaceError("invalid_query", "Use an opaque query reference.")
        record = self.session_record(token)
        if not record:
            raise MarketplaceError("invalid_session", "Start sign-in again.", 403)
        intent = secrets.token_urlsafe(32)
        with self.db.transaction() as session:
            session.add(ResumeIntent(digest=token_digest(intent), session_digest=record.digest, user_id=record.user_id,
                next_path=next_path, query_id=query_id, expires_at=utcnow() + timedelta(seconds=self.intent_ttl)))
        return intent

    @staticmethod
    def _intent(session, intent, token, principal=None):
        row = session.get(ResumeIntent, token_digest(intent), with_for_update=True)
        if not row or row.session_digest != token_digest(token) or row.consumed_at or row.expires_at <= utcnow():
            raise MarketplaceError("expired_intent", "This return link expired. Start sign-in again.", 400)
        if principal is not None and row.user_id and row.user_id != principal.user_id:
            raise MarketplaceError("access_denied", "This return link belongs to another account.", 403)
        return row

    def check_resume(self, intent, token):
        with self.db.transaction() as session:
            self._intent(session, intent, token)

    def consume_resume(self, intent, token, *, principal, query_owner_check=None):
        if not principal.authenticated:
            raise MarketplaceError("login_required", "Sign in to resume.", 401)
        with self.db.transaction() as session:
            row = self._intent(session, intent, token, principal)
            query_id = row.query_id
            if query_id and (query_owner_check is None or not query_owner_check(
                    principal=principal, query_id=query_id, session_digest=row.session_digest)):
                query_id = None
            row.consumed_at = utcnow()
            row.user_id = principal.user_id
            return ResumeTarget(row.next_path, query_id)

    def claim_owner(self, *, principal, proven_owner_id):
        """Internal boundary: caller must validate the original signed legacy cookie."""
        if not principal.authenticated:
            raise MarketplaceError("login_required", "Sign in to claim browser data.", 401)
        try:
            with self.db.transaction() as session:
                session.add(PrivateAvatarOwner(owner_id=proven_owner_id, user_id=principal.user_id))
                session.add(AuditEvent(actor_id=principal.user_id, action="legacy_owner_claimed", target_id=proven_owner_id))
        except IntegrityError:
            raise MarketplaceError("owner_claimed", "This browser data has already been claimed.", 409) from None
