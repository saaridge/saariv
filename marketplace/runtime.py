"""Mount completed screens while keeping unfinished domain operations fail-closed."""
from urllib.parse import urlencode

from flask import Blueprint, redirect, render_template, request

from .contracts import MarketplaceError
from .security import current_principal, require_login

blueprint = Blueprint("marketplace_pages", __name__)


def unavailable():
    raise MarketplaceError("feature_unavailable", "This feature is not available yet.", 503)


@blueprint.get("/experiences/new")
def new_experience():
    principal = current_principal()
    if not principal.authenticated:
        return redirect("/login?" + urlencode({"next": "/experiences/new"}))
    return render_template("marketplace/editor.html", principal=principal, wallet=None, draft=None)


@blueprint.post("/api/search")
def search_pending():
    # Never substitute fixture cards or private avatar sources for public search.
    return unavailable()


@blueprint.post("/api/experiences/drafts")
@blueprint.patch("/api/experiences/drafts/<uuid:draft_id>")
@blueprint.post("/api/experiences/drafts/<uuid:draft_id>/submit")
@require_login
def draft_pending(draft_id=None):
    return unavailable()


@blueprint.get("/wallet")
@blueprint.get("/experiences/<uuid:experience_id>")
def domain_pending(experience_id=None):
    if not current_principal().authenticated:
        return redirect("/login?" + urlencode({"next": request.path}))
    return unavailable()


def install_page_headers(app):
    @app.after_request
    def private_pages(response):
        if request.path == "/" or request.blueprint == blueprint.name:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response
