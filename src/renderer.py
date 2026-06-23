"""Raycasting renderer."""

from __future__ import annotations

import math

import pygame

from .asset_manager import TEXTURE_CEILING, TEXTURE_FLOOR, TextureStore
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
        self.textures = TextureStore()

    def render(self, player, elapsed: float) -> None:
        self._draw_background(player, elapsed)
        start_angle = player.angle - HALF_FOV

        for ray in range(NUM_RAYS):
            ray_angle = start_angle + ray * DELTA_ANGLE
            distance, tile, hit_x, hit_y = self._cast_ray(player.x, player.y, ray_angle)
            corrected = max(0.0001, distance * math.cos(ray_angle - player.angle))
            wall_height = min(SCREEN_HEIGHT * 1.35, DISTANCE_TO_PROJECTION / corrected)

            x = ray * SCALE
            y = HALF_HEIGHT - int(wall_height / 2)
            texture = self.textures.for_tile(tile)
            if texture is not None:
                self._draw_textured_wall(texture, x, y, wall_height, hit_x, hit_y, corrected, ray_angle, player, elapsed)
            else:
                color = self._shade_color(tile, corrected, ray_angle, player, elapsed)
                pygame.draw.rect(self.screen, color, (x, y, SCALE + 1, int(wall_height)))

    def _draw_background(self, player, elapsed: float) -> None:
        power_restored = player.flags.get("power_restored", False)
        ceiling_texture = self.textures.get(TEXTURE_CEILING)
        floor_texture = self.textures.get(TEXTURE_FLOOR)
        ceiling = (14, 20, 23) if not power_restored else (21, 27, 29)
        floor = (19, 24, 22) if not power_restored else (28, 33, 30)

        self.screen.fill(ceiling, (0, 0, SCREEN_WIDTH, HALF_HEIGHT))
        self.screen.fill(floor, (0, HALF_HEIGHT, SCREEN_WIDTH, HALF_HEIGHT))

        if ceiling_texture is not None:
            self._draw_floor_cast(ceiling_texture, player, elapsed, is_ceiling=True)

        if floor_texture is not None:
            self._draw_floor_cast(floor_texture, player, elapsed, is_ceiling=False)

    def _draw_floor_cast(self, texture: pygame.Surface, player, elapsed: float, *, is_ceiling: bool) -> None:
        texture_width, texture_height = texture.get_size()
        if texture_width <= 0 or texture_height <= 0:
            return

        sample_step = 4
        left_angle = player.angle - HALF_FOV
        right_angle = player.angle + HALF_FOV
        left_dir = (math.cos(left_angle), math.sin(left_angle))
        right_dir = (math.cos(right_angle), math.sin(right_angle))

        if is_ceiling:
            y_range = range(HALF_HEIGHT - sample_step, -1, -sample_step)
        else:
            y_range = range(HALF_HEIGHT + 1, SCREEN_HEIGHT, sample_step)

        for screen_y in y_range:
            depth_from_horizon = abs(screen_y - HALF_HEIGHT)
            if depth_from_horizon <= 0:
                continue
            row_distance = (0.5 * SCREEN_HEIGHT) / depth_from_horizon
            if row_distance > MAX_DEPTH:
                continue

            for screen_x in range(0, SCREEN_WIDTH, sample_step):
                t = screen_x / SCREEN_WIDTH
                ray_x = left_dir[0] + (right_dir[0] - left_dir[0]) * t
                ray_y = left_dir[1] + (right_dir[1] - left_dir[1]) * t
                world_x = player.x + ray_x * row_distance
                world_y = player.y + ray_y * row_distance

                texture_x = int(world_x * texture_width) % texture_width
                texture_y = int(world_y * texture_height) % texture_height
                base_color = texture.get_at((texture_x, texture_y))[:3]
                sample_angle = math.atan2(world_y - player.y, world_x - player.x)
                shade = self._shade_factor(row_distance, sample_angle, player, elapsed)
                if is_ceiling:
                    shade *= 0.82
                color = tuple(max(0, min(255, int(channel * shade))) for channel in base_color)
                rect_y = screen_y if not is_ceiling else max(0, screen_y - sample_step + 1)
                pygame.draw.rect(self.screen, color, (screen_x, rect_y, sample_step, sample_step))

    def _cast_ray(self, x: float, y: float, angle: float) -> tuple[float, int, float, float]:
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)
        distance = 0.02
        while distance < MAX_DEPTH:
            hit_x = x + cos_a * distance
            hit_y = y + sin_a * distance
            test_x = int(hit_x)
            test_y = int(hit_y)
            tile = self.game_map.tile_at(test_x, test_y)
            if self.game_map.is_solid_cell(test_x, test_y):
                return distance, tile, hit_x, hit_y
            distance += 0.025
        return MAX_DEPTH, TILE_WALL, x + cos_a * MAX_DEPTH, y + sin_a * MAX_DEPTH

    def _draw_textured_wall(
        self,
        texture: pygame.Surface,
        x: int,
        y: int,
        wall_height: float,
        hit_x: float,
        hit_y: float,
        distance: float,
        ray_angle: float,
        player,
        elapsed: float,
    ) -> None:
        texture_width, texture_height = texture.get_size()
        if texture_width <= 0 or texture_height <= 0:
            return

        texture_offset = self._texture_offset(hit_x, hit_y)
        texture_x = max(0, min(texture_width - 1, int(texture_offset * texture_width)))
        source = pygame.Rect(texture_x, 0, 1, texture_height)
        column_height = max(1, int(wall_height))
        column = texture.subsurface(source)
        column = pygame.transform.scale(column, (SCALE + 1, column_height))

        shade = self._shade_factor(distance, ray_angle, player, elapsed)
        shade_value = max(0, min(255, int(255 * min(1.0, shade))))
        column.fill((shade_value, shade_value, shade_value), special_flags=pygame.BLEND_RGB_MULT)
        if shade > 1.0:
            boost = max(0, min(70, int((shade - 1.0) * 85)))
            column.fill((boost, boost, boost), special_flags=pygame.BLEND_RGB_ADD)

        self.screen.blit(column, (x, y))

    def _texture_offset(self, hit_x: float, hit_y: float) -> float:
        x_grid_distance = abs(hit_x - round(hit_x))
        y_grid_distance = abs(hit_y - round(hit_y))
        if x_grid_distance < y_grid_distance:
            offset = hit_y - math.floor(hit_y)
        else:
            offset = hit_x - math.floor(hit_x)
        return offset % 1.0

    def _shade_color(self, tile: int, distance: float, ray_angle: float, player, elapsed: float) -> tuple[int, int, int]:
        base = WALL_COLORS.get(tile, WALL_COLORS[TILE_WALL])
        shade = self._shade_factor(distance, ray_angle, player, elapsed)
        return tuple(max(0, min(255, int(channel * shade))) for channel in base)

    def _shade_factor(self, distance: float, ray_angle: float, player, elapsed: float) -> float:
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
        return shade

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
