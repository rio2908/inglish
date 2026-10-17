import copy
import random
import unittest

from game_logic import (
    growth_stage, hatch_complete, mastered_count, new_game, normalize_game,
    record_answer, start_session,
)
from game_storage import make_backup_bytes, read_backup_bytes
from learning_stats import pending_review
from words import ALL_WORDS, WORD_BANKS, words_for_species
from learning_fixtures import clear_checkpoints
from assessments import expected_word
from zoo import (
    SPECIES, advance_final_test, answer_final_test, begin_replay, current_species, final_passed,
    growth_complete, normalize_zoo, pet_learned_count, ready_for_zoo, settle_pet, start_final_test, repair_final_test,
)


def pass_exam(game, correct=100):
    exam = start_final_test(game, random.Random(4), retry=True)
    for i, expected in enumerate(exam["queue"][:]):
        chosen = expected if i < correct else next(word["id"] for word in words_for_species(current_species(game)) if word["id"] != expected)
        answer_final_test(game, chosen)
        advance_final_test(game)
    if repair_final_test(game):
        while exam["phase"] != "summary":
            if exam["phase"] == "repair_quiz":
                answer_final_test(game, expected_word(exam))
            else:
                advance_final_test(game)


def grow_current_pet(game, count=150, certify=True):
    for _ in range(2):
        game["session"] += 1
        for word in words_for_species(current_species(game))[:count]:
            record_answer(game, word["id"], True)
            clear_checkpoints(game)
    if count == 150 and certify:
        pass_exam(game)


