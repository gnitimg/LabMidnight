from __future__ import annotations

from dataclasses import asdict
import json

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement


class MapEditorStateDoorSaveMixin:
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

    def door_group_at(self, cell: tuple[int, int]) -> frozenset[tuple[int, int]]:
        symbol = self.doors.get(cell)
        if symbol is None:
            return frozenset()
        seen: set[tuple[int, int]] = set()
        pending = [cell]
        while pending:
            current = pending.pop()
            if current in seen or self.doors.get(current) != symbol:
                continue
            seen.add(current)
            x, y = current
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor not in seen and self.doors.get(neighbor) == symbol:
                    pending.append(neighbor)
        return frozenset(seen)

    def door_orientation_at(self, cell: tuple[int, int]) -> str:
        group = self.door_group_at(cell)
        if not group:
            return "vertical"
        xs = [x for x, _ in group]
        ys = [y for _, y in group]
        width = max(xs) - min(xs) + 1
        height = max(ys) - min(ys) + 1
        if width > height:
            return "horizontal"
        if height > width:
            return "vertical"

        x, y = cell
        west_open = self._floorish(x - 1, y)
        east_open = self._floorish(x + 1, y)
        north_open = self._floorish(x, y - 1)
        south_open = self._floorish(x, y + 1)
        west_wall = self._door_wallish(x - 1, y)
        east_wall = self._door_wallish(x + 1, y)
        north_wall = self._door_wallish(x, y - 1)
        south_wall = self._door_wallish(x, y + 1)
        if (west_wall and east_wall and (north_open or south_open)) or (north_open and south_open and not (west_open and east_open)):
            return "horizontal"
        if north_wall and south_wall and (west_open or east_open):
            return "vertical"
        return "vertical"

    def _door_wallish(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.grid[y][x] in {"#", WINDOW_SYMBOL, *DOOR_SYMBOLS}

    def door_span_length(self, cell: tuple[int, int]) -> int:
        group = self.door_group_at(cell)
        if not group:
            return 0
        if self.door_orientation_at(cell) == "horizontal":
            xs = [x for x, _ in group]
            return max(xs) - min(xs) + 1
        ys = [y for _, y in group]
        return max(ys) - min(ys) + 1

    def resize_selected_door(self, length: int) -> bool:
        current = self.selected_door
        if current is None or current not in self.doors:
            return False
        symbol = self.doors[current]
        group = self.door_group_at(current)
        if not group:
            return False
        length = max(1, int(length))
        orientation = self.door_orientation_at(current)
        old_group = set(group)
        for cells in self._door_span_candidates(current, group, orientation, length):
            if not self._door_span_fits(cells, old_group):
                continue
            for old_cell in old_group:
                self.doors.pop(old_cell, None)
            for cell in cells:
                self.doors[cell] = symbol
                self.overrides.pop(cell, None)
            self.selected_door = current if current in cells else cells[0]
            self.selected_room_id = None
            self.selected_object = None
            self.rebuild_grid()
            self.status = f"Door span resized to {length}."
            return True
        self.status = "Door span does not fit valid wall cells."
        return False

    def _door_span_candidates(
        self,
        selected: tuple[int, int],
        group: frozenset[tuple[int, int]],
        orientation: str,
        length: int,
    ) -> list[list[tuple[int, int]]]:
        xs = [x for x, _ in group]
        ys = [y for _, y in group]
        starts: list[int] = []
        if orientation == "horizontal":
            y = selected[1] if any(gy == selected[1] for _, gy in group) else min(ys)
            old_start = min(xs)
            old_end = max(xs)
            center = (old_start + old_end) / 2
            for candidate in (old_start, int(round(center - (length - 1) / 2)), selected[0] - length // 2, old_end - length + 1):
                if candidate not in starts:
                    starts.append(candidate)
            return [[(x, y) for x in range(start, start + length)] for start in starts]

        x = selected[0] if any(gx == selected[0] for gx, _ in group) else min(xs)
        old_start = min(ys)
        old_end = max(ys)
        center = (old_start + old_end) / 2
        for candidate in (old_start, int(round(center - (length - 1) / 2)), selected[1] - length // 2, old_end - length + 1):
            if candidate not in starts:
                starts.append(candidate)
        return [[(x, y) for y in range(start, start + length)] for start in starts]

    def _door_span_fits(self, cells: list[tuple[int, int]], old_group: set[tuple[int, int]]) -> bool:
        for cell in cells:
            x, y = cell
            if not self.in_bounds(x, y):
                return False
            if cell in self.doors and cell not in old_group:
                return False
            if self.start_cell == cell:
                return False
            if self.object_anchor_at(cell) is not None:
                return False
            if self.grid[y][x] not in {"#", WINDOW_SYMBOL, *DOOR_SYMBOLS}:
                return False
            if not self._can_hold_door(x, y):
                return False
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
        item = {
            "x": x,
            "y": y,
            "object_id": self._canonical_object_id(placement.object_id),
            "rotation": placement.rotation % 360,
            "length": length,
            "width": width,
            "height": height,
            "placement_height": placement_height,
        }
        if placement.element_type != ELEMENT_STORY:
            item["element_type"] = placement.element_type
        if placement.pickup_item:
            item["pickup_item"] = placement.pickup_item
        if placement.pickup_flag:
            item["pickup_flag"] = placement.pickup_flag
        if placement.is_trigger:
            item["is_trigger"] = True
        if placement.trigger_id:
            item["trigger_id"] = placement.trigger_id
        if not placement.trigger_once:
            item["trigger_once"] = False
        if placement.resource_role:
            item["resource_role"] = placement.resource_role
        if placement.interaction_prompt:
            item["interaction_prompt"] = placement.interaction_prompt
        if placement.interaction_message:
            item["interaction_message"] = placement.interaction_message
        if placement.required_item:
            item["required_item"] = placement.required_item
        if placement.required_flag:
            item["required_flag"] = placement.required_flag
        if placement.failure_message:
            item["failure_message"] = placement.failure_message
        if placement.remove_on_pickup:
            item["remove_on_pickup"] = True
        if placement.random_drop:
            item["random_drop"] = True
            item["drop_count"] = max(1, placement.drop_count)
        elif placement.drop_count != 1:
            item["drop_count"] = max(1, placement.drop_count)
        return item

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
            "; Terrain: # wall, W window wall, . floor, @ player start",
            "; Doors: L lab, M machine/server lab-style, C classroom, G guard, P power, E exit",
            "; Legacy objects: 1-9 story objects defined in src/map_data.py",
            "; Custom objects are stored in the floor metadata JSON.",
            "",
        ]
        lines.extend("".join(row) for row in self.grid)
        return "\n".join(lines) + "\n"



