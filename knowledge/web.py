"""Authorized, model-independent HTTP search and knowledge management."""

import hashlib
import os
from pathlib import Path
import re
import secrets
import threading
import time

from flask import current_app, g, jsonify, request, session
from werkzeug.exceptions import Forbidden, HTTPException, Unauthorized

from .config import Settings
from .embeddings import ProviderError
from .service import KnowledgeService, ReindexRequired


_initialization_lock = threading.Lock()


def get_service():
    configured = current_app.config.get("KNOWLEDGE_SERVICE")
    if configured is not None:
        return configured
    with _initialization_lock:
        if "knowledge_service" not in current_app.extensions:
            current_app.extensions["knowledge_service"] = KnowledgeService(Settings.from_env(current_app.root_path))
        return current_app.extensions["knowledge_service"]


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Please send a JSON object.")
    return data


def _token_owner(token):
    store = get_service().store
    with store.connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS access_tokens (digest TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
        row = conn.execute("SELECT owner FROM access_tokens WHERE digest=? AND expires>?",
                           (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    return row[0] if row else None


def resolve_owner(create=False, browser_only=False, supplied=None):
    header = request.headers.get("Authorization", "")
    if header:
        if browser_only:
            raise Forbidden("This action requires the owning browser session.")
        scheme, _, token = header.partition(" ")
        owner = _token_owner(token) if scheme.lower() == "bearer" and token else None
        if not owner:
            raise Unauthorized("The access token is invalid or expired.")
    else:
        owner = session.get("knowledge_owner")
    if supplied is not None and (not isinstance(supplied, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", supplied)):
        raise ValueError("Invalid session identifier.")
    if not owner:
        if not create:
            raise Unauthorized("Start your avatar in this browser or supply an avatar access token.")
        owner = secrets.token_urlsafe(24)
        session["knowledge_owner"] = owner
        session.permanent = True
        # Client identifiers are only UI state; never adopt them as ownership.
    elif supplied and supplied != owner:
        raise Forbidden("The requested avatar does not belong to this session or token.")
    return owner


def initialize_knowledge(app):
    configured_secret = os.getenv("FLASK_SECRET_KEY", "")
    if not configured_secret or configured_secret in {"change-me-to-a-long-random-string", "saariv-stepper-rag-secret-2025"}:
        secret_path = Path(app.root_path) / "data" / "session.secret"
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            app.secret_key = secret_path.read_text()
        else:
            with os.fdopen(descriptor, "w") as stream:
                app.secret_key = secrets.token_hex(32)
                stream.write(app.secret_key)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      MAX_CONTENT_LENGTH=20 * 1024 * 1024)

    @app.before_request
    def knowledge_request_guard():
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                raise Forbidden("Cross-origin writes are not allowed.")
        if request.path.startswith("/api/onboarding/") or request.path == "/api/playground/rag-query":
            data = request.form if request.mimetype == "multipart/form-data" else json_body()
            g.knowledge_owner = resolve_owner(create=request.path.startswith("/api/onboarding/"),
                                             browser_only=True, supplied=data.get("session_id"))

    @app.errorhandler(ProviderError)
    def provider_error(error):
        return jsonify(ok=False, message=str(error)), 503

    @app.errorhandler(ReindexRequired)
    def reindex_error(error):
        return jsonify(ok=False, message=str(error), needs_reindex=True), 409

    @app.errorhandler(ValueError)
    def validation_error(error):
        return jsonify(ok=False, message=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, message=error.description), error.code
        return error.get_response()

    def api_owner(browser_only=False, data=None):
        data = data or {}
        supplied = data.get("session_id") or data.get("avatar_id")
        return resolve_owner(browser_only=browser_only, supplied=supplied)

    @app.post("/api/knowledge/search")
    def knowledge_search():
        data = json_body()
        owner = api_owner(data=data)
        result = get_service().search(owner, data.get("query"), data.get("limit", 5), data.get("mode", "auto"))
        return jsonify(ok=True, **result)

    @app.get("/api/knowledge/status")
    def knowledge_status():
        return jsonify(ok=True, **get_service().status(api_owner()))

    @app.get("/api/knowledge/documents")
    def knowledge_documents():
        return jsonify(ok=True, documents=get_service().documents(api_owner()))

    @app.delete("/api/knowledge/documents/<document_id>")
    def knowledge_delete(document_id):
        owner = api_owner(browser_only=True)
        deleted = get_service().delete_document(owner, document_id)
        if deleted:
            exporter = current_app.config.get("KNOWLEDGE_EXPORTER")
            if exporter:
                exporter(owner)
        return jsonify(ok=deleted, message="Document deleted." if deleted else "Document not found."), 200 if deleted else 404

    @app.post("/api/knowledge/reindex")
    def knowledge_reindex():
        return jsonify(ok=True, **get_service().reindex(api_owner(browser_only=True)))

    @app.post("/api/knowledge/token")
    def knowledge_token():
        owner = api_owner(browser_only=True)
        token = secrets.token_urlsafe(32)
        expires = time.time() + 30 * 24 * 60 * 60
        with get_service().store.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS access_tokens (digest TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
            conn.execute("DELETE FROM access_tokens WHERE expires<?", (time.time(),))
            conn.execute("INSERT INTO access_tokens VALUES (?,?,?)",
                         (hashlib.sha256(token.encode()).hexdigest(), owner, expires))
        response = jsonify(ok=True, token=token, expires_at=expires, scope="knowledge:read")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.delete("/api/knowledge/token")
    def knowledge_revoke_tokens():
        owner = api_owner(browser_only=True)
        with get_service().store.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS access_tokens (digest TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
            conn.execute("DELETE FROM access_tokens WHERE owner=?", (owner,))
        return jsonify(ok=True)
