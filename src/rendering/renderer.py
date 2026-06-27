"""Raycasting renderer."""

from __future__ import annotations

import math

import pygame

try:
    import numpy as np
except ImportError:  # pragma: no cover - fallback path for minimal installs.
    np = None

from src.resources.asset_manager import TEXTURE_CEILING, TEXTURE_ELEVATOR, TEXTURE_FLOOR, TextureStore
from src.settings import (
    CAMERA_HEIGHT_UNITS,
    CEILING_HEIGHT_UNITS,
    CEILING_TEXTURE_TILE_SPAN,
    COLOR_BLACK,
    DELTA_ANGLE,
    DOOR_PANEL_NEAR_CLIP,
    DOOR_OPEN_REST_WIDTH,
    DOOR_TILES,
    FOV,
    HALF_FOV,
    HALF_HEIGHT,
    HALF_WIDTH,
    MAX_DEPTH,
    NUM_RAYS,
    RAY_NEAR_CLIP,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_WALL,
    VERTICAL_UNITS_PER_TILE,
    VERTICAL_PROJECTION,
    WALL_COLORS,
    WALL_TILES,
)


from src.rendering.renderer_doors import RendererDoorMixin
from src.rendering.renderer_lighting import RendererLightingMixin
from src.rendering.renderer_objects import RendererObjectMixin
from src.rendering.renderer_planes import RendererPlaneMixin
from src.rendering.renderer_projection import RendererProjectionMixin
from src.rendering.renderer_raycast import RendererRaycastMixin


class RaycastingRenderer(
    RendererPlaneMixin,
    RendererRaycastMixin,
    RendererObjectMixin,
    RendererDoorMixin,
    RendererLightingMixin,
    RendererProjectionMixin,
):
    def __init__(self, screen: pygame.Surface, game_map) -> None:
        self.screen = screen
        self.game_map = game_map
        self.textures = TextureStore()
        self._mapped_texture_cache: dict[int, tuple[int, int, list[list[int]]]] = {}
        self._texture_mip_cache: dict[int, list] = {}
        self._ceiling_surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._perspective_surface_cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._fallback_object_texture_cache: dict[tuple[str, str], pygame.Surface] = {}
        self.floor_quality_scale = 2
        self.floor_sample_width = SCREEN_WIDTH // self.floor_quality_scale
        self.floor_sample_height = HALF_HEIGHT // self.floor_quality_scale
        self.floor_sample_surface = pygame.Surface((self.floor_sample_width, self.floor_sample_height)).convert()
        self.ceiling_sample_surface = pygame.Surface((self.floor_sample_width, self.floor_sample_height)).convert()
        self.render_quality = ""
        self.set_quality("balanced")

    def set_quality(self, quality: str) -> None:
        presets = {
            "performance": (0.40, 0.25),
            "balanced": (0.52, 0.45),
            "sharp": (0.75, 0.75),
        }
        self.render_quality = quality if quality in presets else "balanced"
        self.floor_perspective_quality, self.ceiling_perspective_quality = presets[self.render_quality]
        self.floor_perspective_width = max(1, int(SCREEN_WIDTH * self.floor_perspective_quality))
        self.floor_perspective_height = max(1, int(HALF_HEIGHT * self.floor_perspective_quality))
        self.ceiling_perspective_width = max(1, int(SCREEN_WIDTH * self.ceiling_perspective_quality))
        self.ceiling_perspective_height = max(1, int(HALF_HEIGHT * self.ceiling_perspective_quality))
        self.floor_full_surface = pygame.Surface((self.floor_perspective_width, self.floor_perspective_height)).convert()
        self.ceiling_full_surface = pygame.Surface((self.ceiling_perspective_width, self.ceiling_perspective_height)).convert()
        self._floor_xs = np.arange(self.floor_perspective_width, dtype=np.float32) if np is not None else None
        self._ceiling_xs = np.arange(self.ceiling_perspective_width, dtype=np.float32) if np is not None else None
        self._perspective_surface_cache.clear()

    def cycle_quality(self) -> str:
        order = ("performance", "balanced", "sharp")
        next_quality = order[(order.index(self.render_quality) + 1) % len(order)]
        self.set_quality(next_quality)
        return next_quality

    def render(self, player, elapsed: float, dynamic_entities=None) -> None:
        self._dynamic_health_bars = []
        horizon = self._horizon(player)
        self._draw_background(player, elapsed, horizon)
        view_angle = self._player_view_angle(player)
        start_angle = view_angle - HALF_FOV
        depth_buffer = [MAX_DEPTH] * NUM_RAYS

        for ray in range(NUM_RAYS):
            ray_angle = start_angle + ray * DELTA_ANGLE
            distance, tile, hit_x, hit_y, side, cell, texture_offset = self._cast_ray(player.x, player.y, ray_angle)
            corrected = max(0.0001, distance * math.cos(ray_angle - view_angle))
            depth_buffer[ray] = corrected
            ceiling_delta = CEILING_HEIGHT_UNITS - CAMERA_HEIGHT_UNITS
            top_y = horizon - VERTICAL_PROJECTION * ceiling_delta / corrected
            bottom_y = horizon + VERTICAL_PROJECTION * CAMERA_HEIGHT_UNITS / corrected

            x = int(ray * SCREEN_WIDTH / NUM_RAYS)
            next_x = int((ray + 1) * SCREEN_WIDTH / NUM_RAYS)
            column_width = max(1, next_x - x)
            texture = self.textures.for_tile(tile)
            if texture is not None:
                self._draw_textured_wall(texture, x, column_width, top_y, bottom_y, hit_x, hit_y, tile, side, cell, texture_offset, corrected, ray_angle, player, elapsed)
            else:
                span = self._visible_wall_span(top_y, bottom_y)
                if span is not None:
                    visible_top, visible_height = span
                    color = self._shade_color(tile, corrected, ray_angle, player, elapsed, side)
                    pygame.draw.rect(self.screen, color, (x, visible_top, column_width + 1, visible_height))

        self._draw_objects(player, elapsed, horizon, depth_buffer)
        self._draw_dynamic_entities(player, elapsed, horizon, depth_buffer, dynamic_entities)
        self._draw_open_doors(player, elapsed, horizon, depth_buffer)
