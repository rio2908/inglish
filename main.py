"""Sniffer Garden: a small landscape Android game built on MathCraft's pygame stack."""

import asyncio
import json
import math
import os
from pathlib import Path
import random
import sys

import pygame

from game_logic import (
    can_explore, choice_ids, clean, egg_frame, explore, feed, finish_session,
    growth_stage, hatch_complete, mark_seen, mastered, mastered_count,
    new_game, normalize_game, play, record_answer, start_session,
)
from sprites import SnifferSprites
from speech import Speech
from words import WORD_BY_ID


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


def save_path():
    if sys.platform == "android":
        try:
            from android.storage import app_storage_path
            return Path(app_storage_path()) / "sniffer_save.json"
        except Exception:
            pass
    return ROOT / "sniffer_save.json"


def load_game():
    try:
        with save_path().open("r", encoding="utf-8") as file:
            return normalize_game(json.load(file))
    except (OSError, ValueError, TypeError):
        return new_game()


def save_game(game):
    path = save_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(game, file, ensure_ascii=False)
        try:
            os.replace(temporary, path)
        except OSError:
            # Some browser-backed filesystems do not support atomic replace.
            with path.open("w", encoding="utf-8") as file:
                json.dump(game, file, ensure_ascii=False)
    except OSError:
        pass


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
        try:
            pygame.mixer.init()
        except pygame.error:
            pass
        if sys.platform == "android":
            self.display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.display = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Сниффер и сад слов")
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self.pet_rect = pygame.Rect(0, 0, 0, 0)
        self.poop_rect = None
        self.ball_rect = pygame.Rect(0, 0, 0, 0)
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
        self.play_hits = 0
        self.ball_x = 690
        self.story_index = 0
        self.pet_tapped_until = 0
        self.hatching_until = 0
        self.running = True
        self.last_pointer_ms = -1000
        self.last_pointer_pos = (-1000, -1000)

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
            self.audio_notice = "На ПК нет записи слова; на Android работает системная озвучка"
            self.audio_notice_until = pygame.time.get_ticks() / 1000 + 4

    def start_lesson(self):
        self.queue = start_session(self.game)
        self.card_index = 0
        self.session_answer_count = 0
        if not self.queue:
            self.notify("Все слова выучены! Можно повторять главы.")
            return
        save_game(self.game)
        self.screen = "cards"
        self.prepare_card()

    def prepare_card(self):
        if self.card_index >= len(self.queue):
            finish_session(self.game)
            save_game(self.game)
            self.screen = "home"
            self.notify("Раунд закончен! Загляни к снифферу.")
            return
        self.word_id = self.queue[self.card_index]
        record = self.game["cards"].get(self.word_id, {})
        self.card_new = not record.get("seen", False)
        self.card_phase = "intro" if self.card_new else "quiz"
        self.quiz_mode = "meaning" if self.card_new or not record.get("correct_sessions") else "spelling"
        self.options = choice_ids(self.word_id)
        if not self.card_new:
            self.play_audio(self.word_id)

    def intro_done(self):
        mark_seen(self.game, self.word_id)
        save_game(self.game)
        self.card_phase = "quiz"
        self.play_audio(self.word_id)

    def answer(self, chosen_id):
        self.answer_correct = chosen_id == self.word_id
        self.session_answer_count += 1
        before_hatch = hatch_complete(self.game)
        self.just_mastered = record_answer(self.game, self.word_id, self.answer_correct)
        self.just_hatched = not before_hatch and hatch_complete(self.game)
        if self.just_hatched:
            self.hatching_until = pygame.time.get_ticks() / 1000 + 4
        self.card_phase = "result"
        save_game(self.game)

    def next_card(self):
        self.card_index += 1
        self.prepare_card()

    def do_feed(self, food):
        if feed(self.game, food):
            save_game(self.game)
            self.screen = "home"
            self.notify("Сниффер поел и довольно сопит!")

    def do_clean(self):
        if clean(self.game):
            save_game(self.game)
            self.notify("Чисто! Отходы стали компостом для сада.")
        else:
            self.notify("Пока убирать нечего.")

    def do_explore(self):
        if explore(self.game):
            save_game(self.game)
            self.story_index = min(len(STORIES) - 1, self.game["garden_plants"] - 1)
            self.screen = "story"

    def finish_play(self):
        if play(self.game):
            save_game(self.game)
            self.screen = "home"
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
        text(self.canvas, "СНИФФЕР И САД СЛОВ", 38, (240, 33), CREAM, True)
        text(self.canvas, "150 английских слов", 27, (860, 33), GOLD)

    def draw_progress(self):
        rect = pygame.Rect(35, 82, 365, 150)
        panel(self.canvas, rect)
        learned = mastered_count(self.game)
        text(self.canvas, f"Выучено: {learned} / 150", 33, (217, 111), INK, True)
        for i in range(30):
            col, row = i % 15, i // 15
            tile(self.canvas, 55 + col * 22, 144 + row * 29, TEAL_LIGHT if i < learned // 5 else PAPER_DARK, 17)
        text(self.canvas, "1 клетка = 5 слов", 22, (217, 215), (77, 94, 79))

    def draw_garden(self):
        rect = pygame.Rect(35, 247, 618, 237)
        panel(self.canvas, rect, (197, 231, 198))
        pygame.draw.rect(self.canvas, (150, 202, 150), (39, 251, 610, 150))
        pygame.draw.rect(self.canvas, (78, 153, 75), (39, 401, 610, 18))
        pygame.draw.rect(self.canvas, GROUND, (39, 419, 610, 61))
        for x in range(58, 630, 36):
            tile(self.canvas, x, 425 + (x // 36 % 2) * 20, (141, 95, 60), 18, (104, 70, 46))
        for i in range(self.game["garden_plants"]):
            x = 75 + (i % 10) * 52
            y = 393 - (i // 10) * 29
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
            x = 510 if stage >= 3 else 343
        bob = 0 if stage == 0 else int(math.sin(now * 4) * 3)
        self.canvas.blit(pet, pet.get_rect(midbottom=(x, 419 + bob)))
        self.pet_rect = pet.get_rect(midbottom=(x, 419 + bob))
        if self.game["poop"]:
            poop_x = 95 if stage >= 3 else 540
            draw_poop(self.canvas, poop_x, 420)
            self.poop_rect = pygame.Rect(poop_x - 8, 412, 95, 59)
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
        text(self.canvas, STAGE_NAMES[stage], 32, (820, 111), INK, True)
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
            self.button((701, 345, 238, 45), "Поиграть", self.start_play, fill=(84, 129, 168), size=26)
            self.button((701, 402, 238, 45), "Убрать", self.do_clean, enabled=self.game["poop"], fill=(100, 117, 79), size=26)
        self.button((35, 506, 365, 63), "УЧИТЬ СЛОВА", self.start_lesson, fill=TEAL, size=36)
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
            text(self.canvas, word["hint"], 40, (686, 292), RED)
            text(self.canvas, word["ru"], 36, (686, 339), INK, True)
            self.button((586, 382, 246, 54), "СЛУШАТЬ", lambda: self.play_audio(self.word_id), fill=(88, 129, 155), size=26)
            self.button((586, 472, 246, 63), "ПОНЯТНО", self.intro_done, size=32)
        elif self.card_phase == "quiz":
            if self.quiz_mode == "meaning":
                text(self.canvas, "Что означает слово?", 35, (500, 171), INK, True)
                self.draw_letter_tiles(word["en"], 500, 210, 36 if len(word["en"]) < 10 else 29)
            else:
                text(self.canvas, "Выбери английское слово", 35, (500, 171), INK, True)
                text(self.canvas, word["ru"], 45, (500, 233), TEAL, True)
            self.button((782, 145, 115, 49), "ЗВУК", lambda: self.play_audio(self.word_id), fill=(88, 129, 155), size=23)
            for i, option_id in enumerate(self.options):
                option = WORD_BY_ID[option_id]
                label = option["ru"] if self.quiz_mode == "meaning" else option["en"]
                self.button((194, 299 + i * 76, 612, 60), label, lambda chosen=option_id: self.answer(chosen), fill=(90, 126, 111), size=35)
        else:
            badge = "ПРАВИЛЬНО!" if self.answer_correct else "ПОПРОБУЕМ ЕЩЁ ПОЗЖЕ"
            text(self.canvas, badge, 42, (500, 172), TEAL if self.answer_correct else RED, True)
            self.draw_letter_tiles(word["en"], 500, 223, 37 if len(word["en"]) < 10 else 29)
            text(self.canvas, f"{word['hint']}  —  {word['ru']}", 34, (500, 293), INK)
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
        save_game(self.game)
        self.screen = "home"
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
        self.screen = "play"
        self.play_hits = 0
        self.ball_x = 690

    def draw_play(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(80, 90, 840, 450), (211, 235, 204))
        text(self.canvas, "Покидай снифферу мяч!", 40, (500, 138), INK, True)
        text(self.canvas, f"Поймано: {self.play_hits} / 3", 30, (500, 177), TEAL)
        pet = self.sprites.scaled("growth", growth_stage(self.game), 330, 215)
        self.canvas.blit(pet, pet.get_rect(midbottom=(475, 425)))
        t = pygame.time.get_ticks() / 1000
        y = 269 + int(math.sin(t * 5) * 18)
        tile(self.canvas, self.ball_x - 26, y - 26, GOLD, 52)
        self.ball_rect = pygame.Rect(self.ball_x - 38, y - 38, 76, 76)
        self.button((390, 462, 220, 53), "НАЗАД", lambda: setattr(self, "screen", "home"), fill=(124, 111, 89))

    def draw_help(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(80, 90, 840, 445))
        lines = [
            "КАК ИГРАТЬ",
            "1. Читай карточки и слушай английские слова.",
            "2. Узнай слово снова в следующем раунде — оно выучено.",
            "3. Каждые 5 выученных слов заполняют клетку шкалы.",
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
        if self.screen == "play" and self.ball_rect.collidepoint(point):
            self.play_hits += 1
            self.ball_x = random.choice((230, 290, 690, 760))
            if self.play_hits >= 3:
                self.finish_play()
            return
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
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.screen == "cards":
                self.leave_cards()
            else:
                self.screen = "home"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(event.pos)
        elif event.type == pygame.FINGERDOWN:
            w, h = self.display.get_size()
            self.click((event.x * w, event.y * h))


async def main():
    app = GameApp()
    while app.running:
        for event in pygame.event.get():
            app.handle_event(event)
        app.speech.tick()
        app.draw()
        await asyncio.sleep(0)
        app.clock.tick(30)
    save_game(app.game)
    app.speech.shutdown()
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
