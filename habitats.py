"""Cached pixel habitats with lightweight ambient animation for each companion."""

import math

import pygame


HABITAT_NAMES = {
    "sniffer": "Лужайка", "axolotl": "Подводный мир", "fox": "Лесная опушка",
    "bee": "Цветочная поляна", "turtle": "Морской берег", "allay": "Волшебная роща",
}
GROUND_COLORS = {
    "sniffer": ((105, 157, 74), (116, 166, 81)),
    "axolotl": ((199, 188, 135), (211, 202, 151)),
    "fox": ((112, 148, 82), (124, 158, 90)),
    "bee": ((132, 176, 88), (144, 186, 97)),
    "turtle": ((223, 199, 142), (234, 214, 163)),
    "allay": ((128, 164, 151), (139, 174, 160)),
}
SHADOW_COLORS = {"sniffer": (76, 133, 63), "axolotl": (149, 156, 119), "fox": (80, 119, 67),
                 "bee": (96, 145, 67), "turtle": (188, 165, 114), "allay": (94, 137, 130)}


def kelp(surface, x, bottom, height):
    pygame.draw.rect(surface, (39, 125, 102), (x, bottom - height, 7, height))
    for i, y in enumerate(range(bottom - height + 8, bottom - 5, 20)):
        pygame.draw.rect(surface, (66, 164, 124), (x - 15 if i % 2 else x + 4, y, 20, 8))
        pygame.draw.rect(surface, (106, 191, 137), (x - 11 if i % 2 else x + 8, y, 12, 3))


