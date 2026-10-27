"""Regression checks for authored visual learning and the public curriculum."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAPTOP = ROOT / "laptop"
sys.path.insert(0, str(LAPTOP))

from full_math_schema import load_bank


class VisualLearningContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank_path = LAPTOP / "full_math_lessons.json"
        cls.bank = load_bank(cls.bank_path)

    def _play_module(self):
        path = LAPTOP / "visual_learning.js"
        self.assertTrue(path.is_file(), "visual-learning module has not landed yet")
        return path.read_text(encoding="utf-8")

    def test_canonical_bank_is_complete_and_valid(self):
        self.assertEqual(len(self.bank), 576)
        self.assertEqual(set(self.bank), {row["topic_id"] for row in self.bank.values()})

    def test_authored_discoveries_reference_real_topics(self):
        """Extract module's authored ID list without imposing its presentation copy."""
        source = self._play_module()
        import re
        ids = set(re.findall(r"(?:topic_id|topicId|id)\s*:\s*['\"]([^'\"]+)['\"]", source))
        ids.update(re.findall(r"['\"](mt_[A-Za-z0-9_-]+)['\"]", source))
        self.assertGreaterEqual(len(ids & set(self.bank)), 6, "author at least six valid discovery topics")
        self.assertTrue(ids <= set(self.bank), f"unknown discovery IDs: {sorted(ids - set(self.bank))}")

    def test_public_module_build_and_mount_contract(self):
        source = self._play_module()
        for token in ("window.MathsPlay", "discoveries:", "has(topic_id)", "mountLesson(container, lesson)", "mountQuestion(container, active)"):
            self.assertIn(token, source)
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
        self.assertIn("./visual_learning.js", scripts)
        self.assertIn("./public_runtime.js", scripts)
        self.assertTrue((ROOT / "docs" / "public_runtime.js").is_file())
        self.assertTrue((ROOT / "docs" / "catalog.json").is_file())


if __name__ == "__main__":
    unittest.main()
