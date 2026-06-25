"""Developer map editor for LabMidnight.

The editor writes the same text layout consumed by GameMap. Room labels are
stored in a sidecar JSON file because the runtime map format is intentionally
kept compact and character based.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import sys
from typing import Iterable

import pygame

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.resources.object_assets import ObjectSpec, load_object_specs
from src.settings import PLAYER_SPEED, PLAYER_SPEED_MAX, PLAYER_SPEED_MIN


LEGACY_MAP_LAYOUT_PATH = Path("data/map_layout.txt")
LEGACY_ROOM_META_PATH = Path("data/map_rooms.json")
FLOOR_MAP_DIR = Path("data/floors")
MAP_CONFIG_PATH = Path("data/map_config.json")

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 760
TOOLBAR_WIDTH = 220
PANEL_WIDTH = 300
STATUS_HEIGHT = 34
CELL_SIZE = 20
MIN_VIEW_CELL_SIZE = 8
MAX_VIEW_CELL_SIZE = 48
VIEW_ZOOM_STEP = 1.14
H_SCROLLBAR_HEIGHT = 18
H_SCROLLBAR_MIN_THUMB_WIDTH = 36
V_SCROLLBAR_WIDTH = 10
V_SCROLLBAR_MIN_THUMB_HEIGHT = 36
SIDE_SCROLL_STEP = 42
OBJECT_HANDLE_SIZE = 8
HISTORY_LIMIT = 80
MAP_SCALE_VALUES = (0.5, 1.0, 2.0, 3.0, 5.0)
MIN_ROOM_SIZE = 3
DEFAULT_GRID_WIDTH = 40
DEFAULT_GRID_HEIGHT = 24
MIN_GRID_WIDTH = 12
MIN_GRID_HEIGHT = 12
BOTTOM_FLOOR = 1
TOP_FLOOR = 4

COLOR_BG = (18, 22, 24)
COLOR_TOOLBAR = (28, 34, 37)
COLOR_PANEL = (24, 29, 31)
COLOR_PANEL_EDGE = (74, 90, 92)
COLOR_TEXT = (224, 231, 225)
COLOR_MUTED = (146, 156, 150)
COLOR_ACCENT = (221, 178, 76)
COLOR_WARNING = COLOR_ACCENT
COLOR_GRID = (42, 49, 51)
COLOR_FLOOR = (47, 52, 51)
COLOR_WALL = (164, 169, 164)
COLOR_START = (93, 151, 214)
COLOR_OBJECT = (214, 184, 82)
COLOR_SELECTED = (80, 190, 178)
COLOR_ERROR = (222, 91, 80)

FLOOR_CHARS = {".", "@", *"123456789"}
DOOR_SYMBOLS = {
    "G": ("Guard", (138, 98, 67)),
    "L": ("Lab", (134, 104, 72)),
    "M": ("Machine", (122, 94, 67)),
    "C": ("Classroom", (72, 139, 134)),
    "P": ("Power", (150, 135, 63)),
    "E": ("Exit", (166, 69, 64)),
}

OBJECT_LABELS = {
    "1": "Lab Desk",
    "2": "Blackboard",
    "3": "Lectern",
    "4": "Guard Desk",
    "5": "Fuse Cabinet",
    "6": "Battery",
    "7": "Power Box",
    "8": "Server Terminal",
    "9": "Exit Panel",
}

LEGACY_OBJECT_IDS = set(OBJECT_LABELS)
LEGACY_OBJECT_ASSET_ALIASES = {
    "1": "desk",
}

OBJECT_NUMERIC_FIELDS = {
    "object_x",
    "object_y",
    "object_footprint_w",
    "object_footprint_d",
    "object_height",
    "object_z",
}
FLOAT_NUMERIC_FIELDS = {"player_speed", "object_footprint_w", "object_footprint_d", "object_height", "object_z"}
NUMERIC_FIELDS = {"grid_width", "grid_height", "initial_hp", "initial_sanity", "initial_battery", "player_speed"} | OBJECT_NUMERIC_FIELDS


def floor_layout_path(floor: int) -> Path:
    return FLOOR_MAP_DIR / f"floor_{floor}.txt"


def floor_room_meta_path(floor: int) -> Path:
    return FLOOR_MAP_DIR / f"floor_{floor}_rooms.json"


def existing_layout_path_for_floor(floor: int) -> Path:
    path = floor_layout_path(floor)
    if path.exists():
        return path
    if floor == TOP_FLOOR and LEGACY_MAP_LAYOUT_PATH.exists():
        return LEGACY_MAP_LAYOUT_PATH
    return path


def existing_room_meta_path_for_floor(floor: int) -> Path:
    path = floor_room_meta_path(floor)
    if path.exists():
        return path
    if floor == TOP_FLOOR and LEGACY_ROOM_META_PATH.exists():
        return LEGACY_ROOM_META_PATH
    return path


@dataclass
class Room:
    room_id: int
    x: int
    y: int
    w: int
    h: int
    name: str
    number: str

    def contains(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def handle_cell(self) -> tuple[int, int]:
        return self.x + self.w - 1, self.y + self.h - 1


@dataclass
class ObjectPlacement:
    object_id: str
    rotation: int = 0
    length: float | None = None
    width: float | None = None
    height: float | None = None
    placement_height: float | None = None

    def label_char(self) -> str:
        return self.object_id if self.object_id in LEGACY_OBJECT_IDS else "O"


class MapEditorState:
    def __init__(self, floor: int = TOP_FLOOR) -> None:
        self.floor = max(BOTTOM_FLOOR, min(TOP_FLOOR, floor))
        self.grid_width = DEFAULT_GRID_WIDTH
        self.grid_height = DEFAULT_GRID_HEIGHT
        self.cell_scale = 1.0
        self.initial_hp = 100
        self.initial_sanity = 100
        self.initial_battery = 86
        self.player_speed = PLAYER_SPEED
        self.object_specs: dict[str, ObjectSpec] = load_object_specs()
        self.rooms: list[Room] = []
        self.doors: dict[tuple[int, int], str] = {}
        self.objects: dict[tuple[int, int], ObjectPlacement] = {}
        self.overrides: dict[tuple[int, int], str] = {}
        self.start_cell: tuple[int, int] | None = None
        self.grid: list[list[str]] = []
        self.selected_room_id: int | None = None
        self.selected_door: tuple[int, int] | None = None
        self.selected_object: tuple[int, int] | None = None
        self.next_room_id = 1
        self.status = ""
        self._load_initial_config()
        self.rebuild_grid()

    @classmethod
    def load(cls, floor: int = TOP_FLOOR) -> "MapEditorState":
        state = cls(floor)
        layout_path = existing_layout_path_for_floor(state.floor)
        if not layout_path.exists():
            state.status = f"No map for floor {state.floor}; started with an empty grid."
            return state

        rows = [
            line.rstrip("\n")
            for line in layout_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(";")
        ]
        if not rows:
            state.status = f"Floor {state.floor} map is empty; started with an empty grid."
            return state

        state.grid_width = max(MIN_GRID_WIDTH, max(len(row) for row in rows))
        state.grid_height = max(MIN_GRID_HEIGHT, len(rows))
        padded = [row.ljust(state.grid_width, "#") for row in rows]
        state.doors.clear()
        state.objects.clear()
        state.overrides.clear()
        state.start_cell = None

        for y, row in enumerate(padded):
            for x, char in enumerate(row):
                if char in DOOR_SYMBOLS:
                    state.doors[(x, y)] = char
                elif char == "@":
                    state.start_cell = (x, y)
                elif char in "123456789":
                    state.objects[(x, y)] = ObjectPlacement(state._object_id_for_layout_symbol(char))

        state.rooms = state._load_room_metadata()
        state.cell_scale = state._load_cell_scale()
        if not state.rooms:
            state.rooms = state._infer_rooms_from_rows(padded)
        state.overrides = state._load_overrides()
        state._load_object_metadata()
        state.next_room_id = 1 + max((room.room_id for room in state.rooms), default=0)
        state.rebuild_grid()
        state.status = f"Loaded floor {state.floor}: {layout_path}."
        return state

    def _object_id_for_layout_symbol(self, symbol: str) -> str:
        alias = LEGACY_OBJECT_ASSET_ALIASES.get(symbol)
        if alias is not None and alias in self.object_specs:
            return alias
        return symbol

    def _load_initial_config(self) -> None:
        if not MAP_CONFIG_PATH.exists():
            return
        try:
            payload = json.loads(MAP_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        initial = payload.get("initial_player", {})
        if not isinstance(initial, dict):
            return
        self.initial_hp = self._read_int(initial, "hp", self.initial_hp)
        self.initial_sanity = self._read_int(initial, "sanity", self.initial_sanity)
        self.initial_battery = self._read_int(initial, "flashlight_power", self.initial_battery)
        raw_speed = self._read_float(initial, ("speed", "player_speed"), self.player_speed)
        self.player_speed = max(PLAYER_SPEED_MIN, min(PLAYER_SPEED_MAX, raw_speed))

    def _read_int(self, payload: dict, key: str, fallback: int) -> int:
        try:
            return max(0, int(float(payload.get(key, fallback))))
        except (TypeError, ValueError):
            return fallback

    def _read_float(self, payload: dict, keys: tuple[str, ...], fallback: float) -> float:
        for key in keys:
            if key not in payload:
                continue
            try:
                return max(0.0, float(payload[key]))
            except (TypeError, ValueError):
                return fallback
        return fallback

    def _load_room_metadata(self) -> list[Room]:
        meta_path = existing_room_meta_path_for_floor(self.floor)
        if not meta_path.exists():
            return []
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        rooms: list[Room] = []
        for raw in payload.get("rooms", []):
            try:
                room = Room(
                    room_id=int(raw["room_id"]),
                    x=int(raw["x"]),
                    y=int(raw["y"]),
                    w=max(MIN_ROOM_SIZE, int(raw["w"])),
                    h=max(MIN_ROOM_SIZE, int(raw["h"])),
                    name=str(raw.get("name", "Room")),
                    number=str(raw.get("number", raw["room_id"])),
                )
            except (KeyError, TypeError, ValueError):
                continue
            rooms.append(room)
        return rooms

    def _load_cell_scale(self) -> float:
        meta_path = existing_room_meta_path_for_floor(self.floor)
        if not meta_path.exists():
            return 1.0
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 1.0
        try:
            raw_value = float(payload.get("cell_scale", 1.0))
        except (TypeError, ValueError):
            return 1.0
        return min(MAP_SCALE_VALUES, key=lambda value: abs(value - raw_value))

    def _load_overrides(self) -> dict[tuple[int, int], str]:
        meta_path = existing_room_meta_path_for_floor(self.floor)
        if not meta_path.exists():
            return {}
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        overrides: dict[tuple[int, int], str] = {}
        for raw in payload.get("overrides", []):
            try:
                x = int(raw["x"])
                y = int(raw["y"])
                symbol = str(raw["symbol"])
            except (KeyError, TypeError, ValueError):
                continue
            if symbol in {"#", "."}:
                overrides[(x, y)] = symbol
        return overrides

    def _load_object_metadata(self) -> None:
        meta_path = existing_room_meta_path_for_floor(self.floor)
        if not meta_path.exists():
            return
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        raw_objects = payload.get("objects", [])
        if not isinstance(raw_objects, list):
            return
        for raw in raw_objects:
            if not isinstance(raw, dict):
                continue
            try:
                x = int(raw["x"])
                y = int(raw["y"])
            except (KeyError, TypeError, ValueError):
                continue
            object_id = str(raw.get("object_id") or raw.get("symbol") or raw.get("asset_id") or "")
            if not object_id:
                continue
            alias = LEGACY_OBJECT_ASSET_ALIASES.get(object_id)
            if alias is not None and alias in self.object_specs:
                object_id = alias
            try:
                rotation = int(raw.get("rotation", 0)) % 360
            except (TypeError, ValueError):
                rotation = 0
            if object_id in LEGACY_OBJECT_IDS or object_id in self.object_specs:
                self.objects[(x, y)] = ObjectPlacement(
                    object_id,
                    rotation,
                    self._read_optional_positive_float(raw, "length"),
                    self._read_optional_positive_float(raw, "width"),
                    self._read_optional_positive_float(raw, "height"),
                    self._read_optional_non_negative_float(raw, "placement_height"),
                )

    def _read_optional_positive_float(self, payload: dict, key: str) -> float | None:
        if key not in payload:
            return None
        try:
            return max(0.05, float(payload[key]))
        except (TypeError, ValueError):
            return None

    def _read_optional_non_negative_float(self, payload: dict, key: str) -> float | None:
        if key not in payload:
            return None
        try:
            return max(0.0, float(payload[key]))
        except (TypeError, ValueError):
            return None

    def _infer_rooms_from_rows(self, rows: list[str]) -> list[Room]:
        height = len(rows)
        width = max((len(row) for row in rows), default=0)
        seen: set[tuple[int, int]] = set()
        rooms: list[Room] = []
        next_id = 1

        for start_y in range(height):
            for start_x in range(width):
                if (start_x, start_y) in seen or rows[start_y][start_x] not in FLOOR_CHARS:
                    continue

                stack = [(start_x, start_y)]
                seen.add((start_x, start_y))
                cells: list[tuple[int, int]] = []
                while stack:
                    x, y = stack.pop()
                    cells.append((x, y))
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if not (0 <= nx < width and 0 <= ny < height):
                            continue
                        if (nx, ny) in seen or rows[ny][nx] not in FLOOR_CHARS:
                            continue
                        seen.add((nx, ny))
                        stack.append((nx, ny))

                if len(cells) < 4:
                    continue
                xs = [x for x, _ in cells]
                ys = [y for _, y in cells]
                min_x = max(0, min(xs) - 1)
                min_y = max(0, min(ys) - 1)
                max_x = min(width - 1, max(xs) + 1)
                max_y = min(height - 1, max(ys) + 1)
                rooms.append(
                    Room(
                        room_id=next_id,
                        x=min_x,
                        y=min_y,
                        w=max(MIN_ROOM_SIZE, max_x - min_x + 1),
                        h=max(MIN_ROOM_SIZE, max_y - min_y + 1),
                        name=f"Room {next_id}",
                        number=str(next_id),
                    )
                )
                next_id += 1
        return rooms

    def selected_room(self) -> Room | None:
        if self.selected_room_id is None:
            return None
        for room in self.rooms:
            if room.room_id == self.selected_room_id:
                return room
        return None

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

    def scale_existing_cells(self, factor: int) -> None:
        self.set_cell_scale(float(factor))

    def set_cell_scale(self, target_scale: float) -> bool:
        target_scale = min(MAP_SCALE_VALUES, key=lambda value: abs(value - float(target_scale)))
        current_scale = self.cell_scale if self.cell_scale > 0 else 1.0
        if abs(target_scale - current_scale) < 0.001:
            self.status = f"Map cell scale already {self._format_scale(target_scale)}."
            return False

        ratio = target_scale / current_scale
        self.rebuild_grid()
        old_grid = [row[:] for row in self.grid]
        old_width = self.grid_width
        old_height = self.grid_height
        old_rooms = [replace(room) for room in self.rooms]
        old_doors = dict(self.doors)
        old_objects = {cell: replace(placement) for cell, placement in self.objects.items()}
        old_start = self.start_cell

        self.grid_width = max(MIN_GRID_WIDTH, int(round(old_width * ratio)))
        self.grid_height = max(MIN_GRID_HEIGHT, int(round(old_height * ratio)))
        self.rooms = [
            Room(
                room.room_id,
                self._scale_cell_index(room.x, ratio, self.grid_width),
                self._scale_cell_index(room.y, ratio, self.grid_height),
                max(MIN_ROOM_SIZE, int(round(room.w * ratio))),
                max(MIN_ROOM_SIZE, int(round(room.h * ratio))),
                room.name,
                room.number,
            )
            for room in old_rooms
        ]

        self.doors.clear()
        self.overrides.clear()
        self.objects.clear()
        self.start_cell = None

        for y in range(self.grid_height):
            old_y = min(old_height - 1, int(y / ratio)) if old_height > 0 else 0
            for x in range(self.grid_width):
                old_x = min(old_width - 1, int(x / ratio)) if old_width > 0 else 0
                char = old_grid[old_y][old_x]
                self.overrides[(x, y)] = "#" if char == "#" or char in DOOR_SYMBOLS else "."

        for (x, y), symbol in old_doors.items():
            for target in self._scaled_cell_rect(x, y, ratio, self.grid_width, self.grid_height):
                self.doors[target] = symbol
                self.overrides.pop(target, None)

        if old_start is not None:
            self.start_cell = (
                self._scale_cell_index(old_start[0], ratio, self.grid_width),
                self._scale_cell_index(old_start[1], ratio, self.grid_height),
            )

        for (x, y), placement in old_objects.items():
            length, width, height, placement_height = self.object_dimensions(placement)
            scaled = replace(
                placement,
                length=max(0.05, length * ratio),
                width=max(0.05, width * ratio),
                height=height,
                placement_height=placement_height,
            )
            anchor = (
                self._scale_cell_index(x, ratio, self.grid_width),
                self._scale_cell_index(y, ratio, self.grid_height),
            )
            self.objects[anchor] = scaled

        self.cell_scale = target_scale
        self.selected_room_id = None
        self.selected_door = None
        self.selected_object = None
        self.rebuild_grid()
        self.status = f"Map cell scale set to {self._format_scale(target_scale)}."
        return True

    def _format_scale(self, scale: float) -> str:
        return str(int(scale)) if abs(scale - int(scale)) < 0.001 else str(scale)

    def _scale_cell_index(self, value: int, ratio: float, limit: int) -> int:
        if limit <= 1:
            return 0
        scaled = int(round((value + 0.5) * ratio - 0.5))
        return max(0, min(limit - 1, scaled))

    def _scaled_cell_rect(
        self,
        x: int,
        y: int,
        ratio: float,
        width: int,
        height: int,
    ) -> list[tuple[int, int]]:
        x0 = max(0, min(width - 1, int(math.floor(x * ratio))))
        y0 = max(0, min(height - 1, int(math.floor(y * ratio))))
        x1 = max(x0, min(width - 1, int(math.ceil((x + 1) * ratio)) - 1))
        y1 = max(y0, min(height - 1, int(math.ceil((y + 1) * ratio)) - 1))
        return [(tx, ty) for ty in range(y0, y1 + 1) for tx in range(x0, x1 + 1)]

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

    def place_object(
        self,
        cell: tuple[int, int],
        object_id: str,
        rotation: int = 0,
        *,
        auto_wall_snap: bool = False,
    ) -> None:
        placement = ObjectPlacement(object_id, rotation % 360)
        target = cell
        if auto_wall_snap:
            snapped = self.snap_object_to_wall(cell, placement)
            if snapped is not None:
                target, placement = snapped
        if not self._object_fits(target, placement):
            self.status = "Objects must be placed on floor cells."
            return
        if self.start_cell == target:
            self.start_cell = None
        self.objects[target] = placement
        self.selected_object = target
        self.selected_room_id = None
        self.selected_door = None
        self.rebuild_grid()
        snap_note = " snapped to wall" if target != cell or placement.rotation % 360 != rotation % 360 else ""
        self.status = f"Object {self.object_label(object_id)} placed at {target}{snap_note}."

    def snap_object_to_wall(
        self,
        requested_cell: tuple[int, int],
        placement: ObjectPlacement,
    ) -> tuple[tuple[int, int], ObjectPlacement] | None:
        cx, cy = requested_cell
        directions = (
            (0, -1, 0),
            (1, 0, 90),
            (0, 1, 180),
            (-1, 0, 270),
        )
        for radius in range(0, 4):
            for y in range(cy - radius, cy + radius + 1):
                for x in range(cx - radius, cx + radius + 1):
                    if abs(x - cx) + abs(y - cy) != radius:
                        continue
                    if not self._floorish(x, y):
                        continue
                    for dx, dy, rotation in directions:
                        wall = (x + dx, y + dy)
                        if not self.in_bounds(*wall) or self.grid[wall[1]][wall[0]] != "#":
                            continue
                        rotated = replace(placement, rotation=rotation)
                        width, height = self.object_footprint_size(rotated)
                        anchor_x = x - width + 1 if dx > 0 else x
                        anchor_y = y - height + 1 if dy > 0 else y
                        anchor = (anchor_x, anchor_y)
                        if self._object_fits(anchor, rotated):
                            return anchor, rotated
        return None

    def update_selected_object(
        self,
        *,
        anchor: tuple[int, int] | None = None,
        length: float | None = None,
        width: float | None = None,
        height: float | None = None,
        placement_height: float | None = None,
    ) -> bool:
        current_anchor = self.selected_object
        if current_anchor is None:
            return False
        placement = self.objects.get(current_anchor)
        if placement is None:
            return False

        updated = replace(placement)
        if length is not None:
            updated.length = max(0.05, length)
        if width is not None:
            updated.width = max(0.05, width)
        if height is not None:
            updated.height = max(0.05, height)
        if placement_height is not None:
            updated.placement_height = max(0.0, placement_height)

        target = anchor if anchor is not None else current_anchor
        if not self._object_fits(target, updated, ignore_anchor=current_anchor):
            self.status = "Object position or footprint does not fit on valid floor cells."
            return False

        if target != current_anchor:
            self.objects.pop(current_anchor, None)
            self.selected_object = target
        self.objects[target] = updated
        self.rebuild_grid()
        self.status = "Object placement updated."
        return True

    def update_selected_object_asset(self, object_id: str) -> bool:
        current_anchor = self.selected_object
        if current_anchor is None:
            return False
        placement = self.objects.get(current_anchor)
        if placement is None:
            return False
        updated = ObjectPlacement(object_id, placement.rotation % 360)
        if not self._object_fits(current_anchor, updated, ignore_anchor=current_anchor):
            self.status = "Selected asset does not fit at this position."
            return False
        self.objects[current_anchor] = updated
        self.rebuild_grid()
        self.status = f"Selected object changed to {self.object_label(object_id)}."
        return True

    def _is_floor_target(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return self.in_bounds(x, y) and self.grid[y][x] in FLOOR_CHARS | {"."}

    def object_label(self, object_id: str) -> str:
        if object_id in OBJECT_LABELS:
            return OBJECT_LABELS[object_id]
        spec = self.object_specs.get(object_id)
        return spec.name if spec is not None else object_id

    def object_dimensions(self, placement: ObjectPlacement) -> tuple[float, float, float, float]:
        base_length, base_width, base_height, base_z = self._base_object_dimensions(placement.object_id)
        return (
            placement.length if placement.length is not None else base_length,
            placement.width if placement.width is not None else base_width,
            placement.height if placement.height is not None else base_height,
            placement.placement_height if placement.placement_height is not None else base_z,
        )

    def _base_object_dimensions(self, object_id: str) -> tuple[float, float, float, float]:
        spec = self.object_specs.get(object_id)
        if spec is None:
            return 1.0, 1.0, 1.0, 0.0
        return spec.length, spec.width, spec.height, spec.placement_height

    def object_footprint_size(self, placement: ObjectPlacement) -> tuple[int, int]:
        length, width, _, _ = self.object_dimensions(placement)
        if placement.rotation % 360 in (90, 270):
            length, width = width, length
        return max(1, int(length + 0.999)), max(1, int(width + 0.999))

    def object_footprint_cells(self, anchor: tuple[int, int], placement: ObjectPlacement) -> list[tuple[int, int]]:
        width, height = self.object_footprint_size(placement)
        ax, ay = anchor
        return [(x, y) for y in range(ay, ay + height) for x in range(ax, ax + width)]

    def object_anchor_at(self, cell: tuple[int, int]) -> tuple[int, int] | None:
        for anchor, placement in self.objects.items():
            if cell in self.object_footprint_cells(anchor, placement):
                return anchor
        return None

    def _object_fits(
        self,
        anchor: tuple[int, int],
        placement: ObjectPlacement,
        ignore_anchor: tuple[int, int] | None = None,
    ) -> bool:
        for cell in self.object_footprint_cells(anchor, placement):
            if not self._is_floor_target(cell):
                return False
            if cell == self.start_cell:
                return False
            if cell in self.doors:
                return False
            existing_anchor = self.object_anchor_at(cell)
            if existing_anchor is not None and existing_anchor not in {anchor, ignore_anchor}:
                return False
        return True

    def nearest_wall_for_door(self, cell: tuple[int, int]) -> tuple[int, int] | None:
        candidates: list[tuple[int, int, int]] = []
        cx, cy = cell
        for radius in range(0, 3):
            for y in range(cy - radius, cy + radius + 1):
                for x in range(cx - radius, cx + radius + 1):
                    if not self.in_bounds(x, y):
                        continue
                    if abs(x - cx) + abs(y - cy) != radius:
                        continue
                    if self._can_hold_door(x, y):
                        candidates.append((radius, x, y))
            if candidates:
                _, x, y = min(candidates)
                return x, y
        return None

    def _can_hold_door(self, x: int, y: int) -> bool:
        if self.grid[y][x] not in {"#", *DOOR_SYMBOLS}:
            return False
        north = self._floorish(x, y - 1)
        south = self._floorish(x, y + 1)
        west = self._floorish(x - 1, y)
        east = self._floorish(x + 1, y)
        return north or south or west or east

    def _floorish(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.grid[y][x] in FLOOR_CHARS | {"."}

    def place_door(self, requested_cell: tuple[int, int], symbol: str) -> bool:
        target = self.nearest_wall_for_door(requested_cell)
        if target is None:
            self.status = "Door must snap to a wall next to floor."
            return False
        self.doors[target] = symbol
        self.overrides.pop(target, None)
        object_anchor = self.object_anchor_at(target)
        if object_anchor is not None:
            self.objects.pop(object_anchor, None)
        if self.start_cell == target:
            self.start_cell = None
        self.selected_room_id = None
        self.selected_door = target
        self.selected_object = None
        self.rebuild_grid()
        self.status = f"Placed {DOOR_SYMBOLS[symbol][0]} door at {target}."
        return True

    def save(self) -> None:
        layout_path = floor_layout_path(self.floor)
        room_meta_path = floor_room_meta_path(self.floor)
        layout_path.parent.mkdir(parents=True, exist_ok=True)
        layout = self._layout_text()
        layout_path.write_text(layout, encoding="utf-8")
        metadata = {
            "tile_size_cm": 60,
            "cell_scale": self.cell_scale,
            "floor": self.floor,
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "rooms": [asdict(room) for room in self.rooms],
            "overrides": [
                {"x": x, "y": y, "symbol": symbol}
                for (x, y), symbol in sorted(self.overrides.items())
            ],
            "objects": [
                self._object_metadata_item(x, y, placement)
                for (x, y), placement in sorted(self.objects.items())
            ],
        }
        room_meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self._save_initial_config()
        if self.floor == TOP_FLOOR:
            LEGACY_MAP_LAYOUT_PATH.write_text(layout, encoding="utf-8")
            LEGACY_ROOM_META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status = f"Saved floor {self.floor}."

    def _object_metadata_item(self, x: int, y: int, placement: ObjectPlacement) -> dict:
        length, width, height, placement_height = self.object_dimensions(placement)
        return {
            "x": x,
            "y": y,
            "object_id": placement.object_id,
            "rotation": placement.rotation % 360,
            "length": length,
            "width": width,
            "height": height,
            "placement_height": placement_height,
        }

    def _save_initial_config(self) -> None:
        MAP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "initial_player": {
                "hp": self.initial_hp,
                "sanity": self.initial_sanity,
                "flashlight_power": self.initial_battery,
                "speed": self.player_speed,
            }
        }
        MAP_CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _layout_text(self) -> str:
        lines = [
            "; LabMidnight editable map layout.",
            f"; Generated by map_editor.py for floor {self.floor}. One character is one 60cm floor tile.",
            ";",
            "; Terrain: # wall, . floor, @ player start",
            "; Doors: L lab, M machine/server lab-style, C classroom, G guard, P power, E exit",
            "; Legacy objects: 1-9 story objects defined in src/map_data.py",
            "; Custom objects are stored in the floor metadata JSON.",
            "",
        ]
        lines.extend("".join(row) for row in self.grid)
        return "\n".join(lines) + "\n"


class MapEditor:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("LabMidnight Map Editor")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 19)
        self.big_font = pygame.font.Font(None, 30)
        self.state = MapEditorState.load(TOP_FLOOR)
        self.running = True
        self.active_tool = "select"
        self.active_door_symbol = "L"
        self.active_object_symbol = "1"
        self.active_object_rotation = 0
        self.auto_wall_snap = False
        if self.state.object_specs:
            self.active_object_symbol = next(iter(sorted(self.state.object_specs)))
        self.buttons: list[tuple[pygame.Rect, str, str, str | None]] = []
        self.object_buttons: dict[str, pygame.Rect] = {}
        self.object_dropdown_open = False
        self.object_dropdown_rect = pygame.Rect(0, 0, 0, 0)
        self.auto_wall_snap_rect = pygame.Rect(0, 0, 0, 0)
        self.map_scale_track_rect = pygame.Rect(0, 0, 0, 0)
        self.map_scale_tick_rects: dict[float, pygame.Rect] = {}
        self.editing_field: str | None = None
        self.edit_buffer = ""
        self.drag_mode: str | None = None
        self.drag_history_pushed = False
        self.drag_start_cell: tuple[int, int] | None = None
        self.drag_current_cell: tuple[int, int] | None = None
        self.drag_initial_room: tuple[int, int, int, int] | None = None
        self.drag_initial_object: tuple[tuple[int, int], ObjectPlacement, str] | None = None
        self.selection_rect: tuple[int, int, int, int] | None = None
        self.selection_items = self._empty_selection_items()
        self.selection_move_snapshot: dict[str, object] | None = None
        self.hover_cell: tuple[int, int] | None = None
        self.panel_fields: dict[str, pygame.Rect] = {}
        self.floor_buttons: dict[int, pygame.Rect] = {}
        self.scrollbar_drag_offset = 0
        self.side_scrollbar_drag_offset = 0
        self.cell_size = CELL_SIZE
        self.scroll_x = 0
        self.scroll_y = 0
        self.toolbar_scroll_y = 0
        self.panel_scroll_y = 0
        self.toolbar_help_y = 0
        self.toolbar_content_height = 0
        self.panel_content_height = WINDOW_HEIGHT - STATUS_HEIGHT
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self._build_buttons()

    def run(self) -> None:
        while self.running:
            self._handle_events()
            self._draw()
            self.clock.tick(60)
        pygame.quit()

    @property
    def toolbar_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, TOOLBAR_WIDTH, WINDOW_HEIGHT - STATUS_HEIGHT)

    @property
    def canvas_rect(self) -> pygame.Rect:
        return pygame.Rect(TOOLBAR_WIDTH, 0, WINDOW_WIDTH - TOOLBAR_WIDTH - PANEL_WIDTH, WINDOW_HEIGHT - STATUS_HEIGHT)

    @property
    def viewport_rect(self) -> pygame.Rect:
        canvas = self.canvas_rect
        return pygame.Rect(canvas.x, canvas.y, canvas.width, max(0, canvas.height - H_SCROLLBAR_HEIGHT))

    @property
    def panel_rect(self) -> pygame.Rect:
        return pygame.Rect(WINDOW_WIDTH - PANEL_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT - STATUS_HEIGHT)

    def _build_buttons(self) -> None:
        self.buttons.clear()
        y = 18
        self._add_button("Select", "select", None, y)
        y += 36
        self._add_button("Room", "room", None, y)
        y += 36
        self._add_button("Wall", "wall", None, y)
        y += 36
        self._add_button("Erase", "erase", None, y)
        y += 36
        self._add_button("Start", "start", None, y)
        y += 36
        self._add_button("Object", "object", None, y)
        y += 36
        self._add_button("Rotate CCW", "command", "rotate_ccw", y)
        y += 36
        self._add_button("Rotate CW", "command", "rotate_cw", y)
        y += 50
        for symbol, (name, _) in DOOR_SYMBOLS.items():
            self._add_button(f"Door {symbol} {name}", "door", symbol, y)
            y += 32
        y += 18
        self._add_button("Save Ctrl+S", "command", "save", y)
        y += 36
        self._add_button("Reload Ctrl+L", "command", "load", y)
        y += 36
        self._add_button("Clear Map", "command", "clear", y)
        y += 42
        self.toolbar_help_y = y
        self.toolbar_content_height = self.toolbar_help_y + len(self._toolbar_help_lines()) * 20 + 18

    def _add_button(self, label: str, action: str, payload: str | None, y: int) -> None:
        self.buttons.append((pygame.Rect(14, y, TOOLBAR_WIDTH - 28, 28), label, action, payload))

    def _toolbar_help_lines(self) -> list[str]:
        return [
            "Drag Room from toolbar or canvas.",
            "Drag bottom-right handle to resize.",
            "Doors snap to valid wall cells.",
            "Ctrl+drag box-selects items.",
            "Bottom bar scrolls left/right.",
            "Middle/right drag pans the grid.",
            "Mouse wheel zooms the canvas.",
            "Keys: Ctrl+S save, Del delete.",
            "Undo: Ctrl+Z / Ctrl+Shift+Z.",
            "Objects: click list or press 1-9.",
            "Rotate object: Q/E or buttons.",
            "Map scale is in Properties.",
        ]

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_up(event)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_mouse_wheel(event)

    def _state_snapshot(self) -> dict:
        return {
            "floor": self.state.floor,
            "grid_width": self.state.grid_width,
            "grid_height": self.state.grid_height,
            "cell_scale": self.state.cell_scale,
            "initial_hp": self.state.initial_hp,
            "initial_sanity": self.state.initial_sanity,
            "initial_battery": self.state.initial_battery,
            "player_speed": self.state.player_speed,
            "rooms": [asdict(room) for room in self.state.rooms],
            "doors": [
                {"x": x, "y": y, "symbol": symbol}
                for (x, y), symbol in sorted(self.state.doors.items())
            ],
            "objects": [
                self.state._object_metadata_item(x, y, placement)
                for (x, y), placement in sorted(self.state.objects.items())
            ],
            "overrides": [
                {"x": x, "y": y, "symbol": symbol}
                for (x, y), symbol in sorted(self.state.overrides.items())
            ],
            "start_cell": self.state.start_cell,
            "next_room_id": self.state.next_room_id,
        }

    def _restore_snapshot(self, snapshot: dict) -> None:
        state = MapEditorState(int(snapshot.get("floor", self.state.floor)))
        state.grid_width = max(MIN_GRID_WIDTH, int(snapshot.get("grid_width", DEFAULT_GRID_WIDTH)))
        state.grid_height = max(MIN_GRID_HEIGHT, int(snapshot.get("grid_height", DEFAULT_GRID_HEIGHT)))
        try:
            state.cell_scale = float(snapshot.get("cell_scale", 1.0))
        except (TypeError, ValueError):
            state.cell_scale = 1.0
        state.initial_hp = int(snapshot.get("initial_hp", state.initial_hp))
        state.initial_sanity = int(snapshot.get("initial_sanity", state.initial_sanity))
        state.initial_battery = int(snapshot.get("initial_battery", state.initial_battery))
        try:
            raw_speed = float(snapshot.get("player_speed", state.player_speed))
            state.player_speed = max(PLAYER_SPEED_MIN, min(PLAYER_SPEED_MAX, raw_speed))
        except (TypeError, ValueError):
            state.player_speed = PLAYER_SPEED
        state.rooms = []
        for raw in snapshot.get("rooms", []):
            try:
                state.rooms.append(
                    Room(
                        int(raw["room_id"]),
                        int(raw["x"]),
                        int(raw["y"]),
                        max(MIN_ROOM_SIZE, int(raw["w"])),
                        max(MIN_ROOM_SIZE, int(raw["h"])),
                        str(raw.get("name", "Room")),
                        str(raw.get("number", raw["room_id"])),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        state.doors = {}
        for raw in snapshot.get("doors", []):
            try:
                symbol = str(raw["symbol"])
                if symbol in DOOR_SYMBOLS:
                    state.doors[(int(raw["x"]), int(raw["y"]))] = symbol
            except (KeyError, TypeError, ValueError):
                continue
        state.objects = {}
        for raw in snapshot.get("objects", []):
            try:
                x = int(raw["x"])
                y = int(raw["y"])
                object_id = str(raw["object_id"])
                state.objects[(x, y)] = ObjectPlacement(
                    object_id,
                    int(raw.get("rotation", 0)) % 360,
                    state._read_optional_positive_float(raw, "length"),
                    state._read_optional_positive_float(raw, "width"),
                    state._read_optional_positive_float(raw, "height"),
                    state._read_optional_non_negative_float(raw, "placement_height"),
                )
            except (KeyError, TypeError, ValueError):
                continue
        state.overrides = {}
        for raw in snapshot.get("overrides", []):
            try:
                symbol = str(raw["symbol"])
                if symbol in {"#", "."}:
                    state.overrides[(int(raw["x"]), int(raw["y"]))] = symbol
            except (KeyError, TypeError, ValueError):
                continue
        start_cell = snapshot.get("start_cell")
        state.start_cell = tuple(start_cell) if isinstance(start_cell, (list, tuple)) and len(start_cell) == 2 else None
        try:
            state.next_room_id = int(snapshot.get("next_room_id", 1 + max((room.room_id for room in state.rooms), default=0)))
        except (TypeError, ValueError):
            state.next_room_id = 1 + max((room.room_id for room in state.rooms), default=0)
        state.selected_room_id = None
        state.selected_door = None
        state.selected_object = None
        state.rebuild_grid()
        self.state = state
        self._clear_area_selection()
        self._cancel_editing_field()
        self.drag_mode = None
        self._clamp_scroll()

    def _push_history(self) -> None:
        snapshot = self._state_snapshot()
        if self.undo_stack and self.undo_stack[-1] == snapshot:
            return
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > HISTORY_LIMIT:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _push_drag_history(self) -> None:
        if self.drag_history_pushed:
            return
        self._push_history()
        self.drag_history_pushed = True

    def _undo(self) -> None:
        if not self.undo_stack:
            self.state.status = "Nothing to undo."
            return
        self.redo_stack.append(self._state_snapshot())
        snapshot = self.undo_stack.pop()
        self._restore_snapshot(snapshot)
        self.state.status = "Undo."

    def _redo(self) -> None:
        if not self.redo_stack:
            self.state.status = "Nothing to redo."
            return
        self.undo_stack.append(self._state_snapshot())
        snapshot = self.redo_stack.pop()
        self._restore_snapshot(snapshot)
        self.state.status = "Redo."

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()
        if event.key == pygame.K_z and mods & pygame.KMOD_CTRL:
            if self.editing_field is not None:
                self._cancel_editing_field()
            if mods & pygame.KMOD_SHIFT:
                self._redo()
            else:
                self._undo()
            return

        if self.editing_field is not None:
            if event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
                self._commit_editing_field()
                self.state.save()
                return
            if event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
                self._cancel_editing_field()
                self.state = MapEditorState.load(self.state.floor)
                return
            self._edit_text(event)
            return

        if event.key == pygame.K_ESCAPE:
            self.state.selected_room_id = None
            self.state.selected_door = None
            self.state.selected_object = None
            self._clear_area_selection()
            self.drag_mode = None
            self._cancel_editing_field()
        elif event.key == pygame.K_DELETE:
            self._push_history()
            if self.selection_rect is not None:
                self._delete_area_selection()
            else:
                self.state.delete_selection()
        elif event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
            self.state.save()
        elif event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
            self.state = MapEditorState.load(self.state.floor)
            self._clear_area_selection()
            self.undo_stack.clear()
            self.redo_stack.clear()
        elif event.key == pygame.K_q:
            self._push_history()
            self._rotate_active_object(-90)
        elif event.key == pygame.K_e:
            self._push_history()
            self._rotate_active_object(90)
        elif event.unicode in "123456789":
            self.active_object_symbol = event.unicode
            if self.active_tool == "object":
                self.state.status = f"Object tool uses symbol {self.active_object_symbol}."

    def _edit_text(self, event: pygame.event.Event) -> None:
        if self.editing_field in NUMERIC_FIELDS:
            self._edit_number(event)
            return

        room = self.state.selected_room()
        if room is None or self.editing_field is None:
            self._cancel_editing_field()
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._commit_editing_field()
            return
        if event.key == pygame.K_ESCAPE:
            self._cancel_editing_field()
            return
        if event.key == pygame.K_BACKSPACE:
            self.edit_buffer = self.edit_buffer[:-1]
            return
        typed = getattr(event, "unicode", "")
        if typed and typed.isprintable():
            limit = 32 if self.editing_field == "name" else 16
            self.edit_buffer = (self.edit_buffer + typed)[:limit]

    def _edit_number(self, event: pygame.event.Event) -> None:
        if self.editing_field is None:
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._commit_editing_field()
            return
        if event.key == pygame.K_ESCAPE:
            self._cancel_editing_field()
            return

        if event.key == pygame.K_BACKSPACE:
            self.edit_buffer = self.edit_buffer[:-1]
            return

        typed = getattr(event, "unicode", "")
        if typed and typed.isdigit():
            max_digits = 4 if self.editing_field in {"grid_width", "grid_height", "object_x", "object_y"} else 5
            if len(self.edit_buffer) < max_digits:
                self.edit_buffer += typed
            return
        if self.editing_field in FLOAT_NUMERIC_FIELDS:
            if typed == "." and "." not in self.edit_buffer and self.edit_buffer:
                self.edit_buffer += typed

    def _begin_editing_field(self, field: str) -> None:
        if self.editing_field == field:
            return
        self._commit_editing_field()
        if field in {"name", "number"} and self.state.selected_room() is None:
            return
        if field in OBJECT_NUMERIC_FIELDS and self.state.selected_object is None:
            return
        self.editing_field = field
        self.edit_buffer = self._editing_field_value(field)

    def _commit_editing_field(self) -> None:
        field = self.editing_field
        if field is None:
            return
        before = self._state_snapshot()
        if field in OBJECT_NUMERIC_FIELDS:
            self._set_object_numeric_field(field, self.edit_buffer)
        elif field in NUMERIC_FIELDS:
            if field in FLOAT_NUMERIC_FIELDS:
                try:
                    value = float(self.edit_buffer) if self.edit_buffer else 0.0
                except ValueError:
                    self.state.status = "Field needs a number."
                    self._cancel_editing_field()
                    return
            else:
                value = int(self.edit_buffer) if self.edit_buffer else 0
            self._set_numeric_field(field, value)
        else:
            room = self.state.selected_room()
            if room is not None:
                if field == "name":
                    room.name = self.edit_buffer[:32]
                elif field == "number":
                    room.number = self.edit_buffer[:16]
                self.state.status = "Room metadata updated."
        if self._state_snapshot() != before:
            self.undo_stack.append(before)
            if len(self.undo_stack) > HISTORY_LIMIT:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
        self._cancel_editing_field()

    def _cancel_editing_field(self) -> None:
        self.editing_field = None
        self.edit_buffer = ""

    def _editing_field_value(self, field: str) -> str:
        if field in NUMERIC_FIELDS:
            return self._numeric_field_value(field)
        room = self.state.selected_room()
        if room is None:
            return ""
        if field == "name":
            return room.name
        if field == "number":
            return room.number
        return ""

    def _numeric_field_value(self, field: str) -> str:
        if field in OBJECT_NUMERIC_FIELDS:
            return self._object_numeric_field_value(field)
        values = {
            "grid_width": self.state.grid_width,
            "grid_height": self.state.grid_height,
            "initial_hp": self.state.initial_hp,
            "initial_sanity": self.state.initial_sanity,
            "initial_battery": self.state.initial_battery,
            "player_speed": self.state.player_speed,
        }
        value = values.get(field, 0)
        return self._format_number(value) if isinstance(value, float) else str(value)

    def _object_numeric_field_value(self, field: str) -> str:
        cell = self.state.selected_object
        if cell is None:
            return "0"
        placement = self.state.objects.get(cell)
        if placement is None:
            return "0"
        length, width, height, placement_height = self.state.object_dimensions(placement)
        values = {
            "object_x": cell[0],
            "object_y": cell[1],
            "object_footprint_w": length,
            "object_footprint_d": width,
            "object_height": height,
            "object_z": placement_height,
        }
        return self._format_number(values.get(field, 0))

    def _format_number(self, value: float | int) -> str:
        if isinstance(value, int) or abs(value - int(value)) < 0.001:
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _set_numeric_field(self, field: str, value: int | float) -> None:
        if field == "grid_width":
            self.state.resize_grid(max(MIN_GRID_WIDTH, int(value)), self.state.grid_height)
        elif field == "grid_height":
            self.state.resize_grid(self.state.grid_width, max(MIN_GRID_HEIGHT, int(value)))
        elif field == "initial_hp":
            self.state.initial_hp = max(0, min(999, int(value)))
        elif field == "initial_sanity":
            self.state.initial_sanity = max(0, min(999, int(value)))
        elif field == "initial_battery":
            self.state.initial_battery = max(0, min(999, int(value)))
        elif field == "player_speed":
            self.state.player_speed = max(PLAYER_SPEED_MIN, min(PLAYER_SPEED_MAX, float(value)))

    def _set_object_numeric_field(self, field: str, text: str) -> None:
        cell = self.state.selected_object
        if cell is None:
            return
        try:
            raw_value = float(text) if text else 0.0
        except ValueError:
            self.state.status = "Object field needs a number."
            return

        if field == "object_x":
            self.state.update_selected_object(anchor=(max(0, int(raw_value)), cell[1]))
        elif field == "object_y":
            self.state.update_selected_object(anchor=(cell[0], max(0, int(raw_value))))
        elif field == "object_footprint_w":
            self.state.update_selected_object(length=max(0.05, raw_value))
        elif field == "object_footprint_d":
            self.state.update_selected_object(width=max(0.05, raw_value))
        elif field == "object_height":
            self.state.update_selected_object(height=max(0.05, raw_value))
        elif field == "object_z":
            self.state.update_selected_object(placement_height=max(0.0, raw_value))

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 4:
            if self.viewport_rect.collidepoint(event.pos):
                self._zoom_view_at(event.pos, 1)
                return
            self._scroll_area_at(event.pos, -SIDE_SCROLL_STEP)
            return
        if event.button == 5:
            if self.viewport_rect.collidepoint(event.pos):
                self._zoom_view_at(event.pos, -1)
                return
            self._scroll_area_at(event.pos, SIDE_SCROLL_STEP)
            return
        if event.button != 1:
            return

        pos = event.pos
        if self.editing_field is not None and not self.panel_rect.collidepoint(pos):
            self._commit_editing_field()
        if self._handle_side_scrollbar_down(pos):
            return
        button = self._button_at(pos)
        if button is not None:
            _, _, action, payload = button
            self._activate_button(action, payload)
            if action != "command":
                self.drag_mode = "toolbar"
            return

        if self._handle_panel_click(pos):
            return
        if self._handle_horizontal_scrollbar_down(pos):
            return

        cell = self._cell_from_pos(pos)
        if cell is None:
            return

        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.active_tool = "select"
            self._begin_box_selection(cell)
        elif self.active_tool == "select" and self._begin_object_resize_at(pos):
            self._push_drag_history()
            return
        elif self.active_tool == "select" and self._begin_area_move(cell):
            self._push_drag_history()
            return
        elif self.active_tool == "select":
            self._begin_select_drag(cell)
            if self.drag_mode in {"move_room", "resize_room"}:
                self._push_drag_history()
        elif self.active_tool == "room":
            self._clear_area_selection()
            self.drag_mode = "create_room"
            self.drag_start_cell = cell
            self.drag_current_cell = cell
        elif self.active_tool == "door":
            self._clear_area_selection()
            self.drag_mode = "place_door"
            self.drag_current_cell = cell
        else:
            self._clear_area_selection()
            self.drag_mode = "paint"
            self._push_drag_history()
            self._paint_cell(cell)

    def _handle_mouse_wheel(self, event: pygame.event.Event) -> None:
        pos = pygame.mouse.get_pos()
        if self.viewport_rect.collidepoint(pos):
            self._zoom_view_at(pos, event.y)
            return
        self._scroll_area_at(pos, -event.y * SIDE_SCROLL_STEP)

    def _zoom_view_at(self, pos: tuple[int, int], wheel_delta: int) -> None:
        if wheel_delta == 0:
            return
        old_size = self.cell_size
        factor = VIEW_ZOOM_STEP if wheel_delta > 0 else 1.0 / VIEW_ZOOM_STEP
        new_size = int(round(old_size * factor))
        new_size = max(MIN_VIEW_CELL_SIZE, min(MAX_VIEW_CELL_SIZE, new_size))
        if new_size == old_size:
            return

        viewport = self.viewport_rect
        world_x = (pos[0] - viewport.x + self.scroll_x) / old_size
        world_y = (pos[1] - viewport.y + self.scroll_y) / old_size
        self.cell_size = new_size
        self.scroll_x = int(round(world_x * new_size - (pos[0] - viewport.x)))
        self.scroll_y = int(round(world_y * new_size - (pos[1] - viewport.y)))
        self._clamp_scroll()
        self.state.status = f"Canvas zoom: {self.cell_size}px per cell."

    def _scroll_area_at(self, pos: tuple[int, int], amount: int) -> None:
        if self.toolbar_rect.collidepoint(pos):
            self.toolbar_scroll_y += amount
            self._clamp_side_scrolls()
            return
        if self.panel_rect.collidepoint(pos):
            self.panel_scroll_y += amount
            self._clamp_side_scrolls()
            return
        self.scroll_y += amount
        self._clamp_scroll()

    def _button_at(self, pos: tuple[int, int]) -> tuple[pygame.Rect, str, str, str | None] | None:
        if not self.toolbar_rect.collidepoint(pos):
            return None
        content_pos = (pos[0], pos[1] + self.toolbar_scroll_y)
        for button in self.buttons:
            if button[0].collidepoint(content_pos):
                return button
        return None

    def _activate_button(self, action: str, payload: str | None) -> None:
        if action == "command":
            self._commit_editing_field()
            if payload == "save":
                self.state.save()
            elif payload == "load":
                self.state = MapEditorState.load(self.state.floor)
                self._clear_area_selection()
                self.undo_stack.clear()
                self.redo_stack.clear()
            elif payload == "clear":
                self._push_history()
                self._clear_area_selection()
                self.drag_mode = None
                self.state.clear_map()
                self.active_tool = "select"
            elif payload == "rotate_ccw":
                self._push_history()
                self._rotate_active_object(-90)
            elif payload == "rotate_cw":
                self._push_history()
                self._rotate_active_object(90)
            return
        self.active_tool = action
        if action == "door" and payload is not None:
            self.active_door_symbol = payload
        self.state.status = f"Tool: {self._tool_label()}."

    def _handle_panel_click(self, pos: tuple[int, int]) -> bool:
        if not self.panel_rect.collidepoint(pos):
            return False
        for floor, rect in self.floor_buttons.items():
            if rect.collidepoint(pos):
                self._commit_editing_field()
                self._switch_floor(floor)
                return True
        if self.object_dropdown_rect.collidepoint(pos):
            self._commit_editing_field()
            self.object_dropdown_open = not self.object_dropdown_open
            return True
        if self.object_dropdown_open:
            for object_id, rect in self.object_buttons.items():
                if rect.collidepoint(pos):
                    self._commit_editing_field()
                    if self.state.selected_object is not None:
                        self._push_history()
                        self.state.update_selected_object_asset(object_id)
                    self.active_tool = "object"
                    self.active_object_symbol = object_id
                    self.object_dropdown_open = False
                    self.state.status = f"Object tool uses {self.state.object_label(object_id)}."
                    return True
            self.object_dropdown_open = False
        if self.auto_wall_snap_rect.collidepoint(pos):
            self._commit_editing_field()
            self.auto_wall_snap = not self.auto_wall_snap
            state = "on" if self.auto_wall_snap else "off"
            self.state.status = f"Auto wall snap {state}."
            return True
        if self.map_scale_track_rect.collidepoint(pos) or any(rect.collidepoint(pos) for rect in self.map_scale_tick_rects.values()):
            self._commit_editing_field()
            self.drag_mode = "map_scale_slider"
            self._set_map_scale_from_panel_x(pos[0])
            return True
        for field, rect in self.panel_fields.items():
            if rect.collidepoint(pos):
                self._begin_editing_field(field)
                return True
        self._commit_editing_field()
        return True

    def _set_map_scale_from_panel_x(self, screen_x: int) -> None:
        track = self.map_scale_track_rect
        if track.width <= 0:
            return
        values = list(MAP_SCALE_VALUES)
        positions: dict[float, int] = {}
        for index, value in enumerate(values):
            t = index / max(1, len(values) - 1)
            positions[value] = int(round(track.x + t * track.width))
        target = min(values, key=lambda value: abs(screen_x - positions[value]))
        if abs(target - self.state.cell_scale) < 0.001:
            return

        current_scale = self.state.cell_scale if self.state.cell_scale > 0 else 1.0
        ratio = target / current_scale
        viewport = self.viewport_rect
        center_x = (self.scroll_x + viewport.width / 2) / self.cell_size
        center_y = (self.scroll_y + viewport.height / 2) / self.cell_size
        self._push_history()
        if self.state.set_cell_scale(target):
            self.scroll_x = int(round(center_x * ratio * self.cell_size - viewport.width / 2))
            self.scroll_y = int(round(center_y * ratio * self.cell_size - viewport.height / 2))
            self._clamp_scroll()
            self._clear_area_selection()

    def _switch_floor(self, floor: int) -> None:
        self._commit_editing_field()
        floor = max(BOTTOM_FLOOR, min(TOP_FLOOR, floor))
        if floor == self.state.floor:
            return
        self.state.save()
        self.state = MapEditorState.load(floor)
        self._cancel_editing_field()
        self.drag_mode = None
        self.scroll_x = 0
        self.scroll_y = 0
        self.undo_stack.clear()
        self.redo_stack.clear()

    def _handle_side_scrollbar_down(self, pos: tuple[int, int]) -> bool:
        if self._max_toolbar_scroll_y() > 0 and self._side_scrollbar_track_rect(self.toolbar_rect).collidepoint(pos):
            thumb = self._side_scrollbar_thumb_rect(self.toolbar_rect, self.toolbar_scroll_y, self.toolbar_content_height)
            if thumb.collidepoint(pos):
                self.side_scrollbar_drag_offset = pos[1] - thumb.y
            else:
                self.side_scrollbar_drag_offset = thumb.height // 2
                self._set_toolbar_scroll_from_thumb(pos[1] - self.side_scrollbar_drag_offset)
            self.drag_mode = "toolbar_v_scrollbar"
            return True
        if self._max_panel_scroll_y() > 0 and self._side_scrollbar_track_rect(self.panel_rect).collidepoint(pos):
            thumb = self._side_scrollbar_thumb_rect(self.panel_rect, self.panel_scroll_y, self.panel_content_height)
            if thumb.collidepoint(pos):
                self.side_scrollbar_drag_offset = pos[1] - thumb.y
            else:
                self.side_scrollbar_drag_offset = thumb.height // 2
                self._set_panel_scroll_from_thumb(pos[1] - self.side_scrollbar_drag_offset)
            self.drag_mode = "panel_v_scrollbar"
            return True
        return False

    def _rotate_active_object(self, delta: int) -> None:
        if self.state.selected_object is not None:
            placement = self.state.objects.get(self.state.selected_object)
            if placement is not None:
                rotated = replace(placement, rotation=(placement.rotation + delta) % 360)
                if not self.state._object_fits(self.state.selected_object, rotated, ignore_anchor=self.state.selected_object):
                    self.state.status = "Rotated object would overlap blocked cells."
                    return
                self.state.objects[self.state.selected_object] = rotated
                self.active_object_rotation = rotated.rotation
                self.state.rebuild_grid()
                self.state.status = f"Rotated {self.state.object_label(rotated.object_id)} to {rotated.rotation} deg."
                return
        self.active_object_rotation = (self.active_object_rotation + delta) % 360
        self.state.status = f"Placement rotation: {self.active_object_rotation} deg."

    def _begin_object_resize_at(self, pos: tuple[int, int]) -> bool:
        handle = self._object_resize_handle_at(pos)
        if handle is None or self.state.selected_object is None:
            return False
        placement = self.state.objects.get(self.state.selected_object)
        if placement is None:
            return False
        self._clear_area_selection()
        self.drag_mode = "resize_object"
        self.drag_initial_object = (self.state.selected_object, replace(placement), handle)
        self.drag_start_cell = self.state.selected_object
        self.drag_current_cell = self.state.selected_object
        self.state.status = "Drag object corner to resize footprint."
        return True

    def _object_resize_handle_at(self, pos: tuple[int, int]) -> str | None:
        anchor = self.state.selected_object
        if anchor is None:
            return None
        placement = self.state.objects.get(anchor)
        if placement is None:
            return None
        for handle, rect in self._object_resize_handle_rects(anchor, placement).items():
            if rect.collidepoint(pos):
                return handle
        return None

    def _object_resize_handle_rects(self, anchor: tuple[int, int], placement: ObjectPlacement) -> dict[str, pygame.Rect]:
        width, height = self.state.object_footprint_size(placement)
        sx, sy = self._screen_from_cell(*anchor)
        rect = pygame.Rect(sx, sy, width * self.cell_size, height * self.cell_size)
        half = OBJECT_HANDLE_SIZE // 2
        points = {
            "nw": rect.topleft,
            "ne": rect.topright,
            "sw": rect.bottomleft,
            "se": rect.bottomright,
        }
        return {
            handle: pygame.Rect(point[0] - half, point[1] - half, OBJECT_HANDLE_SIZE, OBJECT_HANDLE_SIZE)
            for handle, point in points.items()
        }

    def _begin_select_drag(self, cell: tuple[int, int]) -> None:
        if cell in self.state.doors:
            self._clear_area_selection()
            self.state.selected_door = cell
            self.state.selected_room_id = None
            self.state.selected_object = None
            return
        object_anchor = self.state.object_anchor_at(cell)
        if object_anchor is not None:
            self._clear_area_selection()
            self.state.selected_object = object_anchor
            self.state.selected_room_id = None
            self.state.selected_door = None
            return
        room = self.state.room_at(cell)
        if room is None:
            self._clear_area_selection()
            self.state.selected_room_id = None
            self.state.selected_door = None
            self.state.selected_object = None
            return

        self._clear_area_selection()
        self.state.selected_room_id = room.room_id
        self.state.selected_door = None
        self.state.selected_object = None
        self.drag_start_cell = cell
        self.drag_initial_room = (room.x, room.y, room.w, room.h)
        if cell == room.handle_cell():
            self.drag_mode = "resize_room"
        else:
            self.drag_mode = "move_room"

    def _begin_box_selection(self, cell: tuple[int, int]) -> None:
        self._clear_individual_selection()
        self.selection_rect = None
        self.selection_items = self._empty_selection_items()
        self.drag_mode = "box_select"
        self.drag_start_cell = cell
        self.drag_current_cell = cell

    def _finish_box_selection(self) -> None:
        if self.drag_start_cell is None or self.drag_current_cell is None:
            return
        rect = self._normalized_cell_rect(self.drag_start_cell, self.drag_current_cell)
        self._select_area(rect)

    def _begin_area_move(self, cell: tuple[int, int]) -> bool:
        if self.selection_rect is None or not self._cell_in_rect(cell, self.selection_rect):
            return False
        if self._selection_item_count(self.selection_items) == 0:
            self._clear_area_selection()
            return False
        self._clear_individual_selection()
        self.drag_mode = "move_selection"
        self.drag_start_cell = cell
        self.drag_current_cell = cell
        self.selection_move_snapshot = self._capture_selection_move_snapshot()
        return True

    def _finish_area_move(self) -> None:
        if self.selection_rect is None:
            return
        self.selection_items = self._collect_area_items(self.selection_rect)
        count = self._selection_item_count(self.selection_items)
        if count == 0:
            self._clear_area_selection()
            return
        self.state.status = f"Moved selected area ({count} item(s))."

    def _move_area_selection(self, cell: tuple[int, int]) -> None:
        if self.drag_start_cell is None or self.selection_move_snapshot is None:
            return
        start_x, start_y = self.drag_start_cell
        dx = cell[0] - start_x
        dy = cell[1] - start_y
        rect = self.selection_move_snapshot["rect"]
        if not isinstance(rect, tuple):
            return
        dx, dy = self._clamp_selection_delta(rect, dx, dy)

        room_positions = self.selection_move_snapshot["rooms"]
        if isinstance(room_positions, dict):
            for room in self.state.rooms:
                original = room_positions.get(room.room_id)
                if original is None:
                    continue
                x, y, w, h = original
                room.x = x + dx
                room.y = y + dy
                room.w = w
                room.h = h

        self.state.doors = self._move_cell_dict_snapshot("doors", dx, dy)
        self.state.objects = self._move_cell_dict_snapshot("objects", dx, dy)
        self.state.overrides = self._move_cell_dict_snapshot("overrides", dx, dy)

        start_cell = self.selection_move_snapshot.get("start_cell")
        start_selected = bool(self.selection_move_snapshot.get("start_selected"))
        if start_selected and isinstance(start_cell, tuple):
            self.state.start_cell = (start_cell[0] + dx, start_cell[1] + dy)
        elif isinstance(start_cell, tuple):
            self.state.start_cell = start_cell
        else:
            self.state.start_cell = None

        self.selection_rect = self._translate_cell_rect(rect, dx, dy)
        self.state.rebuild_grid()

    def _move_cell_dict_snapshot(self, key: str, dx: int, dy: int) -> dict:
        base = self.selection_move_snapshot.get(f"base_{key}") if self.selection_move_snapshot else None
        selected = self.selection_move_snapshot.get(f"selected_{key}") if self.selection_move_snapshot else None
        moved: dict = dict(base) if isinstance(base, dict) else {}
        if isinstance(selected, dict):
            for (x, y), symbol in selected.items():
                moved[(x + dx, y + dy)] = symbol
        return moved

    def _capture_selection_move_snapshot(self) -> dict[str, object]:
        room_ids = self.selection_items["rooms"]
        door_cells = self.selection_items["doors"]
        object_cells = self.selection_items["objects"]
        override_cells = self.selection_items["overrides"]
        return {
            "rect": self.selection_rect,
            "rooms": {
                room.room_id: (room.x, room.y, room.w, room.h)
                for room in self.state.rooms
                if room.room_id in room_ids
            },
            "base_doors": {cell: symbol for cell, symbol in self.state.doors.items() if cell not in door_cells},
            "selected_doors": {cell: symbol for cell, symbol in self.state.doors.items() if cell in door_cells},
            "base_objects": {cell: symbol for cell, symbol in self.state.objects.items() if cell not in object_cells},
            "selected_objects": {cell: symbol for cell, symbol in self.state.objects.items() if cell in object_cells},
            "base_overrides": {cell: symbol for cell, symbol in self.state.overrides.items() if cell not in override_cells},
            "selected_overrides": {cell: symbol for cell, symbol in self.state.overrides.items() if cell in override_cells},
            "start_cell": self.state.start_cell,
            "start_selected": bool(self.selection_items["start"]),
        }

    def _select_area(self, rect: tuple[int, int, int, int]) -> None:
        self.selection_rect = rect
        self.selection_items = self._collect_area_items(rect)
        count = self._selection_item_count(self.selection_items)
        if count == 0:
            self._clear_area_selection()
            self.state.status = "Selection is empty."
            return
        self._clear_individual_selection()
        self.state.status = f"Selected area ({count} item(s)). Drag inside it to move."

    def _collect_area_items(self, rect: tuple[int, int, int, int]) -> dict[str, object]:
        items = self._empty_selection_items()

        object_cells = items["objects"]
        for cell, placement in self.state.objects.items():
            if any(self._cell_in_rect(footprint_cell, rect) for footprint_cell in self.state.object_footprint_cells(cell, placement)):
                object_cells.add(cell)
        if object_cells:
            return items

        door_cells = items["doors"]
        for cell in self.state.doors:
            if self._cell_in_rect(cell, rect):
                door_cells.add(cell)
        if door_cells:
            return items

        for cell in self.state.overrides:
            if self._cell_in_rect(cell, rect):
                items["overrides"].add(cell)
        if self.state.start_cell is not None and self._cell_in_rect(self.state.start_cell, rect):
            items["start"] = True
        if items["overrides"] or items["start"]:
            return items

        room_ids = items["rooms"]
        for room in self.state.rooms:
            if self._room_intersects_rect(room, rect):
                room_ids.add(room.room_id)
        return items

    def _delete_area_selection(self) -> None:
        room_ids = self.selection_items["rooms"]
        self.state.rooms = [room for room in self.state.rooms if room.room_id not in room_ids]
        for cell in list(self.selection_items["doors"]):
            self.state.doors.pop(cell, None)
        for cell in list(self.selection_items["objects"]):
            self.state.objects.pop(cell, None)
        for cell in list(self.selection_items["overrides"]):
            self.state.overrides.pop(cell, None)
        if self.selection_items["start"]:
            self.state.start_cell = None
        self._clear_area_selection()
        self.state.rebuild_grid()
        self.state.status = "Deleted selected area."

    def _clear_individual_selection(self) -> None:
        self.state.selected_room_id = None
        self.state.selected_door = None
        self.state.selected_object = None

    def _clear_area_selection(self) -> None:
        self.selection_rect = None
        self.selection_items = self._empty_selection_items()
        self.selection_move_snapshot = None

    def _empty_selection_items(self) -> dict[str, object]:
        return {
            "rooms": set(),
            "doors": set(),
            "objects": set(),
            "overrides": set(),
            "start": False,
        }

    def _selection_item_count(self, items: dict[str, object]) -> int:
        total = 0
        for key in ("rooms", "doors", "objects", "overrides"):
            values = items.get(key)
            if isinstance(values, set):
                total += len(values)
        if items.get("start"):
            total += 1
        return total

    def _normalized_cell_rect(self, start: tuple[int, int], end: tuple[int, int]) -> tuple[int, int, int, int]:
        min_x, max_x = sorted((start[0], end[0]))
        min_y, max_y = sorted((start[1], end[1]))
        return min_x, min_y, max_x, max_y

    def _translate_cell_rect(self, rect: tuple[int, int, int, int], dx: int, dy: int) -> tuple[int, int, int, int]:
        min_x, min_y, max_x, max_y = rect
        return min_x + dx, min_y + dy, max_x + dx, max_y + dy

    def _clamp_selection_delta(self, rect: tuple[int, int, int, int], dx: int, dy: int) -> tuple[int, int]:
        min_x, min_y, _, _ = rect
        if min_x + dx < 0:
            dx = -min_x
        if min_y + dy < 0:
            dy = -min_y
        return dx, dy

    def _cell_in_rect(self, cell: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
        x, y = cell
        min_x, min_y, max_x, max_y = rect
        return min_x <= x <= max_x and min_y <= y <= max_y

    def _room_intersects_rect(self, room: Room, rect: tuple[int, int, int, int]) -> bool:
        min_x, min_y, max_x, max_y = rect
        room_max_x = room.x + room.w - 1
        room_max_y = room.y + room.h - 1
        return not (room_max_x < min_x or room.x > max_x or room_max_y < min_y or room.y > max_y)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button != 1:
            return
        if self.drag_mode == "box_select" and self.drag_start_cell and self.drag_current_cell:
            self._finish_box_selection()
        elif self.drag_mode == "move_selection":
            self._finish_area_move()
        elif self.drag_mode == "create_room" and self.drag_start_cell and self.drag_current_cell:
            self._push_drag_history()
            self.state.add_room(*self.drag_start_cell, *self.drag_current_cell)
        elif self.drag_mode == "place_door" and self.drag_current_cell:
            self._push_drag_history()
            self.state.place_door(self.drag_current_cell, self.active_door_symbol)
        elif self.drag_mode == "toolbar":
            cell = self._cell_from_pos(event.pos)
            if cell is not None and self.active_tool == "door":
                self._push_drag_history()
                self.state.place_door(cell, self.active_door_symbol)
            elif cell is not None and self.active_tool == "room":
                self._push_drag_history()
                self.state.add_room(cell[0], cell[1], cell[0] + MIN_ROOM_SIZE - 1, cell[1] + MIN_ROOM_SIZE - 1)
            elif cell is not None and self.active_tool == "object":
                self._push_drag_history()
                self._place_active_object(cell)
        self.drag_mode = None
        self.drag_history_pushed = False
        self.drag_start_cell = None
        self.drag_current_cell = None
        self.drag_initial_room = None
        self.drag_initial_object = None
        self.selection_move_snapshot = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        self.hover_cell = self._cell_from_pos(event.pos)
        if self.drag_mode == "toolbar_v_scrollbar":
            self._set_toolbar_scroll_from_thumb(event.pos[1] - self.side_scrollbar_drag_offset)
            return
        if self.drag_mode == "panel_v_scrollbar":
            self._set_panel_scroll_from_thumb(event.pos[1] - self.side_scrollbar_drag_offset)
            return
        if self.drag_mode == "h_scrollbar":
            self._set_scroll_x_from_thumb(event.pos[0] - self.scrollbar_drag_offset)
            return
        if self.drag_mode == "map_scale_slider":
            self._set_map_scale_from_panel_x(event.pos[0])
            return
        if event.buttons[1] or event.buttons[2]:
            self.scroll_x = max(0, self.scroll_x - event.rel[0])
            self.scroll_y = max(0, self.scroll_y - event.rel[1])
            self._clamp_scroll()
            return
        if not event.buttons[0]:
            return

        cell = self._cell_from_pos(event.pos)
        if cell is None:
            return
        if self.drag_mode == "box_select":
            self.drag_current_cell = cell
            return
        if self.drag_mode == "move_selection":
            self.drag_current_cell = cell
            self._move_area_selection(cell)
            return
        if self.drag_mode == "resize_object":
            self.drag_current_cell = cell
            self._resize_selected_object_from_corner(cell)
            return
        if self.drag_mode == "toolbar":
            if self.active_tool == "room":
                self.drag_mode = "create_room"
                self.drag_start_cell = cell
                self.drag_current_cell = cell
            elif self.active_tool == "door":
                self.drag_mode = "place_door"
                self.drag_current_cell = cell
            elif self.active_tool == "object":
                self._push_drag_history()
                self._place_active_object(cell)
            return
        self.drag_current_cell = cell
        if self.drag_mode == "move_room":
            self._move_selected_room(cell)
        elif self.drag_mode == "resize_room":
            self._resize_selected_room(cell)
        elif self.active_tool in {"wall", "erase", "start", "object"}:
            self._paint_cell(cell)

    def _move_selected_room(self, cell: tuple[int, int]) -> None:
        room = self.state.selected_room()
        if room is None or self.drag_start_cell is None or self.drag_initial_room is None:
            return
        start_x, start_y = self.drag_start_cell
        init_x, init_y, init_w, init_h = self.drag_initial_room
        dx = cell[0] - start_x
        dy = cell[1] - start_y
        room.x = max(0, init_x + dx)
        room.y = max(0, init_y + dy)
        room.w = init_w
        room.h = init_h
        self.state.rebuild_grid()

    def _resize_selected_object_from_corner(self, cell: tuple[int, int]) -> None:
        if self.drag_initial_object is None:
            return
        original_anchor, original_placement, handle = self.drag_initial_object
        current_anchor = self.state.selected_object
        if current_anchor is None or current_anchor not in self.state.objects:
            return

        original_width, original_height = self.state.object_footprint_size(original_placement)
        left = original_anchor[0]
        top = original_anchor[1]
        right = left + original_width - 1
        bottom = top + original_height - 1

        if "w" in handle:
            new_left = max(0, min(cell[0], right))
            new_right = right
        else:
            new_left = left
            new_right = max(left, cell[0])

        if "n" in handle:
            new_top = max(0, min(cell[1], bottom))
            new_bottom = bottom
        else:
            new_top = top
            new_bottom = max(top, cell[1])

        visible_width = max(1, new_right - new_left + 1)
        visible_height = max(1, new_bottom - new_top + 1)
        rotation = original_placement.rotation % 360
        if rotation in (90, 270):
            length = float(visible_height)
            width = float(visible_width)
        else:
            length = float(visible_width)
            width = float(visible_height)

        if self.state.update_selected_object(anchor=(new_left, new_top), length=length, width=width):
            self.state.status = f"Object footprint resized to {visible_width} x {visible_height}."

    def _resize_selected_room(self, cell: tuple[int, int]) -> None:
        room = self.state.selected_room()
        if room is None or self.drag_initial_room is None:
            return
        init_x, init_y, _, _ = self.drag_initial_room
        room.x = init_x
        room.y = init_y
        room.w = max(MIN_ROOM_SIZE, cell[0] - init_x + 1)
        room.h = max(MIN_ROOM_SIZE, cell[1] - init_y + 1)
        self.state.rebuild_grid()

    def _paint_cell(self, cell: tuple[int, int]) -> None:
        if self.active_tool == "wall":
            self.state.place_wall(cell)
        elif self.active_tool == "erase":
            self.state.erase_cell(cell)
        elif self.active_tool == "start":
            self.state.place_start(cell)
        elif self.active_tool == "object":
            self._place_active_object(cell)

    def _place_active_object(self, cell: tuple[int, int]) -> None:
        self.state.place_object(
            cell,
            self.active_object_symbol,
            self.active_object_rotation,
            auto_wall_snap=self.auto_wall_snap,
        )
        if self.state.selected_object is not None:
            placement = self.state.objects.get(self.state.selected_object)
            if placement is not None:
                self.active_object_rotation = placement.rotation

    def _handle_horizontal_scrollbar_down(self, pos: tuple[int, int]) -> bool:
        track = self._horizontal_scrollbar_track_rect()
        if not track.collidepoint(pos) or self._max_scroll_x() <= 0:
            return False
        thumb = self._horizontal_scrollbar_thumb_rect()
        if thumb.collidepoint(pos):
            self.scrollbar_drag_offset = pos[0] - thumb.x
        else:
            self.scrollbar_drag_offset = thumb.width // 2
            self._set_scroll_x_from_thumb(pos[0] - self.scrollbar_drag_offset)
        self.drag_mode = "h_scrollbar"
        return True

    def _horizontal_scrollbar_track_rect(self) -> pygame.Rect:
        canvas = self.canvas_rect
        return pygame.Rect(canvas.x + 8, canvas.bottom - H_SCROLLBAR_HEIGHT + 4, canvas.width - 16, H_SCROLLBAR_HEIGHT - 8)

    def _horizontal_scrollbar_thumb_rect(self) -> pygame.Rect:
        track = self._horizontal_scrollbar_track_rect()
        content_width = max(1, self.state.grid_width * self.cell_size)
        visible_width = max(1, self.viewport_rect.width)
        if content_width <= visible_width:
            return track.copy()
        thumb_width = max(H_SCROLLBAR_MIN_THUMB_WIDTH, int(track.width * visible_width / content_width))
        thumb_width = min(track.width, thumb_width)
        travel = max(1, track.width - thumb_width)
        thumb_x = track.x + int((self.scroll_x / self._max_scroll_x()) * travel)
        return pygame.Rect(thumb_x, track.y, thumb_width, track.height)

    def _set_scroll_x_from_thumb(self, thumb_left: int) -> None:
        max_scroll = self._max_scroll_x()
        if max_scroll <= 0:
            self.scroll_x = 0
            return
        track = self._horizontal_scrollbar_track_rect()
        thumb = self._horizontal_scrollbar_thumb_rect()
        travel = max(1, track.width - thumb.width)
        clamped_left = max(track.x, min(track.x + travel, thumb_left))
        self.scroll_x = int(round((clamped_left - track.x) / travel * max_scroll))
        self._clamp_scroll()

    def _side_scrollbar_track_rect(self, area: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(area.right - V_SCROLLBAR_WIDTH + 2, area.y + 8, V_SCROLLBAR_WIDTH - 4, max(1, area.height - 16))

    def _side_scrollbar_thumb_rect(self, area: pygame.Rect, scroll_y: int, content_height: int) -> pygame.Rect:
        track = self._side_scrollbar_track_rect(area)
        if content_height <= area.height:
            return track.copy()
        thumb_height = max(V_SCROLLBAR_MIN_THUMB_HEIGHT, int(track.height * area.height / max(1, content_height)))
        thumb_height = min(track.height, thumb_height)
        travel = max(1, track.height - thumb_height)
        max_scroll = max(1, content_height - area.height)
        thumb_y = track.y + int((scroll_y / max_scroll) * travel)
        return pygame.Rect(track.x, thumb_y, track.width, thumb_height)

    def _set_toolbar_scroll_from_thumb(self, thumb_top: int) -> None:
        self.toolbar_scroll_y = self._scroll_from_side_thumb(self.toolbar_rect, self.toolbar_content_height, thumb_top)
        self._clamp_side_scrolls()

    def _set_panel_scroll_from_thumb(self, thumb_top: int) -> None:
        self.panel_scroll_y = self._scroll_from_side_thumb(self.panel_rect, self.panel_content_height, thumb_top)
        self._clamp_side_scrolls()

    def _scroll_from_side_thumb(self, area: pygame.Rect, content_height: int, thumb_top: int) -> int:
        max_scroll = max(0, content_height - area.height)
        if max_scroll <= 0:
            return 0
        track = self._side_scrollbar_track_rect(area)
        thumb = self._side_scrollbar_thumb_rect(area, 0, content_height)
        travel = max(1, track.height - thumb.height)
        clamped_top = max(track.y, min(track.y + travel, thumb_top))
        return int(round((clamped_top - track.y) / travel * max_scroll))

    def _draw_side_scrollbar(self, area: pygame.Rect, scroll_y: int, content_height: int, active: bool) -> None:
        if content_height <= area.height:
            return
        track = self._side_scrollbar_track_rect(area)
        pygame.draw.rect(self.screen, (35, 43, 45), track, border_radius=3)
        thumb = self._side_scrollbar_thumb_rect(area, scroll_y, content_height)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else (102, 119, 121), thumb, border_radius=3)

    def _max_scroll_x(self) -> int:
        return max(0, self.state.grid_width * self.cell_size - self.viewport_rect.width)

    def _max_scroll_y(self) -> int:
        return max(0, self.state.grid_height * self.cell_size - self.viewport_rect.height)

    def _max_toolbar_scroll_y(self) -> int:
        return max(0, self.toolbar_content_height - self.toolbar_rect.height)

    def _max_panel_scroll_y(self) -> int:
        return max(0, self.panel_content_height - self.panel_rect.height)

    def _clamp_scroll(self) -> None:
        self.scroll_x = max(0, min(self.scroll_x, self._max_scroll_x()))
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll_y()))

    def _clamp_side_scrolls(self) -> None:
        self.toolbar_scroll_y = max(0, min(self.toolbar_scroll_y, self._max_toolbar_scroll_y()))
        self.panel_scroll_y = max(0, min(self.panel_scroll_y, self._max_panel_scroll_y()))

    def _cell_from_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        viewport = self.viewport_rect
        if not viewport.collidepoint(pos):
            return None
        x = (pos[0] - viewport.x + self.scroll_x) // self.cell_size
        y = (pos[1] - viewport.y + self.scroll_y) // self.cell_size
        if x < 0 or y < 0:
            return None
        if x >= self.state.grid_width or y >= self.state.grid_height:
            return None
        return int(x), int(y)

    def _screen_from_cell(self, x: int, y: int) -> tuple[int, int]:
        viewport = self.viewport_rect
        return viewport.x + x * self.cell_size - self.scroll_x, viewport.y + y * self.cell_size - self.scroll_y

    def _draw(self) -> None:
        self.screen.fill(COLOR_BG)
        self._draw_toolbar()
        self._draw_canvas()
        self._draw_panel()
        self._draw_status()
        pygame.display.flip()

    def _draw_toolbar(self) -> None:
        toolbar = self.toolbar_rect
        self._clamp_side_scrolls()
        pygame.draw.rect(self.screen, COLOR_TOOLBAR, toolbar)
        clip = self.screen.get_clip()
        self.screen.set_clip(toolbar)
        self._draw_text("Map Editor", (16, 8 - self.toolbar_scroll_y), self.big_font, COLOR_TEXT)
        for rect, label, action, payload in self.buttons:
            draw_rect = rect.move(0, -self.toolbar_scroll_y)
            if not draw_rect.colliderect(toolbar):
                continue
            selected = action == self.active_tool
            if action == "door" and payload != self.active_door_symbol:
                selected = False
            color = (58, 68, 70) if selected else (38, 45, 48)
            pygame.draw.rect(self.screen, color, draw_rect, border_radius=4)
            pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, draw_rect, 1, border_radius=4)
            self._draw_text(label, (draw_rect.x + 8, draw_rect.y + 6), self.small_font, COLOR_TEXT)

        y = self.toolbar_help_y - self.toolbar_scroll_y
        for line in self._toolbar_help_lines():
            self._draw_text(line, (14, y), self.small_font, COLOR_MUTED)
            y += 20
        self.screen.set_clip(clip)
        self._draw_side_scrollbar(toolbar, self.toolbar_scroll_y, self.toolbar_content_height, self.drag_mode == "toolbar_v_scrollbar")
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, toolbar, 1)

    def _draw_canvas(self) -> None:
        canvas = self.canvas_rect
        viewport = self.viewport_rect
        self._clamp_scroll()
        pygame.draw.rect(self.screen, (14, 17, 18), canvas)
        clip = self.screen.get_clip()
        self.screen.set_clip(viewport)

        start_x = max(0, self.scroll_x // self.cell_size)
        start_y = max(0, self.scroll_y // self.cell_size)
        end_x = min(self.state.grid_width, start_x + viewport.width // self.cell_size + 3)
        end_y = min(self.state.grid_height, start_y + viewport.height // self.cell_size + 3)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                sx, sy = self._screen_from_cell(x, y)
                char = self.state.grid[y][x]
                rect = pygame.Rect(sx, sy, self.cell_size, self.cell_size)
                pygame.draw.rect(self.screen, self._cell_color(char), rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)
                if char in DOOR_SYMBOLS or char == "@" or (char in "123456789" and (x, y) not in self.state.objects):
                    self._draw_centered_text(char, rect, self.small_font, COLOR_TEXT)

        self._draw_objects_overlay()
        for room in self.state.rooms:
            self._draw_room_overlay(room)
        self._draw_drag_preview()
        self._draw_door_preview()
        self._draw_area_selection()
        self.screen.set_clip(clip)
        self._draw_horizontal_scrollbar()
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, canvas, 1)

    def _draw_horizontal_scrollbar(self) -> None:
        track = self._horizontal_scrollbar_track_rect()
        pygame.draw.rect(self.screen, (19, 24, 26), track.inflate(8, 8), border_radius=4)
        pygame.draw.rect(self.screen, (45, 54, 56), track, border_radius=4)
        thumb = self._horizontal_scrollbar_thumb_rect()
        active = self.drag_mode == "h_scrollbar"
        thumb_color = COLOR_ACCENT if active else (111, 128, 130)
        pygame.draw.rect(self.screen, thumb_color, thumb, border_radius=4)
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, track, 1, border_radius=4)

    def _cell_color(self, char: str) -> tuple[int, int, int]:
        if char == "#":
            return COLOR_WALL
        if char == "@":
            return COLOR_START
        if char in "123456789":
            return COLOR_OBJECT
        if char in DOOR_SYMBOLS:
            return DOOR_SYMBOLS[char][1]
        return COLOR_FLOOR

    def _draw_room_overlay(self, room: Room) -> None:
        sx, sy = self._screen_from_cell(room.x, room.y)
        rect = pygame.Rect(sx, sy, room.w * self.cell_size, room.h * self.cell_size)
        selected = room.room_id == self.state.selected_room_id
        color = COLOR_SELECTED if selected else (92, 104, 105)
        pygame.draw.rect(self.screen, color, rect, 2 if selected else 1)
        if selected:
            hx, hy = self._screen_from_cell(*room.handle_cell())
            handle_size = min(8, max(5, self.cell_size // 2))
            handle = pygame.Rect(
                hx + self.cell_size - handle_size,
                hy + self.cell_size - handle_size,
                handle_size,
                handle_size,
            )
            pygame.draw.rect(self.screen, COLOR_SELECTED, handle)

    def _draw_objects_overlay(self) -> None:
        for anchor, placement in self.state.objects.items():
            width, height = self.state.object_footprint_size(placement)
            sx, sy = self._screen_from_cell(*anchor)
            rect = pygame.Rect(sx, sy, width * self.cell_size, height * self.cell_size)
            selected = anchor == self.state.selected_object
            color = COLOR_SELECTED if selected else COLOR_OBJECT
            fill = self._object_fill_color(placement)
            for cell in self.state.object_footprint_cells(anchor, placement):
                if not self._cell_visible(cell):
                    continue
                cell_sx, cell_sy = self._screen_from_cell(*cell)
                cell_rect = pygame.Rect(cell_sx, cell_sy, self.cell_size, self.cell_size)
                pygame.draw.rect(self.screen, fill, cell_rect)
                pygame.draw.rect(self.screen, COLOR_GRID, cell_rect, 1)
            pygame.draw.rect(self.screen, color, rect, 2 if selected else 1)
            self._draw_centered_text(placement.label_char(), rect, self.small_font, COLOR_TEXT)
            self._draw_rotation_marker(rect, placement.rotation, color)
            if selected:
                self._draw_object_resize_handles(anchor, placement)

    def _object_fill_color(self, placement: ObjectPlacement) -> tuple[int, int, int]:
        if placement.object_id in LEGACY_OBJECT_IDS:
            return COLOR_OBJECT
        return (122, 104, 58)

    def _cell_visible(self, cell: tuple[int, int]) -> bool:
        sx, sy = self._screen_from_cell(*cell)
        return self.viewport_rect.colliderect(pygame.Rect(sx, sy, self.cell_size, self.cell_size))

    def _draw_object_resize_handles(self, anchor: tuple[int, int], placement: ObjectPlacement) -> None:
        for rect in self._object_resize_handle_rects(anchor, placement).values():
            if not self.viewport_rect.colliderect(rect):
                continue
            pygame.draw.rect(self.screen, COLOR_PANEL, rect)
            pygame.draw.rect(self.screen, COLOR_SELECTED, rect, 2)

    def _draw_rotation_marker(self, rect: pygame.Rect, rotation: int, color: tuple[int, int, int]) -> None:
        center = rect.center
        normalized = rotation % 360
        directions = {
            0: (0, -1),
            90: (1, 0),
            180: (0, 1),
            270: (-1, 0),
        }
        dx, dy = directions.get(normalized, (0, -1))
        end = (center[0] + dx * 7, center[1] + dy * 7)
        pygame.draw.line(self.screen, color, center, end, 2)

    def _draw_drag_preview(self) -> None:
        if self.drag_mode != "create_room" or self.drag_start_cell is None or self.drag_current_cell is None:
            return
        x1, y1 = self.drag_start_cell
        x2, y2 = self.drag_current_cell
        min_x, max_x = sorted((x1, x2))
        min_y, max_y = sorted((y1, y2))
        sx, sy = self._screen_from_cell(min_x, min_y)
        rect = pygame.Rect(sx, sy, (max_x - min_x + 1) * self.cell_size, (max_y - min_y + 1) * self.cell_size)
        pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 2)

    def _draw_door_preview(self) -> None:
        if self.active_tool != "door" or self.hover_cell is None:
            return
        target = self.state.nearest_wall_for_door(self.hover_cell)
        if target is None:
            return
        sx, sy = self._screen_from_cell(*target)
        rect = pygame.Rect(sx, sy, self.cell_size, self.cell_size)
        pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 3)

    def _draw_area_selection(self) -> None:
        rect_cells: tuple[int, int, int, int] | None = None
        color = COLOR_SELECTED
        if self.drag_mode == "box_select" and self.drag_start_cell is not None and self.drag_current_cell is not None:
            rect_cells = self._normalized_cell_rect(self.drag_start_cell, self.drag_current_cell)
            color = COLOR_ACCENT
        elif self.selection_rect is not None:
            rect_cells = self.selection_rect
        if rect_cells is None:
            return
        min_x, min_y, max_x, max_y = rect_cells
        sx, sy = self._screen_from_cell(min_x, min_y)
        rect = pygame.Rect(sx, sy, (max_x - min_x + 1) * self.cell_size, (max_y - min_y + 1) * self.cell_size)
        pygame.draw.rect(self.screen, color, rect, 2)

    def _draw_panel(self) -> None:
        panel = self.panel_rect
        pygame.draw.rect(self.screen, COLOR_PANEL, panel)
        self.panel_fields.clear()
        self.floor_buttons.clear()
        self.object_buttons.clear()
        self.map_scale_tick_rects.clear()
        self._clamp_side_scrolls()
        clip = self.screen.get_clip()
        self.screen.set_clip(panel)

        def py(value: int) -> int:
            return panel.y + value - self.panel_scroll_y

        self._draw_text("Properties", (panel.x + 20, py(20)), self.big_font, COLOR_TEXT)
        self._draw_text("Floor", (panel.x + 20, py(58)), self.small_font, COLOR_MUTED)
        for index, floor in enumerate(range(BOTTOM_FLOOR, TOP_FLOOR + 1)):
            rect = pygame.Rect(panel.x + 68 + index * 42, py(52), 32, 28)
            self.floor_buttons[floor] = rect
            active = floor == self.state.floor
            pygame.draw.rect(self.screen, (54, 64, 65) if active else (31, 38, 40), rect, border_radius=4)
            pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=4)
            self._draw_centered_text(str(floor), rect, self.small_font, COLOR_WARNING if active else COLOR_TEXT)

        self._draw_text(f"Tool: {self._tool_label()}", (panel.x + 20, py(92)), self.font, COLOR_ACCENT)
        self._draw_number_input("grid_width", "W", self.state.grid_width, pygame.Rect(panel.x + 42, py(126), 58, 28))
        self._draw_number_input("grid_height", "H", self.state.grid_height, pygame.Rect(panel.x + 132, py(126), 58, 28))
        self._draw_map_scale_slider(panel, py)
        self._draw_number_input("initial_hp", "HP", self.state.initial_hp, pygame.Rect(panel.x + 42, py(230), 58, 28))
        self._draw_number_input("initial_sanity", "SAN", self.state.initial_sanity, pygame.Rect(panel.x + 132, py(230), 58, 28))
        self._draw_number_input("initial_battery", "BAT", self.state.initial_battery, pygame.Rect(panel.x + 222, py(230), 58, 28))
        self._draw_number_input("player_speed", "SPD", self._format_number(self.state.player_speed), pygame.Rect(panel.x + 42, py(284), 58, 28))

        object_y = 334
        self._draw_text("Object Asset", (panel.x + 20, py(object_y)), self.small_font, COLOR_MUTED)
        self.object_dropdown_rect = pygame.Rect(panel.x + 24, py(object_y + 22), PANEL_WIDTH - 48, 28)
        pygame.draw.rect(self.screen, (35, 43, 45), self.object_dropdown_rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if self.object_dropdown_open else COLOR_PANEL_EDGE, self.object_dropdown_rect, 1, border_radius=3)
        active_object_label = f"{self.active_object_symbol}  {self.state.object_label(self.active_object_symbol)}"
        self._draw_text_in_rect(active_object_label, self.object_dropdown_rect.inflate(-14, -4), self.small_font, COLOR_TEXT)
        arrow_x = self.object_dropdown_rect.right - 18
        arrow_y = self.object_dropdown_rect.centery
        pygame.draw.polygon(self.screen, COLOR_MUTED, [(arrow_x - 5, arrow_y - 3), (arrow_x + 5, arrow_y - 3), (arrow_x, arrow_y + 4)])

        option_y = object_y + 52
        if self.object_dropdown_open:
            for object_id, label in self._object_list_items():
                option_rect = pygame.Rect(panel.x + 24, py(option_y), PANEL_WIDTH - 48, 22)
                self.object_buttons[object_id] = option_rect
                active = object_id == self.active_object_symbol
                pygame.draw.rect(self.screen, (54, 64, 65) if active else (30, 36, 38), option_rect)
                pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, option_rect, 1)
                color = COLOR_ACCENT if active else COLOR_TEXT
                self._draw_text_in_rect(label, option_rect.inflate(-12, -2), self.small_font, color)
                option_y += 22

        snap_y = option_y + 8 if self.object_dropdown_open else object_y + 60
        self.auto_wall_snap_rect = pygame.Rect(panel.x + 24, py(snap_y), 18, 18)
        pygame.draw.rect(self.screen, (35, 43, 45), self.auto_wall_snap_rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if self.auto_wall_snap else COLOR_PANEL_EDGE, self.auto_wall_snap_rect, 1, border_radius=3)
        if self.auto_wall_snap:
            pygame.draw.line(self.screen, COLOR_ACCENT, (self.auto_wall_snap_rect.x + 4, self.auto_wall_snap_rect.centery), (self.auto_wall_snap_rect.x + 8, self.auto_wall_snap_rect.bottom - 4), 2)
            pygame.draw.line(self.screen, COLOR_ACCENT, (self.auto_wall_snap_rect.x + 8, self.auto_wall_snap_rect.bottom - 4), (self.auto_wall_snap_rect.right - 4, self.auto_wall_snap_rect.y + 4), 2)
        self._draw_text("Auto wall snap", (panel.x + 48, py(snap_y + 1)), self.small_font, COLOR_TEXT)

        selection_y = max(380, snap_y + 42)

        room = self.state.selected_room()
        if room is not None:
            self._draw_text("Selected room", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_input("name", room.name, pygame.Rect(panel.x + 24, py(selection_y + 28), PANEL_WIDTH - 48, 28))
            self._draw_input("number", room.number, pygame.Rect(panel.x + 24, py(selection_y + 92), PANEL_WIDTH - 48, 28))
            self._draw_text(f"Pos: {room.x}, {room.y}", (panel.x + 24, py(selection_y + 132)), self.small_font, COLOR_MUTED)
            self._draw_text(f"Size: {room.w} x {room.h} tiles", (panel.x + 24, py(selection_y + 154)), self.small_font, COLOR_MUTED)
        elif self.state.selected_door is not None:
            cell = self.state.selected_door
            symbol = self.state.doors.get(cell, "?")
            self._draw_text("Selected door", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_text(f"Type: {symbol} {DOOR_SYMBOLS.get(symbol, ('Unknown',))[0]}", (panel.x + 24, py(selection_y + 32)), self.font, COLOR_ACCENT)
            self._draw_text(f"Cell: {cell[0]}, {cell[1]}", (panel.x + 24, py(selection_y + 62)), self.small_font, COLOR_MUTED)
            self._draw_text("Delete removes it.", (panel.x + 24, py(selection_y + 96)), self.small_font, COLOR_MUTED)
        elif self.state.selected_object is not None:
            cell = self.state.selected_object
            placement = self.state.objects.get(cell)
            object_id = placement.object_id if placement is not None else "?"
            rotation = placement.rotation if placement is not None else 0
            self._draw_text("Selected object", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_text(f"{object_id}: {self.state.object_label(object_id)}", (panel.x + 24, py(selection_y + 32)), self.font, COLOR_ACCENT)
            self._draw_text(f"Rotation: {rotation} deg", (panel.x + 24, py(selection_y + 62)), self.small_font, COLOR_MUTED)
            if placement is not None:
                footprint_w, footprint_h = self.state.object_footprint_size(placement)
                self._draw_number_input("object_x", "X", cell[0], pygame.Rect(panel.x + 24, py(selection_y + 102), 58, 28))
                self._draw_number_input("object_y", "Y", cell[1], pygame.Rect(panel.x + 112, py(selection_y + 102), 58, 28))
                length, width, height, placement_height = self.state.object_dimensions(placement)
                self._draw_number_input("object_footprint_w", "Len", self._format_number(length), pygame.Rect(panel.x + 24, py(selection_y + 156), 58, 28))
                self._draw_number_input("object_footprint_d", "Wid", self._format_number(width), pygame.Rect(panel.x + 112, py(selection_y + 156), 58, 28))
                self._draw_number_input("object_height", "H", self._format_number(height), pygame.Rect(panel.x + 200, py(selection_y + 156), 58, 28))
                self._draw_number_input("object_z", "Z", self._format_number(placement_height), pygame.Rect(panel.x + 24, py(selection_y + 210), 58, 28))
                self._draw_text(f"Rotated footprint: {footprint_w} x {footprint_h}", (panel.x + 24, py(selection_y + 250)), self.small_font, COLOR_MUTED)
        elif self.selection_rect is not None:
            min_x, min_y, max_x, max_y = self.selection_rect
            count = self._selection_item_count(self.selection_items)
            self._draw_text("Selected area", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_text(f"Items: {count}", (panel.x + 24, py(selection_y + 32)), self.font, COLOR_ACCENT)
            self._draw_text(f"From: {min_x}, {min_y}", (panel.x + 24, py(selection_y + 62)), self.small_font, COLOR_MUTED)
            self._draw_text(f"To: {max_x}, {max_y}", (panel.x + 24, py(selection_y + 86)), self.small_font, COLOR_MUTED)
            self._draw_text("Drag inside box to move.", (panel.x + 24, py(selection_y + 120)), self.small_font, COLOR_MUTED)
        else:
            self._draw_text("No selection", (panel.x + 20, py(selection_y)), self.font, COLOR_MUTED)
            self._draw_text("Create or select a room to edit metadata.", (panel.x + 20, py(selection_y + 30)), self.small_font, COLOR_MUTED)

        self.panel_content_height = max(WINDOW_HEIGHT - STATUS_HEIGHT, selection_y + 290)
        self._clamp_side_scrolls()
        self.screen.set_clip(clip)
        self._draw_side_scrollbar(panel, self.panel_scroll_y, self.panel_content_height, self.drag_mode == "panel_v_scrollbar")
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, panel, 1)

    def _draw_map_scale_slider(self, panel: pygame.Rect, py) -> None:
        label_y = py(164)
        track_y = py(194)
        self._draw_text("Map Scale", (panel.x + 20, label_y), self.small_font, COLOR_MUTED)
        value_text = f"{self.state._format_scale(self.state.cell_scale)}x"
        self._draw_text(value_text, (panel.x + PANEL_WIDTH - 62, label_y), self.small_font, COLOR_ACCENT)

        track = pygame.Rect(panel.x + 42, track_y, PANEL_WIDTH - 84, 4)
        self.map_scale_track_rect = track.inflate(18, 28)
        pygame.draw.rect(self.screen, (40, 48, 50), track, border_radius=2)
        values = list(MAP_SCALE_VALUES)
        active_x = track.x
        for index, value in enumerate(values):
            t = index / max(1, len(values) - 1)
            x = int(round(track.x + t * track.width))
            tick_rect = pygame.Rect(x - 14, track_y - 15, 28, 36)
            self.map_scale_tick_rects[value] = tick_rect
            active = abs(value - self.state.cell_scale) < 0.001
            if active:
                active_x = x
            color = COLOR_ACCENT if active else COLOR_PANEL_EDGE
            pygame.draw.line(self.screen, color, (x, track_y - 5), (x, track_y + 9), 2)
            label = self.state._format_scale(value)
            surface = self.small_font.render(label, True, color if active else COLOR_MUTED)
            self.screen.blit(surface, surface.get_rect(center=(x, track_y + 26)))

        pygame.draw.circle(self.screen, COLOR_ACCENT, (active_x, track_y + 2), 8)
        pygame.draw.circle(self.screen, COLOR_PANEL, (active_x, track_y + 2), 4)

    def _draw_number_input(self, field: str, label: str, value: int | float | str, rect: pygame.Rect) -> None:
        self.panel_fields[field] = rect
        active = self.editing_field == field
        self._draw_text(label, (rect.x, rect.y - 18), self.small_font, COLOR_MUTED)
        pygame.draw.rect(self.screen, (35, 43, 45), rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=3)
        suffix = "|" if active else ""
        display = self.edit_buffer if active else str(value)
        self._draw_text_in_rect(display + suffix, rect.inflate(-12, -4), self.small_font, COLOR_TEXT)

    def _draw_input(self, field: str, value: str, rect: pygame.Rect) -> None:
        self.panel_fields[field] = rect
        label = "Name" if field == "name" else "Number"
        active = self.editing_field == field
        self._draw_text(label, (rect.x, rect.y - 20), self.small_font, COLOR_MUTED)
        pygame.draw.rect(self.screen, (35, 43, 45), rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=3)
        suffix = "|" if active else ""
        display = self.edit_buffer if active else value
        self._draw_text_in_rect(display + suffix, rect.inflate(-14, -4), self.small_font, COLOR_TEXT)

    def _draw_status(self) -> None:
        y = WINDOW_HEIGHT - STATUS_HEIGHT
        pygame.draw.rect(self.screen, (10, 13, 14), (0, y, WINDOW_WIDTH, STATUS_HEIGHT))
        status = self.state.status or "Ready."
        color = COLOR_ERROR if status.startswith("Door must") or status.startswith("Room needs") else COLOR_MUTED
        self._draw_text(status, (14, y + 9), self.small_font, color)
        if self.hover_cell is not None:
            text = f"Cell {self.hover_cell[0]}, {self.hover_cell[1]}"
            surface = self.small_font.render(text, True, COLOR_MUTED)
            self.screen.blit(surface, (WINDOW_WIDTH - surface.get_width() - 18, y + 9))

    def _tool_label(self) -> str:
        if self.active_tool == "door":
            return f"Door {self.active_door_symbol}"
        if self.active_tool == "object":
            return f"Object {self.active_object_symbol} {self.active_object_rotation}deg"
        return self.active_tool.title()

    def _object_list_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for object_id, spec in sorted(self.state.object_specs.items()):
            if object_id not in LEGACY_OBJECT_IDS:
                items.append((object_id, object_id))
        items.extend((symbol, f"Legacy {symbol}: {label}") for symbol, label in OBJECT_LABELS.items())
        return items

    def _draw_text(self, text: str, pos: tuple[int, int], font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)

    def _draw_text_in_rect(self, text: str, rect: pygame.Rect, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        visible_text = self._fit_text_to_width(text, font, rect.width)
        surface = font.render(visible_text, True, color)
        pos = (rect.x, rect.y + (rect.height - surface.get_height()) // 2)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(rect.clip(old_clip) if old_clip is not None else rect)
        self.screen.blit(surface, pos)
        self.screen.set_clip(old_clip)

    def _fit_text_to_width(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        if max_width <= 0:
            return ""
        if font.size(text)[0] <= max_width:
            return text
        prefix = "..."
        trimmed = text
        while trimmed and font.size(prefix + trimmed)[0] > max_width:
            trimmed = trimmed[1:]
        if trimmed:
            return prefix + trimmed
        while prefix and font.size(prefix)[0] > max_width:
            prefix = prefix[:-1]
        return prefix

    def _draw_centered_text(self, text: str, rect: pygame.Rect, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))


def main() -> None:
    MapEditor().run()


if __name__ == "__main__":
    main()
