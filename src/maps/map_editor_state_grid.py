from __future__ import annotations

from typing import Iterable

from src.maps.map_editor_config import *
from src.maps.map_editor_models import Room


class MapEditorStateGridMixin:
    def selected_room(self) -> Room | None:
        if self.selected_room_id is None:
            return None
        for room in self.rooms:
            if room.room_id == self.selected_room_id:
                return room
        return None

    def update_selected_room(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        w: int | None = None,
        h: int | None = None,
    ) -> bool:
        room = self.selected_room()
        if room is None:
            return False
        if x is not None:
            room.x = max(0, int(x))
        if y is not None:
            room.y = max(0, int(y))
        if w is not None:
            room.w = max(MIN_ROOM_SIZE, int(w))
        if h is not None:
            room.h = max(MIN_ROOM_SIZE, int(h))
        self.rebuild_grid()
        self.status = "Room placement updated."
        return True

    def room_at(self, cell: tuple[int, int]) -> Room | None:
        for room in reversed(self.rooms):
            if room.contains(cell):
                return room
        return None

    def ensure_grid_size_for(self, cells: Iterable[tuple[int, int]]) -> None:
        for x, y in cells:
            if x >= self.grid_width:
                self.grid_width = x + 1
            if y >= self.grid_height:
                self.grid_height = y + 1

    def rebuild_grid(self) -> None:
        self.ensure_grid_size_for(
            (cell for room in self.rooms for cell in ((room.x + room.w - 1, room.y + room.h - 1),))
        )
        object_cells = [
            cell
            for anchor, placement in self.objects.items()
            for cell in self.object_footprint_cells(anchor, placement)
        ]
        all_cells = list(self.doors) + object_cells + list(self.overrides)
        if self.start_cell is not None:
            all_cells.append(self.start_cell)
        self.ensure_grid_size_for(all_cells)

        self.grid = [["#" for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        for room in self.rooms:
            self._draw_room(room)
        for (x, y), symbol in self.overrides.items():
            if self.in_bounds(x, y):
                self.grid[y][x] = symbol
        for (x, y), symbol in self.doors.items():
            if self.in_bounds(x, y):
                self.grid[y][x] = symbol
        for (x, y), placement in self.objects.items():
            if self.in_bounds(x, y) and placement.object_id in LEGACY_OBJECT_IDS:
                self.grid[y][x] = placement.object_id
        if self.start_cell is not None and self.in_bounds(*self.start_cell):
            x, y = self.start_cell
            self.grid[y][x] = "@"

    def _draw_room(self, room: Room) -> None:
        for y in range(room.y, room.y + room.h):
            for x in range(room.x, room.x + room.w):
                if not self.in_bounds(x, y):
                    continue
                is_border = x in (room.x, room.x + room.w - 1) or y in (room.y, room.y + room.h - 1)
                self.grid[y][x] = "#" if is_border else "."

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.grid_width and 0 <= y < self.grid_height

    def resize_grid(self, width: int, height: int) -> None:
        self.grid_width = max(MIN_GRID_WIDTH, int(width))
        self.grid_height = max(MIN_GRID_HEIGHT, int(height))
        original_room_count = len(self.rooms)
        clipped_room_count = 0
        kept_rooms: list[Room] = []
        for room in self.rooms:
            if room.x >= self.grid_width or room.y >= self.grid_height:
                continue
            clipped_w = min(room.w, self.grid_width - room.x)
            clipped_h = min(room.h, self.grid_height - room.y)
            if clipped_w < MIN_ROOM_SIZE or clipped_h < MIN_ROOM_SIZE:
                continue
            if clipped_w != room.w or clipped_h != room.h:
                clipped_room_count += 1
                room.w = clipped_w
                room.h = clipped_h
            kept_rooms.append(room)
        self.rooms = kept_rooms
        if self.selected_room_id is not None and self.selected_room() is None:
            self.selected_room_id = None
        self.doors = {cell: symbol for cell, symbol in self.doors.items() if self.in_bounds(*cell)}
        self.objects = {cell: symbol for cell, symbol in self.objects.items() if self.in_bounds(*cell)}
        self.overrides = {cell: symbol for cell, symbol in self.overrides.items() if self.in_bounds(*cell)}
        if self.start_cell is not None and not self.in_bounds(*self.start_cell):
            self.start_cell = None
        self.rebuild_grid()
        removed = original_room_count - len(self.rooms)
        detail = ""
        if removed:
            detail = f" Removed {removed} room(s) outside bounds."
        elif clipped_room_count:
            detail = f" Clipped {clipped_room_count} room(s) at bounds."
        self.status = f"Grid resized to {self.grid_width} x {self.grid_height}.{detail}"

    def clear_map(self) -> None:
        self.rooms.clear()
        self.doors.clear()
        self.objects.clear()
        self.overrides.clear()
        self.start_cell = None
        self.selected_room_id = None
        self.selected_door = None
        self.selected_object = None

        room = Room(1, 1, 1, MIN_ROOM_SIZE, MIN_ROOM_SIZE, "Start Room", "1")
        self.rooms.append(room)
        self.next_room_id = 2
        self.start_cell = (room.x + 1, room.y + 1)
        self.rebuild_grid()
        self.status = "Cleared map. Kept one 3 x 3 start room."

    def add_room(self, x1: int, y1: int, x2: int, y2: int) -> Room | None:
        min_x, max_x = sorted((x1, x2))
        min_y, max_y = sorted((y1, y2))
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        if width < MIN_ROOM_SIZE or height < MIN_ROOM_SIZE:
            self.status = "Room needs at least 3 x 3 cells."
            return None
        room = Room(self.next_room_id, min_x, min_y, width, height, f"Room {self.next_room_id}", str(self.next_room_id))
        self.next_room_id += 1
        self.rooms.append(room)
        self.selected_room_id = room.room_id
        self.selected_door = None
        self.selected_object = None
        self.rebuild_grid()
        self.status = f"Created {room.name} ({room.w} x {room.h})."
        return room

    def delete_selection(self) -> None:
        if self.selected_room_id is not None:
            self.rooms = [room for room in self.rooms if room.room_id != self.selected_room_id]
            self.selected_room_id = None
            self.rebuild_grid()
            self.status = "Deleted selected room."
            return
        if self.selected_door is not None:
            self.doors.pop(self.selected_door, None)
            self.selected_door = None
            self.rebuild_grid()
            self.status = "Deleted selected door."
            return
        if self.selected_object is not None:
            self.objects.pop(self.selected_object, None)
            self.selected_object = None
            self.rebuild_grid()
            self.status = "Deleted selected object."

    def place_wall(self, cell: tuple[int, int]) -> None:
        x, y = cell
        if not self.in_bounds(x, y):
            return
        self.doors.pop(cell, None)
        object_anchor = self.object_anchor_at(cell)
        if object_anchor is not None:
            self.objects.pop(object_anchor, None)
        if self.start_cell == cell:
            self.start_cell = None
        self.overrides[cell] = "#"
        self.rebuild_grid()

    def place_window(self, cell: tuple[int, int]) -> None:
        x, y = cell
        if not self.in_bounds(x, y):
            return
        self.doors.pop(cell, None)
        object_anchor = self.object_anchor_at(cell)
        if object_anchor is not None:
            self.objects.pop(object_anchor, None)
        if self.start_cell == cell:
            self.start_cell = None
        self.overrides[cell] = WINDOW_SYMBOL
        self.selected_room_id = None
        self.selected_door = None
        self.selected_object = None
        self.rebuild_grid()
        self.status = f"Placed window wall at {cell}."

    def erase_cell(self, cell: tuple[int, int]) -> None:
        x, y = cell
        if not self.in_bounds(x, y):
            return
        self.doors.pop(cell, None)
        object_anchor = self.object_anchor_at(cell)
        if object_anchor is not None:
            self.objects.pop(object_anchor, None)
        if self.start_cell == cell:
            self.start_cell = None
        self.overrides[cell] = "."
        self.rebuild_grid()

    def place_start(self, cell: tuple[int, int]) -> None:
        if not self._is_floor_target(cell):
            self.status = "Start must be placed inside a room or corridor."
            return
        self.start_cell = cell
        self.rebuild_grid()
        self.status = f"Player start set to {cell}."


