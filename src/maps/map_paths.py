"""Map file paths and player-start configuration."""

from __future__ import annotations

import json
from pathlib import Path

from src.settings import (
    BUILDING_TOP_FLOOR,
    PLAYER_SPEED,
    PLAYER_SPEED_MAX,
    PLAYER_SPEED_MIN,
)


MAP_LAYOUT_PATH = Path("data/map_layout.txt")
MAP_ROOM_META_PATH = Path("data/map_rooms.json")
FLOOR_MAP_DIR = Path("data/floors")
MAP_CONFIG_PATH = Path("data/map_config.json")

def floor_layout_path(floor: int) -> Path:
    return FLOOR_MAP_DIR / f"floor_{floor}.txt"


def floor_room_meta_path(floor: int) -> Path:
    return FLOOR_MAP_DIR / f"floor_{floor}_rooms.json"


def room_meta_path_for_floor(floor: int) -> Path:
    floor_path = floor_room_meta_path(floor)
    if floor_path.exists():
        return floor_path
    if floor == BUILDING_TOP_FLOOR and MAP_ROOM_META_PATH.exists():
        return MAP_ROOM_META_PATH
    return floor_path


def layout_path_for_floor(floor: int) -> Path:
    floor_path = floor_layout_path(floor)
    if floor_path.exists():
        return floor_path
    if floor == BUILDING_TOP_FLOOR and MAP_LAYOUT_PATH.exists():
        return MAP_LAYOUT_PATH
    if MAP_LAYOUT_PATH.exists():
        return MAP_LAYOUT_PATH
    return floor_path


def load_initial_player_config() -> dict[str, float]:
    defaults = {"hp": 100.0, "sanity": 100.0, "flashlight_power": 86.0, "speed": PLAYER_SPEED}
    if not MAP_CONFIG_PATH.exists():
        return defaults
    try:
        payload = json.loads(MAP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults

    initial = payload.get("initial_player", {})
    if not isinstance(initial, dict):
        return defaults
    for key in defaults:
        source_key = key
        if key == "speed" and key not in initial and "player_speed" in initial:
            source_key = "player_speed"
        try:
            value = max(0.0, float(initial.get(source_key, defaults[key])))
            if key == "speed":
                value = max(PLAYER_SPEED_MIN, min(PLAYER_SPEED_MAX, value))
            defaults[key] = value
        except (TypeError, ValueError):
            pass
    return defaults


