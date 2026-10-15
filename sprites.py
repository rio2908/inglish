"""Load and crop the transparent concept strips once at startup."""

from pathlib import Path

import pygame
from creature_sprites import families


ASSET_DIR = Path(__file__).resolve().parent / "assets" / "sniffer"


def _split_strip(filename, edges):
    sheet = pygame.image.load(str(ASSET_DIR / filename)).convert_alpha()
    sprites = []
    for left, right in zip(edges, edges[1:]):
        part = sheet.subsurface((left, 0, right - left, sheet.get_height())).copy()
        mask = pygame.mask.from_surface(part, 80)
        rects = mask.get_bounding_rects()
        if not rects:
            raise ValueError(f"Empty sprite in {filename}: {left}-{right}")
        largest = max(rect.width * rect.height for rect in rects)
        # The generated strips have a few disconnected pixels from a neighbour.
        rects = [rect for rect in rects if rect.width * rect.height >= largest * 0.1]
        bounds = rects[0].copy()
        for rect in rects[1:]:
            bounds.union_ip(rect)
        sprites.append(part.subsurface(bounds.inflate(4, 4).clip(part.get_rect())).copy())
    return sprites


class SnifferSprites:
    def __init__(self):
        self.growth = _split_strip("growth-grid.png", [0, 245, 535, 935, 1470, 2160])
        self.hatching = _split_strip("hatching-grid.png", [0, 390, 770, 1160, 1580, 2172])
        self.walk = _split_strip("walk-grid.png", [0, 370, 720, 1070, 1420, 1770, 2172])
        self.cache = {}
        self.species = "sniffer"
        self.families = {"sniffer": {"growth": self.growth, "hatching": self.hatching, "walk": self.walk}}

    def select_species(self, species):
        if species not in self.families:
            self.families[species] = families(species)
        self.species = species
        for family, frames in self.families[species].items():
            setattr(self, family, frames)

    def scaled(self, family, index, max_width, max_height):
        return self.scaled_species(self.species, family, index, max_width, max_height)

    def scaled_species(self, species, family, index, max_width, max_height):
        key = (species, family, index, max_width, max_height)
        if key in self.cache:
            return self.cache[key]
        if species not in self.families:
            self.families[species] = families(species)
        source = self.families[species][family][index]
        ratio = min(max_width / source.get_width(), max_height / source.get_height())
        size = (max(1, int(source.get_width() * ratio)), max(1, int(source.get_height() * ratio)))
        sprite = pygame.transform.scale(source, size)
        self.cache[key] = sprite
        return sprite
