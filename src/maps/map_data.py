"""Map layout and collision helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math
from pathlib import Path
from typing import Iterable

from src.resources.object_assets import ObjectSpec, load_object_specs
from src.settings import (
    BUILDING_BOTTOM_FLOOR,
    BUILDING_TOP_FLOOR,
    DOOR_COLLISION_THICKNESS,
    DOOR_OPEN_SPEED,
    DOOR_PASSABLE_PROGRESS,
    DOOR_TILES,
    OBJECT_COLLISION_RADIUS,
    PLAYER_RADIUS,
    TILE_CLASSROOM_DOOR,
    TILE_EMPTY,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
    TILE_WALL,
)


MAP_LAYOUT_PATH = Path("data/map_layout.txt")
MAP_ROOM_META_PATH = Path("data/map_rooms.json")
FLOOR_MAP_DIR = Path("data/floors")
MAP_CONFIG_PATH = Path("data/map_config.json")

SOLID_TEMPLATE_OBJECT_IDS = {
    "lab_desk",
    "blackboard",
    "lectern",
    "security_desk",
    "fuse_cabinet",
    "power_box",
    "server_terminal",
    "exit_panel",
}

LEGACY_OBJECT_ASSET_ALIASES = {
    "lab_desk": "desk",
}
LEGACY_OBJECT_SYMBOL_ASSET_ALIASES = {
    "1": "desk",
}


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
    defaults = {"hp": 100.0, "sanity": 100.0, "flashlight_power": 86.0}
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
        try:
            defaults[key] = max(0.0, float(initial.get(key, defaults[key])))
        except (TypeError, ValueError):
            pass
    return defaults


@dataclass(frozen=True)
class MapObject:
    object_id: str
    name: str
    prompt: str
    description: str = ""
    asset_id: str = ""
    length: float = 1.0
    width: float = 1.0
    height: float = 1.0
    placement_height: float = 0.0
    rotation: int = 0
    solid: bool = False

    def footprint_size(self) -> tuple[float, float]:
        normalized = self.rotation % 360
        if normalized in (90, 270):
            return self.width, self.length
        return self.length, self.width


def object_templates() -> dict[str, MapObject]:
    return {
        "1": MapObject(
            "lab_desk",
            "实验桌",
            "按 Space 检查实验桌",
            "电脑还亮着，桌上压着一只旧手电和备用钥匙。",
        ),
        "2": MapObject(
            "blackboard",
            "异常黑板",
            "按 Space 检查黑板",
            "第二节课还没有结束。02:00。第 4 组，进度未完成。",
        ),
        "3": MapObject(
            "lectern",
            "讲台",
            "按 Space 检查讲台",
            "讲台上有一张纸条，边缘像被电流烧焦。",
        ),
        "4": MapObject(
            "security_desk",
            "值班桌",
            "按 Space 检查值班桌",
            "值班记录停在凌晨两点，之后每一行都是同一个时间。",
        ),
        "5": MapObject(
            "fuse_cabinet",
            "工具柜",
            "按 Space 打开工具柜",
            "柜子里放着一枚还能用的保险丝。",
        ),
        "6": MapObject(
            "battery",
            "备用电池",
            "按 Space 拾取电池",
            "地上有一节备用电池，外壳有些磨损。",
        ),
        "7": MapObject(
            "power_box",
            "配电箱",
            "按 Space 检查配电箱",
            "配电箱里缺了一枚保险丝。",
        ),
        "8": MapObject(
            "server_terminal",
            "机房终端",
            "按 Space 检查机房终端",
            "屏幕显示：LabMidnight.map，出口状态等待确认。",
        ),
        "9": MapObject(
            "exit_panel",
            "出口门禁",
            "按 Space 使用门禁",
            "门禁灯闪着红光，像是在等最后一次确认。",
        ),
    }


def _object_from_spec(spec: ObjectSpec, rotation: int = 0) -> MapObject:
    return MapObject(
        object_id=spec.object_id,
        name=spec.name,
        prompt=spec.prompt,
        description=spec.description,
        asset_id=spec.object_id,
        length=spec.length,
        width=spec.width,
        height=spec.height,
        placement_height=spec.placement_height,
        rotation=rotation % 360,
        solid=spec.solid,
    )


def _template_with_asset(template: MapObject, specs: dict[str, ObjectSpec], rotation: int = 0) -> MapObject:
    spec = specs.get(template.object_id)
    if spec is None:
        alias = LEGACY_OBJECT_ASSET_ALIASES.get(template.object_id)
        spec = specs.get(alias) if alias is not None else None
    if spec is None:
        return replace(
            template,
            asset_id=template.asset_id or template.object_id,
            rotation=rotation % 360,
            solid=_legacy_template_solid(template),
        )
    return replace(
        template,
        asset_id=spec.object_id,
        length=spec.length,
        width=spec.width,
        height=spec.height,
        placement_height=spec.placement_height,
        rotation=rotation % 360,
        solid=spec.solid,
    )


def _legacy_template_solid(template: MapObject) -> bool:
    if template.object_id in SOLID_TEMPLATE_OBJECT_IDS:
        return True
    return template.solid


def _object_with_metadata_overrides(obj: MapObject, raw: dict) -> MapObject:
    updates: dict[str, float] = {}
    length = _optional_positive_float(raw, "length")
    width = _optional_positive_float(raw, "width")
    height = _optional_positive_float(raw, "height")
    placement_height = _optional_non_negative_float(raw, "placement_height")
    if length is not None:
        updates["length"] = length
    if width is not None:
        updates["width"] = width
    if height is not None:
        updates["height"] = height
    if placement_height is not None:
        updates["placement_height"] = placement_height
    return replace(obj, **updates) if updates else obj


def _optional_positive_float(payload: dict, key: str) -> float | None:
    if key not in payload:
        return None
    try:
        return max(0.05, float(payload[key]))
    except (TypeError, ValueError):
        return None


def _optional_non_negative_float(payload: dict, key: str) -> float | None:
    if key not in payload:
        return None
    try:
        return max(0.0, float(payload[key]))
    except (TypeError, ValueError):
        return None


class GameMap:
    """A compact fourth-floor slice of the lab building."""

    def __init__(self, floor: int = BUILDING_TOP_FLOOR) -> None:
        self.floor = floor
        self.width = 34
        self.height = 16
        self.grid = [[TILE_WALL for _ in range(self.width)] for _ in range(self.height)]
        self.open_doors: set[tuple[int, int]] = set()
        self.door_open_progress: dict[tuple[int, int], float] = {}
        self.picked_objects: set[tuple[int, int]] = set()
        self.objects: dict[tuple[int, int], MapObject] = {}
        self.door_roles: dict[tuple[int, int], str] = {}
        self.door_groups: dict[tuple[int, int], frozenset[tuple[int, int]]] = {}
        self.object_specs = load_object_specs()
        self.start_position = (3.0, 3.0)
        layout_path = layout_path_for_floor(floor)
        if layout_path.exists():
            self._build_from_layout(layout_path)
        else:
            self._build_layout()
        self._hydrate_existing_objects()
        self._load_object_metadata()
        self._index_door_groups()

    def _build_from_layout(self, path: Path) -> None:
        rows = [
            line.rstrip("\n")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith(";")
        ]
        if not rows:
            self._build_layout()
            return

        self.width = max(len(row) for row in rows)
        self.height = len(rows)
        self.grid = [[TILE_WALL for _ in range(self.width)] for _ in range(self.height)]
        self.objects.clear()
        self.door_roles.clear()
        self.door_groups.clear()

        templates = object_templates()
        for y, row in enumerate(rows):
            for x, symbol in enumerate(row.ljust(self.width, "#")):
                self._apply_layout_symbol(x, y, symbol, templates)

    def _apply_layout_symbol(self, x: int, y: int, symbol: str, templates: dict[str, MapObject]) -> None:
        if symbol in {" ", "#"}:
            self._set_tile(x, y, TILE_WALL)
            return
        if symbol == ".":
            self._set_tile(x, y, TILE_EMPTY)
            return
        if symbol == "@":
            self._set_tile(x, y, TILE_EMPTY)
            self.start_position = (x + 0.5, y + 0.5)
            return

        door_symbols = {
            "G": (TILE_GUARD_DOOR, "guard"),
            "L": (TILE_LAB_DOOR, "lab"),
            "M": (TILE_LAB_DOOR, "server"),
            "C": (TILE_CLASSROOM_DOOR, "classroom"),
            "P": (TILE_POWER_DOOR, "power"),
            "E": (TILE_EXIT_DOOR, "exit"),
        }
        if symbol in door_symbols:
            tile, role = door_symbols[symbol]
            self._set_door_span(((x, y),), tile, role)
            return

        obj = templates.get(symbol)
        if obj is not None:
            self._set_tile(x, y, TILE_EMPTY)
            self.objects[(x, y)] = _template_with_asset(obj, self.object_specs)
            return

        self._set_tile(x, y, TILE_EMPTY)

    def _build_layout(self) -> None:
        self.start_position = (2.5, 3.5)
        self._carve_rect(1, 1, 8, 5)      # Initial lab
        self._carve_rect(18, 1, 30, 5)    # Abnormal classroom
        self._carve_rect(1, 7, 32, 8)     # Main corridor
        self._carve_rect(1, 10, 7, 14)    # Guard room
        self._carve_rect(10, 10, 16, 14)  # Power room
        self._carve_rect(19, 10, 24, 14)  # Server room
        self._carve_rect(27, 10, 32, 14)  # Exit area

        self._set_door_span(((5, 6),), TILE_LAB_DOOR, "lab")
        self._set_door_span(((23, 6),), TILE_CLASSROOM_DOOR, "classroom")
        self._set_door_span(((4, 9),), TILE_GUARD_DOOR, "guard")
        self._set_door_span(((13, 9),), TILE_POWER_DOOR, "power")
        self._set_door_span(((21, 9),), TILE_LAB_DOOR, "server")
        self._set_door_span(((29, 9),), TILE_EXIT_DOOR, "exit")

        self.objects[(3, 3)] = MapObject(
            "lab_desk",
            "实验桌",
            "按 Space 检查实验桌",
            "电脑还亮着，桌上压着一只旧手电和备用钥匙。",
        )
        self.objects[(28, 2)] = MapObject(
            "blackboard",
            "异常黑板",
            "按 Space 检查黑板",
            "第二节课还没有结束。02:00。第 4 组，进度未完成。",
        )
        self.objects[(21, 4)] = MapObject(
            "lectern",
            "讲台",
            "按 Space 检查讲台",
            "讲台上有一张纸条，边缘像被电流烧焦。",
        )
        self.objects[(3, 12)] = MapObject(
            "security_desk",
            "值班桌",
            "按 Space 检查值班桌",
            "值班记录停在凌晨两点，之后每一行都是同一个时间。",
        )
        self.objects[(5, 13)] = MapObject(
            "fuse_cabinet",
            "工具柜",
            "按 Space 打开工具柜",
            "柜子里放着一枚还能用的保险丝。",
        )
        self.objects[(8, 8)] = MapObject(
            "battery",
            "备用电池",
            "按 Space 拾取电池",
            "地上有一节备用电池，外壳有些磨损。",
        )
        self.objects[(13, 12)] = MapObject(
            "power_box",
            "配电箱",
            "按 Space 检查配电箱",
            "配电箱里缺了一枚保险丝。",
        )
        self.objects[(21, 12)] = MapObject(
            "server_terminal",
            "机房终端",
            "按 Space 检查机房终端",
            "屏幕显示：LabMidnight.map，出口状态等待确认。",
        )
        self.objects[(29, 12)] = MapObject(
            "exit_panel",
            "出口门禁",
            "按 Space 使用门禁",
            "门禁灯闪着红光，像是在等最后一次确认。",
        )

    def _hydrate_existing_objects(self) -> None:
        templates_by_id = {template.object_id: template for template in object_templates().values()}
        for cell, obj in list(self.objects.items()):
            template = templates_by_id.get(obj.object_id, obj)
            self.objects[cell] = _template_with_asset(template, self.object_specs, obj.rotation)

    def _load_object_metadata(self) -> None:
        meta_path = room_meta_path_for_floor(self.floor)
        if not meta_path.exists():
            return
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        raw_objects = payload.get("objects", [])
        if not isinstance(raw_objects, list):
            return

        templates = object_templates()
        templates_by_id = {template.object_id: template for template in templates.values()}
        for raw in raw_objects:
            if not isinstance(raw, dict):
                continue
            try:
                x = int(raw["x"])
                y = int(raw["y"])
            except (KeyError, TypeError, ValueError):
                continue
            object_id = str(raw.get("object_id") or raw.get("asset_id") or raw.get("symbol") or "")
            if not object_id:
                continue
            try:
                rotation = int(raw.get("rotation", 0)) % 360
            except (TypeError, ValueError):
                rotation = 0

            if object_id in templates:
                obj = _template_with_asset(templates[object_id], self.object_specs, rotation)
                self.objects[(x, y)] = _object_with_metadata_overrides(obj, raw)
            elif object_id in templates_by_id:
                obj = _template_with_asset(templates_by_id[object_id], self.object_specs, rotation)
                self.objects[(x, y)] = _object_with_metadata_overrides(obj, raw)
            elif object_id in self.object_specs:
                obj = _object_from_spec(self.object_specs[object_id], rotation)
                self.objects[(x, y)] = _object_with_metadata_overrides(obj, raw)

    def _carve_rect(self, x1: int, y1: int, x2: int, y2: int) -> None:
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self._set_tile(x, y, TILE_EMPTY)

    def _set_tile(self, x: int, y: int, tile: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = tile

    def _set_door_span(self, cells: Iterable[tuple[int, int]], tile: int, role: str) -> None:
        for x, y in cells:
            self._set_tile(x, y, tile)
            self.door_roles[(x, y)] = role

    def _index_door_groups(self) -> None:
        seen: set[tuple[int, int]] = set()
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) in seen or self.tile_at(x, y) not in DOOR_TILES:
                    continue
                tile = self.tile_at(x, y)
                role = self.door_role_at(x, y)
                group: set[tuple[int, int]] = set()
                stack = [(x, y)]
                seen.add((x, y))
                while stack:
                    current = stack.pop()
                    group.add(current)
                    cx, cy = current
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if (nx, ny) in seen:
                            continue
                        if self.tile_at(nx, ny) == tile and self.door_role_at(nx, ny) == role:
                            seen.add((nx, ny))
                            stack.append((nx, ny))
                frozen = frozenset(group)
                for cell in group:
                    self.door_groups[cell] = frozen

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return TILE_WALL
        return self.grid[y][x]

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

        west_open = self.tile_at(x - 1, y) != TILE_WALL
        east_open = self.tile_at(x + 1, y) != TILE_WALL
        north_open = self.tile_at(x, y - 1) != TILE_WALL
        south_open = self.tile_at(x, y + 1) != TILE_WALL
        if north_open and south_open and not (west_open and east_open):
            return "horizontal"
        return "vertical"

    def exit_spawn_pose(self) -> tuple[float, float, float]:
        exit_cells = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.tile_at(x, y) == TILE_EXIT_DOOR
        ]
        best: tuple[int, int, int, int, int] | None = None
        for door_x, door_y in exit_cells:
            for spawn_x, spawn_y in ((door_x + 1, door_y), (door_x - 1, door_y), (door_x, door_y + 1), (door_x, door_y - 1)):
                if not self._is_spawn_floor(spawn_x, spawn_y):
                    continue
                openness = sum(
                    1
                    for nx, ny in ((spawn_x + 1, spawn_y), (spawn_x - 1, spawn_y), (spawn_x, spawn_y + 1), (spawn_x, spawn_y - 1))
                    if self._is_spawn_floor(nx, ny)
                )
                candidate = (openness, door_x, door_y, spawn_x, spawn_y)
                if best is None or candidate > best:
                    best = candidate

        if best is None:
            return self.start_position[0], self.start_position[1], 0.0

        _, door_x, door_y, spawn_x, spawn_y = best
        player_x = spawn_x + 0.5
        player_y = spawn_y + 0.5
        angle = math.atan2(player_y - (door_y + 0.5), player_x - (door_x + 0.5)) % math.tau
        return player_x, player_y, angle

    def _is_spawn_floor(self, x: int, y: int) -> bool:
        tile = self.tile_at(x, y)
        return tile != TILE_WALL and tile not in DOOR_TILES

    def is_solid_cell(self, x: int, y: int) -> bool:
        tile = self.tile_at(x, y)
        if tile == TILE_WALL:
            return True
        if self.is_ground_exit_tile(x, y):
            return False
        if tile in DOOR_TILES and not self.is_open_door(x, y):
            return True
        return False

    def can_move_to(self, x: float, y: float) -> bool:
        radius_squared = PLAYER_RADIUS * PLAYER_RADIUS
        min_x = int(x - PLAYER_RADIUS)
        max_x = int(x + PLAYER_RADIUS)
        min_y = int(y - PLAYER_RADIUS)
        max_y = int(y + PLAYER_RADIUS)

        for cell_y in range(min_y, max_y + 1):
            for cell_x in range(min_x, max_x + 1):
                tile = self.tile_at(cell_x, cell_y)
                if tile == TILE_WALL and self._collides_wall_rect(x, y, cell_x, cell_y, radius_squared):
                    return False
                if self.is_ground_exit_tile(cell_x, cell_y):
                    continue
                if tile in DOOR_TILES and not self.is_passable_door(cell_x, cell_y):
                    if self._collides_wall_rect(x, y, cell_x, cell_y, radius_squared):
                        return False
        for anchor, obj in self.objects.items():
            if anchor in self.picked_objects or not obj.solid:
                continue
            object_radius_squared = OBJECT_COLLISION_RADIUS * OBJECT_COLLISION_RADIUS
            if self._collides_object_rect(x, y, anchor, obj, object_radius_squared):
                return False
        return True

    def is_ground_exit_tile(self, x: int, y: int) -> bool:
        return self.floor == BUILDING_BOTTOM_FLOOR and self.tile_at(x, y) == TILE_EXIT_DOOR

    def reached_ground_exit(self, x: float, y: float) -> bool:
        return self.is_ground_exit_tile(int(x), int(y))

    def _collides_wall_rect(self, x: float, y: float, cell_x: int, cell_y: int, radius_squared: float) -> bool:
        closest_x = min(max(x, cell_x), cell_x + 1.0)
        closest_y = min(max(y, cell_y), cell_y + 1.0)
        dx = x - closest_x
        dy = y - closest_y
        return dx * dx + dy * dy < radius_squared

    def _collides_closed_door(self, x: float, y: float, cell_x: int, cell_y: int) -> bool:
        group = self.door_group_at(cell_x, cell_y)
        xs = [gx for gx, _ in group]
        ys = [gy for _, gy in group]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        span_padding = PLAYER_RADIUS
        half_thickness = DOOR_COLLISION_THICKNESS / 2

        if self.door_orientation_at(cell_x, cell_y) == "vertical":
            plane_x = min_x + 0.5
            within_span = (min_y - span_padding) <= y <= (max_y + 1.0 + span_padding)
            return within_span and abs(x - plane_x) <= PLAYER_RADIUS + half_thickness

        plane_y = min_y + 0.5
        within_span = (min_x - span_padding) <= x <= (max_x + 1.0 + span_padding)
        return within_span and abs(y - plane_y) <= PLAYER_RADIUS + half_thickness

    def _collides_object_rect(self, x: float, y: float, anchor: tuple[int, int], obj: MapObject, radius_squared: float) -> bool:
        min_x, min_y, max_x, max_y = self.object_bounds(anchor, obj)
        closest_x = min(max(x, min_x), max_x)
        closest_y = min(max(y, min_y), max_y)
        dx = x - closest_x
        dy = y - closest_y
        return dx * dx + dy * dy < radius_squared

    def object_bounds(self, anchor: tuple[int, int], obj: MapObject) -> tuple[float, float, float, float]:
        length, width = obj.footprint_size()
        x, y = anchor
        return float(x), float(y), float(x) + max(0.05, length), float(y) + max(0.05, width)

    def object_anchor_at(self, x: int, y: int) -> tuple[int, int] | None:
        for anchor, obj in self.objects.items():
            if anchor in self.picked_objects:
                continue
            min_x, min_y, max_x, max_y = self.object_bounds(anchor, obj)
            if min_x <= x < max_x and min_y <= y < max_y:
                return anchor
        return None

    def object_at(self, x: int, y: int) -> MapObject | None:
        anchor = self.object_anchor_at(x, y)
        if anchor is None:
            return None
        return self.objects.get(anchor)

    def remove_object(self, x: int, y: int) -> None:
        anchor = self.object_anchor_at(x, y) or (x, y)
        self.picked_objects.add(anchor)

    def region_at(self, x: float, y: float) -> str:
        ix, iy = int(x), int(y)
        if 1 <= ix <= 8 and 1 <= iy <= 5:
            return "lab"
        if 18 <= ix <= 30 and 1 <= iy <= 5:
            return "classroom"
        if 1 <= ix <= 7 and 10 <= iy <= 14:
            return "security"
        if 10 <= ix <= 16 and 10 <= iy <= 14:
            return "power"
        if 19 <= ix <= 24 and 10 <= iy <= 14:
            return "server"
        if 27 <= ix <= 32 and 10 <= iy <= 14:
            return "exit"
        return "corridor"