class ZooTests(unittest.TestCase):
    def test_old_profiles_start_with_sniffer_and_no_unlocked_collection(self):
        game = normalize_game({"correct_answers": 12, "pet_name": "Пушок"})
        self.assertEqual(current_species(game), "sniffer")
        self.assertEqual(game["zoo"]["residents"], [])
        self.assertEqual(game["pet_name"], "Пушок")

    def test_growing_up_at_120_is_not_enough_to_open_the_next_creature(self):
        game = new_game()
        grow_current_pet(game, 120)
        self.assertEqual(growth_stage(game), 4)
        self.assertFalse(ready_for_zoo(game))
        self.assertFalse(settle_pet(game))

    def test_creatures_unlock_in_order_one_per_complete_learning_cycle(self):
        game = new_game()
        for i, (species, _) in enumerate(SPECIES):
            with self.subTest(species=species):
                self.assertEqual(current_species(game), species)
                self.assertFalse(ready_for_zoo(game))
                grow_current_pet(game)
                self.assertEqual(pet_learned_count(game), 150)
                self.assertTrue(ready_for_zoo(game))
                self.assertTrue(settle_pet(game))
                self.assertEqual([record["species"] for record in game["zoo"]["residents"]], [item[0] for item in SPECIES[:i + 1]])
                self.assertFalse(ready_for_zoo(game))
                self.assertFalse(settle_pet(game))
                game = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(len(game["zoo"]["residents"]), 6)
        self.assertEqual(current_species(game), "allay")
        self.assertEqual(growth_stage(game), 4)

    def test_new_pet_gets_its_own_progress_without_losing_vocabulary_or_stats(self):
        game = new_game()
        grow_current_pet(game)
        game["garden_plants"] = 10
        game["pet_name"] = "Пушок"
        before = copy.deepcopy(game)
        self.assertTrue(settle_pet(game))
        self.assertEqual(game["zoo"]["residents"][0], {"species": "sniffer", "name": "Пушок"})
        self.assertEqual(game["pet_name"], "Аксолотль")
        self.assertEqual(mastered_count(game), 150)
        self.assertEqual(pet_learned_count(game), 0)
        self.assertEqual(growth_stage(game), 0)
        self.assertFalse(hatch_complete(game))
        for key in ("cards", "word_stats", "learned_order", "correct_answers", "garden_plants", "reviews", "repeat_words"):
            self.assertEqual(game[key], before[key])
        game["session"] += 1
        for word in words_for_species("axolotl")[:5]:
            record_answer(game, word["id"], True)
        self.assertFalse(hatch_complete(game))
        self.assertEqual(growth_stage(game), 0)
        self.assertEqual(pet_learned_count(game), 0)
        self.assertEqual(mastered_count(game), 150)
        grow_current_pet(game, 30)
        self.assertTrue(hatch_complete(game))
        self.assertEqual(growth_stage(game), 1)

    def test_new_pet_requires_recall_in_two_distinct_sessions(self):
        game = new_game()
        grow_current_pet(game)
        settle_pet(game)
        game["session"] += 1
        self.assertFalse(record_answer(game, "one", True))
        self.assertFalse(record_answer(game, "one", True))
        self.assertEqual(pet_learned_count(game), 0)
        game["session"] += 1
        self.assertTrue(record_answer(game, "one", True))
        self.assertEqual(pet_learned_count(game), 1)
        self.assertFalse(record_answer(game, "two", False))
        self.assertEqual(game["zoo"]["pet_correct_answers"], 3)

    def test_new_pet_growth_uses_its_own_thirty_word_thresholds(self):
        base = new_game()
        grow_current_pet(base)
        settle_pet(base)
        for count, stage in ((29, 0), (30, 1), (59, 1), (60, 2), (89, 2), (90, 3), (119, 3), (120, 4), (150, 4)):
            with self.subTest(count=count):
                game = copy.deepcopy(base)
                grow_current_pet(game, count)
                self.assertEqual(mastered_count(game), 150 + count)
                self.assertEqual(pet_learned_count(game), count)
                self.assertEqual(growth_stage(game), stage)
                self.assertEqual(ready_for_zoo(game), count == 150)

    def test_repeat_scheduler_finishes_remaining_words_instead_of_repeating_completed_ones(self):
        game = new_game()
        grow_current_pet(game)
        settle_pet(game)
        grow_current_pet(game, 149)
        queue = start_session(game, random.Random(3))
        self.assertIn(words_for_species("axolotl")[-1]["id"], queue)
        self.assertTrue(all(word_id in {word["id"] for word in words_for_species("axolotl")} for word_id in queue))

    def test_cannot_replace_a_pet_during_a_suspended_lesson_or_review(self):
        game = new_game()
        grow_current_pet(game)
        for key in ("lesson", "active_review"):
            game[key] = {"pending": True}
            self.assertFalse(settle_pet(game))
            game[key] = None
        self.assertTrue(settle_pet(game))

    def test_partial_growth_and_collection_survive_export_and_reload(self):
        game = new_game()
        grow_current_pet(game)
        settle_pet(game)
        grow_current_pet(game, 55)
        game["pet_name"] = "Розочка"
        restored = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(restored, game)
        self.assertEqual(growth_stage(restored), 1)
        self.assertEqual(pet_learned_count(restored), 55)
        self.assertEqual(len(restored["zoo"]["residents"]), 1)

    def test_each_creature_gets_its_own_three_checks_without_erasing_earlier_results(self):
        game = new_game()
        grow_current_pet(game)
        first_results = copy.deepcopy(game["reviews"])
        self.assertTrue(settle_pet(game))
        self.assertIsNone(pending_review(game))
        grow_current_pet(game, 50)
        restored = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(restored, game)
        self.assertEqual(len(restored["reviews"]), 4)
        self.assertNotIn("species", restored["reviews"][0])
        self.assertEqual([item for item in restored["reviews"] if item.get("species", "sniffer") == "sniffer"], first_results)
        self.assertEqual(next(item for item in restored["reviews"] if item.get("species") == "axolotl")["milestone"], 50)
        self.assertEqual(pet_learned_count(restored), 50)

    def test_bad_collection_cannot_skip_directly_to_the_last_creature(self):
        zoo = normalize_zoo({"active": "allay", "residents": [{"species": "allay", "name": "oops"}],
                             "pet_correct_answers": -1, "pet_cards": {"unknown": {}, "cat": {"correct_sessions": [True, -2, 4, 4]}}})
        self.assertEqual(zoo["active"], "sniffer")
        self.assertEqual(zoo["residents"], [])
        self.assertEqual(zoo["pet_correct_answers"], 0)
        self.assertEqual(zoo["pet_cards"], {})

    def test_all_six_pets_have_different_sets_of_150_words(self):
        self.assertEqual(len(ALL_WORDS), 900)
        seen = set()
        for bank in WORD_BANKS.values():
            self.assertEqual(len(bank), 150)
            ids = {word["id"] for word in bank}
            self.assertFalse(seen & ids)
            seen |= ids

    def test_final_exam_blocks_34_out_of_50_but_accepts_35_after_corrections(self):
        game = new_game()
        grow_current_pet(game, certify=False)
        self.assertTrue(growth_complete(game))
        self.assertFalse(ready_for_zoo(game))
        self.assertFalse(settle_pet(game))
        before = game["correct_answers"]
        pass_exam(game, 34)
        self.assertFalse(final_passed(game))
        self.assertFalse(settle_pet(game))
        self.assertEqual(game["correct_answers"], before)
        self.assertEqual(pet_learned_count(game), 150)
        pass_exam(game, 35)
        self.assertTrue(final_passed(game))
        self.assertEqual([item["score"] for item in game["zoo"]["exam_history"]], [34, 35])
        self.assertTrue(settle_pet(game))
        self.assertEqual(current_species(game), "axolotl")

    def test_final_exam_resumes_without_duplicate_answer_statistics(self):
        game = new_game()
        grow_current_pet(game, certify=False)
        exam = start_final_test(game)
        first = exam["queue"][0]
        self.assertTrue(answer_final_test(game, first))
        self.assertFalse(answer_final_test(game, first))
        restored = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(restored, game)
        self.assertFalse(answer_final_test(restored, first))
        advance_final_test(restored)
        self.assertEqual(len(restored["zoo"]["exam"]["answers"]), 1)

    def test_replay_keeps_old_friend_and_restores_suspended_pet(self):
        game = new_game()
        grow_current_pet(game)
        settle_pet(game)
        grow_current_pet(game, 40)
        game["pet_name"] = "Розочка"
        before = copy.deepcopy(game)
        self.assertTrue(begin_replay(game, 0))
        self.assertEqual(current_species(game), "sniffer")
        self.assertTrue(game["zoo"]["replay"])
        self.assertEqual(pet_learned_count(game), 0)
        self.assertFalse(hatch_complete(game))
        self.assertEqual(mastered_count(game), 190)
        self.assertEqual(len(game["zoo"]["residents"]), 1)
        self.assertFalse(begin_replay(game, 0))
        game = read_backup_bytes(make_backup_bytes(game))
        self.assertTrue(game["zoo"]["replay"])
        grow_current_pet(game)
        self.assertTrue(settle_pet(game))
        self.assertEqual(current_species(game), "axolotl")
        self.assertFalse(game["zoo"]["replay"])
        self.assertEqual(game["pet_name"], "Розочка")
        self.assertEqual(pet_learned_count(game), 40)
        self.assertEqual(game["care"], before["care"])
        self.assertEqual(game["zoo"]["pet_cards"], before["zoo"]["pet_cards"])
        self.assertEqual(game["zoo"]["residents"][0]["grown"], 2)
        self.assertEqual(mastered_count(game), 190)
        restored = read_backup_bytes(make_backup_bytes(game))
        self.assertEqual(restored, game)

    def test_replaying_an_old_pet_cannot_bypass_a_failed_unlock_exam(self):
        game = new_game()
        grow_current_pet(game)
        settle_pet(game)
        grow_current_pet(game, certify=False)
        pass_exam(game, 6)
        failed_exam = copy.deepcopy(game["zoo"]["exam"])
        self.assertTrue(begin_replay(game, 0))
        grow_current_pet(game)
        self.assertTrue(settle_pet(game))
        self.assertEqual(current_species(game), "axolotl")
        self.assertEqual(game["zoo"]["exam"], failed_exam)
        self.assertFalse(ready_for_zoo(game))
        self.assertFalse(settle_pet(game))
        self.assertEqual(len(game["zoo"]["residents"]), 1)


if __name__ == "__main__":
    unittest.main()
