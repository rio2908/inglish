import os
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:
    raise unittest.SkipTest("UI checks need pygame")

from game_logic import new_game, normalize_game
import main
from speech import Speech
from words import WORDS
from learning_stats import statistics


class AppTests(unittest.TestCase):
    def setUp(self):
        self.save = patch("main.write_game").start()
        patch("main.load_game", side_effect=new_game).start()
        self.app = main.GameApp()
        self.app.speech.speak = Mock(return_value=True)

    def tearDown(self):
        self.app.speech.shutdown()
        pygame.quit()
        patch.stopall()

    def test_name_input_is_saved_and_can_be_cancelled(self):
        self.app.open_profile()
        self.app.edit_name()
        self.app.name_input = ""
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="Пушок"))
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.game["pet_name"], "Пушок")
        self.save.assert_called()
        self.app.edit_name()
        self.app.name_input = "Другое имя"
        self.app.cancel_name()
        self.assertEqual(self.app.game["pet_name"], "Пушок")

    def test_resume_result_does_not_count_answer_twice(self):
        self.app.start_lesson()
        self.app.intro_done()
        self.app.answer(self.app.word_id)
        saved = normalize_game(self.app.game)
        self.app.game = saved
        self.app.restore_lesson()
        self.assertEqual(self.app.screen, "cards")
        self.assertEqual(self.app.card_phase, "result")
        self.assertEqual(self.app.game["correct_answers"], 1)
        self.app.next_card()
        self.assertEqual(self.app.card_index, 1)
        self.assertEqual(self.app.game["correct_answers"], 1)

    def test_background_saves_active_lesson(self):
        self.app.start_lesson()
        self.save.reset_mock()
        self.app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.save.assert_called_once()
        self.assertEqual(self.app.game["lesson"]["queue"], self.app.queue)

    def test_import_waits_for_confirmation_and_preserves_current_game_on_write_failure(self):
        imported = new_game()
        imported["pet_name"] = "Другой"
        self.app.profile_picker.poll = Mock(return_value=("OK", imported))
        self.app.poll_profile()
        self.assertEqual(self.app.screen, "import")
        self.assertEqual(self.app.game["pet_name"], "Сниффер")
        self.app.cancel_import()
        self.assertEqual(self.app.game["pet_name"], "Сниффер")
        self.app.imported_game = imported
        self.save.side_effect = OSError("disk full")
        self.app.accept_import()
        self.assertEqual(self.app.game["pet_name"], "Сниффер")

    def test_all_screens_render_and_pet_is_on_main_meadow(self):
        for screen in ("home", "profile", "name", "help", "feed", "play", "story"):
            with self.subTest(screen=screen):
                self.app.screen = screen
                self.app.draw()
                self.assertTrue(all(pygame.Rect(0, 0, main.WIDTH, main.HEIGHT).contains(rect)
                                    for rect, _ in self.app.buttons))
        self.app.imported_game = new_game()
        self.app.screen = "import"
        self.app.draw()
        self.app.start_lesson()
        for phase in ("intro", "quiz", "result"):
            self.app.card_phase = phase
            self.app.draw()
        self.app.screen = "home"
        self.app.draw()
        self.assertAlmostEqual(self.app.pet_rect.bottom, 455, delta=3)
        self.assertEqual(self.app.canvas.get_at((39, 300))[:3], main.SKY)

    def test_audio_button_calls_speech(self):
        self.app.start_lesson()
        self.app.speech.speak = Mock(return_value=True)
        self.app.draw()
        self.app.click((709, 409))
        self.app.speech.speak.assert_called_once_with(self.app.word_id)

    def set_pet_stage(self, stage):
        self.app.game = new_game()
        self.app.game["correct_answers"] = 5 if stage else 0
        self.app.game["care"]["joy"] = 0
        learned = {0: 0, 1: 0, 2: 40, 3: 80, 4: 120}[stage]
        self.app.game["cards"] = {
            word["id"]: {"seen": True, "correct_sessions": [1, 2]}
            for word in WORDS[:learned]
        }

    def test_each_growth_stage_opens_and_renders_its_own_game(self):
        for stage in (1, 2, 3, 4):
            with self.subTest(stage=stage):
                self.set_pet_stage(stage)
                self.app.start_play()
                self.assertEqual(self.app.pet_game.stage, stage)
                self.app.draw()
                self.assertEqual(self.app.screen, "play")
                self.assertTrue(all(pygame.Rect(0, 0, main.WIDTH, main.HEIGHT).contains(rect)
                                    for rect, _ in self.app.buttons))
                self.app.leave_play()
                self.assertEqual(self.app.game["care"]["joy"], 0)
        self.set_pet_stage(0)
        self.app.start_play()
        self.assertIsNone(self.app.pet_game)
        self.assertEqual(self.app.screen, "home")

    def test_completed_games_save_joy_without_changing_word_or_garden_progress(self):
        for stage in (1, 2, 3, 4):
            with self.subTest(stage=stage):
                self.set_pet_stage(stage)
                before = normalize_game(self.app.game)
                self.app.start_play()
                activity = self.app.pet_game
                now = 0
                if stage in (1, 2):
                    for _ in range(3):
                        activity.choose(activity.target, now)
                        now = activity.until
                        activity.tick(now)
                elif stage == 3:
                    for _ in range(3):
                        now = activity.show_start + len(activity.sequence) * 900 + 350
                        activity.tick(now)
                        for move in activity.sequence[:]:
                            activity.choose(move, now)
                        activity.tick(activity.until)
                else:
                    for _ in range(3):
                        for tool in range(3):
                            activity.choose(tool, now)
                    activity.tick(activity.until)
                self.assertTrue(activity.done)
                self.save.reset_mock()
                self.app.draw()
                self.assertEqual(self.app.screen, "home")
                self.assertEqual(self.app.game["care"]["joy"], 3)
                self.assertEqual(self.app.game["cards"], before["cards"])
                self.assertEqual(self.app.game["correct_answers"], before["correct_answers"])
                self.assertEqual(self.app.game["garden_plants"], before["garden_plants"])
                self.save.assert_called_once()
                self.app.finish_play()
                self.save.assert_called_once()

    def test_touching_hidden_treat_uses_the_new_game_not_old_ball_hitbox(self):
        self.set_pet_stage(1)
        self.app.start_play()
        target = self.app.pet_game.target
        self.app.draw()
        self.app.click((200 + target * 300, 380))
        self.assertEqual(self.app.pet_game.hits, 1)
        self.assertEqual(self.app.pet_game.phase, "celebrate")

    def test_thirtieth_mastered_word_interrupts_and_then_resumes_the_lesson(self):
        self.app.game = new_game()
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS[:29]:
                main.record_answer(self.app.game, word["id"], True)
        target, following = WORDS[29]["id"], WORDS[30]["id"]
        self.app.game["cards"][target] = {"seen": True, "correct_sessions": [1]}
        self.app.queue = [target, following]
        self.app.screen = "cards"
        self.app.card_index = 0
        self.app.prepare_card()
        self.app.answer(target)
        self.app.next_card()
        self.assertEqual(self.app.screen, "review")
        self.assertEqual(self.app.game["active_review"]["milestone"], 30)
        self.assertEqual(self.app.game["lesson"]["index"], 1)
        before = self.app.game["correct_answers"]
        self.app.draw()
        for word_id in self.app.game["active_review"]["queue"][:]:
            self.app.submit_review(word_id)
            self.app.draw()
            self.app.next_review()
        self.app.draw()
        self.assertEqual(self.app.game["active_review"]["phase"], "summary")
        self.app.close_review()
        self.assertEqual(self.app.screen, "cards")
        self.assertEqual(self.app.word_id, following)
        self.assertEqual(self.app.card_index, 1)
        self.assertEqual(self.app.game["correct_answers"], before)
        self.assertEqual(self.app.game["reviews"][0]["score"], 6)

    def test_review_survives_pause_and_restart_without_recounting_answers(self):
        self.set_pet_stage(2)
        self.app.start_lesson()
        self.assertEqual(self.app.screen, "review")
        first = self.app.game["active_review"]["queue"][0]
        self.app.submit_review(first)
        self.app.pause_review()
        saved = normalize_game(self.app.game)
        with patch("main.load_game", return_value=saved):
            restarted = main.GameApp()
        try:
            self.assertEqual(restarted.screen, "review")
            self.assertEqual(restarted.game["active_review"]["phase"], "feedback")
            restarted.submit_review(first)
            self.assertEqual(statistics(restarted.game)["attempts"], 1)
            restarted.next_review()
            self.assertEqual(len(restarted.game["active_review"]["answers"]), 1)
        finally:
            restarted.speech.shutdown()

    def test_statistics_tabs_and_last_word_page_render(self):
        self.set_pet_stage(4)
        self.app.open_statistics()
        for tab in ("overview", "words", "reviews"):
            self.app.statistics_tab(tab)
            self.app.draw()
            self.assertTrue(all(pygame.Rect(0, 0, main.WIDTH, main.HEIGHT).contains(rect)
                                for rect, _ in self.app.buttons))
        self.app.statistics_tab("words")
        self.app.stats_page = (len(WORDS) - 1) // 8
        self.app.draw()


