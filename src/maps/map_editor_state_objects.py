from __future__ import annotations

from dataclasses import replace

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement


class MapEditorStateObjectMixin:
    def place_object(
        self,
        cell: tuple[int, int],
        object_id: str,
        rotation: int = 0,
        *,
        auto_wall_snap: bool = False,
    ) -> None:
        object_id = self._canonical_object_id(object_id)
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
            (1, 0, 270),
            (0, 1, 180),
            (-1, 0, 90),
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
        object_id = self._canonical_object_id(object_id)
        updated = replace(
            placement,
            object_id=object_id,
            length=None,
            width=None,
            height=None,
            placement_height=None,
            rotation=placement.rotation % 360,
        )
        if not self._object_fits(current_anchor, updated, ignore_anchor=current_anchor):
            self.status = "Selected asset does not fit at this position."
            return False
        self.objects[current_anchor] = updated
        self.rebuild_grid()
        self.status = f"Selected object changed to {self.object_label(object_id)}."
        return True

    def update_selected_object_binding(self, **updates) -> bool:
        current_anchor = self.selected_object
        if current_anchor is None:
            return False
        placement = self.objects.get(current_anchor)
        if placement is None:
            return False
        data = {
            "element_type": placement.element_type,
            "pickup_item": placement.pickup_item,
            "pickup_flag": placement.pickup_flag,
            "interaction_prompt": placement.interaction_prompt,
            "interaction_message": placement.interaction_message,
            "required_item": placement.required_item,
            "required_flag": placement.required_flag,
            "failure_message": placement.failure_message,
            "remove_on_pickup": placement.remove_on_pickup,
            "random_drop": placement.random_drop,
            "drop_count": placement.drop_count,
            "is_trigger": placement.is_trigger,
            "trigger_id": placement.trigger_id,
            "trigger_once": placement.trigger_once,
            "resource_role": placement.resource_role,
        }
        data.update(updates)
        element_type = str(data["element_type"])
        if element_type not in VALID_ELEMENT_TYPES:
            element_type = ELEMENT_STORY
        resource_role = str(data["resource_role"]).strip().lower()
        if resource_role not in RESOURCE_ROLES:
            resource_role = ""
        self.objects[current_anchor] = replace(
            placement,
            element_type=element_type,
            pickup_item=str(data["pickup_item"]).strip(),
            pickup_flag=str(data["pickup_flag"]).strip(),
            interaction_prompt=str(data["interaction_prompt"]).strip(),
            interaction_message=str(data["interaction_message"]).strip(),
            required_item=str(data["required_item"]).strip(),
            required_flag=str(data["required_flag"]).strip(),
            failure_message=str(data["failure_message"]).strip(),
            remove_on_pickup=bool(data["remove_on_pickup"]),
            random_drop=bool(data["random_drop"]),
            drop_count=max(1, int(data["drop_count"])),
            is_trigger=bool(data["is_trigger"]),
            trigger_id=str(data["trigger_id"]).strip(),
            trigger_once=bool(data["trigger_once"]),
            resource_role=resource_role,
        )
        self.status = "Object story binding updated."
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
        object_id = self._canonical_object_id(object_id)
        spec = self.object_specs.get(object_id)
        if spec is None:
            length, width, height, placement_height = 1.0, 1.0, 1.0, 0.0
        else:
            length, width, height, placement_height = spec.length, spec.width, spec.height, spec.placement_height
        style = FIXED_OBJECT_STYLES.get(object_id)
        if style is not None:
            length = float(style.get("length", length))
            width = float(style.get("width", width))
            height = float(style.get("height", height))
            placement_height = float(style.get("placement_height", placement_height))
        return length, width, height, placement_height

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
        for anchor, placement in reversed(list(self.objects.items())):
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
        if self.grid[y][x] not in {"#", WINDOW_SYMBOL, *DOOR_SYMBOLS}:
            return False
        north = self._floorish(x, y - 1)
        south = self._floorish(x, y + 1)
        west = self._floorish(x - 1, y)
        east = self._floorish(x + 1, y)
        return north or south or west or east

    def _floorish(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.grid[y][x] in FLOOR_CHARS | {"."}


