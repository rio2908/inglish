"""Saveable game rules independent from pygame."""

import random
from grammar import form_choices

from learning_stats import normalize_progress, record_attempt
from words import ALL_WORDS, WORD_BY_ID, words_for_species
from zoo import current_species, new_zoo, normalize_zoo, pet_learned_count, record_pet_answer


CARE_MAX = 3
GROWTH_THRESHOLDS = (30, 60, 90, 120)


def new_game():
    return {
        "version": 1,
        "pet_name": "Сниффер",
        "lesson": None,
        "growth_notice": None,
        "word_stats": {},
        "repeat_words": [],
        "learned_order": [],
        "reviews": [],
        "active_review": None,
        "session": 0,
        "correct_answers": 0,
        "cards": {},
        "care": {"food": CARE_MAX, "joy": CARE_MAX, "clean": CARE_MAX},
        "feedings": 0,
        "poop": False,
        "garden_plants": 0,
        "last_food": "seed",
        "zoo": new_zoo(),
    }


def normalize_game(raw):
    """Ignore corrupt or unknown saved fields without losing valid progress."""
    game = new_game()
    if not isinstance(raw, dict):
        return game
    if isinstance(raw.get("pet_name"), str):
        game["pet_name"] = clean_pet_name(raw["pet_name"]) or "Сниффер"
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
            sessions = sorted({s for s in sessions if type(s) is int and s > 0})
            game["cards"][word_id] = {
                "seen": bool(record.get("seen", False)),
                "correct_sessions": sessions,
            }
    game["garden_plants"] = min(game["garden_plants"], 10, mastered_count(game) // 15)
    lesson = raw.get("lesson")
    if isinstance(lesson, dict):
        queue = lesson.get("queue")
        index = lesson.get("index")
        if (isinstance(queue, list) and 0 < len(queue) <= 150
                and all(isinstance(word, str) and word in WORD_BY_ID for word in queue)
                and type(index) is int and 0 <= index < len(queue)):
            game["lesson"] = {
                "queue": queue[:], "index": index,
                "phase": lesson.get("phase") if lesson.get("phase") in ("intro", "quiz", "result") else "intro",
                "mode": "spelling" if lesson.get("mode") == "spelling" else "meaning",
                "correct": lesson.get("correct") is True,
                "answers": max(0, min(len(queue), lesson.get("answers", 0))) if type(lesson.get("answers")) is int else 0,
            }
    game["zoo"] = normalize_zoo(raw.get("zoo"))
    normalize_progress(game, raw)
    notice = raw.get("growth_notice")
    if (isinstance(notice, dict) and notice.get("species") == current_species(game)
            and notice.get("cycle", 0) == game["zoo"]["cycle"]
            and type(notice.get("before")) is int and 0 <= notice["before"] < 4
            and type(notice.get("after")) is int
            and notice.get("after") == notice["before"] + 1
            and growth_stage(game) >= notice["after"]):
        game["growth_notice"] = {"species": current_species(game), "cycle": game["zoo"]["cycle"],
                                 "before": notice["before"], "after": notice["after"]}
    return game


def clean_pet_name(value):
    return " ".join("".join(char for char in value if char.isprintable()).split())[:20]


def growth_remaining(game):
    """Return the next growth goal without mixing answers and learned words."""
    if not hatch_complete(game):
        return "hatch_words", max(0, GROWTH_THRESHOLDS[0] - pet_learned_count(game))
    learned = pet_learned_count(game)
    for goal in GROWTH_THRESHOLDS[1:]:
        if learned < goal:
            return "words", goal - learned
    return "complete", 0


def record_for(game, word_id):
    return game["cards"].setdefault(word_id, {"seen": False, "correct_sessions": []})


def mastered(game, word_id):
    record = game["cards"].get(word_id, {})
    return len(record.get("correct_sessions", [])) >= 2


def mastered_count(game):
    return sum(mastered(game, word["id"]) for word in ALL_WORDS)


def introduced_count(game):
    return sum(bool(game["cards"].get(word["id"], {}).get("seen")) for word in ALL_WORDS)


def hatch_complete(game):
    return pet_learned_count(game) >= GROWTH_THRESHOLDS[0]


def egg_frame(game):
    return min(pet_learned_count(game) // max(1, GROWTH_THRESHOLDS[0] // 5), 4)


def growth_stage(game):
    """0 egg, 1 baby, 2 youngster, 3 adult, 4 flowered Sniffer."""
    if not hatch_complete(game):
        return 0
    learned = pet_learned_count(game)
    if learned >= GROWTH_THRESHOLDS[3]:
        return 4
    if learned >= GROWTH_THRESHOLDS[2]:
        return 3
    if learned >= GROWTH_THRESHOLDS[1]:
        return 2
    return 1


def start_session(game, rng=None):
    rng = rng or random
    game["session"] += 1
    pool = words_for_species(current_species(game))
    if game["zoo"]["replay"]:
        cards = game["zoo"]["pet_cards"]
        waiting = [word["id"] for word in pool if len(cards.get(word["id"], {}).get("correct_sessions", [])) < 2]
        rng.shuffle(waiting)
        return waiting[:6] or rng.sample([word["id"] for word in pool], 6)
    seen_unmastered = [w["id"] for w in pool if game["cards"].get(w["id"], {}).get("seen") and not mastered(game, w["id"])]
    rng.shuffle(seen_unmastered)
    review = seen_unmastered[:5]
    new = [w["id"] for w in pool if not game["cards"].get(w["id"], {}).get("seen")][:5]
    if len(review) + len(new) < 6:
        known = [w["id"] for w in pool if mastered(game, w["id"])]
        rng.shuffle(known)
        review.extend(known[:6 - len(review) - len(new)])
    return review + new


def mark_seen(game, word_id):
    record_for(game, word_id)["seen"] = True


def record_answer(game, word_id, correct):
    """Track global learning and the current pet; return its newly learned word."""
    before_stage = growth_stage(game)
    record = record_for(game, word_id)
    record["seen"] = True
    record_attempt(game, word_id, correct)
    newly_pet_learned = record_pet_answer(game, word_id, correct)
    if not correct:
        return False
    was_mastered = mastered(game, word_id)
    game["correct_answers"] += 1
    if game["session"] not in record["correct_sessions"]:
        record["correct_sessions"].append(game["session"])
    newly_mastered = not was_mastered and mastered(game, word_id)
    if newly_mastered and word_id not in game["learned_order"]:
        game["learned_order"].append(word_id)
    after_stage = growth_stage(game)
    if after_stage > before_stage:
        game["growth_notice"] = {"species": current_species(game), "cycle": game["zoo"]["cycle"],
                                 "before": before_stage, "after": after_stage}
    return newly_pet_learned if game["zoo"]["replay"] else newly_mastered


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
    return hatch_complete(game) and all(value > 0 for value in game["care"].values()) and game["garden_plants"] < min(10, mastered_count(game) // 15)


def explore(game):
    if not can_explore(game):
        return False
    game["garden_plants"] += 1
    game["care"]["food"] = max(0, game["care"]["food"] - 1)
    game["care"]["joy"] = max(0, game["care"]["joy"] - 1)
    return True


def choice_ids(word_id, rng=None):
    rng = rng or random
    contextual = form_choices(word_id, rng)
    if contextual is not None:
        return contextual
    word = WORD_BY_ID[word_id]
    pool = words_for_species(word["species"])
    same = [w["id"] for w in pool if w["chapter"] == word["chapter"] and w["id"] != word_id and w["ru"] != word["ru"]]
    other = [w["id"] for w in pool if w["chapter"] != word["chapter"] and w["ru"] != word["ru"]]
    rng.shuffle(same)
    rng.shuffle(other)
    options = [word_id] + same[:2]
    if len(options) < 3:
        options += other[:3 - len(options)]
    rng.shuffle(options)
    return options
