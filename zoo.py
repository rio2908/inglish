"""Sequential creature collection; shared vocabulary and statistics are never reset."""

import copy
import random
from grammar import form_choices

from words import WORD_BY_ID, words_for_species


SPECIES = (
    ("sniffer", "Сниффер"), ("axolotl", "Аксолотль"), ("fox", "Лиса"),
    ("bee", "Пчела"), ("turtle", "Черепаха"), ("allay", "Эллей"),
)
SPECIES_NAMES = dict(SPECIES)


def new_zoo():
    return {"active": "sniffer", "residents": [], "pet_cards": {}, "pet_correct_answers": 0,
            "exam": None, "exam_history": [], "replay": False, "suspended": None, "cycle": 0, "serial": 0}


def normalize_zoo(raw, allow_replay=True):
    zoo = new_zoo()
    if not isinstance(raw, dict):
        return zoo
    residents = raw.get("residents")
    if isinstance(residents, list):
        for expected, record in zip(SPECIES, residents):
            if not isinstance(record, dict) or record.get("species") != expected[0]:
                break
            name = record.get("name")
            name = " ".join("".join(c for c in name if c.isprintable()).split())[:20] if isinstance(name, str) else ""
            zoo["residents"].append({"species": expected[0], "name": name or expected[1]})
            if type(record.get("grown")) is int and record["grown"] > 1:
                zoo["residents"][-1]["grown"] = record["grown"]
    zoo["active"] = SPECIES[min(len(zoo["residents"]), len(SPECIES) - 1)][0]
    for key in ("cycle", "serial"):
        if type(raw.get(key)) is int and raw[key] >= 0:
            zoo[key] = raw[key]
    zoo["serial"] = max(zoo["serial"], zoo["cycle"])
    suspended = raw.get("suspended")
    if (allow_replay and raw.get("replay") is True and isinstance(suspended, dict)
            and isinstance(suspended.get("zoo"), dict)
            and isinstance(raw.get("active"), str) and raw["active"] in {item["species"] for item in zoo["residents"]}):
        previous = normalize_zoo(suspended["zoo"], allow_replay=False)
        zoo["active"] = raw["active"]
        zoo["replay"] = True
        zoo["suspended"] = {"zoo": previous, "pet_name": suspended.get("pet_name") if isinstance(suspended.get("pet_name"), str) else SPECIES_NAMES[previous["active"]],
                            "care": {key: max(0, min(3, suspended.get("care", {}).get(key, 3)))
                                     if isinstance(suspended.get("care"), dict) and type(suspended["care"].get(key, 3)) is int else 3
                                     for key in ("food", "joy", "clean")},
                            "feedings": suspended.get("feedings", 0) if type(suspended.get("feedings", 0)) is int else 0,
                            "poop": suspended.get("poop") is True,
                            "last_food": suspended.get("last_food") if isinstance(suspended.get("last_food"), str) else "seed",
                            "growth_notice": copy.deepcopy(suspended.get("growth_notice")) if isinstance(suspended.get("growth_notice"), dict) else None}
    if raw.get("active", zoo["active"]) != zoo["active"]:
        return zoo
    value = raw.get("pet_correct_answers")
    if type(value) is int and value >= 0:
        zoo["pet_correct_answers"] = value
    cards = raw.get("pet_cards")
    if isinstance(cards, dict):
        for word_id, record in cards.items():
            if word_id not in WORD_BY_ID or WORD_BY_ID[word_id]["species"] != zoo["active"] or not isinstance(record, dict):
                continue
            sessions = record.get("correct_sessions")
            if isinstance(sessions, list):
                zoo["pet_cards"][word_id] = {"correct_sessions": sorted({s for s in sessions if type(s) is int and s > 0})}
    history = raw.get("exam_history")
    if isinstance(history, list):
        for result in history:
            if (isinstance(result, dict) and isinstance(result.get("species"), str) and result["species"] in SPECIES_NAMES
                    and type(result.get("score")) is int and 0 <= result["score"] <= 10
                    and type(result.get("cycle", 0)) is int and 0 <= result.get("cycle", 0) <= zoo["serial"]):
                zoo["exam_history"].append({"species": result["species"], "cycle": result.get("cycle", 0), "score": result["score"], "total": 10})
    exam = raw.get("exam")
    if isinstance(exam, dict):
        queue, answers = exam.get("queue"), exam.get("answers")
        if (isinstance(queue, list) and len(queue) == 10
                and all(isinstance(word_id, str) and word_id in WORD_BY_ID and WORD_BY_ID[word_id]["species"] == zoo["active"] for word_id in queue)
                and len(set(queue)) == 10 and isinstance(answers, list) and len(answers) <= 10
                and all(isinstance(word_id, str) and word_id in WORD_BY_ID for word_id in answers)):
            phase = exam.get("phase")
            if phase not in ("quiz", "feedback", "summary") or (phase == "feedback" and not answers) or (phase == "summary" and len(answers) < 10):
                phase = "quiz"
            if len(answers) == 10 and phase == "quiz":
                phase = "feedback"
            zoo["exam"] = {"queue": queue[:], "answers": answers[:], "phase": phase}
    return zoo


def current_species(game):
    return game["zoo"]["active"]


def pet_learned_count(game):
    cards = game["zoo"]["pet_cards"] if game["zoo"]["replay"] else game["cards"]
    return sum(len(cards.get(word["id"], {}).get("correct_sessions", [])) >= 2 for word in words_for_species(current_species(game)))


def pet_answers(game):
    return game["correct_answers"] if current_species(game) == "sniffer" and not game["zoo"]["replay"] else game["zoo"]["pet_correct_answers"]


