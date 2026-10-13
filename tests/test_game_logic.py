import unittest

from game_logic import (
    can_explore, clean, egg_frame, explore, feed, finish_session,
    growth_stage, hatch_complete, mastered_count, new_game, normalize_game,
    play, record_answer, start_session,
)
from words import WORDS


class GameLogicTests(unittest.TestCase):
    def test_word_bank_has_ten_chapters_of_fifteen_distinct_words(self):
        self.assertEqual(len(WORDS), 150)
        self.assertEqual(len({word["id"] for word in WORDS}), 150)
        self.assertEqual([sum(word["chapter"] == chapter for word in WORDS) for chapter in range(10)], [15] * 10)

    def test_egg_hatches_after_five_correct_answers_but_learning_needs_recall(self):
        game = new_game()
        first = start_session(game)
        self.assertEqual(len(first), 5)
        for index, word_id in enumerate(first, start=1):
            self.assertFalse(record_answer(game, word_id, False))
            self.assertEqual(game["correct_answers"], index - 1)
            self.assertFalse(record_answer(game, word_id, True))
            self.assertEqual(egg_frame(game), min(index, 4))
        self.assertTrue(hatch_complete(game))
        self.assertEqual(growth_stage(game), 1)
        self.assertEqual(mastered_count(game), 0)
        start_session(game)
        for word_id in first:
            record_answer(game, word_id, True)
        self.assertEqual(mastered_count(game), 5)

    def test_care_controls_garden_discovery_without_erasing_words(self):
        game = new_game()
        game["correct_answers"] = 5
        game["session"] = 1
        for word in WORDS[:15]:
            record_answer(game, word["id"], True)
        game["session"] = 2
        for word in WORDS[:15]:
            record_answer(game, word["id"], True)
        self.assertEqual(mastered_count(game), 15)
        finish_session(game)
        finish_session(game)
        finish_session(game)
        self.assertFalse(can_explore(game))
        self.assertTrue(feed(game))
        self.assertTrue(play(game))
        self.assertTrue(can_explore(game))
        self.assertTrue(feed(game))
        self.assertTrue(game["poop"])
        self.assertFalse(can_explore(game))
        self.assertTrue(clean(game))
        self.assertTrue(explore(game))
        self.assertEqual(game["garden_plants"], 1)
        self.assertEqual(mastered_count(game), 15)

    def test_loaded_progress_is_bounded_and_unknown_words_are_discarded(self):
        game = normalize_game({
            "cards": {"cat": {"seen": True, "correct_sessions": [2, 1, 2]}, "unknown": {"seen": True}},
            "care": {"food": -5, "joy": 99, "clean": 2},
            "garden_plants": 200,
        })
        self.assertEqual(mastered_count(game), 1)
        self.assertEqual(game["care"], {"food": 0, "joy": 3, "clean": 2})
        self.assertEqual(game["garden_plants"], 0)


if __name__ == "__main__":
    unittest.main()
