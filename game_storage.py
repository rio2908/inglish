"""Atomic local saves and validated portable profiles, independent of pygame."""

import json
import os
from pathlib import Path
import sys

from game_logic import new_game, normalize_game


ROOT = Path(__file__).resolve().parent
MAX_BACKUP_BYTES = 2 * 1024 * 1024
WEB_STORAGE_KEY = "sniffer-garden-save-v1"


def save_path():
    if sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ:
        from android.storage import app_storage_path
        return Path(app_storage_path()) / "sniffer_save.json"
    return ROOT / "sniffer_save.json"


def write_game(game, path=None):
    if path is None and sys.platform == "emscripten":
        import platform
        platform.window.localStorage.setItem(WEB_STORAGE_KEY, json.dumps(game, ensure_ascii=False))
        return
    path = Path(path) if path is not None else save_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(game, file, ensure_ascii=False)
        file.flush()
        if sys.platform != "emscripten":
            os.fsync(file.fileno())
    os.replace(temporary, path)


def load_game(path=None):
    if path is None and sys.platform == "emscripten":
        import platform
        try:
            content = platform.window.localStorage.getItem(WEB_STORAGE_KEY)
            if content:
                raw = json.loads(str(content))
                if isinstance(raw, dict):
                    return normalize_game(raw)
        except Exception:
            pass
    target = Path(path) if path is not None else save_path()
    # Migrate saves made by earlier APKs in the unpacked application directory.
    candidates = [target]
    if path is None and target != ROOT / "sniffer_save.json":
        candidates.append(ROOT / "sniffer_save.json")
    for candidate in candidates:
        try:
            with candidate.open("r", encoding="utf-8") as file:
                raw = json.load(file)
            if not isinstance(raw, dict):
                continue
            game = normalize_game(raw)
            if candidate != target:
                write_game(game, target)
            return game
        except (OSError, ValueError, TypeError):
            continue
    return new_game()


def make_backup_bytes(game):
    return json.dumps({"format": "sniffer-garden-profile", "version": 1,
                       "game": normalize_game(game)}, ensure_ascii=False).encode("utf-8")


def read_backup_bytes(content):
    if len(content) > MAX_BACKUP_BYTES:
        raise ValueError("Файл профиля слишком большой")
    try:
        raw = json.loads(content)
    except (ValueError, UnicodeError) as error:
        raise ValueError("Не удалось прочитать JSON профиля") from error
    if (not isinstance(raw, dict) or raw.get("format") != "sniffer-garden-profile"
            or raw.get("version") != 1 or not isinstance(raw.get("game"), dict)):
        raise ValueError("Это не профиль Inglish поддерживаемой версии")
    return normalize_game(raw["game"])
