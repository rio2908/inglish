"""Real JSON/descriptors and UI/store integration; Android classes are simulated."""

import copy
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
    raise unittest.SkipTest("UI profile integration needs pygame")

import main
from game_backup import EXPORT_REQUEST, IMPORT_REQUEST
from game_logic import new_game, normalize_game, record_answer
from game_storage import make_backup_bytes, read_player_backup_bytes
from learning_stats import advance_review, answer_review, start_review
from player_profiles import PlayerStore
from words import WORDS, words_for_species
from zoo import advance_final_test, answer_final_test, begin_replay, settle_pet, start_final_test
from learning_fixtures import clear_checkpoints
from assessments import expected_word
from learning_stats import repair_review
from zoo import repair_final_test


def learn(game, count, checks=True):
    for _ in range(2):
        game["session"] += 1
        for word in words_for_species(game["zoo"]["active"])[:count]:
            record_answer(game, word["id"], True)
            if checks:
                clear_checkpoints(game)
    game["growth_notice"] = None


def scenario(kind):
    game = new_game()
    if kind.startswith("lesson-"):
        learn(game, 7)
        game["session"] += 1
        phase = kind.split("-", 1)[1]
        if phase != "intro":
            game["cards"]["cat"] = {"seen": True, "correct_sessions": []}
        if phase == "result":
            record_answer(game, "cat", True)
        game["lesson"] = {"queue": ["cat", "dog"], "index": 0, "phase": phase,
                          "mode": "meaning", "correct": phase == "result", "answers": int(phase == "result")}
    elif kind.startswith("review-"):
        learn(game, 50, checks=False)
        review = start_review(game)
        if kind == "review-feedback":
            answer_review(game, review["queue"][0])
        elif kind == "review-summary" or "repair" in kind:
            for i, expected in enumerate(review["queue"][:]):
                wrong = next(word["id"] for word in WORDS if word["id"] != expected)
                answer_review(game, wrong if "repair" in kind and i >= 14 else expected)
                advance_review(game)
            if "repair" in kind:
                repair_review(game)
                if not kind.endswith("intro"):
                    advance_review(game)
                if kind.endswith("feedback"):
                    answer_review(game, expected_word(review))
    elif kind.startswith("final-"):
        learn(game, 150)
        exam = start_final_test(game)
        if kind == "final-feedback":
            answer_final_test(game, exam["queue"][0])
        elif kind == "final-summary" or "repair" in kind:
            for i, expected in enumerate(exam["queue"][:]):
                wrong = next(word["id"] for word in WORDS if word["id"] != expected)
                answer_final_test(game, expected if i < 35 else wrong)
                advance_final_test(game)
            if "repair" in kind:
                repair_final_test(game)
                if not kind.endswith("intro"):
                    advance_final_test(game)
                if kind.endswith("feedback"):
                    answer_final_test(game, expected_word(exam))
    elif kind == "growth":
        learn(game, 29)
        game["session"] += 1
        target = WORDS[29]["id"]
        game["cards"][target] = {"seen": True, "correct_sessions": [game["session"] - 1]}
        record_answer(game, target, True)
        game["lesson"] = {"queue": [target, "tree"], "index": 0, "phase": "result", "mode": "meaning", "correct": True, "answers": 1}
    elif kind == "replay":
        learn(game, 150)
        exam = start_final_test(game)
        for expected in exam["queue"][:]:
            answer_final_test(game, expected)
            advance_final_test(game)
        assert settle_pet(game)
        learn(game, 60)
        game["pet_name"] = "Розочка"
        assert begin_replay(game, 0)
        learn(game, 13)
        game["session"] += 1
        game["lesson"] = {"queue": ["cat", "dog"], "index": 1, "phase": "quiz", "mode": "meaning", "correct": False, "answers": 0}
    else:
        raise AssertionError(kind)
    game["pet_name"] = "Листик"
    game["care"] = {"food": 1, "joy": 2, "clean": 0}
    game["poop"] = True
    return game


class AndroidDocument:
    def __init__(self, path):
        self.path = path
        self.activity, self.current, self.intent = Mock(), Mock(), Mock()
        self.modes = []
        self.current.getContentResolver.return_value.openFileDescriptor.side_effect = self.open_descriptor

    def api(self):
        return self.activity, self.current, self.intent

    def open_descriptor(self, uri, mode):
        self.modes.append(mode)
        # Deliberately retain old bytes for writable descriptors: the bridge must
        # truncate seekable files itself as well as requesting Android's 'wt'.
        flags = os.O_WRONLY | os.O_CREAT if mode.startswith("w") else os.O_RDONLY
        flags |= getattr(os, "O_BINARY", 0)
        descriptor = Mock()
        descriptor.detachFd.return_value = os.open(self.path, flags, 0o600)
        return descriptor


