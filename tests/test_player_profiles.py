import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from game_logic import new_game
from game_storage import (WEB_STORAGE_KEY, make_backup_bytes, read_player_backup_bytes, write_game)
from player_profiles import PlayerStore


class PlayerProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "players.json"
        self.store = PlayerStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_registration_creates_isolated_states_and_remembers_the_last_player(self):
        anna = self.store.create_player("Анна")
        anna_game = self.store.load_game(anna)
        anna_game.update(pet_name="Пушок", correct_answers=17)
        anna_game["cards"]["cat"] = {"seen": True, "correct_sessions": [1, 2]}
        anna_game["lesson"] = {"queue": ["dog"], "index": 0, "phase": "quiz", "mode": "meaning", "correct": False, "answers": 0}
        self.store.save_game(anna, anna_game)
        boris = self.store.create_player("Борис")
        self.assertEqual(self.store.load_game(boris), new_game())
        self.assertEqual(self.store.load_game(anna)["pet_name"], "Пушок")
        self.assertIsNotNone(self.store.load_game(anna)["lesson"])
        self.assertEqual(self.store.list_players()[0]["id"], boris)
        self.store.select_player(anna)
        self.assertEqual(PlayerStore(self.path).list_players()[0]["id"], anna)

    def test_duplicate_case_or_whitespace_and_empty_names_do_not_overwrite(self):
        self.store.create_player("  Анна   Иванова ")
        before = self.path.read_bytes()
        for name in ("анна иванова", " АННА   ИВАНОВА ", "  "):
            with self.assertRaises(ValueError):
                self.store.create_player(name)
        self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_single_save_is_migrated_without_assigning_it_to_a_new_child(self):
        old = new_game()
        old.update(pet_name="Моховичок", correct_answers=33)
        write_game(old, self.path)
        profiles = self.store.list_players()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["name"], "Сохранённая игра")
        original_id = profiles[0]["id"]
        self.assertEqual(self.store.load_game(original_id), old)
        new_id = self.store.create_player("Настя")
        self.assertEqual(self.store.load_game(new_id), new_game())
        self.assertEqual(self.store.load_game(original_id), old)
        self.assertEqual(self.store.list_players()[1]["id"], original_id)
        with self.assertRaises(ValueError):
            write_game(new_game(), self.path)

    def test_loading_game_returns_a_separate_object(self):
        identity = self.store.create_player("Анна")
        game = self.store.load_game(identity)
        game["care"]["food"] = 0
        game["zoo"]["residents"].append({"species": "sniffer", "name": "Не сохранять"})
        self.assertEqual(self.store.load_game(identity), new_game())

    def test_each_save_reads_other_profiles_fresh(self):
        anna = self.store.create_player("Анна")
        boris = self.store.create_player("Борис")
        second_store = PlayerStore(self.path)
        a, b = self.store.load_game(anna), second_store.load_game(boris)
        a["correct_answers"], b["correct_answers"] = 15, 41
        self.store.save_game(anna, a)
        second_store.save_game(boris, b)
        self.assertEqual(self.store.load_game(anna)["correct_answers"], 15)
        self.assertEqual(self.store.load_game(boris)["correct_answers"], 41)

    def test_failed_write_preserves_both_players(self):
        anna = self.store.create_player("Анна")
        self.store.create_player("Борис")
        before = self.path.read_bytes()
        with patch("game_storage.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save_game(anna, new_game())
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_storage_is_not_replaced_by_a_new_registration(self):
        self.path.write_text("broken JSON", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.create_player("Анна")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "broken JSON")

    def test_rename_changes_only_the_player_name(self):
        anna = self.store.create_player("Анна")
        boris = self.store.create_player("Борис")
        before = self.store.load_game(anna)
        self.store.rename_player(anna, "Аня")
        self.assertEqual(self.store.metadata(anna)["name"], "Аня")
        self.assertEqual(self.store.load_game(anna), before)
        with self.assertRaises(ValueError):
            self.store.rename_player(anna, "борис")
        self.assertEqual(self.store.metadata(boris)["name"], "Борис")

    def test_import_of_an_existing_other_player_cannot_replace_current_or_sibling(self):
        anna = self.store.create_player("Анна")
        boris = self.store.create_player("Борис")
        imported = new_game()
        imported["correct_answers"] = 77
        backup = read_player_backup_bytes(make_backup_bytes(imported, self.store.metadata(anna)))
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.restore_backup(backup, boris)
        self.assertEqual(self.path.read_bytes(), before)
        self.store.restore_backup(backup, anna)
        self.assertEqual(self.store.load_game(anna)["correct_answers"], 77)
        self.assertEqual(self.store.load_game(boris), new_game())

    def test_import_adds_a_missing_player_without_touching_current(self):
        anna = self.store.create_player("Анна")
        old_game = self.store.load_game(anna)
        backup = {"player": {"id": "external-profile", "name": "Ксюша"}, "game": new_game()}
        backup["game"]["pet_name"] = "Листик"
        restored = self.store.restore_backup(backup, anna)
        self.assertEqual(restored, "external-profile")
        self.assertEqual(self.store.load_game(anna), old_game)
        self.assertEqual(self.store.load_game(restored)["pet_name"], "Листик")

    def test_legacy_import_requires_registration_when_nobody_is_selected(self):
        backup = read_player_backup_bytes(make_backup_bytes(new_game()))
        self.assertEqual(self.store.import_target(backup), ("register", None))
        self.assertFalse(self.path.exists())

    def test_browser_profiles_migrate_and_survive_reload(self):
        legacy = new_game()
        legacy["pet_name"] = "Листик"
        data = {WEB_STORAGE_KEY: json.dumps(legacy, ensure_ascii=False)}
        window = SimpleNamespace(localStorage=SimpleNamespace(
            getItem=lambda key: data.get(key), setItem=lambda key, value: data.update({key: value})))
        with patch("game_storage.sys.platform", "emscripten"), patch("platform.window", window, create=True):
            store = PlayerStore()
            old_id = store.list_players()[0]["id"]
            new_id = store.create_player("Ксюша")
            game = store.load_game(new_id)
            game["correct_answers"] = 9
            store.save_game(new_id, game)
            reopened = PlayerStore()
            self.assertEqual(reopened.load_game(old_id)["pet_name"], "Листик")
            self.assertEqual(reopened.load_game(new_id)["correct_answers"], 9)
            self.assertEqual(len(reopened.list_players()), 2)


if __name__ == "__main__":
    unittest.main()
