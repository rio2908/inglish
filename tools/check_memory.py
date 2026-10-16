"""Repeat UI workloads using temporary profiles; report Python and native memory.

Run from the repository: python tools/check_memory.py --batches 6 --frames 120
No system TTS, file picker, real saves, or player progress is used.
"""

import argparse
import ctypes
import gc
import json
import os
from pathlib import Path
import sys
import tempfile
import tracemalloc

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame

import main
from game_logic import new_game
from player_profiles import PlayerStore
from words import ALL_WORDS
from zoo import SPECIES


class Counters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


if sys.platform == "win32":
    KERNEL = ctypes.WinDLL("kernel32", use_last_error=True)
    PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
    KERNEL.GetCurrentProcess.restype = ctypes.c_void_p
    PSAPI.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]


def working_set_bytes():
    """Current resident memory on Windows (not peak RSS); unavailable elsewhere."""
    if sys.platform != "win32":
        return None
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not PSAPI.GetProcessMemoryInfo(KERNEL.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.WorkingSetSize


def cache_state(app):
    caches = {"sprites": app.sprites.cache, "habitats": app.habitats.cache, "pictures": app.word_pictures.cache}
    return {"entries": {name: len(cache) for name, cache in caches.items()},
            "surface_bytes": sum(surface.get_pitch() * surface.get_height()
                                 for cache in caches.values() for surface in cache.values() if surface is not None)}


def exercise(app, frames):
    """Fixed workload: no accumulating attempts or intended learning history."""
    for word in ALL_WORDS:
        app.word_pictures.picture(word["id"])
    for frame in range(frames):
        screen = frame % 6
        if screen == 0:
            app.screen = "home"
            app.hearts.emit(400, 400, pygame.time.get_ticks() / 1000)
        elif screen == 1:
            app.open_statistics()
        elif screen == 2:
            app.open_dictionary()
        elif screen == 3:
            app.open_zoo()
        elif screen == 4:
            app.start_play()
            app.play_choice(0)
        else:
            app.open_help()
        app.draw()
        pygame.event.clear()


def audit(batches, frames):
    with tempfile.TemporaryDirectory() as directory:
        store = PlayerStore(Path(directory) / "players.json")
        game = new_game()
        game["session"] = 2
        game["cards"] = {word["id"]: {"seen": True, "correct_sessions": [1, 2]} for word in ALL_WORDS}
        game["zoo"]["residents"] = [{"species": key, "name": name} for key, name in SPECIES]
        game["zoo"]["active"] = "allay"
        identities = [store.create_player(name, game=game) for name in ("Memory A", "Memory B")]
        app = main.GameApp(profile_store=store)
        samples = []
        try:
            tracemalloc.start()
            for batch in range(batches + 1):
                app.enter_player(identities[batch % 2])
                exercise(app, frames)
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                samples.append({"batch": batch, "python_bytes": current, "python_peak_bytes": peak,
                                "working_set_bytes": working_set_bytes(), "caches": cache_state(app),
                                "buttons": len(app.buttons), "particles": len(app.hearts.particles)})
            return {"frames": (batches + 1) * frames, "samples": samples,
                    "note": "batch 0 warms caches; tracemalloc excludes SDL/JVM memory; Windows working set includes native allocations"}
        finally:
            tracemalloc.stop()
            app.profile_picker.close()
            app.speech.shutdown()
            pygame.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=6)
    parser.add_argument("--frames", type=int, default=120)
    args = parser.parse_args()
    if args.batches < 1 or args.frames < 6:
        parser.error("Use at least one measured batch and six frames per batch")
    print(json.dumps(audit(args.batches, args.frames), indent=2))
