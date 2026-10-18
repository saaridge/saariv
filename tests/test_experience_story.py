import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as application
from knowledge.config import Settings
from knowledge.service import KnowledgeService


class ExperienceStoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = patch.object(application, "TMP_DIR", self.directory.name)
        override.start()
        self.addCleanup(override.stop)
        service = KnowledgeService(Settings(data_dir=Path(self.directory.name) / "knowledge"))
        self.addCleanup(service.close)
        settings_override = patch.dict(application.app.config, {"KNOWLEDGE_SERVICE": service})
        settings_override.start()
        self.addCleanup(settings_override.stop)
        self.client = application.app.test_client()

    def test_plain_story_is_saved_and_available_for_retrieval(self):
        story = "You asked about moving to Amsterdam. You said finding housing was your main concern."
        response = self.client.post("/api/onboarding/step4", json={
            "session_id": "story-test",
            "experience_story": story,
            "selected_items": {"topics": ["Relocation"]},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["indexed_count"], 1)
        folder = Path(self.directory.name) / response.get_json()["session_id"]
        self.assertEqual((folder / "experiences.md").read_text(), story)
        chunks = json.loads((folder / "chunks_index.json").read_text())
        self.assertEqual(chunks[0]["experience"], story)
        self.assertEqual(chunks[0]["topic"], "Relocation")
        results = application.retrieve_relevant_experience("housing", chunks)
        self.assertEqual(results[0]["experience"], story)

    def test_topic_headings_split_stories_without_losing_introductory_text(self):
        story = (
            "You described two questions you were exploring.\n\n"
            "## Relocation\nYou asked about apartment deposits.\n\n"
            "## Career\nYou compared two engineering roles."
        )
        response = self.client.post("/api/onboarding/step4", json={
            "session_id": "headings-test", "experience_story": story,
        })
        self.assertEqual(response.status_code, 200)
        folder = Path(self.directory.name) / response.get_json()["session_id"]
        chunks = json.loads((folder / "chunks_index.json").read_text())
        self.assertEqual([c["experience"] for c in chunks], [
            "You described two questions you were exploring.",
            "You asked about apartment deposits.",
            "You compared two engineering roles.",
        ])
        self.assertEqual(chunks[1]["topic"], "Relocation")
        self.assertEqual(chunks[2]["topic"], "Career")

    def test_code_fence_contents_are_preserved_as_part_of_the_story(self):
        story = "## Tooling\nYou shared this snippet:\n```python\n# Keep this comment\nprint('hello')\n```"
        response = self.client.post("/api/onboarding/step4", json={
            "session_id": "code-test", "experience_story": story,
        })
        self.assertEqual(response.status_code, 200)
        folder = Path(self.directory.name) / response.get_json()["session_id"]
        chunks = json.loads((folder / "chunks_index.json").read_text())
        self.assertEqual(len(chunks), 1)
        self.assertIn("# Keep this comment", chunks[0]["experience"])

    def test_empty_story_or_headings_without_narrative_are_rejected(self):
        for story in ["", " \n ", "## Relocation\n\n## Career"]:
            with self.subTest(story=story):
                response = self.client.post("/api/onboarding/step4", json={
                    "experience_story": story,
                })
                self.assertEqual(response.status_code, 400)

    def test_existing_json_imports_remain_usable(self):
        experiences = {"domains": [{"domain": "Career", "subdomains": [{
            "subdomain": "Engineering", "topics": [{
                "topic": "Interviews", "experience": "You practiced system design.",
            }],
        }]}]}
        response = self.client.post("/api/onboarding/step4", json={
            "session_id": "legacy-test", "experiences_json": experiences,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["indexed_count"], 1)


if __name__ == "__main__":
    unittest.main()
