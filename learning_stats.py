"""Learning statistics and mandatory, resumable checkpoints at 50/100/150 words."""

import random
from grammar import form_choices
from assessments import (advance_correction, answer_correction, corrected, expected_word,
                         normalize_test, passed, score, start_corrections)

from words import ALL_WORDS, WORD_BY_ID, words_for_species
from zoo import SPECIES_NAMES, current_species, pet_learned_count


MILESTONES = (50, 100, 150)
REVIEW_SIZE = 20
COUNTERS = ("lesson_attempts", "lesson_correct", "review_attempts", "review_correct")


def review_learned_ids(game):
    pool = words_for_species(current_species(game))
    cards = game["zoo"]["pet_cards"] if game["zoo"]["replay"] else game["cards"]
    learned = {word["id"] for word in pool if len(cards.get(word["id"], {}).get("correct_sessions", [])) >= 2}
    return [word_id for word_id in learned_ids(game) if word_id in learned]


def review_species(review):
    return review.get("species", "sniffer")


def review_cycle(review):
    return review.get("cycle", 0)


def learned_ids(game):
    known = {word["id"] for word in ALL_WORDS
             if len(game["cards"].get(word["id"], {}).get("correct_sessions", [])) >= 2}
    ordered = []
    for word_id in game.get("learned_order", []) + [word["id"] for word in ALL_WORDS]:
        if word_id in known and word_id not in ordered:
            ordered.append(word_id)
    return ordered


def record_attempt(game, word_id, correct, review=False):
    stats = game.setdefault("word_stats", {}).setdefault(word_id, dict.fromkeys(COUNTERS, 0))
    prefix = "review" if review else "lesson"
    stats[prefix + "_attempts"] += 1
    stats[prefix + "_correct"] += int(bool(correct))
    repeat = game.setdefault("repeat_words", [])
    if not correct:
        # Move tested mistakes to the back so larger backlogs get a fair turn.
        if word_id in repeat:
            repeat.remove(word_id)
        repeat.append(word_id)
    elif review and word_id in repeat:
        repeat.remove(word_id)


