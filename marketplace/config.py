"""Marketplace-only settings. Never load .env files or expose credentials."""
from dataclasses import dataclass, field
import os
import re
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url


@dataclass(frozen=True)
class Settings:
    enabled: bool = False
    environment: str = "development"
    database_url: str = field(default="", repr=False)
    secret_key: str = field(default="", repr=False)
    public_base_url: str = "http://localhost:8080"
    session_ttl: int = 86400
    intent_ttl: int = 900
    oauth_ttl: int = 600
    provider_credentials: dict = field(default_factory=dict, repr=False)
    facebook_graph_version: str = ""
    mock_mode: bool = False

    @classmethod
    def from_mapping(cls, mapping, *, environ=None):
        env = os.environ if environ is None else environ

        def get(name, default=""):
            value = mapping.get(name)
            return env.get(name, default) if value is None else value

        enabled = str(get("MARKETPLACE_ENABLED", "false")).lower() in {"true", "1", "yes"}
        mock_mode = str(get("MARKETPLACE_MOCK_MODE", "false")).lower() in {"true", "1", "yes"}
        environment = str(get("MARKETPLACE_ENV", "development")).lower()
        database_url = str(get("DATABASE_URL"))
        secret = str(get("SECRET_KEY") or get("FLASK_SECRET_KEY"))
        public_base = str(get("MARKETPLACE_PUBLIC_BASE_URL", "http://localhost:8080")).rstrip("/")
        credentials = {name: (str(get(name.upper() + "_CLIENT_ID")),
                               str(get(name.upper() + "_CLIENT_SECRET")))
                       for name in ("google", "linkedin", "facebook")}
        if mock_mode:
            if not enabled or environment not in {"development", "test"}:
                raise ValueError("Mock mode requires an enabled development or test marketplace")
            try:
                demo_db = make_url(database_url)
                local = {"127.0.0.1", "localhost", "::1"}
                if (demo_db.host not in local or not demo_db.database
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_(mock|test)", demo_db.database)
                        or set(demo_db.query) - {"options", "connect_timeout", "application_name"}
                        or any(env.get(name) for name in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"))
                        or urlsplit(public_base).hostname not in local):
                    raise ValueError()
            except Exception:
                raise ValueError("Mock mode requires a loopback origin and a dedicated local _mock or _test database") from None
        if enabled:
            if not database_url:
                raise ValueError("DATABASE_URL is required when MARKETPLACE_ENABLED")
            try:
                if make_url(database_url).drivername != "postgresql+psycopg":
                    raise ValueError()
            except Exception:
                raise ValueError("DATABASE_URL must use postgresql+psycopg") from None
            origin = urlsplit(public_base)
            if origin.scheme not in {"http", "https"} or not origin.netloc or origin.username or origin.path or origin.query or origin.fragment:
                raise ValueError("MARKETPLACE_PUBLIC_BASE_URL must be an absolute origin")
            if environment == "production":
                weak = {"change-me-to-a-long-random-string", "saariv-stepper-rag-secret-2025"}
                if len(secret) < 32 or len(set(secret)) < 10 or secret in weak or secret.lower().startswith(("change-me", "replace-me")):
                    raise ValueError("A strong non-default production signing secret is required")
                if origin.scheme != "https":
                    raise ValueError("Production callbacks require HTTPS")
        graph_version = str(get("FACEBOOK_GRAPH_VERSION"))
        if graph_version and not re.fullmatch(r"v[1-9][0-9]*\.0", graph_version):
            raise ValueError("FACEBOOK_GRAPH_VERSION must be an explicitly verified version")
        ttl = [int(get(name, default)) for name, default in
               (("MARKETPLACE_SESSION_TTL", 86400), ("MARKETPLACE_INTENT_TTL", 900), ("MARKETPLACE_OAUTH_TTL", 600))]
        if any(value <= 0 or value > 2592000 for value in ttl):
            raise ValueError("Marketplace expiry settings must be positive and at most 30 days")
        return cls(enabled, environment, database_url, secret, public_base, *ttl, credentials, graph_version, mock_mode)

    def provider_configured(self, provider):
        return bool(all(self.provider_credentials.get(provider, ()))) and (provider != "facebook" or bool(self.facebook_graph_version))
