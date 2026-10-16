"""Resource lifetime and fixed-workload cache regressions, not an Android profiler."""

import gc
import os
from pathlib import Path
import tempfile
import unittest
import weakref

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
except ImportError:
    raise unittest.SkipTest("Memory UI checks need pygame")

import main
from game_logic import new_game
from player_profiles import PlayerStore
from tools.check_memory import cache_state, exercise
from words import ALL_WORDS
from zoo import SPECIES


class MemoryTests(unittest.TestCase):
    def test_repeated_screens_and_player_switches_do_not_accumulate_ui_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PlayerStore(Path(directory) / "players.json")
            game = new_game()
            game["session"] = 2
            game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in ALL_WORDS}
            game["zoo"]["residents"] = [{"species": key, "name": name} for key, name in SPECIES]
            game["zoo"]["active"] = "allay"
            identities = [store.create_player(name, game=game) for name in ("A", "B")]
            app = main.GameApp(profile_store=store)
            try:
                app.enter_player(identities[0])
                exercise(app, 24)
                warmed = cache_state(app)
                for i in range(4):
                    self.assertTrue(app.enter_player(identities[i % 2]))
                    exercise(app, 24)
                    self.assertEqual(cache_state(app), warmed)
                    self.assertLessEqual(len(app.buttons), 30)
                    self.assertLessEqual(len(app.hearts.particles), 48)
                app.hearts.frame(pygame.time.get_ticks() / 1000 + 3)
                self.assertEqual(app.hearts.particles, [])
            finally:
                app.profile_picker.close()
                app.speech.shutdown()
                pygame.quit()
            reference = weakref.ref(app)
            del app
            gc.collect()
            self.assertIsNone(reference())