def normalize_progress(game, raw):
    stats = raw.get("word_stats")
    if isinstance(stats, dict):
        for word_id, record in stats.items():
            if word_id not in WORD_BY_ID or not isinstance(record, dict):
                continue
            clean = {key: record[key] if type(record.get(key)) is int and record[key] >= 0 else 0 for key in COUNTERS}
            for prefix in ("lesson", "review"):
                clean[prefix + "_correct"] = min(clean[prefix + "_correct"], clean[prefix + "_attempts"])
            game["word_stats"][word_id] = clean
    order = raw.get("learned_order")
    if isinstance(order, list):
        game["learned_order"] = [word_id for word_id in order if isinstance(word_id, str) and word_id in WORD_BY_ID]
    game["learned_order"] = learned_ids(game)
    repeat = raw.get("repeat_words")
    if isinstance(repeat, list):
        for word_id in repeat:
            if (isinstance(word_id, str) and word_id in WORD_BY_ID and word_id not in game["repeat_words"]
                    and (game["cards"].get(word_id, {}).get("seen") or word_id in game["word_stats"])):
                game["repeat_words"].append(word_id)
    count = pet_learned_count(game)
    species = current_species(game)
    archived = {resident["species"] for resident in game["zoo"]["residents"]}
    waiting = game["zoo"].get("suspended")
    waiting_context = None
    waiting_count = 0
    if game["zoo"]["replay"] and waiting:
        waiting_zoo = waiting["zoo"]
        waiting_context = (waiting_zoo["active"], waiting_zoo["cycle"])
        waiting_count = pet_learned_count({"cards": game["cards"], "zoo": waiting_zoo})
    results = raw.get("reviews")
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, dict):
                continue
            milestone, score = result.get("milestone"), result.get("score")
            owner = review_species(result)
            cycle = review_cycle(result)
            if owner == species and cycle == game["zoo"]["cycle"]:
                limit = count
            elif (owner, cycle) == waiting_context:
                limit = waiting_count
            else:
                limit = 150 if isinstance(owner, str) and owner in archived else 0
            if (isinstance(owner, str) and owner in SPECIES_NAMES
                    and type(cycle) is int and 0 <= cycle <= game["zoo"]["serial"]
                    and type(milestone) is int and milestone in (30, 50, 60, 90, 100, 120, 150) and milestone <= limit
                    and type(result.get("total")) is int and result["total"] in (6, REVIEW_SIZE)
                    and type(score) is int and 0 <= score <= result["total"]):
                clean_result = {"milestone": milestone, "score": score, "total": result["total"]}
                if result["total"] == REVIEW_SIZE:
                    clean_result["attempt"] = max(1, result.get("attempt", 1)) if type(result.get("attempt", 1)) is int else 1
                    clean_result["cleared"] = result.get("cleared") is True or score == REVIEW_SIZE
                if owner != "sniffer":
                    clean_result["species"] = owner
                if cycle:
                    clean_result["cycle"] = cycle
                game["reviews"].append(clean_result)
    game["reviews"].sort(key=lambda item: item["milestone"])
    active = raw.get("active_review")
    if not isinstance(active, dict):
        return
    if active.get("species", species) != species:
        return
    if review_cycle(active) != game["zoo"]["cycle"]:
        return
    milestone = active.get("milestone")
    size = 6 if isinstance(active.get("queue"), list) and len(active["queue"]) == 6 else REVIEW_SIZE
    pool = {word["id"] for word in words_for_species(species)}
    test = normalize_test(active, pool, size)
    if (type(milestone) is not int or milestone not in (MILESTONES if size == REVIEW_SIZE else (30, 60, 90, 120, 150))
            or milestone > count or test is None):
        return
    game["active_review"] = {"milestone": milestone, **test}
    if size == REVIEW_SIZE:
        game["active_review"]["attempt"] = max(1, active.get("attempt", 1)) if type(active.get("attempt", 1)) is int else 1
    if species != "sniffer":
        game["active_review"]["species"] = species
    if game["zoo"]["cycle"]:
        game["active_review"]["cycle"] = game["zoo"]["cycle"]
    if len(test["answers"]) == size:
        _finish_review(game)


def pending_review(game):
    completed = {item["milestone"] for item in game["reviews"] if review_species(item) == current_species(game)
                 and review_cycle(item) == game["zoo"]["cycle"] and item["total"] == REVIEW_SIZE
                 and item["score"] * 10 >= REVIEW_SIZE * 7 and item.get("cleared", item["score"] == REVIEW_SIZE)}
    count = pet_learned_count(game)
    return next((milestone for milestone in MILESTONES if milestone <= count and milestone not in completed), None)


def start_review(game, rng=None):
    if game["active_review"] is not None:
        return game["active_review"]
    milestone = pending_review(game)
    if milestone is None:
        return None
    rng = rng or random
    game["learned_order"] = learned_ids(game)
    eligible = review_learned_ids(game)[:milestone]
    pool = {word["id"] for word in words_for_species(current_species(game))}
    queue = [word for word in game["repeat_words"] if word in pool and
             (word in eligible or game["cards"].get(word, {}).get("seen"))][:REVIEW_SIZE]
    candidates = [word_id for word_id in review_learned_ids(game)[:milestone] if word_id not in queue]
    queue += rng.sample(candidates, REVIEW_SIZE - len(queue))
    rng.shuffle(queue)
    game["active_review"] = {
        "milestone": milestone, "queue": queue,
        "answers": [], "phase": "quiz",
        "attempt": 1 + sum(item["milestone"] == milestone and review_species(item) == current_species(game)
                           and review_cycle(item) == game["zoo"]["cycle"] and item["total"] == REVIEW_SIZE for item in game["reviews"]),
    }
    if current_species(game) != "sniffer":
        game["active_review"]["species"] = current_species(game)
    if game["zoo"]["cycle"]:
        game["active_review"]["cycle"] = game["zoo"]["cycle"]
    return game["active_review"]


