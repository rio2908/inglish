"""Shared scored tests and non-scoring, resumable work on mistakes."""

import random

from words import WORD_BY_ID


def score(test):
    return sum(a == b for a, b in zip(test["queue"], test["answers"]))


def score_passed(test):
    return len(test["answers"]) == len(test["queue"]) and score(test) * 10 >= len(test["queue"]) * 7


def mistakes(test):
    return list(dict.fromkeys(expected for expected, chosen in zip(test["queue"], test["answers"]) if expected != chosen))


def corrected(test):
    if len(test["answers"]) != len(test["queue"]):
        return False
    return not mistakes(test) or (isinstance(test.get("corrections"), dict) and not test["corrections"]["remaining"])


def passed(test):
    return score_passed(test) and corrected(test)


def normalize_test(raw, pool, size):
    if not isinstance(raw, dict):
        return None
    queue, answers = raw.get("queue"), raw.get("answers")
    if (not isinstance(queue, list) or len(queue) != size or len(set(word for word in queue if isinstance(word, str))) != size
            or any(not isinstance(word, str) or word not in pool for word in queue)
            or not isinstance(answers, list) or len(answers) > size
            or any(not isinstance(word, str) or word not in WORD_BY_ID for word in answers)):
        return None
    phase = raw.get("phase", "quiz")
    if phase not in ("quiz", "feedback", "summary", "repair_intro", "repair_quiz", "repair_feedback"):
        phase = "quiz"
    if phase == "feedback" and not answers:
        phase = "quiz"
    if phase not in ("quiz", "feedback") and len(answers) < size:
        phase = "quiz"
    if phase == "quiz" and len(answers) == size:
        phase = "feedback"
    test = {"queue": queue[:], "answers": answers[:], "phase": phase}
    correction = raw.get("corrections")
    if len(answers) == size and isinstance(correction, dict):
        remaining, practice = correction.get("remaining"), correction.get("queue")
        if (isinstance(remaining, list) and isinstance(practice, list) and len(practice) <= 450
                and all(isinstance(word, str) and word in pool for word in remaining + practice)
                and len(set(remaining)) == len(remaining) and set(remaining) <= set(practice)):
            shown = correction.get("shown", [])
            shown = list(dict.fromkeys(word for word in shown if isinstance(word, str) and word in pool)) if isinstance(shown, list) else []
            test["corrections"] = {"remaining": remaining[:], "queue": practice[:], "correct": correction.get("correct") is True, "shown": shown}
    if phase.startswith("repair_") and ("corrections" not in test or not test["corrections"]["queue"]):
        test["phase"] = "summary"
    return test


def expected_word(test):
    if test["phase"].startswith("repair_"):
        return test["corrections"]["queue"][0]
    return test["queue"][len(test["answers"]) - (test["phase"] == "feedback")]


def start_corrections(test, rng=None):
    if test["phase"] != "summary" or corrected(test):
        return False
    rng = rng or random
    wrong = mistakes(test)
    rng.shuffle(wrong)
    test["corrections"] = {"remaining": wrong[:], "queue": wrong[:], "correct": False, "shown": []}
    test["phase"] = "repair_intro"
    return True


def answer_correction(test, chosen, record_attempt, game):
    if test["phase"] != "repair_quiz" or not isinstance(chosen, str) or chosen not in WORD_BY_ID:
        return False
    expected = expected_word(test)
    correct = chosen == expected
    record_attempt(game, expected, correct, review=True)
    correction = test["corrections"]
    correction["correct"] = correct
    if not correct and expected not in correction["remaining"]:
        correction["remaining"].append(expected)
    if not correct and expected not in correction["shown"]:
        correction["shown"].append(expected)
    test["phase"] = "repair_feedback"
    return True


def advance_correction(test, rng=None):
    rng = rng or random
    if test["phase"] == "repair_intro":
        # Seeing the answer is study, not recall: insert two other questions.
        word = test["corrections"]["queue"][0]
        if word not in test["corrections"]["shown"]:
            test["corrections"]["shown"].append(word)
        fillers = [item for item in test["queue"] if item != word]
        test["corrections"]["queue"] = rng.sample(fillers, min(2, len(fillers))) + test["corrections"]["queue"]
        test["phase"] = "repair_quiz"
    elif test["phase"] == "repair_feedback":
        correction = test["corrections"]
        word = correction["queue"].pop(0)
        if correction["correct"]:
            if word in correction["remaining"]:
                correction["remaining"].remove(word)
        else:
            # At least two other questions before the failed word comes back.
            fillers = [item for item in test["queue"] if item != word]
            correction["queue"] = [item for item in correction["queue"] if item != word]
            while len(correction["queue"]) < 2:
                correction["queue"].append(rng.choice(fillers))
            correction["queue"].append(word)
        if not correction["remaining"]:
            correction["queue"] = []
            test["phase"] = "summary"
        else:
            next_word = correction["queue"][0]
            test["phase"] = "repair_intro" if next_word in correction["remaining"] and next_word not in correction["shown"] else "repair_quiz"
