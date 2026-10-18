"""Small HTTP adapters. Storage and retrieval only depend on this protocol."""

import json
import math
import time
from typing import Protocol, Sequence
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    """A safe, credential-free message for an external API failure."""


class EmbeddingProvider(Protocol):
    dimension: int | None
    stats: dict

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def post_json(url, payload, api_key="", timeout=20, retries=2):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                value = json.load(response)
            if not isinstance(value, dict):
                raise ProviderError("The API returned an invalid JSON object.")
            return value
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(0.25 * (2 ** attempt))
                continue
            raise ProviderError(f"Model API returned HTTP {status}. Check credentials, model, and endpoint.") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < retries:
                time.sleep(0.25 * (2 ** attempt))
                continue
            raise ProviderError("Model API could not be reached before the timeout.") from None
        except (ValueError, TypeError):
            raise ProviderError("Model API returned invalid JSON.") from None


def validate_vectors(vectors, count, dimension=None):
    if not isinstance(vectors, list) or len(vectors) != count:
        raise ProviderError("Embedding API returned the wrong number of vectors.")
    expected = dimension
    for vector in vectors:
        if not isinstance(vector, list) or not vector:
            raise ProviderError("Embedding API returned an empty or invalid vector.")
        expected = expected or len(vector)
        if len(vector) != expected:
            raise ProviderError("Embedding dimensions changed. Rebuild the index with a consistent model.")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
            raise ProviderError("Embedding API returned non-finite or non-numeric vector values.")
        if not any(v != 0 for v in vector):
            raise ProviderError("Embedding API returned a zero vector.")
    return expected


class HTTPEmbeddingProvider:
    def __init__(self, settings):
        self.settings = settings
        self.dimension = settings.embedding_dimensions
        self.stats = {"calls": 0, "input_tokens": 0, "tokens_reported": False}

    def embed_documents(self, texts):
        return self._embed(texts, "document")

    def embed_query(self, text):
        return self._embed([text], "query")[0]

    def _embed(self, texts, role):
        if not texts:
            return []
        prefix = self.settings.query_prefix if role == "query" else self.settings.document_prefix
        inputs = [prefix + text for text in texts]
        url, payload = self.request(inputs, role)
        self.stats["calls"] += 1
        result = post_json(url, payload, self.settings.embedding_api_key,
                           self.settings.timeout, self.settings.retries)
        try:
            vectors = self.parse(result, len(texts))
        except (KeyError, TypeError, ValueError, IndexError):
            raise ProviderError("Embedding API returned an unexpected response format.") from None
        self.dimension = validate_vectors(vectors, len(texts), self.dimension)
        tokens = result.get("usage", {}).get("prompt_tokens")
        if tokens is None:
            tokens = result.get("meta", {}).get("billed_units", {}).get("input_tokens")
        if tokens is None:
            tokens = result.get("prompt_eval_count")
        if isinstance(tokens, (int, float)):
            self.stats["input_tokens"] += tokens
            self.stats["tokens_reported"] = True
        return vectors


class CompatibleEmbeddings(HTTPEmbeddingProvider):
    def request(self, texts, role):
        payload = {"model": self.settings.embedding_model, "input": texts, "encoding_format": "float"}
        if self.settings.embedding_dimensions:
            payload["dimensions"] = self.settings.embedding_dimensions
        return self.settings.embedding_base_url.rstrip("/") + "/embeddings", payload

    def parse(self, result, count):
        items = sorted(result["data"], key=lambda item: item["index"])
        if [item["index"] for item in items] != list(range(count)):
            raise ProviderError("Embedding API returned incomplete or repeated vector indices.")
        return [item["embedding"] for item in items]


class CohereEmbeddings(HTTPEmbeddingProvider):
    def request(self, texts, role):
        payload = {"model": self.settings.embedding_model, "texts": texts,
                   "input_type": "search_query" if role == "query" else "search_document",
                   "embedding_types": ["float"], "truncate": "NONE"}
        if self.settings.embedding_dimensions:
            payload["output_dimension"] = self.settings.embedding_dimensions
        return self.settings.embedding_base_url.rstrip("/") + "/v2/embed", payload

    def parse(self, result, count):
        return result["embeddings"]["float"]


class OllamaEmbeddings(HTTPEmbeddingProvider):
    def request(self, texts, role):
        payload = {"model": self.settings.embedding_model, "input": texts, "truncate": False}
        if self.settings.embedding_dimensions:
            payload["dimensions"] = self.settings.embedding_dimensions
        return self.settings.embedding_base_url.rstrip("/") + "/api/embed", payload

    def parse(self, result, count):
        return result["embeddings"]


def create_provider(settings):
    adapters = {"openai_compatible": CompatibleEmbeddings, "cohere": CohereEmbeddings,
                "ollama": OllamaEmbeddings}
    return adapters[settings.embedding_provider](settings) if settings.enabled else None
