"""Actual old JSON -> migration -> file export/import -> restart, without user saves."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from game_logic import new_game
from game_storage import PLAYERS_FORMAT, make_backup_bytes, read_player_backup_bytes
from player_profiles import PlayerStore
from words import words_for_species


def old_game():
    game = new_game()
    game["session"] = 5
    game["correct_answers"] = 610
    game["pet_name"] = "Розочка"
    game["care"] = {"food": 1, "joy": 2, "clean": 0}
    game["poop"] = True
    game["feedings"] = 7
    game["last_food"] = "apple"
    game["garden_plants"] = 9
    for species in ("sniffer", "axolotl"):
        for word in words_for_species(species):
            game["cards"][word["id"]] = {"seen": True, "correct_sessions": [2, 5]}
            game["learned_order"].append(word["id"])
        for milestone in (30, 60, 90, 120, 150):
            result = {"milestone": milestone, "score": 4, "total": 6}
            if species != "sniffer":
                result["species"] = species
            game["reviews"].append(result)
    word = words_for_species("axolotl")[0]["id"]
    game["repeat_words"] = [word]
    game["word_stats"][word] = {"lesson_attempts": 7, "lesson_correct": 5, "review_attempts": 3, "review_correct": 1}
    game["zoo"].update({"active": "axolotl", "residents": [{"species": "sniffer", "name": "Листик"}],
                        "exam_history": [{"species": "sniffer", "cycle": 0, "score": 7, "total": 10}]})
    queue = [word["id"] for word in words_for_species("axolotl")[:10]]
    game["zoo"]["exam"] = {"queue": queue, "answers": queue[:5], "phase": "feedback"}
    return game


class ProfileMigrationTests(unittest.TestCase):
    def test_existing_state_survives_old_private_file_export_import_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "old-players.json"
            original = old_game()
            sibling = new_game()
            sibling["pet_name"] = "Другой ребёнок"
            document = {"format": PLAYERS_FORMAT, "version": 2, "last_player": "anna",
                        "profiles": {"anna": {"name": "Анна", "game": original, "revision": 3},
                                     "sibling": {"name": "Ваня", "game": sibling, "revision": 9}}}
            path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            original_bytes = path.read_bytes()
            source = PlayerStore(path)
            profile = source.load_profile("anna")
            migrated = profile["game"]
            for key in ("cards", "learned_order", "word_stats", "repeat_words", "care", "poop", "feedings",
                        "last_food", "garden_plants", "pet_name", "session", "correct_answers"):
                self.assertEqual(migrated[key], original[key], key)
            self.assertEqual(len(migrated["reviews"]), 10)
            def review_identity(item):
                return (item.get("species", "sniffer"), item.get("cycle", 0), item["milestone"], item["score"], item["total"])
            self.assertEqual(sorted(map(review_identity, migrated["reviews"])), sorted(map(review_identity, original["reviews"])))
            self.assertEqual(migrated["zoo"]["residents"], original["zoo"]["residents"])
            self.assertEqual(migrated["zoo"]["exam_history"], original["zoo"]["exam_history"])
            self.assertEqual(migrated["zoo"]["exam"]["answers"], original["zoo"]["exam"]["answers"])
            self.assertEqual(migrated["zoo"]["exam"]["queue"][:10], original["zoo"]["exam"]["queue"])
            self.assertEqual(len(migrated["zoo"]["exam"]["queue"]), 60)
            self.assertEqual(path.read_bytes(), original_bytes)  # A read/export must not rewrite the source.

            exported = root / "portable.json"
            exported.write_bytes(make_backup_bytes(migrated, source.metadata("anna")))
            decoded = read_player_backup_bytes(exported.read_bytes())
            target_path = root / "target.json"
            target = PlayerStore(target_path)
            other = target.create_player("Другой игрок", sibling)
            before = copy.deepcopy(target.load_game(other))
            identity = target.restore_backup(decoded, None)
            self.assertEqual(PlayerStore(target_path).load_game(identity), migrated)
            self.assertEqual(PlayerStore(target_path).load_game(other), before)
            source.save_game("anna", migrated, expected_revision=profile["revision"])
            restarted = PlayerStore(path)
            self.assertEqual(restarted.load_game("anna"), migrated)
            self.assertEqual(restarted.load_game("sibling"), sibling)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["profiles"]["sibling"], document["profiles"]["sibling"])

    def test_legacy_ownerless_copy_preserves_unfinished_six_question_review(self):
        with tempfile.TemporaryDirectory() as directory:
            game = old_game()
            game["zoo"]["exam"] = None
            queue = [word["id"] for word in words_for_species("axolotl")[:6]]
            game["active_review"] = {"species": "axolotl", "milestone": 150, "queue": queue,
                                     "answers": queue[:3], "phase": "feedback"}
            path = Path(directory) / "old-profile.json"
            path.write_text(json.dumps({"format": "sniffer-garden-profile", "version": 1, "game": game}), encoding="utf-8")
            decoded = read_player_backup_bytes(path.read_bytes())
            self.assertIsNone(decoded["player"])
            self.assertEqual(decoded["game"]["active_review"], game["active_review"])
            store_path = Path(directory) / "registered.json"
            store = PlayerStore(store_path)
            identity = store.create_player("Анна", decoded["game"])
            self.assertEqual(PlayerStore(store_path).load_game(identity), decoded["game"])
