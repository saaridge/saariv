from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from knowledge.config import Settings
from knowledge.embeddings import ProviderError
from knowledge.service import KnowledgeService, ReindexRequired
from knowledge_fixtures import ConceptEmbeddings


class KnowledgeServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(data_dir=Path(self.directory.name), embedding_provider="ollama",
                                 embedding_base_url="http://localhost:11434", embedding_model="test-model",
                                 embedding_dimensions=3)
        self.provider = ConceptEmbeddings()
        self.service = KnowledgeService(self.settings, self.provider)
        self.addCleanup(lambda: self.service.close())

    def add_sources(self):
        self.service.ingest("alice", "housing", "You compared apartment deposits before moving.", "Housing")
        self.service.ingest("alice", "career", "You practiced engineering interviews.", "Career")

    def test_dense_paraphrase_search_returns_original_text_and_offsets(self):
        self.add_sources()
        result = self.service.search("alice", "accommodation", mode="dense")
        self.assertEqual(result["results"][0]["document_id"], "housing")
        self.assertEqual(result["mode"], "dense")
        hit = result["results"][0]
        document = self.service.documents("alice")[0]
        self.assertTrue(hit["source"]["end"] > hit["source"]["start"])
        self.assertEqual(hit["text"], "You compared apartment deposits before moving.")
        self.assertIn("timings_ms", result)
        self.assertTrue(document["document_id"])

    def test_disk_persistence_reuses_vectors_after_restart(self):
        self.add_sources()
        self.service.close()
        self.service = KnowledgeService(self.settings, ConceptEmbeddings())
        self.assertEqual(self.service.status("alice")["documents_count"], 2)
        hits = self.service.search("alice", "accommodation", mode="dense")["results"]
        self.assertEqual(hits[0]["document_id"], "housing")

    def test_duplicate_import_and_equal_passages_reuse_cached_embeddings(self):
        text = "You compared apartment deposits."
        self.service.ingest("alice", "one", text, "Housing")
        calls = self.provider.stats["calls"]
        self.service.ingest("alice", "one", text, "Housing")
        self.service.ingest("alice", "two", text, "Housing")
        self.assertEqual(self.provider.stats["calls"], calls)
        self.assertGreaterEqual(self.service.status("alice")["metrics"]["cache_hits"], 1)

    def test_replacement_and_deletion_remove_old_vectors_and_text(self):
        self.add_sources()
        self.service.ingest("alice", "housing", "You practiced hiring interviews.", "Updated")
        self.assertEqual(self.service.search("alice", "accommodation", mode="dense")["results"], [])
        self.assertEqual(self.service.store.vector_count("alice"), 2)
        self.assertTrue(self.service.delete_document("alice", "housing"))
        self.assertEqual(self.service.status("alice")["documents_count"], 1)
        self.assertEqual(self.service.store.vector_count("alice"), 1)
        self.assertFalse(self.service.delete_document("alice", "missing"))

    def test_failed_import_preserves_previous_source_and_vectors(self):
        self.add_sources()
        self.provider.fail = True
        with self.assertRaises(ProviderError):
            self.service.ingest("alice", "housing", "You discussed something new.", "Changed")
        self.provider.fail = False
        hits = self.service.search("alice", "deposits", mode="hybrid")["results"]
        self.assertIn("apartment deposits", hits[0]["text"])
        self.assertEqual(self.service.store.vector_count("alice"), 2)

    def test_equal_dimensions_do_not_allow_mixing_model_profiles(self):
        self.add_sources()
        self.service.close()
        self.service = KnowledgeService(replace(self.settings, embedding_model="another-model"), ConceptEmbeddings())
        self.assertTrue(self.service.status("alice")["needs_reindex"])
        with self.assertRaises(ReindexRequired):
            self.service.search("alice", "housing")
        self.service.reindex("alice")
        self.assertFalse(self.service.status("alice")["needs_reindex"])
        self.assertEqual(self.service.search("alice", "accommodation")["results"][0]["document_id"], "housing")

    def test_failed_rebuild_does_not_publish_a_partial_profile(self):
        self.add_sources()
        self.service.close()
        provider = ConceptEmbeddings()
        provider.fail = True
        self.service = KnowledgeService(replace(self.settings, embedding_model="another-model"), provider)
        with self.assertRaises(ProviderError):
            self.service.reindex("alice")
        self.assertTrue(self.service.status("alice")["needs_reindex"])
        self.assertEqual(len(self.service.search("alice", "deposits", mode="lexical")["results"]), 1)

    def test_owner_filter_applies_to_dense_keyword_and_deletion(self):
        self.add_sources()
        self.service.ingest("bob", "secret", "You paid an apartment deposit of 900.", "Bob")
        for mode in ("dense", "lexical", "hybrid"):
            hits = self.service.search("alice", "apartment deposit", mode=mode)["results"]
            self.assertTrue(hits)
            self.assertNotIn("secret", [hit["document_id"] for hit in hits])
        self.assertFalse(self.service.delete_document("alice", "secret"))

    def test_unrelated_query_never_returns_the_first_document(self):
        self.add_sources()
        for mode in ("lexical", "dense", "hybrid"):
            self.assertEqual(self.service.search("alice", "astronomy telescope", mode=mode)["results"], [])

    def test_question_word_alone_does_not_match_unrelated_evidence(self):
        self.service.ingest("alice", "housing", "You asked which apartment deposits were refundable.", "Housing")
        for mode in ("lexical", "hybrid"):
            with self.subTest(mode=mode):
                self.assertEqual(self.service.search("alice", "Which telescope did I buy?", mode=mode)["results"], [])
                hits = self.service.search("alice", "Which apartment deposits were refundable?", mode=mode)["results"]
                self.assertEqual(hits[0]["document_id"], "housing")

    def test_no_provider_is_explicitly_lexical_and_dense_is_unavailable(self):
        self.service.close()
        self.service = KnowledgeService(Settings(data_dir=Path(self.directory.name)))
        self.service.ingest("alice", "housing", "You compared apartment deposits.", "Housing")
        result = self.service.search("alice", "deposits")
        self.assertEqual(result["mode"], "lexical")
        self.assertTrue(result["warnings"])
        with self.assertRaises(ProviderError):
            self.service.search("alice", "deposits", mode="dense")

    def test_invalid_text_or_limits_do_not_modify_saved_sources(self):
        self.add_sources()
        with self.assertRaises(ValueError):
            self.service.ingest("alice", "housing", "## Empty", "Housing")
        with self.assertRaises(ValueError):
            self.service.search("alice", "question", limit=99)
        self.assertEqual(self.service.status("alice")["documents_count"], 2)

    def test_keyword_query_punctuation_is_data_not_fts_syntax(self):
        self.add_sources()
        result = self.service.search("alice", '"deposits" OR (housing:* NOT \"', mode="lexical")
        self.assertTrue(result["results"])

    def test_shared_local_client_accepts_serialized_flask_worker_threads(self):
        self.add_sources()
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(self.service.ingest, "alice", f"thread-{index}",
                                f"You compared apartment number {index}.", "Housing") for index in range(3)]
            for job in jobs:
                job.result()
        self.assertEqual(self.service.status("alice")["documents_count"], 5)

    def test_cleanup_failure_after_commit_is_reported_as_recoverable_maintenance(self):
        self.add_sources()
        with patch.object(self.service.store, "prune_vectors", side_effect=OSError("cleanup failed")):
            result = self.service.ingest("alice", "housing", "You practiced engineering interviews.", "Updated")
        self.assertTrue(result["warnings"])
        self.assertTrue(self.service.status("alice")["maintenance_pending"])
        self.service.close()
        self.service = KnowledgeService(self.settings, ConceptEmbeddings())
        self.assertTrue(self.service.status("alice")["maintenance_pending"])
        self.service.reindex("alice")
        self.assertFalse(self.service.status("alice")["maintenance_pending"])
        self.assertEqual(self.service.store.vector_count("alice"), 2)
