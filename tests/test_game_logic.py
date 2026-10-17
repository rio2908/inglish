import unittest
import random
import copy

from game_logic import (
    can_explore, clean, egg_frame, explore, feed, finish_session,
    growth_stage, hatch_complete, mastered_count, new_game, normalize_game,
    play, record_answer, start_session,
)
from words import WORDS
from learning_fixtures import clear_checkpoints


class GameLogicTests(unittest.TestCase):
    def test_answer_without_a_started_round_is_rejected_without_mutating_progress(self):
        game = new_game()
        before = copy.deepcopy(game)
        with self.assertRaises(ValueError):
            record_answer(game, "cat", True)
        self.assertEqual(game, before)

    def test_resumed_legacy_lesson_recovers_a_valid_non_reused_round_number(self):
        raw = new_game()
        raw["cards"]["cat"] = {"seen": True, "correct_sessions": [2]}
        raw["lesson"] = {"queue": ["cat", "dog"], "index": 0, "phase": "quiz", "mode": "meaning", "correct": False, "answers": 0}
        game = normalize_game(raw)
        self.assertGreater(game["session"], 2)
        record_answer(game, "cat", True)
        restored = normalize_game(game)
        self.assertEqual(mastered_count(restored), mastered_count(game))
        self.assertEqual(restored["cards"]["cat"]["correct_sessions"], game["cards"]["cat"]["correct_sessions"])

    def test_recovered_round_counter_is_idempotent_and_handles_old_completed_rounds(self):
        raw = new_game()
        raw["cards"]["cat"] = {"seen": True, "correct_sessions": [4, 7]}
        recovered = normalize_game(raw)
        self.assertEqual(recovered["session"], 7)
        self.assertEqual(normalize_game(recovered), recovered)
        self.assertIn(start_session(recovered, random.Random(1))[-1], {word["id"] for word in WORDS})
        self.assertEqual(recovered["session"], 8)

    def test_unknown_word_is_rejected_before_it_changes_attempts_or_cards(self):
        game = new_game()
        start_session(game)
        before = copy.deepcopy(game)
        with self.assertRaises(ValueError):
            record_answer(game, "not-a-vocabulary-id", True)
        self.assertEqual(game, before)

    def test_learned_count_never_decreases_during_normal_play_or_backup_round_trips(self):
        from game_storage import make_backup_bytes, read_backup_bytes
        game = new_game()
        rng = random.Random(21)
        previous = 0
        for _ in range(20):
            for word_id in start_session(game, rng):
                record_answer(game, word_id, rng.random() > 0.25)
                current = mastered_count(game)
                self.assertGreaterEqual(current, previous)
                previous = current
            game = read_backup_bytes(make_backup_bytes(game))
            self.assertEqual(mastered_count(game), previous)

    def test_word_bank_has_ten_chapters_of_fifteen_distinct_words(self):
        self.assertEqual(len(WORDS), 150)
        self.assertEqual(len({word["id"] for word in WORDS}), 150)
        self.assertEqual([sum(word["chapter"] == chapter for word in WORDS) for chapter in range(10)], [15] * 10)

    def test_greetings_replace_standalone_articles(self):
        words = {word["en"]: word for word in WORDS}
        for article in ("a", "an", "the"):
            self.assertNotIn(article, words)
        for english, russian in (("hello", "привет"), ("bye", "пока")):
            self.assertEqual(words[english]["ru"], russian)
            self.assertEqual(words[english]["chapter"], 0)

    def test_egg_cracks_gradually_and_hatches_after_thirty_mastered_words(self):
        game = new_game()
        first = start_session(game)
        self.assertEqual(len(first), 5)
        for index, word_id in enumerate(first, start=1):
            self.assertFalse(record_answer(game, word_id, False))
            self.assertEqual(game["correct_answers"], index - 1)
            self.assertFalse(record_answer(game, word_id, True))
            self.assertEqual(egg_frame(game), 0)
        self.assertFalse(hatch_complete(game))
        self.assertEqual(growth_stage(game), 0)
        self.assertEqual(mastered_count(game), 0)
        for count in range(31):
            game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in WORDS[:count]}
            self.assertEqual(egg_frame(game), min(count // 6, 4))
            self.assertEqual(hatch_complete(game), count >= 30)
        self.assertEqual(growth_stage(game), 1)

    def test_care_controls_garden_discovery_without_erasing_words(self):
        game = new_game()
        game["correct_answers"] = 5
        game["session"] = 1
        for word in WORDS[:30]:
            record_answer(game, word["id"], True)
        game["session"] = 2
        for word in WORDS[:30]:
            record_answer(game, word["id"], True)
        self.assertEqual(mastered_count(game), 30)
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
        self.assertEqual(mastered_count(game), 30)

    def test_loaded_progress_is_bounded_and_unknown_words_are_discarded(self):
        game = normalize_game({
            "cards": {"cat": {"seen": True, "correct_sessions": [2, 1, 2]}, "unknown": {"seen": True}},
            "care": {"food": -5, "joy": 99, "clean": 2},
            "garden_plants": 200,
        })
        self.assertEqual(mastered_count(game), 1)
        self.assertEqual(game["care"], {"food": 0, "joy": 3, "clean": 2})
        self.assertEqual(game["garden_plants"], 0)

    def test_growth_notice_is_created_only_at_the_four_thirty_word_transitions(self):
        game = new_game()
        game["session"] = 1
        for word in WORDS:
            record_answer(game, word["id"], True)
        game["session"] = 2
        transitions = []
        for count, word in enumerate(WORDS, start=1):
            record_answer(game, word["id"], True)
            clear_checkpoints(game)
            if game["growth_notice"]:
                transitions.append((count, game["growth_notice"]["before"], game["growth_notice"]["after"]))
                game["growth_notice"] = None
        self.assertEqual(transitions, [(30, 0, 1), (60, 1, 2), (90, 2, 3), (120, 3, 4)])
        record_answer(game, WORDS[0]["id"], True)
        self.assertIsNone(game["growth_notice"])


if __name__ == "__main__":
    unittest.main()
