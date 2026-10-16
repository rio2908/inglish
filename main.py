"""EnglishCraft: a landscape vocabulary game built on MathCraft's pygame stack."""

import asyncio
import math
import os
from pathlib import Path
import sys
import textwrap

import pygame

from game_logic import (
    can_explore, choice_ids, clean, egg_frame, explore, feed, finish_session,
    growth_stage, hatch_complete, mark_seen, mastered, mastered_count,
    clean_pet_name, growth_remaining, new_game, play, record_answer, start_session,
)
from game_backup import ProfilePicker
from game_storage import read_player_backup_bytes
from player_profiles import PlayerStore, StaleProfileError, player_name
from creature_sprites import GROWTH_SIZES
from habitats import Habitats, SHADOW_COLORS, kelp
from grammar import FORM_QUESTIONS, NOTES
from learning_stats import (
    advance_review, answer_review, pending_review, review_choices, review_score,
    review_cycle, review_species, start_review, statistics, word_status,
)
from pet_games import GAME_NAMES, MOVES, TOOLS, PetGame
from pet_behavior import HeartBurst, LABELS, PetBehavior
from sprites import SnifferSprites
from word_pictures import WordPictures
from instructions import HELP_PAGES
from vocabulary import learned_vocabulary
from speech import Speech
from words import ALL_WORDS, CHAPTERS_BY_SPECIES, WORD_BY_ID, words_for_species
from zoo import (
    SPECIES, SPECIES_NAMES, advance_final_test, answer_final_test, begin_replay, can_replay,
    current_species, final_choices, final_passed, growth_complete,
    pet_learned_count, ready_for_zoo, settle_pet, start_final_test,
)


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


def text(surf, value, size, center, color=INK, bold=False, backdrop=None, max_width=None):
    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    while max_width and font.size(str(value))[0] > max_width and size > 16:
        size -= 1
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
    image = font.render(str(value), True, color)
    rect = image.get_rect(center=center)
    if backdrop is not None:
        pygame.draw.rect(surf, backdrop, rect.inflate(12, 6))
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


def heart_sprite(pixel):
    """A real two-lobed pixel heart; no dependence on the device font's glyphs."""
    rows = ("0110110", "1111111", "1111111", "0111110", "0011100", "0001000")
    sprite = pygame.Surface((9 * pixel, 8 * pixel), pygame.SRCALPHA)
    cells = [(x + 1, y + 1) for y, row in enumerate(rows) for x, value in enumerate(row) if value == "1"]
    for x, y in cells:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            pygame.draw.rect(sprite, (123, 38, 58), ((x + dx) * pixel, (y + dy) * pixel, pixel, pixel))
    for x, y in cells:
        pygame.draw.rect(sprite, (242, 91, 119), (x * pixel, y * pixel, pixel, pixel))
    pygame.draw.rect(sprite, (255, 190, 197), (2 * pixel, pixel, pixel, pixel))
    return sprite


def word_hint_icon(surface, kind, x, y, color):
    """Small drawn icons remain recognizable even if a phone font lacks emoji."""
    if kind == "sound":
        pygame.draw.rect(surface, color, (x, y + 7, 6, 10))
        pygame.draw.polygon(surface, color, ((x + 5, y + 7), (x + 13, y + 1), (x + 13, y + 23), (x + 5, y + 17)))
        pygame.draw.lines(surface, color, False, ((x + 17, y + 7), (x + 20, y + 10), (x + 20, y + 14), (x + 17, y + 17)), 2)
        pygame.draw.lines(surface, color, False, ((x + 21, y + 3), (x + 25, y + 8), (x + 25, y + 16), (x + 21, y + 21)), 2)
    else:
        pygame.draw.rect(surface, color, (x, y + 3, 26, 20))
        for dx in (2, 14):
            pygame.draw.rect(surface, WHITE, (x + dx, y + 5, 10, 15))
            for dy in (8, 12, 16):
                pygame.draw.rect(surface, color, (x + dx + 2, y + dy, 6, 1))


