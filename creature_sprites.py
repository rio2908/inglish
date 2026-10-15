"""Original voxel-style Minecraft creature drawings, built on a small pixel grid."""

import pygame


PALETTES = {
    "axolotl": (239, 157, 181), "fox": (224, 120, 42), "bee": (246, 190, 49),
    "turtle": (76, 154, 86), "allay": (80, 194, 227),
}
EDGE = (29, 43, 44)


def shade(color, factor):
    return tuple(max(0, min(255, round(value * factor))) for value in color)


def block(surface, rect, color, grid=True):
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, EDGE, rect)
    inner = rect.inflate(-2, -2)
    if inner.width <= 0 or inner.height <= 0:
        return
    pygame.draw.rect(surface, color, inner)
    pygame.draw.rect(surface, shade(color, 1.18), (inner.x, inner.y, inner.width, min(2, inner.height)))
    pygame.draw.rect(surface, shade(color, 0.7), (inner.right - min(3, inner.width), inner.y, min(3, inner.width), inner.height))
    if grid:
        for x in range(inner.x + 4, inner.right, 4):
            pygame.draw.line(surface, shade(color, 0.83), (x, inner.y), (x, inner.bottom - 1))
        for y in range(inner.y + 4, inner.bottom, 4):
            pygame.draw.line(surface, shade(color, 0.83), (inner.x, y), (inner.right - 1, y))


def eye(surface, x, y):
    pygame.draw.rect(surface, EDGE, (x, y, 3, 4))
    pygame.draw.rect(surface, (246, 252, 241), (x, y, 1, 1))


GROWTH_SIZES = {1: (245, 150), 2: (270, 180), 3: (290, 210), 4: (310, 230)}


def _axolotl(surface, stage, step):
    color = PALETTES["axolotl"]
    body, head, tail, foot = {
        1: ((22, 37, 18, 11), (35, 29, 23, 19), (13, 40, 12, 5), 4),
        2: ((18, 34, 26, 14), (38, 24, 23, 21), (5, 36, 17, 7), 6),
        3: ((17, 32, 29, 17), (40, 21, 24, 23), (2, 34, 19, 10), 8),
        4: ((17, 32, 30, 19), (40, 20, 25, 24), (2, 32, 20, 14), 9),
    }[stage]
    block(surface, tail, shade(color, 0.86))
    if stage >= 2:
        block(surface, (tail[0] + 4, tail[1] - (8 if stage == 4 else 5), 12, 7), (213, 112, 164))
    if stage == 4:
        block(surface, (19, 26, 24, 8), (177, 113, 190))
        for x in (8, 16, 24, 32):
            pygame.draw.rect(surface, (249, 199, 218), (x, 29, 3, 3))
    block(surface, body, color)
    for i, x in enumerate((body[0] + 4, body[0] + body[2] - 9)):
        block(surface, (x, body[1] + body[3] - 3 + (step if i else -step), foot, foot + 2), shade(color, 1.06))
    hx, hy, hw, hh = head
    branches = 1 if stage == 1 else 2 if stage == 2 else 3
    length = (4, 7, 8, 9)[stage - 1]
    gill_color = (202, 78, 135) if stage < 4 else (160, 83, 172)
    for side in (-1, 1):
        base_x = hx - length + 2 if side < 0 else hx + hw - 2
        for branch in range(branches):
            y = hy + 2 + branch * 7
            block(surface, (base_x, y, length, 4), gill_color, False)
            if stage >= 3:
                tip_x = base_x if side < 0 else base_x + length - 3
                block(surface, (tip_x, y - 3, 3, 5), (237, 139, 192), False)
    block(surface, head, shade(color, 1.07))
    eye(surface, hx + 8, hy + 7)
    eye(surface, hx + 17, hy + 7)
    pygame.draw.rect(surface, (169, 65, 104), (hx + 11, hy + hh - 5, 7, 1))
    if stage >= 2:
        for x in (hx + 4, hx + 11, hx + 18):
            pygame.draw.rect(surface, (255, 208, 213), (x, hy + 3, 2, 2))


