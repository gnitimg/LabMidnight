"""Map editor constants and file path helpers."""

from __future__ import annotations

from pathlib import Path


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

WINDOW_SYMBOL = "W"
OVERRIDE_SYMBOLS = {"#", ".", WINDOW_SYMBOL}
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
    "9": "Elevator",
}

ELEMENT_STORY = "story_required"
ELEMENT_PICKUP = "pickup"
ELEMENT_TRIGGER = "trigger"
ELEMENT_DECORATION = "decoration"
VALID_ELEMENT_TYPES = {ELEMENT_STORY, ELEMENT_PICKUP, ELEMENT_TRIGGER, ELEMENT_DECORATION}
RESOURCE_ROLES = {"", "required", "optional", "decor"}

LEGACY_OBJECT_IDS = set(OBJECT_LABELS)
LEGACY_OBJECT_ASSET_ALIASES = {
    "1": "desk",
    "2": "blackboard",
    "9": "elevator",
}
FIXED_OBJECT_STYLES = {
    "blackboard": {
        "width": 0.08,
        "height": 2.0,
        "placement_height": 1.5,
    },
    "elevator": {
        "height": 3.0,
        "placement_height": 0.0,
    },
}
WALL_FACING_OBJECT_IDS = {"blackboard", "elevator"}
WALL_FACING_ROTATIONS = (
    (0, -1, 0),
    (1, 0, 270),
    (0, 1, 180),
    (-1, 0, 90),
)

OBJECT_NUMERIC_FIELDS = {
    "object_x",
    "object_y",
    "object_footprint_w",
    "object_footprint_d",
    "object_height",
    "object_z",
    "object_drop_count",
}
DOOR_NUMERIC_FIELDS = {
    "door_length",
}
ROOM_NUMERIC_FIELDS = {
    "room_x",
    "room_y",
    "room_w",
    "room_h",
}
FLOAT_NUMERIC_FIELDS = {"player_speed", "object_footprint_w", "object_footprint_d", "object_height", "object_z"}
NUMERIC_FIELDS = (
    {"grid_width", "grid_height", "initial_hp", "initial_sanity", "initial_battery", "player_speed"}
    | OBJECT_NUMERIC_FIELDS
    | DOOR_NUMERIC_FIELDS
    | ROOM_NUMERIC_FIELDS
)
OBJECT_TEXT_FIELDS = {
    "object_pickup_item",
    "object_pickup_flag",
    "object_trigger_id",
    "object_resource_role",
    "object_interaction_prompt",
    "object_interaction_message",
    "object_required_item",
    "object_required_flag",
    "object_failure_message",
}
OBJECT_TOGGLE_FIELDS = {
    "object_is_pickup",
    "object_is_trigger",
    "object_random_drop",
    "object_remove_on_pickup",
    "object_trigger_once",
}


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


