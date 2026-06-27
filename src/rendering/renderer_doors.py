from __future__ import annotations

import math

from src.rendering.renderer_config import DOOR_VISUAL_ASPECT
from src.settings import (
    CEILING_HEIGHT_UNITS,
    DOOR_OPEN_REST_WIDTH,
    DOOR_TILES,
    WALL_TILES,
)


class RendererDoorMixin:
    def _door_visual_span(self, min_cell: int, max_cell: int) -> tuple[float, float]:
        total_span = max(1.0, max_cell - min_cell + 1.0)
        visual_span = min(total_span, max(0.18, CEILING_HEIGHT_UNITS * DOOR_VISUAL_ASPECT))
        start = min_cell + (total_span - visual_span) * 0.5
        return start, start + visual_span

    def _draw_open_doors(self, player, elapsed: float, horizon: int, depth_buffer: list[float]) -> None:
        drawn: set[frozenset[tuple[int, int]]] = set()
        groups: list[frozenset[tuple[int, int]]] = []
        for cell in sorted(self.game_map.open_doors):
            group = self.game_map.door_group_at(*cell)
            if group in drawn:
                continue
            drawn.add(group)
            groups.append(group)

        groups.sort(
            key=lambda group: sum((x + 0.5 - player.x) ** 2 + (y + 0.5 - player.y) ** 2 for x, y in group)
            / len(group),
            reverse=True,
        )

        for group in groups:
            x, y = min(group)
            tile = self.game_map.tile_at(x, y)
            texture = self.textures.for_tile(tile)
            if texture is None:
                continue
            progress = max(self.game_map.door_progress_at(cx, cy) for cx, cy in group)
            self._draw_open_door_panel(texture, tile, (x, y), progress, player, elapsed, horizon, depth_buffer)

    def _draw_open_door_panel(
        self,
        texture: pygame.Surface,
        tile: int,
        cell: tuple[int, int],
        progress: float,
        player,
        elapsed: float,
        horizon: int,
        depth_buffer: list[float],
    ) -> None:
        x, y = cell
        group = self.game_map.door_group_at(x, y)
        xs = [gx for gx, _ in group]
        ys = [gy for _, gy in group]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        progress = max(0.0, min(1.0, progress))
        eased = progress * progress * (3.0 - 2.0 * progress)
        orientation = self.game_map.door_orientation_at(x, y)

        if orientation == "horizontal":
            visual_start, visual_end = self._door_visual_span(min_x, max_x)
            visual_span = visual_end - visual_start
            rest_span = min(DOOR_OPEN_REST_WIDTH, visual_span)
            visible_width = max(rest_span, visual_span - (visual_span - rest_span) * eased)
            direction = self._door_slide_direction(x, y, axis="x")
            y_plane = min_y + 0.5
            if direction >= 0:
                start = visual_end - visible_width
                texture_start = (visual_span - visible_width) / visual_span
            else:
                start = visual_start
                texture_start = 0.0
            texture_span = visible_width / visual_span
            p0 = (start, y_plane)
            p1 = (start + visible_width, y_plane)
        else:
            visual_start, visual_end = self._door_visual_span(min_y, max_y)
            visual_span = visual_end - visual_start
            rest_span = min(DOOR_OPEN_REST_WIDTH, visual_span)
            visible_width = max(rest_span, visual_span - (visual_span - rest_span) * eased)
            direction = self._door_slide_direction(x, y, axis="y")
            x_plane = min_x + 0.5
            if direction >= 0:
                start = visual_end - visible_width
                texture_start = (visual_span - visible_width) / visual_span
            else:
                start = visual_start
                texture_start = 0.0
            texture_span = visible_width / visual_span
            p0 = (x_plane, start)
            p1 = (x_plane, start + visible_width)

        self._draw_world_panel(
            texture,
            tile,
            p0,
            p1,
            player,
            elapsed,
            horizon,
            depth_buffer,
            texture_start=texture_start,
            texture_span=texture_span,
        )

    def _door_slide_direction(self, x: int, y: int, *, axis: str) -> int:
        group = self.game_map.door_group_at(x, y)
        xs = [gx for gx, _ in group]
        ys = [gy for _, gy in group]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        if axis == "x":
            right_is_wall = any(self.game_map.tile_at(max_x + 1, gy) in WALL_TILES for gy in range(min_y, max_y + 1))
            left_is_wall = any(self.game_map.tile_at(min_x - 1, gy) in WALL_TILES for gy in range(min_y, max_y + 1))
            if right_is_wall:
                return 1
            if left_is_wall:
                return -1
            return 1

        down_is_wall = any(self.game_map.tile_at(gx, max_y + 1) in WALL_TILES for gx in range(min_x, max_x + 1))
        up_is_wall = any(self.game_map.tile_at(gx, min_y - 1) in WALL_TILES for gx in range(min_x, max_x + 1))
        if down_is_wall:
            return 1
        if up_is_wall:
            return -1
        return 1

