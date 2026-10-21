import io
import json
import ssl
import unittest
from unittest.mock import patch

from knowledge.answers import answer_from_sources


class AnswerTests(unittest.TestCase):
    def sources(self):
        return [{"citation_id": "S1", "text": "You asked about apartment deposits.",
                 "source": {"title": "Story", "section": "Housing"}}]

    def test_missing_sources_never_call_an_answer_api(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("must not call")):
            self.assertEqual(answer_from_sources("housing", [], {})["answer_mode"], "insufficient")

    def test_extractive_mode_preserves_original_claim_and_marks_source(self):
        with patch.dict("os.environ", {"CHAT_PROVIDER": "extractive"}):
            result = answer_from_sources("housing", self.sources(), {})
        self.assertIn("You asked", result["reply"])
        self.assertIn("[S1]", result["reply"])

    def test_compatible_chat_uses_configured_model_and_grounding_instructions(self):
        requests = []

        def request(req, timeout, context):
            self.assertEqual(timeout, 45)
            self.assertIsInstance(context, ssl.SSLContext)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            requests.append(json.loads(req.data))
            self.assertEqual(req.full_url, "https://chat.example/v1/chat/completions")
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": "You asked about deposits. [S1]"}}]}).encode())

        config = {"CHAT_PROVIDER": "openai_compatible", "CHAT_BASE_URL": "https://chat.example/v1",
                  "CHAT_MODEL": "a-different-answer-model", "CHAT_API_KEY": "test-key"}
        with patch.dict("os.environ", config), patch("urllib.request.urlopen", side_effect=request):
            result = answer_from_sources("housing", self.sources(), {})
        self.assertEqual(requests[0]["model"], config["CHAT_MODEL"])
        self.assertIn("planned", requests[0]["messages"][0]["content"])
        self.assertEqual(result["answer_mode"], "generated")

    def test_invalid_citations_and_api_failure_use_honest_source_excerpts(self):
        with patch.dict("os.environ", {"CHAT_PROVIDER": "openai_compatible", "CHAT_MODEL": "model",
                                      "CHAT_BASE_URL": "https://chat.example/v1"}), \
             patch("knowledge.answers.post_json", return_value={
                 "choices": [{"message": {"content": "I paid the deposit. [S99]"}}]
             }):
            result = answer_from_sources("housing", self.sources(), {})
        self.assertEqual(result["answer_mode"], "extractive")
        self.assertNotIn("I paid", result["reply"])
