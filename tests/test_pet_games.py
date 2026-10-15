import random
import unittest

from pet_games import PetGame


class PetGameTests(unittest.TestCase):
    def test_games_require_a_hatched_stage(self):
        for stage in (0, -1, 5):
            with self.assertRaises(ValueError):
                PetGame(stage)

    def test_search_games_need_three_finds_and_move_hiding_place(self):
        for stage in (1, 2):
            with self.subTest(stage=stage):
                game = PetGame(stage, rng=random.Random(12))
                now = 0
                for hits in range(1, 4):
                    target = game.target
                    self.assertFalse(game.choose((target + 1) % 3, now))
                    self.assertEqual(game.hits, hits - 1)
                    self.assertTrue(game.choose(target, now))
                    self.assertEqual(game.hits, hits)
                    self.assertFalse(game.choose(target, now + 1))
                    self.assertFalse(game.done)
                    now = game.until
                    game.tick(now)
                    if hits < 3:
                        self.assertNotEqual(game.target, target)
                self.assertTrue(game.done)
                self.assertFalse(game.choose(game.target, now))

    def test_memory_displays_sequence_before_accepting_input(self):
        game = PetGame(3, now=100, rng=random.Random(3))
        self.assertEqual(len(game.sequence), 2)
        self.assertEqual(game.shown_move(100), game.sequence[0])
        self.assertIsNone(game.shown_move(850))
        self.assertEqual(game.shown_move(1000), game.sequence[1])
        self.assertFalse(game.choose(game.sequence[0], 100))
        self.assertEqual(game.input_index, 0)
        game.tick(100 + 2 * 900 + 350)
        self.assertEqual(game.phase, "repeat")

    def test_memory_can_be_replayed_and_wrong_move_preserves_completed_rounds(self):
        game = PetGame(3, rng=random.Random(8))
        now = 0
        for hits, length in enumerate((2, 3, 4), start=1):
            self.assertEqual(len(game.sequence), length)
            sequence = game.sequence[:]
            now = game.show_start + length * 900 + 350
            game.tick(now)
            game.replay(now)
            self.assertEqual(game.sequence, sequence)
            self.assertFalse(game.choose(sequence[0], now))
            now += length * 900 + 350
            game.tick(now)
            self.assertFalse(game.choose((sequence[0] + 1) % 3, now))
            self.assertEqual(game.hits, hits - 1)
            self.assertEqual(game.input_index, 0)
            self.assertEqual(game.sequence, sequence)
            now += length * 900 + 350
            game.tick(now)
            for move in sequence:
                self.assertTrue(game.choose(move, now))
            self.assertEqual(game.hits, hits)
            self.assertEqual(game.phase, "celebrate")
            game.tick(game.until)
        self.assertTrue(game.done)

    def test_flowers_need_seed_water_and_sun_for_each_bed(self):
        game = PetGame(4)
        self.assertFalse(game.choose(2, 0))
        self.assertEqual(game.plants, [0, 0, 0])
        # It is valid to plant every bed before watering any of them.
        for bed in range(3):
            game.select_bed(bed)
            self.assertTrue(game.choose(0, 0))
        for bed in range(3):
            game.select_bed(bed)
            self.assertTrue(game.choose(1, 0))
            self.assertFalse(game.choose(0, 0))
            self.assertTrue(game.choose(2, 0))
            self.assertEqual(game.hits, bed + 1)
        self.assertEqual(game.plants, [3, 3, 3])
        self.assertFalse(game.done)
        game.tick(game.until)
        self.assertTrue(game.done)

    def test_invalid_controls_do_not_change_progress(self):
        for stage in range(1, 5):
            game = PetGame(stage)
            for index in (-1, 100, "1", True, None):
                self.assertFalse(game.choose(index, 0))
            self.assertEqual(game.hits, 0)


if __name__ == "__main__":
    unittest.main()
