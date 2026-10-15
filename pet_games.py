"""Stage-specific pet activities. No pygame, timers or changes to word progress."""

import random


GAME_NAMES = {1: "Найди вкусняшку", 2: "Прятки", 3: "Повтори за мной", 4: "Цветочный сад"}
MOVES = ("Прыжок", "Топот", "Поворот")
TOOLS = ("Семечко", "Вода", "Солнышко")


class PetGame:
    def __init__(self, stage, now=0, rng=None):
        if stage not in GAME_NAMES:
            raise ValueError("Pet activities are available only after hatching")
        self.stage = stage
        self.rng = rng or random
        self.hits = 0
        self.phase = "search"
        self.until = 0
        self.last_choice = None
        self.sequence = []
        self.input_index = 0
        self.show_start = now
        self.plants = [0, 0, 0]
        self.selected = 0
        self.target = self.rng.randrange(3 if stage == 1 else 4)
        self.message = ""
        if stage == 3:
            self._new_sequence(now)
        elif stage == 4:
            self.message = "Выбери грядку и посади семечко."
        elif stage == 1:
            self.message = "Нажми на куст. Сниффер поможет своим нюхом!"
        else:
            self.message = "Найди, откуда выглядывает твой питомец!"

    @property
    def done(self):
        return self.phase == "done"

    def _new_sequence(self, now):
        self.sequence = [self.rng.randrange(3) for _ in range(self.hits + 2)]
        self._show_sequence(now)

    def _show_sequence(self, now):
        self.phase = "show"
        self.input_index = 0
        self.show_start = now
        self.message = "Смотри, что делает сниффер, и запоминай!"

    def shown_move(self, now):
        if self.phase != "show":
            return None
        elapsed = max(0, now - self.show_start)
        index = elapsed // 900
        if index >= len(self.sequence) or elapsed % 900 >= 700:
            return None
        return self.sequence[index]

    def tick(self, now):
        if self.phase == "show" and now - self.show_start >= len(self.sequence) * 900 + 350:
            self.phase = "repeat"
            self.message = "Теперь твоя очередь! Нажми движения по порядку."
        elif self.phase == "celebrate" and now >= self.until:
            if self.hits >= 3:
                self.phase = "done"
            elif self.stage == 3:
                self._new_sequence(now)
            else:
                previous = self.target
                choices = [i for i in range(3 if self.stage == 1 else 4) if i != previous]
                self.target = self.rng.choice(choices)
                self.last_choice = None
                self.phase = "search"
                self.message = "Теперь поищем ещё!" if self.stage == 1 else "Сниффер спрятался в другом месте!"

    def _celebrate(self, now, message):
        self.phase = "celebrate"
        self.until = now + 1100
        self.message = message

    def select_bed(self, index):
        if self.stage == 4 and self.phase == "search" and 0 <= index < 3:
            self.selected = index
            state = self.plants[index]
            self.message = "Цветок уже вырос! Выбери другую грядку." if state == 3 else (
                "Сначала семечко." if state == 0 else "Росток хочет пить." if state == 1 else "Теперь нужно солнышко!")

    def choose(self, index, now):
        if type(index) is not int or index < 0 or index >= (4 if self.stage == 2 else 3):
            return False
        if self.phase in ("show", "celebrate", "done"):
            return False
        self.last_choice = index
        if self.stage in (1, 2):
            if index != self.target:
                if self.stage == 1:
                    self.message = "Уже близко! Попробуй соседний куст." if abs(index - self.target) == 1 else "Здесь не пахнет. Ищи с другой стороны!"
                else:
                    self.message = "Тут пусто. Посмотри, где выглядывает нос или хвост!"
                return False
            self.hits += 1
            self._celebrate(now, "Нашли угощение! Сниффер довольно сопит!" if self.stage == 1 else "Нашёл! Питомец радостно выскакивает!")
        elif self.stage == 3:
            if index != self.sequence[self.input_index]:
                self._show_sequence(now)
                self.message = "Ничего страшного! Сниффер покажет ещё раз."
                return False
            self.input_index += 1
            if self.input_index == len(self.sequence):
                self.hits += 1
                self._celebrate(now, "Получилось! Вы отлично понимаете друг друга!")
            else:
                self.message = "Верно! Какое движение было следующим?"
        else:
            state = self.plants[self.selected]
            if state == 3:
                self.message = "Этот цветок уже вырос. Выбери свободную грядку."
                return False
            if index != state:
                self.message = ("Сначала посади семечко.", "Семечку нужна вода.", "Добавь солнышко, чтобы цветок раскрылся!")[state]
                return False
            self.plants[self.selected] += 1
            if self.plants[self.selected] == 3:
                self.hits += 1
                if self.hits == 3:
                    self._celebrate(now, "Все цветы распустились! Сниффер танцует от радости!")
                else:
                    self.selected = next(i for i, plant in enumerate(self.plants) if plant < 3)
                    self.message = "Красота! Посадим следующий цветок."
            else:
                self.message = "Теперь польём семечко!" if state == 0 else "Росток появился! Добавь солнышко."
        return True

    def replay(self, now):
        if self.stage == 3 and self.phase in ("show", "repeat"):
            self._show_sequence(now)
