from __future__ import annotations

from src.settings import (
    DOOR_OPEN_SPEED,
    DOOR_PASSABLE_PROGRESS,
    DOOR_TILES,
    TILE_CLASSROOM_DOOR,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
    WALL_TILES,
)


class GameMapDoorMixin:
    def is_door(self, x: int, y: int) -> bool:
        return self.tile_at(x, y) in DOOR_TILES

    def is_open_door(self, x: int, y: int) -> bool:
        return (x, y) in self.open_doors

    def is_passable_door(self, x: int, y: int) -> bool:
        return self.is_open_door(x, y) and self.door_progress_at(x, y) >= DOOR_PASSABLE_PROGRESS

    def open_door(self, x: int, y: int) -> None:
        if self.is_door(x, y):
            for cell in self.door_group_at(x, y):
                self.open_doors.add(cell)
                self.door_open_progress.setdefault(cell, 0.0)

    def close_door(self, x: int, y: int) -> None:
        if self.is_door(x, y):
            for cell in self.door_group_at(x, y):
                self.open_doors.discard(cell)
                self.door_open_progress.pop(cell, None)

    def update_doors(self, dt: float) -> None:
        if not self.door_open_progress:
            return
        step = DOOR_OPEN_SPEED * dt
        for cell, progress in list(self.door_open_progress.items()):
            self.door_open_progress[cell] = min(1.0, progress + step)

    def door_progress_at(self, x: int, y: int) -> float:
        return self.door_open_progress.get((x, y), 0.0)

    def door_group_at(self, x: int, y: int) -> frozenset[tuple[int, int]]:
        return self.door_groups.get((x, y), frozenset({(x, y)}))

    def door_role_at(self, x: int, y: int) -> str:
        return self.door_roles.get((x, y), "")

    def door_orientation_at(self, x: int, y: int) -> str:
        group = self.door_group_at(x, y)
        xs = [gx for gx, _ in group]
        ys = [gy for _, gy in group]
        width = max(xs) - min(xs) + 1
        height = max(ys) - min(ys) + 1
        if height > width:
            return "vertical"
        if width > height:
            return "horizontal"

        west_open = self.tile_at(x - 1, y) not in WALL_TILES
        east_open = self.tile_at(x + 1, y) not in WALL_TILES
        north_open = self.tile_at(x, y - 1) not in WALL_TILES
        south_open = self.tile_at(x, y + 1) not in WALL_TILES
        west_wall = self.tile_at(x - 1, y) in WALL_TILES
        east_wall = self.tile_at(x + 1, y) in WALL_TILES
        north_wall = self.tile_at(x, y - 1) in WALL_TILES
        south_wall = self.tile_at(x, y + 1) in WALL_TILES
        if (west_wall and east_wall and (north_open or south_open)) or (north_open and south_open and not (west_open and east_open)):
            return "horizontal"
        if north_wall and south_wall and (west_open or east_open):
            return "vertical"
        return "vertical"
