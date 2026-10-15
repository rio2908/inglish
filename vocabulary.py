"""Read-only views of the selected player's learned vocabulary."""

from game_logic import mastered
from words import ALL_WORDS


def learned_vocabulary(game, species=None, query="", errors_only=False):
    query = " ".join(query.casefold().split())
    mistakes = set(game.get("repeat_words", []))
    result = []
    for word in ALL_WORDS:
        if species is not None and word["species"] != species:
            continue
        if not mastered(game, word["id"]):
            continue
        if errors_only and word["id"] not in mistakes:
            continue
        if query and not any(query in word[field].casefold() for field in ("en", "ru", "hint")):
            continue
        result.append(word)
    return sorted(result, key=lambda word: word["en"].casefold())
