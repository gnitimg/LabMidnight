"""Raycasting renderer."""

from __future__ import annotations

import math

import pygame

from .settings import (
    COLOR_BLACK,
    DELTA_ANGLE,
    DISTANCE_TO_PROJECTION,
    FOV,
    HALF_FOV,
    HALF_HEIGHT,
    MAX_DEPTH,
    NUM_RAYS,
    SCALE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_WALL,
    WALL_COLORS,
)


class RaycastingRenderer:
    def __init__(self, screen: pygame.Surface, game_map) -> None:
        self.screen = screen
        self.game_map = game_map

    def render(self, player, elapsed: float) -> None:
        self._draw_background(player)
        start_angle = player.angle - HALF_FOV

        for ray in range(NUM_RAYS):
            ray_angle = start_angle + ray * DELTA_ANGLE
            distance, tile = self._cast_ray(player.x, player.y, ray_angle)
            corrected = max(0.0001, distance * math.cos(ray_angle - player.angle))
            wall_height = min(SCREEN_HEIGHT * 1.35, DISTANCE_TO_PROJECTION / corrected)

            color = self._shade_color(tile, corrected, ray_angle, player, elapsed)
            x = ray * SCALE
            y = HALF_HEIGHT - int(wall_height / 2)
            pygame.draw.rect(self.screen, color, (x, y, SCALE + 1, int(wall_height)))

    def _draw_background(self, player) -> None:
        power_restored = player.flags.get("power_restored", False)
        ceiling = (14, 20, 23) if not power_restored else (21, 27, 29)
        floor = (19, 24, 22) if not power_restored else (28, 33, 30)
        self.screen.fill(ceiling, (0, 0, SCREEN_WIDTH, HALF_HEIGHT))
        self.screen.fill(floor, (0, HALF_HEIGHT, SCREEN_WIDTH, HALF_HEIGHT))

    def _cast_ray(self, x: float, y: float, angle: float) -> tuple[float, int]:
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        distance = 0.02
        while distance < MAX_DEPTH:
            test_x = int(x + cos_a * distance)
            test_y = int(y + sin_a * distance)
            tile = self.game_map.tile_at(test_x, test_y)
            if self.game_map.is_solid_cell(test_x, test_y):
                return distance, tile
            distance += 0.025
        return MAX_DEPTH, TILE_WALL

    def _shade_color(self, tile: int, distance: float, ray_angle: float, player, elapsed: float) -> tuple[int, int, int]:
        base = WALL_COLORS.get(tile, WALL_COLORS[TILE_WALL])
        power_restored = player.flags.get("power_restored", False)
        visible_distance = 7.0 if power_restored else 5.0
        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            visible_distance = 14.0 if power_restored else 12.0

        distance_shade = max(0.10, 1.0 - distance / visible_distance)
        center_offset = abs((ray_angle - player.angle + math.pi) % math.tau - math.pi)
        beam = max(0.0, 1.0 - center_offset / (FOV * 0.42))
        beam_boost = 0.55 * beam * beam if player.flashlight_on and player.flashlight_power > 0 else 0.0

        flicker = 1.0
        if player.flashlight_on and 0 < player.flashlight_power < 20:
            flicker = 0.72 + 0.28 * abs(math.sin(elapsed * 18.0))

        sanity_dark = 1.0
        if player.sanity < 40:
            sanity_dark = 0.75 + player.sanity / 160.0

        shade = min(1.25, (distance_shade + beam_boost) * flicker * sanity_dark)
        if distance > visible_distance + 2.0:
            shade *= 0.35

        return tuple(max(0, min(255, int(channel * shade))) for channel in base)

    def draw_dark_overlay(self, player) -> None:
        darkness = 0
        if not player.flashlight_on or player.flashlight_power <= 0:
            darkness += 55
        if player.sanity < 45:
            darkness += int((45 - player.sanity) * 2.2)
        darkness = max(0, min(170, darkness))
        if darkness <= 0:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*COLOR_BLACK, darkness))
        self.screen.blit(overlay, (0, 0))
