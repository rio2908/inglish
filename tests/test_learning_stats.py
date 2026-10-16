import copy
import random
import unittest

from game_logic import new_game, normalize_game, record_answer
from game_storage import make_backup_bytes, read_backup_bytes
from learning_stats import (
    MILESTONES, advance_review, answer_review, learned_ids, pending_review,
    review_choices, review_score, start_review, statistics, word_status,
)
from words import WORDS
from words import words_for_species
from zoo import begin_replay


def learned_game(count):
    game = new_game()
    for session in (1, 2):
        game["session"] = session
        for word in WORDS[:count]:
            record_answer(game, word["id"], True)
    return game


def complete_review(game, correct=6):
    review = start_review(game, random.Random(4))
    queue = review["queue"][:]
    for i, word_id in enumerate(queue):
        chosen = word_id if i < correct else next(word["id"] for word in WORDS if word["id"] != word_id)
        answer_review(game, chosen)
        advance_review(game)
    return review


class LearningStatsTests(unittest.TestCase):
    def test_suspended_pets_completed_checks_survive_saving_during_replay(self):
        game = learned_game(150)
        game["zoo"]["residents"] = [{"species": "sniffer", "name": "Сниффер"}]
        game["zoo"]["active"] = "axolotl"
        for _ in range(2):
            game["session"] += 1
            for word in words_for_species("axolotl")[:40]:
                record_answer(game, word["id"], True)
        review = start_review(game, random.Random(2))
        for word_id in review["queue"][:]:
            answer_review(game, word_id)
            advance_review(game)
        game["active_review"] = None
        game["growth_notice"] = None
        self.assertEqual(game["reviews"], [{"milestone": 30, "score": 6, "total": 6, "species": "axolotl"}])
        self.assertTrue(begin_replay(game, 0))
        restored = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(restored["reviews"], game["reviews"])

    def test_only_mastered_words_unlock_reviews(self):
        game = new_game()
        game["session"] = 1
        for word in WORDS[:30]:
            record_answer(game, word["id"], True)
        self.assertIsNone(pending_review(game))
        game["session"] = 2
        for word in WORDS[:29]:
            record_answer(game, word["id"], True)
        self.assertIsNone(pending_review(game))
        record_answer(game, WORDS[29]["id"], True)
        self.assertEqual(pending_review(game), 30)

    def test_all_five_milestones_are_offered_once(self):
        game = learned_game(150)
        for milestone in MILESTONES:
            self.assertEqual(pending_review(game), milestone)
            review = complete_review(game)
            self.assertEqual(review["milestone"], milestone)
            self.assertEqual(review["phase"], "summary")
            self.assertEqual(review_score(review), 6)
            self.assertEqual(game["reviews"][-1], {"milestone": milestone, "score": 6, "total": 6})
            game["active_review"] = None
            game = normalize_game(game)
        self.assertIsNone(pending_review(game))
        self.assertIsNone(start_review(game))
        self.assertEqual(len(game["reviews"]), 5)

    def test_questions_and_options_use_only_previously_learned_words(self):
        game = learned_game(45)
        review = start_review(game, random.Random(9))
        self.assertEqual(len(review["queue"]), 6)
        self.assertEqual(len(set(review["queue"])), 6)
        eligible = set(learned_ids(game)[:30])
        self.assertTrue(set(review["queue"]) <= eligible)
        self.assertTrue(set(review_choices(game)) <= eligible)
        self.assertIn(review["queue"][0], review_choices(game))

    def test_reviews_record_errors_without_affecting_growth_or_care(self):
        game = learned_game(30)
        before = copy.deepcopy(game)
        review = complete_review(game, correct=4)
        self.assertEqual(review_score(review), 4)
        for key in ("correct_answers", "cards", "care", "session", "garden_plants", "learned_order"):
            self.assertEqual(game[key], before[key])
        totals = statistics(game)
        self.assertEqual(totals["attempts"], 66)
        self.assertEqual(totals["correct"], 64)
        self.assertEqual(totals["learned"], 30)

    def test_double_clicks_and_reload_do_not_record_twice(self):
        game = learned_game(30)
        review = start_review(game)
        self.assertTrue(answer_review(game, review["queue"][0]))
        self.assertFalse(answer_review(game, review["queue"][0]))
        game = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(game["active_review"]["phase"], "feedback")
        self.assertEqual(len(game["active_review"]["answers"]), 1)
        self.assertFalse(answer_review(game, game["active_review"]["queue"][0]))
        self.assertEqual(statistics(game)["attempts"], 61)
        advance_review(game)
        self.assertEqual(game["active_review"]["phase"], "quiz")
        self.assertEqual(len(game["active_review"]["answers"]), 1)

    def test_old_saves_keep_progress_but_do_not_invent_historical_errors(self):
        old = {"cards": {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in WORDS[:30]}}
        game = normalize_game(old)
        totals = statistics(game)
        self.assertEqual(totals["learned"], 30)
        self.assertEqual(totals["attempts"], 0)
        self.assertIsNone(totals["accuracy"])
        self.assertEqual(pending_review(game), 30)

    def test_training_counts_errors_and_distinguishes_word_statuses(self):
        game = new_game()
        self.assertEqual(word_status(game, "cat"), "Не открыто")
        game["session"] = 1
        record_answer(game, "cat", False)
        self.assertEqual(word_status(game, "cat"), "Повторить")
        record_answer(game, "cat", True)
        game["session"] = 2
        record_answer(game, "cat", True)
        self.assertEqual(word_status(game, "cat"), "Повторить")
        self.assertEqual(statistics(game)["accuracy"], 67)
        self.assertEqual(game["word_stats"]["cat"]["lesson_attempts"], 3)
        self.assertEqual(game["word_stats"]["cat"]["lesson_correct"], 2)
        self.assertEqual(game["learned_order"], ["cat"])

    def test_mistakes_are_prioritized_even_if_the_word_is_not_mastered_yet(self):
        game = learned_game(30)
        difficult = WORDS[35]["id"]
        record_answer(game, difficult, False)
        record_answer(game, difficult, True)
        self.assertIn(difficult, game["repeat_words"])
        self.assertNotIn(difficult, learned_ids(game))
        review = start_review(game, random.Random(2))
        self.assertIn(difficult, review["queue"])
        game = read_backup_bytes(make_backup_bytes(game))
        self.assertIn(difficult, game["active_review"]["queue"])
        for word_id in game["active_review"]["queue"][:]:
            answer_review(game, word_id)
            advance_review(game)
        self.assertNotIn(difficult, game["repeat_words"])
        self.assertNotIn(difficult, learned_ids(game))
        self.assertEqual(word_status(game, difficult), "Повторяем")
        # Reload must keep the completed check even after its successful word left the error list.
        self.assertEqual(read_backup_bytes(make_backup_bytes(game)), game)

    def test_failed_review_words_return_at_the_next_thirty_word_checkpoint(self):
        game = learned_game(60)
        review = complete_review(game, correct=4)
        missed = review["queue"][4:]
        self.assertEqual(set(game["repeat_words"]), set(missed))
        game["active_review"] = None
        game = normalize_game(game)
        second = start_review(game, random.Random(17))
        self.assertEqual(second["milestone"], 60)
        self.assertTrue(set(missed) <= set(second["queue"]))
        for word_id in second["queue"][:]:
            answer_review(game, word_id)
            advance_review(game)
        self.assertEqual(game["repeat_words"], [])

    def test_large_error_backlog_is_rotated_without_growing_the_test(self):
        game = learned_game(60)
        difficult = [word["id"] for word in WORDS[:8]]
        for word_id in difficult:
            record_answer(game, word_id, False)
        first = start_review(game, random.Random(1))
        self.assertEqual(set(first["queue"]), set(difficult[:6]))
        for expected in first["queue"][:]:
            wrong = next(word["id"] for word in WORDS if word["id"] != expected)
            answer_review(game, wrong)
            advance_review(game)
        game["active_review"] = None
        second = start_review(game, random.Random(5))
        self.assertEqual(len(second["queue"]), 6)
        self.assertTrue(set(difficult[6:]) <= set(second["queue"]))

    def test_corrupt_statistics_and_active_review_are_sanitized(self):
        raw = learned_game(30)
        raw["word_stats"] = {"cat": {"lesson_attempts": 2, "lesson_correct": 100, "review_attempts": -1}, "unknown": {}}
        raw["active_review"] = {"milestone": 30, "queue": [{}] * 6, "answers": []}
        raw["reviews"] = [{"milestone": 30, "score": 90, "total": 6}, {"milestone": True, "score": 1, "total": 6}]
        game = normalize_game(raw)
        self.assertIsNone(game["active_review"])
        self.assertEqual(game["reviews"], [])
        self.assertEqual(game["word_stats"]["cat"]["lesson_correct"], 2)
        self.assertEqual(game["word_stats"]["cat"]["review_attempts"], 0)
        self.assertNotIn("unknown", game["word_stats"])

    def test_finished_review_history_and_stats_survive_export_import(self):
        game = learned_game(30)
        complete_review(game, 3)
        restored = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(restored, game)
        self.assertEqual(restored["reviews"][0]["score"], 3)
        self.assertIsNone(pending_review(restored))


if __name__ == "__main__":
    unittest.main()
