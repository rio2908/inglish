import os
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from game_backup import EXPORT_REQUEST, IMPORT_REQUEST, ProfilePicker
from game_logic import new_game
from game_storage import make_backup_bytes


class ProfilePickerTests(unittest.TestCase):
    def test_android_document_picker_round_trip(self):
        picker = ProfilePicker()
        activity, current, intent_class = Mock(), Mock(), Mock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "external-profile.json"

            def open_descriptor(uri, mode):
                descriptor = Mock()
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC if mode == "w" else os.O_RDONLY
                flags |= getattr(os, "O_BINARY", 0)
                descriptor.detachFd.return_value = os.open(path, flags, 0o600)
                return descriptor

            current.getContentResolver.return_value.openFileDescriptor.side_effect = open_descriptor
            game = new_game()
            game["pet_name"] = "Листик"
            with patch("game_backup.sys.platform", "android"), patch.object(picker, "_android", return_value=(activity, current, intent_class)):
                picker.start(True, game)
                current.startActivityForResult.assert_called_with(intent_class.return_value, EXPORT_REQUEST)
                picker._on_activity_result(EXPORT_REQUEST, -1, Mock())
                message, imported = picker.poll()
                self.assertIn("сохранён", message)
                self.assertIsNone(imported)
                self.assertTrue(path.exists())
                picker.start(False, new_game())
                current.startActivityForResult.assert_called_with(intent_class.return_value, IMPORT_REQUEST)
                picker._on_activity_result(IMPORT_REQUEST, -1, Mock())
                _, imported = picker.poll()
                self.assertEqual(imported, game)
                self.assertIsNone(picker.pending)
                activity.bind.assert_called_once()

    def test_cancelled_picker_does_not_import_anything(self):
        picker = ProfilePicker()
        picker.pending = True
        picker._on_activity_result(IMPORT_REQUEST, 0, None)
        message, imported = picker.poll()
        self.assertIn("отменён", message)
        self.assertIsNone(imported)
        self.assertIsNone(picker.pending)

    def test_browser_profile_import_is_validated(self):
        picker = ProfilePicker()
        window = SimpleNamespace(eval=Mock(), snifferProfileResult=None)
        game = new_game()
        game["pet_name"] = "Листик"
        with patch("game_backup.sys.platform", "emscripten"), patch("platform.window", window, create=True):
            picker.start(False, new_game())
            self.assertTrue(picker.web_pending)
            window.snifferProfileResult = json.dumps({"content": make_backup_bytes(game).decode("utf-8")})
            _, imported = picker.poll()
            self.assertEqual(imported, game)
            self.assertFalse(picker.web_pending)
            picker.start(False, new_game())
            window.snifferProfileResult = json.dumps({"content": "not JSON"})
            message, imported = picker.poll()
            self.assertIn("Ошибка", message)
            self.assertIsNone(imported)


if __name__ == "__main__":
    unittest.main()
