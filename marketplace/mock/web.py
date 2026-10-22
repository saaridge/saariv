"""Loopback-only demo routes. Loaded only by the explicit mock configuration."""
from urllib.parse import urlencode, urlsplit

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request

from marketplace.accounts.models import User, utcnow
from marketplace.accounts.service import token_digest, validate_next_path
from marketplace.contracts import MarketplaceError, Principal
from marketplace.security import (accounts, browser_token, current_principal, ensure_browser_session,
    require_csrf, require_login, require_role, set_browser_session)
from .service import DemoService, PERSONAS

blueprint = Blueprint("marketplace_mock", __name__)


def demo():
    return current_app.extensions["marketplace_mock"]


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise MarketplaceError("invalid_payload", "Send an object with the required fields.")
    return data


def safe_next(path):
    if path in {"/demo", "/demo/mine", "/demo/admin"}:
        return path
    return validate_next_path(path)


def destination(path, query_id=None):
    return path + ("?" + urlencode({"query_id": query_id}) if query_id else "")


def login_redirect():
    values = {"next": request.path}
    if request.args.get("query_id"):
        values["query_id"] = request.args["query_id"]
    return redirect("/login?" + urlencode(values))


def home():
    token = ensure_browser_session()
    principal = current_principal()
    query_id = request.args.get("query_id")
    query, page = "", None
    if query_id:
        query = demo().restored_query(query_id, principal.user_id, token_digest(token))
        page = demo().search(query, principal.user_id, token_digest(token), query_id+":0")
    return render_template("marketplace/home.html", initial_query=query, search_page=page)


@blueprint.get("/demo")
def demo_home():
    return home()


def switch_persona(persona, intent=None, next_path="/", query_id=None):
    require_csrf()
    if persona not in PERSONAS:
        raise MarketplaceError("invalid_persona", "Choose Reader, Author, or Admin.")
    old_token = browser_token()
    with demo().db.transaction() as session:
        user = session.get(User, PERSONAS[persona]["id"])
        if not user or not user.is_active:
            raise MarketplaceError("demo_not_initialized", "Initialize the local demo database first.", 503)
        principal = Principal(user.id, frozenset(user.roles))
        if intent:
            resume = accounts()._intent(session, intent, old_token)
            next_path, query_id = resume.next_path, resume.query_id
            if query_id and not demo().claim_query(principal=principal, query_id=query_id,
                    session_digest=resume.session_digest, session=session):
                query_id = None
            resume.consumed_at, resume.user_id = utcnow(), user.id
        elif query_id and not demo().claim_query(principal=principal, query_id=query_id,
                session_digest=token_digest(old_token), session=session):
            query_id = None
        next_path = safe_next(next_path)
        if next_path == "/demo/admin" and "admin" not in principal.roles:
            next_path = "/"
        ticket = accounts().issue_session(user.id, previous_token=old_token, session=session)
    set_browser_session(ticket)
    return redirect(destination(next_path, query_id))


@blueprint.post("/auth/mock/<provider>")
def mock_login(provider):
    if provider not in {"google", "linkedin", "facebook"}:
        abort(404)
    return switch_persona(request.form.get("persona", "reader"), request.form.get("intent"))


@blueprint.post("/demo/persona/<persona>")
def persona_switch(persona):
    return switch_persona(persona, request.form.get("intent"), next_path=request.form.get("next", "/"),
        query_id=request.form.get("query_id"))


@blueprint.post("/demo/logout")
@require_login
def logout():
    accounts().revoke_session(browser_token())
    g.marketplace_clear_cookie = True
    return redirect("/")


@blueprint.post("/api/search")
def search():
    require_csrf()
    data = payload()
    return jsonify(demo().search(data.get("query"), current_principal().user_id,
        token_digest(browser_token()), data.get("cursor")))


@blueprint.get("/experiences/new")
def new_experience():
    if not current_principal().authenticated:
        return login_redirect()
    return render_template("marketplace/editor.html", draft=None)


@blueprint.get("/experiences/<uuid:experience_id>/edit")
def edit_experience(experience_id):
    if not current_principal().authenticated:
        return login_redirect()
    return render_template("marketplace/editor.html", draft=demo().draft(current_principal().user_id, experience_id))


@blueprint.get("/demo/mine")
def mine():
    if not current_principal().authenticated:
        return redirect("/login?next=%2F")
    data = demo().dashboard(current_principal().user_id)
    return render_template("marketplace/mock/mine.html", experiences=data["experiences"])


