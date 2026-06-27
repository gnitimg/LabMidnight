from __future__ import annotations

import math

import pygame

from src.settings import (
    COLOR_BLACK,
    FOV,
    HALF_HEIGHT,
    HALF_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_WALL,
    WALL_COLORS,
)


class RendererLightingMixin:
    def _cut_flashlight_beam(self, overlay: pygame.Surface, player, elapsed: float, darkness: int) -> None:
        if darkness <= 0 or not player.flashlight_on or player.flashlight_power <= 0 or not player.has_item("flashlight"):
            return

        flicker = 1.0
        if player.flashlight_power < 20:
            flicker = 0.72 + 0.28 * abs(math.sin(elapsed * 18.0))

        strength = max(0.28, min(1.0, player.flashlight_power / 100.0)) * flicker
        cutout = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        cx, cy = HALF_WIDTH, HALF_HEIGHT

        core = int(darkness * 0.55 * strength)
        for layer in range(32, 0, -1):
            t = layer / 32.0
            rx = int(48 + 265 * t)
            ry = int(34 + 176 * t)
            alpha = int(core * (1.0 - t) ** 1.8)
            if alpha <= 0:
                continue
            pygame.draw.ellipse(cutout, (0, 0, 0, alpha), pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2))

        overlay.blit(cutout, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

    def _shade_color(self, tile: int, distance: float, ray_angle: float, player, elapsed: float, side: int) -> tuple[int, int, int]:
        base = WALL_COLORS.get(tile, WALL_COLORS[TILE_WALL])
        shade = self._shade_factor(distance, ray_angle, player, elapsed) * self._wall_side_light(side)
        return tuple(max(0, min(255, int(channel * shade))) for channel in base)

    def _wall_side_light(self, side: int) -> float:
        return 0.78 if side == 1 else 0.94

    def _shade_factor(self, distance: float, ray_angle: float, player, elapsed: float) -> float:
        power_restored = player.flags.get("power_restored", False)
        visible_distance = 9.0 if power_restored else 6.5
        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            visible_distance = 30.0 if power_restored else 26.0

        distance_shade = max(0.10, 1.0 - distance / visible_distance)
        center_offset = abs((ray_angle - self._player_view_angle(player) + math.pi) % math.tau - math.pi)
        beam = max(0.0, 1.0 - center_offset / (FOV * 0.42))
        beam_boost = 0.08 * beam * beam if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight") else 0.0

        flicker = 1.0
        if player.flashlight_on and 0 < player.flashlight_power < 20:
            flicker = 0.72 + 0.28 * abs(math.sin(elapsed * 18.0))

        sanity_dark = 1.0
        if player.sanity < 40:
            sanity_dark = 0.75 + player.sanity / 160.0

        shade = min(1.25, (distance_shade + beam_boost) * flicker * sanity_dark)
        if distance > visible_distance + 2.0:
            shade *= 0.35
        return shade

    def draw_dark_overlay(self, player, elapsed: float = 0.0) -> None:
        flashlight_active = player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight")
        darkness = 38 if flashlight_active else 55
        if player.sanity < 45:
            darkness += int((45 - player.sanity) * 2.2)
        darkness = max(0, min(170, darkness))
        if darkness <= 0:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*COLOR_BLACK, darkness))
        self._cut_flashlight_beam(overlay, player, elapsed, darkness)
        self.screen.blit(overlay, (0, 0))
