from flask import Blueprint, g, jsonify, request

from marketplace.contracts import MarketplaceError
from marketplace.security import accounts, browser_token, current_principal, proven_legacy_owner, require_login

blueprint = Blueprint("marketplace_accounts", __name__)


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
