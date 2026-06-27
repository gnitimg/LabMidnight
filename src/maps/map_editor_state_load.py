from __future__ import annotations

import json

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement, Room
from src.resources.object_assets import ObjectSpec
from src.settings import PLAYER_SPEED_MAX, PLAYER_SPEED_MIN


class MapEditorStateLoadMixin:
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
        layout_overrides: dict[tuple[int, int], str] = {}

        for y, row in enumerate(padded):
            for x, char in enumerate(row):
                if char in DOOR_SYMBOLS:
                    state.doors[(x, y)] = char
                elif char == WINDOW_SYMBOL:
                    layout_overrides[(x, y)] = WINDOW_SYMBOL
                elif char == "@":
                    state.start_cell = (x, y)
                elif char in "123456789":
                    state.objects[(x, y)] = ObjectPlacement(state._object_id_for_layout_symbol(char))

        state.rooms = state._load_room_metadata()
        if not state.rooms:
            state.rooms = state._infer_rooms_from_rows(padded)
        state.overrides = {**layout_overrides, **state._load_overrides()}
        state._load_object_metadata()
        state.next_room_id = 1 + max((room.room_id for room in state.rooms), default=0)
        state.rebuild_grid()
        state.status = f"Loaded floor {state.floor}: {layout_path}."
        return state

    def _object_id_for_layout_symbol(self, symbol: str) -> str:
        return self._canonical_object_id(symbol)

    def _canonical_object_id(self, object_id: str) -> str:
        alias = LEGACY_OBJECT_ASSET_ALIASES.get(object_id)
        if alias is not None and alias in self.object_specs:
            return alias
        return object_id

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
            if symbol in OVERRIDE_SYMBOLS:
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
            object_id = self._canonical_object_id(object_id)
            try:
                rotation = int(raw.get("rotation", 0)) % 360
            except (TypeError, ValueError):
                rotation = 0
            if object_id in LEGACY_OBJECT_IDS or object_id in self.object_specs:
                self.objects[(x, y)] = self._placement_from_metadata(object_id, rotation, raw)

    def _placement_from_metadata(self, object_id: str, rotation: int, raw: dict) -> ObjectPlacement:
        element_type = str(raw.get("element_type", ELEMENT_STORY))
        if element_type not in VALID_ELEMENT_TYPES:
            element_type = ELEMENT_STORY
        return ObjectPlacement(
            object_id,
            rotation,
            self._read_optional_positive_float(raw, "length"),
            self._read_optional_positive_float(raw, "width"),
            self._read_optional_positive_float(raw, "height"),
            self._read_optional_non_negative_float(raw, "placement_height"),
            element_type,
            str(raw.get("pickup_item", "")),
            str(raw.get("pickup_flag", "")),
            str(raw.get("interaction_prompt", "")),
            str(raw.get("interaction_message", "")),
            str(raw.get("required_item", "")),
            str(raw.get("required_flag", "")),
            str(raw.get("failure_message", "")),
            self._read_bool(raw, "remove_on_pickup", False),
            self._read_bool(raw, "random_drop", False),
            max(1, self._read_int(raw, "drop_count", 1)),
            self._read_bool(raw, "is_trigger", False) or bool(str(raw.get("trigger_id", "")).strip()) or element_type == ELEMENT_TRIGGER,
            str(raw.get("trigger_id", "")).strip(),
            self._read_bool(raw, "trigger_once", True),
            self._read_resource_role(raw),
        )

    def _read_resource_role(self, payload: dict) -> str:
        value = str(payload.get("resource_role", "")).strip().lower()
        return value if value in RESOURCE_ROLES else ""

    def _read_bool(self, payload: dict, key: str, default: bool = False) -> bool:
        value = payload.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

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