class AndroidProfileRoundTripTests(unittest.TestCase):
    def test_android_export_import_preserves_complete_state_across_all_progress_phases(self):
        expected_screens = {
            "lesson-intro": "cards", "lesson-quiz": "cards", "lesson-result": "cards",
            "review-feedback": "review", "review-summary": "review",
            "final-quiz": "final_test", "final-feedback": "final_test", "final-summary": "home",
            "growth": "growth", "replay": "cards",
            "review-repair-intro": "review", "review-repair-quiz": "review", "review-repair-feedback": "review",
            "final-repair-intro": "final_test", "final-repair-quiz": "final_test", "final-repair-feedback": "final_test",
        }
        for kind, expected_screen in expected_screens.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source_store, target_store = PlayerStore(root / "source.json"), PlayerStore(root / "android.json")
                identity = source_store.create_player("Ксюша")
                source = main.GameApp(profile_store=source_store)
                target = reopened = None
                try:
                    source.enter_player(identity)
                    game = scenario(kind)
                    # These are valid states produced by model actions, not an
                    # already-normalized fixture that could hide lost fields.
                    self.assertEqual(normalize_game(game), game)
                    source.activate_game(game)
                    source.speech.speak = Mock(return_value=True)
                    source.open_profile()
                    expected = copy.deepcopy(source.game)
                    document = AndroidDocument(root / "backup.json")
                    document.path.write_bytes(b"stale longer document" * 12000)
                    with patch("game_backup.sys.platform", "android"), patch.object(source.profile_picker, "_android", side_effect=document.api):
                        source.transfer_profile(True)
                        source.profile_picker._on_activity_result(EXPORT_REQUEST, -1, Mock())
                        source.poll_profile()
                    decoded = read_player_backup_bytes(document.path.read_bytes())
                    self.assertEqual(decoded["player"], {"id": identity, "name": "Ксюша"})
                    self.assertEqual(decoded["game"], expected)
                    self.assertEqual(source_store.load_game(identity), expected)
                    self.assertEqual(document.modes, ["wt"])

                    target = main.GameApp(profile_store=target_store)
                    target.open_login()
                    with patch("game_backup.sys.platform", "android"), patch.object(target.profile_picker, "_android", side_effect=document.api):
                        target.transfer_profile(False)
                        target.profile_picker._on_activity_result(IMPORT_REQUEST, -1, Mock())
                        target.poll_profile()
                    self.assertEqual(target.screen, "import")
                    self.assertIsNone(target.player_id)
                    self.assertEqual(target_store.list_players(), [])
                    target.accept_import()
                    self.assertEqual(target.player_id, identity)
                    self.assertEqual(target.player_name, "Ксюша")
                    self.assertEqual(target.game, expected)
                    self.assertEqual(target.screen, expected_screen)
                    self.assertEqual(target_store.load_game(identity), expected)

                    reopened = main.GameApp(profile_store=PlayerStore(root / "android.json"))
                    reopened.enter_player(identity)
                    self.assertEqual(reopened.game, expected)
                    self.assertEqual(reopened.screen, expected_screen)
                finally:
                    for app in (source, target, reopened):
                        if app is not None:
                            app.speech.shutdown()
                    pygame.quit()

    def test_android_import_replaces_only_the_selected_matching_player(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = PlayerStore(root / "android.json")
            local_id = store.create_player("Ксюша")
            sibling_id = store.create_player("Ваня")
            sibling = store.load_game(sibling_id)
            sibling["pet_name"] = "Не менять"
            store.save_game(sibling_id, sibling)
            app = main.GameApp(profile_store=store)
            try:
                app.enter_player(sibling_id)
                game = scenario("replay")
                owner = {"id": "id-from-another-device", "name": "Ксюша"}
                document = AndroidDocument(root / "backup.json")
                document.path.write_bytes(make_backup_bytes(game, owner))

                def import_file():
                    with patch("game_backup.sys.platform", "android"), patch.object(app.profile_picker, "_android", side_effect=document.api):
                        app.transfer_profile(False)
                        app.profile_picker._on_activity_result(IMPORT_REQUEST, -1, Mock())
                        app.poll_profile()

                import_file()
                app.accept_import()
                self.assertEqual(app.player_id, sibling_id)
                self.assertEqual(store.load_game(sibling_id), sibling)
                self.assertEqual(store.load_game(local_id), new_game())

                app.open_login()
                app.enter_player(local_id)
                import_file()
                app.accept_import()
                self.assertEqual(app.player_id, local_id)
                self.assertEqual(app.game, game)
                self.assertEqual(store.load_game(local_id), game)
                self.assertEqual(store.load_game(sibling_id), sibling)
            finally:
                app.speech.shutdown()
                pygame.quit()

    def test_android_legacy_copy_without_owner_preserves_rich_state_after_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = PlayerStore(root / "android.json")
            app = main.GameApp(profile_store=store)
            try:
                app.open_login()
                game = scenario("replay")
                document = AndroidDocument(root / "legacy.json")
                document.path.write_bytes(make_backup_bytes(game))
                with patch("game_backup.sys.platform", "android"), patch.object(app.profile_picker, "_android", side_effect=document.api):
                    app.transfer_profile(False)
                    app.profile_picker._on_activity_result(IMPORT_REQUEST, -1, Mock())
                    app.poll_profile()
                app.accept_import()
                self.assertEqual(app.screen, "register")
                self.assertEqual(store.list_players(), [])
                app.registration_input = "Вика"
                app.submit_registration()
                self.assertEqual(app.player_name, "Вика")
                self.assertEqual(app.game, game)
                self.assertEqual(store.load_game(app.player_id), game)
            finally:
                app.speech.shutdown()
                pygame.quit()


if __name__ == "__main__":
    unittest.main()
