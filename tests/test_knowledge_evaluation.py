import unittest

from knowledge.evaluate import retrieval_metrics


class EvaluationTests(unittest.TestCase):
    def test_metrics_distinguish_first_hit_coverage_and_ranking(self):
        result = retrieval_metrics([["a", "noise"], ["b", "a"], []], [{"a", "b"}, {"a"}, set()], 2)
        self.assertEqual(result["hit_at_k"], 1.0)
        self.assertEqual(result["recall_at_k"], 0.75)
        self.assertEqual(result["precision_at_k"], 0.5)
        self.assertEqual(result["unanswerable_empty_accuracy"], 1.0)
        self.assertLess(result["ndcg_at_k"], 1)
        self.assertEqual(result["answerable_queries"], 2)

    def test_duplicate_chunks_do_not_count_as_multiple_relevant_documents(self):
        result = retrieval_metrics([["a", "a", "b"]], [{"a", "b"}], 2)
        self.assertEqual(result["recall_at_k"], 1)
        self.assertEqual(result["precision_at_k"], 1)

    def test_no_answerable_questions_does_not_report_perfect_retrieval(self):
        result = retrieval_metrics([["noise"]], [set()], 5)
        self.assertIsNone(result["hit_at_k"])
        self.assertEqual(result["unanswerable_empty_accuracy"], 0)
