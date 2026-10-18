import unittest

from knowledge.chunking import chunk_document


class ChunkingTests(unittest.TestCase):
    def test_long_unicode_sections_keep_exact_offsets_and_size(self):
        text = "## Housing\n" + ("You compared cafés and homes in 東京. " * 100)
        chunks = chunk_document(text, "Story", {}, size=180, overlap=30)
        self.assertGreater(len(chunks), 10)
        covered = set()
        for chunk in chunks:
            self.assertLessEqual(len(chunk["text"]), 180)
            self.assertEqual(text[chunk["start"]:chunk["end"]], chunk["text"])
            self.assertEqual(chunk["section"], "Housing")
            covered.update(range(chunk["start"], chunk["end"]))
        for index, char in enumerate(text[text.index("You"):], text.index("You")):
            if not char.isspace():
                self.assertIn(index, covered)

    def test_fenced_headings_are_body_text_and_intro_is_preserved(self):
        text = "You described tooling.\n## Setup\nYou shared:\n```python\n# A comment\nprint('x')\n```\n## Next\nYou asked a question."
        chunks = chunk_document(text, "Original", {})
        self.assertEqual([c["section"] for c in chunks], ["Original", "Setup", "Next"])
        self.assertIn("# A comment", chunks[1]["text"])

    def test_page_spans_are_attached_to_the_original_excerpt(self):
        text = "You discussed housing.\n\nYou discussed interviews."
        chunks = chunk_document(text, "Upload", {"page_spans": [
            {"start": 0, "end": 22, "page": 1},
            {"start": 24, "end": len(text), "page": 2},
        ]})
        self.assertEqual(chunks[0]["page_start"], 1)
        self.assertEqual(chunks[0]["page_end"], 2)

    def test_empty_or_headings_only_documents_have_no_chunks(self):
        for text in ("", "  \n", "## Empty\n\n## Also empty"):
            self.assertEqual(chunk_document(text, "Story", {}), [])

    def test_invalid_window_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            chunk_document("text", "Story", {}, size=10, overlap=10)
