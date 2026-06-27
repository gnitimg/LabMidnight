from __future__ import annotations

import math
from typing import Iterable

from src.maps.map_objects import MapObject
from src.settings import DOOR_TILES, OBJECT_COLLISION_RADIUS, TILE_EMPTY, TILE_EXIT_DOOR, WALL_TILES


class GameMapSpawnMixin:
    def entry_spawn_pose(self, entry_kind: str, source_cell: tuple[int, int] | None = None) -> tuple[float, float, float] | None:
        entry_kind = entry_kind.strip().lower()
        if entry_kind == "exit":
            return self._door_entry_spawn_pose(TILE_EXIT_DOOR, source_cell)
        if entry_kind == "elevator":
            return self._object_entry_spawn_pose({"elevator"}, source_cell)
        return None

    def exit_spawn_pose(self) -> tuple[float, float, float]:
        if self.has_explicit_start_position:
            return self.start_position[0], self.start_position[1], 0.0
        pose = self.entry_spawn_pose("exit")
        if pose is not None:
            return pose
        return self.start_position[0], self.start_position[1], 0.0

    def _door_entry_spawn_pose(self, tile: int, source_cell: tuple[int, int] | None) -> tuple[float, float, float] | None:
        groups: list[frozenset[tuple[int, int]]] = []
        seen: set[frozenset[tuple[int, int]]] = set()
        for y in range(self.height):
            for x in range(self.width):
                if self.tile_at(x, y) != tile:
                    continue
                group = self.door_group_at(x, y)
                if group in seen:
                    continue
                seen.add(group)
                groups.append(group)

        best: tuple[float, int, float, float, float, int, int] | None = None
        for group in groups:
            center_x = sum(x + 0.5 for x, _y in group) / len(group)
            center_y = sum(y + 0.5 for _x, y in group) / len(group)
            reference_x = sum(x for x, _y in group) / len(group)
            reference_y = sum(y for _x, y in group) / len(group)
            for spawn_x, spawn_y in self._adjacent_spawn_cells(group):
                candidate = self._spawn_candidate_score(spawn_x, spawn_y, center_x, center_y, reference_x, reference_y, source_cell)
                if candidate is not None and (best is None or candidate < best):
                    best = candidate

        return self._pose_from_candidate(best)

    def _object_entry_spawn_pose(self, object_ids: set[str], source_cell: tuple[int, int] | None) -> tuple[float, float, float] | None:
        best: tuple[float, int, float, float, float, int, int] | None = None
        for anchor, obj in self.objects.items():
            if anchor in self.picked_objects or obj.object_id not in object_ids:
                continue
            occupied = self._object_occupied_cells(anchor, obj)
            if not occupied:
                continue
            min_x, min_y, max_x, max_y = self.object_bounds(anchor, obj)
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            reference_x, reference_y = anchor
            for spawn_x, spawn_y in self._adjacent_spawn_cells(occupied):
                candidate = self._spawn_candidate_score(spawn_x, spawn_y, center_x, center_y, reference_x, reference_y, source_cell)
                if candidate is not None and (best is None or candidate < best):
                    best = candidate

        return self._pose_from_candidate(best)

    def _object_occupied_cells(self, anchor: tuple[int, int], obj: MapObject) -> frozenset[tuple[int, int]]:
        min_x, min_y, max_x, max_y = self.object_bounds(anchor, obj)
        start_x = math.floor(min_x)
        start_y = math.floor(min_y)
        end_x = math.ceil(max_x)
        end_y = math.ceil(max_y)
        return frozenset(
            (x, y)
            for y in range(start_y, end_y)
            for x in range(start_x, end_x)
            if self.in_bounds(x, y)
        )

    def _adjacent_spawn_cells(self, entry_cells: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
        occupied = set(entry_cells)
        candidates: set[tuple[int, int]] = set()
        for x, y in occupied:
            for spawn_x, spawn_y in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (spawn_x, spawn_y) in occupied:
                    continue
                if self._is_spawn_floor(spawn_x, spawn_y):
                    candidates.add((spawn_x, spawn_y))
        return sorted(candidates)

    def _spawn_candidate_score(
        self,
        spawn_x: int,
        spawn_y: int,
        entry_center_x: float,
        entry_center_y: float,
        reference_x: float,
        reference_y: float,
        source_cell: tuple[int, int] | None,
    ) -> tuple[float, int, float, float, float, int, int] | None:
        if not self._is_spawn_floor(spawn_x, spawn_y):
            return None
        if source_cell is None:
            source_distance = 0.0
        else:
            source_distance = (reference_x - source_cell[0]) ** 2 + (reference_y - source_cell[1]) ** 2
        openness = sum(
            1
            for nx, ny in ((spawn_x + 1, spawn_y), (spawn_x - 1, spawn_y), (spawn_x, spawn_y + 1), (spawn_x, spawn_y - 1))
            if self._is_spawn_floor(nx, ny)
        )
        center_distance = (spawn_x + 0.5 - entry_center_x) ** 2 + (spawn_y + 0.5 - entry_center_y) ** 2
        return (source_distance, -openness, center_distance, entry_center_x, entry_center_y, spawn_x, spawn_y)

    def _pose_from_candidate(self, candidate: tuple[float, int, float, float, float, int, int] | None) -> tuple[float, float, float] | None:
        if candidate is None:
            return None
        _source_distance, _openness, _center_distance, entry_center_x, entry_center_y, spawn_x, spawn_y = candidate
        player_x = spawn_x + 0.5
        player_y = spawn_y + 0.5
        angle = math.atan2(player_y - entry_center_y, player_x - entry_center_x) % math.tau
        return player_x, player_y, angle

    def _is_spawn_floor(self, x: int, y: int) -> bool:
        tile = self.tile_at(x, y)
        if tile in WALL_TILES or tile in DOOR_TILES:
            return False
        center_x = x + 0.5
        center_y = y + 0.5
        object_radius_squared = OBJECT_COLLISION_RADIUS * OBJECT_COLLISION_RADIUS
        for anchor, obj in self.objects.items():
            if anchor in self.picked_objects or not obj.solid:
                continue
            if self._collides_object_rect(center_x, center_y, anchor, obj, object_radius_squared):
                return False
        return True

