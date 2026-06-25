"""Texture loading with stable asset names and fallback support."""

from __future__ import annotations

from pathlib import Path

import pygame

from src.resources.object_assets import OBJECT_ASSET_DIR, OBJECT_FACES, load_object_specs, object_texture_path
from src.settings import (
    TILE_CLASSROOM_DOOR,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
    TILE_WALL,
)


TEXTURE_DIR = Path("assets/textures")
TEXTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")

TEXTURE_CEILING = "ceiling"
TEXTURE_FLOOR = "floor"
TEXTURE_WALL = "wall"
TEXTURE_DOOR = "door"
TEXTURE_DOOR_LAB = "door_lab"
TEXTURE_DOOR_CLASSROOM = "door_classroom"
TEXTURE_DOOR_POWER = "door_power"
TEXTURE_DOOR_EXIT = "door_exit"

TILE_TEXTURES = {
    TILE_WALL: TEXTURE_WALL,
    TILE_GUARD_DOOR: TEXTURE_DOOR,
    TILE_LAB_DOOR: TEXTURE_DOOR_LAB,
    TILE_CLASSROOM_DOOR: TEXTURE_DOOR_CLASSROOM,
    TILE_POWER_DOOR: TEXTURE_DOOR_POWER,
    TILE_EXIT_DOOR: TEXTURE_DOOR_EXIT,
}


class TextureStore:
    def __init__(self, texture_dir: Path = TEXTURE_DIR) -> None:
        self.texture_dir = texture_dir
        self.textures: dict[str, pygame.Surface] = {}
        self.object_specs = load_object_specs()
        self.object_textures: dict[tuple[str, str], pygame.Surface] = {}
        self._load_standard_textures()
        self._load_object_textures()

    def _load_standard_textures(self) -> None:
        names = {
            TEXTURE_CEILING,
            TEXTURE_FLOOR,
            TEXTURE_WALL,
            TEXTURE_DOOR,
            TEXTURE_DOOR_LAB,
            TEXTURE_DOOR_CLASSROOM,
            TEXTURE_DOOR_POWER,
            TEXTURE_DOOR_EXIT,
        }
        for name in names:
            surface = self._load_first_existing(name)
            if surface is not None:
                self.textures[name] = surface

    def _load_first_existing(self, name: str) -> pygame.Surface | None:
        for extension in TEXTURE_EXTENSIONS:
            path = self.texture_dir / f"{name}{extension}"
            if not path.exists():
                continue
            try:
                return pygame.image.load(str(path)).convert()
            except (pygame.error, OSError):
                continue
        return None

    def get(self, name: str) -> pygame.Surface | None:
        return self.textures.get(name)

    def for_tile(self, tile: int) -> pygame.Surface | None:
        name = TILE_TEXTURES.get(tile, TEXTURE_WALL)
        return self.get(name) or self.get(TEXTURE_DOOR if "door" in name else TEXTURE_WALL)

    def _load_object_textures(self) -> None:
        for object_id in self.object_specs:
            for face in OBJECT_FACES:
                path = object_texture_path(object_id, face, OBJECT_ASSET_DIR)
                if path is None:
                    continue
                try:
                    self.object_textures[(object_id, face)] = pygame.image.load(str(path)).convert_alpha()
                except (pygame.error, OSError):
                    continue

    def for_object_face(self, object_id: str, face: str) -> pygame.Surface | None:
        return self.object_textures.get((object_id, face))
