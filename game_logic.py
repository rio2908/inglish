"""Saveable game rules independent from pygame."""

import random

from words import WORDS, WORD_BY_ID


CARE_MAX = 3


def new_game():
    return {
        "version": 1,
        "session": 0,
        "correct_answers": 0,
        "cards": {},
        "care": {"food": CARE_MAX, "joy": CARE_MAX, "clean": CARE_MAX},
        "feedings": 0,
        "poop": False,
        "garden_plants": 0,
        "last_food": "seed",
    }


def normalize_game(raw):
    """Ignore corrupt or unknown saved fields without losing valid progress."""
    game = new_game()
    if not isinstance(raw, dict):
        return game
    for key in ("session", "correct_answers", "feedings", "garden_plants"):
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            game[key] = value
    if isinstance(raw.get("last_food"), str):
        game["last_food"] = raw["last_food"]
    if isinstance(raw.get("poop"), bool):
        game["poop"] = raw["poop"]
    if isinstance(raw.get("care"), dict):
        for key in game["care"]:
            value = raw["care"].get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                game["care"][key] = max(0, min(CARE_MAX, value))
    if isinstance(raw.get("cards"), dict):
        for word_id, record in raw["cards"].items():
            if word_id not in WORD_BY_ID or not isinstance(record, dict):
                continue
            sessions = record.get("correct_sessions", [])
            if not isinstance(sessions, list):
                sessions = []
            sessions = sorted({s for s in sessions if isinstance(s, int) and s > 0})
            game["cards"][word_id] = {
                "seen": bool(record.get("seen", False)),
                "correct_sessions": sessions,
            }
    game["garden_plants"] = min(game["garden_plants"], mastered_count(game) // 15)
    return game


def record_for(game, word_id):
    return game["cards"].setdefault(word_id, {"seen": False, "correct_sessions": []})


def mastered(game, word_id):
    record = game["cards"].get(word_id, {})
    return len(record.get("correct_sessions", [])) >= 2


def mastered_count(game):
    return sum(mastered(game, word["id"]) for word in WORDS)


def introduced_count(game):
    return sum(bool(game["cards"].get(word["id"], {}).get("seen")) for word in WORDS)


def hatch_complete(game):
    return game["correct_answers"] >= 5


def egg_frame(game):
    return min(game["correct_answers"], 4)


def growth_stage(game):
    """0 egg, 1 baby, 2 youngster, 3 adult, 4 flowered Sniffer."""
    if not hatch_complete(game):
        return 0
    learned = mastered_count(game)
    if learned >= 120:
        return 4
    if learned >= 80:
        return 3
    if learned >= 40:
        return 2
    return 1


def start_session(game, rng=None):
    rng = rng or random
    game["session"] += 1
    seen_unmastered = [w["id"] for w in WORDS if game["cards"].get(w["id"], {}).get("seen") and not mastered(game, w["id"])]
    rng.shuffle(seen_unmastered)
    review = seen_unmastered[:5]
    new = [w["id"] for w in WORDS if not game["cards"].get(w["id"], {}).get("seen")][:5]
    if len(review) + len(new) < 6:
        known = [w["id"] for w in WORDS if mastered(game, w["id"])]
        rng.shuffle(known)
        review.extend(known[:6 - len(review) - len(new)])
    return review + new


def mark_seen(game, word_id):
    record_for(game, word_id)["seen"] = True


def record_answer(game, word_id, correct):
    """Return True only when this answer newly masters the word."""
    record = record_for(game, word_id)
    record["seen"] = True
    if not correct:
        return False
    was_mastered = mastered(game, word_id)
    game["correct_answers"] += 1
    if game["session"] not in record["correct_sessions"]:
        record["correct_sessions"].append(game["session"])
    return not was_mastered and mastered(game, word_id)


def finish_session(game):
    if hatch_complete(game):
        game["care"]["food"] = max(0, game["care"]["food"] - 1)
        game["care"]["joy"] = max(0, game["care"]["joy"] - 1)


def feed(game, food="seed"):
    if not hatch_complete(game):
        return False
    game["care"]["food"] = CARE_MAX
    game["last_food"] = food
    game["feedings"] += 1
    if game["feedings"] % 2 == 0:
        game["poop"] = True
        game["care"]["clean"] = 0
    return True


def play(game):
    if not hatch_complete(game):
        return False
    game["care"]["joy"] = CARE_MAX
    return True


def clean(game):
    if not hatch_complete(game) or not game["poop"]:
        return False
    game["poop"] = False
    game["care"]["clean"] = CARE_MAX
    return True


def can_explore(game):
    return hatch_complete(game) and all(value > 0 for value in game["care"].values()) and game["garden_plants"] < mastered_count(game) // 15


def explore(game):
    if not can_explore(game):
        return False
    game["garden_plants"] += 1
    game["care"]["food"] = max(0, game["care"]["food"] - 1)
    game["care"]["joy"] = max(0, game["care"]["joy"] - 1)
    return True


def choice_ids(word_id, rng=None):
    rng = rng or random
    word = WORD_BY_ID[word_id]
    same = [w["id"] for w in WORDS if w["chapter"] == word["chapter"] and w["id"] != word_id and w["ru"] != word["ru"]]
    other = [w["id"] for w in WORDS if w["chapter"] != word["chapter"] and w["ru"] != word["ru"]]
    rng.shuffle(same)
    rng.shuffle(other)
    options = [word_id] + same[:2]
    if len(options) < 3:
        options += other[:3 - len(options)]
    rng.shuffle(options)
    return options