def word_hint_row(surface, value, kind, center, size, color, bold=False):
    font = pygame.font.Font(None, size)
    font.set_bold(bold)
    while font.size(value)[0] > 380 and size > 16:
        size -= 1
        font = pygame.font.Font(None, size)
        font.set_bold(bold)
    width = font.size(value)[0]
    left = round(center[0] - (width + 42) / 2)
    word_hint_icon(surface, kind, left, center[1] - 12, color)
    text(surface, value, size, (left + 42 + width // 2, center[1]), color, bold)


def contextual_sentence(surface, subject, form, ending, center, size=29, max_width=720, focus=None):
    """Keep the subject and verb visually distinct, without relying only on prose."""
    font = pygame.font.Font(None, size)
    font.set_bold(True)
    while sum(font.size(part)[0] for part in (subject, form, ending)) + 18 > max_width and size > 16:
        size -= 1
        font = pygame.font.Font(None, size)
        font.set_bold(True)
    widths = [font.size(part)[0] for part in (subject, form, ending)]
    focused = [part.casefold().strip(".?!") == focus.casefold() for part in (subject, form, ending)] if focus else [False, True, False]
    if not any(focused):
        focused = [False, True, False]
    x = center[0] - (sum(widths) + 18) // 2
    for i, (part, width, color) in enumerate(zip((subject, form, ending), widths, (TEAL, RED, INK))):
        if focus:
            color = RED if focused[i] else INK
        if focused[i]:
            pygame.draw.rect(surface, (255, 224, 170), (x - 3, center[1] - size // 2, width + 6, size))
        text(surface, part, size, (x + width // 2, center[1]), color, True)
        x += width + 9


class GameApp:
    def __init__(self, profile_store=None):
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
        pygame.display.set_caption("EnglishCraft")
        pygame.display.set_icon(pygame.image.load(str(ROOT / "assets" / "icon.png")))
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.viewport = pygame.Rect(0, 0, WIDTH, HEIGHT)
        self.pet_rect = pygame.Rect(0, 0, 0, 0)
        self.poop_rect = None
        self.clock = pygame.time.Clock()
        self.sprites = SnifferSprites()
        self.habitats = Habitats()
        self.word_pictures = WordPictures()
        self.players = profile_store if profile_store is not None else PlayerStore()
        self.player_id = None
        self.player_name = ""
        self.player_revision = None
        self.save_conflict = False
        self.game = new_game()
        self.sprites.select_species(current_species(self.game))
        self.screen = "home"
        self.buttons = []
        self.input_ready = False
        self.button_scope = None
        self.message = "Занимайся словами и помоги питомцу вылупиться!" if not hatch_complete(self.game) else "Питомец ждёт тебя в саду!"
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
        self.crack_advanced = False
        self.session_answer_count = 0
        self.pet_game = None
        self.story_index = 0
        self.pet_behavior = PetBehavior(growth_stage(self.game), pygame.time.get_ticks() / 1000)
        self.hearts = HeartBurst()
        self.heart_sprites = {size: heart_sprite(size) for size in (3, 4)}
        self.hatching_until = 0
        self.running = True
        self.last_pointer_ms = -1000
        self.last_pointer_pos = (-1000, -1000)
        self.profile_picker = ProfilePicker(decoder=read_player_backup_bytes)
        self.imported_game = None
        self.imported_player = None
        self.profile_transfer_started = False
        self.profile_transfer_owner = None
        self.name_input = self.game["pet_name"]
        self.profile_notice = ""
        self.review_options = []
        self.final_options = []
        self.stats_tab = "overview"
        self.stats_page = 0
        self.stats_review_index = 0
        self.zoo_selection = 0
        self.profile_cache = []
        self.login_page = 0
        self.login_notice = ""
        self.storage_error = ""
        self.registration_input = ""
        self.registration_game = None
        self.name_kind = "pet"
        self.name_error = ""
        self.help_page = 0
        self.help_return = "home"
        self.dictionary_return = "home"
        self.dictionary_species = None
        self.dictionary_page = 0
        self.dictionary_query = ""
        self.dictionary_errors = False
        self.dictionary_reveal = True
        self.dictionary_typing = False
        self.open_login(initial=True)

    def refresh_players(self):
        try:
            self.profile_cache = self.players.list_players()
            self.storage_error = ""
            return True
        except Exception as error:
            self.storage_error = f"Не удалось открыть игроков: {error}"
            self.profile_cache = []
            return False

    def open_login(self, initial=False):
        if self.player_id is not None and not self.persist():
            return
        pygame.key.stop_text_input()
        self.speech.stop()
        self.input_ready = False
        self.player_id = None
        self.player_name = ""
        self.player_revision = None
        self.save_conflict = False
        self.game = new_game()
        self.sprites.select_species("sniffer")
        self.pet_behavior = PetBehavior(0, pygame.time.get_ticks() / 1000)
        self.imported_game = self.imported_player = None
        self.registration_game = None
        self.pet_game = None
        self.hearts = HeartBurst()
        self.queue = []
        self.word_id = None
        self.login_page = 0
        self.refresh_players()
        self.screen = "login"
        if initial and not self.profile_cache and not self.storage_error:
            self.open_registration()

    def open_registration(self, game=None):
        if self.storage_error:
            return
        self.registration_game = game
        self.registration_input = ""
        self.login_notice = ""
        self.screen = "register"
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(240, 225, 520, 60))

    def submit_registration(self):
        try:
            identity = self.players.create_player(self.registration_input, self.registration_game)
        except Exception as error:
            self.login_notice = str(error)
            return
        self.registration_game = None
        pygame.key.stop_text_input()
        self.enter_player(identity)

    def activate_game(self, game):
        self.speech.stop()
        self.input_ready = False
        self.save_conflict = False
        self.game = game
        self.sprites.select_species(current_species(game))
        self.pet_behavior = PetBehavior(growth_stage(game), pygame.time.get_ticks() / 1000)
        self.hearts = HeartBurst()
        self.pet_game = None
        self.pet_rect = pygame.Rect(0, 0, 0, 0)
        self.poop_rect = None
        self.queue = []
        self.options = []
        self.review_options = []
        self.final_options = []
        self.word_id = None
        self.card_index = 0
        self.card_phase = "intro"
        self.card_new = False
        self.quiz_mode = "meaning"
        self.answer_correct = self.just_mastered = self.just_hatched = False
        self.crack_advanced = False
        self.session_answer_count = 0
        self.hatching_until = 0
        self.audio_notice = ""
        self.audio_notice_until = 0
        self.name_input = game["pet_name"]
        self.name_kind = "pet"
        self.name_error = ""
        self.profile_notice = ""
        self.stats_tab = "overview"
        self.stats_page = 0
        self.stats_review_index = [item[0] for item in SPECIES].index(current_species(game))
        self.story_index = 0
        self.dictionary_return = "home"
        self.dictionary_species = None
        self.dictionary_page = 0
        self.dictionary_query = ""
        self.dictionary_errors = False
        self.dictionary_reveal = True
        self.dictionary_typing = False
        self.zoo_selection = 0
        self.screen = "home"
        self.restore_lesson()

    def enter_player(self, identity):
        if self.player_id is not None and self.player_id != identity and not self.persist():
            return
        try:
            profile = self.players.load_profile(identity)
            self.players.select_player(identity)
        except Exception as error:
            self.login_notice = str(error)
            return False
        pygame.key.stop_text_input()
        self.player_id, self.player_name = identity, profile["name"]
        self.player_revision = profile["revision"]
        self.activate_game(profile["game"])
        self.notify(f"Привет, {self.player_name}! Это твой питомец.")
        return True

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
        exam = self.game["zoo"]["exam"]
        if exam is not None and exam["phase"] in ("quiz", "feedback"):
            self.final_options = final_choices(self.game)
            self.screen = "final_test"
        if self.game.get("growth_notice"):
            self.screen = "growth"

    def persist(self):
        if self.player_id is None:
            return True
        if self.screen == "cards" and self.word_id:
            self.game["lesson"] = {
                "queue": self.queue[:], "index": self.card_index,
                "phase": self.card_phase, "mode": self.quiz_mode,
                "correct": self.answer_correct, "answers": self.session_answer_count,
            }
        try:
            self.player_revision = self.players.save_game(self.player_id, self.game, expected_revision=self.player_revision)
            return True
        except StaleProfileError as error:
            self.save_conflict = True
            self.profile_notice = str(error)
            self.speech.stop()
            return False
        except Exception as error:
            self.notify("Не удалось сохранить игру. Выгрузите профиль.", 8)
            self.profile_notice = f"Ошибка сохранения: {error}"
            return False

    def check_profile_freshness(self):
        if self.player_id is None:
            return
        try:
            if self.players.revision(self.player_id) != self.player_revision:
                self.save_conflict = True
                self.profile_notice = "Сохранение обновилось в другом окне. Старые данные не будут записаны поверх него."
                self.speech.stop()
        except Exception as error:
            self.profile_notice = f"Не удалось проверить сохранение: {error}"

    def open_profile(self):
        self.name_input = self.game["pet_name"]
        self.screen = "profile"

    def open_help(self):
        self.help_return = self.screen
        self.help_page = 0
        pygame.key.stop_text_input()
        self.screen = "help"

    def close_help(self):
        self.screen = self.help_return
        if self.player_id is None and self.screen not in ("login", "register"):
            self.screen = "login"
        if self.screen == "register":
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(pygame.Rect(240, 225, 520, 60))

    def open_dictionary(self, species=None):
        if self.player_id is None:
            return
        self.dictionary_return = self.screen
        self.dictionary_species = species
        self.dictionary_page = 0
        self.dictionary_query = ""
        self.dictionary_errors = False
        self.dictionary_reveal = True
        self.dictionary_typing = False
        self.speech.stop()
        self.screen = "dictionary"

    def close_dictionary(self):
        pygame.key.stop_text_input()
        self.dictionary_typing = False
        self.speech.stop()
        self.screen = self.dictionary_return

    def search_dictionary(self):
        self.dictionary_typing = True
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(65, 192, 790, 35))

    def dictionary_filter(self, species):
        self.dictionary_species = species
        self.dictionary_page = 0
        self.dictionary_typing = False
        pygame.key.stop_text_input()

    def toggle_dictionary_errors(self):
        self.dictionary_errors = not self.dictionary_errors
        self.dictionary_page = 0

    def clear_dictionary_search(self):
        self.dictionary_query = ""
        self.dictionary_page = 0

    def edit_name(self):
        self.name_kind = "pet"
        self.name_error = ""
        self.name_input = self.game["pet_name"]
        self.screen = "name"
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(220, 240, 560, 60))

    def edit_player_name(self):
        self.name_kind = "player"
        self.name_error = ""
        self.name_input = self.player_name
        self.screen = "name"
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(220, 240, 560, 60))

    def accept_name(self):
        if self.name_kind == "player":
            try:
                self.player_name = self.players.rename_player(self.player_id, self.name_input)
            except Exception as error:
                self.name_error = str(error)
                return
            pygame.key.stop_text_input()
            self.screen = "profile"
            self.profile_notice = "Имя игрока сохранено."
            return
        name = clean_pet_name(self.name_input)
        if not name:
            return
        self.game["pet_name"] = name
        for resident in self.game["zoo"]["residents"]:
            if resident["species"] == current_species(self.game) and not self.game["zoo"]["replay"]:
                resident["name"] = name
        pygame.key.stop_text_input()
        self.screen = "profile"
        if self.persist():
            self.profile_notice = "Имя сохранено."

    def transfer_profile(self, export):
        try:
            if self.profile_picker.busy:
                raise ValueError("Дождись завершения текущего выбора файла")
            if not self.persist() and not export:
                return
            if export and self.player_id is None:
                raise ValueError("Сначала выбери игрока")
            # A copy must remain exportable even if the private store cannot be
            # read/written. Identity was verified on entry and rename.
            metadata = {"id": self.player_id, "name": self.player_name} if self.player_id else None
            owner = self.player_id
            if self.profile_picker.start(export, self.game, metadata):
                self.profile_transfer_owner = owner
                self.profile_transfer_started = True
        except Exception as error:
            self.profile_notice = f"Не удалось открыть файл: {error}"
            self.login_notice = self.profile_notice

    def poll_profile(self):
        result = self.profile_picker.poll()
        if result:
            if self.profile_transfer_started and self.profile_transfer_owner != self.player_id:
                self.profile_transfer_started = False
                self.login_notice = "Игрок сменился. Откройте файл профиля заново."
                return
            self.profile_transfer_started = False
            self.profile_notice, imported = result
            self.login_notice = self.profile_notice
            if imported is not None:
                if "game" in imported and "player" in imported:
                    self.imported_game = imported["game"]
                    self.imported_player = imported["player"]
                else:
                    self.imported_game, self.imported_player = imported, None
                self.screen = "import"

    def accept_import(self):
        backup = {"player": self.imported_player, "game": self.imported_game}
        try:
            mode, _ = self.players.import_target(backup, self.player_id)
            if mode == "register":
                game = self.imported_game
                self.imported_game = self.imported_player = None
                self.open_registration(game)
                return
            identity = self.players.restore_backup(backup, self.player_id)
        except Exception as error:
            self.profile_notice = f"Профиль не загружен: {error}"
            self.login_notice = self.profile_notice
            self.screen = "profile" if self.player_id else "login"
            return
        self.imported_game = self.imported_player = None
        if self.enter_player(identity):
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
        else:
            self.audio_notice = ""
            self.audio_notice_until = 0

    def start_lesson(self):
        exam = self.game["zoo"]["exam"]
        if (self.game["growth_notice"] or self.game["lesson"] or self.game["active_review"] is not None
                or (exam and exam["phase"] in ("quiz", "feedback"))):
            self.restore_lesson()
            return
        if pending_review(self.game) is not None:
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
            self.notify("Раунд закончен! Загляни к питомцу.")
            if pending_review(self.game) is not None:
                self.open_review()
            return
        self.word_id = self.queue[self.card_index]
        record = self.game["cards"].get(self.word_id, {})
        self.card_new = not record.get("seen", False)
        self.card_phase = "intro" if self.card_new else "quiz"
        if self.game["zoo"]["replay"]:
            record = self.game["zoo"]["pet_cards"].get(self.word_id, {})
        self.quiz_mode = "meaning" if self.card_new or not record.get("correct_sessions") else "spelling"
        self.options = choice_ids(self.word_id)
        self.persist()
        if pending_review(self.game) is not None:
            self.open_review()
        elif not self.card_new:
            self.play_audio(self.word_id)

    def intro_done(self):
        if self.screen != "cards" or self.card_phase != "intro" or self.word_id is None:
            return
        mark_seen(self.game, self.word_id)
        self.card_phase = "quiz"
        self.persist()
        self.play_audio(self.word_id)

    def answer(self, chosen_id):
        if self.screen != "cards" or self.card_phase != "quiz" or self.word_id is None:
            return
        self.answer_correct = chosen_id == self.word_id
        self.session_answer_count += 1
        before_hatch = hatch_complete(self.game)
        before_crack = egg_frame(self.game)
        self.just_mastered = record_answer(self.game, self.word_id, self.answer_correct)
        self.just_hatched = not before_hatch and hatch_complete(self.game)
        self.crack_advanced = egg_frame(self.game) > before_crack
        if self.just_hatched:
            self.hatching_until = pygame.time.get_ticks() / 1000 + 4
        self.card_phase = "result"
        self.persist()
        if self.game["growth_notice"]:
            self.screen = "growth"

    def next_card(self):
        if self.screen != "cards" or self.card_phase != "result":
            return
        if self.game["growth_notice"]:
            self.screen = "growth"
            return
        self.card_index += 1
        self.prepare_card()

    def acknowledge_growth(self):
        notice = self.game["growth_notice"]
        self.game["growth_notice"] = None
        if notice and notice["after"] == 1:
            self.hatching_until = pygame.time.get_ticks() / 1000 + 4
        self.screen = "home"
        self.restore_lesson()
        self.persist()

    def open_review(self):
        if start_review(self.game) is None:
            return
        self.review_options = review_choices(self.game)
        self.screen = "review"
        self.persist()

    def submit_review(self, chosen_id):
        if self.screen != "review":
            return
        if answer_review(self.game, chosen_id):
            self.persist()

    def next_review(self):
        if self.screen != "review" or self.game["active_review"] is None or self.game["active_review"]["phase"] != "feedback":
            return
        advance_review(self.game)
        self.review_options = review_choices(self.game)
        self.persist()

    def close_review(self):
        review = self.game["active_review"]
        if self.screen != "review" or review is None or review["phase"] != "summary":
            return
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
        self.stats_review_index = [item[0] for item in SPECIES].index(current_species(self.game))
        self.screen = "statistics"

    def statistics_tab(self, tab):
        self.stats_tab = tab
        self.stats_page = 0

    def open_zoo(self):
        self.screen = "zoo"

    def settle_current_pet(self):
        if growth_complete(self.game) and not final_passed(self.game):
            self.open_final_test()
            return
        was_replay = self.game["zoo"]["replay"]
        if not settle_pet(self.game):
            return
        self.sprites.select_species(current_species(self.game))
        self.pet_behavior = PetBehavior(growth_stage(self.game), pygame.time.get_ticks() / 1000)
        self.hearts = HeartBurst()
        self.hatching_until = 0
        self.pet_game = None
        self.queue = []
        self.word_id = None
        self.screen = "zoo"
        self.persist()
        self.notify("Повторное выращивание завершено. Твой питомец вернулся!" if was_replay else "Новый питомец ждёт на лужайке!" if len(self.game["zoo"]["residents"]) < len(SPECIES) else "Весь зоопарк собран!")

    def open_final_test(self, retry=False):
        if start_final_test(self.game, retry=retry) is None:
            return
        self.final_options = final_choices(self.game)
        self.screen = "final_test"
        self.persist()

    def submit_final_test(self, chosen):
        if self.screen != "final_test":
            return
        if answer_final_test(self.game, chosen):
            self.persist()

    def next_final_test(self):
        if self.screen != "final_test" or self.game["zoo"]["exam"] is None or self.game["zoo"]["exam"]["phase"] != "feedback":
            return
        advance_final_test(self.game)
        self.final_options = final_choices(self.game)
        self.persist()

    def pause_final_test(self):
        self.screen = "zoo"
        self.persist()

    def request_replay(self, index):
        if can_replay(self.game, index):
            self.zoo_selection = index
            self.screen = "replay_confirm"

    def start_replay(self):
        if not begin_replay(self.game, self.zoo_selection):
            return
        self.sprites.select_species(current_species(self.game))
        self.pet_behavior = PetBehavior(0, pygame.time.get_ticks() / 1000)
        self.pet_behavior.x = 400
        self.hearts = HeartBurst()
        self.pet_game = None
        self.queue = []
        self.word_id = None
        self.hatching_until = 0
        self.screen = "home"
        self.persist()
        self.notify("Новое яйцо! Старший друг будет рядом.")

    def inspect_resident(self, index):
        self.zoo_selection = index
        self.screen = "resident"

    def do_feed(self, food):
        if feed(self.game, food):
            self.screen = "home"
            self.persist()
            self.notify("Питомец поел и радуется угощению!")

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

    def draw_background(self, species=None, play=False, stage=None):
        age = growth_stage(self.game) if species is None else 0
        self.habitats.draw(self.canvas, species or current_species(self.game), pygame.time.get_ticks() / 1000, play, age if stage is None else stage)

    def draw_header(self):
        pygame.draw.rect(self.canvas, INK, (0, 0, WIDTH, 65))
        text(self.canvas, "EnglishCraft", 40, (170, 26 if self.player_id else 33), CREAM, True)
        if self.player_id:
            text(self.canvas, "Игрок: " + self.player_name, 18, (170, 55), GOLD, max_width=305)
        if self.screen == "home" and not self.save_conflict:
            self.button((345, 10, 175, 43), "ЗООПАРК", self.open_zoo, fill=(119, 138, 65), size=26)
            self.button((535, 10, 220, 43), "СТАТИСТИКА", self.open_statistics, fill=(88, 129, 155), size=25)
            self.button((770, 10, 195, 43), "ПРОФИЛЬ", self.open_profile, fill=TEAL, size=27)
        elif self.screen in ("login", "register"):
            self.button((770, 10, 195, 43), "КАК ИГРАТЬ", self.open_help, fill=(88, 129, 155), size=25)
        else:
            text(self.canvas, "900 слов · 6 питомцев", 25, (860, 33), GOLD)

    def draw_progress(self):
        rect = pygame.Rect(35, 82, 618, 88)
        panel(self.canvas, rect)
        learned = pet_learned_count(self.game)
        label = "Повторено" if self.game["zoo"]["replay"] else "Выучено для питомца"
        text(self.canvas, f"{label}: {learned} / 150", 30, (344, 108), INK, True)
        kind, remaining = growth_remaining(self.game)
        if kind == "hatch_words":
            caption = f"До вылупления — выучить слов: {remaining}"
        elif kind == "words":
            caption = f"До следующего превращения — слов: {remaining}"
        else:
            caption = "Питомец вырос! Собери зоопарк после 150 слов."
        if growth_complete(self.game) and not final_passed(self.game):
            caption = "150 слов! Пройди итоговый тест на 70%."
        elif ready_for_zoo(self.game):
            caption = "150 слов! Посели питомца в зоопарке."
        elif len(self.game["zoo"]["residents"]) == len(SPECIES) and not self.game["zoo"]["replay"]:
            caption = "Весь зоопарк собран! Все друзья выросли."
        text(self.canvas, caption, 26, (344, 145), TEAL, True)

    def draw_garden(self):
        self.sprites.select_species(current_species(self.game))
        species = current_species(self.game)
        stage = growth_stage(self.game)
        # The pet lives on the main meadow, not in a separate framed scene.
        for x in range(55, 640, 47):
            y = 453 + (x % 3) * 9
            if species != "axolotl":
                pygame.draw.line(self.canvas, (65, 126, 58), (x, y), (x - 5, y - 9), 3)
                pygame.draw.line(self.canvas, (65, 126, 58), (x, y), (x + 5, y - 12), 3)
        visible_plants = min(self.game["garden_plants"], (0, 3, 6, 8, 10)[stage])
        for i in range(visible_plants):
            x = 75 + (i % 10) * 52
            y = 473 - (i // 10) * 29
            if species == "axolotl":
                kelp(self.canvas, x, y + 20, 33 + (i % 3) * 8)
            else:
                draw_flower(self.canvas, x, y, 9, GOLD if i % 2 else (235, 98, 144))

        now = pygame.time.get_ticks() / 1000
        self.pet_behavior.left_bound = 405 if self.game["zoo"]["replay"] else 225
        self.pet_behavior.right_bound = 480 if self.game["zoo"]["replay"] else 460
        if self.game["zoo"]["replay"]:
            self.pet_behavior.x = max(405, self.pet_behavior.x)
            older = self.sprites.scaled_species(species, "growth", 4, 200, 170)
            self.canvas.blit(older, older.get_rect(midbottom=(130, 455)))
            text(self.canvas, "Старший друг", 20, (130, 265), TEAL, True, backdrop=CREAM)
        pose = self.pet_behavior.update(stage, now)
        if stage == 0:
            family, index = "hatching", egg_frame(self.game)
            pet = self.sprites.scaled(family, index, 180, 162)
        elif now < self.hatching_until:
            size = (275, 164) if current_species(self.game) == "sniffer" else GROWTH_SIZES[1]
            pet = self.sprites.scaled("hatching", 4, *size)
        elif current_species(self.game) != "sniffer":
            walking = stage == 2 and pose.action == "walk"
            pet = self.sprites.scaled("walk" if walking else "growth", pose.walk_frame if walking else stage, *GROWTH_SIZES[stage])
        elif stage == 2 and pose.action == "walk":
            pet = self.sprites.scaled("walk", pose.walk_frame, 350, 196)
        else:
            pet = self.sprites.scaled("growth", stage, 285 if stage >= 3 else 290, 225 if stage >= 3 else 165)
        pet = pygame.transform.scale(pet, (max(1, round(pet.get_width() * pose.scale_x)),
                                           max(1, round(pet.get_height() * pose.scale_y))))
        if pose.flip:
            pet = pygame.transform.flip(pet, True, False)
        if abs(pose.angle) > 0.3:
            pet = pygame.transform.rotate(pet, pose.angle)
        x = round(pose.x)
        pygame.draw.ellipse(self.canvas, SHADOW_COLORS[species], (x - pet.get_width() // 2, 439, pet.get_width(), 24))
        float_y = -13 + math.sin(self.pet_behavior.time * 5) * 5 if stage and species in ("bee", "allay", "axolotl") else 0
        self.pet_rect = pet.get_rect(midbottom=(x, round(455 + pose.bob + float_y)))
        self.canvas.blit(pet, self.pet_rect)
        caption_y = max(192, self.pet_rect.top - 20)
        if pose.action != "happy":
            caption = "Плавает и изучает дно" if species == "axolotl" and pose.action in ("walk", "toddle", "hop") else LABELS[pose.action]
            text(self.canvas, caption, 23, (x, caption_y), TEAL, True, backdrop=CREAM)
        if pose.action == "rest" and stage:
            text(self.canvas, "Z z", 26, (self.pet_rect.right - 25, self.pet_rect.top - 5), TEAL)
        if pose.action == "bloom":
            for i in range(5):
                phase = (self.pet_behavior.time * 0.6 + i * 0.2) % 1
                px = x + math.sin(self.pet_behavior.time * 1.5 + i * 1.8) * (55 + phase * 55)
                py = self.pet_rect.top + 20 + phase * 120
                pygame.draw.rect(self.canvas, (245, 164, 192) if i % 2 else GOLD, (round(px), round(py), 7, 7))
        if self.game["poop"]:
            poop_x = 95 if stage >= 3 else 540
            draw_poop(self.canvas, poop_x, 440)
            self.poop_rect = pygame.Rect(poop_x - 8, 432, 95, 59)
        else:
            self.poop_rect = None
        for hx, hy, size, alpha in self.hearts.frame(now):
            heart = self.heart_sprites[size]
            heart.set_alpha(alpha)
            self.canvas.blit(heart, heart.get_rect(center=(round(hx), round(hy))))

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
        stage_name = "Выросший питомец" if stage == 4 and current_species(self.game) != "sniffer" else STAGE_NAMES[stage]
        if stage == 0 and egg_frame(self.game) == 4:
            stage_name = "Вылупляется"
        text(self.canvas, stage_name, 23, (820, 132), TEAL)
        if stage == 0:
            text(self.canvas, f"Трещин: {egg_frame(self.game)} / 4", 27, (820, 156), TEAL, True)
            text(self.canvas, "30 выученных слов — малыш", 23, (820, 190), INK)
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
        exam = self.game["zoo"]["exam"]
        testing = self.game["active_review"] is not None or (exam and exam["phase"] in ("quiz", "feedback"))
        label = "ПРОДОЛЖИТЬ ТЕСТ" if testing else "ПРОДОЛЖИТЬ УРОК" if self.game["lesson"] else f"ПРОВЕРКА: {milestone} СЛОВ" if milestone else "УЧИТЬ СЛОВА"
        self.button((35, 506, 365, 63), label, self.start_lesson, fill=TEAL, size=36 if label == "УЧИТЬ СЛОВА" else 29)
        available = self.game["garden_plants"] < min(10, mastered_count(self.game) // 15)
        self.button((420, 506, 232, 63), "ИСКАТЬ СЕМЕНА", self.do_explore, enabled=can_explore(self.game), fill=(119, 138, 65), size=27)
        if available and not can_explore(self.game):
            text(self.canvas, "Сначала позаботься о питомце", 20, (536, 491), RED, True)
        self.button((676, 506, 175, 63), "СЛОВАРИК", self.open_dictionary, fill=(88, 129, 155), size=25)
        self.button((865, 506, 100, 63), "СПРАВКА", self.open_help, fill=(100, 111, 125), size=19)
        if self.message:
            text(self.canvas, self.message, 25, (500, 584), INK, True)

    def draw_letter_tiles(self, value, center_x, y, cell=34, max_width=760):
        gap = 4
        cell = min(cell, max(12, (max_width + gap) // max(1, len(value)) - gap))
        width = len(value) * (cell + gap) - gap
        x = center_x - width // 2
        for char in value:
            tile(self.canvas, x, y, WHITE, cell)
            text(self.canvas, char, cell + 3, (x + cell // 2, y + cell // 2 + 1), INK, True)
            x += cell + gap

    def draw_word_art(self, word):
        rect = pygame.Rect(108, 175, 325, 277)
        underwater = current_species(self.game) == "axolotl"
        panel(self.canvas, rect, (113, 195, 204) if underwater else (213, 235, 205))
        pictured = self.word_pictures.draw(self.canvas, word["id"], pygame.Rect(143, 202, 256, 201))
        if not pictured:
            text(self.canvas, "ПРИДУМАЙ СВОЙ ПРИМЕР", 23, (271, 233), TEAL, True, max_width=295)
            self.draw_letter_tiles(word["en"], 271, 275, 25, max_width=278)
            text(self.canvas, word["ru"], 28, (271, 355), INK, True, max_width=285)
        text(self.canvas, "Запомни по картинке" if pictured else "Что ты представляешь?", 21, (271, 429), INK)

    def draw_grammar_note(self, word):
        rule, examples = NOTES[word["id"]]
        panel(self.canvas, pygame.Rect(108, 175, 325, 277), (235, 241, 218))
        text(self.canvas, "КАК ИСПОЛЬЗОВАТЬ", 24, (271, 198), TEAL, True)
        for i, line in enumerate(textwrap.wrap(rule, width=29)[:4]):
            text(self.canvas, line, 22, (271, 231 + i * 21), INK, max_width=300)
        for i, (subject, form, ending, russian) in enumerate(examples):
            y = 337 + i * 62
            contextual_sentence(self.canvas, subject, form, ending, (271, y), size=25, max_width=295, focus=word["en"])
            text(self.canvas, russian, 22, (271, y + 25), INK, max_width=295)

    def draw_cards(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(55, 78, 890, 492))
        word = WORD_BY_ID[self.word_id]
        text(self.canvas, f"Глава {word['chapter'] + 1}: {word['chapter_name']}", 27, (297, 111), TEAL, True)
        text(self.canvas, f"{self.card_index + 1} / {len(self.queue)}", 27, (855, 111), INK, True)
        if self.card_phase == "intro":
            if word["id"] in NOTES:
                self.draw_grammar_note(word)
            else:
                self.draw_word_art(word)
            text(self.canvas, "Новое слово", 28, (686, 163), TEAL, True)
            self.draw_letter_tiles(word["en"], 686, 198, 34 if len(word["en"]) < 10 else 28, max_width=425)
            word_hint_row(self.canvas, word["hint"], "sound", (686, 292), 46, RED)
            pygame.draw.line(self.canvas, PAPER_DARK, (483, 314), (896, 314))
            word_hint_row(self.canvas, word["ru"], "book", (686, 349), 42, TEAL, True)
            self.button((586, 382, 246, 54), "СЛУШАТЬ", lambda: self.play_audio(self.word_id), fill=(88, 129, 155), size=26)
            self.button((586, 472, 246, 63), "ПОНЯТНО", self.intro_done, size=32)
        elif self.card_phase == "quiz":
            contextual = FORM_QUESTIONS.get(word["id"])
            if contextual:
                subject, ending, russian = contextual
                text(self.canvas, "Вставь пропущенное слово", 33, (500, 171), INK, True)
                contextual_sentence(self.canvas, subject, "___", ending, (500, 228), size=42)
                text(self.canvas, russian, 27, (500, 271), TEAL)
            elif self.quiz_mode == "meaning":
                text(self.canvas, "Что означает слово?", 35, (500, 171), INK, True)
                self.draw_letter_tiles(word["en"], 500, 210, 36 if len(word["en"]) < 10 else 29)
            else:
                text(self.canvas, "Выбери английское слово", 35, (500, 171), INK, True)
                text(self.canvas, word["ru"], 49, (500, 233), TEAL, True, max_width=740)
            self.button((782, 145, 115, 49), "ЗВУК", lambda: self.play_audio(self.word_id), fill=(88, 129, 155), size=23)
            for i, option_id in enumerate(self.options):
                option = WORD_BY_ID[option_id]
                label = option["en"] if contextual else option["ru"] if self.quiz_mode == "meaning" else option["en"]
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
                    caption = "На скорлупе новая трещина!" if self.crack_advanced else "Слово выучено! Яйцо растёт." if self.just_mastered else "Верно! Повторим слово позже."
                    text(self.canvas, caption, 25, (500, 457), TEAL, True)
                self.button((365, 492, 270, 61), "ДАЛЬШЕ", self.next_card, size=32)
            else:
                if word["id"] in NOTES:
                    rule, examples = NOTES[word["id"]]
                    contextual_sentence(self.canvas, *examples[0][:3], (500, 344), size=30, focus=word["en"])
                    text(self.canvas, examples[0][3], 23, (500, 371), TEAL, max_width=740)
                    for i, line in enumerate(textwrap.wrap(rule, width=78)[:2]):
                        text(self.canvas, line, 22, (500, 394 + i * 22), INK, max_width=790)
                if self.just_mastered:
                    text(self.canvas, f"Слов для питомца: {pet_learned_count(self.game)} / 150", 24 if word["id"] in NOTES else 27, (500, 443 if word["id"] in NOTES else 380), TEAL, True)
                self.button((365, 460, 270, 67), "ДАЛЬШЕ", self.next_card, size=34)
        self.button((78, 513, 121, 40), "В САД", self.leave_cards, fill=(124, 111, 89), size=22)
        if pygame.time.get_ticks() / 1000 < self.audio_notice_until:
            text(self.canvas, self.audio_notice, 21, (500, 585), INK)

    def leave_cards(self):
        saved = self.persist()
        self.screen = "home"
        if saved:
            self.notify("Урок на паузе. Можно продолжить с этой же карточки.")

    def draw_feed(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(115, 100, 770, 430))
        text(self.canvas, "Чем угостим питомца?", 42, (500, 151), INK, True)
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
        self.draw_background(play=True)
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
        panel(self.canvas, pygame.Rect(80, 90, 840, 455))
        title, lines = HELP_PAGES[self.help_page]
        text(self.canvas, title, 37, (500, 128), TEAL, True, max_width=780)
        text(self.canvas, f"КАК ИГРАТЬ · {self.help_page + 1} / {len(HELP_PAGES)}", 24, (500, 171), INK)
        for i, line in enumerate(lines):
            text(self.canvas, line, 26, (500, 215 + i * 37), INK, max_width=755)
        self.button((110, 482, 170, 49), "< НАЗАД", lambda: setattr(self, "help_page", self.help_page - 1), enabled=self.help_page > 0, size=25)
        self.button((340, 482, 320, 49), "ПОНЯТНО", self.close_help, fill=(124, 111, 89), size=29)
        self.button((720, 482, 170, 49), "ДАЛЬШЕ >", lambda: setattr(self, "help_page", self.help_page + 1), enabled=self.help_page + 1 < len(HELP_PAGES), size=25)

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
        text(self.canvas, "Игрок: " + self.player_name, 34, (410, 120), TEAL, True, max_width=550)
        self.button((710, 96, 175, 44), "СМЕНИТЬ", self.open_login, size=25)
        text(self.canvas, "Питомец: " + self.game["pet_name"], 34, (500, 174), INK, True, max_width=730)
        self.button((140, 210, 340, 48), "ИМЯ ИГРОКА", self.edit_player_name, size=27)
        self.button((520, 210, 340, 48), "ИМЯ ПИТОМЦА", self.edit_name, size=27)
        self.button((140, 287, 340, 55), "ВЫГРУЗИТЬ ПРОФИЛЬ", lambda: self.transfer_profile(True), size=25)
        self.button((520, 287, 340, 55), "ЗАГРУЗИТЬ ПРОФИЛЬ", lambda: self.transfer_profile(False), size=25)
        text(self.canvas, "Все слова, питомцы и проверки сохраняются только этому игроку.", 24, (500, 375), INK)
        text(self.canvas, "Перед удалением игры выгрузите профиль в отдельный файл.", 24, (500, 411), INK)
        text(self.canvas, "После переустановки загрузите этот файл здесь.", 24, (500, 442), INK)
        self.button((390, 487, 220, 49), "В САД", lambda: setattr(self, "screen", "home"), size=27)
        # Keep long platform errors inside the screen.
        text(self.canvas, self.profile_notice[:95], 21, (500, 580), INK)

    def draw_login(self):
        self.draw_background("sniffer")
        self.draw_header()
        panel(self.canvas, pygame.Rect(80, 88, 840, 472))
        text(self.canvas, "КТО ИГРАЕТ?", 42, (500, 132), TEAL, True)
        text(self.canvas, "Выбери своё имя. У каждого игрока свой мир и прогресс.", 25, (500, 175), INK)
        start = self.login_page * 3
        for i, profile in enumerate(self.profile_cache[start:start + 3]):
            rect = pygame.Rect(130, 205 + i * 83, 740, 68)
            panel(self.canvas, rect, (226, 236, 202) if start + i == 0 else PAPER)
            text(self.canvas, profile["name"], 31, (390, rect.y + 21), TEAL, True, max_width=440)
            text(self.canvas, f"Выучено: {mastered_count(profile['game'])} / 900 · {profile['game']['pet_name']}", 21,
                 (390, rect.y + 49), INK, max_width=480)
            self.button((690, rect.y + 12, 157, 44), "ИГРАТЬ", lambda identity=profile["id"]: self.enter_player(identity), size=26)
        if not self.profile_cache:
            text(self.canvas, "Создай игрока или загрузи сохранённый профиль.", 27, (500, 324), INK)
        if self.storage_error:
            self.button((340, 378, 320, 48), "ПРОЧИТАТЬ ЗАНОВО", self.refresh_players, size=25)
        self.button((35, 300, 65, 45), "<", lambda: setattr(self, "login_page", self.login_page - 1), enabled=self.login_page > 0)
        self.button((900, 300, 65, 45), ">", lambda: setattr(self, "login_page", self.login_page + 1), enabled=(self.login_page + 1) * 3 < len(self.profile_cache))
        self.button((140, 490, 340, 51), "НОВЫЙ ИГРОК", self.open_registration, enabled=not bool(self.storage_error), size=28)
        self.button((520, 490, 340, 51), "ЗАГРУЗИТЬ ПРОФИЛЬ", lambda: self.transfer_profile(False), enabled=not bool(self.storage_error), size=25)
        text(self.canvas, (self.storage_error or self.login_notice)[:105], 21, (500, 582), RED if self.storage_error else INK)

    def draw_registration(self):
        self.draw_background("sniffer")
        self.draw_header()
        panel(self.canvas, pygame.Rect(110, 100, 780, 440))
        text(self.canvas, "КАК ТЕБЯ ЗОВУТ?", 40, (500, 153), TEAL, True)
        text(self.canvas, "Это локальный профиль. Почта и пароль не нужны.", 25, (500, 195), INK)
        field = pygame.Rect(240, 225, 520, 60)
        panel(self.canvas, field, WHITE)
        text(self.canvas, self.registration_input + "|", 37, field.center, INK, max_width=485)
        self.buttons.append((field, pygame.key.start_text_input))
        text(self.canvas, "До 20 символов. Имя питомца можно выбрать отдельно.", 24, (500, 317), INK)
        text(self.canvas, "Старый прогресс будет перенесён этому игроку." if self.registration_game else "У тебя будут свои слова, питомцы и зоопарк.", 25, (500, 365), TEAL)
        text(self.canvas, self.login_notice[:95], 22, (500, 410), RED)
        self.button((210, 466, 280, 53), "СОЗДАТЬ ИГРОКА", self.submit_registration, enabled=bool(player_name(self.registration_input)), size=26)
        self.button((530, 466, 260, 53), "НАЗАД", self.open_login, fill=(124, 111, 89), size=27)

    def draw_save_conflict(self):
        self.draw_background("sniffer")
        self.draw_header()
        panel(self.canvas, pygame.Rect(70, 105, 860, 440))
        text(self.canvas, "ПРОФИЛЬ ИЗМЕНЁН В ДРУГОМ ОКНЕ", 35, (500, 163), TEAL, True, max_width=800)
        text(self.canvas, "Чтобы не откатить свежий прогресс, запись остановлена.", 27, (500, 235), INK)
        text(self.canvas, "Можешь выгрузить копию того, что сделано в этом окне.", 26, (500, 285), INK)
        text(self.canvas, "Затем загрузи свежую версию профиля из хранилища.", 26, (500, 330), INK)
        text(self.canvas, "Неперенесённые изменения этого окна будут заменены.", 24, (500, 365), RED)
        self.button((125, 420, 350, 60), "ВЫГРУЗИТЬ МОЮ КОПИЮ", lambda: self.transfer_profile(True), size=24)
        self.button((525, 420, 350, 60), "ЗАГРУЗИТЬ СВЕЖЕЕ", lambda: self.enter_player(self.player_id), size=26)
        text(self.canvas, self.profile_notice[:100], 21, (500, 514), INK, max_width=800)

    def draw_growth(self):
        notice = self.game["growth_notice"]
        if notice is None:
            self.screen = "home"
            self.restore_lesson()
            self.draw()
            return
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(55, 82, 890, 488))
        titles = {1: "МАЛЫШ ВЫЛУПИЛСЯ!", 2: "ПИТОМЕЦ ПОДРОС!", 3: "ПИТОМЕЦ СТАЛ ВЗРОСЛЫМ!", 4: "НОВОЕ ПРЕВРАЩЕНИЕ!"}
        text(self.canvas, titles[notice["after"]], 38, (500, 130), TEAL, True, max_width=820)
        text(self.canvas, self.game["pet_name"], 32, (500, 177), INK, True)
        species = current_species(self.game)
        before = self.sprites.scaled_species(species, "hatching" if notice["before"] == 0 else "growth",
                                             3 if notice["before"] == 0 else notice["before"], 190, 155)
        after = self.sprites.scaled_species(species, "growth", notice["after"], 240, 175)
        self.canvas.blit(before, before.get_rect(midbottom=(285, 370)))
        self.canvas.blit(after, after.get_rect(midbottom=(710, 370)))
        pygame.draw.line(self.canvas, TEAL, (470, 290), (530, 290), 5)
        pygame.draw.polygon(self.canvas, TEAL, ((530, 278), (548, 290), (530, 302)))
        new_label = "Выросший друг" if notice["after"] == 4 and species != "sniffer" else STAGE_NAMES[notice["after"]]
        text(self.canvas, STAGE_NAMES[notice["before"]], 26, (285, 405), INK)
        text(self.canvas, new_label, 26, (710, 405), TEAL, True)
        text(self.canvas, f"Ты выучил для питомца {pet_learned_count(self.game)} слов. Так держать!", 27, (500, 450), INK, True)
        now = pygame.time.get_ticks() / 1000
        for i in range(10):
            x = 130 + i * 80 + int(math.sin(now * 2 + i) * 8)
            y = 220 + (i % 3) * 58 + int(math.cos(now * 2.5 + i) * 9)
            pygame.draw.rect(self.canvas, GOLD, (x - 5, y - 1, 11, 3))
            pygame.draw.rect(self.canvas, GOLD, (x - 1, y - 5, 3, 11))
        self.button((330, 495, 340, 54), "УРА! ПРОДОЛЖИТЬ", self.acknowledge_growth, size=29)

    def draw_review(self, final=False):
        review = self.game["zoo"]["exam"] if final else self.game["active_review"]
        if review is None:
            self.screen = "home"
            self.draw_home()
            return
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(55, 78, 890, 492))
        title = "ИТОГОВЫЙ ТЕСТ · " + SPECIES_NAMES[current_species(self.game)] if final else f"ПРОВЕРКА: {review['milestone']} СЛОВ"
        text(self.canvas, title, 34, (500, 112), TEAL, True)
        if review["phase"] == "summary":
            text(self.canvas, f"Верно: {review_score(review)} / {len(review['queue'])}", 45, (500, 194), TEAL, True)
            mistakes = [word_id for word_id, chosen in zip(review["queue"], review["answers"]) if word_id != chosen]
            passed = final_passed(self.game) if final else True
            caption = ("Тест пройден!" if passed else "Нужно минимум 7 из 10. Попробуем ещё!") if final else ("Эти слова повторим в следующих проверках:" if mistakes else "Отлично! Все ответы верны!")
            text(self.canvas, caption, 27, (500, 248), TEAL if passed else RED, True)
            for i, word_id in enumerate(mistakes):
                word = WORD_BY_ID[word_id]
                text(self.canvas, f"{word['en']} — {word['ru']}", 24,
                     (290 + (i % 2) * 420, 286 + (i // 2) * 31), TEAL, max_width=395)
            text(self.canvas, "Результат сохранён. Выученные слова и рост не пропадают.", 24, (500, 457), INK)
            if final:
                self.button((240, 493, 250, 57), "ЗАВЕРШИТЬ" if passed else "ЕЩЁ РАЗ", self.settle_current_pet if passed else lambda: self.open_final_test(True), size=28)
                self.button((520, 493, 250, 57), "В ЗООПАРК" if passed else "ПОВТОРИТЬ СЛОВА",
                            self.pause_final_test if passed else lambda: self.open_dictionary(current_species(self.game)), size=25)
            else:
                self.button((340, 493, 320, 57), "ПРОДОЛЖИТЬ", self.close_review, size=31)
            return
        index = len(review["answers"]) - (1 if review["phase"] == "feedback" else 0)
        word = WORD_BY_ID[review["queue"][index]]
        contextual = FORM_QUESTIONS.get(word["id"])
        text(self.canvas, f"Вопрос {index + 1} / {len(review['queue'])}", 25, (500, 153), INK)
        if review["phase"] == "quiz":
            text(self.canvas, "Вставь пропущенное слово" if contextual else "Выбери перевод" if index % 2 == 0 else "Выбери английское слово", 33, (500, 205), INK, True)
            if contextual:
                subject, ending, russian = contextual
                contextual_sentence(self.canvas, subject, "___", ending, (500, 253), size=38)
                text(self.canvas, russian, 23, (500, 286), TEAL)
            else:
                text(self.canvas, word["en"] if index % 2 == 0 else word["ru"], 46, (500, 259), TEAL, True, max_width=740)
            self.button((785, 175, 110, 45), "ЗВУК", lambda: self.play_audio(word["en"]), fill=(88, 129, 155), size=22)
            for i, word_id in enumerate(self.final_options if final else self.review_options):
                option = WORD_BY_ID[word_id]
                self.button((194, 307 + i * 65, 612, 54), option["en"] if contextual else option["ru"] if index % 2 == 0 else option["en"],
                            lambda chosen=word_id: self.submit_final_test(chosen) if final else self.submit_review(chosen), size=32)
        else:
            correct = review["answers"][index] == word["id"]
            text(self.canvas, "ПРАВИЛЬНО!" if correct else "ДАВАЙ ЗАПОМНИМ", 39, (500, 221), TEAL if correct else RED, True)
            if contextual:
                contextual_sentence(self.canvas, contextual[0], word["en"], contextual[1], (500, 288), size=39)
            else:
                text(self.canvas, word["en"], 48, (500, 288), INK, True, max_width=780)
            text(self.canvas, word["hint"], 42, (500, 341), RED, max_width=780)
            text(self.canvas, contextual[2] if contextual else word["ru"], 42, (500, 393), TEAL, True, max_width=780)
            if contextual:
                for i, line in enumerate(textwrap.wrap(NOTES[word["id"]][0], width=88)[:2]):
                    text(self.canvas, line, 21, (500, 427 + i * 22), INK, max_width=790)
            self.button((345, 470, 310, 60), "ИТОГИ" if len(review["answers"]) == len(review["queue"]) else "ДАЛЬШЕ", self.next_final_test if final else self.next_review, size=31)
        self.button((78, 517, 140, 36), "ПОЗЖЕ", self.pause_final_test if final else self.pause_review, fill=(124, 111, 89), size=23)
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
        pool = words_for_species(current_species(self.game))
        if self.stats_tab == "overview":
            text(self.canvas, f"Выучено: {stats['learned']} / {len(ALL_WORDS)}", 33, (290, 222), TEAL, True)
            text(self.canvas, f"К повторению: {stats['needs_review']}", 31, (720, 222), INK, True)
            accuracy = f"{stats['accuracy']}%" if stats["accuracy"] is not None else "пока нет ответов"
            text(self.canvas, f"Точность: {accuracy}", 28, (500, 265), INK, True)
            text(self.canvas, f"Открыто: {stats['seen']} · Учим: {stats['learning']} · Верно: {stats['correct']} / {stats['attempts']}", 24, (500, 301), INK)
            for i, (name, _) in enumerate(CHAPTERS_BY_SPECIES[current_species(self.game)]):
                words = [word for word in pool if word["chapter"] == i]
                learned = sum(mastered(self.game, word["id"]) for word in words)
                x, y = 280 + (i // 5) * 450, 347 + (i % 5) * 32
                text(self.canvas, f"{name}: {learned} / 15", 25, (x, y), TEAL if learned == 15 else INK, max_width=420)
            text(self.canvas, "Подсчёт ответов ведётся с обновления; прежний прогресс слов сохранён.", 21, (500, 497), INK)
        elif self.stats_tab == "words":
            text(self.canvas, "Слово", 24, (175, 208), TEAL, True)
            text(self.canvas, "Перевод", 24, (410, 208), TEAL, True)
            text(self.canvas, "Статус", 24, (670, 208), TEAL, True)
            text(self.canvas, "Верно / всего", 23, (855, 208), TEAL, True)
            for i, word in enumerate(pool[self.stats_page * 8:(self.stats_page + 1) * 8]):
                y = 244 + i * 32
                counts = self.game["word_stats"].get(word["id"], {})
                attempts = counts.get("lesson_attempts", 0) + counts.get("review_attempts", 0)
                correct = counts.get("lesson_correct", 0) + counts.get("review_correct", 0)
                status = word_status(self.game, word["id"])
                text(self.canvas, word["en"], 26, (175, y), INK, True, max_width=220)
                text(self.canvas, word["ru"], 24, (410, y), INK, max_width=235)
                text(self.canvas, status, 23, (670, y), RED if status == "Повторить" else TEAL if status == "Выучено" else INK)
                text(self.canvas, f"{correct} / {attempts}" if attempts else "—", 24, (855, y), INK)
            last_page = (len(pool) - 1) // 8
            self.button((600, 517, 70, 37), "<", lambda: setattr(self, "stats_page", self.stats_page - 1), enabled=self.stats_page > 0)
            text(self.canvas, f"{self.stats_page + 1} / {last_page + 1}", 24, (750, 536), INK)
            self.button((830, 517, 70, 37), ">", lambda: setattr(self, "stats_page", self.stats_page + 1), enabled=self.stats_page < last_page)
        else:
            owner, species_name = SPECIES[self.stats_review_index]
            cycle = self.game["zoo"]["cycle"] if owner == current_species(self.game) else max((review_cycle(item) for item in self.game["reviews"] if review_species(item) == owner), default=0)
            text(self.canvas, "Проверки питомца: " + species_name, 29, (500, 221), INK, True)
            for i, milestone in enumerate((30, 60, 90, 120, 150)):
                result = next((item for item in self.game["reviews"] if item["milestone"] == milestone and review_species(item) == owner and review_cycle(item) == cycle), None)
                if result:
                    label = f"Верно: {result['score']} / {result['total']}"
                elif owner == current_species(self.game) and self.game["active_review"] and self.game["active_review"]["milestone"] == milestone:
                    label = "В процессе"
                elif owner != current_species(self.game):
                    label = "Не пройдена"
                else:
                    label = "Можно пройти" if pet_learned_count(self.game) >= milestone else "Ещё не открыта"
                text(self.canvas, f"{milestone} слов", 29, (290, 275 + i * 47), INK, True)
                text(self.canvas, label, 28, (690, 275 + i * 47), TEAL if result else INK)
            last_index = [item[0] for item in SPECIES].index(current_species(self.game))
            last_index = max(last_index, len(self.game["zoo"]["residents"]) - 1)
            exam_result = next((item for item in reversed(self.game["zoo"]["exam_history"]) if item["species"] == owner and item["cycle"] == cycle), None)
            if exam_result:
                text(self.canvas, f"Итоговый тест: {exam_result['score']} / 10 · нужно 7", 22, (500, 495), TEAL if exam_result["score"] >= 7 else RED)
            self.button((600, 517, 70, 37), "<", lambda: setattr(self, "stats_review_index", self.stats_review_index - 1), enabled=self.stats_review_index > 0)
            text(self.canvas, f"{self.stats_review_index + 1} / {last_index + 1}", 24, (750, 536), INK)
            self.button((830, 517, 70, 37), ">", lambda: setattr(self, "stats_review_index", self.stats_review_index + 1), enabled=self.stats_review_index < last_index)
        self.button((65, 517, 180, 37), "В САД", lambda: setattr(self, "screen", "home"), size=24)

    def draw_dictionary(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(35, 82, 930, 488))
        words = learned_vocabulary(self.game, self.dictionary_species, self.dictionary_query, self.dictionary_errors)
        last_page = max(0, (len(words) - 1) // 5)
        self.dictionary_page = max(0, min(self.dictionary_page, last_page))
        text(self.canvas, f"МОЙ СЛОВАРИК · {len(words)}", 35, (500, 110), TEAL, True)
        self.button((65, 144, 270, 38), "ВСЕ МОИ СЛОВА", lambda: self.dictionary_filter(None),
                    fill=TEAL if self.dictionary_species is None else (100, 111, 125), size=24)
        species = current_species(self.game)
        self.button((355, 144, 285, 38), "НАБОР: " + SPECIES_NAMES[species].upper(), lambda: self.dictionary_filter(species),
                    fill=TEAL if self.dictionary_species == species else (100, 111, 125), size=23)
        self.button((660, 144, 275, 38), "С ОШИБКАМИ", self.toggle_dictionary_errors,
                    fill=RED if self.dictionary_errors else (100, 111, 125), size=24)
        field = pygame.Rect(65, 192, 790, 35)
        panel(self.canvas, field, WHITE, border=2)
        search = self.dictionary_query + ("|" if self.dictionary_typing else "")
        text(self.canvas, search or "Поиск слова, перевода или произношения", 24, field.center,
             INK if search else (107, 122, 111), max_width=755)
        self.buttons.append((field, self.search_dictionary))
        self.button((870, 192, 65, 35), "X", self.clear_dictionary_search, fill=(124, 111, 89), size=23)
        for label, x in (("Слово", 190), ("Произношение", 445), ("Перевод", 711)):
            text(self.canvas, label, 21, (x, 246), TEAL, True)
        for i, word in enumerate(words[self.dictionary_page * 5:(self.dictionary_page + 1) * 5]):
            y = 283 + i * 46
            if i % 2 == 0:
                pygame.draw.rect(self.canvas, (240, 233, 208), (65, y - 21, 870, 43))
            color = RED if word["id"] in self.game["repeat_words"] else INK
            text(self.canvas, word["en"], 26, (190, y), color, True, max_width=235)
            text(self.canvas, word["hint"], 25, (445, y), RED, max_width=225)
            text(self.canvas, word["ru"] if self.dictionary_reveal else "Вспомни перевод", 25, (711, y),
                 TEAL if self.dictionary_reveal else (113, 126, 112), self.dictionary_reveal, max_width=255)
            self.button((877, y - 20, 48, 40), "", lambda word_id=word["id"]: self.play_audio(word_id), fill=(88, 129, 155), size=20)
            word_hint_icon(self.canvas, "sound", 888, y - 12, WHITE)
        if not words:
            text(self.canvas, "Выученные слова появятся здесь после двух верных раундов.", 26, (500, 349), INK, max_width=825)
            text(self.canvas, "Если включены фильтры, попробуй изменить поиск.", 24, (500, 397), INK)
        self.button((65, 520, 145, 38), "НАЗАД", self.close_dictionary, size=25)
        self.button((245, 520, 285, 38), "СКРЫТЬ ПЕРЕВОД" if self.dictionary_reveal else "ПОКАЗАТЬ ПЕРЕВОД",
                    lambda: setattr(self, "dictionary_reveal", not self.dictionary_reveal), size=23)
        self.button((590, 520, 60, 38), "<", lambda: setattr(self, "dictionary_page", self.dictionary_page - 1), enabled=self.dictionary_page > 0)
        text(self.canvas, f"{self.dictionary_page + 1} / {last_page + 1}", 24, (740, 540), INK)
        self.button((830, 520, 60, 38), ">", lambda: setattr(self, "dictionary_page", self.dictionary_page + 1), enabled=self.dictionary_page < last_page)
        if pygame.time.get_ticks() / 1000 < self.audio_notice_until:
            text(self.canvas, self.audio_notice, 21, (500, 585), INK)

    def draw_zoo(self):
        self.draw_background("sniffer")
        self.draw_header()
        residents = self.game["zoo"]["residents"]
        text(self.canvas, f"МОЙ ЗООПАРК · {len(residents)} / {len(SPECIES)}", 37, (500, 105), TEAL, True)
        active = current_species(self.game)
        for i, (species, name) in enumerate(SPECIES):
            rect = pygame.Rect(35 + (i % 3) * 315, 140 + (i // 3) * 177, 300, 163)
            panel(self.canvas, rect, PAPER if i <= len(residents) else (214, 218, 202))
            text(self.canvas, name, 27, (rect.centerx, rect.y + 22), INK, True)
            available = i < len(residents) or species == active
            collected = i < len(residents)
            # Zoo slots stay eggs until the fully raised companion moves in.
            sprite = self.sprites.scaled_species(species, "growth" if collected else "hatching",
                                                 4 if collected else 0, 155, 85)
            self.canvas.blit(sprite, sprite.get_rect(midbottom=(rect.centerx, rect.y + 126)))
            if collected:
                label = residents[i]["name"]
                if residents[i].get("grown", 1) > 1:
                    label += f" · выращено: {residents[i]['grown']}"
                self.buttons.append((rect, lambda index=i: self.inspect_resident(index)))
                egg_rect = pygame.Rect(rect.right - 54, rect.y + 67, 42, 54)
                if self.game["zoo"]["replay"] and species == active:
                    # Keep the grown friend visible alongside the new egg/baby.
                    young_stage = growth_stage(self.game)
                    young = self.sprites.scaled_species(species, "growth" if young_stage else "hatching", young_stage, 55, 66)
                    text(self.canvas, f"Снова: {pet_learned_count(self.game)}/150", 18, (rect.right - 65, rect.y + 49), TEAL)
                else:
                    young = self.sprites.scaled_species(species, "hatching", 0, 35, 49)
                    pygame.draw.rect(self.canvas, TEAL_LIGHT if can_replay(self.game, i) else PAPER_DARK, egg_rect)
                self.canvas.blit(young, young.get_rect(midbottom=(egg_rect.centerx, egg_rect.bottom)))
                if can_replay(self.game, i):
                    self.buttons.append((egg_rect.inflate(8, 8), lambda index=i: self.request_replay(index)))
            elif species == active:
                label = f"На лужайке: {pet_learned_count(self.game)} / 150 слов"
            elif self.game["zoo"]["replay"] and species == self.game["zoo"]["suspended"]["zoo"]["active"]:
                label = "Твой питомец ждёт возвращения"
            else:
                # A small corner lock distinguishes waiting eggs without hiding them.
                pygame.draw.rect(self.canvas, (112, 127, 117), (rect.right - 32, rect.y + 63, 19, 17))
                pygame.draw.rect(self.canvas, (112, 127, 117), (rect.right - 28, rect.y + 53, 11, 13), 3)
                pygame.draw.rect(self.canvas, PAPER, (rect.right - 24, rect.y + 69, 3, 5))
                label = "Сначала вырасти: " + SPECIES[i - 1][1]
            text(self.canvas, label, 22, (rect.centerx, rect.y + 145), TEAL if available else INK, max_width=278)
        if self.game["zoo"]["replay"]:
            caption = f"Новое яйцо · {SPECIES_NAMES[active]}: {pet_learned_count(self.game)} / 150. Старший друг остаётся рядом."
        elif len(residents) == len(SPECIES):
            caption = "Все шесть друзей собраны! Можно навещать каждого."
        elif pet_learned_count(self.game) >= 150 and not ready_for_zoo(self.game):
            caption = "Заверши текущий урок и проверку, затем посели питомца."
        else:
            caption = f"Чтобы открыть следующего друга, вырасти текущего: {pet_learned_count(self.game)} / 150 слов."
        text(self.canvas, caption, 24, (500, 505), INK, True)
        self.button((35, 537, 180, 46), "В САД", lambda: setattr(self, "screen", "home"), size=26)
        self.button((227, 537, 90, 46), "СЛОВА", lambda: self.open_dictionary(current_species(self.game)), size=21)
        if len(residents) < len(SPECIES) or self.game["zoo"]["replay"]:
            label = "ПРОЙТИ ИТОГОВЫЙ ТЕСТ · НУЖНО 70%"
            if final_passed(self.game):
                label = "ЗАВЕРШИТЬ ПОВТОРНОЕ ВЫРАЩИВАНИЕ" if self.game["zoo"]["replay"] else "ПОСЕЛИТЬ ПИТОМЦА И ОТКРЫТЬ СЛЕДУЮЩЕГО"
            self.button((330, 537, 635, 46), label, self.settle_current_pet, enabled=growth_complete(self.game), size=23)

    def draw_replay_confirm(self):
        self.draw_background("sniffer")
        self.draw_header()
        panel(self.canvas, pygame.Rect(100, 95, 800, 445))
        species = self.game["zoo"]["residents"][self.zoo_selection]["species"]
        text(self.canvas, "Вырастить ещё раз: " + SPECIES_NAMES[species] + "?", 34, (500, 145), TEAL, True)
        older = self.sprites.scaled_species(species, "growth", 4, 220, 155)
        egg = self.sprites.scaled_species(species, "hatching", 0, 100, 130)
        self.canvas.blit(older, older.get_rect(midbottom=(350, 337)))
        self.canvas.blit(egg, egg.get_rect(midbottom=(650, 337)))
        text(self.canvas, "Выращенный друг останется в зоопарке.", 27, (500, 370), INK)
        text(self.canvas, "Текущий питомец подождёт — его прогресс сохранится.", 25, (500, 408), INK)
        self.button((210, 465, 270, 53), "НОВОЕ ЯЙЦО", self.start_replay, size=29)
        self.button((520, 465, 270, 53), "ОТМЕНА", self.open_zoo, size=29)

    def draw_resident(self):
        resident = self.game["zoo"]["residents"][self.zoo_selection]
        self.draw_background(resident["species"], stage=4)
        self.draw_header()
        text(self.canvas, resident["name"], 42, (500, 120), TEAL, True, backdrop=CREAM)
        text(self.canvas, SPECIES_NAMES[resident["species"]] + " · Живёт в твоём зоопарке", 28, (500, 164), INK, backdrop=CREAM)
        text(self.canvas, f"Выращено раз: {resident.get('grown', 1)}", 23, (830, 202), TEAL, True, backdrop=CREAM)
        sprite = self.sprites.scaled_species(resident["species"], "growth", 4, 400, 265)
        now = pygame.time.get_ticks() / 1000
        bob = int(math.sin(now * 3) * 3)
        pygame.draw.ellipse(self.canvas, SHADOW_COLORS[resident["species"]], (350, 441, 300, 24))
        self.canvas.blit(sprite, sprite.get_rect(midbottom=(500, 455 + bob)))
        text(self.canvas, "Ты вырастил этого друга, занимаясь английским!", 28, (500, 493), INK, True)
        self.button((335, 535, 330, 48), "В ЗООПАРК", self.open_zoo, size=29)

    def cancel_name(self):
        pygame.key.stop_text_input()
        self.screen = "profile"

    def draw_name(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(110, 110, 780, 390))
        text(self.canvas, "Как зовут игрока?" if self.name_kind == "player" else "Как зовут твоего питомца?", 40, (500, 171), TEAL, True)
        panel(self.canvas, pygame.Rect(220, 240, 560, 60), WHITE)
        text(self.canvas, self.name_input + "|", 36, (500, 270), INK)
        text(self.canvas, self.name_error or "До 20 символов", 24, (500, 330), RED if self.name_error else INK, max_width=710)
        self.button((220, 390, 260, 60), "СОХРАНИТЬ", self.accept_name,
                    enabled=bool(clean_pet_name(self.name_input)), size=28)
        self.button((520, 390, 260, 60), "ОТМЕНА", self.cancel_name, fill=(124, 111, 89), size=28)

    def cancel_import(self):
        self.imported_game = self.imported_player = None
        self.screen = "profile" if self.player_id else "login"

    def draw_import(self):
        self.draw_background()
        self.draw_header()
        panel(self.canvas, pygame.Rect(110, 110, 780, 390))
        text(self.canvas, "Загрузить этот профиль?", 40, (500, 169), TEAL, True)
        name = self.imported_player["name"] if self.imported_player else "Копия без имени игрока"
        text(self.canvas, name, 35, (500, 227), TEAL, True, max_width=720)
        text(self.canvas, f"Выучено: {mastered_count(self.imported_game)} / 900 · {self.imported_game['pet_name']}", 28, (500, 278), INK, max_width=720)
        try:
            mode, _ = self.players.import_target({"player": self.imported_player, "game": self.imported_game}, self.player_id)
            caption = "Заменится только профиль игрока «" + self.player_name + "»." if mode == "replace" else "Будет создан отдельный игрок. Другие профили не изменятся."
            allowed = True
        except Exception as error:
            caption, allowed, mode = str(error), False, ""
        for i, line in enumerate(textwrap.wrap(caption, width=66)[:2]):
            text(self.canvas, line, 23, (500, 329 + i * 25), RED if mode == "replace" or not allowed else INK)
        self.button((220, 390, 260, 60), "УКАЗАТЬ ИМЯ" if mode == "register" else "ЗАГРУЗИТЬ", self.accept_import, enabled=allowed, size=28)
        self.button((520, 390, 260, 60), "ОТМЕНА", self.cancel_import, fill=(124, 111, 89), size=28)

    def draw(self):
        self.buttons = []
        if self.player_id is None and self.screen not in ("login", "register", "import", "help"):
            self.screen = "login"
        if self.save_conflict:
            self.draw_save_conflict()
        elif self.screen == "login":
            self.draw_login()
        elif self.screen == "register":
            self.draw_registration()
        elif self.screen == "growth":
            self.draw_growth()
        elif self.screen == "home":
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
        elif self.screen == "final_test":
            self.draw_review(final=True)
        elif self.screen == "statistics":
            self.draw_statistics()
        elif self.screen == "dictionary":
            self.draw_dictionary()
        elif self.screen == "zoo":
            self.draw_zoo()
        elif self.screen == "resident":
            self.draw_resident()
        elif self.screen == "replay_confirm":
            self.draw_replay_confirm()
        else:
            self.draw_help()
        display_size = self.display.get_size()
        scale = min(display_size[0] / WIDTH, display_size[1] / HEIGHT)
        view_size = (max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale)))
        self.viewport = pygame.Rect((display_size[0] - view_size[0]) // 2, (display_size[1] - view_size[1]) // 2, *view_size)
        self.display.fill(INK)
        self.display.blit(pygame.transform.scale(self.canvas, view_size), self.viewport)
        pygame.display.flip()
        self.button_scope = (self.screen, self.player_id, self.save_conflict)
        self.input_ready = True

    def click(self, screen_pos):
        if not self.input_ready or self.button_scope != (self.screen, self.player_id, self.save_conflict):
            return
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
        if self.screen == "home" and not self.save_conflict:
            if self.poop_rect and self.poop_rect.collidepoint(point):
                self.input_ready = False
                self.do_clean()
                return
            if self.pet_rect.collidepoint(point) and hatch_complete(self.game):
                self.input_ready = False
                self.pet_behavior.pet()
                self.hearts.emit(self.pet_rect.centerx, self.pet_rect.top + 35, pygame.time.get_ticks() / 1000)
                self.notify("Питомцу нравится твоё внимание!")
                return
        for rect, action in reversed(self.buttons):
            if rect.collidepoint(point):
                self.input_ready = False
                action()
                return

    def handle_event(self, event):
        if self.save_conflict and event.type == pygame.KEYDOWN:
            return
        if event.type == pygame.QUIT:
            self.persist()
            self.running = False
        elif event.type in tuple(getattr(pygame, name, -1) for name in
                                 ("APP_WILLENTERBACKGROUND", "APP_DIDENTERBACKGROUND", "WINDOWFOCUSLOST")):
            self.persist()
        elif event.type in tuple(getattr(pygame, name, -1) for name in ("APP_DIDENTERFOREGROUND", "WINDOWFOCUSGAINED")):
            self.check_profile_freshness()
        elif event.type == pygame.TEXTINPUT and self.screen == "register":
            self.registration_input = "".join(c for c in (self.registration_input + event.text) if c.isprintable())[:20]
        elif event.type == pygame.KEYDOWN and self.screen == "register":
            if event.key == pygame.K_BACKSPACE:
                self.registration_input = self.registration_input[:-1]
            elif event.key == pygame.K_RETURN:
                self.submit_registration()
            elif event.key == pygame.K_ESCAPE:
                self.open_login()
        elif event.type == pygame.TEXTINPUT and self.screen == "dictionary" and self.dictionary_typing:
            self.dictionary_query = "".join(c for c in (self.dictionary_query + event.text) if c.isprintable())[:40]
            self.dictionary_page = 0
        elif event.type == pygame.KEYDOWN and self.screen == "dictionary":
            if self.dictionary_typing and event.key == pygame.K_BACKSPACE:
                self.dictionary_query = self.dictionary_query[:-1]
                self.dictionary_page = 0
            elif event.key in (pygame.K_RETURN, pygame.K_ESCAPE) and self.dictionary_typing:
                pygame.key.stop_text_input()
                self.dictionary_typing = False
            elif event.key == pygame.K_ESCAPE:
                self.close_dictionary()
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
            if self.screen == "login":
                self.running = False
            elif self.screen == "help":
                self.close_help()
            elif self.screen == "growth":
                self.acknowledge_growth()
            elif self.screen == "cards":
                self.leave_cards()
            elif self.screen == "review":
                self.pause_review()
            elif self.screen == "final_test":
                self.pause_final_test()
            elif self.screen == "play":
                self.leave_play()
            elif self.screen == "import":
                self.cancel_import()
            elif self.screen in ("resident", "replay_confirm"):
                self.open_zoo()
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
        try:
            app.profile_picker.close()
        finally:
            try:
                app.speech.shutdown()
            finally:
                pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
