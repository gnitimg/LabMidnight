from __future__ import annotations

import math

import pygame

from src.settings import (
    CAMERA_HEIGHT_UNITS,
    CEILING_HEIGHT_UNITS,
    DOOR_TILES,
    MAX_DEPTH,
    RAY_NEAR_CLIP,
    SCREEN_HEIGHT,
    TILE_WALL,
    VERTICAL_PROJECTION,
    WALL_COLORS,
    WALL_TILES,
)


class RendererRaycastMixin:
    def _cast_ray(self, x: float, y: float, angle: float) -> tuple[float, int, float, float, int, tuple[int, int], float | None]:
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

        side = 0
        max_steps = (self.game_map.width + self.game_map.height) * 2
        for _ in range(max_steps):
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
            if tile in DOOR_TILES:
                door_hit = self._door_plane_hit(x, y, ray_dir_x, ray_dir_y, map_x, map_y)
                if door_hit is not None:
                    hit_distance, door_hit_x, door_hit_y, door_side, door_texture_offset, is_visual_door = door_hit
                    if self.game_map.is_open_door(map_x, map_y) and is_visual_door:
                        continue
                    projected_distance = max(RAY_NEAR_CLIP, min(MAX_DEPTH, hit_distance))
                    render_tile = tile if is_visual_door and not self.game_map.is_open_door(map_x, map_y) else TILE_WALL
                    return projected_distance, render_tile, door_hit_x, door_hit_y, door_side, (map_x, map_y), door_texture_offset
                continue

            if self.game_map.is_solid_cell(map_x, map_y):
                hit_distance = min(MAX_DEPTH, abs(distance))
                projected_distance = max(RAY_NEAR_CLIP, hit_distance)
                hit_x = x + ray_dir_x * hit_distance
                hit_y = y + ray_dir_y * hit_distance
                if side == 0:
                    hit_x = float(map_x) if step_x > 0 else float(map_x + 1)
                else:
                    hit_y = float(map_y) if step_y > 0 else float(map_y + 1)
                return projected_distance, tile, hit_x, hit_y, side, (map_x, map_y), None

            if distance >= MAX_DEPTH:
                break

        return MAX_DEPTH, TILE_WALL, x + ray_dir_x * MAX_DEPTH, y + ray_dir_y * MAX_DEPTH, side, (map_x, map_y), None

    def _door_plane_hit(
        self,
        origin_x: float,
        origin_y: float,
        ray_dir_x: float,
        ray_dir_y: float,
        cell_x: int,
        cell_y: int,
    ) -> tuple[float, float, float, int, float, bool] | None:
        group = self.game_map.door_group_at(cell_x, cell_y)
        xs = [x for x, _ in group]
        ys = [y for _, y in group]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        if self.game_map.door_orientation_at(cell_x, cell_y) == "horizontal":
            if abs(ray_dir_y) <= 1e-8:
                return None
            plane_y = min_y + 0.5
            distance = (plane_y - origin_y) / ray_dir_y
            if distance <= 1e-5:
                return None
            hit_x = origin_x + ray_dir_x * distance
            if not (min_x <= hit_x <= max_x + 1.0):
                return None
            visual_start, visual_end = self._door_visual_span(min_x, max_x)
            if visual_start <= hit_x <= visual_end:
                texture_offset = (hit_x - visual_start) / max(0.001, visual_end - visual_start)
                return abs(distance), hit_x, plane_y, 1, max(0.0, min(0.999, texture_offset)), True
            wall_offset = (hit_x - math.floor(hit_x)) % 1.0
            return abs(distance), hit_x, plane_y, 1, max(0.0, min(0.999, wall_offset)), False

        if abs(ray_dir_x) <= 1e-8:
            return None
        plane_x = min_x + 0.5
        distance = (plane_x - origin_x) / ray_dir_x
        if distance <= 1e-5:
            return None
        hit_y = origin_y + ray_dir_y * distance
        if not (min_y <= hit_y <= max_y + 1.0):
            return None
        visual_start, visual_end = self._door_visual_span(min_y, max_y)
        if visual_start <= hit_y <= visual_end:
            texture_offset = (hit_y - visual_start) / max(0.001, visual_end - visual_start)
            return abs(distance), plane_x, hit_y, 0, max(0.0, min(0.999, texture_offset)), True
        wall_offset = (hit_y - math.floor(hit_y)) % 1.0
        return abs(distance), plane_x, hit_y, 0, max(0.0, min(0.999, wall_offset)), False

    def _draw_textured_wall(
        self,
        texture: pygame.Surface,
        x: int,
        column_width: int,
        top_y: float,
        bottom_y: float,
        hit_x: float,
        hit_y: float,
        tile: int,
        side: int,
        cell: tuple[int, int],
        texture_offset: float | None,
        distance: float,
        ray_angle: float,
        player,
        elapsed: float,
    ) -> None:
        texture_width, texture_height = texture.get_size()
        if texture_width <= 0 or texture_height <= 0:
            return

        if texture_offset is None:
            texture_offset = self._texture_offset(hit_x, hit_y, tile, side, cell)
        texture_x = max(0, min(texture_width - 1, int(texture_offset * texture_width)))
        slice_info = self._visible_wall_slice(top_y, bottom_y, texture_height)
        if slice_info is None:
            return
        visible_top, visible_height, source_y, source_height = slice_info
        source = pygame.Rect(texture_x, source_y, 1, source_height)
        column = texture.subsurface(source)
        column = pygame.transform.scale(column, (column_width + 1, visible_height))

        shade = self._shade_factor(distance, ray_angle, player, elapsed) * self._wall_side_light(side)
        shade_value = max(0, min(255, int(255 * min(1.0, shade))))
        column.fill((shade_value, shade_value, shade_value), special_flags=pygame.BLEND_RGB_MULT)
        if shade > 1.0:
            boost = max(0, min(70, int((shade - 1.0) * 85)))
            column.fill((boost, boost, boost), special_flags=pygame.BLEND_RGB_ADD)

        self.screen.blit(column, (x, visible_top))

    def _texture_offset(self, hit_x: float, hit_y: float, tile: int, side: int, cell: tuple[int, int]) -> float:
        if tile in DOOR_TILES:
            group = self.game_map.door_group_at(*cell)
            if len(group) > 1:
                xs = [x for x, _ in group]
                ys = [y for _, y in group]
                min_x = min(xs)
                min_y = min(ys)
                width = max(xs) - min_x + 1
                height = max(ys) - min_y + 1
                if width >= height:
                    return max(0.0, min(0.999, (hit_x - min_x) / width))
                return max(0.0, min(0.999, (hit_y - min_y) / height))

        x_grid_distance = abs(hit_x - round(hit_x))
        y_grid_distance = abs(hit_y - round(hit_y))
        if x_grid_distance < y_grid_distance:
            offset = hit_y - math.floor(hit_y)
        else:
            offset = hit_x - math.floor(hit_x)
        return offset % 1.0