def review_score(review):
    return score(review)


def review_passed(review):
    return passed(review)


def retry_review(game, rng=None):
    review = game["active_review"]
    if review is None or review["phase"] != "summary" or not corrected(review) or passed(review):
        return None
    game["active_review"] = None
    return start_review(game, rng)


def repair_review(game):
    review = game["active_review"]
    return bool(review and start_corrections(review))


def review_choices(game, rng=None):
    review = game["active_review"]
    if review is None or review["phase"] not in ("quiz", "repair_quiz"):
        return []
    rng = rng or random
    expected = expected_word(review)
    contextual = form_choices(expected, rng)
    if contextual is not None:
        return contextual
    eligible = list(dict.fromkeys(review_learned_ids(game)[:review["milestone"]] + review["queue"]))
    candidates = [word_id for word_id in eligible
                  if word_id != expected and WORD_BY_ID[word_id]["ru"] != WORD_BY_ID[expected]["ru"]]
    options = [expected] + rng.sample(candidates, min(2, len(candidates)))
    rng.shuffle(options)
    return options


def _finish_review(game):
    review = game["active_review"]
    result = next((item for item in game["reviews"] if item["milestone"] == review["milestone"]
                   and review_species(item) == current_species(game) and review_cycle(item) == game["zoo"]["cycle"]
                   and item.get("attempt") == review.get("attempt") and item["total"] == len(review["queue"])), None)
    if result is None:
        result = {"milestone": review["milestone"], "score": review_score(review), "total": len(review["queue"])}
        if len(review["queue"]) == REVIEW_SIZE:
            result["attempt"] = review["attempt"]
        if current_species(game) != "sniffer":
            result["species"] = current_species(game)
        if game["zoo"]["cycle"]:
            result["cycle"] = game["zoo"]["cycle"]
        game["reviews"].append(result)
        game["reviews"].sort(key=lambda item: item["milestone"])
    if result["total"] == REVIEW_SIZE:
        result["cleared"] = corrected(review)


def answer_review(game, chosen_id):
    review = game["active_review"]
    if review is not None and review["phase"] == "repair_quiz":
        return answer_correction(review, chosen_id, record_attempt, game)
    if review is None or review["phase"] != "quiz" or not isinstance(chosen_id, str) or chosen_id not in WORD_BY_ID:
        return False
    index = len(review["answers"])
    if index >= len(review["queue"]):
        return False
    expected = review["queue"][index]
    record_attempt(game, expected, chosen_id == expected, review=True)
    review["answers"].append(chosen_id)
    review["phase"] = "feedback"
    if len(review["answers"]) == len(review["queue"]):
        _finish_review(game)
    return True


def advance_review(game):
    review = game["active_review"]
    if review is not None and review["phase"].startswith("repair_"):
        advance_correction(review)
        _finish_review(game)
        return
    if review is not None and review["phase"] == "feedback":
        review["phase"] = "summary" if len(review["answers"]) == len(review["queue"]) else "quiz"


def statistics(game):
    attempts = correct = 0
    for record in game["word_stats"].values():
        attempts += record["lesson_attempts"] + record["review_attempts"]
        correct += record["lesson_correct"] + record["review_correct"]
    seen = sum(bool(record.get("seen")) for record in game["cards"].values())
    learned = len(learned_ids(game))
    return {"seen": seen, "learned": learned, "learning": max(0, seen - learned), "needs_review": len(game["repeat_words"]),
            "attempts": attempts, "correct": correct,
            "accuracy": round(correct * 100 / attempts) if attempts else None}


def word_status(game, word_id):
    record = game["cards"].get(word_id, {})
    if word_id in game["repeat_words"]:
        return "Повторить"
    if len(record.get("correct_sessions", [])) >= 2:
        return "Выучено"
    return "Повторяем" if record.get("seen") else "Не открыто"
