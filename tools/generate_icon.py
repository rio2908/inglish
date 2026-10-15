"""Generate Inglish launcher icons from the game's own transparent pixel sprite."""

import os
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame

from sprites import _split_strip


def make_art():
    art = pygame.Surface((128, 128), pygame.SRCALPHA)
    pet = _split_strip("growth-grid.png", [0, 245, 535, 935, 1470, 2160])[1]
    ratio = min(104 / pet.get_width(), 86 / pet.get_height())
    pet = pygame.transform.scale(pet, (round(pet.get_width() * ratio), round(pet.get_height() * ratio)))
    pygame.draw.ellipse(art, (40, 97, 65, 150), (13, 88, 100, 16))
    art.blit(pet, pet.get_rect(midbottom=(62, 100)))
    # A small open book identifies this as the language game, not just a pet app.
    pygame.draw.rect(art, (34, 47, 43), (78, 79, 37, 34))
    pygame.draw.rect(art, (255, 194, 70), (81, 82, 31, 28))
    pygame.draw.rect(art, (253, 247, 224), (84, 82, 25, 24))
    pygame.draw.rect(art, (224, 209, 170), (96, 82, 3, 24))
    for x in (86, 101):
        for y in (88, 94, 100):
            pygame.draw.rect(art, (29, 111, 102), (x, y, 6, 2))
    return art


def main():
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    try:
        assets = ROOT / "assets"
        art = make_art()
        icon = pygame.Surface((128, 128))
        icon.fill((29, 111, 102))
        pygame.draw.rect(icon, (82, 171, 147), (8, 8, 112, 112))
        pygame.draw.rect(icon, (112, 169, 82), (8, 76, 112, 44))
        pygame.draw.rect(icon, (255, 194, 70), (96, 17, 13, 13))
        icon.blit(art, (0, 0))
        pygame.image.save(pygame.transform.scale(icon, (512, 512)), str(assets / "icon.png"))

        # Keep the important artwork inside the center of Android's adaptive mask.
        foreground = pygame.Surface((432, 432), pygame.SRCALPHA)
        foreground.blit(pygame.transform.scale(art, (264, 264)), (84, 84))
        background = pygame.Surface((432, 432))
        background.fill((29, 111, 102))
        pygame.draw.rect(background, (82, 171, 147), (0, 0, 432, 270))
        pygame.draw.rect(background, (112, 169, 82), (0, 270, 432, 162))
        pygame.image.save(foreground, str(assets / "icon-foreground.png"))
        pygame.image.save(background, str(assets / "icon-background.png"))
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
