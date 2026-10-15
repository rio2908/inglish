import random
import unittest

from pet_behavior import HeartBurst, PetBehavior, ROUTINES


class PetBehaviorTests(unittest.TestCase):
    def test_every_stage_uses_its_own_routine_and_all_actions_run(self):
        for stage in range(5):
            with self.subTest(stage=stage):
                behavior = PetBehavior(stage, rng=random.Random(4))
                actions = set()
                positions = []
                for frame in range(1400):
                    pose = behavior.update(stage, frame / 30)
                    actions.add(pose.action)
                    positions.append(pose.x)
                    self.assertGreaterEqual(pose.x, 225)
                    self.assertLessEqual(pose.x, 460)
                self.assertEqual(actions, set(ROUTINES[stage]))
                if stage:
                    self.assertGreater(max(positions) - min(positions), 15)

    def test_baby_moves_immediately_instead_of_standing_still(self):
        behavior = PetBehavior(1, rng=random.Random(1))
        before = behavior.update(1, 0)
        after = behavior.update(1, 0.1)
        self.assertEqual(after.action, "toddle")
        self.assertGreater(after.x, before.x)
        self.assertLess(after.bob, 0)

    def test_long_absence_does_not_teleport_the_pet(self):
        behavior = PetBehavior(2)
        before = behavior.update(2, 0)
        after = behavior.update(2, 3600)
        self.assertLessEqual(abs(after.x - before.x), 5.3 + 0.001)
        self.assertLessEqual(behavior.time, 0.1)

    def test_affection_temporarily_overrides_routine_then_expires(self):
        behavior = PetBehavior(1)
        behavior.pet()
        original_x = behavior.x
        self.assertEqual(behavior.update(1, 0.1).action, "happy")
        self.assertEqual(behavior.x, original_x)
        for frame in range(1, 60):
            pose = behavior.update(1, 0.1 + frame / 30)
        self.assertNotEqual(pose.action, "happy")

    def test_transform_resets_to_new_stage_routine(self):
        behavior = PetBehavior(1)
        behavior.pet()
        pose = behavior.update(4, 0.1)
        self.assertEqual(pose.action, "bloom")
        self.assertEqual(behavior.stage, 4)

    def test_walking_turns_around_at_the_meadow_boundary(self):
        behavior = PetBehavior(2)
        behavior.x = 459
        pose = behavior.update(2, 0.1)
        self.assertEqual(pose.x, 460)
        self.assertTrue(pose.flip)
        self.assertLess(behavior.update(2, 0.2).x, 460)

    def test_movement_is_consistent_at_different_frame_rates(self):
        positions = []
        for fps in (30, 60):
            behavior = PetBehavior(1, rng=random.Random(3))
            for frame in range(fps + 1):
                behavior.update(1, frame / fps)
            positions.append(behavior.x)
        self.assertAlmostEqual(positions[0], positions[1], places=5)


class HeartBurstTests(unittest.TestCase):
    def test_hearts_spread_both_ways_rise_and_fade(self):
        burst = HeartBurst()
        burst.emit(350, 320, 10)
        initial = burst.frame(10)
        later = burst.frame(10.5)
        self.assertEqual(len(initial), 6)
        self.assertTrue(any(x < 350 for x, _, _, _ in later))
        self.assertTrue(any(x > 350 for x, _, _, _ in later))
        self.assertTrue(all(y < 320 for _, y, _, _ in later))
        self.assertTrue(all(alpha < 255 for _, _, _, alpha in later))
        self.assertEqual(burst.frame(12), [])
        self.assertEqual(burst.particles, [])

    def test_repeated_taps_have_bounded_particle_count(self):
        burst = HeartBurst()
        for _ in range(1000):
            burst.emit(350, 320, 0)
        self.assertEqual(len(burst.particles), 48)


if __name__ == "__main__":
    unittest.main()
