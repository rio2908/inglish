"""Inglish: a small landscape Android game built on MathCraft's pygame stack."""

import asyncio
import math
import os
from pathlib import Path
import sys

import pygame

from game_logic import (
    can_explore, choice_ids, clean, egg_frame, explore, feed, finish_session,
    growth_stage, hatch_complete, mark_seen, mastered, mastered_count,
    clean_pet_name, growth_remaining, play, record_answer, start_session,
)
from game_backup import ProfilePicker
from game_storage import load_game, write_game
from learning_stats import (
    advance_review, answer_review, pending_review, review_choices, review_score,
    start_review, statistics, word_status,
)
from pet_games import GAME_NAMES, MOVES, TOOLS, PetGame
from sprites import SnifferSprites
from speech import Speech
from words import CHAPTERS, WORDS, WORD_BY_ID


WIDTH, HEIGHT = 1000, 600
ROOT = Path(__file__).resolve().parent
AUDIO_DIR = ROOT / "assets" / "audio"

INK = (34, 47, 43)
CREAM = (253, 247, 224)
PAPER = (247, 239, 211)
PAPER_DARK = (224, 209, 170)
TEAL = (29, 111, 102)
TEAL_LIGHT = (82, 171, 147)
GOLD = (255, 194, 70)
RED = (188, 71, 61)
WHITE = (255, 255, 255)
SKY = (145, 213, 221)
GRASS = (112, 169, 82)
GROUND = (120, 80, 49)

STAGE_NAMES = ["Яйцо", "Малыш", "Подросток", "Взрослый", "Цветущий сниффер"]
CHAPTER_SCENES = [
    "Яйцо слышит первые слова.",
    "Сниффер увидел нового зверя!",
    "Сниффер изучает сад и природу.",
    "Сниффер выбирает угощение.",
    "Сниффер обустраивает свой дом.",
    "Сниффер знакомится с друзьями.",
    "Сниффер замечает цвета и формы.",
    "Сниффер показывает новое действие.",
    "Сниффер рассказывает, как себя чувствует.",
    "Сниффер узнаёт, где его вещи.",
]
STORIES = [
    ("I have it.", "You have it.", "Оно у меня.", "Теперь оно у тебя."),
    ("I have a cat.", "She has a dog.", "У меня есть кошка.", "У неё есть собака."),
    ("A seed is in the grass.", "The flower is here.", "Семечко лежит в траве.", "Цветок здесь."),
    ("It has a carrot.", "I have the apple.", "У него есть морковь.", "У меня есть яблоко."),
    ("A bed is in the house.", "The ball is here.", "Кровать стоит в доме.", "Мяч здесь."),
    ("My mother is here.", "My father is here.", "Мама здесь.", "Папа здесь."),
    ("The flower is red.", "The sky is blue.", "Цветок красный.", "Небо синее."),
    ("I can run and jump.", "You can play.", "Я умею бегать и прыгать.", "Ты умеешь играть."),
    ("The garden is clean.", "It is a good garden.", "Сад чистый.", "Это хороший сад."),
    ("Where is the ball?", "It is under the tree.", "Где мяч?", "Он под деревом."),
]


def text(surf, value, size, center, color=INK, bold=False):
    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    image = font.render(str(value), True, color)
    rect = image.get_rect(center=center)
    surf.blit(image, rect)
    return rect


def panel(surf, rect, fill=PAPER, edge=INK, border=4):
    pygame.draw.rect(surf, (60, 81, 69), rect.move(4, 5))
    pygame.draw.rect(surf, fill, rect)
    pygame.draw.rect(surf, edge, rect, border)


def tile(surf, x, y, color, size=17, edge=INK):
    rect = pygame.Rect(int(x), int(y), size, size)
    pygame.draw.rect(surf, color, rect)
    pygame.draw.rect(surf, edge, rect, 2)


