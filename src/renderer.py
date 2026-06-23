"""Raycasting renderer."""

from __future__ import annotations

import math

import pygame

try:
    import numpy as np
except ImportError:  # pragma: no cover - fallback path for minimal installs.
    np = None

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
    RAY_NEAR_CLIP,
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
        self._mapped_texture_cache: dict[int, tuple[int, int, list[list[int]]]] = {}
        self._texture_mip_cache: dict[int, list] = {}
        self._ceiling_surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._perspective_surface_cache: dict[tuple[str, int, int], pygame.Surface] = {}
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

    def render(self, player, elapsed: float) -> None:
        horizon = self._horizon(player)
        self._draw_background(player, elapsed, horizon)
        start_angle = player.angle - HALF_FOV

        for ray in range(NUM_RAYS):
            ray_angle = start_angle + ray * DELTA_ANGLE
            distance, tile, hit_x, hit_y = self._cast_ray(player.x, player.y, ray_angle)
            corrected = max(0.0001, distance * math.cos(ray_angle - player.angle))
            wall_height = min(SCREEN_HEIGHT * 4.0, DISTANCE_TO_PROJECTION / corrected)

            x = ray * SCALE
            y = horizon - int(wall_height / 2)
            texture = self.textures.for_tile(tile)
            if texture is not None:
                self._draw_textured_wall(texture, x, y, wall_height, hit_x, hit_y, corrected, ray_angle, player, elapsed)
            else:
                color = self._shade_color(tile, corrected, ray_angle, player, elapsed)
                pygame.draw.rect(self.screen, color, (x, y, SCALE + 1, int(wall_height)))

    def _horizon(self, player) -> int:
        return int(HALF_HEIGHT + player.pitch_offset)

    def _draw_background(self, player, elapsed: float, horizon: int) -> None:
        power_restored = player.flags.get("power_restored", False)
        ceiling_texture = self.textures.get(TEXTURE_CEILING)
        floor_texture = self.textures.get(TEXTURE_FLOOR)
        ceiling = (14, 20, 23) if not power_restored else (21, 27, 29)
        floor = (19, 24, 22) if not power_restored else (28, 33, 30)

        ceiling_height = max(0, min(SCREEN_HEIGHT, horizon))
        floor_top = max(0, min(SCREEN_HEIGHT, horizon))
        if ceiling_height > 0:
            self.screen.fill(ceiling, (0, 0, SCREEN_WIDTH, ceiling_height))
        if floor_top < SCREEN_HEIGHT:
            self.screen.fill(floor, (0, floor_top, SCREEN_WIDTH, SCREEN_HEIGHT - floor_top))

        if ceiling_texture is not None:
            self._draw_floor_cast(ceiling_texture, player, elapsed, is_ceiling=True, horizon=horizon)

        if floor_texture is not None:
            self._draw_floor_cast(floor_texture, player, elapsed, is_ceiling=False, horizon=horizon)

    def _draw_ceiling_texture(self, texture: pygame.Surface, player) -> None:
        darkness = 165 if not player.flags.get("power_restored", False) else 130
        cache_key = (id(texture), darkness)
        cached = self._ceiling_surface_cache.get(cache_key)
        if cached is not None:
            self.screen.blit(cached, (0, 0))
            return

        target_width = max(1, SCREEN_WIDTH // 2)
        target_height = max(1, HALF_HEIGHT // 2)
        scaled = pygame.transform.smoothscale(texture, (target_width, target_height))
        tiled = pygame.Surface((SCREEN_WIDTH, HALF_HEIGHT)).convert()
        for y in range(0, HALF_HEIGHT, target_height):
            for x in range(0, SCREEN_WIDTH, target_width):
                tiled.blit(scaled, (x, y))
        tiled.fill((darkness, darkness, darkness), special_flags=pygame.BLEND_RGB_MULT)
        self._ceiling_surface_cache[cache_key] = tiled
        self.screen.blit(tiled, (0, 0))

    def _draw_floor_cast(self, texture: pygame.Surface, player, elapsed: float, *, is_ceiling: bool, horizon: int) -> None:
        if np is not None:
            self._draw_floor_cast_numpy(texture, player, elapsed, is_ceiling=is_ceiling, horizon=horizon)
            return
        self._draw_floor_cast_scaled(texture, player, elapsed, is_ceiling=is_ceiling)

    def _draw_floor_cast_numpy(self, texture: pygame.Surface, player, elapsed: float, *, is_ceiling: bool, horizon: int) -> None:
        mips = self._texture_mips(texture)
        if not mips:
            return

        target_top, target_height = self._plane_target_rect(horizon, is_ceiling)
        if target_height <= 0:
            return
        sample_width = self.ceiling_perspective_width if is_ceiling else self.floor_perspective_width
        quality = self.ceiling_perspective_quality if is_ceiling else self.floor_perspective_quality
        sample_height = max(1, int(target_height * quality))
        sample_surface = self._perspective_surface("ceiling" if is_ceiling else "floor", sample_width, sample_height)
        xs = self._ceiling_xs if is_ceiling else self._floor_xs
        if xs is None:
            return

        if is_ceiling:
            screen_rows = np.linspace(target_top, target_top + target_height - 1, sample_height, dtype=np.float32)
        else:
            screen_rows = np.linspace(target_top, target_top + target_height - 1, sample_height, dtype=np.float32)

        depth_from_horizon = np.maximum(1.0, np.abs(screen_rows - horizon))
        row_distance = np.minimum((0.5 * SCREEN_HEIGHT) / depth_from_horizon, MAX_DEPTH).astype(np.float32)

        left_angle = player.angle - HALF_FOV
        right_angle = player.angle + HALF_FOV
        ray_dir_x0 = math.cos(left_angle)
        ray_dir_y0 = math.sin(left_angle)
        ray_dir_x1 = math.cos(right_angle)
        ray_dir_y1 = math.sin(right_angle)

        step_x = row_distance * (ray_dir_x1 - ray_dir_x0) / sample_width
        step_y = row_distance * (ray_dir_y1 - ray_dir_y0) / sample_width
        start_x = player.x + row_distance * ray_dir_x0
        start_y = player.y + row_distance * ray_dir_y0

        output = np.empty((sample_height, sample_width, 3), dtype=np.uint8)
        mip_indices = np.zeros(sample_height, dtype=np.int32)
        mip_indices[row_distance > 2.8] = 1
        mip_indices[row_distance > 6.5] = 2
        mip_indices[row_distance > 12.0] = 3

        for mip_index, texture_array in enumerate(mips):
            row_indices = np.where(mip_indices == mip_index)[0]
            if row_indices.size == 0:
                continue
            texture_width, texture_height = texture_array.shape[0], texture_array.shape[1]
            world_x = start_x[row_indices, None] + step_x[row_indices, None] * xs[None, :]
            world_y = start_y[row_indices, None] + step_y[row_indices, None] * xs[None, :]
            texture_x = np.mod((world_x * texture_width).astype(np.int32), texture_width)
            texture_y = np.mod((world_y * texture_height).astype(np.int32), texture_height)
            output[row_indices, :, :] = texture_array[texture_x, texture_y]

        light = self._floor_light(row_distance, player, is_ceiling=is_ceiling, sample_width=sample_width, xs=xs)
        output = np.clip(output.astype(np.float32) * light[:, :, None], 0, 255).astype(np.uint8)
        pygame.surfarray.blit_array(sample_surface, np.swapaxes(output, 0, 1))
        scaled = pygame.transform.scale(sample_surface, (SCREEN_WIDTH, target_height))
        self.screen.blit(scaled, (0, target_top))

    def _plane_target_rect(self, horizon: int, is_ceiling: bool) -> tuple[int, int]:
        if is_ceiling:
            target_top = 0
            target_bottom = max(0, min(SCREEN_HEIGHT, horizon))
        else:
            target_top = max(0, min(SCREEN_HEIGHT, horizon))
            target_bottom = SCREEN_HEIGHT
        return target_top, max(0, target_bottom - target_top)

    def _perspective_surface(self, key: str, width: int, height: int) -> pygame.Surface:
        cache_key = (key, width, height)
        surface = self._perspective_surface_cache.get(cache_key)
        if surface is None:
            surface = pygame.Surface((width, height)).convert()
            self._perspective_surface_cache[cache_key] = surface
        return surface

    def _texture_mips(self, texture: pygame.Surface) -> list:
        cache_key = id(texture)
        cached = self._texture_mip_cache.get(cache_key)
        if cached is not None:
            return cached
        if np is None:
            return []

        surfaces = [texture.convert()]
        width, height = texture.get_size()
        for divisor in (2, 4, 8):
            mip_width = max(1, width // divisor)
            mip_height = max(1, height // divisor)
            surfaces.append(pygame.transform.smoothscale(texture, (mip_width, mip_height)).convert())

        arrays = [pygame.surfarray.array3d(surface).astype(np.uint8) for surface in surfaces]
        self._texture_mip_cache[cache_key] = arrays
        return arrays

    def _floor_light(self, row_distance, player, *, is_ceiling: bool, sample_width: int, xs):
        power_restored = player.flags.get("power_restored", False)
        visible_distance = 7.0 if power_restored else 5.0
        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            visible_distance = 14.0 if power_restored else 12.0

        base_strength = 0.34 if power_restored else 0.26
        falloff = np.clip(1.0 - row_distance / visible_distance, 0.0, 1.0)
        row_light = 0.06 + base_strength * falloff

        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            beam_profile = np.clip(1.0 - np.abs(xs - sample_width / 2) / (sample_width * 0.34), 0.0, 1.0) ** 2
            beam_distance = np.clip(1.0 - row_distance / visible_distance, 0.0, 1.0) ** 0.7
            light = row_light[:, None] + 0.58 * beam_distance[:, None] * beam_profile[None, :]
        else:
            light = np.repeat(row_light[:, None], sample_width, axis=1)

        if is_ceiling:
            light *= 0.46
        if player.sanity < 40:
            light *= 0.75 + player.sanity / 160.0
        return np.clip(light, 0.04, 0.90)

    def _draw_floor_cast_scaled(self, texture: pygame.Surface, player, elapsed: float, *, is_ceiling: bool) -> None:
        texture_width, texture_height, texture_pixels = self._mapped_texture(texture)
        if texture_width <= 0 or texture_height <= 0:
            return

        sample_surface = self.ceiling_sample_surface if is_ceiling else self.floor_sample_surface
        sample_width = self.floor_sample_width
        sample_height = self.floor_sample_height
        sample_surface.fill((0, 0, 0))

        left_angle = player.angle - HALF_FOV
        right_angle = player.angle + HALF_FOV
        ray_dir_x0 = math.cos(left_angle)
        ray_dir_y0 = math.sin(left_angle)
        ray_dir_x1 = math.cos(right_angle)
        ray_dir_y1 = math.sin(right_angle)

        pixel_sample = pygame.PixelArray(sample_surface)
        try:
            for sample_y in range(sample_height):
                if is_ceiling:
                    screen_y = HALF_HEIGHT - 1 - sample_y * self.floor_quality_scale
                else:
                    screen_y = HALF_HEIGHT + 1 + sample_y * self.floor_quality_scale

                depth_from_horizon = abs(screen_y - HALF_HEIGHT)
                if depth_from_horizon <= 0:
                    continue
                row_distance = (0.5 * SCREEN_HEIGHT) / depth_from_horizon
                row_distance = min(row_distance, MAX_DEPTH)

                step_x = row_distance * (ray_dir_x1 - ray_dir_x0) / sample_width
                step_y = row_distance * (ray_dir_y1 - ray_dir_y0) / sample_width
                world_x = player.x + row_distance * ray_dir_x0
                world_y = player.y + row_distance * ray_dir_y0

                for sample_x in range(sample_width):
                    texture_x = int(world_x * texture_width) % texture_width
                    texture_y = int(world_y * texture_height) % texture_height
                    pixel_sample[sample_x, sample_y] = texture_pixels[texture_y][texture_x]
                    world_x += step_x
                    world_y += step_y
        finally:
            del pixel_sample

        scaled = pygame.transform.smoothscale(sample_surface, (SCREEN_WIDTH, HALF_HEIGHT))
        self.screen.blit(scaled, (0, 0 if is_ceiling else HALF_HEIGHT))
        self._draw_floor_depth_haze(player, is_ceiling=is_ceiling)

    def _mapped_texture(self, texture: pygame.Surface) -> tuple[int, int, list[list[int]]]:
        cache_key = id(texture)
        cached = self._mapped_texture_cache.get(cache_key)
        if cached is not None:
            return cached
        texture_width, texture_height = texture.get_size()
        pixels: list[list[int]] = []
        for y in range(texture_height):
            row: list[int] = []
            for x in range(texture_width):
                row.append(self.screen.map_rgb(texture.get_at((x, y))[:3]))
            pixels.append(row)
        cached = (texture_width, texture_height, pixels)
        self._mapped_texture_cache[cache_key] = cached
        return cached

    def _draw_floor_depth_haze(self, player, *, is_ceiling: bool) -> None:
        power_restored = player.flags.get("power_restored", False)
        visible_distance = 7.0 if power_restored else 5.0
        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            visible_distance = 14.0 if power_restored else 12.0

        overlay_height = HALF_HEIGHT
        overlay = pygame.Surface((SCREEN_WIDTH, overlay_height), pygame.SRCALPHA)
        for local_y in range(overlay_height):
            screen_y = local_y if is_ceiling else HALF_HEIGHT + local_y
            depth_from_horizon = max(1, abs(screen_y - HALF_HEIGHT))
            row_distance = (0.5 * SCREEN_HEIGHT) / depth_from_horizon
            if row_distance <= 1.2:
                alpha = 0
            else:
                alpha = int(max(0, min(185, (row_distance / visible_distance) * 150)))
            if is_ceiling:
                alpha = min(205, alpha + 22)
            if alpha > 0:
                pygame.draw.line(overlay, (0, 0, 0, alpha), (0, local_y), (SCREEN_WIDTH, local_y))
        self.screen.blit(overlay, (0, 0 if is_ceiling else HALF_HEIGHT))

    def _cast_ray(self, x: float, y: float, angle: float) -> tuple[float, int, float, float]:
        ray_dir_x = math.cos(angle)
        ray_dir_y = math.sin(angle)
        map_x = int(x)
        map_y = int(y)

        delta_dist_x = abs(1.0 / ray_dir_x) if abs(ray_dir_x) > 1e-8 else 1e30
        delta_dist_y = abs(1.0 / ray_dir_y) if abs(ray_dir_y) > 1e-8 else 1e30

        if ray_dir_x < 0:
            step_x = -1
            side_dist_x = (x - map_x) * delta_dist_x
        else:
            step_x = 1
            side_dist_x = (map_x + 1.0 - x) * delta_dist_x

        if ray_dir_y < 0:
            step_y = -1
            side_dist_y = (y - map_y) * delta_dist_y
        else:
            step_y = 1
            side_dist_y = (map_y + 1.0 - y) * delta_dist_y

        distance = MAX_DEPTH
        side = 0
        tile = TILE_WALL
        while distance < MAX_DEPTH or (map_x == int(x) and map_y == int(y)):
            if side_dist_x < side_dist_y:
                side_dist_x += delta_dist_x
                map_x += step_x
                side = 0
                distance = (map_x - x + (1 - step_x) / 2) / ray_dir_x if abs(ray_dir_x) > 1e-8 else MAX_DEPTH
            else:
                side_dist_y += delta_dist_y
                map_y += step_y
                side = 1
                distance = (map_y - y + (1 - step_y) / 2) / ray_dir_y if abs(ray_dir_y) > 1e-8 else MAX_DEPTH

            tile = self.game_map.tile_at(map_x, map_y)
            if self.game_map.is_solid_cell(map_x, map_y):
                distance = max(RAY_NEAR_CLIP, min(MAX_DEPTH, abs(distance)))
                hit_x = x + ray_dir_x * distance
                hit_y = y + ray_dir_y * distance
                if side == 0:
                    hit_x = float(map_x) if step_x > 0 else float(map_x + 1)
                else:
                    hit_y = float(map_y) if step_y > 0 else float(map_y + 1)
                return distance, tile, hit_x, hit_y

            if distance >= MAX_DEPTH:
                break

        return MAX_DEPTH, TILE_WALL, x + ray_dir_x * MAX_DEPTH, y + ray_dir_y * MAX_DEPTH

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