def _fox(surface, stage, step):
    color, white, dark = PALETTES["fox"], (245, 237, 215), (67, 54, 49)
    body, head, tail, leg, ear = {
        1: ((24, 37, 18, 14), (36, 26, 24, 22), (13, 40, 14, 7), 6, 7),
        2: ((21, 34, 25, 16), (39, 21, 23, 23), (5, 33, 20, 12), 9, 12),
        3: ((19, 33, 29, 18), (43, 20, 23, 22), (2, 28, 21, 18), 12, 16),
        4: ((19, 33, 30, 18), (43, 20, 24, 22), (2, 25, 23, 23), 12, 17),
    }[stage]
    block(surface, tail, color)
    if stage == 4:
        block(surface, (6, 19, 13, 11), color)
    block(surface, (tail[0], tail[1], 5 + stage, tail[3] - 2), white)
    for i, x in enumerate((body[0] + 4, body[0] + body[2] - 8)):
        block(surface, (x, body[1] + body[3] - 3 + (step if i else -step), 5 + (stage > 2), leg), dark)
    block(surface, body, color)
    hx, hy, hw, hh = head
    for x in (hx + 2, hx + hw - 8):
        block(surface, (x, hy - ear, 7, ear + 4), color)
        pygame.draw.rect(surface, dark, (x + 2, hy - ear + 2, 3, max(2, ear - 4)))
    if stage >= 3:
        block(surface, (40, 36, 12 if stage == 4 else 9, 19 if stage == 4 else 16), white)
        if stage == 4:
            block(surface, (36, 40, 9, 10), white)
    block(surface, head, color)
    muzzle = (hx + 12, hy + hh - 9, 12 + stage, 9)
    block(surface, muzzle, white)
    pygame.draw.rect(surface, EDGE, (min(68, muzzle[0] + muzzle[2] - 3), muzzle[1], 4, 4))
    eye(surface, hx + 7, hy + 6)
    eye(surface, hx + 16, hy + 6)
    if stage == 4:
        # A leafy ear accent replaces the identical flower crown used by every species.
        block(surface, (44, 7, 8, 4), (112, 172, 73), False)
        pygame.draw.rect(surface, (250, 199, 64), (47, 4, 3, 3))


