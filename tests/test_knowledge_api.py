import io
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as application
from knowledge.config import Settings
from knowledge.service import KnowledgeService
from knowledge_fixtures import ConceptEmbeddings


def two_page_pdf():
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for text in (b"You compared apartment deposits.", b"You practiced engineering interviews."):
        stream = b"BT /F1 12 Tf 50 700 Td (" + text + b") Tj ET"
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    data = b"%PDF-1.4\n"
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 8\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return data + f"trailer << /Size 8 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


class KnowledgeAPITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.service = KnowledgeService(Settings(data_dir=Path(self.directory.name) / "knowledge"))
        self.addCleanup(lambda: self.service.close())
        self.override = patch.dict(application.app.config, {"TESTING": True, "KNOWLEDGE_SERVICE": self.service})
        self.override.start()
        self.addCleanup(self.override.stop)
        self.path_override = patch.object(application, "TMP_DIR", str(Path(self.directory.name) / "profiles"))
        self.path_override.start()
        self.addCleanup(self.path_override.stop)
        log_override = patch.object(application, "QUESTIONS_LOG_PATH", str(Path(self.directory.name) / "questions.jsonl"))
        log_override.start()
        self.addCleanup(log_override.stop)
        self.chat = patch.dict("os.environ", {"CHAT_PROVIDER": "extractive"})
        self.chat.start()
        self.addCleanup(self.chat.stop)
        self.client = application.app.test_client()

    def use_embeddings(self, model="test-model"):
        settings = replace(self.service.settings, embedding_provider="ollama",
                           embedding_base_url="http://localhost:11434", embedding_model=model,
                           embedding_dimensions=3)
        self.service.close()
        self.service = KnowledgeService(settings, ConceptEmbeddings())
        application.app.config["KNOWLEDGE_SERVICE"] = self.service

    def import_story(self, client=None, text="You asked about apartment deposits."):
        response = (client or self.client).post("/api/onboarding/step4", json={
            "session_id": "client-provided-id", "experience_story": text,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["session_id"]

    def test_story_import_to_search_returns_sources_with_server_issued_owner(self):
        owner = self.import_story()
        self.assertNotEqual(owner, "client-provided-id")
        response = self.client.post("/api/knowledge/search", json={"query": "deposits"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["results"][0]["text"], "You asked about apartment deposits.")
        self.assertEqual(response.json["mode"], "lexical")
        self.assertIn("source", response.json["results"][0])

    def test_another_browser_cannot_select_an_owner_by_session_id(self):
        owner = self.import_story()
        other = application.app.test_client()
        response = other.post("/api/knowledge/search", json={"query": "deposits", "session_id": owner})
        self.assertEqual(response.status_code, 401)
        other_owner = self.import_story(other, "You practiced interviews.")
        response = other.post("/api/knowledge/search", json={"query": "deposits", "session_id": owner})
        self.assertEqual(response.status_code, 403)
        response = other.post("/api/knowledge/search", json={"query": "deposits"})
        self.assertEqual(response.json["results"], [])
        self.assertNotEqual(owner, other_owner)

    def test_agent_token_is_owner_scoped_read_only_and_revocable(self):
        owner = self.import_story()
        token_response = self.client.post("/api/knowledge/token")
        self.assertEqual(token_response.status_code, 200)
        token = token_response.json["token"]
        headers = {"Authorization": "Bearer " + token}
        agent = application.app.test_client()
        response = agent.post("/api/knowledge/search", json={"query": "deposits"}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["results"])
        denied = agent.delete("/api/knowledge/documents/story", headers=headers)
        self.assertEqual(denied.status_code, 403)
        self.client.delete("/api/knowledge/token")
        response = agent.post("/api/knowledge/search", json={"query": "deposits"}, headers=headers)
        self.assertEqual(response.status_code, 401)
        with self.service.store.connect() as conn:
            self.assertNotIn(token, json.dumps([tuple(row) for row in conn.execute("SELECT * FROM access_tokens")]))

    def test_unknown_query_has_no_sample_biography_or_first_chunk_fallback(self):
        self.import_story()
        response = self.client.post("/api/playground/rag-query", json={"query": "astronomy telescope"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["sources"], [])
        self.assertEqual(response.json["answer_mode"], "insufficient")
        self.assertNotIn("Aarav", response.json["reply"])

    def test_extract_mode_preserves_asked_wording_and_returns_citations(self):
        self.import_story()
        response = self.client.post("/api/playground/rag-query", json={"query": "deposits"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["answer_mode"], "extractive")
        self.assertIn("I asked", response.json["reply"])
        self.assertNotIn("I paid", response.json["reply"])
        self.assertIn("[S1]", response.json["reply"])
        self.assertEqual(len(response.json["sources"]), 1)
        self.assertEqual(response.json["sources"][0]["text"], "You asked about apartment deposits.")
        self.assertEqual(response.json["sources"][0]["display_text"], "I asked about apartment deposits.")

    def test_first_person_display_preserves_raw_unicode_citations_and_claim_states(self):
        story = ("## Housing 🏡\nYou asked about apartment deposits.\n\n"
                 "You planned to compare rents.\n\nYou paid one deposit.")
        self.import_story(text=story)
        response = self.client.post("/api/playground/rag-query", json={"query": "deposits"})
        self.assertEqual(response.status_code, 200)
        source = response.json["sources"][0]
        self.assertEqual(source["text"], story[source["source"]["start"]:source["source"]["end"]])
        self.assertEqual(source["text"], "You asked about apartment deposits.\n\nYou planned to compare rents.\n\nYou paid one deposit.")
        self.assertEqual(source["display_text"], "I asked about apartment deposits.\n\nI planned to compare rents.\n\nI paid one deposit.")
        self.assertIn("I asked", response.json["reply"])
        self.assertIn("I planned", response.json["reply"])
        self.assertIn("I paid", response.json["reply"])

    def test_file_upload_keeps_pdf_pages_and_distinct_sources(self):
        self.import_story()
        response = self.client.post("/api/onboarding/step5-files", data={
            "topic_tag": "Uploaded", "files": [(io.BytesIO(two_page_pdf()), "journey.pdf"),
                                                 (io.BytesIO(b"You compared flight schedules."), "travel.txt")],
        })
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.service.status(response.json["session_id"])["documents_count"], 3)
        hits = self.client.post("/api/knowledge/search", json={"query": "engineering"}).json["results"]
        self.assertEqual(hits[0]["source"]["filename"], "journey.pdf")
        self.assertEqual(hits[0]["source"]["page_end"], 2)

    def test_path_like_filenames_never_write_outside_storage(self):
        self.import_story()
        response = self.client.post("/api/onboarding/step5-files", data={
            "files": (io.BytesIO(b"You asked about apartment deposits."), "../../escape.txt"),
        })
        self.assertEqual(response.status_code, 200, response.json)
        self.assertFalse((Path(self.directory.name) / "escape.txt").exists())
        response = self.client.post("/api/onboarding/step4", json={
            "session_id": "../../escape", "experience_story": "Text",
        })
        self.assertIn(response.status_code, {400, 403})

    def test_empty_pdf_and_legacy_doc_are_clear_errors(self):
        self.import_story()
        from PyPDF2 import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buffer = io.BytesIO()
        writer.write(buffer)
        for content, filename in ((buffer.getvalue(), "scanned.pdf"), (b"binary", "legacy.doc")):
            response = self.client.post("/api/onboarding/step5-files", data={
                "files": (io.BytesIO(content), filename),
            })
            self.assertEqual(response.status_code, 400)
            self.assertFalse(response.json["ok"])

    def test_automatic_cleanup_does_not_delete_old_profiles(self):
        owner = self.import_story()
        folder = Path(application.TMP_DIR) / owner
        (folder / "profile.json").write_text(json.dumps({"created_at": "2020-01-01T00:00:00+00:00"}))
        application.cleanup_old_sessions()
        self.assertTrue(folder.exists())
        self.assertEqual(self.service.status(owner)["documents_count"], 1)

    def test_delete_and_reindex_endpoints_operate_on_owned_documents(self):
        self.import_story()
        self.assertEqual(self.client.get("/api/knowledge/documents").json["documents"][0]["document_id"], "story")
        self.assertEqual(self.client.post("/api/knowledge/reindex").status_code, 200)
        self.assertEqual(self.client.delete("/api/knowledge/documents/story").status_code, 200)
        self.assertEqual(self.client.get("/api/knowledge/status").json["documents_count"], 0)

    def test_invalid_json_and_bad_limits_are_not_internal_server_errors(self):
        self.import_story()
        for body in ([], {"query": "test", "limit": "five"}, {"query": "test", "limit": 100}):
            response = self.client.post("/api/knowledge/search", json=body)
            self.assertEqual(response.status_code, 400)

    def test_custom_text_is_separately_retrievable(self):
        owner = self.import_story()
        response = self.client.post("/api/onboarding/step5", json={
            "custom_experience": "You practiced engineering interviews.", "topic_tag": "Career",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.status(owner)["documents_count"], 2)
        self.assertEqual(self.client.post("/api/knowledge/search", json={"query": "engineering"}).status_code, 200)

    def test_failed_first_import_retries_using_the_signed_browser_cookie(self):
        first = self.client.post("/api/onboarding/step4", json={"experience_story": "## Empty"})
        self.assertEqual(first.status_code, 400)
        with self.client.session_transaction() as session:
            owner = session["knowledge_owner"]
        self.assertEqual(self.service.store.documents(owner), [])
        retry = self.client.post("/api/onboarding/step4", json={"experience_story": "You asked about deposits."})
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json["session_id"], owner)

    def test_failed_first_embedding_import_retries_with_same_signed_owner(self):
        self.use_embeddings()
        provider = self.service.provider
        provider.fail = True
        first = self.client.post("/api/onboarding/step4", json={"experience_story": "You asked about deposits."})
        self.assertEqual(first.status_code, 503)
        with self.client.session_transaction() as session:
            owner = session["knowledge_owner"]
        self.assertEqual(self.service.store.documents(owner), [])
        self.assertFalse((Path(application.TMP_DIR) / owner).exists())
        self.assertIs(self.service.provider, provider)
        provider.fail = False
        retry = self.client.post("/api/onboarding/step4", json={"experience_story": "You asked about deposits."})
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json["session_id"], owner)
        self.assertEqual(retry.json["indexing_mode"], "hybrid")

    def test_embedding_failure_keeps_saved_story_and_other_owner_searchable(self):
        self.use_embeddings()
        owner = self.import_story()
        self.service.ingest("other-owner", "housing", "You compared apartment deposits.", "Housing")
        self.service.provider.fail = True
        response = self.client.post("/api/onboarding/step4", json={"experience_story": "You practiced engineering interviews."})
        self.assertEqual(response.status_code, 503)
        self.assertEqual((Path(application.TMP_DIR) / owner / "experiences.md").read_text(), "You asked about apartment deposits.")
        self.service.provider.fail = False
        hits = self.client.post("/api/knowledge/search", json={"query": "accommodation", "mode": "dense"})
        self.assertEqual(hits.json["results"][0]["text"], "You asked about apartment deposits.")
        self.assertEqual(self.service.search("other-owner", "accommodation", mode="dense")["results"][0]["document_id"], "housing")

    def test_profile_change_returns_conflict_until_explicit_reindex(self):
        self.use_embeddings()
        owner = self.import_story()
        self.service.ingest(owner, "career", "You practiced engineering interviews.", "Career")
        self.use_embeddings(model="another-model")
        documents = self.service.store.documents(owner)
        response = self.client.post("/api/onboarding/step4", json={"experience_story": "You discussed astronomy."})
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json["needs_reindex"])
        self.assertEqual(self.service.store.documents(owner), documents)
        self.assertEqual(self.service.store.vector_count(owner), 2)
        self.assertEqual(self.client.post("/api/knowledge/reindex").status_code, 200)
        self.assertEqual(self.client.post("/api/knowledge/search", json={"query": "accommodation", "mode": "dense"}).json["results"][0]["document_id"], "story")

    def test_different_files_with_same_name_are_preserved_and_identical_reuploads_deduplicate(self):
        owner = self.import_story()
        for content in (b"You compared apartment deposits.", b"You practiced engineering interviews."):
            response = self.client.post("/api/onboarding/step5-files", data={
                "files": (io.BytesIO(content), "report.txt"),
            })
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.status(owner)["documents_count"], 3)
        self.client.post("/api/onboarding/step5-files", data={
            "files": (io.BytesIO(b"You practiced engineering interviews."), "report.txt"),
        })
        self.assertEqual(self.service.status(owner)["documents_count"], 3)

    def test_file_replacement_requires_an_explicit_owned_document_id(self):
        owner = self.import_story()
        self.client.post("/api/onboarding/step5-files", data={
            "files": (io.BytesIO(b"You compared flight schedules."), "first.txt"),
        })
        document_id = next(doc["document_id"] for doc in self.service.documents(owner) if doc["document_id"] != "story")
        response = self.client.post("/api/onboarding/step5-files", data={
            "replace_document_id": document_id,
            "files": (io.BytesIO(b"You practiced engineering interviews."), "updated.txt"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.status(owner)["documents_count"], 2)
        hits = self.client.post("/api/knowledge/search", json={"query": "engineering"}).json["results"]
        self.assertEqual(hits[0]["document_id"], document_id)
        self.assertEqual(self.client.post("/api/knowledge/search", json={"query": "flight"}).json["results"], [])

    def test_committed_import_exports_sources_and_reports_deferred_cleanup(self):
        owner = self.import_story()
        with patch.object(self.service.store, "prune_vectors", side_effect=OSError("synthetic cleanup failure")):
            response = self.client.post("/api/onboarding/step4", json={"experience_story": "You practiced engineering interviews."})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["warnings"])
        self.assertEqual((Path(application.TMP_DIR) / owner / "experiences.md").read_text(), "You practiced engineering interviews.")
        self.assertTrue(self.client.get("/api/knowledge/status").json["maintenance_pending"])
        self.client.post("/api/knowledge/reindex")
        self.assertFalse(self.client.get("/api/knowledge/status").json["maintenance_pending"])
