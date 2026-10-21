import io
import json
import math
from pathlib import Path
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from knowledge.config import Settings
from knowledge.embeddings import ProviderError, create_provider


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(json.dumps(data).encode())


class ProviderTests(unittest.TestCase):
    def settings(self, provider="openai_compatible", **kwargs):
        values = dict(data_dir=Path("unused"), embedding_provider=provider,
                      embedding_base_url="https://embeddings.example/v1",
                      embedding_model="portable-model", embedding_api_key="private-test-key",
                      embedding_dimensions=3, retries=0)
        values.update(kwargs)
        return Settings(**values)

    def test_compatible_adapter_orders_response_vectors_and_records_usage(self):
        provider = create_provider(self.settings())
        requests = []

        def request(req, timeout, context):
            self.assertEqual(timeout, 20)
            self.assertIsInstance(context, ssl.SSLContext)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            requests.append(req)
            return Response({"data": [{"index": 1, "embedding": [0, 1, 0]},
                                      {"index": 0, "embedding": [1, 0, 0]}],
                             "usage": {"prompt_tokens": 9}})

        with patch("urllib.request.urlopen", side_effect=request):
            vectors = provider.embed_documents(["first", "second"])
        self.assertEqual(vectors, [[1, 0, 0], [0, 1, 0]])
        self.assertEqual(requests[0].full_url, "https://embeddings.example/v1/embeddings")
        self.assertEqual(json.loads(requests[0].data)["dimensions"], 3)
        self.assertEqual(provider.stats["input_tokens"], 9)

    def test_cohere_uses_distinct_query_and_document_roles(self):
        provider = create_provider(self.settings("cohere", embedding_base_url="https://api.cohere.com"))
        requests = []

        def request(req, timeout, context):
            self.assertEqual(timeout, 20)
            self.assertIsInstance(context, ssl.SSLContext)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            requests.append(json.loads(req.data))
            self.assertEqual(req.full_url, "https://api.cohere.com/v2/embed")
            return Response({"embeddings": {"float": [[1, 0, 0]]}})

        with patch("urllib.request.urlopen", side_effect=request):
            provider.embed_documents(["a document"])
            provider.embed_query("a question")
        self.assertEqual([r["input_type"] for r in requests], ["search_document", "search_query"])
        self.assertEqual(requests[0]["embedding_types"], ["float"])

    def test_ollama_native_adapter_and_prefixes(self):
        provider = create_provider(self.settings("ollama", embedding_base_url="http://localhost:11434",
                                                query_prefix="query: ", document_prefix="passage: "))
        requests = []

        def request(req, timeout, context):
            self.assertEqual(timeout, 20)
            self.assertIsNone(context)
            self.assertEqual(req.full_url, "http://localhost:11434/api/embed")
            requests.append(json.loads(req.data))
            return Response({"embeddings": [[1, 0, 0]], "prompt_eval_count": 3})

        with patch("urllib.request.urlopen", side_effect=request):
            provider.embed_documents(["a story"])
            provider.embed_query("a question")
        self.assertEqual(requests[0]["input"], ["passage: a story"])
        self.assertEqual(requests[1]["input"], ["query: a question"])
        self.assertIs(requests[0]["truncate"], False)

    def test_invalid_vectors_and_incomplete_indices_are_rejected(self):
        bad_vectors = ([1, 0], [0, 0, 0], [math.nan, 1, 0], ["secret", 1, 0])
        for vector in bad_vectors:
            with self.subTest(vector=vector):
                provider = create_provider(self.settings())
                with patch("urllib.request.urlopen", return_value=Response({
                    "data": [{"index": 0, "embedding": vector}]
                })), self.assertRaises(ProviderError):
                    provider.embed_documents(["story"])
        provider = create_provider(self.settings())
        with patch("urllib.request.urlopen", return_value=Response({"data": []})), self.assertRaises(ProviderError):
            provider.embed_query("question")

    def test_transient_errors_retry_and_auth_errors_do_not_leak_response(self):
        provider = create_provider(self.settings(retries=1))
        temporary = HTTPError("https://example", 429, "rate limited", {}, io.BytesIO(b"private-test-key"))
        with patch("urllib.request.urlopen", side_effect=[temporary, Response({
            "data": [{"index": 0, "embedding": [1, 0, 0]}]
        })]), patch("time.sleep"):
            self.assertEqual(provider.embed_query("q"), [1, 0, 0])
        denied = HTTPError("https://example", 401, "private-test-key", {}, io.BytesIO(b"private-test-key"))
        with patch("urllib.request.urlopen", side_effect=denied), self.assertRaises(ProviderError) as error:
            provider.embed_query("q")
        self.assertNotIn("private-test-key", str(error.exception))

    def test_profile_identifies_model_settings_but_excludes_credentials(self):
        first = self.settings()
        self.assertEqual(first.profile_id, self.settings(embedding_api_key="another-key").profile_id)
        self.assertNotEqual(first.profile_id, self.settings(embedding_model="other-model").profile_id)
        self.assertNotEqual(first.profile_id, self.settings(query_prefix="query: ").profile_id)
        self.assertNotIn("private-test-key", repr(first))

    def test_disabled_provider_has_no_fake_embeddings(self):
        self.assertIsNone(create_provider(Settings(data_dir=Path("unused"))))
