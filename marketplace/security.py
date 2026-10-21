"""Server-built principal, synchronizer CSRF and independent opaque cookies."""
from functools import wraps
import re
import secrets

from flask import current_app, g, request
from itsdangerous import BadSignature

from .contracts import MarketplaceError

COOKIE_NAME = "marketplace_session"


def accounts():
    return current_app.extensions["marketplace_accounts"]


def browser_token():
    return g.get("marketplace_token", request.cookies.get(COOKIE_NAME))


def ensure_browser_session():
    token = browser_token()
    if accounts().session_record(token):
        return token
    ticket = accounts().issue_session()
    set_browser_session(ticket)
    return ticket.token


def set_browser_session(ticket):
    g.marketplace_token = ticket.token
    g.marketplace_ticket = ticket


def current_principal():
    return accounts().principal(browser_token())


def csrf_token():
    token = ensure_browser_session()
    return accounts().session_record(token).csrf_token


def require_csrf():
    record = accounts().session_record(browser_token())
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not record or not isinstance(supplied, str) or not secrets.compare_digest(record.csrf_token, supplied):
        raise MarketplaceError("csrf_failed", "Refresh the page and try again.", 403)
    origin = request.headers.get("Origin")
    expected = current_app.extensions["marketplace_settings"].public_base_url
    if origin and origin.rstrip("/") != expected:
        raise MarketplaceError("access_denied", "Cross-origin writes are not allowed.", 403)


def require_login(view):
    @wraps(view)
    def guarded(*args, **kwargs):
        if not current_principal().authenticated:
            raise MarketplaceError("login_required", "Sign in to continue.", 401)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_csrf()
        return view(*args, **kwargs)
    return guarded


def require_role(role):
    def decorate(view):
        @wraps(view)
        @require_login
        def guarded(*args, **kwargs):
            if role not in current_principal().roles:
                raise MarketplaceError("access_denied", "This action requires an authorized role.", 403)
            return view(*args, **kwargs)
        return guarded
    return decorate


def proven_legacy_owner():
    # Validate the original cookie rather than accepting any owner from JSON/headers.
    raw_cookie = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
    serializer = current_app.session_interface.get_signing_serializer(current_app)
    if not raw_cookie or serializer is None:
        raise MarketplaceError("access_denied", "The original owning browser is required.", 403)
    try:
        data = serializer.loads(raw_cookie, max_age=int(current_app.permanent_session_lifetime.total_seconds()))
    except BadSignature:
        raise MarketplaceError("access_denied", "The original owning browser is required.", 403) from None
    owner = data.get("knowledge_owner") if isinstance(data, dict) else None
    if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", owner):
        raise MarketplaceError("access_denied", "The original owning browser is required.", 403)
    return owner


def install_security(app):
    app.jinja_env.globals.update(csrf_token=csrf_token, current_principal=current_principal)

    @app.after_request
    def marketplace_cookie(response):
        settings = app.extensions["marketplace_settings"]
        if g.get("marketplace_clear_cookie"):
            response.delete_cookie(COOKIE_NAME, path="/", secure=settings.environment == "production", httponly=True, samesite="Lax")
        elif g.get("marketplace_ticket"):
            ticket = g.marketplace_ticket
            response.set_cookie(COOKIE_NAME, ticket.token, max_age=settings.session_ttl, expires=ticket.expires_at,
                                path="/", secure=settings.environment == "production", httponly=True, samesite="Lax")
        if request.path == "/login" or request.path.startswith("/auth/") or g.get("marketplace_ticket"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response
