import unittest
import re

from game_logic import choice_ids
from grammar import FORM_QUESTIONS, NOTES, form_choices
from words import WORD_BY_ID


class GrammarTests(unittest.TestCase):
    def test_dependent_forms_have_pronoun_context_and_contrasting_choices(self):
        expected_subjects = {"is": "She", "are": "They", "has": "He", "have": "We"}
        for word_id, subject in expected_subjects.items():
            with self.subTest(word=word_id):
                self.assertEqual(FORM_QUESTIONS[word_id][0], subject)
                self.assertTrue(FORM_QUESTIONS[word_id][2])
                options = choice_ids(word_id)
                self.assertEqual(len(options), 3)
                self.assertIn(word_id, options)
                partner = {"is": "are", "are": "is", "have": "has", "has": "have"}[word_id]
                self.assertIn(partner, options)
                self.assertTrue(all(option in WORD_BY_ID for option in options))

    def test_notes_have_rules_and_two_translated_examples(self):
        for word_id, (rule, examples) in NOTES.items():
            with self.subTest(word=word_id):
                self.assertIn(word_id, WORD_BY_ID)
                self.assertTrue(rule)
                self.assertEqual(len(examples), 2)
                self.assertTrue(all(len(example) == 4 and all(example) for example in examples))
        self.assertIsNone(form_choices("cat"))

    def test_rule_explains_only_the_current_form_without_comparison_tables(self):
        forms = {"is", "are", "am", "has", "have"}
        for word_id in ("is", "are", "has", "have"):
            rule, examples = NOTES[word_id]
            mentioned = set(re.findall(r"[a-z]+", rule.lower())) & forms
            self.assertEqual(mentioned, {word_id})
            self.assertTrue(all(example[1] == word_id for example in examples))

    def test_it_rule_explains_who_it_refers_to_with_matching_examples(self):
        rule, examples = NOTES["it"]
        self.assertIn("предмете", rule)
        self.assertIn("животном", rule)
        self.assertIn("не о человеке", rule)
        self.assertTrue(all(example[0] == "It" for example in examples))
        self.assertEqual({example[2] for example in examples}, {"a toy.", "a cat."})


if __name__ == "__main__":
    unittest.main()
