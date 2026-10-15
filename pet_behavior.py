"""Frame-rate-independent meadow behaviour and small affection particles."""

from dataclasses import dataclass
import math
import random


ROUTINES = {
    0: ("egg",),
    1: ("toddle", "sniff", "hop", "idle", "rest"),
    2: ("walk", "sniff", "walk", "hop", "idle"),
    3: ("idle", "walk", "sniff", "rest", "sniff"),
    4: ("bloom", "walk", "bloom", "sniff", "rest"),
}
LABELS = {"egg": "Прислушивается к словам", "idle": "Осматривается", "toddle": "Первые шаги",
          "walk": "Гуляет по лужайке", "sniff": "Нюхает траву", "hop": "Играет", "rest": "Отдыхает",
          "bloom": "Радуется цветам", "happy": "Радуется твоему вниманию!"}
SPEEDS = {1: 24, 2: 53, 3: 19, 4: 16}


@dataclass
class PetPose:
    x: float
    bob: float
    angle: float
    scale_x: float
    scale_y: float
    flip: bool
    walk_frame: int
    action: str


class PetBehavior:
    def __init__(self, stage, now=0, rng=None):
        self.rng = rng or random
        self.stage = stage
        self.x = 343 if stage < 3 else 365
        self.direction = 1
        self.left_bound, self.right_bound = 225, 460
        self.last_time = now
        self.time = 0.0
        self.action_time = 0.0
        self.routine_index = 0
        self.action = ROUTINES[stage][0]
        self.duration = self.rng.uniform(2.4, 4.0)
        self.happy_until = 0.0

    def pet(self):
        if self.stage:
            self.happy_until = self.time + 1.4

    def update(self, stage, now):
        if stage != self.stage:
            self.stage = stage
            self.routine_index = 0
            self.action = ROUTINES[stage][0]
            self.action_time = 0.0
            self.happy_until = 0.0
        # Do not teleport or simulate a long absence after returning from another screen.
        dt = max(0.0, min(0.1, now - self.last_time))
        self.last_time = now
        self.time += dt
        happy = self.time < self.happy_until
        if not happy:
            self.action_time += dt
            if self.action_time >= self.duration:
                self.routine_index = (self.routine_index + 1) % len(ROUTINES[stage])
                self.action = ROUTINES[stage][self.routine_index]
                self.action_time = 0.0
                self.duration = self.rng.uniform(2.0, 3.6) if stage == 2 else self.rng.uniform(2.8, 4.5)
            if self.action in ("walk", "toddle"):
                self.x += self.direction * SPEEDS[stage] * dt
                if self.x >= self.right_bound:
                    self.x, self.direction = self.right_bound, -1
                elif self.x <= self.left_bound:
                    self.x, self.direction = self.left_bound, 1

        action = "happy" if happy else self.action
        phase = self.time
        breath = math.sin(phase * (4.2 if stage == 1 else 2.4))
        bob, angle = 0.0, 0.0
        sx, sy = 1.0, 1.0 + (0.012 if stage else 0.0) * breath
        if action in ("walk", "toddle"):
            frequency = 9 if stage == 2 else 7
            bob = -abs(math.sin(phase * frequency)) * (6 if stage < 3 else 3)
            angle = math.sin(phase * frequency) * (3 if stage == 1 else 1.5)
        elif action in ("hop", "happy"):
            bob = -abs(math.sin(phase * 7)) * (17 if stage == 1 or happy else 11)
            sx, sy = 1.025, 0.985 + math.sin(phase * 7) * 0.015
            angle = math.sin(phase * 7) * 2
        elif action == "sniff":
            angle = -4 + math.sin(phase * 6) * 1.5
            sx, sy = 1.03, 0.95
        elif action == "rest":
            sx, sy = 1.04, 0.90 + breath * 0.012
        elif action == "bloom":
            angle = math.sin(phase * 1.8) * 3
        elif action == "egg":
            angle = math.sin(phase * 2.5) * 2
        return PetPose(self.x, bob, angle * self.direction, sx, sy, self.direction < 0,
                       int(self.time * 6) % 6, action)


class HeartBurst:
    """Bounded transient particles. Coordinates use the fixed game canvas."""

    def __init__(self):
        self.particles = []

    def emit(self, x, y, now):
        for i, velocity in enumerate((-160, -100, -45, 45, 100, 160)):
            self.particles.append({"x": x, "y": y, "vx": velocity, "vy": -85 - (i % 3) * 18,
                                   "born": now, "life": 1.25 + (i % 3) * 0.15, "size": 3 + i % 2})
        self.particles = self.particles[-48:]

    def frame(self, now):
        self.particles = [particle for particle in self.particles if now - particle["born"] < particle["life"]]
        frames = []
        for particle in self.particles:
            age = max(0, now - particle["born"])
            alpha = round(255 * min(1, max(0, (particle["life"] - age) / (particle["life"] * 0.7))))
            frames.append((particle["x"] + particle["vx"] * age,
                           particle["y"] + particle["vy"] * age + 12 * age * age,
                           particle["size"], alpha))
        return frames
