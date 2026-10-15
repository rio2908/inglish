"""Offline pixel associations for common concrete words; never guess unknown pictures."""

import math

import pygame

from creature_sprites import block, creature


INK = (35, 49, 48)
SKIN = (239, 190, 143)
COLORS = {"red": (219, 74, 66), "blue": (77, 139, 210), "green": (76, 163, 92),
          "yellow": (247, 205, 69), "black": (53, 58, 62), "white": (242, 242, 224),
          "pink": (236, 151, 184), "brown": (145, 102, 66), "purple": (156, 111, 184),
          "gray": (157, 166, 165), "orange": (238, 153, 51)}
NUMBERS = dict(zip(("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                    "eleven", "twelve", "thirteen", "fourteen", "fifteen"), range(1, 16)))
ANIMALS = {"cat", "dog", "mouse", "rabbit", "bear", "cow", "horse", "sheep", "bird", "fish", "chicken", "frog", "butterfly"}
PEOPLE = {"mother", "father", "sister", "brother", "baby", "boy", "girl", "friend", "teacher", "child", "family", "grandma", "grandpa", "man", "woman"}
FOOD = {"apple", "banana", "orange", "pear", "carrot", "tomato", "potato", "bread", "cheese", "milk", "egg", "cake", "cookie", "soup", "juice",
        "peach", "plum", "lemon", "lime", "grape", "cherry", "strawberry", "watermelon", "melon", "cucumber", "pepper", "pumpkin", "coconut"}
OBJECTS = {"house", "home", "room", "door", "window", "bed", "chair", "table", "lamp", "box", "cup", "ball", "toy", "clock", "book", "key",
           "plate", "bowl", "fork", "spoon", "knife", "bottle", "notebook", "pencil", "pen", "crayon", "ruler", "paper", "bag", "backpack", "umbrella"}
NATURE = {"tree", "flower", "leaf", "grass", "seed", "plant", "sun", "rain", "cloud", "sky", "moon", "star", "stone", "river", "garden",
          "water", "sea", "ocean", "lake", "pond", "snow", "ice", "snowy", "sunny", "rainy", "cloudy", "rock", "wood", "branch", "bush", "soil", "sand", "beach"}
FACES = {"happy", "sad", "angry", "tired", "sleepy", "hungry", "thirsty", "scared", "excited", "bored", "calm", "funny", "worried"}
ACTIONS = {"eat", "drink", "sleep", "run", "jump", "walk", "sit", "stand", "play", "look", "listen", "open", "close", "give", "take",
           "clap", "wave hello", "smile", "laugh", "cry", "touch", "kick", "dance", "throw", "catch", "read", "write", "draw", "paint"}
BODY = {"head", "face", "eye", "ear", "nose", "mouth", "tooth", "tongue", "hair", "hand", "arm", "leg", "foot", "finger", "knee"}
CLOTHES = {"shirt", "t-shirt", "dress", "skirt", "trousers", "shorts", "jeans", "sweater", "jacket", "coat", "hat", "cap", "scarf", "glove", "sock", "shoe", "boot", "slipper", "sandal", "belt", "button", "pocket", "zip", "pyjamas"}


def letter(surface, value, size, center, color=INK):
    font = pygame.font.Font(None, size)
    font.set_bold(True)
    image = font.render(value, True, color)
    surface.blit(image, image.get_rect(center=center))


def face(surface, mood="happy", x=22, y=15, size=52):
    block(surface, (x, y, size, size), (250, 210, 104), False)
    for dx in (size // 4, size * 3 // 4 - 4):
        pygame.draw.rect(surface, INK, (x + dx, y + size // 3, 4, 6))
    mouth_y = y + size * 2 // 3
    if mood in ("sad", "cry", "worried", "scared"):
        pygame.draw.lines(surface, INK, False, ((x + 15, mouth_y + 4), (x + size // 2, mouth_y), (x + size - 15, mouth_y + 4)), 3)
    elif mood in ("tired", "sleepy", "bored"):
        pygame.draw.line(surface, INK, (x + 17, mouth_y), (x + size - 17, mouth_y), 3)
    else:
        pygame.draw.lines(surface, INK, False, ((x + 13, mouth_y - 3), (x + 19, mouth_y + 4), (x + size - 19, mouth_y + 4), (x + size - 13, mouth_y - 3)), 3)
    if mood == "angry":
        pygame.draw.line(surface, INK, (x + 9, y + 11), (x + 23, y + 17), 3)
        pygame.draw.line(surface, INK, (x + size - 9, y + 11), (x + size - 23, y + 17), 3)
    if mood in ("sad", "cry"):
        pygame.draw.rect(surface, COLORS["blue"], (x + 12, y + size // 3 + 9, 5, 13))


def person(surface, x=35, y=10, small=False, pose="stand", female=False, old=False):
    head = 18 if small else 23
    block(surface, (x, y, head, head), SKIN, False)
    pygame.draw.rect(surface, (205, 205, 193) if old else (106, 73, 48), (x, y, head, 5))
    if female:
        pygame.draw.rect(surface, (106, 73, 48), (x - 3, y + 2, 5, head + 7))
    for dx in (5, head - 7):
        pygame.draw.rect(surface, INK, (x + dx, y + 9, 2, 3))
    torso = (x + 2, y + head, head - 4, 20 if small else 26)
    block(surface, torso, COLORS["pink"] if female else COLORS["blue"])
    hip_y = torso[1] + torso[3]
    if pose in ("run", "walk", "jump", "dance", "kick"):
        pygame.draw.lines(surface, INK, False, ((x + 7, hip_y), (x - 4, hip_y + 10), (x - 10, hip_y + 14)), 6)
        pygame.draw.lines(surface, INK, False, ((x + head - 7, hip_y), (x + head + 8, hip_y + 7), (x + head + 10, hip_y + 18)), 6)
    elif pose == "sit":
        pygame.draw.lines(surface, INK, False, ((x + 5, hip_y), (x + head + 10, hip_y), (x + head + 10, hip_y + 15)), 6)
    else:
        pygame.draw.rect(surface, INK, (x + 4, hip_y, 6, 18))
        pygame.draw.rect(surface, INK, (x + head - 10, hip_y, 6, 18))
    arm_y = torso[1] + 5
    pygame.draw.line(surface, SKIN, (x + 2, arm_y), (x - 8, arm_y - 15 if pose in ("jump", "clap", "dance") else arm_y + 16), 6)
    pygame.draw.line(surface, SKIN, (x + head - 2, arm_y), (x + head + 10, arm_y - 15 if pose in ("jump", "clap", "wave hello") else arm_y + 13), 6)


def animal(surface, name):
    if name in ("fish", "bird", "chicken", "butterfly", "frog"):
        color = {"fish": COLORS["orange"], "bird": COLORS["blue"], "chicken": COLORS["white"], "butterfly": COLORS["purple"], "frog": COLORS["green"]}[name]
        if name == "butterfly":
            for x in (15, 52):
                block(surface, (x, 19, 28, 31), color)
                block(surface, (x + 4, 49, 22, 23), COLORS["pink"])
            pygame.draw.rect(surface, INK, (44, 25, 7, 53))
            pygame.draw.lines(surface, INK, False, ((37, 12), (47, 27), (57, 12)), 3)
            return
        block(surface, (24, 37, 48, 28), color)
        if name == "fish":
            pygame.draw.polygon(surface, INK, ((25, 49), (7, 31), (7, 70)))
            pygame.draw.polygon(surface, color, ((24, 49), (10, 37), (10, 64)))
            pygame.draw.polygon(surface, color, ((43, 38), (53, 22), (59, 38)))
        elif name == "frog":
            for x in (25, 58):
                block(surface, (x, 23, 17, 20), color, False)
                pygame.draw.rect(surface, COLORS["white"], (x + 4, 26, 9, 11))
                pygame.draw.rect(surface, INK, (x + 8, 29, 4, 6))
            for x in (13, 62):
                block(surface, (x, 61, 23, 13), color)
            return
        else:
            block(surface, (53, 21, 23, 26), color)
            pygame.draw.polygon(surface, COLORS["yellow"], ((76, 31), (90, 37), (76, 40)))
            pygame.draw.rect(surface, INK, (64, 28, 4, 5))
            pygame.draw.rect(surface, COLORS["yellow"], (35, 65, 5, 16))
            pygame.draw.rect(surface, COLORS["yellow"], (58, 65, 5, 16))
            if name == "chicken":
                pygame.draw.rect(surface, COLORS["red"], (58, 14, 14, 9))
        pygame.draw.rect(surface, INK, (61, 44, 5, 6))
        return
    color = {"cat": (207, 152, 80), "dog": (155, 111, 71), "mouse": (165, 170, 168), "rabbit": (230, 225, 215),
             "bear": (131, 94, 61), "cow": (235, 233, 219), "horse": (159, 107, 65), "sheep": (236, 235, 218)}[name]
    block(surface, (17, 43, 51, 27), color)
    for x in (25, 57):
        block(surface, (x, 66, 9, 17), color)
    block(surface, (59, 27, 27, 32), color)
    if name == "rabbit":
        for x in (60, 76):
            block(surface, (x, 3, 8, 27), color)
            pygame.draw.rect(surface, COLORS["pink"], (x + 3, 8, 2, 17))
    elif name == "cat":
        for x in (59, 76):
            pygame.draw.polygon(surface, color, ((x, 28), (x + 5, 12), (x + 11, 28)))
        pygame.draw.lines(surface, color, False, ((19, 56), (8, 47), (8, 29)), 8)
    elif name == "dog":
        block(surface, (56, 27, 9, 25), (114, 77, 47))
        block(surface, (81, 27, 9, 25), (114, 77, 47))
    else:
        for x in (59, 77):
            block(surface, (x, 17, 12 if name == "mouse" else 9, 14), color, False)
    if name == "cow":
        for x, y in ((27, 48), (48, 55), (67, 30)):
            pygame.draw.rect(surface, INK, (x, y, 10, 10))
        block(surface, (68, 49, 23, 12), (225, 172, 161), False)
    elif name == "horse":
        pygame.draw.rect(surface, INK, (56, 24, 7, 30))
        pygame.draw.rect(surface, INK, (14, 48, 6, 27))
    elif name == "sheep":
        for x in (17, 32, 48):
            block(surface, (x, 35, 20, 19), COLORS["white"])
    elif name == "mouse":
        pygame.draw.lines(surface, COLORS["pink"], False, ((18, 60), (7, 68), (3, 55)), 3)
    pygame.draw.rect(surface, INK, (69, 36, 4, 5))
    pygame.draw.rect(surface, INK, (81, 49, 8, 5))


def nature(surface, name):
    if name in ("tree", "plant", "leaf", "grass", "flower", "seed", "garden", "bush", "branch", "wood"):
        if name == "seed":
            for x, y in ((22, 47), (46, 31), (65, 53)):
                block(surface, (x, y, 12, 8), (169, 121, 63), False)
        elif name in ("leaf", "grass", "plant", "flower"):
            if name == "leaf":
                pygame.draw.polygon(surface, INK, ((18, 65), (24, 31), (75, 12), (82, 46), (54, 73), (25, 77)))
                pygame.draw.polygon(surface, COLORS["green"], ((23, 63), (29, 35), (72, 18), (76, 44), (51, 68), (28, 71)))
                pygame.draw.line(surface, (51, 116, 65), (19, 84), (69, 27), 4)
                return
            pygame.draw.rect(surface, COLORS["green"], (44, 27, 7, 57))
            for x, y in ((23, 44), (48, 57)):
                pygame.draw.polygon(surface, COLORS["green"], ((x, y), (x + 22, y + 10), (x + 16, y + 20), (x, y + 10)))
            if name == "flower":
                for dx, dy in ((-14, 0), (14, 0), (0, -14), (0, 14)):
                    block(surface, (39 + dx, 22 + dy, 17, 17), COLORS["pink"], False)
                block(surface, (40, 23, 15, 15), COLORS["yellow"], False)
            if name == "grass":
                for x in (16, 27, 64, 75):
                    pygame.draw.line(surface, COLORS["green"], (48, 84), (x, 38), 6)
        else:
            block(surface, (40, 42, 16, 42), COLORS["brown"])
            for x, y, w in ((13, 27, 69), (25, 12, 47), (33, 5, 31)):
                block(surface, (x, y, w, 29), COLORS["green"])
            if name == "garden":
                for x in (7, 22, 69, 84):
                    pygame.draw.rect(surface, COLORS["pink"], (x, 65, 8, 8))
            if name == "wood" or name == "branch":
                surface.fill((0, 0, 0, 0))
                block(surface, (15, 33, 66, 25), COLORS["brown"])
        return
    if name in ("sun", "sunny", "moon", "star", "sky"):
        if name in ("moon", "sky"):
            block(surface, (7, 7, 82, 80), (86, 143, 191))
        if name == "star":
            points = [(48 + math.cos(-math.pi / 2 + i * math.pi / 5) * (36 if i % 2 == 0 else 16),
                       48 + math.sin(-math.pi / 2 + i * math.pi / 5) * (36 if i % 2 == 0 else 16)) for i in range(10)]
            pygame.draw.polygon(surface, COLORS["yellow"], points)
        elif name == "moon":
            pygame.draw.circle(surface, (247, 238, 178), (48, 43), 30)
            pygame.draw.circle(surface, (86, 143, 191), (62, 31), 26)
        else:
            block(surface, (29, 24, 38, 38), COLORS["yellow"])
            for x, y, w, h in ((43, 7, 8, 11), (43, 69, 8, 11), (9, 39, 12, 8), (75, 39, 12, 8)):
                pygame.draw.rect(surface, COLORS["yellow"], (x, y, w, h))
        return
    if name in ("water", "sea", "ocean", "lake", "pond", "river", "beach"):
        for i in range(5):
            pygame.draw.rect(surface, (84, 172 + i * 8, 202), (8, 20 + i * 12, 80, 10))
        if name == "river":
            pygame.draw.polygon(surface, COLORS["green"], ((0, 0), (40, 0), (15, 96), (0, 96)))
            pygame.draw.polygon(surface, COLORS["green"], ((80, 0), (96, 0), (96, 96), (53, 96)))
    elif name in ("stone", "rock", "sand", "soil"):
        block(surface, (17, 36, 65, 39), COLORS["gray"] if name in ("stone", "rock") else (204, 177, 119))
        block(surface, (29, 25, 42, 15), (190, 195, 175))
    else:
        for x, y, w, h in ((10, 30, 76, 28), (26, 14, 45, 35)):
            block(surface, (x, y, w, h), COLORS["white"])
        if name in ("rain", "rainy", "snow", "snowy", "ice"):
            for x in (21, 45, 69):
                pygame.draw.line(surface, COLORS["blue"], (x, 67), (x - 4, 82), 4)
                if name in ("snow", "snowy", "ice"):
                    pygame.draw.line(surface, COLORS["blue"], (x - 7, 73), (x + 5, 77), 3)


def food(surface, name):
    if name == "banana":
        pygame.draw.polygon(surface, INK, ((13, 20), (26, 49), (54, 64), (81, 50), (68, 77), (39, 80), (16, 58), (8, 32)))
        pygame.draw.polygon(surface, COLORS["yellow"], ((14, 27), (29, 53), (53, 68), (75, 58), (66, 72), (40, 75), (21, 56), (13, 34)))
    elif name in ("milk", "juice"):
        block(surface, (25, 23, 45, 60), COLORS["white"] if name == "milk" else COLORS["orange"])
        block(surface, (31, 10, 33, 16), COLORS["blue"] if name == "milk" else COLORS["green"])
        letter(surface, "M" if name == "milk" else "J", 32, (48, 52))
    elif name == "egg":
        pygame.draw.ellipse(surface, INK, (24, 10, 47, 74))
        pygame.draw.ellipse(surface, COLORS["white"], (27, 13, 41, 68))
    elif name == "cheese":
        pygame.draw.polygon(surface, INK, ((15, 67), (75, 21), (82, 70), (19, 80)))
        pygame.draw.polygon(surface, COLORS["yellow"], ((19, 66), (73, 27), (78, 67), (22, 75)))
        for x, y in ((40, 61), (65, 46), (66, 66)):
            pygame.draw.circle(surface, COLORS["orange"], (x, y), 4)
    elif name == "soup":
        block(surface, (13, 33, 70, 40), COLORS["blue"])
        pygame.draw.ellipse(surface, COLORS["orange"], (17, 28, 62, 23))
        for x in (30, 53):
            pygame.draw.line(surface, COLORS["gray"], (x, 21), (x + 7, 8), 3)
    elif name == "bread":
        block(surface, (18, 23, 60, 56), (167, 105, 54))
        block(surface, (24, 29, 48, 44), (236, 199, 133))
    elif name == "cake":
        block(surface, (15, 45, 68, 33), (159, 97, 70))
        block(surface, (15, 34, 68, 18), COLORS["pink"])
        pygame.draw.rect(surface, COLORS["blue"], (45, 17, 6, 19))
        pygame.draw.rect(surface, COLORS["yellow"], (45, 9, 6, 8))
    elif name == "cookie":
        pygame.draw.circle(surface, COLORS["brown"], (48, 47), 34)
        for x, y in ((33, 31), (61, 28), (43, 57), (69, 53), (25, 51)):
            pygame.draw.rect(surface, INK, (x, y, 7, 7))
    elif name == "carrot":
        pygame.draw.polygon(surface, INK, ((22, 25), (69, 35), (34, 86)))
        pygame.draw.polygon(surface, COLORS["orange"], ((28, 30), (63, 37), (35, 76)))
        for x in (33, 45, 57):
            pygame.draw.line(surface, COLORS["green"], (43, 31), (x, 8), 6)
    else:
        color = {"apple": COLORS["red"], "tomato": COLORS["red"], "strawberry": COLORS["red"], "cherry": COLORS["red"],
                 "pear": (145, 186, 85), "potato": (182, 144, 90), "plum": COLORS["purple"], "grape": COLORS["purple"],
                 "lime": COLORS["green"], "cucumber": COLORS["green"], "watermelon": COLORS["green"], "coconut": COLORS["brown"],
                 "lemon": COLORS["yellow"], "peach": (239, 160, 109)}.get(name, COLORS["orange"])
        block(surface, (22, 30, 53, 48), color)
        pygame.draw.rect(surface, COLORS["brown"], (45, 17, 6, 17))
        pygame.draw.polygon(surface, COLORS["green"], ((50, 25), (67, 12), (75, 23), (59, 30)))
        if name in ("potato", "strawberry", "watermelon"):
            for x, y in ((30, 40), (59, 50), (40, 65)):
                pygame.draw.rect(surface, (111, 112, 66), (x, y, 3, 4))


def object_picture(surface, name):
    if name in ("house", "home", "room", "door", "window"):
        block(surface, (19, 32, 59, 52), (228, 192, 139))
        if name == "room":
            block(surface, (11, 13, 74, 69), (230, 216, 170), False)
            pygame.draw.rect(surface, (151, 112, 76), (14, 61, 68, 18))
            block(surface, (22, 23, 25, 27), COLORS["blue"])
            pygame.draw.rect(surface, COLORS["white"], (33, 25, 3, 23))
            block(surface, (58, 45, 19, 26), COLORS["brown"])
            return
        if name in ("house", "home"):
            pygame.draw.polygon(surface, INK, ((8, 35), (48, 7), (89, 35)))
            pygame.draw.polygon(surface, COLORS["red"], ((15, 32), (48, 13), (81, 32)))
        if name in ("door", "house", "home"):
            block(surface, (43, 44 if name != "door" else 20, 23, 40 if name != "door" else 64), COLORS["brown"])
            pygame.draw.rect(surface, COLORS["yellow"], (59, 62, 4, 4))
        else:
            block(surface, (26, 25, 45, 46), COLORS["blue"])
            pygame.draw.line(surface, COLORS["white"], (48, 28), (48, 68), 3)
            pygame.draw.line(surface, COLORS["white"], (29, 48), (68, 48), 3)
    elif name in ("table", "chair", "bed"):
        if name == "bed":
            block(surface, (12, 42, 74, 27), COLORS["red"])
            block(surface, (15, 38, 24, 15), COLORS["white"])
        else:
            block(surface, (15, 42, 67 if name == "table" else 45, 10), COLORS["brown"])
            if name == "chair":
                block(surface, (15, 10, 10, 40), COLORS["brown"])
                block(surface, (15, 13, 45, 25), COLORS["brown"])
        for x in (17, 74 if name != "chair" else 49):
            block(surface, (x, 52, 8, 29), COLORS["brown"])
    elif name in ("book", "notebook", "paper"):
        block(surface, (15, 15, 66, 67), COLORS["blue"])
        block(surface, (20, 19, 56, 57), COLORS["white"], False)
        pygame.draw.line(surface, INK, (48, 20), (48, 75), 2)
        for x in (26, 54):
            for y in (31, 42, 53, 64):
                pygame.draw.line(surface, COLORS["blue"], (x, y), (x + 14, y), 2)
    elif name in ("ball", "toy"):
        if name == "ball":
            pygame.draw.circle(surface, INK, (48, 47), 33)
            pygame.draw.circle(surface, COLORS["orange"], (48, 47), 30)
            pygame.draw.line(surface, INK, (20, 47), (76, 47), 3)
            pygame.draw.line(surface, INK, (48, 19), (48, 76), 3)
        else:
            for rect, color in (((15, 53, 30, 29), "red"), ((48, 53, 30, 29), "blue"), ((32, 22, 29, 29), "yellow")):
                block(surface, rect, COLORS[color])
    elif name == "key":
        pygame.draw.rect(surface, COLORS["yellow"], (16, 24, 28, 29), 7)
        pygame.draw.rect(surface, COLORS["yellow"], (37, 42, 43, 9))
        for x in (61, 74):
            pygame.draw.rect(surface, COLORS["yellow"], (x, 47, 7, 15))
    elif name == "clock":
        pygame.draw.circle(surface, INK, (48, 48), 36)
        pygame.draw.circle(surface, COLORS["white"], (48, 48), 31)
        pygame.draw.lines(surface, INK, False, ((48, 21), (48, 48), (67, 58)), 4)
    elif name in ("cup", "bowl", "plate", "bottle"):
        if name == "plate":
            pygame.draw.circle(surface, COLORS["blue"], (48, 48), 33)
            pygame.draw.circle(surface, COLORS["white"], (48, 48), 25)
        elif name == "bowl":
            pygame.draw.polygon(surface, COLORS["blue"], ((12, 36), (84, 36), (70, 76), (26, 76)))
            pygame.draw.ellipse(surface, COLORS["white"], (12, 26, 72, 24))
            pygame.draw.ellipse(surface, (205, 224, 219), (18, 31, 60, 14))
        else:
            block(surface, (24, 25, 45, 53), COLORS["white"])
            if name == "cup":
                pygame.draw.rect(surface, COLORS["blue"], (68, 33, 15, 29), 5)
            if name == "bottle":
                block(surface, (34, 10, 25, 20), COLORS["blue"])
    elif name == "lamp":
        pygame.draw.rect(surface, INK, (45, 35, 7, 44))
        pygame.draw.rect(surface, INK, (27, 77, 43, 6))
        pygame.draw.polygon(surface, COLORS["yellow"], ((31, 12), (65, 12), (79, 44), (17, 44)))
    elif name in ("pencil", "pen", "crayon", "ruler", "fork", "spoon", "knife"):
        block(surface, (40, 20, 15, 58), COLORS["yellow"] if name in ("pencil", "ruler", "crayon") else COLORS["gray"])
        if name in ("pencil", "pen", "crayon"):
            pygame.draw.polygon(surface, INK, ((40, 77), (55, 77), (47, 90)))
        elif name == "spoon":
            pygame.draw.ellipse(surface, COLORS["gray"], (32, 6, 30, 37))
        elif name == "fork":
            for x in (33, 44, 55):
                pygame.draw.rect(surface, COLORS["gray"], (x, 7, 6, 33))
        elif name == "knife":
            pygame.draw.polygon(surface, (205, 214, 211), ((34, 11), (58, 11), (58, 57), (44, 65), (37, 48)))
            block(surface, (44, 59, 13, 28), COLORS["brown"])
        elif name == "ruler":
            for i, y in enumerate(range(25, 75, 7)):
                pygame.draw.line(surface, INK, (42, y), (48 if i % 2 else 52, y), 1)
    elif name in ("bag", "backpack"):
        pygame.draw.rect(surface, INK, (31, 12, 35, 29), 5)
        block(surface, (21, 30, 55, 52), COLORS["blue"] if name == "backpack" else COLORS["brown"])
        if name == "backpack":
            block(surface, (29, 54, 39, 21), (97, 169, 205))
            pygame.draw.line(surface, INK, (31, 58), (65, 58), 2)
    elif name == "umbrella":
        pygame.draw.polygon(surface, INK, ((6, 43), (22, 18), (48, 10), (74, 18), (90, 43)))
        pygame.draw.polygon(surface, COLORS["red"], ((12, 39), (25, 22), (48, 15), (71, 22), (84, 39)))
        pygame.draw.rect(surface, COLORS["brown"], (46, 39, 5, 41))
        pygame.draw.lines(surface, COLORS["brown"], False, ((48, 76), (48, 85), (35, 85), (31, 78)), 5)
    else:
        block(surface, (16, 32, 65, 48), COLORS["brown"])
        pygame.draw.line(surface, INK, (48, 34), (48, 77), 3)
        pygame.draw.polygon(surface, (193, 147, 96), ((16, 32), (31, 18), (48, 32), (65, 18), (81, 32)))


def body_part(surface, name):
    if name == "eye":
        pygame.draw.ellipse(surface, INK, (8, 24, 80, 44))
        pygame.draw.ellipse(surface, COLORS["white"], (13, 28, 70, 36))
        pygame.draw.circle(surface, COLORS["blue"], (48, 46), 17)
        pygame.draw.circle(surface, INK, (48, 46), 8)
        pygame.draw.rect(surface, COLORS["white"], (51, 37, 5, 5))
    elif name == "ear":
        pygame.draw.ellipse(surface, SKIN, (24, 9, 49, 75))
        pygame.draw.lines(surface, (195, 132, 113), False, ((38, 29), (45, 20), (59, 26), (59, 43), (45, 48), (51, 62)), 6)
    elif name == "tooth":
        pygame.draw.polygon(surface, INK, ((18, 18), (35, 10), (49, 16), (62, 10), (79, 20), (73, 54), (64, 85), (54, 83), (48, 58), (39, 83), (28, 85), (22, 54)))
        pygame.draw.polygon(surface, COLORS["white"], ((23, 22), (35, 16), (49, 22), (62, 16), (73, 23), (68, 53), (62, 78), (58, 76), (49, 48), (36, 77), (32, 78), (27, 52)))
    elif name in ("hand", "finger", "glove"):
        color = COLORS["blue"] if name == "glove" else SKIN
        block(surface, (28, 40, 40, 38), color, False)
        for i, x in enumerate((28, 38, 48, 58)):
            block(surface, (x, 13 + abs(i - 1) * 5, 9, 36), COLORS["red"] if name == "finger" and i == 1 else color, False)
        pygame.draw.polygon(surface, color, ((28, 43), (12, 33), (8, 42), (31, 66)))
    elif name in ("head", "face", "nose", "mouth", "tongue", "hair"):
        block(surface, (20, 12, 56, 69), SKIN, False)
        pygame.draw.rect(surface, COLORS["brown"], (20, 12, 56, 14 if name == "hair" else 6))
        for x in (33, 61):
            pygame.draw.rect(surface, INK, (x, 35, 4, 5))
        pygame.draw.polygon(surface, COLORS["red"] if name == "nose" else (199, 141, 114), ((47, 39), (40, 55), (55, 55)))
        pygame.draw.rect(surface, COLORS["red"] if name in ("mouth", "tongue") else INK, (33, 63, 30, 7))
        if name == "tongue":
            pygame.draw.rect(surface, COLORS["pink"], (42, 64, 13, 15))
        if name == "face":
            pygame.draw.rect(surface, COLORS["red"], (25, 28, 46, 46), 3)
    else:
        person(surface)
        rect = {"arm": (25, 36, 8, 30), "leg": (38, 59, 7, 24), "foot": (33, 78, 14, 7), "knee": (38, 66, 8, 8)}[name]
        pygame.draw.rect(surface, COLORS["red"], rect)


def clothing(surface, name):
    if name == "glove":
        body_part(surface, name)
    elif name in ("trousers", "shorts", "jeans"):
        bottom = 59 if name == "shorts" else 85
        block(surface, (22, 13, 54, bottom - 13), COLORS["blue"])
        pygame.draw.rect(surface, (0, 0, 0, 0), (44, 43, 10, bottom - 41))
        pygame.draw.line(surface, INK, (25, 24), (73, 24), 3)
    elif name in ("shoe", "boot", "slipper", "sandal", "sock"):
        color = COLORS["pink"] if name == "sock" else COLORS["brown"]
        block(surface, (38, 16 if name in ("boot", "sock") else 42, 29, 61 if name in ("boot", "sock") else 35), color)
        block(surface, (13, 60, 54, 20), color)
        if name != "sock":
            pygame.draw.rect(surface, INK, (12, 79, 56, 6))
    elif name in ("hat", "cap"):
        block(surface, (25, 22, 47, 40), COLORS["blue"])
        block(surface, (11, 60, 76, 10), COLORS["blue"])
        pygame.draw.rect(surface, COLORS["yellow"], (28, 49, 41, 7))
    elif name == "scarf":
        block(surface, (20, 22, 56, 18), COLORS["red"])
        block(surface, (49, 34, 20, 49), COLORS["red"])
        for y in (46, 62, 77):
            pygame.draw.rect(surface, COLORS["yellow"], (52, y, 14, 4))
    elif name == "belt":
        block(surface, (9, 39, 79, 17), COLORS["brown"])
        pygame.draw.rect(surface, COLORS["yellow"], (42, 35, 22, 25), 5)
    elif name == "button":
        pygame.draw.circle(surface, COLORS["blue"], (48, 48), 32)
        for x in (38, 54):
            for y in (38, 54):
                pygame.draw.rect(surface, INK, (x, y, 5, 5))
    elif name == "zip":
        for y in range(10, 85, 7):
            pygame.draw.rect(surface, COLORS["gray"], (35 if y % 2 else 47, y, 14, 5))
        block(surface, (35, 15, 25, 16), INK, False)
    else:
        color = COLORS["pink"] if name in ("dress", "skirt") else COLORS["blue"]
        bottom = 84 if name in ("dress", "coat", "skirt") else 73
        if name == "skirt":
            pygame.draw.polygon(surface, color, ((29, 20), (67, 20), (85, 84), (11, 84)))
        else:
            pygame.draw.polygon(surface, INK, ((24, 14), (38, 20), (56, 20), (70, 14), (91, 35), (77, 53), (69, 46), (74, bottom), (20, bottom), (25, 46), (17, 53), (4, 35)))
            pygame.draw.polygon(surface, color, ((26, 20), (39, 26), (55, 26), (68, 20), (84, 36), (76, 46), (65, 36), (68, bottom - 5), (26, bottom - 5), (31, 36), (18, 46), (11, 36)))
            if name in ("shirt", "coat", "jacket"):
                for y in range(35, bottom - 6, 12):
                    pygame.draw.rect(surface, COLORS["white"], (46, y, 4, 4))


class WordPictures:
    def __init__(self):
        self.cache = {}

    def picture(self, word_id):
        name = word_id.lower()
        if name in self.cache:
            return self.cache[name]
        surface = pygame.Surface((96, 96), pygame.SRCALPHA)
        if name in ("fox", "bee", "turtle", "axolotl", "allay"):
            image = creature(name, 3)
            surface.blit(image, image.get_rect(center=(48, 48)))
        elif name in ANIMALS:
            animal(surface, name)
        elif name in FOOD:
            food(surface, name)
        elif name in NATURE:
            nature(surface, name)
        elif name in OBJECTS:
            object_picture(surface, name)
        elif name in BODY:
            body_part(surface, name)
        elif name in CLOTHES:
            clothing(surface, name)
        elif name in FACES:
            face(surface, name)
            if name in ("tired", "sleepy"):
                letter(surface, "Z z", 22, (77, 13))
            elif name == "hungry":
                pygame.draw.rect(surface, COLORS["brown"], (27, 77, 42, 9))
            elif name == "thirsty":
                block(surface, (63, 57, 20, 30), COLORS["blue"])
        elif name in PEOPLE:
            if name == "family":
                person(surface, 11, 10)
                person(surface, 61, 10, female=True)
                person(surface, 38, 37, small=True)
            elif name == "teacher":
                block(surface, (39, 10, 51, 42), COLORS["green"])
                person(surface, 15, 20, pose="wave hello")
                pygame.draw.line(surface, SKIN, (35, 49), (59, 27), 5)
            elif name == "friend":
                person(surface, 15, 16, small=True)
                person(surface, 62, 16, small=True, female=True)
                pygame.draw.line(surface, SKIN, (39, 55), (55, 55), 5)
            elif name == "baby":
                block(surface, (28, 11, 39, 34), SKIN, False)
                for x in (39, 54):
                    pygame.draw.rect(surface, INK, (x, 26, 3, 4))
                pygame.draw.polygon(surface, COLORS["blue"], ((20, 45), (76, 45), (69, 84), (32, 88), (20, 65)))
                pygame.draw.line(surface, COLORS["white"], (23, 47), (67, 73), 5)
            elif name in ("mother", "father", "grandma", "grandpa"):
                person(surface, 15, 8, female=name in ("mother", "grandma"), old=name in ("grandma", "grandpa"))
                person(surface, 65, 35, small=True)
            else:
                small = name in ("sister", "brother", "baby", "boy", "girl", "friend", "child")
                person(surface, small=small, female=name in ("mother", "sister", "girl", "grandma", "woman"), old=name in ("grandma", "grandpa"))
        elif name in NUMBERS:
            letter(surface, str(NUMBERS[name]), 54, (48, 28), COLORS["blue"])
            for i in range(NUMBERS[name]):
                pygame.draw.rect(surface, COLORS["red"], (14 + i % 5 * 15, 57 + i // 5 * 11, 8, 8))
        elif name in COLORS:
            block(surface, (13, 19, 70, 59), COLORS[name])
        elif name in ("yes", "no", "good"):
            if name == "no":
                pygame.draw.line(surface, COLORS["red"], (20, 20), (76, 76), 11)
                pygame.draw.line(surface, COLORS["red"], (20, 76), (76, 20), 11)
            else:
                pygame.draw.lines(surface, COLORS["green"], False, ((14, 46), (37, 70), (82, 18)), 11)
        elif name in ("big", "small", "little", "long", "short", "round"):
            if name == "round":
                pygame.draw.circle(surface, COLORS["blue"], (48, 48), 31)
            else:
                block(surface, (8, 55, 23, 23), COLORS["gray"])
                block(surface, (44, 16, 42, 62), COLORS["blue"])
                x = 18 if name in ("small", "little", "short") else 64
                pygame.draw.polygon(surface, COLORS["red"], ((x - 6, 3), (x + 6, 3), (x, 13)))
        elif name in ("hot", "cold"):
            nature(surface, "sun" if name == "hot" else "snow")
        elif name in ("clean", "dirty", "new"):
            block(surface, (22, 18, 52, 61), COLORS["white"] if name != "new" else COLORS["blue"])
            if name == "dirty":
                for x, y in ((30, 32), (57, 49), (39, 66)):
                    pygame.draw.rect(surface, COLORS["brown"], (x, y, 11, 8))
            else:
                letter(surface, "+", 35, (70, 20), COLORS["yellow"])
        elif name in ACTIONS:
            if name in ("smile", "laugh", "cry"):
                face(surface, name)
            elif name == "sleep":
                object_picture(surface, "bed")
                letter(surface, "Z z", 25, (53, 15))
            elif name in ("look", "listen"):
                face(surface)
                if name == "look":
                    pygame.draw.rect(surface, COLORS["blue"], (34, 30, 26, 10), 2)
                else:
                    for x in (78, 86):
                        pygame.draw.line(surface, COLORS["blue"], (x, 24), (x + 4, 39), 3)
            elif name in ("open", "close"):
                object_picture(surface, "door")
                if name == "open":
                    pygame.draw.polygon(surface, COLORS["brown"], ((24, 25), (50, 33), (50, 91), (24, 80)))
            elif name in ("give", "take"):
                block(surface, (36, 39, 25, 26), COLORS["yellow"])
                pygame.draw.rect(surface, SKIN, (5, 56, 31, 12))
                pygame.draw.rect(surface, SKIN, (61, 56, 30, 12))
                pygame.draw.line(surface, COLORS["red"], (22, 24), (74, 24), 4)
                points = ((74, 16), (85, 24), (74, 32)) if name == "give" else ((22, 16), (11, 24), (22, 32))
                pygame.draw.polygon(surface, COLORS["red"], points)
            else:
                person(surface, pose=name)
                if name in ("play", "kick", "throw", "catch"):
                    pygame.draw.circle(surface, COLORS["red"], (80, 70), 10)
                if name == "run":
                    for y in (47, 57, 67):
                        pygame.draw.line(surface, COLORS["blue"], (3, y), (19, y), 3)
                elif name in ("eat", "drink"):
                    block(surface, (62, 31, 17, 21), COLORS["red"] if name == "eat" else COLORS["blue"])
                elif name in ("read", "write", "draw", "paint"):
                    block(surface, (55, 42, 31, 24), COLORS["white"])
        elif name in ("hello", "bye", "goodbye", "welcome", "please", "thanks", "sorry"):
            person(surface, pose="wave hello")
        else:
            self.cache[name] = None
            return None
        bounds = surface.get_bounding_rect()
        self.cache[name] = surface.subsurface(bounds.inflate(4, 4).clip(surface.get_rect())).copy()
        return self.cache[name]

    def draw(self, surface, word_id, rect):
        picture = self.picture(word_id)
        if picture is None:
            return False
        ratio = min(rect.width / picture.get_width(), rect.height / picture.get_height())
        scaled = pygame.transform.scale(picture, (max(1, round(picture.get_width() * ratio)), max(1, round(picture.get_height() * ratio))))
        surface.blit(scaled, scaled.get_rect(center=rect.center))
        return True