def flower(surface, x, y, color, size=8):
    pygame.draw.rect(surface, (59, 126, 71), (x - 2, y, 5, 25))
    for dx, dy in ((-size, 0), (size, 0), (0, -size), (0, size)):
        pygame.draw.rect(surface, color, (x + dx - size // 2, y + dy - size // 2, size, size))
    pygame.draw.rect(surface, (255, 216, 93), (x - size // 2, y - size // 2, size, size))


def tree(surface, x, bottom, height, enchanted=False):
    trunk = (101, 83, 106) if enchanted else (113, 83, 56)
    pygame.draw.rect(surface, trunk, (x - 15, bottom - height, 30, height))
    pygame.draw.rect(surface, (137, 110, 97), (x - 10, bottom - height, 5, height))
    colors = ((123, 148, 175), (147, 163, 191), (165, 177, 203)) if enchanted else ((64, 111, 75), (83, 133, 83), (110, 151, 92))
    for i in range(3):
        width = 160 - i * 28
        pygame.draw.rect(surface, colors[i], (x - width // 2, bottom - height - 40 - i * 26, width, 58))


class Habitats:
    def __init__(self):
        self.cache = {}

    def _background(self, species, size, play):
        surface = pygame.Surface(size)
        width, height = size
        ground_y = 280 if play else 390
        if species == "sniffer":
            surface.fill((145, 213, 221))
            pygame.draw.rect(surface, (219, 239, 218), (0, 0, width, 260))
            for x, y in ((86, 114), (610, 138), (855, 84)):
                pygame.draw.rect(surface, (255, 255, 255), (x, y + 15, 86, 18))
                pygame.draw.rect(surface, (255, 255, 255), (x + 18, y, 50, 36))
        elif species == "axolotl":
            for y in range(0, ground_y, 26):
                depth = y / max(1, ground_y)
                color = (round(104 - depth * 62), round(207 - depth * 52), round(214 - depth * 43))
                pygame.draw.rect(surface, color, (0, y, width, 26))
            for x in (145, 365, 750):
                pygame.draw.polygon(surface, (104, 201, 204), ((x, 65), (x + 24, 65), (x + 115, ground_y), (x + 63, ground_y)))
        elif species == "turtle":
            surface.fill((178, 228, 228))
            pygame.draw.rect(surface, (255, 220, 124), (815, 106, 45, 45))
            sea_y = 195 if play else 235
            for i, color in enumerate(((85, 183, 194), (72, 170, 188), (97, 191, 197))):
                pygame.draw.rect(surface, color, (0, sea_y + i * 45, width, max(0, ground_y - sea_y - i * 45)))
            pygame.draw.rect(surface, (218, 239, 213), (0, ground_y - 9, width, 9))
        else:
            sky = {"fox": (197, 219, 192), "bee": (186, 226, 219), "allay": (204, 193, 231)}[species]
            surface.fill(sky)
            if species == "bee":
                pygame.draw.rect(surface, (255, 220, 112), (790, 100, 52, 52))
            elif species == "allay":
                pygame.draw.rect(surface, (242, 245, 220), (815, 105, 37, 43))
                pygame.draw.rect(surface, sky, (827, 100, 30, 33))
            else:
                pygame.draw.rect(surface, (144, 176, 126), (0, 270 if not play else 225, width, ground_y))
            if species in ("fox", "allay"):
                locations = (30, 960) if play else (65, 575, 950)
                for i, x in enumerate(locations):
                    tree(surface, x, ground_y + 8, 135 + (i % 2) * 55, species == "allay")
        colors = GROUND_COLORS[species]
        pygame.draw.rect(surface, colors[0], (0, ground_y, width, height - ground_y))
        for y in range(ground_y if play else 430, height, 34):
            for x in range(0, width, 34):
                pygame.draw.rect(surface, colors[1 - (x // 34 + y // 34) % 2], (x, y, 34, 34))
        if species == "sniffer" and not play:
            pygame.draw.rect(surface, (67, 123, 59), (0, 390, width, 13))
        if species == "axolotl":
            for x, h in ((24, 125), (103, 88), (615, 105), (960, 140)):
                kelp(surface, x, ground_y + 18, h if not play else h // 2)
            for x in (145, 570, 875):
                if play and 100 < x < 900:
                    continue
                for dx, h in ((0, 35), (15, 52), (30, 26)):
                    pygame.draw.rect(surface, (211, 112, 138), (x + dx, ground_y + 20 - h, 9, h))
                pygame.draw.rect(surface, (235, 156, 160), (x - 5, ground_y - 4, 49, 8))
            for x, y in ((50, 445), (195, 474), (600, 453), (890, 485)):
                pygame.draw.rect(surface, (161, 164, 140), (x, y, 20, 12))
        elif species == "bee":
            for i, x in enumerate(range(20, width, 67)):
                if not play or x < 65 or x > 935:
                    flower(surface, x, ground_y + 10 + (i % 3) * 18, ((244, 145, 166), (247, 245, 217), (202, 158, 210))[i % 3])
            tree(surface, 930, ground_y + 10, 165)
            pygame.draw.rect(surface, (168, 114, 55), (899, ground_y - 115, 57, 53))
            for y in range(ground_y - 110, ground_y - 62, 9):
                pygame.draw.rect(surface, (225, 167, 67), (903, y, 49, 5))
            pygame.draw.rect(surface, (87, 69, 45), (917, ground_y - 82, 15, 10))
        elif species == "turtle":
            for x, y in ((70, 451), (595, 473), (902, 451)):
                pygame.draw.rect(surface, (246, 235, 203), (x, y, 19, 11))
                pygame.draw.rect(surface, (213, 161, 145), (x + 4, y - 4, 10, 5))
            pygame.draw.rect(surface, (125, 99, 66), (53, ground_y - 140, 18, 140))
            for x, y, w in ((5, ground_y - 145, 135), (23, ground_y - 164, 98), (42, ground_y - 182, 45)):
                pygame.draw.rect(surface, (76, 139, 95), (x, y, w, 18))
        elif species == "allay":
            for x in (30, 140, 610, 930):
                pygame.draw.rect(surface, (215, 222, 197), (x, ground_y - 10, 8, 28))
                pygame.draw.rect(surface, (139, 116, 184), (x - 12, ground_y - 21, 32, 14))
                pygame.draw.rect(surface, (216, 188, 234), (x - 7, ground_y - 18, 6, 4))
        elif species == "fox":
            for i, x in enumerate((28, 134, 550, 915)):
                pygame.draw.rect(surface, (171, 120, 66), (x, ground_y + 35 + i % 2 * 14, 14, 7))
                pygame.draw.rect(surface, (201, 157, 77), (x + 8, ground_y + 31 + i % 2 * 14, 9, 6))
        return surface

    def _growth_details(self, surface, species, stage, play):
        ground = 280 if play else 390
        if play:
            # Decorative borders never cover the large interactive game areas.
            for level in range(stage):
                for x in (18, 967):
                    if species == "axolotl":
                        kelp(surface, x, ground + 35 + level * 30, 25)
                    else:
                        flower(surface, x, ground + 20 + level * 30, (236, 166, 178), 5)
            return
        if stage >= 1:
            for x, y in ((70, ground + 35), (615, ground + 70), (915, ground + 50)):
                color = (147, 161, 143) if species not in ("turtle", "axolotl") else (185, 176, 145)
                pygame.draw.rect(surface, color, (x, y, 23, 12))
                pygame.draw.rect(surface, (203, 207, 177), (x + 5, y - 5, 12, 6))
        if stage >= 2:
            for x in (140, 585):
                if species == "axolotl":
                    kelp(surface, x, ground + 67, 48)
                elif species == "turtle":
                    for dx in (0, 8, 16):
                        pygame.draw.rect(surface, (97, 153, 98), (x + dx, ground + 22 - dx, 4, 28 + dx))
                elif species == "allay":
                    pygame.draw.rect(surface, (216, 225, 211), (x, ground + 22, 7, 26))
                    pygame.draw.rect(surface, (168, 124, 190), (x - 9, ground + 13, 27, 13))
                    pygame.draw.rect(surface, (238, 209, 241), (x - 3, ground + 15, 5, 4))
                else:
                    flower(surface, x, ground + 35, (248, 170, 187), 9)
        if stage >= 3:
            if species == "axolotl":
                for x, color in ((77, (222, 143, 108)), (592, (173, 124, 184))):
                    for dx, height in ((0, 36), (12, 57), (24, 44)):
                        pygame.draw.rect(surface, color, (x + dx, ground + 57 - height, 7, height))
                    pygame.draw.rect(surface, color, (x - 5, ground + 28, 38, 7))
            elif species == "fox":
                pygame.draw.rect(surface, (133, 94, 61), (110, ground + 61, 68, 22))
                pygame.draw.rect(surface, (188, 142, 88), (112, ground + 64, 14, 16))
                pygame.draw.rect(surface, (98, 77, 51), (116, ground + 68, 6, 8))
                tree(surface, 620, ground + 30, 80)
            elif species == "bee":
                tree(surface, 640, ground + 10, 172)
                pygame.draw.rect(surface, (121, 90, 55), (583, ground - 125, 58, 8))
                pygame.draw.rect(surface, (174, 119, 51), (583, ground - 103, 42, 49))
                for y in range(ground - 99, ground - 55, 8):
                    pygame.draw.rect(surface, (240, 179, 70), (587, y, 34, 4))
                pygame.draw.rect(surface, (79, 65, 42), (599, ground - 70, 12, 9))
            elif species == "allay":
                for x, height in ((115, 36), (141, 51), (590, 42)):
                    pygame.draw.rect(surface, (115, 195, 197), (x, ground + 62 - height, 15, height))
                    pygame.draw.rect(surface, (208, 247, 224), (x + 3, ground + 64 - height, 4, height - 4))
            elif species == "turtle":
                for x in (120, 600):
                    pygame.draw.rect(surface, (242, 179, 155), (x, ground + 70, 21, 7))
                    pygame.draw.rect(surface, (251, 221, 183), (x + 4, ground + 64, 13, 7))
            else:
                for x in (88, 598):
                    pygame.draw.rect(surface, (62, 129, 73), (x, ground + 17, 49, 28))
                    pygame.draw.rect(surface, (94, 156, 79), (x + 9, ground + 6, 29, 32))
        if stage >= 4:
            if species == "axolotl":
                pygame.draw.rect(surface, (130, 108, 76), (126, ground + 50, 37, 27))
                pygame.draw.rect(surface, (201, 158, 77), (126, ground + 53, 37, 8))
                pygame.draw.rect(surface, (255, 213, 94), (141, ground + 58, 7, 9))
                for x in (543, 579):
                    pygame.draw.rect(surface, (140, 163, 153), (x, ground + 16, 13, 57))
                pygame.draw.rect(surface, (162, 184, 163), (543, ground + 10, 49, 15))
            elif species == "turtle":
                pygame.draw.rect(surface, (202, 165, 100), (550, ground + 43, 72, 36))
                for x in (548, 572, 600):
                    pygame.draw.rect(surface, (238, 207, 143), (x, ground + 26, 20, 42))
                    pygame.draw.rect(surface, (251, 228, 173), (x, ground + 22, 6, 9))
                pygame.draw.rect(surface, (157, 126, 84), (578, ground + 60, 11, 20))
            elif species == "allay":
                for x in (75, 555, 610):
                    flower(surface, x, ground + 51, (208, 174, 227), 10)
                    pygame.draw.rect(surface, (245, 248, 188), (x - 2, ground + 49, 4, 4))
            else:
                for i, x in enumerate((97, 125, 160, 554, 585, 620)):
                    flower(surface, x, ground + 65 + (i % 2) * 7, ((246, 170, 190), (247, 236, 163), (199, 157, 216))[i % 3], 7)

    def draw(self, surface, species, now, play=False, stage=0):
        key = (species, surface.get_size(), play)
        if key not in self.cache:
            self.cache[key] = self._background(species, surface.get_size(), play)
        surface.blit(self.cache[key], (0, 0))
        stage = max(0, min(4, stage))
        self._growth_details(surface, species, stage, play)
        ground_y = 280 if play else 390
        if species == "axolotl":
            for i in range(8 + stage * 2):
                x = 40 + i * 82 + int(math.sin(now * 0.8 + i) * 10)
                y = 100 + ((i * 41 - now * (15 + i % 3 * 4)) % (ground_y - 80))
                size = 6 + i % 3 * 3
                pygame.draw.rect(surface, (175, 231, 225), (round(x), round(y), size, size + 2), 2)
            for i in range(1 + stage // 2):
                x = round((110 + i * 310 + now * (9 + i * 4)) % 1060) - 30
                y = 215 + i * 38 if not play else 195 + i * 16
                color = ((239, 190, 108), (167, 207, 225), (225, 161, 164))[i]
                pygame.draw.rect(surface, color, (x, y, 18, 9))
                pygame.draw.polygon(surface, color, ((x, y + 4), (x - 7, y - 2), (x - 7, y + 10)))
                pygame.draw.rect(surface, (39, 87, 103), (x + 13, y + 2, 2, 2))
        elif species == "turtle":
            for i in range(8):
                x = (i * 147 + int(now * 12)) % surface.get_width()
                pygame.draw.rect(surface, (197, 234, 223), (x, ground_y - 23 - (i % 3) * 32, 43, 3))
        elif species == "allay":
            for i in range(4 + stage * 3):
                x = 25 + i * 62 + math.sin(now * 0.7 + i * 2) * 15
                y = 200 + (i * 31 % 190) + math.cos(now + i) * 12
                if math.sin(now * 2 + i) > -0.25:
                    pygame.draw.rect(surface, (250, 240, 158), (round(x), round(y), 4, 4))
        elif species == "fox":
            for i in range(4):
                x = 75 + i * 235 + math.sin(now * 0.8 + i) * 30
                y = 180 + ((now * 12 + i * 55) % 240)
                pygame.draw.rect(surface, (207, 168, 96), (round(x), round(y), 7, 4))
        elif species == "bee" and stage >= 3:
            for i in range(stage - 2):
                x = 170 + i * 380 + math.sin(now * 1.2 + i) * 35
                y = 230 + math.cos(now * 1.8 + i) * 13
                pygame.draw.rect(surface, (213, 139, 184), (round(x - 8), round(y - 4), 7, 10))
                pygame.draw.rect(surface, (239, 175, 196), (round(x + 2), round(y - 4), 7, 10))
                pygame.draw.rect(surface, (87, 93, 81), (round(x), round(y), 2, 9))