class SpeechTests(unittest.TestCase):
    def test_android_initialization_and_playback_run_on_ui_thread(self):
        from types import SimpleNamespace
        calls = []
        tts = Mock()
        tts.setLanguage.return_value = 0
        tts.speak.return_value = 0

        def initialize_tts(activity, listener):
            listener.onInit(0)
            return tts

        def ui_thread(function):
            def run(*args):
                calls.append(function.__name__)
                return function(*args)
            return run

        classes = {
            "org.kivy.android.PythonActivity": SimpleNamespace(mActivity="activity"),
            "java.util.Locale": SimpleNamespace(US="en-US"),
            "android.speech.tts.TextToSpeech": initialize_tts,
        }
        modules = {
            "jnius": SimpleNamespace(PythonJavaClass=object, autoclass=lambda name: classes[name],
                                     java_method=lambda signature: lambda function: function),
            "android.runnable": SimpleNamespace(run_on_ui_thread=ui_thread),
        }
        with patch.dict("sys.modules", modules), patch("speech.sys.platform", "android"):
            speech = Speech(Path("missing-audio"))
            self.assertTrue(speech.ready)
            self.assertTrue(speech.speak("hello"))
            self.assertEqual(calls, ["initialize", "speak"])
            tts.setLanguage.assert_called_once_with("en-US")
            tts.speak.assert_called_once_with("hello", 0, None, "sniffer-word")

    def test_android_missing_english_voice_is_reported(self):
        speech = Speech(Path("missing-audio"))
        speech.android = True
        speech.ready = True
        speech.locale = "en-US"
        speech.tts = Mock()
        speech.tts.setLanguage.return_value = -1
        from types import SimpleNamespace
        with patch.dict("sys.modules", {"android.runnable": SimpleNamespace(run_on_ui_thread=lambda fn: fn)}):
            self.assertFalse(speech.speak("hello"))
        self.assertIn("английский голос", speech.error)
        speech.tts.speak.assert_not_called()

    def test_android_queues_word_until_tts_initializes(self):
        speech = Speech(Path("missing-audio"))
        speech.android = True
        self.assertTrue(speech.speak("hello"))
        self.assertEqual(speech.pending, "hello")
        speech.ready = True
        speech.tts = Mock()
        speech._speak_android = Mock()
        speech.tick()
        speech._speak_android.assert_called_once_with("hello")
        self.assertIsNone(speech.pending)


if __name__ == "__main__":
    unittest.main()