def draw_flower(surf, x, y, size=12, petals=GOLD):
    pygame.draw.rect(surf, (37, 104, 54), (x - 3, y, 6, 24))
    for dx, dy in ((-size, 0), (size, 0), (0, -size), (0, size)):
        tile(surf, x + dx - size // 2, y + dy - size // 2, petals, size)
    tile(surf, x - size // 2, y - size // 2, (132, 72, 48), size)


def draw_poop(surf, x, y):
    for dx, dy, w, h in ((8, 22, 58, 18), (15, 8, 44, 17), (25, 0, 23, 12)):
        pygame.draw.rect(surf, (115, 67, 43), (x + dx, y + dy, w, h))
        pygame.draw.rect(surf, (55, 44, 32), (x + dx, y + dy, w, h), 3)
    tile(surf, x + 25, y + 18, WHITE, 7)
    tile(surf, x + 45, y + 18, WHITE, 7)


class GameApp:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass
        if sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ:
            self.display = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
        else:
            self.display = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Inglish")
        pygame.display.set_icon(pygame.image.load(str(ROOT / "assets" / "icon.png")))
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self.pet_rect = pygame.Rect(0, 0, 0, 0)
        self.poop_rect = None
        self.clock = pygame.time.Clock()
        self.sprites = SnifferSprites()
        self.game = load_game()
        self.screen = "home"
        self.buttons = []
        self.message = "Выучи слова и помоги снифферу вылупиться!" if not hatch_complete(self.game) else "Сниффер ждёт тебя в саду!"
        self.message_until = 0
        self.speech = Speech(AUDIO_DIR)
        self.audio_notice = ""
        self.audio_notice_until = 0
        self.queue = []
        self.card_index = 0
        self.word_id = None
        self.card_phase = "intro"
        self.card_new = False
        self.quiz_mode = "meaning"
        self.options = []
        self.answer_correct = False
        self.just_mastered = False
        self.just_hatched = False
        self.session_answer_count = 0
        self.pet_game = None
        self.story_index = 0
        self.pet_tapped_until = 0
        self.hatching_until = 0
        self.running = True
        self.last_pointer_ms = -1000
        self.last_pointer_pos = (-1000, -1000)
        self.profile_picker = ProfilePicker()
        self.imported_game = None
        self.name_input = self.game["pet_name"]
        self.profile_notice = ""
        self.review_options = []
        self.stats_tab = "overview"
        self.stats_page = 0
        self.restore_lesson()

    def restore_lesson(self):
        lesson = self.game.get("lesson")
        if lesson:
            self.queue = lesson["queue"][:]
            self.card_index = lesson["index"]
            self.word_id = self.queue[self.card_index]
            self.card_phase = lesson["phase"]
            self.quiz_mode = lesson["mode"]
            self.answer_correct = lesson["correct"]
            self.session_answer_count = lesson["answers"]
            self.options = choice_ids(self.word_id)
            self.screen = "cards"
        if self.game["active_review"] is not None:
            self.review_options = review_choices(self.game)
            self.screen = "review"

    def persist(self):
        if self.screen == "cards" and self.word_id:
            self.game["lesson"] = {
                "queue": self.queue[:], "index": self.card_index,
                "phase": self.card_phase, "mode": self.quiz_mode,
                "correct": self.answer_correct, "answers": self.session_answer_count,
            }
        try:
            write_game(self.game)
            return True
        except Exception as error:
            self.notify("Не удалось сохранить игру. Выгрузите профиль.", 8)
            self.profile_notice = f"Ошибка сохранения: {error}"
            return False

    def open_profile(self):
        self.name_input = self.game["pet_name"]
        self.screen = "profile"

    def edit_name(self):
        self.name_input = self.game["pet_name"]
        self.screen = "name"
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(220, 240, 560, 60))

    def accept_name(self):
        name = clean_pet_name(self.name_input)
        if not name:
            return
        self.game["pet_name"] = name
        pygame.key.stop_text_input()
        self.screen = "profile"
        if self.persist():
            self.profile_notice = "Имя сохранено."

    def transfer_profile(self, export):
        self.persist()
        try:
            self.profile_picker.start(export, self.game)
        except Exception as error:
            self.profile_notice = f"Не удалось открыть файл: {error}"

    def poll_profile(self):
        result = self.profile_picker.poll()
        if result:
            self.profile_notice, imported = result
            if imported is not None:
                self.imported_game = imported
                self.screen = "import"

    def accept_import(self):
        # Persist the imported profile before replacing the current in-memory game.
        try:
            write_game(self.imported_game)
        except Exception as error:
            self.profile_notice = f"Профиль не загружен: {error}"
            self.screen = "profile"
            return
        self.game = self.imported_game
        self.imported_game = None
        self.queue = []
        self.word_id = None
        self.just_mastered = self.just_hatched = False
        self.screen = "home"
        self.restore_lesson()
        self.notify("Профиль загружен!")

    def notify(self, value, duration=3.2):
        self.message = value
        self.message_until = pygame.time.get_ticks() / 1000 + duration

    def button(self, rect, label, action, enabled=True, fill=TEAL, size=27):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.canvas, (55, 69, 53), rect.move(3, 4))
        pygame.draw.rect(self.canvas, fill if enabled else (135, 143, 126), rect)
        pygame.draw.rect(self.canvas, INK, rect, 3)
        text(self.canvas, label, size, rect.center, WHITE if enabled else (227, 231, 216), True)
        if enabled:
            self.buttons.append((rect, action))

    def play_audio(self, word_id):
        if not self.speech.speak(word_id):
            self.audio_notice = self.speech.error or "Не удалось воспроизвести английскую озвучку"
            self.audio_notice_until = pygame.time.get_ticks() / 1000 + 4

    def start_lesson(self):
        if self.game["active_review"] is not None or pending_review(self.game) is not None:
            self.open_review()
            return
        self.queue = start_session(self.game)
        self.card_index = 0
        self.session_answer_count = 0
        if not self.queue:
            self.notify("Все слова выучены! Можно повторять главы.")
            return
        self.screen = "cards"
        self.prepare_card()

    def prepare_card(self):
        if self.card_index >= len(self.queue):
            finish_session(self.game)
            self.game["lesson"] = None
            self.screen = "home"
            self.persist()
            self.notify("Раунд закончен! Загляни к снифферу.")
            if pending_review(self.game) is not None:
                self.open_review()
            return
        self.word_id = self.queue[self.card_index]
        record = self.game["cards"].get(self.word_id, {})
        self.card_new = not record.get("seen", False)
        self.card_phase = "intro" if self.card_new else "quiz"
        self.quiz_mode = "meaning" if self.card_new or not record.get("correct_sessions") else "spelling"
        self.options = choice_ids(self.word_id)
        self.persist()
        if pending_review(self.game) is not None:
            self.open_review()
        elif not self.card_new:
            self.play_audio(self.word_id)

    def intro_done(self):
        mark_seen(self.game, self.word_id)
        self.card_phase = "quiz"
        self.persist()
        self.play_audio(self.word_id)

    def answer(self, chosen_id):
        if self.card_phase != "quiz":
            return
        self.answer_correct = chosen_id == self.word_id
        self.session_answer_count += 1
        before_hatch = hatch_complete(self.game)
        self.just_mastered = record_answer(self.game, self.word_id, self.answer_correct)
        self.just_hatched = not before_hatch and hatch_complete(self.game)
        if self.just_hatched:
            self.hatching_until = pygame.time.get_ticks() / 1000 + 4
        self.card_phase = "result"
        self.persist()

    def next_card(self):
        self.card_index += 1
        self.prepare_card()

    def open_review(self):
        if start_review(self.game) is None:
            return
        self.review_options = review_choices(self.game)
        self.screen = "review"
        self.persist()

    def submit_review(self, chosen_id):
        if answer_review(self.game, chosen_id):
            self.persist()

    def next_review(self):
        advance_review(self.game)
        self.review_options = review_choices(self.game)
        self.persist()

    def close_review(self):
        review = self.game["active_review"]
        if review is not None and review["phase"] == "summary":
            self.game["active_review"] = None
        self.screen = "home"
        self.restore_lesson()
        self.persist()

    def pause_review(self):
        self.screen = "home"
        self.persist()
        self.notify("Проверку можно продолжить кнопкой «Учить слова».")

    def open_statistics(self):
        self.stats_tab = "overview"
        self.stats_page = 0
        self.screen = "statistics"

    def statistics_tab(self, tab):
        self.stats_tab = tab
        self.stats_page = 0

    def do_feed(self, food):
        if feed(self.game, food):
            self.screen = "home"
            self.persist()
            self.notify("Сниффер поел и довольно сопит!")

    def do_clean(self):
        if clean(self.game):
            self.persist()
            self.notify("Чисто! Отходы стали компостом для сада.")
        else:
            self.notify("Пока убирать нечего.")

    def do_explore(self):
        if explore(self.game):
            self.story_index = min(len(STORIES) - 1, self.game["garden_plants"] - 1)
            self.screen = "story"
            self.persist()

    def finish_play(self):
        if self.pet_game is None or not self.pet_game.done:
            return
        if play(self.game):
            self.pet_game = None
            self.screen = "home"
            self.persist()
            self.notify("Вы отлично поиграли вместе!")

    def draw_background(self):
        self.canvas.fill(SKY)
        pygame.draw.rect(self.canvas, (219, 239, 218), (0, 0, WIDTH, 260))
        for x, y in ((86, 114), (610, 138), (855, 84)):
            for dx, dy, w, h in ((0, 15, 86, 18), (18, 0, 50, 36)):
                pygame.draw.rect(self.canvas, WHITE, (x + dx, y + dy, w, h))
        pygame.draw.rect(self.canvas, GRASS, (0, 390, WIDTH, 210))
        pygame.draw.rect(self.canvas, (67, 123, 59), (0, 390, WIDTH, 13))
        for y in range(430, HEIGHT, 34):
            for x in range(0, WIDTH, 34):
                pygame.draw.rect(self.canvas, (105, 157, 74) if (x // 34 + y // 34) % 2 else (116, 166, 81), (x, y, 34, 34))

    def draw_header(self):
        pygame.draw.rect(self.canvas, INK, (0, 0, WIDTH, 65))
        text(self.canvas, "Inglish", 44, (170, 33), CREAM, True)
        if self.screen == "home":
            self.button((535, 10, 220, 43), "СТАТИСТИКА", self.open_statistics, fill=(88, 129, 155), size=25)
            self.button((770, 10, 195, 43), "ПРОФИЛЬ", self.open_profile, fill=TEAL, size=27)
        else:
            text(self.canvas, "150 английских слов", 27, (860, 33), GOLD)

    def draw_progress(self):
        rect = pygame.Rect(35, 82, 618, 88)
        panel(self.canvas, rect)
        learned = mastered_count(self.game)
        text(self.canvas, f"Выучено: {learned} / 150", 30, (344, 108), INK, True)
        kind, remaining = growth_remaining(self.game)
        if kind == "answers":
            caption = f"До вылупления — правильных ответов: {remaining}"
        elif kind == "words":
            caption = f"До следующего превращения — слов: {remaining}"
        else:
            caption = "Сниффер вырос! Продолжайте собирать сад."
        text(self.canvas, caption, 26, (344, 145), TEAL, True)

    def draw_garden(self):
        # The pet lives on the main meadow, not in a separate framed scene.
        for x in range(55, 640, 47):
            y = 453 + (x % 3) * 9
            pygame.draw.line(self.canvas, (65, 126, 58), (x, y), (x - 5, y - 9), 3)
            pygame.draw.line(self.canvas, (65, 126, 58), (x, y), (x + 5, y - 12), 3)
        for i in range(self.game["garden_plants"]):
            x = 75 + (i % 10) * 52
            y = 473 - (i // 10) * 29
            draw_flower(self.canvas, x, y, 9, GOLD if i % 2 else (235, 98, 144))

        now = pygame.time.get_ticks() / 1000
        stage = growth_stage(self.game)
        if stage == 0:
            family, index = "hatching", egg_frame(self.game)
            pet = self.sprites.scaled(family, index, 180, 162)
            x = 342
        elif now < self.hatching_until:
            pet = self.sprites.scaled("hatching", 4, 275, 164)
            x = 342
        elif stage == 2:
            index = int(now * 5.5) % 6
            pet = self.sprites.scaled("walk", index, 350, 196)
            x = 343 + int(math.sin(now * 0.72) * 55)
        else:
            pet = self.sprites.scaled("growth", stage, 285 if stage >= 3 else 290, 225 if stage >= 3 else 165)
            x = 365 if stage >= 3 else 343
        bob = 0 if stage == 0 else int(math.sin(now * 4) * 3)
        pygame.draw.ellipse(self.canvas, (76, 133, 63), (x - pet.get_width() // 2, 439, pet.get_width(), 24))
        self.canvas.blit(pet, pet.get_rect(midbottom=(x, 455 + bob)))
        self.pet_rect = pet.get_rect(midbottom=(x, 455 + bob))
        if self.game["poop"]:
            poop_x = 95 if stage >= 3 else 540
            draw_poop(self.canvas, poop_x, 440)
            self.poop_rect = pygame.Rect(poop_x - 8, 432, 95, 59)
        else:
            self.poop_rect = None
        if now < self.pet_tapped_until:
            text(self.canvas, "♥", 48, (x + 80, 288), RED, True)

    def draw_care_meter(self, label, key, y):
        text(self.canvas, label, 27, (754, y), INK, True)
        for i in range(3):
            tile(self.canvas, 825 + i * 33, y - 9, TEAL_LIGHT if i < self.game["care"][key] else PAPER_DARK, 24)

    def draw_home(self):
        self.draw_background()
        self.draw_header()
        self.draw_garden()
        self.draw_progress()
        stage = growth_stage(self.game)
        panel(self.canvas, pygame.Rect(676, 82, 289, 402))
        text(self.canvas, self.game["pet_name"], 29, (820, 105), INK, True)
        text(self.canvas, STAGE_NAMES[stage], 23, (820, 132), TEAL)
        if stage == 0:
            text(self.canvas, f"Трещин: {egg_frame(self.game)} / 4", 27, (820, 156), TEAL, True)
            text(self.canvas, "5 ответов — малыш появится", 23, (820, 190), INK)
            text(self.canvas, "Пока он ждёт в яйце", 25, (820, 280), INK)
            text(self.canvas, "Уход откроется после", 25, (820, 311), INK)
            text(self.canvas, "вылупления", 25, (820, 340), INK)
        else:
            self.draw_care_meter("Еда", "food", 158)
            self.draw_care_meter("Игра", "joy", 203)
            self.draw_care_meter("Чистота", "clean", 248)
            self.button((701, 288, 238, 45), "Покормить", lambda: setattr(self, "screen", "feed"), fill=(174, 112, 61), size=26)
            self.button((701, 345, 238, 45), GAME_NAMES[stage], self.start_play, fill=(84, 129, 168), size=23)
            self.button((701, 402, 238, 45), "Убрать", self.do_clean, enabled=self.game["poop"], fill=(100, 117, 79), size=26)
        milestone = pending_review(self.game)
        label = "ПРОДОЛЖИТЬ ТЕСТ" if self.game["active_review"] else f"ПРОВЕРКА: {milestone} СЛОВ" if milestone else "УЧИТЬ СЛОВА"
        self.button((35, 506, 365, 63), label, self.start_lesson, fill=TEAL, size=29 if milestone or self.game["active_review"] else 36)
        available = self.game["garden_plants"] < mastered_count(self.game) // 15
        self.button((420, 506, 232, 63), "ИСКАТЬ СЕМЕНА", self.do_explore, enabled=can_explore(self.game), fill=(119, 138, 65), size=27)
        if available and not can_explore(self.game):
            text(self.canvas, "Сначала позаботься о питомце", 20, (536, 491), RED, True)
        self.button((676, 506, 289, 63), "СПРАВКА", lambda: setattr(self, "screen", "help"), fill=(100, 111, 125), size=29)
        if self.message:
            text(self.canvas, self.message, 25, (500, 584), INK, True)

    def draw_letter_tiles(self, value, center_x, y, cell=34):
        gap = 4
        width = len(value) * (cell + gap) - gap
        x = center_x - width // 2
        for char in value:
            tile(self.canvas, x, y, WHITE, cell)
            text(self.canvas, char, cell + 3, (x + cell // 2, y + cell // 2 + 1), INK, True)
            x += cell + gap

    def draw_word_art(self, word):
        # A chapter scene is used until all 150 individual object pictures are made.
        rect = pygame.Rect(108, 175, 325, 277)
        panel(self.canvas, rect, (213, 235, 205))
        pygame.draw.rect(self.canvas, (116, 182, 115), (113, 376, 315, 71))
        if hatch_complete(self.game):
            small = self.sprites.scaled("growth", growth_stage(self.game), 220, 135)
        else:
            small = self.sprites.scaled("hatching", egg_frame(self.game), 150, 135)
        self.canvas.blit(small, small.get_rect(midbottom=(271, 400)))
        if word["chapter"] == 2:
            draw_flower(self.canvas, 175, 350, 14)
        elif word["chapter"] == 3:
            tile(self.canvas, 165, 342, RED, 33)
            tile(self.canvas, 174, 335, (46, 126, 59), 13)
        elif word["chapter"] == 6:
            for c, x in ((RED, 161), (GOLD, 185), (TEAL, 209)):
                tile(self.canvas, x, 341, c, 22)
        else:
            draw_flower(self.canvas, 175, 350, 11, (242, 124, 152))
        caption = CHAPTER_SCENES[word["chapter"]] if hatch_complete(self.game) else "Яйцо откликается на новое слово!"
        text(self.canvas, caption, 19, (271, 430), INK)

    def draw_cards(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(55, 78, 890, 492))
        word = WORD_BY_ID[self.word_id]
        text(self.canvas, f"Глава {word['chapter'] + 1}: {word['chapter_name']}", 27, (297, 111), TEAL, True)
        text(self.canvas, f"{self.card_index + 1} / {len(self.queue)}", 27, (855, 111), INK, True)
        if self.card_phase == "intro":
            self.draw_word_art(word)
            text(self.canvas, "Новое слово", 28, (686, 163), TEAL, True)
            self.draw_letter_tiles(word["en"], 686, 198, 34 if len(word["en"]) < 10 else 28)
            text(self.canvas, word["hint"], 46, (686, 292), RED)
            text(self.canvas, word["ru"], 42, (686, 339), TEAL, True)
            self.button((586, 382, 246, 54), "СЛУШАТЬ", lambda: self.play_audio(self.word_id), fill=(88, 129, 155), size=26)
            self.button((586, 472, 246, 63), "ПОНЯТНО", self.intro_done, size=32)
        elif self.card_phase == "quiz":
            if self.quiz_mode == "meaning":
                text(self.canvas, "Что означает слово?", 35, (500, 171), INK, True)
                self.draw_letter_tiles(word["en"], 500, 210, 36 if len(word["en"]) < 10 else 29)
            else:
                text(self.canvas, "Выбери английское слово", 35, (500, 171), INK, True)
            text(self.canvas, word["ru"], 49, (500, 233), TEAL, True)
            self.button((782, 145, 115, 49), "ЗВУК", lambda: self.play_audio(self.word_id), fill=(88, 129, 155), size=23)
            for i, option_id in enumerate(self.options):
                option = WORD_BY_ID[option_id]
                label = option["ru"] if self.quiz_mode == "meaning" else option["en"]
                self.button((194, 299 + i * 76, 612, 60), label, lambda chosen=option_id: self.answer(chosen), fill=(90, 126, 111), size=35)
        else:
            badge = "ПРАВИЛЬНО!" if self.answer_correct else "ПОПРОБУЕМ ЕЩЁ ПОЗЖЕ"
            text(self.canvas, badge, 42, (500, 172), TEAL if self.answer_correct else RED, True)
            self.draw_letter_tiles(word["en"], 500, 223, 37 if len(word["en"]) < 10 else 29)
            text(self.canvas, word["hint"], 40, (300, 293), RED)
            text(self.canvas, word["ru"], 40, (690, 293), TEAL, True)
            if not hatch_complete(self.game) or self.just_hatched:
                egg = self.sprites.scaled("hatching", egg_frame(self.game), 130, 135)
                self.canvas.blit(egg, egg.get_rect(center=(500, 380)))
                if self.just_hatched:
                    text(self.canvas, "Малыш вылупился!", 25, (500, 457), RED, True)
                elif self.answer_correct:
                    text(self.canvas, "На скорлупе новая трещина!", 25, (500, 457), TEAL, True)
                self.button((365, 492, 270, 61), "ДАЛЬШЕ", self.next_card, size=32)
            else:
                if self.just_mastered:
                    text(self.canvas, f"Слово выучено: {mastered_count(self.game)} / 150", 27, (500, 380), TEAL, True)
                self.button((365, 460, 270, 67), "ДАЛЬШЕ", self.next_card, size=34)
        self.button((78, 513, 121, 40), "В САД", self.leave_cards, fill=(124, 111, 89), size=22)
        if pygame.time.get_ticks() / 1000 < self.audio_notice_until:
            text(self.canvas, self.audio_notice, 21, (500, 585), INK)

    def leave_cards(self):
        if self.session_answer_count:
            finish_session(self.game)
        self.screen = "home"
        self.game["lesson"] = None
        self.persist()
        self.notify("Можно продолжить слова в любой момент.")

    def draw_feed(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(115, 100, 770, 430))
        text(self.canvas, "Чем покормим сниффера?", 42, (500, 151), INK, True)
        text(self.canvas, "Новая еда открывается, когда слово выучено", 25, (500, 191), TEAL)
        choices = [("seed", "Семечко", True), ("apple", "Яблоко", mastered(self.game, "apple")), ("carrot", "Морковь", mastered(self.game, "carrot"))]
        for i, (food_id, label, available) in enumerate(choices):
            x = 165 + i * 230
            if food_id == "seed":
                for dx, dy in ((0, 8), (18, 0), (36, 8), (18, 25)):
                    tile(self.canvas, x + 70 + dx, 247 + dy, (215, 161, 78), 18)
            elif food_id == "apple":
                for dx, dy in ((0, 15), (18, 0), (36, 15), (18, 30)):
                    tile(self.canvas, x + 70 + dx, 238 + dy, RED, 22)
                tile(self.canvas, x + 99, 232, (56, 125, 55), 13)
            else:
                for dx, dy in ((0, 0), (14, 14), (28, 28)):
                    tile(self.canvas, x + 76 + dx, 238 + dy, (238, 132, 62), 20)
                tile(self.canvas, x + 69, 231, (56, 125, 55), 16)
            self.button((x, 345, 200, 63), label if available else "Пока закрыто", lambda food=food_id: self.do_feed(food), enabled=available, fill=(174, 112, 61), size=27)
        self.button((390, 448, 220, 52), "НАЗАД", lambda: setattr(self, "screen", "home"), fill=(124, 111, 89))

    def start_play(self):
        stage = growth_stage(self.game)
        if not stage:
            self.notify("Поиграем, когда малыш вылупится!")
            return
        self.pet_game = PetGame(stage, pygame.time.get_ticks())
        self.screen = "play"

    def play_choice(self, index):
        if self.pet_game is not None:
            self.pet_game.choose(index, pygame.time.get_ticks())

    def leave_play(self):
        self.pet_game = None
        self.screen = "home"

    def draw_play_pet(self, center, size=(220, 150), move=None):
        pet = self.sprites.scaled("growth", self.pet_game.stage, *size)
        now = pygame.time.get_ticks()
        x, y = center
        if move == 0:
            y -= int(abs(math.sin(now / 160)) * 45)
        elif move == 1:
            x += int(math.sin(now / 55) * 9)
        elif move == 2:
            pet = pygame.transform.flip(pet, now // 220 % 2 == 0, False)
        self.canvas.blit(pet, pet.get_rect(midbottom=(x, y)))

    def draw_bush(self, rect, color=(66, 132, 65)):
        pygame.draw.rect(self.canvas, (92, 67, 44), (rect.centerx - 13, rect.bottom - 43, 26, 36))
        for dx, dy, w, h in ((0, 35, rect.width, 65), (25, 10, rect.width - 50, 100), (50, 0, rect.width - 100, 100)):
            pygame.draw.rect(self.canvas, color, (rect.x + dx, rect.y + dy, w, h))
        for dx, dy in ((35, 42), (92, 25), (130, 65)):
            tile(self.canvas, rect.x + dx, rect.y + dy, (108, 169, 81), 14, color)

    def draw_treat_game(self):
        activity = self.pet_game
        self.draw_play_pet((500, 290), (175, 95), 1 if activity.phase == "celebrate" else None)
        for i in range(3):
            rect = pygame.Rect(110 + i * 300, 310, 180, 140)
            self.draw_bush(rect)
            text(self.canvas, str(i + 1), 29, (rect.centerx, 453), INK, True)
            if activity.phase == "search":
                self.buttons.append((rect, lambda index=i: self.play_choice(index)))
            if activity.phase == "celebrate" and i == activity.target:
                tile(self.canvas, rect.centerx - 20, 295, RED, 40)
                tile(self.canvas, rect.centerx - 4, 282, TEAL, 15)
                text(self.canvas, "Нашли!", 26, (rect.centerx, 266), TEAL, True)
            elif activity.last_choice is not None and i == activity.target:
                text(self.canvas, "нюх-нюх…", 24, (rect.centerx, 289), TEAL, True)

    def draw_hide_game(self):
        activity = self.pet_game
        for i in range(4):
            rect = pygame.Rect(55 + i * 240, 286, 170, 170)
            # A different piece of the pet peeks out from each hiding place.
            if i == activity.target and activity.phase == "search":
                pet = self.sprites.scaled("growth", 2, 160, 100)
                self.canvas.blit(pet, pet.get_rect(midbottom=(rect.centerx + 52, rect.bottom - 12)))
            if i in (0, 3):
                self.draw_bush(pygame.Rect(rect.x, rect.y + 45, 155, 125))
            elif i == 1:
                pygame.draw.rect(self.canvas, GROUND, (rect.centerx - 25, rect.y + 30, 65, 140))
                self.draw_bush(pygame.Rect(rect.x - 5, rect.y - 25, 180, 110), (49, 114, 63))
            else:
                pygame.draw.rect(self.canvas, (122, 134, 130), (rect.x + 10, rect.y + 60, 145, 110))
                pygame.draw.rect(self.canvas, (155, 166, 159), (rect.x + 35, rect.y + 36, 100, 95))
            if activity.phase == "celebrate" and i == activity.target:
                self.draw_play_pet((rect.centerx, rect.bottom), (180, 135), 0)
                text(self.canvas, "Нашёл!", 26, (rect.centerx, 260), TEAL, True)
            elif activity.last_choice == i and i != activity.target:
                text(self.canvas, "Тут пусто", 24, (rect.centerx, 260), INK)
            if activity.phase == "search":
                self.buttons.append((rect.inflate(25, 10), lambda index=i: self.play_choice(index)))

    def draw_memory_game(self):
        activity = self.pet_game
        move = activity.shown_move(pygame.time.get_ticks())
        self.draw_play_pet((570, 365), (230, 130), move)
        if move is not None:
            text(self.canvas, MOVES[move] + "!", 32, (260, 238), TEAL, True)
        elif activity.phase == "repeat":
            text(self.canvas, f"Повторено: {activity.input_index} / {len(activity.sequence)}", 27, (260, 238), TEAL, True)
        for i, label in enumerate(MOVES):
            self.button((135 + i * 255, 390, 220, 65), label, lambda index=i: self.play_choice(index),
                        enabled=activity.phase == "repeat", fill=TEAL_LIGHT if move == i else TEAL, size=29)
        self.button((725, 526, 240, 48), "ПОКАЖИ ЕЩЁ", lambda: activity.replay(pygame.time.get_ticks()),
                    enabled=activity.phase in ("show", "repeat"), fill=(88, 129, 155), size=24)

    def draw_flower_game(self):
        activity = self.pet_game
        self.draw_play_pet((855, 350), (170, 140), 0 if activity.phase == "celebrate" else None)
        for i, state in enumerate(activity.plants):
            rect = pygame.Rect(100 + i * 235, 282, 185, 75)
            pygame.draw.rect(self.canvas, GROUND, rect)
            pygame.draw.rect(self.canvas, GOLD if i == activity.selected else INK, rect, 4)
            if state == 1:
                for dx in (-20, 0, 20):
                    tile(self.canvas, rect.centerx + dx - 5, rect.centery - 5, GOLD, 10)
            elif state == 2:
                pygame.draw.rect(self.canvas, TEAL, (rect.centerx - 4, rect.y - 27, 8, 48))
                pygame.draw.rect(self.canvas, TEAL_LIGHT, (rect.centerx - 22, rect.y - 21, 22, 12))
            elif state == 3:
                draw_flower(self.canvas, rect.centerx, rect.y - 30, 17, (RED, GOLD, (182, 109, 198))[i])
            if activity.phase == "search":
                self.buttons.append((rect.inflate(0, 60), lambda index=i: activity.select_bed(index)))
        for i, label in enumerate(TOOLS):
            self.button((100 + i * 235, 395, 185, 60), label, lambda index=i: self.play_choice(index),
                        enabled=activity.phase == "search", fill=(88, 129, 155) if i == 1 else TEAL, size=26)

    def draw_play(self):
        if self.pet_game is None:
            self.start_play()
            if self.pet_game is None:
                self.screen = "home"
                self.draw_home()
                return
        self.pet_game.tick(pygame.time.get_ticks())
        if self.pet_game.done:
            self.finish_play()
            self.draw_home()
            return
        self.draw_background()
        pygame.draw.rect(self.canvas, GRASS, (0, 280, WIDTH, HEIGHT - 280))
        for y in range(280, HEIGHT, 34):
            for x in range(0, WIDTH, 34):
                color = (105, 157, 74) if (x // 34 + y // 34) % 2 else (116, 166, 81)
                pygame.draw.rect(self.canvas, color, (x, y, 34, 34))
        self.draw_header()
        panel(self.canvas, pygame.Rect(35, 82, 930, 100))
        text(self.canvas, GAME_NAMES[self.pet_game.stage], 39, (500, 111), TEAL, True)
        unit = "Цветов" if self.pet_game.stage == 4 else "Найдено" if self.pet_game.stage in (1, 2) else "Повторено"
        text(self.canvas, f"{unit}: {self.pet_game.hits} / 3", 25, (500, 153), INK, True)
        if self.pet_game.stage == 1:
            self.draw_treat_game()
        elif self.pet_game.stage == 2:
            self.draw_hide_game()
        elif self.pet_game.stage == 3:
            self.draw_memory_game()
        else:
            self.draw_flower_game()
        text(self.canvas, self.pet_game.message, 24, (500, 493), INK, True)
        self.button((35, 526, 180, 48), "В САД", self.leave_play, fill=(124, 111, 89), size=27)

    def draw_help(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(80, 90, 840, 445))
        lines = [
            "КАК ИГРАТЬ",
            "1. Читай карточки и слушай английские слова.",
            "2. Узнай слово снова в следующем раунде — оно выучено.",
            "3. Превращения питомца: 40, 80 и 120 выученных слов.",
            "4. Корми питомца, играй с ним и убирай за ним.",
            "5. За каждые 15 слов сниффер ищет семечко для сада.",
            "Слова не пропадают, даже если долго не заходить в игру.",
        ]
        for i, line in enumerate(lines):
            text(self.canvas, line, 31 if i == 0 else 26, (500, 141 + i * 51), TEAL if i == 0 else INK, i == 0)
        self.button((390, 463, 220, 53), "НАЗАД", lambda: setattr(self, "screen", "home"), fill=(124, 111, 89))

    def draw_story(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(95, 85, 810, 468))
        english_1, english_2, russian_1, russian_2 = STORIES[self.story_index]
        text(self.canvas, f"История сада {self.story_index + 1} / 10", 35, (500, 132), TEAL, True)
        pet = self.sprites.scaled("growth", growth_stage(self.game), 250, 130)
        self.canvas.blit(pet, pet.get_rect(center=(500, 223)))
        text(self.canvas, english_1, 33, (500, 312), INK, True)
        text(self.canvas, english_2, 33, (500, 350), INK, True)
        text(self.canvas, russian_1, 24, (500, 399), (94, 92, 78))
        text(self.canvas, russian_2, 24, (500, 430), (94, 92, 78))
        self.button((284, 475, 190, 52), "СЛУШАТЬ", lambda: self.play_audio(english_1 + " " + english_2), fill=(88, 129, 155), size=26)
        self.button((526, 475, 190, 52), "В САД", lambda: setattr(self, "screen", "home"), size=28)
        if pygame.time.get_ticks() / 1000 < self.audio_notice_until:
            text(self.canvas, self.audio_notice, 20, (500, 573), INK)

    def draw_profile(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(80, 82, 840, 476))
        text(self.canvas, "ПРОФИЛЬ ПИТОМЦА", 37, (500, 120), TEAL, True)
        text(self.canvas, self.game["pet_name"], 38, (500, 174), INK, True)
        self.button((310, 210, 380, 48), "ИЗМЕНИТЬ ИМЯ", self.edit_name, size=27)
        self.button((140, 287, 340, 55), "ВЫГРУЗИТЬ ПРОФИЛЬ", lambda: self.transfer_profile(True), size=25)
        self.button((520, 287, 340, 55), "ЗАГРУЗИТЬ ПРОФИЛЬ", lambda: self.transfer_profile(False), size=25)
        text(self.canvas, "Игра сохраняется автоматически после каждого действия.", 25, (500, 375), INK)
        text(self.canvas, "Перед удалением игры выгрузите профиль в отдельный файл.", 24, (500, 411), INK)
        text(self.canvas, "После переустановки загрузите этот файл здесь.", 24, (500, 442), INK)
        self.button((390, 487, 220, 49), "В САД", lambda: setattr(self, "screen", "home"), size=27)
        # Keep long platform errors inside the screen.
        text(self.canvas, self.profile_notice[:95], 21, (500, 580), INK)

    def draw_review(self):
        review = self.game["active_review"]
        if review is None:
            self.screen = "home"
            self.draw_home()
            return
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(55, 78, 890, 492))
        text(self.canvas, f"ПРОВЕРКА: {review['milestone']} СЛОВ", 34, (500, 112), TEAL, True)
        if review["phase"] == "summary":
            text(self.canvas, f"Верно: {review_score(review)} / {len(review['queue'])}", 45, (500, 194), TEAL, True)
            mistakes = [word_id for word_id, chosen in zip(review["queue"], review["answers"]) if word_id != chosen]
            text(self.canvas, "Эти слова повторим в следующих проверках:" if mistakes else "Отлично! Ты помнишь все слова!", 27, (500, 254), INK, True)
            for i, word_id in enumerate(mistakes):
                word = WORD_BY_ID[word_id]
                text(self.canvas, f"{word['en']} — {word['ru']}", 27,
                     (290 + (i % 2) * 420, 308 + (i // 2) * 43), TEAL)
            text(self.canvas, "Результат сохранён. Выученные слова и рост не пропадают.", 24, (500, 457), INK)
            self.button((340, 493, 320, 57), "ПРОДОЛЖИТЬ", self.close_review, size=31)
            return
        index = len(review["answers"]) - (1 if review["phase"] == "feedback" else 0)
        word = WORD_BY_ID[review["queue"][index]]
        text(self.canvas, f"Вопрос {index + 1} / {len(review['queue'])}", 25, (500, 153), INK)
        if review["phase"] == "quiz":
            text(self.canvas, "Выбери перевод" if index % 2 == 0 else "Выбери английское слово", 33, (500, 205), INK, True)
            text(self.canvas, word["en"] if index % 2 == 0 else word["ru"], 46, (500, 259), TEAL, True)
            self.button((785, 175, 110, 45), "ЗВУК", lambda: self.play_audio(word["en"]), fill=(88, 129, 155), size=22)
            for i, word_id in enumerate(self.review_options):
                option = WORD_BY_ID[word_id]
                self.button((194, 307 + i * 65, 612, 54), option["ru"] if index % 2 == 0 else option["en"],
                            lambda chosen=word_id: self.submit_review(chosen), size=32)
        else:
            correct = review["answers"][index] == word["id"]
            text(self.canvas, "ПРАВИЛЬНО!" if correct else "ДАВАЙ ЗАПОМНИМ", 39, (500, 221), TEAL if correct else RED, True)
            text(self.canvas, word["en"], 48, (500, 288), INK, True)
            text(self.canvas, word["hint"], 42, (500, 341), RED)
            text(self.canvas, word["ru"], 42, (500, 393), TEAL, True)
            self.button((345, 470, 310, 60), "ИТОГИ" if len(review["answers"]) == 6 else "ДАЛЬШЕ", self.next_review, size=31)
        self.button((78, 517, 140, 36), "ПОЗЖЕ", self.pause_review, fill=(124, 111, 89), size=23)
        if pygame.time.get_ticks() / 1000 < self.audio_notice_until:
            text(self.canvas, self.audio_notice, 21, (500, 585), INK)

    def draw_statistics(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(35, 82, 930, 488))
        text(self.canvas, "СТАТИСТИКА СЛОВ", 34, (500, 111), TEAL, True)
        for i, (tab, label) in enumerate((("overview", "ОБЗОР"), ("words", "СЛОВА"), ("reviews", "ПРОВЕРКИ"))):
            self.button((65 + i * 295, 140, 280, 43), label, lambda value=tab: self.statistics_tab(value),
                        fill=TEAL if self.stats_tab == tab else (100, 111, 125), size=25)
        stats = statistics(self.game)
        if self.stats_tab == "overview":
            text(self.canvas, f"Выучено: {stats['learned']} / 150", 33, (290, 222), TEAL, True)
            text(self.canvas, f"К повторению: {stats['needs_review']}", 31, (720, 222), INK, True)
            accuracy = f"{stats['accuracy']}%" if stats["accuracy"] is not None else "пока нет ответов"
            text(self.canvas, f"Точность: {accuracy}", 28, (500, 265), INK, True)
            text(self.canvas, f"Открыто: {stats['seen']} · Учим: {stats['learning']} · Верно: {stats['correct']} / {stats['attempts']}", 24, (500, 301), INK)
            for i, (name, _) in enumerate(CHAPTERS):
                words = [word for word in WORDS if word["chapter"] == i]
                learned = sum(mastered(self.game, word["id"]) for word in words)
                x, y = 280 + (i // 5) * 450, 347 + (i % 5) * 32
                text(self.canvas, f"{name}: {learned} / 15", 25, (x, y), TEAL if learned == 15 else INK)
            text(self.canvas, "Подсчёт ответов ведётся с обновления; прежний прогресс слов сохранён.", 21, (500, 497), INK)
        elif self.stats_tab == "words":
            text(self.canvas, "Слово", 24, (175, 208), TEAL, True)
            text(self.canvas, "Перевод", 24, (410, 208), TEAL, True)
            text(self.canvas, "Статус", 24, (670, 208), TEAL, True)
            text(self.canvas, "Верно / всего", 23, (855, 208), TEAL, True)
            for i, word in enumerate(WORDS[self.stats_page * 8:(self.stats_page + 1) * 8]):
                y = 244 + i * 32
                counts = self.game["word_stats"].get(word["id"], {})
                attempts = counts.get("lesson_attempts", 0) + counts.get("review_attempts", 0)
                correct = counts.get("lesson_correct", 0) + counts.get("review_correct", 0)
                status = word_status(self.game, word["id"])
                text(self.canvas, word["en"], 26, (175, y), INK, True)
                text(self.canvas, word["ru"], 24, (410, y), INK)
                text(self.canvas, status, 23, (670, y), TEAL if status == "Выучено" else INK)
                text(self.canvas, f"{correct} / {attempts}" if attempts else "—", 24, (855, y), INK)
            last_page = (len(WORDS) - 1) // 8
            self.button((600, 517, 70, 37), "<", lambda: setattr(self, "stats_page", self.stats_page - 1), enabled=self.stats_page > 0)
            text(self.canvas, f"{self.stats_page + 1} / {last_page + 1}", 24, (750, 536), INK)
            self.button((830, 517, 70, 37), ">", lambda: setattr(self, "stats_page", self.stats_page + 1), enabled=self.stats_page < last_page)
        else:
            text(self.canvas, "Короткая проверка после каждых 30 выученных слов", 27, (500, 221), INK, True)
            for i, milestone in enumerate((30, 60, 90, 120, 150)):
                result = next((item for item in self.game["reviews"] if item["milestone"] == milestone), None)
                if result:
                    label = f"Верно: {result['score']} / {result['total']}"
                elif self.game["active_review"] and self.game["active_review"]["milestone"] == milestone:
                    label = "В процессе"
                else:
                    label = "Можно пройти" if stats["learned"] >= milestone else "Ещё не открыта"
                text(self.canvas, f"{milestone} слов", 29, (290, 275 + i * 47), INK, True)
                text(self.canvas, label, 28, (690, 275 + i * 47), TEAL if result else INK)
        self.button((65, 517, 180, 37), "В САД", lambda: setattr(self, "screen", "home"), size=24)

    def cancel_name(self):
        pygame.key.stop_text_input()
        self.screen = "profile"

    def draw_name(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(110, 110, 780, 390))
        text(self.canvas, "Как зовут твоего питомца?", 40, (500, 171), TEAL, True)
        panel(self.canvas, pygame.Rect(220, 240, 560, 60), WHITE)
        text(self.canvas, self.name_input + "|", 36, (500, 270), INK)
        text(self.canvas, "До 20 символов", 24, (500, 330), INK)
        self.button((220, 390, 260, 60), "СОХРАНИТЬ", self.accept_name,
                    enabled=bool(clean_pet_name(self.name_input)), size=28)
        self.button((520, 390, 260, 60), "ОТМЕНА", self.cancel_name, fill=(124, 111, 89), size=28)

    def cancel_import(self):
        self.imported_game = None
        self.screen = "profile"

    def draw_import(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(110, 110, 780, 390))
        text(self.canvas, "Загрузить этот профиль?", 40, (500, 169), TEAL, True)
        text(self.canvas, self.imported_game["pet_name"], 38, (500, 240), INK, True)
        text(self.canvas, f"Выучено слов: {mastered_count(self.imported_game)} / 150", 30, (500, 290), INK)
        text(self.canvas, "Текущий профиль будет заменён. Сначала выгрузите его, если нужен.", 23, (500, 345), RED)
        self.button((220, 390, 260, 60), "ЗАГРУЗИТЬ", self.accept_import, size=28)
        self.button((520, 390, 260, 60), "ОТМЕНА", self.cancel_import, fill=(124, 111, 89), size=28)

    def draw(self):
        self.buttons = []
        if self.screen == "home":
            self.draw_home()
        elif self.screen == "cards":
            self.draw_cards()
        elif self.screen == "feed":
            self.draw_feed()
        elif self.screen == "play":
            self.draw_play()
        elif self.screen == "story":
            self.draw_story()
        elif self.screen == "profile":
            self.draw_profile()
        elif self.screen == "name":
            self.draw_name()
        elif self.screen == "import":
            self.draw_import()
        elif self.screen == "review":
            self.draw_review()
        elif self.screen == "statistics":
            self.draw_statistics()
        else:
            self.draw_help()
        display_size = self.display.get_size()
        scale = min(display_size[0] / WIDTH, display_size[1] / HEIGHT)
        view_size = (max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale)))
        self.viewport = pygame.Rect((display_size[0] - view_size[0]) // 2, (display_size[1] - view_size[1]) // 2, *view_size)
        self.display.fill(INK)
        self.display.blit(pygame.transform.scale(self.canvas, view_size), self.viewport)
        pygame.display.flip()

    def click(self, screen_pos):
        now_ms = pygame.time.get_ticks()
        if now_ms - self.last_pointer_ms < 120 and math.dist(screen_pos, self.last_pointer_pos) < 24:
            return
        self.last_pointer_ms = now_ms
        self.last_pointer_pos = screen_pos
        if not self.viewport.collidepoint(screen_pos):
            return
        x = (screen_pos[0] - self.viewport.left) * WIDTH / self.viewport.width
        y = (screen_pos[1] - self.viewport.top) * HEIGHT / self.viewport.height
        point = (int(x), int(y))
        if self.screen == "home":
            if self.poop_rect and self.poop_rect.collidepoint(point):
                self.do_clean()
                return
            if self.pet_rect.collidepoint(point) and hatch_complete(self.game):
                self.pet_tapped_until = pygame.time.get_ticks() / 1000 + 1.4
                self.notify("Снифферу нравится внимание!")
                return
        for rect, action in reversed(self.buttons):
            if rect.collidepoint(point):
                action()
                return

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.persist()
            self.running = False
        elif event.type in tuple(getattr(pygame, name, -1) for name in
                                 ("APP_WILLENTERBACKGROUND", "APP_DIDENTERBACKGROUND", "WINDOWFOCUSLOST")):
            self.persist()
        elif event.type == pygame.TEXTINPUT and self.screen == "name":
            self.name_input = "".join(c for c in (self.name_input + event.text) if c.isprintable())[:20]
        elif event.type == pygame.KEYDOWN and self.screen == "name":
            if event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif event.key == pygame.K_RETURN:
                self.accept_name()
            elif event.key == pygame.K_ESCAPE:
                self.cancel_name()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.screen == "cards":
                self.leave_cards()
            elif self.screen == "review":
                self.pause_review()
            elif self.screen == "play":
                self.leave_play()
            elif self.screen == "import":
                self.cancel_import()
            else:
                self.screen = "home"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(event.pos)
        elif event.type == pygame.FINGERDOWN:
            w, h = self.display.get_size()
            self.click((event.x * w, event.y * h))


async def main():
    app = GameApp()
    try:
        while app.running:
            for event in pygame.event.get():
                app.handle_event(event)
            app.speech.tick()
            app.poll_profile()
            if app.speech.error:
                app.audio_notice = app.speech.error
                app.audio_notice_until = pygame.time.get_ticks() / 1000 + 4
                app.speech.error = ""
            app.draw()
            await asyncio.sleep(0)
            app.clock.tick(30)
    finally:
        app.persist()
        app.speech.shutdown()
        pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