def record_pet_answer(game, word_id, correct):
    if (current_species(game) == "sniffer" and not game["zoo"]["replay"]) or WORD_BY_ID[word_id]["species"] != current_species(game):
        return False
    record = game["zoo"]["pet_cards"].setdefault(word_id, {"correct_sessions": []})
    was_learned = len(record["correct_sessions"]) >= 2
    if correct:
        game["zoo"]["pet_correct_answers"] += 1
        if game["session"] not in record["correct_sessions"]:
            record["correct_sessions"].append(game["session"])
    return not was_learned and len(record["correct_sessions"]) >= 2


def growth_complete(game):
    return ((len(game["zoo"]["residents"]) < len(SPECIES) or game["zoo"]["replay"])
            and pet_learned_count(game) == 150
            and game["lesson"] is None and game["active_review"] is None)


def final_score(game):
    exam = game["zoo"]["exam"]
    return sum(a == b for a, b in zip(exam["queue"], exam["answers"])) if exam else 0


def final_passed(game):
    exam = game["zoo"]["exam"]
    return bool(exam and len(exam["answers"]) == 10 and final_score(game) >= 7)


def ready_for_zoo(game):
    return growth_complete(game) and final_passed(game)


def start_final_test(game, rng=None, retry=False):
    if not growth_complete(game):
        return None
    old = game["zoo"]["exam"]
    if old and (old["phase"] != "summary" or not retry or final_passed(game)):
        return old
    rng = rng or random
    pool = [word["id"] for word in words_for_species(current_species(game))]
    queue = [word_id for word_id in game["repeat_words"] if word_id in pool][:10]
    queue += rng.sample([word_id for word_id in pool if word_id not in queue], 10 - len(queue))
    rng.shuffle(queue)
    game["zoo"]["exam"] = {"queue": queue, "answers": [], "phase": "quiz"}
    return game["zoo"]["exam"]


def final_choices(game, rng=None):
    exam = game["zoo"]["exam"]
    if not exam or exam["phase"] != "quiz":
        return []
    rng = rng or random
    expected = exam["queue"][len(exam["answers"])]
    contextual = form_choices(expected, rng)
    if contextual is not None:
        return contextual
    pool = [word["id"] for word in words_for_species(current_species(game))
            if word["id"] != expected and word["ru"] != WORD_BY_ID[expected]["ru"]]
    choices = [expected] + rng.sample(pool, 2)
    rng.shuffle(choices)
    return choices


def answer_final_test(game, chosen):
    exam = game["zoo"]["exam"]
    if not exam or exam["phase"] != "quiz" or not isinstance(chosen, str) or chosen not in WORD_BY_ID or len(exam["answers"]) >= 10:
        return False
    # Deferred import avoids coupling basic zoo state to the statistics module at load time.
    from learning_stats import record_attempt
    expected = exam["queue"][len(exam["answers"])]
    record_attempt(game, expected, chosen == expected, review=True)
    exam["answers"].append(chosen)
    exam["phase"] = "feedback"
    if len(exam["answers"]) == 10:
        game["zoo"]["exam_history"].append({"species": current_species(game), "cycle": game["zoo"]["cycle"], "score": final_score(game), "total": 10})
    return True


def advance_final_test(game):
    exam = game["zoo"]["exam"]
    if exam and exam["phase"] == "feedback":
        exam["phase"] = "summary" if len(exam["answers"]) == 10 else "quiz"


def _fresh_pet(game):
    game["pet_name"] = SPECIES_NAMES[current_species(game)]
    game["care"] = {"food": 3, "joy": 3, "clean": 3}
    game["feedings"], game["poop"], game["last_food"] = 0, False, "seed"
    game["zoo"]["pet_cards"], game["zoo"]["pet_correct_answers"], game["zoo"]["exam"] = {}, 0, None


def can_replay(game, index):
    exam = game["zoo"]["exam"]
    return (type(index) is int and 0 <= index < len(game["zoo"]["residents"]) and not game["zoo"]["replay"]
            and game["lesson"] is None and game["active_review"] is None
            and (exam is None or exam["phase"] == "summary"))


def begin_replay(game, index):
    if not can_replay(game, index):
        return False
    zoo = game["zoo"]
    snapshot = {key: copy.deepcopy(game[key]) for key in ("pet_name", "care", "feedings", "poop", "last_food", "zoo", "growth_notice")}
    zoo["suspended"] = snapshot
    zoo["active"] = zoo["residents"][index]["species"]
    zoo["replay"] = True
    zoo["serial"] += 1
    zoo["cycle"] = zoo["serial"]
    _fresh_pet(game)
    game["growth_notice"] = None
    return True


def settle_pet(game):
    if not ready_for_zoo(game):
        return False
    zoo = game["zoo"]
    game["growth_notice"] = None
    if zoo["replay"]:
        resident = next(item for item in zoo["residents"] if item["species"] == zoo["active"])
        resident["grown"] = resident.get("grown", 1) + 1
        snapshot = zoo["suspended"]
        previous = copy.deepcopy(snapshot["zoo"])
        previous["residents"], previous["exam_history"], previous["serial"] = zoo["residents"], zoo["exam_history"], zoo["serial"]
        for key in ("pet_name", "care", "feedings", "poop", "last_food", "growth_notice"):
            game[key] = copy.deepcopy(snapshot[key])
        game["zoo"] = previous
        return True
    zoo["residents"].append({"species": zoo["active"], "name": game["pet_name"]})
    if len(zoo["residents"]) < len(SPECIES):
        zoo["active"] = SPECIES[len(zoo["residents"])][0]
        zoo["cycle"] = 0
        _fresh_pet(game)
    else:
        zoo["exam"] = None
    return True
