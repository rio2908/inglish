"""Drive approved checkpoints in fixtures that need already trained pets."""

from learning_stats import advance_review, answer_review, pending_review, start_review


def clear_checkpoints(game):
    while pending_review(game) is not None:
        review = start_review(game)
        for word in review["queue"][:]:
            answer_review(game, word)
            advance_review(game)
        game["active_review"] = None
