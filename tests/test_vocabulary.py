import copy
import unittest

from game_logic import new_game, normalize_game, record_answer
from vocabulary import learned_vocabulary


class VocabularyTests(unittest.TestCase):
    def test_dictionary_contains_only_mastered_words_sorted_alphabetically(self):
        game = new_game()
        game["cards"] = {"cat": {"seen": True, "correct_sessions": [1, 2]},
                         "apple": {"seen": True, "correct_sessions": [1, 2]},
                         "dog": {"seen": True, "correct_sessions": [1]}}
        self.assertEqual([word["id"] for word in learned_vocabulary(game)], ["apple", "cat"])
        self.assertTrue(all(word["hint"] and word["ru"] for word in learned_vocabulary(game)))

    def test_search_works_for_english_russian_and_pronunciation(self):
        game = new_game()
        for session in (1, 2):
            game["session"] = session
            record_answer(game, "cat", True)
        for query in ("CAT", "кошка", "кэт"):
            self.assertEqual([word["id"] for word in learned_vocabulary(game, query=query)], ["cat"])
        self.assertEqual(learned_vocabulary(game, query="dog"), [])

    def test_filters_and_reading_do_not_change_any_game_state(self):
        game = new_game()
        for session in (1, 2):
            game["session"] = session
            for word_id in ("cat", "dog", "one"):
                record_answer(game, word_id, True)
        game["repeat_words"] = ["cat", "one", "apple"]
        before = copy.deepcopy(game)
        self.assertEqual([word["id"] for word in learned_vocabulary(game, "sniffer", errors_only=True)], ["cat"])
        self.assertEqual([word["id"] for word in learned_vocabulary(game, "axolotl")], ["one"])
        self.assertEqual(game, before)

    def test_boolean_or_duplicate_rounds_do_not_create_false_learned_entries(self):
        game = normalize_game({"cards": {"cat": {"seen": True, "correct_sessions": [True, 2]},
                                          "dog": {"seen": True, "correct_sessions": [3, 3]}}})
        self.assertEqual(learned_vocabulary(game), [])


if __name__ == "__main__":
    unittest.main()