@blueprint.get("/experiences/<uuid:experience_id>")
def experience(experience_id):
    principal = current_principal()
    if not principal.authenticated:
        return login_redirect()
    data = demo().detail(experience_id, principal.user_id, admin="admin" in principal.roles)
    quote = demo().quote(principal.user_id, experience_id) if data["access_state"] == "locked" else {}
    return render_template("marketplace/mock/experience.html", **data,
        quote_token=quote.get("quote_token"), query_id=request.args.get("query_id", ""))


@blueprint.post("/api/experiences/drafts")
@require_login
def create_draft():
    return jsonify(demo().save_draft(current_principal().user_id, payload())), 201


@blueprint.patch("/api/experiences/drafts/<uuid:draft_id>")
@require_login
def update_draft(draft_id):
    return jsonify(demo().save_draft(current_principal().user_id, payload(), draft_id))


@blueprint.post("/api/experiences/drafts/<uuid:draft_id>/submit")
@require_login
def submit_draft(draft_id):
    return jsonify(demo().submit(current_principal().user_id, draft_id, payload().get("version")))


@blueprint.get("/api/experiences/<uuid:experience_id>/content")
@require_login
def content(experience_id):
    principal = current_principal()
    data = demo().detail(experience_id, principal.user_id, admin="admin" in principal.roles)
    if data["content"] is None:
        raise MarketplaceError("experience_locked", "Unlock this experience before reading it.", 403)
    return jsonify(data["content"])


@blueprint.post("/api/experiences/<uuid:experience_id>/quote")
@require_login
def quote(experience_id):
    return jsonify(demo().quote(current_principal().user_id, experience_id))


@blueprint.post("/api/experiences/<uuid:experience_id>/unlock")
@require_login
def unlock(experience_id):
    return jsonify(demo().unlock(current_principal().user_id, experience_id, payload().get("quote_token")))


@blueprint.put("/api/experiences/<uuid:experience_id>/vote")
@require_login
def vote(experience_id):
    return jsonify(demo().vote(current_principal().user_id, experience_id, payload().get("value")))


@blueprint.post("/demo/experiences/<uuid:experience_id>/unlock")
@require_login
def unlock_form(experience_id):
    query_id = request.form.get("query_id", "")
    try:
        result = demo().unlock(current_principal().user_id, experience_id, request.form.get("quote_token"))
    except MarketplaceError as error:
        if error.code != "insufficient_coins":
            raise
        flash("Add demo coins, then return here to confirm the one-time unlock.")
        return redirect("/wallet?"+urlencode({"return_experience_id": str(experience_id), "query_id": query_id}))
    flash("Experience unlocked." if result["charged_coins"] else "Already unlocked. No coins charged.")
    return redirect(destination("/experiences/"+str(experience_id), query_id))


@blueprint.post("/demo/experiences/<uuid:experience_id>/vote")
@require_login
def vote_form(experience_id):
    demo().vote(current_principal().user_id, experience_id, request.form.get("value"))
    flash("Your helpfulness vote has been updated.")
    return redirect(destination("/experiences/"+str(experience_id), request.form.get("query_id")))


@blueprint.get("/wallet")
def wallet():
    if not current_principal().authenticated:
        return login_redirect()
    data = demo().dashboard(current_principal().user_id)
    return render_template("marketplace/mock/wallet.html", transactions=data["transactions"], requests=data["requests"],
        return_experience_id=request.args.get("return_experience_id", ""), query_id=request.args.get("query_id", ""))


@blueprint.get("/api/wallet")
@require_login
def wallet_api():
    return jsonify(demo().wallet(current_principal().user_id))


def create_funding(data, kind):
    return demo().request_funds(current_principal().user_id, data.get("coins"), kind,
        data.get("return_experience_id"), data.get("query_id"))


@blueprint.post("/api/wallet/recharges")
@require_login
def recharge():
    return jsonify(create_funding(payload(), "recharge"))


@blueprint.post("/api/wallet/withdrawals")
@require_login
def withdrawal():
    return jsonify(create_funding(payload(), "withdrawal")), 201


@blueprint.post("/demo/recharges")
@blueprint.post("/demo/withdrawals")
@require_login
def funding_form():
    kind = "recharge" if request.path == "/demo/recharges" else "withdrawal"
    result = create_funding(request.form, kind)
    return redirect("/wallet/requests/"+result["id"])


@blueprint.get("/wallet/requests/<uuid:request_id>")
def funding_request(request_id):
    principal = current_principal()
    if not principal.authenticated:
        return login_redirect()
    funding = demo().request(principal.user_id, request_id, admin="admin" in principal.roles)
    return render_template("marketplace/mock/request.html", funding=funding, owner_name=funding["owner_name"])


@blueprint.get("/api/wallet/requests/<uuid:request_id>")
@require_login
def funding_request_api(request_id):
    principal = current_principal()
    return jsonify(demo().request(principal.user_id, request_id, admin="admin" in principal.roles))


