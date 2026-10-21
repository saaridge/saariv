from urllib.parse import urlencode
from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request

from marketplace.contracts import MarketplaceError
from marketplace.security import accounts, browser_token, current_principal, ensure_browser_session, proven_legacy_owner, require_login, set_browser_session

blueprint = Blueprint("marketplace_accounts", __name__)


@blueprint.get("/login")
def login():
    from .oauth import PROVIDERS
    token = ensure_browser_session()
    intent = accounts().create_resume(token, next_path=request.args.get("next", "/"), query_id=request.args.get("query_id"))
    settings = current_app.extensions["marketplace_settings"]
    return render_template("marketplace/login.html", intent=intent,
        providers=[{"id": key, "name": name, "configured": settings.provider_configured(key)} for key, name in PROVIDERS.items()])


@blueprint.get("/auth/login/<provider>")
def provider_login(provider):
    manager = current_app.extensions["marketplace_oauth"]
    manager.client(provider)
    token = ensure_browser_session()
    intent = request.args.get("intent") or accounts().create_resume(token, next_path="/")
    return redirect(manager.begin(provider, token, intent))


@blueprint.post("/auth/link/<provider>")
@require_login
def provider_link(provider):
    token = browser_token()
    intent = accounts().create_resume(token, next_path="/")
    return redirect(current_app.extensions["marketplace_oauth"].begin(provider, token, intent,
                    link_user_id=current_principal().user_id))


@blueprint.get("/auth/callback/<provider>")
def provider_callback(provider):
    result = current_app.extensions["marketplace_oauth"].finish(provider, browser_token(),
        state=request.args.get("state"), code=request.args.get("code"), error=request.args.get("error"),
        query_owner_check=current_app.config.get("MARKETPLACE_QUERY_OWNER_CHECK"))
    set_browser_session(result.ticket)
    target = result.target.next_path
    if result.target.query_id:
        target += "?" + urlencode({"query_id": result.target.query_id})
    return redirect(target)


@blueprint.post("/auth/logout")
@require_login
def logout():
    accounts().revoke_session(browser_token())
    g.marketplace_clear_cookie = True
    return jsonify(ok=True)


@blueprint.post("/auth/claim-owner")
@require_login
def claim_owner():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or data:
        raise MarketplaceError("access_denied", "Owner identifiers cannot be supplied by the client.", 403)
    accounts().claim_owner(principal=current_principal(), proven_owner_id=proven_legacy_owner())
    return jsonify(ok=True)