def _bee(surface, stage, step):
    color, brown, wing = PALETTES["bee"], (91, 65, 43), (216, 244, 237)
    body, head, wings = {
        1: ((25, 35, 20, 16), (42, 31, 18, 19), ((30, 27, 7, 10), (39, 24, 8, 13))),
        2: ((18, 31, 29, 21), (44, 27, 20, 23), ((22, 15, 9, 18), (34, 12, 12, 22))),
        3: ((13, 28, 35, 24), (45, 25, 22, 25), ((18, 8, 13, 24), (32, 4, 15, 27))),
        4: ((12, 28, 36, 24), (45, 25, 22, 25), ((16, 5, 15, 27), (32, 2, 17, 29))),
    }[stage]
    if stage >= 3:
        block(surface, (10, 23 - step, 13, 15), (163, 210, 219))
    for i, (x, y, w, h) in enumerate(wings):
        block(surface, (x, y + (step * 2 if i else -step * 2), w, h), wing)
        if stage >= 2:
            pygame.draw.line(surface, (141, 196, 201), (x + w // 2, y + 3), (x + w // 2, y + h - 2))
    block(surface, body, color)
    for i in range(stage if stage < 3 else 3):
        x = body[0] + 6 + i * 10
        if x + 4 < body[0] + body[2]:
            block(surface, (x, body[1] + 2, 5, body[3] - 4), brown)
    for i in range(2 if stage == 1 else 3):
        x = body[0] + 7 + i * 10
        block(surface, (x, body[1] + body[3] - 1, 3, 6 + step), brown, False)
    if stage >= 3:
        block(surface, (body[0] - 5, body[1] + 10, 6, 4), brown, False)
    hx, hy, hw, hh = head
    block(surface, head, color)
    for x in (hx + 5, hx + hw - 5):
        pygame.draw.rect(surface, EDGE, (x, hy - 3 - stage, 2, 4 + stage))
        if stage >= 3:
            pygame.draw.rect(surface, brown, (x - 1, hy - 4 - stage, 4, 3))
    eye(surface, hx + 4, hy + 7)
    eye(surface, hx + hw - 6, hy + 7)
    for x in (hx + 3, hx + hw - 7):
        pygame.draw.rect(surface, (223, 117, 92), (x, hy + hh - 9, 3, 2))
    if stage == 4:
        for x in (21, 35):
            block(surface, (x, 49, 8, 8), (244, 145, 36), False)
            pygame.draw.rect(surface, (255, 223, 91), (x + 2, 50, 3, 3))
        pygame.draw.rect(surface, (246, 237, 162), (51, 43, 9, 2))


def _turtle(surface, stage, step):
    color = PALETTES["turtle"]
    body, shell, head, flipper = {
        1: ((24, 38, 24, 12), (27, 32, 19, 16), (45, 36, 17, 14), 8),
        2: ((17, 37, 33, 14), (20, 27, 29, 23), (47, 34, 18, 15), 11),
        3: ((11, 37, 41, 16), (12, 25, 39, 27), (50, 34, 19, 16), 15),
        4: ((10, 37, 42, 16), (11, 24, 40, 28), (50, 34, 19, 16), 16),
    }[stage]
    for i, x in enumerate((body[0], body[0] + body[2] - flipper)):
        block(surface, (x, body[1] + body[3] - 3 + (step if i else -step), flipper, 5 + stage), shade(color, 1.15))
    block(surface, body, color)
    block(surface, shell, (67, 111, 63))
    sx, sy, sw, sh = shell
    if stage >= 3:
        block(surface, (sx + 7, sy - 6, sw - 14, 15), (74, 126, 68))
    if stage == 1:
        block(surface, (sx + 5, sy + 4, 10, 8), (149, 183, 97))
    else:
        for x, y in ((sx + 5, sy + 3), (sx + sw - 13, sy + 3), (sx + sw // 2 - 4, sy + 13)):
            block(surface, (x, y, 9, 8), (130, 168, 84))
        if stage >= 3:
            block(surface, (sx + 15, sy - 3, 10, 8), (160, 182, 94))
    if stage == 4:
        for x, y in ((14, 23), (23, 17), (39, 19), (16, 35)):
            block(surface, (x, y, 7, 5), (133, 178, 76), False)
        pygame.draw.rect(surface, (62, 139, 74), (30, 13, 2, 11))
        pygame.draw.rect(surface, (244, 132, 175), (26, 10, 10, 4))
        pygame.draw.rect(surface, (244, 132, 175), (29, 7, 4, 10))
        pygame.draw.rect(surface, (255, 211, 79), (29, 10, 4, 4))
    block(surface, head, shade(color, 1.2))
    hx, hy, hw, hh = head
    eye(surface, hx + 5, hy + 4)
    eye(surface, hx + hw - 4, hy + 4)
    pygame.draw.rect(surface, (54, 92, 55), (hx + 8, hy + hh - 4, 7, 1))


def _allay(surface, stage, step):
    color, pale = PALETTES["allay"], (160, 232, 237)
    head = (26, 20 if stage == 1 else 15 if stage == 2 else 13, 25, 23)
    body = (31, 40, 14, 13) if stage == 1 else (30, 36, 17, 19) if stage == 2 else (31, 35, 17, 21)
    wings = {
        1: ((22, 38, 8, 9), (46, 36, 8, 11)),
        2: ((14, 29, 14, 19), (47, 26, 13, 21)),
        3: ((6, 23, 20, 17), (10, 35, 14, 15), (49, 19, 17, 18), (52, 33, 11, 17)),
        4: ((3, 17, 23, 20), (8, 33, 18, 20), (51, 15, 18, 22), (53, 33, 15, 19)),
    }[stage]
    for i, (x, y, w, h) in enumerate(wings):
        block(surface, (x, y + (step if i % 2 else -step), w, h), pale if stage < 4 else (187, 249, 240))
        if stage >= 3:
            pygame.draw.rect(surface, (229, 255, 249), (x + 2, y + 3, 2, h - 5))
    bx, by, bw, bh = body
    for x in (bx + 1, bx + bw - 6):
        block(surface, (x, by + bh - 1, 5, 6 if stage == 1 else 10), shade(color, 0.8))
    block(surface, body, color)
    for x in (bx - 6, bx + bw):
        block(surface, (x, by + 2, 7, 9 if stage == 1 else 14), color)
    block(surface, head, color)
    hx, hy, _, _ = head
    eye(surface, hx + 6, hy + 8)
    eye(surface, hx + 17, hy + 8)
    pygame.draw.rect(surface, (229, 255, 249), (hx + 8, hy + 16, 11, 2))
    if stage >= 2:
        block(surface, (bx + bw + 4, by + 13, 7 if stage == 2 else 10, 8 if stage == 2 else 10), (139, 226, 210), False)
    if stage >= 3:
        pygame.draw.rect(surface, (229, 255, 249), (bx + 7, by + 5, 3, 7))
        pygame.draw.rect(surface, (229, 255, 249), (bx + 5, by + 7, 7, 3))
    if stage == 4:
        for x, y in ((15, 7), (60, 5)):
            pygame.draw.rect(surface, (141, 230, 234), (x - 3, y, 7, 3))
            pygame.draw.rect(surface, (141, 230, 234), (x - 1, y - 2, 3, 7))
            pygame.draw.rect(surface, (244, 255, 227), (x, y, 2, 2))
        pygame.draw.rect(surface, (255, 213, 91), (bx + bw + 7, by + 16, 4, 4))


DRAW_CREATURE = {"axolotl": _axolotl, "fox": _fox, "bee": _bee, "turtle": _turtle, "allay": _allay}


def creature(species, stage, frame=0):
    if stage not in GROWTH_SIZES:
        raise ValueError("Creature stages must be 1 through 4")
    surface = pygame.Surface((76, 72), pygame.SRCALPHA)
    step = (-1, 0, 1, 0, -1, 0)[frame % 6]
    DRAW_CREATURE[species](surface, stage, step)
    bounds = surface.get_bounding_rect()
    return surface.subsurface(bounds.inflate(2, 2).clip(surface.get_rect())).copy()


def egg(species, cracks):
    surface = pygame.Surface((44, 52), pygame.SRCALPHA)
    color = shade(PALETTES[species], 1.1)
    outline = ((16, 4), (28, 4), (28, 8), (33, 8), (33, 14), (37, 14),
               (37, 36), (33, 36), (33, 43), (29, 43), (29, 46), (15, 46),
               (15, 43), (11, 43), (11, 36), (7, 36), (7, 14), (11, 14), (11, 8), (16, 8))
    pygame.draw.polygon(surface, color, outline)
    for y in range(4, 47):
        for x in range(7, 38):
            if surface.get_at((x, y)).a:
                factor = 0.75 if x >= 30 else 1.15 if y < 12 else 1
                if x % 4 == 0 or y % 4 == 0:
                    factor *= 0.83
                surface.set_at((x, y), shade(color, factor))
    pygame.draw.polygon(surface, EDGE, outline, 1)
    for x, y in ((14, 13), (24, 22), (12, 33), (27, 36)):
        pygame.draw.rect(surface, shade(color, 0.65), (x, y, 5, 4))
    for i in range(cracks):
        x, y = 17 + (i % 2) * 7, 12 + i * 6
        pygame.draw.lines(surface, EDGE, False, ((x, y), (x + 4, y + 4), (x, y + 8)), 2)
    return surface


def families(species):
    return {
        "growth": [egg(species, 0)] + [creature(species, stage) for stage in range(1, 5)],
        "hatching": [egg(species, cracks) for cracks in range(4)] + [creature(species, 1)],
        "walk": [creature(species, 2, frame) for frame in range(6)],
    }
