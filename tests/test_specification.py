from pathlib import Path
import re
import unittest

from game_logic import CARE_MAX, GROWTH_THRESHOLDS
from instructions import HELP_PAGES
from learning_stats import MILESTONES, REVIEW_SIZE
from words import ALL_WORDS, WORD_BANKS
from zoo import SPECIES, final_size, pass_mark


class SpecificationTests(unittest.TestCase):
    def test_approved_balance_constants_are_not_changed_silently(self):
        self.assertEqual(GROWTH_THRESHOLDS, (30, 60, 90, 120))
        self.assertEqual(MILESTONES, (50, 100, 150))
        self.assertEqual(REVIEW_SIZE, 20)
        self.assertEqual([final_size(key) for key, _ in SPECIES], [50, 60, 70, 80, 90, 100])
        self.assertEqual([pass_mark(final_size(key)) for key, _ in SPECIES], [35, 42, 49, 56, 63, 70])
        self.assertEqual(CARE_MAX, 3)
        self.assertEqual([key for key, _ in SPECIES], ["sniffer", "axolotl", "fox", "bee", "turtle", "allay"])
        self.assertEqual(len(ALL_WORDS), 900)
        self.assertEqual([len(WORD_BANKS[key]) for key, _ in SPECIES], [150] * 6)

    def test_in_game_guide_has_short_pages_for_all_main_features(self):
        self.assertGreaterEqual(len(HELP_PAGES), 8)
        for title, lines in HELP_PAGES:
            self.assertTrue(title)
            self.assertLessEqual(len(lines), 7)
            self.assertTrue(all(lines))
        content = " ".join(line for _, lines in HELP_PAGES for line in lines)
        for important in ("70%", "150", "900", "Словарик", "JSON", "пароля"):
            self.assertIn(important, content)

    def test_agent_document_links_resolve_to_existing_specification_files(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "AGENTS.md").read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if not target.startswith(("http:", "https:")):
                self.assertTrue((root / target).is_file(), target)


if __name__ == "__main__":
    unittest.main()
