import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from game_logic import growth_remaining, new_game, normalize_game
import game_storage
from words import WORDS


class GameStorageTests(unittest.TestCase):
    def test_save_and_reload_all_progress_and_active_lesson(self):
        game = new_game()
        game.update(pet_name="Моховичок", session=3, correct_answers=8, feedings=2, poop=True)
        game["care"] = {"food": 1, "joy": 2, "clean": 0}
        game["cards"]["cat"] = {"seen": True, "correct_sessions": [1, 3]}
        game["learned_order"] = ["cat"]
        game["lesson"] = {"queue": ["cat", "dog"], "index": 0, "phase": "result",
                          "mode": "spelling", "correct": True, "answers": 1}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            game_storage.write_game(game, path)
            self.assertEqual(game_storage.load_game(path), game)
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_failed_replace_preserves_previous_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "save.json"
            original = new_game()
            game_storage.write_game(original, path)
            changed = new_game()
            changed["pet_name"] = "Новое имя"
            with patch("game_storage.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    game_storage.write_game(changed, path)
            self.assertEqual(game_storage.load_game(path), original)

    def test_old_saves_get_name_and_lesson_defaults(self):
        game = normalize_game({"session": 7, "correct_answers": 16})
        self.assertEqual(game["pet_name"], "Сниффер")
        self.assertIsNone(game["lesson"])
        self.assertEqual(game["correct_answers"], 16)

    def test_bad_lesson_does_not_discard_game(self):
        for lesson in ({"queue": ["unknown"], "index": 0}, {"queue": ["cat"], "index": 2},
                       {"queue": [{}], "index": 0}, {"queue": ["cat"], "index": True}):
            with self.subTest(lesson=lesson):
                game = normalize_game({"correct_answers": 20, "lesson": lesson})
                self.assertIsNone(game["lesson"])
                self.assertEqual(game["correct_answers"], 20)

    def test_name_is_bounded_and_single_line(self):
        game = normalize_game({"pet_name": "  Мох\n  Пушок  "})
        self.assertEqual(game["pet_name"], "Мох Пушок")
        self.assertEqual(len(normalize_game({"pet_name": "я" * 100})["pet_name"]), 20)
        self.assertEqual(normalize_game({"pet_name": "\n"})["pet_name"], "Сниффер")

    def test_backup_restores_profile_after_local_save_is_gone(self):
        game = new_game()
        game["pet_name"] = "Пушок"
        game["correct_answers"] = 6
        game["cards"]["dog"] = {"seen": True, "correct_sessions": [1, 2]}
        game["learned_order"] = ["dog"]
        backup = game_storage.make_backup_bytes(game)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reinstalled" / "save.json"
            self.assertEqual(game_storage.load_game(path), new_game())
            game_storage.write_game(game_storage.read_backup_bytes(backup), path)
            self.assertEqual(game_storage.load_game(path), game)

    def test_rejects_wrong_corrupt_or_oversized_backups(self):
        for content in (b"invalid", b"\xff", b"[]", b"{}", b'{"format":"mathcraft-backup"}',
                        b"x" * (game_storage.MAX_BACKUP_BYTES + 1)):
            with self.subTest(size=len(content)):
                with self.assertRaises(ValueError):
                    game_storage.read_backup_bytes(content)

    def test_migrates_save_from_older_apk_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "private" / "sniffer_save.json"
            old = new_game()
            old["correct_answers"] = 12
            game_storage.write_game(old, root / "sniffer_save.json")
            with patch.object(game_storage, "ROOT", root), patch.object(game_storage, "save_path", return_value=target):
                self.assertEqual(game_storage.load_game(), old)
            self.assertEqual(game_storage.load_game(target), old)

    def test_browser_storage_survives_filesystem_restart(self):
        storage = {}
        window = SimpleNamespace(localStorage=SimpleNamespace(
            setItem=lambda key, value: storage.update({key: value}),
            getItem=lambda key: storage.get(key)))
        game = new_game()
        game["pet_name"] = "Зелёныш"
        with patch("game_storage.sys.platform", "emscripten"), patch("platform.window", window, create=True):
            game_storage.write_game(game)
            self.assertEqual(game_storage.load_game(), game)
        self.assertEqual(json.loads(storage[game_storage.WEB_STORAGE_KEY])["pet_name"], "Зелёныш")

    def test_growth_countdown_boundaries(self):
        game = new_game()
        self.assertEqual(growth_remaining(game), ("hatch_words", 30))
        game["correct_answers"] = 4
        self.assertEqual(growth_remaining(game), ("hatch_words", 30))
        game["correct_answers"] = 5
        for count, expected in ((0, 30), (29, 1), (30, 30), (59, 1), (60, 30), (89, 1), (90, 30), (119, 1), (120, 0), (150, 0)):
            game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in WORDS[:count]}
            kind = "complete" if count >= 120 else "hatch_words" if count < 30 else "words"
            self.assertEqual(growth_remaining(game), (kind, expected))


if __name__ == "__main__":
    unittest.main()
