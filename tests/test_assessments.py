import copy
import random
import unittest

from assessments import corrected, expected_word, score
from game_logic import lesson_retry, new_game, normalize_game, record_answer, start_session
from learning_stats import (advance_review, answer_review, pending_review, repair_review,
                            review_passed, retry_review, start_review)
from words import WORD_BY_ID, words_for_species
from zoo import (SPECIES, advance_final_test, answer_final_test, final_passed, final_size,
                 growth_complete, pass_mark, repair_final_test, settle_pet, start_final_test)


def learned_game(count=150, species="sniffer"):
    game = new_game()
    index = [key for key, _ in SPECIES].index(species)
    game["zoo"]["residents"] = [{"species": key, "name": name} for key, name in SPECIES[:index]]
    game["zoo"]["active"] = species
    game["session"] = 2
    game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in words_for_species(species)[:count]}
    return normalize_game(game)


def clear_checkpoints(game):
    while pending_review(game) is not None:
        review = start_review(game, random.Random(8))
        for word in review["queue"][:]:
            answer_review(game, word)
            advance_review(game)
        game["active_review"] = None


class AssessmentTests(unittest.TestCase):
    def test_model_cannot_unlock_by_repeating_one_word_50_times(self):
        game = learned_game()
        clear_checkpoints(game)
        game["zoo"]["exam"] = {"queue": ["cat"] * 50, "answers": ["cat"] * 50, "phase": "summary"}
        self.assertFalse(final_passed(game))
        self.assertFalse(settle_pet(game))

    def test_one_below_pass_mark_never_unlocks_any_species_even_after_repairs(self):
        for species, _ in SPECIES:
            with self.subTest(species=species):
                game = learned_game(species=species)
                clear_checkpoints(game)
                exam = start_final_test(game)
                mark = pass_mark(final_size(species))
                for i, word in enumerate(exam["queue"][:]):
                    answer_final_test(game, word if i < mark - 1 else next(item for item in exam["queue"] if item != word))
                    advance_final_test(game)
                self.repair(game, final=True)
                self.assertEqual(score(exam), mark - 1)
                self.assertFalse(final_passed(game))
                self.assertFalse(settle_pet(game))

    def do_review(self, game, correct):
        review = start_review(game, random.Random(3))
        for i, word in enumerate(review["queue"][:]):
            wrong = next(item for item in review["queue"] if item != word)
            answer_review(game, word if i < correct else wrong)
            advance_review(game)
        return review

    def repair(self, game, final=False):
        self.assertTrue(repair_final_test(game) if final else repair_review(game))
        test = game["zoo"]["exam"] if final else game["active_review"]
        for _ in range(500):
            if test["phase"] == "summary":
                return
            if test["phase"] == "repair_quiz":
                (answer_final_test if final else answer_review)(game, expected_word(test))
            else:
                (advance_final_test if final else advance_review)(game)
        self.fail("Corrections did not finish")

    def test_checkpoint_blocks_model_until_pass_and_corrections_without_changing_score(self):
        game = learned_game(50)
        self.assertEqual(pending_review(game), 50)
        self.assertEqual(start_session(game), [])
        with self.assertRaises(ValueError):
            record_answer(game, words_for_species("sniffer")[51]["id"], True)
        review = self.do_review(game, 16)
        self.assertFalse(review_passed(review))
        self.assertEqual(pending_review(game), 50)
        self.assertIsNone(retry_review(game))
        before = copy.deepcopy(game["cards"])
        self.repair(game)
        self.assertEqual(score(review), 16)
        self.assertTrue(review_passed(review))
        self.assertIsNone(pending_review(game))
        self.assertEqual(game["cards"], before)
        self.assertEqual(game["reviews"][0]["score"], 16)
        self.assertTrue(game["reviews"][0]["cleared"])

    def test_failed_checkpoint_needs_a_new_attempt_after_corrections(self):
        game = learned_game(50)
        review = self.do_review(game, 12)
        self.repair(game)
        self.assertTrue(corrected(review))
        self.assertFalse(review_passed(review))
        self.assertEqual(pending_review(game), 50)
        self.assertIsNotNone(retry_review(game))
        self.assertEqual(game["active_review"]["answers"], [])
        self.assertEqual(game["active_review"]["attempt"], 2)

    def test_three_checkpoints_and_exam_boundaries_for_every_species(self):
        for species, _ in SPECIES:
            with self.subTest(species=species):
                game = learned_game(species=species)
                self.assertFalse(growth_complete(game))
                clear_checkpoints(game)
                self.assertEqual([item["milestone"] for item in game["reviews"]], [50, 100, 150])
                self.assertTrue(growth_complete(game))
                exam = start_final_test(game, random.Random(1))
                total = final_size(species)
                self.assertEqual(len(set(exam["queue"])), total)
                self.assertEqual([sum(WORD_BY_ID[item]["chapter"] == chapter for item in exam["queue"])
                                  for chapter in range(10)], [total // 10] * 10)
                for i, word in enumerate(exam["queue"][:]):
                    answer_final_test(game, word if i < pass_mark(total) else next(item for item in exam["queue"] if item != word))
                    advance_final_test(game)
                self.assertFalse(final_passed(game))
                self.assertFalse(settle_pet(game))
                self.repair(game, final=True)
                self.assertTrue(final_passed(game))
                self.assertTrue(settle_pet(game))

    def test_repair_survives_normalize_in_every_phase_and_cannot_recount_score(self):
        game = learned_game(50)
        self.do_review(game, 14)
        repair_review(game)
        for _ in range(50):
            game = normalize_game(game)
            test = game["active_review"]
            self.assertEqual(score(test), 14)
            if test["phase"] == "summary":
                break
            if test["phase"] == "repair_quiz":
                answer_review(game, expected_word(test))
                self.assertFalse(answer_review(game, expected_word(test)))
            else:
                advance_review(game)
        self.assertTrue(review_passed(game["active_review"]))
        self.assertEqual(len(game["reviews"]), 1)

    def test_failed_repair_requeues_after_two_other_questions(self):
        game = learned_game(50)
        review = self.do_review(game, 19)
        repair_review(game)
        word = expected_word(review)
        advance_review(game)
        for _ in range(2):
            answer_review(game, expected_word(review))
            advance_review(game)
        self.assertEqual(expected_word(review), word)
        answer_review(game, next(item for item in review["queue"] if item != word))
        advance_review(game)
        self.assertNotIn(word, review["corrections"]["queue"][:2])
        self.assertEqual(review["corrections"]["queue"][2], word)

    def test_old_checks_do_not_unlock_new_gates_and_old_exam_retains_answers(self):
        game = learned_game()
        pool = [word["id"] for word in words_for_species("sniffer")]
        game["reviews"] = [{"milestone": n, "score": 6, "total": 6} for n in (30, 60, 90, 120, 150)]
        game["zoo"]["exam"] = {"queue": pool[:10], "answers": pool[:10], "phase": "summary"}
        restored = normalize_game(game)
        self.assertEqual(len(restored["reviews"]), 5)
        self.assertEqual(restored["zoo"]["exam"]["answers"], pool[:10])
        self.assertEqual(len(restored["zoo"]["exam"]["queue"]), 50)
        self.assertFalse(final_passed(restored))
        self.assertEqual(pending_review(restored), 50)
        self.assertEqual(normalize_game(restored), restored)

    def test_lesson_error_returns_after_two_other_cards_in_same_round(self):
        game = new_game()
        queue = start_session(game, random.Random(1))
        game["cards"][queue[0]] = {"seen": True, "correct_sessions": []}
        result = lesson_retry(game, queue, 0, queue[0])
        self.assertEqual(result[3], queue[0])
        record_answer(game, queue[0], False)
        record_answer(game, queue[0], True)
        self.assertEqual(game["cards"][queue[0]]["correct_sessions"], [1])

    def test_mastered_errors_get_next_round_priority_without_starving_other_words(self):
        game = learned_game(5)
        errors = [word["id"] for word in words_for_species("sniffer")[:5]]
        for word in errors:
            record_answer(game, word, False)
            record_answer(game, word, True)
        for word in words_for_species("sniffer")[5:15]:
            game["cards"][word["id"]] = {"seen": True, "correct_sessions": [1]}
        queue = start_session(game, random.Random(1))
        self.assertEqual(set(queue[:5]), set(errors))
        game = normalize_game(game)
        queue = start_session(game, random.Random(1))
        self.assertTrue(set(queue) & {word["id"] for word in words_for_species("sniffer")[5:15]})
        self.assertFalse(set(queue[:5]) & set(errors))
        self.assertEqual(set(game["repeat_words"]), set(errors))

    def test_retry_removes_duplicate_early_copies_before_scheduling_a_delay(self):
        game = new_game()
        game["cards"] = {word: {"seen": True, "correct_sessions": []} for word in ("cat", "dog", "tree")}
        queue = lesson_retry(game, ["cat", "cat", "dog", "cat", "tree"], 0, "cat")
        self.assertNotIn("cat", queue[1:3])
        self.assertEqual(queue[3], "cat")
