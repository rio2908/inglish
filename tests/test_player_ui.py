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
import main


class PlayerUITests(unittest.TestCase):
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
