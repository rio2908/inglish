import configparser
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AndroidConfigTests(unittest.TestCase):
    def test_inglish_branding_keeps_the_existing_android_identity(self):
        config = configparser.ConfigParser()
        config.read(ROOT / "buildozer.spec", encoding="utf-8")
        app = config["app"]
        self.assertEqual(app["title"], "EnglishCraft")
        self.assertEqual(app["package.domain"] + "." + app["package.name"], "org.game.sniffergarden")
        for key, size in (("icon.filename", (512, 512)),
                          ("icon.adaptive_foreground.filename", (432, 432)),
                          ("icon.adaptive_background.filename", (432, 432))):
            with self.subTest(key=key):
                content = (ROOT / app[key]).read_bytes()
                self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", content[16:24]), size)

    def test_android_stack_matches_working_mathcraft_configuration(self):
        config = configparser.ConfigParser()
        config.read(ROOT / "buildozer.spec", encoding="utf-8")
        expected = {
            "requirements": "python3==3.10.11,hostpython3==3.10.11,pygame,pyjnius",
            "orientation": "landscape",
            "fullscreen": "1",
            "android.archs": "arm64-v8a",
            "android.minapi": "24",
            "android.api": "34",
            "android.ndk": "25b",
            "android.enable_androidx": "True",
            "p4a.bootstrap": "sdl2",
            "p4a.branch": "v2024.01.21",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(config["app"][key], value)


if __name__ == "__main__":
    unittest.main()