@blueprint.post("/api/wallet/recharges/<uuid:request_id>/submitted")
@require_login
def submitted(request_id):
    return jsonify(demo().money_action(current_principal().user_id, request_id, "submitted"))


@blueprint.post("/api/wallet/withdrawals/<uuid:request_id>/cancel")
@require_login
def cancel(request_id):
    return jsonify(demo().money_action(current_principal().user_id, request_id, "cancel"))


@blueprint.post("/demo/requests/<uuid:request_id>/<action>")
@require_login
def funding_action_form(request_id, action):
    if action not in {"submitted", "cancel"}:
        abort(404)
    demo().money_action(current_principal().user_id, request_id, action)
    return redirect("/wallet/requests/"+str(request_id))


@blueprint.get("/demo/admin")
@require_role("admin")
def admin():
    data = demo().dashboard(current_principal().user_id, admin=True)
    return render_template("marketplace/mock/admin.html", submissions=data["submissions"],
        requests=data["requests"], treasury_coins=data["treasury_coins"])


@blueprint.post("/api/admin/experiences/<uuid:experience_id>/<action>")
@require_role("admin")
def review(experience_id, action):
    if action not in {"approve", "reject"}:
        abort(404)
    return jsonify(demo().review(current_principal().user_id, experience_id, action == "approve"))


@blueprint.post("/demo/admin/experiences/<uuid:experience_id>/<action>")
@require_role("admin")
def review_form(experience_id, action):
    if action not in {"approve", "reject"}:
        abort(404)
    result = demo().review(current_principal().user_id, experience_id, action == "approve")
    flash("Publication approved. Awarded "+str(result["reward_coins"])+" demo coins." if action == "approve" else "Publication declined.")
    return redirect("/demo/admin")


@blueprint.post("/api/admin/<kind>/<uuid:request_id>/<action>")
@require_role("admin")
def admin_funding(kind, request_id, action):
    allowed = {"recharges": {"approve", "reject"}, "withdrawals": {"start", "settle", "reject"}}
    if action not in allowed.get(kind, set()):
        abort(404)
    funding = demo().request(current_principal().user_id, request_id, admin=True)
    if funding["kind"]+"s" != kind:
        abort(404)
    return jsonify(demo().money_action(current_principal().user_id, request_id, action, admin=True))


@blueprint.post("/demo/admin/requests/<uuid:request_id>/<action>")
@require_role("admin")
def admin_funding_form(request_id, action):
    if action not in {"approve", "reject", "start", "settle"}:
        abort(404)
    result = demo().money_action(current_principal().user_id, request_id, action, admin=True)
    flash("Demo request is now "+result["status"].replace("_", " ")+".")
    return redirect("/demo/admin")


@blueprint.errorhandler(MarketplaceError)
def domain_error(error):
    if request.path.startswith("/api/"):
        return jsonify(error.to_dict()), error.status
    return render_template("marketplace/mock/error.html", message=error.message, code=error.code, status=error.status), error.status


def register_mock(app):
    service = DemoService(app.extensions["marketplace_db"], app.secret_key)
    app.extensions["marketplace_mock"] = service
    app.extensions["marketplace_mock_home"] = home
    app.config["MARKETPLACE_QUERY_OWNER_CHECK"] = service.claim_query
    app.register_blueprint(blueprint)

    def loopback_only():
        local = {"127.0.0.1", "localhost", "::1"}
        if request.remote_addr not in local or urlsplit(request.host_url).hostname not in local:
            abort(404)
        if ((request.path.startswith("/api/") and request.blueprint != blueprint.name)
                or (request.path.startswith("/auth/") and not request.path.startswith("/auth/mock/")
                    and request.path != "/auth/logout")
                or request.path in {"/waitlist", "/try"}):
            raise MarketplaceError("mock_services_only", "Use the local demo screens and mock sign-in in this mode.", 503)

    # Run before the legacy knowledge guard, which may create a private owner.
    app.before_request_funcs.setdefault(None, []).insert(0, loopback_only)

    @app.after_request
    def demo_headers(response):
        response.headers["Cache-Control"] = "no-store"
        # Native WebKit form navigation sends Origin:null with no-referrer.
        # Keep same-origin form origins while suppressing referrers to other sites.
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.context_processor
    def demo_context():
        principal = current_principal()
        persona = next((key for key, value in PERSONAS.items() if value["id"] == principal.user_id), None)
        try:
            return_path = safe_next(request.path)
        except MarketplaceError:
            return_path = "/"
        return {"mock_mode": True, "mock_persona": persona, "principal": principal,
            "wallet": service.wallet(principal.user_id) if principal.authenticated else None,
            "mock_return_path": return_path}
