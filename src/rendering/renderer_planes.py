from __future__ import annotations

import math

import pygame

try:
    import numpy as np
except ImportError:  # pragma: no cover - fallback path for minimal installs.
    np = None

from src.resources.asset_manager import TEXTURE_CEILING, TEXTURE_FLOOR
from src.settings import (
    CAMERA_HEIGHT_UNITS,
    CEILING_HEIGHT_UNITS,
    CEILING_TEXTURE_TILE_SPAN,
    HALF_HEIGHT,
    HALF_WIDTH,
    MAX_DEPTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    VERTICAL_PROJECTION,
)


class RendererPlaneMixin:
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
        self._draw_floor_cast_scaled(texture, player, elapsed, is_ceiling=is_ceiling, horizon=horizon)

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

        screen_rows = np.linspace(target_top, target_top + target_height - 1, sample_height, dtype=np.float32)
        forward_x, forward_y, forward_z, right_x, right_y, up_x, up_y = self._view_basis(player)
        up_z = math.cos(self._player_view_pitch(player))
        vertical_offsets = (HALF_HEIGHT - screen_rows) / VERTICAL_PROJECTION
        ray_z = forward_z + vertical_offsets * up_z
        plane_delta = CEILING_HEIGHT_UNITS - CAMERA_HEIGHT_UNITS if is_ceiling else -CAMERA_HEIGHT_UNITS
        valid_rows = np.abs(ray_z) > 1e-6
        ray_scale = np.zeros(sample_height, dtype=np.float32)
        ray_scale[valid_rows] = (plane_delta / ray_z[valid_rows]).astype(np.float32)
        valid_rows &= ray_scale > 0

        base_x = (forward_x + vertical_offsets * up_x).astype(np.float32)
        base_y = (forward_y + vertical_offsets * up_y).astype(np.float32)
        raw_distance = np.hypot(base_x * ray_scale, base_y * ray_scale).astype(np.float32)
        distance_scale = np.ones(sample_height, dtype=np.float32)
        far_rows = raw_distance > MAX_DEPTH
        distance_scale[far_rows] = MAX_DEPTH / np.maximum(raw_distance[far_rows], 1e-6)
        effective_ray_scale = ray_scale * distance_scale
        row_distance = np.minimum(raw_distance, MAX_DEPTH).astype(np.float32)
        row_distance[~valid_rows] = MAX_DEPTH

        horizontal_offsets = ((xs + 0.5) * SCREEN_WIDTH / sample_width - HALF_WIDTH) / VERTICAL_PROJECTION

        output = np.zeros((sample_height, sample_width, 3), dtype=np.uint8)
        mip_indices = np.zeros(sample_height, dtype=np.int32)
        mip_indices[row_distance > 2.8] = 1
        mip_indices[row_distance > 6.5] = 2
        mip_indices[row_distance > 12.0] = 3

        for mip_index, texture_array in enumerate(mips):
            row_indices = np.where((mip_indices == mip_index) & valid_rows)[0]
            if row_indices.size == 0:
                continue
            texture_width, texture_height = texture_array.shape[0], texture_array.shape[1]
            ray_x = base_x[row_indices, None] + horizontal_offsets[None, :] * right_x
            ray_y = base_y[row_indices, None] + horizontal_offsets[None, :] * right_y
            world_x = player.x + effective_ray_scale[row_indices, None] * ray_x
            world_y = player.y + effective_ray_scale[row_indices, None] * ray_y
            texture_span = CEILING_TEXTURE_TILE_SPAN if is_ceiling else 1.0
            texture_x = np.mod((world_x / texture_span * texture_width).astype(np.int32), texture_width)
            texture_y = np.mod((world_y / texture_span * texture_height).astype(np.int32), texture_height)
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
        visible_distance = 9.0 if power_restored else 6.5
        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            visible_distance = 30.0 if power_restored else 26.0

        base_strength = 0.34 if power_restored else 0.26
        falloff = np.clip(1.0 - row_distance / visible_distance, 0.0, 1.0)
        row_light = 0.06 + base_strength * falloff

        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            beam_profile = np.clip(1.0 - np.abs(xs - sample_width / 2) / (sample_width * 0.34), 0.0, 1.0) ** 2
            beam_distance = np.clip(1.0 - row_distance / visible_distance, 0.0, 1.0) ** 0.7
            light = row_light[:, None] + 0.14 * beam_distance[:, None] * beam_profile[None, :]
        else:
            light = np.repeat(row_light[:, None], sample_width, axis=1)

        if is_ceiling:
            light *= 0.46
        if player.sanity < 40:
            light *= 0.75 + player.sanity / 160.0
        return np.clip(light, 0.04, 0.90)

    def _draw_floor_cast_scaled(self, texture: pygame.Surface, player, elapsed: float, *, is_ceiling: bool, horizon: int) -> None:
        texture_width, texture_height, texture_pixels = self._mapped_texture(texture)
        if texture_width <= 0 or texture_height <= 0:
            return

        target_top, target_height = self._plane_target_rect(horizon, is_ceiling)
        if target_height <= 0:
            return
        sample_surface = self.ceiling_sample_surface if is_ceiling else self.floor_sample_surface
        sample_width = self.floor_sample_width
        sample_height = self.floor_sample_height
        sample_surface.fill((0, 0, 0))

        forward_x, forward_y, forward_z, right_x, right_y, up_x, up_y = self._view_basis(player)
        up_z = math.cos(self._player_view_pitch(player))
        plane_delta = CEILING_HEIGHT_UNITS - CAMERA_HEIGHT_UNITS if is_ceiling else -CAMERA_HEIGHT_UNITS

        pixel_sample = pygame.PixelArray(sample_surface)
        try:
            for sample_y in range(sample_height):
                screen_y = target_top + sample_y * target_height / max(1, sample_height - 1)
                vertical_offset = (HALF_HEIGHT - screen_y) / VERTICAL_PROJECTION
                ray_z = forward_z + vertical_offset * up_z
                if abs(ray_z) <= 1e-6:
                    continue
                ray_scale = plane_delta / ray_z
                if ray_scale <= 0:
                    continue
                base_x = forward_x + vertical_offset * up_x
                base_y = forward_y + vertical_offset * up_y
                raw_distance = math.hypot(base_x * ray_scale, base_y * ray_scale)
                if raw_distance > MAX_DEPTH:
                    ray_scale *= MAX_DEPTH / max(raw_distance, 1e-6)
                texture_span = CEILING_TEXTURE_TILE_SPAN if is_ceiling else 1.0

                for sample_x in range(sample_width):
                    screen_x = (sample_x + 0.5) * SCREEN_WIDTH / sample_width
                    horizontal_offset = (screen_x - HALF_WIDTH) / VERTICAL_PROJECTION
                    ray_x = base_x + horizontal_offset * right_x
                    ray_y = base_y + horizontal_offset * right_y
                    world_x = player.x + ray_scale * ray_x
                    world_y = player.y + ray_scale * ray_y
                    texture_x = int(world_x / texture_span * texture_width) % texture_width
                    texture_y = int(world_y / texture_span * texture_height) % texture_height
                    pixel_sample[sample_x, sample_y] = texture_pixels[texture_y][texture_x]
        finally:
            del pixel_sample

        scaled = pygame.transform.smoothscale(sample_surface, (SCREEN_WIDTH, target_height))
        self.screen.blit(scaled, (0, target_top))
        self._draw_floor_depth_haze(player, is_ceiling=is_ceiling, horizon=horizon, target_top=target_top, target_height=target_height)

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

    def _draw_floor_depth_haze(self, player, *, is_ceiling: bool, horizon: int, target_top: int, target_height: int) -> None:
        power_restored = player.flags.get("power_restored", False)
        visible_distance = 9.0 if power_restored else 6.5
        if player.flashlight_on and player.flashlight_power > 0 and player.has_item("flashlight"):
            visible_distance = 30.0 if power_restored else 26.0

        overlay_height = target_height
        overlay = pygame.Surface((SCREEN_WIDTH, overlay_height), pygame.SRCALPHA)
        for local_y in range(overlay_height):
            screen_y = target_top + local_y
            row_hit = self._plane_row_hit(player, screen_y, is_ceiling=is_ceiling)
            if row_hit is None:
                continue
            ray_scale, base_x, base_y = row_hit
            row_distance = min(MAX_DEPTH, math.hypot(base_x * ray_scale, base_y * ray_scale))
            if row_distance <= 1.2:
                alpha = 0
            else:
                alpha = int(max(0, min(185, (row_distance / visible_distance) * 150)))
            if is_ceiling:
                alpha = min(205, alpha + 22)
            if alpha > 0:
                pygame.draw.line(overlay, (0, 0, 0, alpha), (0, local_y), (SCREEN_WIDTH, local_y))
        self.screen.blit(overlay, (0, target_top))


