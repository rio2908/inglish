import os
from pathlib import Path
import unittest
import tempfile
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
from player_profiles import PlayerStore
from zoo import SPECIES, advance_final_test, answer_final_test, current_species, pet_learned_count, start_final_test
from vocabulary import learned_vocabulary
import copy
from learning_fixtures import clear_checkpoints
from assessments import expected_word


class AppTests(unittest.TestCase):
    def test_exit_saves_paused_lesson_and_requires_confirmation(self):
        self.app.start_lesson()
        self.app.intro_done()
        expected = self.app.word_id
        self.app.request_exit()
        self.assertTrue(self.app.running)
        self.assertEqual(self.app.screen, "exit_confirm")
        self.app.draw()
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.app.screen, "cards")
        self.app.request_exit()
        self.app.confirm_exit()
        self.assertFalse(self.app.running)
        self.assertEqual(self.store.load_game(self.identity)["lesson"]["phase"], "quiz")
        self.assertEqual(self.store.load_game(self.identity)["lesson"]["queue"][0], expected)

    def test_failed_save_blocks_exit_and_keeps_in_memory_progress(self):
        self.app.game["pet_name"] = "Не терять"
        with patch.object(self.store, "save_game", side_effect=OSError("disk full")):
            self.app.request_exit()
        self.assertTrue(self.app.running)
        self.assertNotEqual(self.app.screen, "exit_confirm")
        self.assertEqual(self.app.game["pet_name"], "Не терять")

    def test_browser_exit_shows_saved_message_instead_of_trying_to_close_tab(self):
        self.app.request_exit()
        with patch("main.sys.platform", "emscripten"):
            self.app.confirm_exit()
        self.assertEqual(self.app.screen, "exited")
        self.assertFalse(self.app.running)
        self.app.draw()

    def test_android_back_in_garden_opens_exit_confirmation(self):
        self.app.screen = "home"
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_AC_BACK))
        self.assertEqual(self.app.screen, "exit_confirm")

    def test_second_window_close_does_not_replace_exit_cancel_destination(self):
        self.app.screen = "home"
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.app.handle_event(pygame.event.Event(pygame.QUIT))
        self.assertEqual(self.app.exit_return, "home")

    def test_small_text_is_not_rendered_below_accessible_minimum(self):
        with patch("pygame.font.Font", wraps=pygame.font.Font) as fonts:
            main.text(self.app.canvas, "Нужен уход", 16, (500, 300), main.RED)
        self.assertTrue(all(call.args[1] >= main.MIN_TEXT_SIZE for call in fonts.call_args_list))

    def test_audio_error_is_a_readable_modal_without_clickthrough_to_pet(self):
        self.set_pet_stage(1)
        self.app.screen = "home"
        self.app.audio_notice = "Не удалось озвучить слово. Попробуй ещё раз."
        self.app.audio_notice_until = pygame.time.get_ticks() / 1000 + 10
        with patch.object(self.app, "button", wraps=self.app.button) as buttons:
            self.app.draw()
        self.assertEqual(buttons.call_args_list[-1].args[1], "ПОНЯТНО")
        self.assertEqual(len(self.app.buttons), 1)
        self.app.click((400, 300))
        self.assertEqual(self.app.hearts.particles, [])

    def certify_pet(self):
        clear_checkpoints(self.app.game)
        exam = start_final_test(self.app.game)
        for expected in exam["queue"][:]:
            answer_final_test(self.app.game, expected)
            advance_final_test(self.app.game)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = PlayerStore(Path(self.directory.name) / "players.json")
        self.identity = self.store.create_player("Тестовый игрок")
        self.app = main.GameApp(profile_store=self.store)
        self.app.enter_player(self.identity)
        self.save = patch.object(self.store, "save_game", wraps=self.store.save_game).start()
        self.app.speech.speak = Mock(return_value=True)

    def tearDown(self):
        self.app.speech.shutdown()
        pygame.quit()
        patch.stopall()
        self.directory.cleanup()

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

    def test_successful_audio_retry_clears_the_previous_error_message(self):
        self.app.speech.speak = Mock(side_effect=(False, True))
        self.app.speech.error = "Не удалось озвучить слово"
        self.app.play_audio("cat")
        self.assertTrue(self.app.audio_notice)
        self.app.play_audio("cat")
        self.assertEqual(self.app.audio_notice, "")
        self.assertEqual(self.app.audio_notice_until, 0)

    def set_pet_stage(self, stage):
        self.app.game = new_game()
        self.app.game["session"] = 2 if stage else 0
        self.app.game["correct_answers"] = 5 if stage else 0
        self.app.game["care"]["joy"] = 0
        learned = {0: 0, 1: 30, 2: 60, 3: 90, 4: 120}[stage]
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

    def test_fiftieth_mastered_word_interrupts_and_then_resumes_the_lesson(self):
        self.app.game = new_game()
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS[:49]:
                main.record_answer(self.app.game, word["id"], True)
        self.app.game["growth_notice"] = None
        target, following = WORDS[49]["id"], WORDS[50]["id"]
        self.app.game["cards"][target] = {"seen": True, "correct_sessions": [1]}
        self.app.queue = [target, following]
        self.app.screen = "cards"
        self.app.card_index = 0
        self.app.prepare_card()
        self.app.answer(target)
        self.app.next_card()
        self.assertEqual(self.app.screen, "review")
        self.assertEqual(self.app.game["active_review"]["milestone"], 50)
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
        self.assertEqual(self.app.game["reviews"][0]["score"], 20)

    def test_review_survives_pause_and_restart_without_recounting_answers(self):
        self.set_pet_stage(2)
        self.app.start_lesson()
        self.assertEqual(self.app.screen, "review")
        first = self.app.game["active_review"]["queue"][0]
        self.app.submit_review(first)
        self.app.pause_review()
        saved = normalize_game(self.app.game)
        self.store.save_game(self.identity, saved)
        restarted = main.GameApp(profile_store=self.store)
        restarted.enter_player(self.identity)
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

    def test_tapping_pet_emits_pixel_hearts_and_does_not_change_progress(self):
        self.set_pet_stage(1)
        self.app.screen = "home"
        before = normalize_game(self.app.game)
        with patch("pygame.time.get_ticks", return_value=1000):
            self.app.draw()
            self.app.click(self.app.pet_rect.center)
        self.assertEqual(len(self.app.hearts.particles), 6)
        with patch("pygame.time.get_ticks", return_value=1500):
            self.app.draw()
        self.assertEqual(self.app.pet_behavior.update(1, 1.5).action, "happy")
        self.assertEqual(self.app.game["care"], before["care"])
        self.assertEqual(self.app.game["correct_answers"], before["correct_answers"])
        self.assertEqual(self.app.game["cards"], before["cards"])
        self.assertEqual(self.app.hearts.frame(3), [])

    def test_pixel_heart_has_two_lobes_and_a_point_without_font_glyphs(self):
        with patch("pygame.font.Font", side_effect=AssertionError("A heart must not use a font")):
            sprite = main.heart_sprite(3)
        pink = (242, 91, 119)
        self.assertEqual(sprite.get_at((3 * 3, 1 * 3))[:3], pink)
        self.assertEqual(sprite.get_at((5 * 3, 1 * 3))[:3], pink)
        self.assertNotEqual(sprite.get_at((4 * 3, 1 * 3))[:3], pink)
        self.assertEqual(sprite.get_at((4 * 3, 6 * 3))[:3], pink)

    def test_zoo_unlocks_only_the_next_pet_and_keeps_residents_viewable(self):
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS:
                main.record_answer(self.app.game, word["id"], True)
                clear_checkpoints(self.app.game)
        self.app.game["pet_name"] = "Пушок"
        self.certify_pet()
        self.app.open_zoo()
        self.app.draw()
        self.app.click((650, 560))
        self.assertEqual(current_species(self.app.game), "axolotl")
        self.assertEqual(pet_learned_count(self.app.game), 0)
        self.assertEqual(len(self.app.game["zoo"]["residents"]), 1)
        self.assertEqual(self.app.sprites.species, "axolotl")
        self.app.draw()
        self.assertTrue(all(pygame.Rect(0, 0, main.WIDTH, main.HEIGHT).contains(rect)
                            for rect, _ in self.app.buttons))
        self.app.inspect_resident(0)
        self.app.draw()
        self.assertEqual(self.app.game["zoo"]["residents"][0]["name"], "Пушок")
        self.assertEqual(self.app.sprites.species, "axolotl")
        self.app.screen = "home"
        self.app.draw()
        self.assertEqual(main.growth_stage(self.app.game), 0)

    def test_zoo_shows_eggs_until_a_grown_pet_moves_in(self):
        self.app.open_zoo()
        original = self.app.sprites.scaled_species
        with patch.object(self.app.sprites, "scaled_species", wraps=original) as render:
            self.app.draw()
            self.assertEqual([(call.args[0], call.args[1], call.args[2]) for call in render.call_args_list],
                             [(species, "hatching", 0) for species, _ in SPECIES])
        self.set_pet_stage(4)
        self.app.open_zoo()
        with patch.object(self.app.sprites, "scaled_species", wraps=original) as render:
            self.app.draw()
            self.assertTrue(all(call.args[1:3] == ("hatching", 0) for call in render.call_args_list))
        for word in WORDS:
            self.app.game["cards"][word["id"]] = {"seen": True, "correct_sessions": [1, 2]}
        self.certify_pet()
        self.app.settle_current_pet()
        with patch.object(self.app.sprites, "scaled_species", wraps=original) as render:
            self.app.draw()
            calls = [(call.args[0], call.args[1], call.args[2]) for call in render.call_args_list]
            self.assertEqual(calls[0], ("sniffer", "growth", 4))
            self.assertEqual(calls[1], ("sniffer", "hatching", 0))
            self.assertEqual(calls[2:], [(species, "hatching", 0) for species, _ in SPECIES[1:]])

    def test_all_new_species_have_distinct_transparent_growth_and_animation_sprites(self):
        adult_images = set()
        for species, _ in SPECIES[1:]:
            self.app.sprites.select_species(species)
            for family, count in (("growth", 5), ("hatching", 5), ("walk", 6)):
                for frame in range(count):
                    image = self.app.sprites.scaled(family, frame, 240, 180)
                    self.assertGreater(image.get_bounding_rect().width, 10)
                    self.assertLessEqual(image.get_width(), 240)
                    self.assertLessEqual(image.get_height(), 180)
                    self.assertTrue(image.get_flags() & pygame.SRCALPHA)
            frames = self.app.sprites.families[species]["walk"]
            self.assertGreater(len({pygame.image.tobytes(image, "RGBA") for image in frames}), 1)
            adult = self.app.sprites.scaled("growth", 4, 240, 180)
            adult_images.add(pygame.image.tobytes(adult, "RGBA"))
        self.assertEqual(len(adult_images), 5)

    def test_growth_changes_the_picture_and_silhouette_not_just_its_size(self):
        from creature_sprites import creature
        for species, _ in SPECIES[1:]:
            with self.subTest(species=species):
                frames = [pygame.transform.scale(creature(species, stage), (64, 64)) for stage in range(1, 5)]
                for before, after in zip(frames, frames[1:]):
                    a, b = pygame.image.tobytes(before, "RGBA"), pygame.image.tobytes(after, "RGBA")
                    changed = sum(a[i:i + 4] != b[i:i + 4] for i in range(0, len(a), 4))
                    self.assertGreater(changed / 4096, 0.04)
                baby, adult = (pygame.mask.from_surface(frames[index]) for index in (0, 2))
                overlap = baby.overlap_area(adult, (0, 0))
                difference = baby.count() + adult.count() - 2 * overlap
                union = baby.count() + adult.count() - overlap
                self.assertGreater(difference / union, 0.08)

    def test_final_test_blocks_next_species_until_35_out_of_50_and_corrections(self):
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS:
                main.record_answer(self.app.game, word["id"], True)
                clear_checkpoints(self.app.game)
        self.app.open_zoo()
        self.app.settle_current_pet()
        self.assertEqual(self.app.screen, "final_test")
        for i, expected in enumerate(self.app.game["zoo"]["exam"]["queue"][:]):
            self.app.submit_final_test(expected if i < 34 else next(word["id"] for word in WORDS if word["id"] != expected))
            self.app.draw()
            self.app.next_final_test()
        self.app.draw()
        self.assertEqual(current_species(self.app.game), "sniffer")
        self.finish_ui_repairs()
        self.app.pause_final_test()
        self.app.open_final_test(retry=True)
        for i, expected in enumerate(self.app.game["zoo"]["exam"]["queue"][:]):
            self.app.submit_final_test(expected if i < 35 else next(word["id"] for word in WORDS if word["id"] != expected))
            self.app.next_final_test()
        self.app.draw()
        self.assertFalse(main.final_passed(self.app.game))
        self.finish_ui_repairs()
        self.app.settle_current_pet()
        self.assertEqual(current_species(self.app.game), "axolotl")
        self.assertEqual(self.app.screen, "zoo")

    def finish_ui_repairs(self):
        self.app.begin_repairs(True)
        exam = self.app.game["zoo"]["exam"]
        for _ in range(400):
            if exam["phase"] == "summary":
                return
            if exam["phase"] == "repair_quiz":
                self.app.submit_final_test(expected_word(exam))
            else:
                self.app.next_final_test()
        self.fail("UI corrections did not finish")

    def test_replay_confirmation_keeps_grown_friend_and_creates_a_new_egg(self):
        for session in (1, 2):
            self.app.game["session"] = session
            for word in WORDS:
                main.record_answer(self.app.game, word["id"], True)
                clear_checkpoints(self.app.game)
        self.certify_pet()
        self.app.settle_current_pet()
        self.app.request_replay(0)
        self.assertEqual(self.app.screen, "replay_confirm")
        self.app.draw()
        self.app.start_replay()
        self.assertTrue(self.app.game["zoo"]["replay"])
        self.assertEqual(len(self.app.game["zoo"]["residents"]), 1)
        self.assertEqual(main.growth_stage(self.app.game), 0)
        with patch.object(self.app.sprites, "scaled_species", wraps=self.app.sprites.scaled_species) as render:
            self.app.draw()
            self.assertTrue(any(call.args[:3] == ("sniffer", "growth", 4) for call in render.call_args_list))
            self.assertTrue(any(call.args[:3] == ("sniffer", "hatching", 0) for call in render.call_args_list))
        self.app.open_zoo()
        self.app.draw()

    def test_grammar_cards_and_checks_use_sentence_context_not_an_isolated_translation(self):
        from grammar import FORM_QUESTIONS
        for word_id in FORM_QUESTIONS:
            self.app.queue = [word_id]
            self.app.word_id = word_id
            self.app.card_index = 0
            self.app.screen = "cards"
            self.app.card_phase = "intro"
            self.app.draw()
            self.app.card_phase = "quiz"
            self.app.options = main.choice_ids(word_id)
            with patch.object(self.app, "button", wraps=self.app.button) as button, patch("main.text", wraps=main.text) as painted_text:
                self.app.draw()
                labels = [call.args[1] for call in button.call_args_list]
                self.assertIn(word_id, labels)
                self.assertNotIn(main.WORD_BY_ID[word_id]["ru"], labels)
                self.assertNotIn(main.WORD_BY_ID[word_id]["ru"], [call.args[1] for call in painted_text.call_args_list])
            self.app.game["active_review"] = {"milestone": 30, "queue": [word_id], "answers": [], "phase": "quiz"}
            self.app.review_options = main.choice_ids(word_id)
            self.app.screen = "review"
            self.app.draw()

    def test_new_word_distinguishes_pronunciation_and_translation_with_icons_only(self):
        self.app.start_lesson()
        with patch("main.word_hint_icon", wraps=main.word_hint_icon) as icon, patch("main.text", wraps=main.text) as painted:
            self.app.draw()
            labels = [call.args[1] for call in painted.call_args_list]
            self.assertNotIn("ПРОИЗНОШЕНИЕ", labels)
            self.assertNotIn("ПЕРЕВОД", labels)
            self.assertEqual([call.args[1] for call in icon.call_args_list], ["sound", "book"])
        icon_surface = pygame.Surface((40, 30), pygame.SRCALPHA)
        with patch("pygame.font.Font", side_effect=AssertionError("Icons must not use a font")):
            main.word_hint_icon(icon_surface, "sound", 2, 2, main.RED)
            main.word_hint_icon(icon_surface, "book", 2, 2, main.TEAL)

    def test_new_word_picture_shows_the_word_not_the_current_pet_or_egg(self):
        self.app.queue = ["cat"]
        self.app.word_id = "cat"
        self.app.screen = "cards"
        self.app.card_phase = "intro"
        with patch.object(self.app.sprites, "scaled", wraps=self.app.sprites.scaled) as pet, patch.object(self.app.word_pictures, "draw", wraps=self.app.word_pictures.draw) as picture:
            self.app.draw()
            pet.assert_not_called()
            self.assertEqual(picture.call_args.args[1], "cat")

    def test_dictionary_listening_and_repetition_do_not_change_test_or_growth_state(self):
        self.set_pet_stage(4)
        self.app.game["repeat_words"] = ["cat"]
        self.app.game["zoo"]["exam"] = {"queue": [word["id"] for word in WORDS[:10]],
                                          "answers": ["cat"] * 10, "phase": "summary"}
        self.app.screen = "final_test"
        before = copy.deepcopy(self.app.game)
        self.app.open_dictionary("sniffer")
        self.app.draw()
        visible = learned_vocabulary(self.app.game, "sniffer")
        self.app.click((900, 283))
        self.app.speech.speak.assert_called_once_with(visible[0]["id"])
        self.app.dictionary_reveal = False
        self.app.draw()
        self.app.toggle_dictionary_errors()
        self.app.draw()
        self.app.search_dictionary()
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="cat"))
        self.app.draw()
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.app.close_dictionary()
        self.assertEqual(self.app.screen, "final_test")
        self.assertEqual(self.app.game, before)

    def test_dictionary_pagination_empty_results_and_search_render_inside_the_canvas(self):
        self.set_pet_stage(4)
        self.app.open_dictionary()
        self.app.dictionary_page = 999
        self.app.draw()
        self.assertLess(self.app.dictionary_page, 999)
        self.app.dictionary_query = "nothing matches this"
        self.app.draw()
        self.assertEqual(self.app.dictionary_page, 0)
        self.assertTrue(all(pygame.Rect(0, 0, main.WIDTH, main.HEIGHT).contains(rect) for rect, _ in self.app.buttons))

    def test_pronoun_example_highlights_the_pronoun_not_another_verb_form(self):
        with patch("main.text", wraps=main.text) as painted:
            main.contextual_sentence(self.app.canvas, "I", "am", "happy.", (400, 250), focus="I")
            self.assertEqual(painted.call_args_list[0].args[4], main.RED)
            self.assertEqual(painted.call_args_list[1].args[4], main.INK)

    def test_next_card_cannot_skip_the_next_question_if_called_twice(self):
        self.app.start_lesson()
        self.app.intro_done()
        self.app.answer(self.app.word_id)
        self.app.next_card()
        index, word = self.app.card_index, self.app.word_id
        self.assertEqual(self.app.card_phase, "intro")
        self.app.next_card()
        self.assertEqual(self.app.card_index, index)
        self.assertEqual(self.app.word_id, word)

    def test_paused_quiz_does_not_accept_an_answer_from_an_old_button(self):
        self.app.start_lesson()
        self.app.intro_done()
        self.app.leave_cards()
        before = copy.deepcopy(self.app.game)
        self.app.answer(self.app.word_id)
        self.assertEqual(self.app.game, before)

    def test_paused_intro_does_not_mark_the_word_seen_from_an_old_button(self):
        self.app.start_lesson()
        self.app.leave_cards()
        before = copy.deepcopy(self.app.game)
        self.app.intro_done()
        self.assertEqual(self.app.game, before)

    def test_paused_checks_ignore_old_answer_and_next_callbacks(self):
        self.set_pet_stage(2)
        self.app.start_lesson()
        first = self.app.game["active_review"]["queue"][0]
        self.app.submit_review(first)
        self.app.pause_review()
        before = copy.deepcopy(self.app.game)
        self.app.submit_review(first)
        self.app.next_review()
        self.assertEqual(self.app.game, before)

    def test_save_conflict_does_not_leave_the_old_pet_hitbox_active_over_export(self):
        self.set_pet_stage(1)
        self.app.screen = "home"
        self.app.draw()
        self.assertTrue(self.app.pet_rect.collidepoint((350, 440)))
        self.app.save_conflict = True
        self.app.draw()
        with patch.object(self.app, "transfer_profile") as transfer:
            self.app.click((350, 440))
            transfer.assert_called_once_with(True)
        self.assertEqual(self.app.hearts.particles, [])

    def test_second_touch_in_the_same_frame_cannot_use_the_previous_next_button(self):
        self.app.start_lesson()
        self.app.intro_done()
        self.app.answer(self.app.word_id)
        self.app.draw()
        self.app.click((420, 510))
        self.assertEqual(self.app.card_index, 1)
        self.app.click((620, 510))
        self.assertEqual(self.app.card_index, 1)

    def test_resumed_legacy_quiz_cannot_show_more_learned_words_than_were_saved(self):
        legacy = new_game()
        legacy["cards"]["cat"] = {"seen": True, "correct_sessions": [2]}
        legacy["lesson"] = {"queue": ["cat", "dog"], "index": 0, "phase": "quiz", "mode": "meaning", "correct": False, "answers": 0}
        self.store.save_game(self.identity, legacy)
        self.app.enter_player(self.identity)
        self.app.answer("cat")
        self.assertEqual(main.mastered_count(self.store.load_game(self.identity)), main.mastered_count(self.app.game))


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
            "java.util.Locale": lambda language, country: language + "-" + country,
            "java.lang.String": lambda value: ("JavaString", value),
            "android.os.Bundle": lambda: {"JavaBundle": True},
            "android.speech.tts.TextToSpeech": initialize_tts,
        }
        modules = {
            "jnius": SimpleNamespace(PythonJavaClass=object, autoclass=lambda name: classes[name],
                                     cast=lambda name, value: value, java_method=lambda signature: lambda function: function),
            "android.runnable": SimpleNamespace(run_on_ui_thread=ui_thread),
        }
        with patch.dict("sys.modules", modules), patch("speech.sys.platform", "android"):
            speech = Speech(Path("missing-audio"))
            self.assertTrue(speech.ready)
            self.assertTrue(speech.speak("hello"))
            self.assertEqual(calls, ["initialize", "speak"])
            tts.setLanguage.assert_called_once_with("en-US")
            tts.speak.assert_called_once_with(("JavaString", "hello"), 0, {"JavaBundle": True}, "sniffer-word")

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
