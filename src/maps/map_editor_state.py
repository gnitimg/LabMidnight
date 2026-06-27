"""Map editor mutable map state."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from typing import Iterable

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement, Room
from src.maps.map_editor_state_doors import MapEditorStateDoorSaveMixin
from src.maps.map_editor_state_grid import MapEditorStateGridMixin
from src.maps.map_editor_state_load import MapEditorStateLoadMixin
from src.maps.map_editor_state_objects import MapEditorStateObjectMixin
from src.resources.object_assets import ObjectSpec, load_object_specs
from src.settings import PLAYER_SPEED, PLAYER_SPEED_MAX, PLAYER_SPEED_MIN


class MapEditorState(
    MapEditorStateLoadMixin,
    MapEditorStateGridMixin,
    MapEditorStateObjectMixin,
    MapEditorStateDoorSaveMixin,
):
    def __init__(self, floor: int = TOP_FLOOR) -> None:
        self.floor = max(BOTTOM_FLOOR, min(TOP_FLOOR, floor))
        self.grid_width = DEFAULT_GRID_WIDTH
        self.grid_height = DEFAULT_GRID_HEIGHT
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

