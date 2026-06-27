from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from src.maps.map_objects import (
    ELEMENT_PICKUP,
    MapObject,
    WALL_FACING_OBJECT_IDS,
    WALL_FACING_ROTATIONS,
    _object_from_spec,
    _object_with_metadata_overrides,
    _template_with_asset,
    object_templates,
)
from src.maps.map_paths import room_meta_path_for_floor
from src.settings import (
    DOOR_TILES,
    TILE_CLASSROOM_DOOR,
    TILE_EMPTY,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
    TILE_WALL,
    TILE_WINDOW,
    WALL_TILES,
)


class GameMapBuildMixin:
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
        if symbol == "W":
            self._set_tile(x, y, TILE_WINDOW)
            return
        if symbol == ".":
            self._set_tile(x, y, TILE_EMPTY)
            return
        if symbol == "@":
            self._set_tile(x, y, TILE_EMPTY)
            self.start_position = (x + 0.5, y + 0.5)
            self.has_explicit_start_position = True
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
            "elevator",
            "东11C货梯",
            "按 Space 使用东11C货梯",
            "货梯面板亮着，楼层按钮停在 1 到 4。",
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

    def _normalize_wall_facing_objects(self) -> None:
        for anchor, obj in list(self.objects.items()):
            normalized = obj
            if normalized.object_id in WALL_FACING_OBJECT_IDS:
                rotation = self._room_facing_rotation(anchor, normalized)
                if rotation is not None:
                    normalized = replace(normalized, rotation=rotation)
            self.objects[anchor] = normalized

    def _room_facing_rotation(self, anchor: tuple[int, int], obj: MapObject) -> int | None:
        occupied = self._object_occupied_cells(anchor, obj)
        if not occupied:
            return None

        scores: dict[int, int] = {}
        for dx, dy, rotation in WALL_FACING_ROTATIONS:
            score = 0
            for x, y in occupied:
                adjacent = (x + dx, y + dy)
                if adjacent in occupied:
                    continue
                if self.tile_at(*adjacent) in WALL_TILES:
                    score += 1
            scores[rotation] = score

        best_score = max(scores.values(), default=0)
        if best_score <= 0:
            return None

        current = obj.rotation % 360
        best_rotations = {rotation for rotation, score in scores.items() if score == best_score}
        if current in best_rotations:
            return current
        return min(best_rotations, key=lambda rotation: ((rotation - current) % 360, rotation))

    def _apply_random_pickup_drops(self) -> None:
        candidates_by_item: dict[str, list[tuple[tuple[int, int], MapObject]]] = {}
        for anchor, obj in self.objects.items():
            if obj.element_type != ELEMENT_PICKUP or not obj.random_drop:
                continue
            item_id = obj.pickup_item or obj.object_id
            candidates_by_item.setdefault(item_id, []).append((anchor, obj))

        for item_id, candidates in candidates_by_item.items():
            keep_count = max(1, max(obj.drop_count for _anchor, obj in candidates))
            if keep_count >= len(candidates):
                continue
            kept = set(random.sample([anchor for anchor, _obj in candidates], keep_count))
            for anchor, _obj in candidates:
                if anchor not in kept:
                    self.picked_objects.add(anchor)

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
