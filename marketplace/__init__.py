"""Opt-in marketplace registration. Registration never creates/migrates tables."""
from flask import jsonify

from .config import Settings
from .contracts import MarketplaceError
from .db import Database


def register_marketplace(app):
    settings = Settings.from_mapping(app.config)
    if not settings.enabled:
        return False
    if "marketplace_db" in app.extensions:
        return True
    app.extensions["marketplace_settings"] = settings
    app.extensions["marketplace_db"] = Database(settings.database_url)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    if settings.environment == "production":
        app.config["SESSION_COOKIE_SECURE"] = True

    from .accounts.service import AccountService
    from .accounts.routes import blueprint
    from .security import install_security
    app.extensions["marketplace_accounts"] = AccountService(
        app.extensions["marketplace_db"], session_ttl=settings.session_ttl, intent_ttl=settings.intent_ttl)
    install_security(app)
    app.register_blueprint(blueprint)

    @app.errorhandler(MarketplaceError)
    def marketplace_error(error):
        return jsonify(error.to_dict()), error.status

    return True
