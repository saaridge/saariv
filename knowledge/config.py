"""Runtime configuration; secrets never participate in index identities."""

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    embedding_provider: str = "none"
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_api_key: str = field(default="", repr=False)
    embedding_dimensions: int | None = None
    embedding_revision: str = ""
    query_prefix: str = ""
    document_prefix: str = ""
    chunk_size: int = 1600
    chunk_overlap: int = 200
    min_score: float = 0.30
    timeout: float = 20
    retries: int = 2
    batch_size: int = 64

    def __post_init__(self):
        if self.embedding_provider not in {"none", "openai_compatible", "cohere", "ollama"}:
            raise ValueError("Unsupported EMBEDDING_PROVIDER; use none, openai_compatible, cohere, or ollama.")
        if self.enabled:
            parsed = urlsplit(self.embedding_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("EMBEDDING_BASE_URL must be an HTTP(S) URL without embedded credentials.")
            if not self.embedding_model:
                raise ValueError("Set EMBEDDING_MODEL for the configured provider.")
        if self.embedding_dimensions is not None and self.embedding_dimensions < 1:
            raise ValueError("EMBEDDING_DIMENSIONS must be positive.")
        if self.chunk_size < 80 or not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("Chunk size must be >=80 characters and overlap must be smaller than the size.")
        if not math.isfinite(self.min_score) or not -1 <= self.min_score <= 1:
            raise ValueError("EMBEDDING_MIN_SCORE must be between -1 and 1.")
        if not 1 <= self.batch_size <= 96 or not 0 <= self.retries <= 4 or self.timeout <= 0:
            raise ValueError("Invalid embedding batch size, retry count, or timeout.")

    @property
    def enabled(self):
        return self.embedding_provider != "none"

    @property
    def profile(self):
        return {
            "provider": self.embedding_provider,
            "endpoint": self.embedding_base_url.rstrip("/"),
            "model": self.embedding_model,
            "revision": self.embedding_revision,
            "dimensions": self.embedding_dimensions,
            "query_prefix": self.query_prefix,
            "document_prefix": self.document_prefix,
        }

    @property
    def profile_id(self):
        encoded = json.dumps(self.profile, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()[:24]

    @classmethod
    def from_env(cls, base_dir):
        # Preserve existing installations while allowing an entirely different API.
        legacy_key = os.getenv("OPENAI_API_KEY", "").strip()
        provider = os.getenv("EMBEDDING_PROVIDER", "openai_compatible" if legacy_key else "none").strip().lower()
        defaults = {
            "cohere": "https://api.cohere.com",
            "ollama": "http://127.0.0.1:11434",
            "openai_compatible": "https://api.openai.com/v1" if legacy_key else "",
        }
        api_key = os.getenv("EMBEDDING_API_KEY", os.getenv("COHERE_API_KEY", "") if provider == "cohere" else legacy_key)
        default_model = "text-embedding-3-small" if provider == "openai_compatible" and legacy_key else ""
        location = Path(os.getenv("KNOWLEDGE_DIR", "data/knowledge")).expanduser()
        if not location.is_absolute():
            location = Path(base_dir) / location
        dimensions = os.getenv("EMBEDDING_DIMENSIONS", "").strip()
        return cls(
            data_dir=location, embedding_provider=provider,
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", defaults.get(provider, "")).rstrip("/"),
            embedding_model=os.getenv("EMBEDDING_MODEL", default_model),
            embedding_api_key=api_key.strip(),
            embedding_dimensions=int(dimensions) if dimensions else None,
            embedding_revision=os.getenv("EMBEDDING_REVISION", ""),
            query_prefix=os.getenv("EMBEDDING_QUERY_PREFIX", ""),
            document_prefix=os.getenv("EMBEDDING_DOCUMENT_PREFIX", ""),
            chunk_size=int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "1600")),
            chunk_overlap=int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "200")),
            min_score=float(os.getenv("EMBEDDING_MIN_SCORE", "0.30")),
            timeout=float(os.getenv("EMBEDDING_TIMEOUT", "20")),
            retries=int(os.getenv("EMBEDDING_RETRIES", "2")),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "64")),
        )
