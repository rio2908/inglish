import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
except ImportError:
    raise unittest.SkipTest("Player UI checks need pygame")

from game_logic import new_game
from player_profiles import PlayerStore
from words import WORDS
from game_storage import make_backup_bytes, read_player_backup_bytes
import main


class PlayerUITests(unittest.TestCase):
    def test_paused_lesson_is_in_the_export_and_resumes_instead_of_starting_a_new_round(self):
        self.register("Анна")
        self.app.start_lesson()
        self.app.intro_done()
        self.app.answer(self.app.word_id)
        expected_queue = self.app.queue[:]
        expected_session = self.app.game["session"]
        expected_word = self.app.word_id
        expected_care = self.app.game["care"].copy()
        self.app.leave_cards()
        self.app.open_profile()
        copied = read_player_backup_bytes(make_backup_bytes(self.app.game, self.store.metadata(self.app.player_id)))
        self.assertIsNotNone(copied["game"]["lesson"])
        self.assertEqual(copied["game"]["lesson"]["queue"], expected_queue)
        self.assertEqual(copied["game"]["lesson"]["phase"], "result")
        self.app.screen = "home"
        self.app.start_lesson()
        self.assertEqual(self.app.game["session"], expected_session)
        self.assertEqual(self.app.word_id, expected_word)
        self.assertEqual(self.app.card_phase, "result")
        self.assertEqual(self.app.game["care"], expected_care)

    def test_second_picker_request_does_not_reassign_the_owner_of_a_busy_transfer(self):
        anna = self.register("Анна")
        boris = self.store.create_player("Борис")
        self.app.profile_picker.pending = True
        self.app.profile_transfer_started = True
        self.app.profile_transfer_owner = anna
        self.app.open_login()
        self.app.enter_player(boris)
        self.app.transfer_profile(False)
        self.assertTrue(self.app.profile_transfer_started)
        self.assertEqual(self.app.profile_transfer_owner, anna)

    def test_pausing_a_hatched_pets_round_does_not_decrease_needs_or_count_as_a_new_round(self):
        self.register("Анна")
        self.app.game["session"] = 2
        self.app.game["correct_answers"] = 60
        self.app.game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in WORDS[:30]}
        self.app.game["reviews"] = [{"milestone": 30, "score": 6, "total": 6}]
        self.app.start_lesson()
        self.app.intro_done()
        self.app.answer(self.app.word_id)
        session = self.app.game["session"]
        answers = self.app.game["correct_answers"]
        care = self.app.game["care"].copy()
        self.app.leave_cards()
        self.app.start_lesson()
        self.assertEqual(self.app.game["session"], session)
        self.assertEqual(self.app.game["care"], care)
        self.assertEqual(self.app.card_phase, "result")
        self.app.answer(self.app.word_id)
        self.assertEqual(self.app.game["correct_answers"], answers)
        self.app.next_card()
        while self.app.screen == "cards":
            if self.app.card_phase == "intro":
                self.app.intro_done()
            elif self.app.card_phase == "quiz":
                self.app.answer(self.app.word_id)
            else:
                self.app.next_card()
        self.assertIsNone(self.app.game["lesson"])
        self.assertEqual(self.app.game["care"]["food"], care["food"] - 1)
        self.assertEqual(self.app.game["care"]["joy"], care["joy"] - 1)

    def test_stale_autosave_does_not_erase_newer_progress_and_can_reload_it(self):
        identity = self.register("Анна")
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS[:4]:
                main.record_answer(self.app.game, word["id"], True)
        self.app.persist()
        other_store = PlayerStore(self.path)
        updated = other_store.load_game(identity)
        for session in (3, 4):
            updated["session"] = session
            for word in WORDS[4:8]:
                main.record_answer(updated, word["id"], True)
        other_store.save_game(identity, updated)
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
        self.assertTrue(self.app.save_conflict)
        self.assertFalse(self.app.persist())
        self.assertTrue(self.app.save_conflict)
        with patch.object(self.app, "button", wraps=self.app.button) as buttons:
            self.app.draw()
            self.assertEqual([call.args[1] for call in buttons.call_args_list], ["ВЫГРУЗИТЬ МОЮ КОПИЮ", "ЗАГРУЗИТЬ СВЕЖЕЕ"])
        self.assertEqual(main.mastered_count(self.store.load_game(identity)), 8)
        self.app.enter_player(identity)
        self.assertFalse(self.app.save_conflict)
        self.assertEqual(main.mastered_count(self.app.game), 8)

    def test_two_app_instances_using_the_same_store_keep_independent_revision_tokens(self):
        identity = self.register("Анна")
        other = main.GameApp(profile_store=self.store)
        try:
            other.enter_player(identity)
            other.game["correct_answers"] = 18
            self.assertTrue(other.persist())
            self.assertFalse(self.app.persist())
            self.assertEqual(self.store.load_game(identity)["correct_answers"], 18)
        finally:
            other.speech.shutdown()

    def test_in_memory_profile_can_still_be_exported_if_private_storage_is_unreadable(self):
        identity = self.register("Анна")
        self.app.game["pet_name"] = "Листик"
        self.path.write_text("broken JSON", encoding="utf-8")
        with patch.object(self.app.profile_picker, "start", return_value=True) as start:
            self.app.transfer_profile(True)
        start.assert_called_once()
        self.assertEqual(start.call_args.args[1]["pet_name"], "Листик")
        self.assertEqual(start.call_args.args[2], {"id": identity, "name": "Анна"})
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken JSON")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "players.json"
        self.store = PlayerStore(self.path)
        self.app = main.GameApp(profile_store=self.store)
        self.app.speech.speak = Mock(return_value=True)

    def tearDown(self):
        self.app.speech.shutdown()
        pygame.quit()
        self.directory.cleanup()

    def register(self, name):
        self.app.registration_input = name
        self.app.submit_registration()
        return self.app.player_id

    def test_registration_and_switching_preserve_only_each_players_state(self):
        self.assertEqual(self.app.screen, "register")
        self.assertIsNone(self.app.player_id)
        self.app.draw()
        anna = self.register("Анна")
        self.assertEqual(self.app.screen, "home")
        self.app.game["pet_name"] = "Моховичок"
        self.app.game["care"]["food"] = 1
        self.app.start_lesson()
        word = self.app.word_id
        self.app.intro_done()
        self.app.answer(word)
        self.app.open_login()
        self.assertIsNone(self.app.player_id)
        self.assertEqual(self.app.game, new_game())
        self.app.draw()
        self.app.open_registration()
        boris = self.register("Борис")
        self.assertNotEqual(anna, boris)
        self.assertEqual(self.app.game, new_game())
        self.assertIsNone(self.app.word_id)
        self.assertEqual(self.app.queue, [])
        self.assertEqual(self.app.game["care"]["food"], 3)
        self.app.game["pet_name"] = "Росток"
        self.app.open_login()
        self.app.enter_player(anna)
        self.assertEqual(self.app.game["pet_name"], "Моховичок")
        self.assertEqual(self.app.game["care"]["food"], 1)
        self.assertEqual(self.app.screen, "cards")
        self.assertEqual(self.app.word_id, word)
        self.assertEqual(self.app.card_phase, "result")
        self.assertEqual(self.store.load_game(boris)["pet_name"], "Росток")

    def test_launch_requires_selection_even_when_a_last_player_exists(self):
        anna = self.register("Анна")
        self.app.persist()
        reopened = main.GameApp(profile_store=self.store)
        try:
            self.assertEqual(reopened.screen, "login")
            self.assertIsNone(reopened.player_id)
            self.assertEqual(reopened.profile_cache[0]["id"], anna)
            before = self.path.read_bytes()
            reopened.persist()
            self.assertEqual(self.path.read_bytes(), before)
        finally:
            reopened.speech.shutdown()

    def test_duplicate_registration_and_player_rename_do_not_change_pet_names(self):
        anna = self.register("Анна")
        self.app.edit_player_name()
        self.app.name_input = "Аня"
        self.app.accept_name()
        self.assertEqual(self.store.metadata(anna)["name"], "Аня")
        self.assertEqual(self.app.game["pet_name"], "Сниффер")
        self.app.open_login()
        self.app.open_registration()
        self.register("аня")
        self.assertEqual(self.app.screen, "register")
        self.assertEqual(len(self.store.list_players()), 1)
        self.assertTrue(self.app.login_notice)

    def test_failed_save_prevents_switching_away_from_unsaved_progress(self):
        anna = self.register("Анна")
        self.app.open_profile()
        with patch.object(self.store, "save_game", side_effect=OSError("disk full")):
            self.app.open_login()
        self.assertEqual(self.app.player_id, anna)
        self.assertEqual(self.app.screen, "profile")

    def test_legacy_backup_from_login_asks_for_name_and_becomes_a_separate_player(self):
        self.app.open_login()
        old = new_game()
        old["pet_name"] = "Пушок"
        old["correct_answers"] = 31
        self.app.imported_game = old
        self.app.imported_player = None
        self.app.accept_import()
        self.assertEqual(self.app.screen, "register")
        self.register("Вика")
        self.assertEqual(self.app.player_name, "Вика")
        self.assertEqual(self.app.game["pet_name"], "Пушок")
        self.assertEqual(self.app.game["correct_answers"], 31)

    def test_late_import_result_cannot_be_applied_to_another_selected_player(self):
        anna = self.register("Анна")
        boris = self.store.create_player("Борис")
        self.app.profile_transfer_started = True
        self.app.profile_transfer_owner = anna
        self.app.open_login()
        self.app.enter_player(boris)
        incoming = new_game()
        incoming["pet_name"] = "Не для Бориса"
        self.app.profile_picker.poll = Mock(return_value=("OK", {"player": None, "game": incoming}))
        self.app.poll_profile()
        self.assertEqual(self.app.game["pet_name"], "Сниффер")
        self.assertEqual(self.app.screen, "home")

    def test_growth_congratulation_survives_switching_and_resumes_the_same_lesson(self):
        anna = self.register("Анна")
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS[:29]:
                main.record_answer(self.app.game, word["id"], True)
        target = WORDS[29]["id"]
        self.app.game["cards"][target] = {"seen": True, "correct_sessions": [1]}
        self.app.queue = [target, WORDS[30]["id"]]
        self.app.card_index = 0
        self.app.screen = "cards"
        self.app.prepare_card()
        self.app.answer(target)
        self.assertEqual(self.app.screen, "growth")
        self.app.draw()
        self.app.open_login()
        self.app.open_registration()
        boris = self.register("Борис")
        self.assertIsNone(self.app.game["growth_notice"])
        self.app.open_login()
        self.app.enter_player(anna)
        self.assertEqual(self.app.screen, "growth")
        self.assertEqual(self.app.game["growth_notice"]["after"], 1)
        self.app.acknowledge_growth()
        self.assertEqual(self.app.screen, "cards")
        self.assertEqual(self.app.card_phase, "result")
        self.assertEqual(self.app.word_id, target)
        self.assertIsNone(self.store.load_game(anna)["growth_notice"])
        self.assertIsNone(self.store.load_game(boris)["growth_notice"])

    def test_help_pages_return_to_registration_without_losing_the_name(self):
        from instructions import HELP_PAGES
        self.app.registration_input = "Анна"
        self.app.open_help()
        self.assertEqual(self.app.screen, "help")
        for page in range(len(HELP_PAGES)):
            self.app.help_page = page
            self.app.draw()
            self.assertTrue(all(pygame.Rect(0, 0, 1000, 600).contains(rect) for rect, _ in self.app.buttons))
        self.app.close_help()
        self.assertEqual(self.app.screen, "register")
        self.assertEqual(self.app.registration_input, "Анна")
        self.assertFalse(self.path.exists())

    def test_dictionary_has_only_selected_players_learned_words(self):
        from vocabulary import learned_vocabulary
        anna = self.register("Анна")
        self.app.game["cards"]["cat"] = {"seen": True, "correct_sessions": [1, 2]}
        self.app.open_login()
        self.app.open_registration()
        self.register("Борис")
        self.app.open_dictionary()
        self.assertEqual(learned_vocabulary(self.app.game), [])
        self.app.draw()
        self.app.dictionary_query = "cat"
        self.app.open_login()
        self.app.enter_player(anna)
        self.assertEqual(self.app.dictionary_query, "")
        self.app.open_dictionary()
        self.assertEqual([word["id"] for word in learned_vocabulary(self.app.game)], ["cat"])


if __name__ == "__main__":
    unittest.main()
