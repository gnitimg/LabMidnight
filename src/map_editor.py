"""Developer map editor for LabMidnight.

The editor writes the same text layout consumed by GameMap. Room labels are
stored in a sidecar JSON file because the runtime map format is intentionally
kept compact and character based.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable

import pygame


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
H_SCROLLBAR_HEIGHT = 18
H_SCROLLBAR_MIN_THUMB_WIDTH = 36
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

NUMERIC_FIELDS = {"grid_width", "grid_height", "initial_hp", "initial_sanity", "initial_battery"}


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


class MapEditorState:
    def __init__(self, floor: int = TOP_FLOOR) -> None:
        self.floor = max(BOTTOM_FLOOR, min(TOP_FLOOR, floor))
        self.grid_width = DEFAULT_GRID_WIDTH
        self.grid_height = DEFAULT_GRID_HEIGHT
        self.initial_hp = 100
        self.initial_sanity = 100
        self.initial_battery = 86
        self.rooms: list[Room] = []
        self.doors: dict[tuple[int, int], str] = {}
        self.objects: dict[tuple[int, int], str] = {}
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
                    state.objects[(x, y)] = char

        state.rooms = state._load_room_metadata()
        if not state.rooms:
            state.rooms = state._infer_rooms_from_rows(padded)
        state.overrides = state._load_overrides()
        state.next_room_id = 1 + max((room.room_id for room in state.rooms), default=0)
        state.rebuild_grid()
        state.status = f"Loaded floor {state.floor}: {layout_path}."
        return state

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

    def _read_int(self, payload: dict, key: str, fallback: int) -> int:
        try:
            return max(0, int(float(payload.get(key, fallback))))
        except (TypeError, ValueError):
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
        all_cells = list(self.doors) + list(self.objects) + list(self.overrides)
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
        for (x, y), symbol in self.objects.items():
            if self.in_bounds(x, y):
                self.grid[y][x] = symbol
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
        self.objects.pop(cell, None)
        if self.start_cell == cell:
            self.start_cell = None
        self.overrides[cell] = "#"
        self.rebuild_grid()

    def erase_cell(self, cell: tuple[int, int]) -> None:
        x, y = cell
        if not self.in_bounds(x, y):
            return
        self.doors.pop(cell, None)
        self.objects.pop(cell, None)
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

    def place_object(self, cell: tuple[int, int], symbol: str) -> None:
        if not self._is_floor_target(cell):
            self.status = "Objects must be placed on floor cells."
            return
        if self.start_cell == cell:
            self.start_cell = None
        self.objects[cell] = symbol
        self.rebuild_grid()
        self.status = f"Object {symbol} placed at {cell}."

    def _is_floor_target(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return self.in_bounds(x, y) and self.grid[y][x] in FLOOR_CHARS | {"."}

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
        self.objects.pop(target, None)
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
            "floor": self.floor,
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "rooms": [asdict(room) for room in self.rooms],
            "overrides": [
                {"x": x, "y": y, "symbol": symbol}
                for (x, y), symbol in sorted(self.overrides.items())
            ],
        }
        room_meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self._save_initial_config()
        if self.floor == TOP_FLOOR:
            LEGACY_MAP_LAYOUT_PATH.write_text(layout, encoding="utf-8")
            LEGACY_ROOM_META_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status = f"Saved floor {self.floor}."

    def _save_initial_config(self) -> None:
        MAP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "initial_player": {
                "hp": self.initial_hp,
                "sanity": self.initial_sanity,
                "flashlight_power": self.initial_battery,
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
            "; Objects: 1-9 story objects defined in src/map_data.py",
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
        self.buttons: list[tuple[pygame.Rect, str, str, str | None]] = []
        self.editing_field: str | None = None
        self.edit_buffer = ""
        self.drag_mode: str | None = None
        self.drag_start_cell: tuple[int, int] | None = None
        self.drag_current_cell: tuple[int, int] | None = None
        self.drag_initial_room: tuple[int, int, int, int] | None = None
        self.selection_rect: tuple[int, int, int, int] | None = None
        self.selection_items = self._empty_selection_items()
        self.selection_move_snapshot: dict[str, object] | None = None
        self.hover_cell: tuple[int, int] | None = None
        self.panel_fields: dict[str, pygame.Rect] = {}
        self.floor_buttons: dict[int, pygame.Rect] = {}
        self.scrollbar_drag_offset = 0
        self.scroll_x = 0
        self.scroll_y = 0
        self._build_buttons()

    def run(self) -> None:
        while self.running:
            self._handle_events()
            self._draw()
            self.clock.tick(60)
        pygame.quit()

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
        self._add_button("Obj 1-9", "object", None, y)
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

    def _add_button(self, label: str, action: str, payload: str | None, y: int) -> None:
        self.buttons.append((pygame.Rect(14, y, TOOLBAR_WIDTH - 28, 28), label, action, payload))

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

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()
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
            if self.selection_rect is not None:
                self._delete_area_selection()
            else:
                self.state.delete_selection()
        elif event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
            self.state.save()
        elif event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
            self.state = MapEditorState.load(self.state.floor)
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
            max_digits = 4 if self.editing_field in {"grid_width", "grid_height"} else 3
            if len(self.edit_buffer) < max_digits:
                self.edit_buffer += typed

    def _begin_editing_field(self, field: str) -> None:
        if self.editing_field == field:
            return
        self._commit_editing_field()
        if field in {"name", "number"} and self.state.selected_room() is None:
            return
        self.editing_field = field
        self.edit_buffer = self._editing_field_value(field)

    def _commit_editing_field(self) -> None:
        field = self.editing_field
        if field is None:
            return
        if field in NUMERIC_FIELDS:
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
        values = {
            "grid_width": self.state.grid_width,
            "grid_height": self.state.grid_height,
            "initial_hp": self.state.initial_hp,
            "initial_sanity": self.state.initial_sanity,
            "initial_battery": self.state.initial_battery,
        }
        return str(values.get(field, 0))

    def _set_numeric_field(self, field: str, value: int) -> None:
        if field == "grid_width":
            self.state.resize_grid(max(MIN_GRID_WIDTH, value), self.state.grid_height)
        elif field == "grid_height":
            self.state.resize_grid(self.state.grid_width, max(MIN_GRID_HEIGHT, value))
        elif field == "initial_hp":
            self.state.initial_hp = max(0, min(999, value))
        elif field == "initial_sanity":
            self.state.initial_sanity = max(0, min(999, value))
        elif field == "initial_battery":
            self.state.initial_battery = max(0, min(999, value))

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 4:
            self.scroll_y = max(0, self.scroll_y - CELL_SIZE)
            self._clamp_scroll()
            return
        if event.button == 5:
            self.scroll_y += CELL_SIZE
            self._clamp_scroll()
            return
        if event.button != 1:
            return

        pos = event.pos
        if self.editing_field is not None and not self.panel_rect.collidepoint(pos):
            self._commit_editing_field()
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
        elif self.active_tool == "select" and self._begin_area_move(cell):
            return
        elif self.active_tool == "select":
            self._begin_select_drag(cell)
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
            self._paint_cell(cell)

    def _button_at(self, pos: tuple[int, int]) -> tuple[pygame.Rect, str, str, str | None] | None:
        for button in self.buttons:
            if button[0].collidepoint(pos):
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
            elif payload == "clear":
                self._clear_area_selection()
                self.drag_mode = None
                self.state.clear_map()
                self.active_tool = "select"
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
        for field, rect in self.panel_fields.items():
            if rect.collidepoint(pos):
                self._begin_editing_field(field)
                return True
        self._commit_editing_field()
        return True

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

    def _begin_select_drag(self, cell: tuple[int, int]) -> None:
        if cell in self.state.doors:
            self._clear_area_selection()
            self.state.selected_door = cell
            self.state.selected_room_id = None
            self.state.selected_object = None
            return
        if cell in self.state.objects:
            self._clear_area_selection()
            self.state.selected_object = cell
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

    def _move_cell_dict_snapshot(self, key: str, dx: int, dy: int) -> dict[tuple[int, int], str]:
        base = self.selection_move_snapshot.get(f"base_{key}") if self.selection_move_snapshot else None
        selected = self.selection_move_snapshot.get(f"selected_{key}") if self.selection_move_snapshot else None
        moved: dict[tuple[int, int], str] = dict(base) if isinstance(base, dict) else {}
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
        room_ids = items["rooms"]
        door_cells = items["doors"]
        object_cells = items["objects"]
        override_cells = items["overrides"]
        for room in self.state.rooms:
            if self._room_intersects_rect(room, rect):
                room_ids.add(room.room_id)
        for cell in self.state.doors:
            if self._cell_in_rect(cell, rect):
                door_cells.add(cell)
        for cell in self.state.objects:
            if self._cell_in_rect(cell, rect):
                object_cells.add(cell)
        for cell in self.state.overrides:
            if self._cell_in_rect(cell, rect):
                override_cells.add(cell)
        if self.state.start_cell is not None and self._cell_in_rect(self.state.start_cell, rect):
            items["start"] = True
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
            self.state.add_room(*self.drag_start_cell, *self.drag_current_cell)
        elif self.drag_mode == "place_door" and self.drag_current_cell:
            self.state.place_door(self.drag_current_cell, self.active_door_symbol)
        elif self.drag_mode == "toolbar":
            cell = self._cell_from_pos(event.pos)
            if cell is not None and self.active_tool == "door":
                self.state.place_door(cell, self.active_door_symbol)
            elif cell is not None and self.active_tool == "room":
                self.state.add_room(cell[0], cell[1], cell[0] + MIN_ROOM_SIZE - 1, cell[1] + MIN_ROOM_SIZE - 1)
        self.drag_mode = None
        self.drag_start_cell = None
        self.drag_current_cell = None
        self.drag_initial_room = None
        self.selection_move_snapshot = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        self.hover_cell = self._cell_from_pos(event.pos)
        if self.drag_mode == "h_scrollbar":
            self._set_scroll_x_from_thumb(event.pos[0] - self.scrollbar_drag_offset)
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
        if self.drag_mode == "toolbar":
            if self.active_tool == "room":
                self.drag_mode = "create_room"
                self.drag_start_cell = cell
                self.drag_current_cell = cell
            elif self.active_tool == "door":
                self.drag_mode = "place_door"
                self.drag_current_cell = cell
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
            self.state.place_object(cell, self.active_object_symbol)

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
        content_width = max(1, self.state.grid_width * CELL_SIZE)
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

    def _max_scroll_x(self) -> int:
        return max(0, self.state.grid_width * CELL_SIZE - self.viewport_rect.width)

    def _max_scroll_y(self) -> int:
        return max(0, self.state.grid_height * CELL_SIZE - self.viewport_rect.height)

    def _clamp_scroll(self) -> None:
        self.scroll_x = max(0, min(self.scroll_x, self._max_scroll_x()))
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll_y()))

    def _cell_from_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        viewport = self.viewport_rect
        if not viewport.collidepoint(pos):
            return None
        x = (pos[0] - viewport.x + self.scroll_x) // CELL_SIZE
        y = (pos[1] - viewport.y + self.scroll_y) // CELL_SIZE
        if x < 0 or y < 0:
            return None
        if x >= self.state.grid_width or y >= self.state.grid_height:
            return None
        return int(x), int(y)

    def _screen_from_cell(self, x: int, y: int) -> tuple[int, int]:
        viewport = self.viewport_rect
        return viewport.x + x * CELL_SIZE - self.scroll_x, viewport.y + y * CELL_SIZE - self.scroll_y

    def _draw(self) -> None:
        self.screen.fill(COLOR_BG)
        self._draw_toolbar()
        self._draw_canvas()
        self._draw_panel()
        self._draw_status()
        pygame.display.flip()

    def _draw_toolbar(self) -> None:
        pygame.draw.rect(self.screen, COLOR_TOOLBAR, (0, 0, TOOLBAR_WIDTH, WINDOW_HEIGHT))
        self._draw_text("Map Editor", (16, 8), self.big_font, COLOR_TEXT)
        for rect, label, action, payload in self.buttons:
            selected = action == self.active_tool
            if action == "door" and payload != self.active_door_symbol:
                selected = False
            color = (58, 68, 70) if selected else (38, 45, 48)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, rect, 1, border_radius=4)
            self._draw_text(label, (rect.x + 8, rect.y + 6), self.small_font, COLOR_TEXT)

        help_lines = [
            "Drag Room from toolbar or canvas.",
            "Drag bottom-right handle to resize.",
            "Doors snap to valid wall cells.",
            "Ctrl+drag box-selects items.",
            "Bottom bar scrolls left/right.",
            "Middle/right drag pans the grid.",
            "Keys: Ctrl+S save, Del delete.",
            "Object tool: press 1-9.",
        ]
        y = WINDOW_HEIGHT - STATUS_HEIGHT - 148
        for line in help_lines:
            self._draw_text(line, (14, y), self.small_font, COLOR_MUTED)
            y += 20

    def _draw_canvas(self) -> None:
        canvas = self.canvas_rect
        viewport = self.viewport_rect
        self._clamp_scroll()
        pygame.draw.rect(self.screen, (14, 17, 18), canvas)
        clip = self.screen.get_clip()
        self.screen.set_clip(viewport)

        start_x = max(0, self.scroll_x // CELL_SIZE)
        start_y = max(0, self.scroll_y // CELL_SIZE)
        end_x = min(self.state.grid_width, start_x + viewport.width // CELL_SIZE + 3)
        end_y = min(self.state.grid_height, start_y + viewport.height // CELL_SIZE + 3)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                sx, sy = self._screen_from_cell(x, y)
                char = self.state.grid[y][x]
                rect = pygame.Rect(sx, sy, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, self._cell_color(char), rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)
                if char in DOOR_SYMBOLS or char == "@" or char in "123456789":
                    self._draw_centered_text(char, rect, self.small_font, COLOR_TEXT)

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
        rect = pygame.Rect(sx, sy, room.w * CELL_SIZE, room.h * CELL_SIZE)
        selected = room.room_id == self.state.selected_room_id
        color = COLOR_SELECTED if selected else (92, 104, 105)
        pygame.draw.rect(self.screen, color, rect, 2 if selected else 1)
        if selected:
            hx, hy = self._screen_from_cell(*room.handle_cell())
            handle = pygame.Rect(hx + CELL_SIZE - 8, hy + CELL_SIZE - 8, 8, 8)
            pygame.draw.rect(self.screen, COLOR_SELECTED, handle)

    def _draw_drag_preview(self) -> None:
        if self.drag_mode != "create_room" or self.drag_start_cell is None or self.drag_current_cell is None:
            return
        x1, y1 = self.drag_start_cell
        x2, y2 = self.drag_current_cell
        min_x, max_x = sorted((x1, x2))
        min_y, max_y = sorted((y1, y2))
        sx, sy = self._screen_from_cell(min_x, min_y)
        rect = pygame.Rect(sx, sy, (max_x - min_x + 1) * CELL_SIZE, (max_y - min_y + 1) * CELL_SIZE)
        pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 2)

    def _draw_door_preview(self) -> None:
        if self.active_tool != "door" or self.hover_cell is None:
            return
        target = self.state.nearest_wall_for_door(self.hover_cell)
        if target is None:
            return
        sx, sy = self._screen_from_cell(*target)
        rect = pygame.Rect(sx, sy, CELL_SIZE, CELL_SIZE)
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
        rect = pygame.Rect(sx, sy, (max_x - min_x + 1) * CELL_SIZE, (max_y - min_y + 1) * CELL_SIZE)
        pygame.draw.rect(self.screen, color, rect, 2)

    def _draw_panel(self) -> None:
        panel = self.panel_rect
        pygame.draw.rect(self.screen, COLOR_PANEL, panel)
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, panel, 1)
        self.panel_fields.clear()
        self.floor_buttons.clear()

        self._draw_text("Properties", (panel.x + 20, 20), self.big_font, COLOR_TEXT)
        self._draw_text("Floor", (panel.x + 20, 58), self.small_font, COLOR_MUTED)
        for index, floor in enumerate(range(BOTTOM_FLOOR, TOP_FLOOR + 1)):
            rect = pygame.Rect(panel.x + 68 + index * 42, 52, 32, 28)
            self.floor_buttons[floor] = rect
            active = floor == self.state.floor
            pygame.draw.rect(self.screen, (54, 64, 65) if active else (31, 38, 40), rect, border_radius=4)
            pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=4)
            self._draw_centered_text(str(floor), rect, self.small_font, COLOR_WARNING if active else COLOR_TEXT)

        self._draw_text(f"Tool: {self._tool_label()}", (panel.x + 20, 92), self.font, COLOR_ACCENT)
        self._draw_number_input("grid_width", "W", self.state.grid_width, pygame.Rect(panel.x + 42, 126, 58, 28))
        self._draw_number_input("grid_height", "H", self.state.grid_height, pygame.Rect(panel.x + 132, 126, 58, 28))
        self._draw_number_input("initial_hp", "HP", self.state.initial_hp, pygame.Rect(panel.x + 42, 180, 58, 28))
        self._draw_number_input("initial_sanity", "SAN", self.state.initial_sanity, pygame.Rect(panel.x + 132, 180, 58, 28))
        self._draw_number_input("initial_battery", "BAT", self.state.initial_battery, pygame.Rect(panel.x + 222, 180, 58, 28))

        room = self.state.selected_room()
        if room is not None:
            self._draw_text("Selected room", (panel.x + 20, 230), self.font, COLOR_TEXT)
            self._draw_input("name", room.name, pygame.Rect(panel.x + 24, 258, PANEL_WIDTH - 48, 28))
            self._draw_input("number", room.number, pygame.Rect(panel.x + 24, 322, PANEL_WIDTH - 48, 28))
            self._draw_text(f"Pos: {room.x}, {room.y}", (panel.x + 24, 362), self.small_font, COLOR_MUTED)
            self._draw_text(f"Size: {room.w} x {room.h} tiles", (panel.x + 24, 384), self.small_font, COLOR_MUTED)
        elif self.state.selected_door is not None:
            cell = self.state.selected_door
            symbol = self.state.doors.get(cell, "?")
            self._draw_text("Selected door", (panel.x + 20, 230), self.font, COLOR_TEXT)
            self._draw_text(f"Type: {symbol} {DOOR_SYMBOLS.get(symbol, ('Unknown',))[0]}", (panel.x + 24, 262), self.font, COLOR_ACCENT)
            self._draw_text(f"Cell: {cell[0]}, {cell[1]}", (panel.x + 24, 292), self.small_font, COLOR_MUTED)
            self._draw_text("Delete removes it.", (panel.x + 24, 326), self.small_font, COLOR_MUTED)
        elif self.state.selected_object is not None:
            cell = self.state.selected_object
            symbol = self.state.objects.get(cell, "?")
            self._draw_text("Selected object", (panel.x + 20, 230), self.font, COLOR_TEXT)
            self._draw_text(f"{symbol}: {OBJECT_LABELS.get(symbol, 'Unknown')}", (panel.x + 24, 262), self.font, COLOR_ACCENT)
            self._draw_text(f"Cell: {cell[0]}, {cell[1]}", (panel.x + 24, 292), self.small_font, COLOR_MUTED)
        elif self.selection_rect is not None:
            min_x, min_y, max_x, max_y = self.selection_rect
            count = self._selection_item_count(self.selection_items)
            self._draw_text("Selected area", (panel.x + 20, 230), self.font, COLOR_TEXT)
            self._draw_text(f"Items: {count}", (panel.x + 24, 262), self.font, COLOR_ACCENT)
            self._draw_text(f"From: {min_x}, {min_y}", (panel.x + 24, 292), self.small_font, COLOR_MUTED)
            self._draw_text(f"To: {max_x}, {max_y}", (panel.x + 24, 316), self.small_font, COLOR_MUTED)
            self._draw_text("Drag inside box to move.", (panel.x + 24, 350), self.small_font, COLOR_MUTED)
        else:
            self._draw_text("No selection", (panel.x + 20, 230), self.font, COLOR_MUTED)
            self._draw_text("Create or select a room to edit metadata.", (panel.x + 20, 260), self.small_font, COLOR_MUTED)

        self._draw_text("Objects", (panel.x + 20, 440), self.font, COLOR_TEXT)
        y = 472
        for symbol, label in OBJECT_LABELS.items():
            color = COLOR_WARNING if symbol == self.active_object_symbol and self.active_tool == "object" else COLOR_MUTED
            self._draw_text(f"{symbol}  {label}", (panel.x + 24, y), self.small_font, color)
            y += 20

    def _draw_number_input(self, field: str, label: str, value: int, rect: pygame.Rect) -> None:
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
            return f"Object {self.active_object_symbol}"
        return self.active_tool.title()

    def _draw_text(self, text: str, pos: tuple[int, int], font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)

    def _draw_text_in_rect(self, text: str, rect: pygame.Rect, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        visible_text = self._fit_text_to_width(text, font, rect.width)
        surface = font.render(visible_text, True, color)
        pos = (rect.x, rect.y + (rect.height - surface.get_height()) // 2)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
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
