from __future__ import annotations

import math

from src.maps.map_objects import MapObject
from src.settings import (
    BUILDING_BOTTOM_FLOOR,
    DOOR_COLLISION_THICKNESS,
    DOOR_TILES,
    OBJECT_COLLISION_RADIUS,
    PLAYER_RADIUS,
    TILE_EXIT_DOOR,
    TILE_WALL,
    WALL_TILES,
)


class GameMapCollisionMixin:
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return TILE_WALL
        return self.grid[y][x]

    def is_solid_cell(self, x: int, y: int) -> bool:
        tile = self.tile_at(x, y)
        if tile in WALL_TILES:
            return True
        if self.is_ground_exit_tile(x, y):
            return False
        if tile in DOOR_TILES and not self.is_open_door(x, y):
            return True
        return False

    def can_move_to(self, x: float, y: float) -> bool:
        radius_squared = PLAYER_RADIUS * PLAYER_RADIUS
        min_x = int(x - PLAYER_RADIUS)
        max_x = int(x + PLAYER_RADIUS)
        min_y = int(y - PLAYER_RADIUS)
        max_y = int(y + PLAYER_RADIUS)

        for cell_y in range(min_y, max_y + 1):
            for cell_x in range(min_x, max_x + 1):
                tile = self.tile_at(cell_x, cell_y)
                if tile in WALL_TILES and self._collides_wall_rect(x, y, cell_x, cell_y, radius_squared):
                    return False
                if self.is_ground_exit_tile(cell_x, cell_y):
                    continue
                if tile in DOOR_TILES and not self.is_passable_door(cell_x, cell_y):
                    if self._collides_wall_rect(x, y, cell_x, cell_y, radius_squared):
                        return False
        for anchor, obj in self.objects.items():
            if anchor in self.picked_objects or not obj.solid:
                continue
            object_radius_squared = OBJECT_COLLISION_RADIUS * OBJECT_COLLISION_RADIUS
            if self._collides_object_rect(x, y, anchor, obj, object_radius_squared):
                return False
        return True

    def is_ground_exit_tile(self, x: int, y: int) -> bool:
        return self.floor == BUILDING_BOTTOM_FLOOR and self.tile_at(x, y) == TILE_EXIT_DOOR

    def reached_ground_exit(self, x: float, y: float) -> bool:
        return self.is_ground_exit_tile(int(x), int(y))

    def _collides_wall_rect(self, x: float, y: float, cell_x: int, cell_y: int, radius_squared: float) -> bool:
        closest_x = min(max(x, cell_x), cell_x + 1.0)
        closest_y = min(max(y, cell_y), cell_y + 1.0)
        dx = x - closest_x
        dy = y - closest_y
        return dx * dx + dy * dy < radius_squared

    def _collides_closed_door(self, x: float, y: float, cell_x: int, cell_y: int) -> bool:
        group = self.door_group_at(cell_x, cell_y)
        xs = [gx for gx, _ in group]
        ys = [gy for _, gy in group]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        span_padding = PLAYER_RADIUS
        half_thickness = DOOR_COLLISION_THICKNESS / 2

        if self.door_orientation_at(cell_x, cell_y) == "vertical":
            plane_x = min_x + 0.5
            within_span = (min_y - span_padding) <= y <= (max_y + 1.0 + span_padding)
            return within_span and abs(x - plane_x) <= PLAYER_RADIUS + half_thickness

        plane_y = min_y + 0.5
        within_span = (min_x - span_padding) <= x <= (max_x + 1.0 + span_padding)
        return within_span and abs(y - plane_y) <= PLAYER_RADIUS + half_thickness

    def _collides_object_rect(self, x: float, y: float, anchor: tuple[int, int], obj: MapObject, radius_squared: float) -> bool:
        min_x, min_y, max_x, max_y = self.object_bounds(anchor, obj)
        closest_x = min(max(x, min_x), max_x)
        closest_y = min(max(y, min_y), max_y)
        dx = x - closest_x
        dy = y - closest_y
        return dx * dx + dy * dy < radius_squared

    def object_bounds(self, anchor: tuple[int, int], obj: MapObject) -> tuple[float, float, float, float]:
        length, width = obj.footprint_size()
        x, y = anchor
        return float(x), float(y), float(x) + max(0.05, length), float(y) + max(0.05, width)

    def object_anchor_at(self, x: int, y: int) -> tuple[int, int] | None:
        for anchor, obj in self.objects.items():
            if anchor in self.picked_objects:
                continue
            min_x, min_y, max_x, max_y = self.object_bounds(anchor, obj)
            if min_x <= x < max_x and min_y <= y < max_y:
                return anchor
        return None

    def object_at(self, x: int, y: int) -> MapObject | None:
        anchor = self.object_anchor_at(x, y)
        if anchor is None:
            return None
        return self.objects.get(anchor)

    def remove_object(self, x: int, y: int) -> None:
        anchor = self.object_anchor_at(x, y) or (x, y)
        self.picked_objects.add(anchor)

    def region_at(self, x: float, y: float) -> str:
        ix, iy = int(x), int(y)
        if 1 <= ix <= 8 and 1 <= iy <= 5:
            return "lab"
        if 18 <= ix <= 30 and 1 <= iy <= 5:
            return "classroom"
        if 1 <= ix <= 7 and 10 <= iy <= 14:
            return "security"
        if 10 <= ix <= 16 and 10 <= iy <= 14:
            return "power"
        if 19 <= ix <= 24 and 10 <= iy <= 14:
            return "server"
        if 27 <= ix <= 32 and 10 <= iy <= 14:
            return "exit"
        return "corridor"
