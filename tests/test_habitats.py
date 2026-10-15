import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
except ImportError:
    raise unittest.SkipTest("Habitat rendering checks need pygame")

from game_logic import new_game
from habitats import Habitats
import main
from words import words_for_species
from zoo import SPECIES
from player_profiles import PlayerStore


class HabitatTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        store = PlayerStore(Path(self.directory.name) / "players.json")
        identity = store.create_player("Тестовый игрок")
        self.app = main.GameApp(profile_store=store)
        self.app.enter_player(identity)
        self.app.speech.speak = Mock(return_value=True)

    def tearDown(self):
        self.app.speech.shutdown()
        pygame.quit()
        patch.stopall()
        self.directory.cleanup()

    def select_species(self, index, grown=True):
        species, name = SPECIES[index]
        self.app.game = new_game()
        self.app.game["zoo"]["residents"] = [{"species": key, "name": value} for key, value in SPECIES[:index]]
        self.app.game["zoo"]["active"] = species
        self.app.game["pet_name"] = name
        self.app.game["session"] = 2
        if grown:
            self.app.game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in words_for_species(species)}
            self.app.game["correct_answers"] = 300
            self.app.game["zoo"]["pet_correct_answers"] = 300
        self.app.sprites.select_species(species)
        self.app.screen = "home"

    def test_all_habitats_are_distinct_cached_and_keep_the_correct_ground_in_games(self):
        worlds = Habitats()
        image = pygame.Surface((1000, 600))
        frames = set()
        for species, _ in SPECIES:
            worlds.draw(image, species, 0)
            frames.add(pygame.image.tobytes(image, "RGB"))
            cached = worlds.cache[(species, (1000, 600), False)]
            worlds.draw(image, species, 1)
            self.assertIs(worlds.cache[(species, (1000, 600), False)], cached)
            worlds.draw(image, species, 1, play=True)
        self.assertEqual(len(frames), 6)
        self.assertEqual(len(worlds.cache), 12)

    def test_underwater_bubbles_and_fish_change_with_time(self):
        worlds = Habitats()
        image = pygame.Surface((1000, 600))
        worlds.draw(image, "axolotl", 0)
        before = pygame.image.tobytes(image, "RGB")
        worlds.draw(image, "axolotl", 1)
        self.assertNotEqual(before, pygame.image.tobytes(image, "RGB"))
        self.assertEqual(len(worlds.cache), 1)

    def test_each_growth_stage_adds_new_details_without_allocating_a_full_background(self):
        worlds = Habitats()
        image = pygame.Surface((1000, 600))
        for species, _ in SPECIES:
            pictures = set()
            for stage in range(5):
                worlds.draw(image, species, 0, stage=stage)
                pictures.add(pygame.image.tobytes(image, "RGB"))
            self.assertEqual(len(pictures), 5, species)
        self.assertEqual(len(worlds.cache), 6)

    def test_every_species_renders_its_home_game_and_longest_word_card(self):
        for index, (species, _) in enumerate(SPECIES):
            with self.subTest(species=species):
                self.select_species(index)
                self.app.draw()
                self.app.start_play()
                self.app.draw()
                self.assertIn((species, (1000, 600), True), self.app.habitats.cache)
                self.app.screen = "cards"
                longest = max(words_for_species(species), key=lambda word: len(word["en"]) + len(word["ru"]))
                self.app.word_id = longest["id"]
                self.app.queue = [longest["id"]]
                self.app.card_index = 0
                self.app.card_phase = "intro"
                self.app.draw()
                self.assertTrue(all(pygame.Rect(0, 0, 1000, 600).contains(rect) for rect, _ in self.app.buttons))

    def test_resident_uses_its_own_background_not_the_current_egg_world(self):
        self.select_species(2)
        self.app.zoo_selection = 1
        self.app.screen = "resident"
        with patch.object(self.app.habitats, "draw", wraps=self.app.habitats.draw) as draw:
            self.app.draw()
            self.assertEqual(draw.call_args.args[1], "axolotl")


if __name__ == "__main__":
    unittest.main()
