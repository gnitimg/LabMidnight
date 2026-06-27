from __future__ import annotations

from dataclasses import asdict

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement, Room
from src.maps.map_editor_state import MapEditorState


class MapEditorHistoryMixin:
    def _state_snapshot(self) -> dict:
        return {
            "floor": self.state.floor,
            "grid_width": self.state.grid_width,
            "grid_height": self.state.grid_height,
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
                state.objects[(x, y)] = state._placement_from_metadata(object_id, int(raw.get("rotation", 0)) % 360, raw)
            except (KeyError, TypeError, ValueError):
                continue
        state.overrides = {}
        for raw in snapshot.get("overrides", []):
            try:
                symbol = str(raw["symbol"])
                if symbol in OVERRIDE_SYMBOLS:
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


