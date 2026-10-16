"""Audit the playable state machine through collection and repeat growth."""

import copy
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
except ImportError:
    raise unittest.SkipTest("Game state-machine audit needs pygame")

from game_logic import mastered_count
from game_storage import PLAYERS_FORMAT
import main
from player_profiles import PlayerStore
from zoo import SPECIES, current_species, growth_complete, pet_learned_count


class MemoryPlayers(PlayerStore):
    def __init__(self, path):
        super().__init__(path)
        self.document = {"format": PLAYERS_FORMAT, "version": 2, "last_player": None, "profiles": {}}

    def _read(self):
        return copy.deepcopy(self.document)

    def _write(self, document):
        self.document = copy.deepcopy(document)


class FullLogicFlowTests(unittest.TestCase):
    def test_all_six_pets_and_replay_preserve_progress_and_unlock_order(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MemoryPlayers(Path(directory) / "never-written.json")
            identity = store.create_player("Проверка логики")
            app = main.GameApp(profile_store=store)
            app.speech.speak = Mock(return_value=True)
            app.enter_player(identity)
            rng = random.Random(1024)
            counts = []

            def drive_until(predicate):
                for _ in range(4000):
                    if predicate():
                        return
                    if app.screen == "home":
                        if growth_complete(app.game):
                            app.settle_current_pet()
                        else:
                            app.start_lesson()
                    elif app.screen == "cards":
                        if app.card_phase == "intro":
                            app.intro_done()
                        elif app.card_phase == "quiz":
                            app.answer(app.word_id)
                        else:
                            app.next_card()
                    elif app.screen == "growth":
                        app.acknowledge_growth()
                    elif app.screen == "review":
                        review = app.game["active_review"]
                        if review["phase"] == "quiz":
                            app.submit_review(review["queue"][len(review["answers"])])
                        elif review["phase"] == "feedback":
                            app.next_review()
                        else:
                            app.close_review()
                    elif app.screen == "final_test":
                        exam = app.game["zoo"]["exam"]
                        if exam["phase"] == "quiz":
                            app.submit_final_test(exam["queue"][len(exam["answers"])])
                        elif exam["phase"] == "feedback":
                            app.next_final_test()
                        else:
                            app.settle_current_pet()
                    elif app.screen == "zoo":
                        app.screen = "home"
                    else:
                        self.fail("Unexpected screen: " + app.screen)
                    self.assertFalse(app.save_conflict)
                    count = mastered_count(app.game)
                    if counts:
                        self.assertGreaterEqual(count, counts[-1])
                    counts.append(count)
                self.fail("Game flow did not finish within the transition budget")

            try:
                with patch("game_logic.random", rng), patch("learning_stats.random", rng), patch("zoo.random", rng):
                    drive_until(lambda: current_species(app.game) == "axolotl")
                    self.assertEqual(mastered_count(app.game), 150)
                    self.assertEqual(pet_learned_count(app.game), 0)
                    self.assertEqual(len(app.game["zoo"]["residents"]), 1)
                    self.assertEqual(len(app.game["reviews"]), 5)
                    app.request_replay(0)
                    self.assertEqual(app.screen, "replay_confirm")
                    app.start_replay()
                    self.assertEqual(pet_learned_count(app.game), 0)
                    drive_until(lambda: not app.game["zoo"]["replay"])
                self.assertEqual(current_species(app.game), "axolotl")
                self.assertEqual(pet_learned_count(app.game), 0)
                self.assertEqual(mastered_count(app.game), 150)
                self.assertEqual(len(app.game["zoo"]["residents"]), 1)
                self.assertEqual(app.game["zoo"]["residents"][0]["grown"], 2)
                self.assertEqual(len(app.game["reviews"]), 10)
                self.assertEqual([item["score"] for item in app.game["zoo"]["exam_history"]], [10, 10])
                self.assertEqual(store.load_game(identity), app.game)
                with patch("game_logic.random", rng), patch("learning_stats.random", rng), patch("zoo.random", rng):
                    for count in range(2, 7):
                        drive_until(lambda: len(app.game["zoo"]["residents"]) == count)
                        self.assertEqual([item["species"] for item in app.game["zoo"]["residents"]],
                                         [key for key, _ in SPECIES[:count]])
                        self.assertEqual(mastered_count(app.game), count * 150)
                        self.assertEqual(len(app.game["reviews"]), (count + 1) * 5)
                        self.assertEqual(store.load_game(identity), app.game)
                self.assertEqual(len(app.game["zoo"]["exam_history"]), 7)
                self.assertFalse(growth_complete(app.game))
                self.assertFalse(Path(directory, "never-written.json").exists())
            finally:
                app.speech.shutdown()
                pygame.quit()
