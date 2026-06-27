from __future__ import annotations

import math
from dataclasses import replace

import pygame

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement, Room


class MapEditorSelectionMixin:
    def _copy_selection(self) -> None:
        clipboard = self._copy_area_clipboard(self.selection_rect) if self.selection_rect is not None else self._copy_element_clipboard()
        if clipboard is None:
            self.state.status = "Nothing selected to copy."
            return
        self.clipboard = clipboard
        self.paste_anchor_cell = None
        label = str(clipboard.get("label", "selection"))
        width = int(clipboard.get("width", 1))
        height = int(clipboard.get("height", 1))
        self.state.status = f"Copied {label} ({width} x {height})."

    def _copy_element_clipboard(self) -> dict[str, object] | None:
        if self.state.selected_object is not None:
            anchor = self.state.selected_object
            placement = self.state.objects.get(anchor)
            if placement is None:
                return None
            width, height = self.state.object_footprint_size(placement)
            return {
                "kind": "element",
                "label": self.state.object_label(placement.object_id),
                "width": width,
                "height": height,
                "rooms": [],
                "terrain": [],
                "doors": [],
                "objects": [((0, 0), replace(placement))],
                "start": None,
            }

        if self.state.selected_door is not None and self.state.selected_door in self.state.doors:
            group = self.state.door_group_at(self.state.selected_door)
            if not group:
                return None
            min_x = min(x for x, _ in group)
            min_y = min(y for _, y in group)
            max_x = max(x for x, _ in group)
            max_y = max(y for _, y in group)
            return {
                "kind": "element",
                "label": "door",
                "width": max_x - min_x + 1,
                "height": max_y - min_y + 1,
                "rooms": [],
                "terrain": [],
                "doors": [((x - min_x, y - min_y), self.state.doors[(x, y)]) for x, y in sorted(group)],
                "objects": [],
                "start": None,
            }

        room = self.state.selected_room()
        if room is not None:
            return {
                "kind": "element",
                "label": room.name,
                "width": room.w,
                "height": room.h,
                "rooms": [Room(0, 0, 0, room.w, room.h, room.name, room.number)],
                "terrain": [],
                "doors": [],
                "objects": [],
                "start": None,
            }
        return None

    def _copy_area_clipboard(self, rect: tuple[int, int, int, int] | None) -> dict[str, object] | None:
        if rect is None:
            return None
        min_x, min_y, max_x, max_y = rect
        terrain = [
            ((x - min_x, y - min_y), self._terrain_symbol_at((x, y)))
            for y in range(min_y, max_y + 1)
            for x in range(min_x, max_x + 1)
        ]
        doors = [
            ((x - min_x, y - min_y), symbol)
            for (x, y), symbol in sorted(self.state.doors.items())
            if self._cell_in_rect((x, y), rect)
        ]
        objects = [
            ((x - min_x, y - min_y), replace(placement))
            for (x, y), placement in sorted(self.state.objects.items())
            if self._cell_in_rect((x, y), rect)
        ]
        start = None
        if self.state.start_cell is not None and self._cell_in_rect(self.state.start_cell, rect):
            start = (self.state.start_cell[0] - min_x, self.state.start_cell[1] - min_y)
        return {
            "kind": "area",
            "label": "area",
            "width": max_x - min_x + 1,
            "height": max_y - min_y + 1,
            "rooms": [],
            "terrain": terrain,
            "doors": doors,
            "objects": objects,
            "start": start,
        }

    def _terrain_symbol_at(self, cell: tuple[int, int]) -> str:
        if cell in self.state.overrides:
            return self.state.overrides[cell]
        for room in reversed(self.state.rooms):
            if not room.contains(cell):
                continue
            x, y = cell
            is_border = x in (room.x, room.x + room.w - 1) or y in (room.y, room.y + room.h - 1)
            return "#" if is_border else "."
        return "#"

    def _paste_clipboard(self) -> None:
        if self.clipboard is None:
            self.state.status = "Clipboard is empty."
            return
        target = self._paste_target_cell()
        if target is None:
            self.state.status = "Select or hover a target cell before pasting."
            return

        before = self._state_snapshot()
        self._push_history()
        pasted, skipped = self._apply_clipboard_at(self.clipboard, target)
        if pasted == 0:
            if self.undo_stack and self.undo_stack[-1] == before:
                self.undo_stack.pop()
            self.state.status = "Paste failed: copied content does not fit here."
            return
        self.redo_stack.clear()
        detail = f" Skipped {skipped} item(s)." if skipped else ""
        self.state.status = f"Pasted {pasted} item(s) at {target}.{detail}"

    def _paste_target_cell(self) -> tuple[int, int] | None:
        if self.paste_anchor_cell is not None:
            return self.paste_anchor_cell
        if self.hover_cell is not None:
            return self.hover_cell
        if self.state.selected_object is not None:
            return self.state.selected_object
        if self.state.selected_door is not None:
            return self.state.selected_door
        room = self.state.selected_room()
        if room is not None:
            return room.x, room.y
        if self.selection_rect is not None:
            return self.selection_rect[0], self.selection_rect[1]
        return None

    def _apply_clipboard_at(self, clipboard: dict[str, object], target: tuple[int, int]) -> tuple[int, int]:
        width = int(clipboard.get("width", 1))
        height = int(clipboard.get("height", 1))
        dest_rect = (target[0], target[1], target[0] + width - 1, target[1] + height - 1)
        self.state.ensure_grid_size_for([(dest_rect[2], dest_rect[3])])
        self._clear_paste_destination(dest_rect)

        pasted = 0
        skipped = 0

        rooms = clipboard.get("rooms", [])
        if isinstance(rooms, list):
            for room in rooms:
                if not isinstance(room, Room):
                    skipped += 1
                    continue
                new_id = self.state.next_room_id
                self.state.next_room_id += 1
                copied = Room(
                    new_id,
                    target[0] + room.x,
                    target[1] + room.y,
                    room.w,
                    room.h,
                    f"{room.name} Copy",
                    str(new_id),
                )
                self.state.rooms.append(copied)
                self.state.selected_room_id = copied.room_id
                self.state.selected_door = None
                self.state.selected_object = None
                pasted += 1
            if pasted:
                self.state.rebuild_grid()

        terrain = clipboard.get("terrain", [])
        if isinstance(terrain, list) and terrain:
            for entry in terrain:
                if not self._valid_offset_entry(entry):
                    skipped += 1
                    continue
                offset, symbol = entry
                cell = (target[0] + offset[0], target[1] + offset[1])
                if symbol in OVERRIDE_SYMBOLS:
                    self.state.overrides[cell] = symbol
                    pasted += 1
                else:
                    skipped += 1
            self.state.rebuild_grid()

        doors = clipboard.get("doors", [])
        if isinstance(doors, list) and doors:
            for entry in doors:
                if not self._valid_offset_entry(entry):
                    skipped += 1
                    continue
                offset, symbol = entry
                cell = (target[0] + offset[0], target[1] + offset[1])
                if symbol not in DOOR_SYMBOLS or not self.state.in_bounds(*cell):
                    skipped += 1
                    continue
                x, y = cell
                if self.state.grid[y][x] not in {"#", WINDOW_SYMBOL, *DOOR_SYMBOLS} or not self.state._can_hold_door(x, y):
                    skipped += 1
                    continue
                self.state.doors[cell] = symbol
                self.state.overrides.pop(cell, None)
                self.state.selected_door = cell
                self.state.selected_room_id = None
                self.state.selected_object = None
                pasted += 1
            self.state.rebuild_grid()

        objects = clipboard.get("objects", [])
        if isinstance(objects, list) and objects:
            for entry in objects:
                if not self._valid_offset_entry(entry):
                    skipped += 1
                    continue
                offset, placement = entry
                if not isinstance(placement, ObjectPlacement):
                    skipped += 1
                    continue
                cell = (target[0] + offset[0], target[1] + offset[1])
                copied = replace(placement)
                if not self.state._object_fits(cell, copied):
                    skipped += 1
                    continue
                self.state.objects[cell] = copied
                self.state.selected_object = cell
                self.state.selected_room_id = None
                self.state.selected_door = None
                pasted += 1
            self.state.rebuild_grid()

        start = clipboard.get("start")
        if isinstance(start, tuple) and len(start) == 2:
            cell = (target[0] + int(start[0]), target[1] + int(start[1]))
            if self.state._is_floor_target(cell) and self.state.object_anchor_at(cell) is None and cell not in self.state.doors:
                self.state.start_cell = cell
                pasted += 1
                self.state.rebuild_grid()
            else:
                skipped += 1

        if clipboard.get("kind") == "area" and pasted:
            self.selection_rect = dest_rect
            self.selection_items = self._collect_area_items(dest_rect)
            self._clear_individual_selection()
        else:
            self._clear_area_selection()
        self.paste_anchor_cell = target
        return pasted, skipped

    def _valid_offset_entry(self, entry: object) -> bool:
        if not isinstance(entry, tuple) or len(entry) != 2:
            return False
        offset, _payload = entry
        return isinstance(offset, tuple) and len(offset) == 2 and all(isinstance(value, int) for value in offset)

    def _clear_paste_destination(self, rect: tuple[int, int, int, int]) -> None:
        self.state.doors = {
            cell: symbol
            for cell, symbol in self.state.doors.items()
            if not self._cell_in_rect(cell, rect)
        }
        self.state.overrides = {
            cell: symbol
            for cell, symbol in self.state.overrides.items()
            if not self._cell_in_rect(cell, rect)
        }
        self.state.objects = {
            anchor: placement
            for anchor, placement in self.state.objects.items()
            if not any(self._cell_in_rect(cell, rect) for cell in self.state.object_footprint_cells(anchor, placement))
        }
        if self.state.start_cell is not None and self._cell_in_rect(self.state.start_cell, rect):
            self.state.start_cell = None
        self.state.rebuild_grid()

    def _rotate_active_object(self, delta: int) -> None:
        if self.state.selected_object is not None:
            current_anchor = self.state.selected_object
            placement = self.state.objects.get(current_anchor)
            if placement is not None:
                rotated = replace(placement, rotation=(placement.rotation + delta) % 360)
                target_anchor = self._best_rotated_object_anchor(current_anchor, placement, rotated)
                if target_anchor is None:
                    self.state.status = "Rotated object would overlap blocked cells. Move it or clear space."
                    return
                if target_anchor != current_anchor:
                    self.state.objects.pop(current_anchor, None)
                    self.state.selected_object = target_anchor
                self.state.objects[target_anchor] = rotated
                self.active_object_rotation = rotated.rotation
                self.state.rebuild_grid()
                move_note = f" and moved to {target_anchor}" if target_anchor != current_anchor else ""
                self.state.status = f"Rotated {self.state.object_label(rotated.object_id)} to {rotated.rotation} deg{move_note}."
                return
        self.active_object_rotation = (self.active_object_rotation + delta) % 360
        self.state.status = f"Placement rotation: {self.active_object_rotation} deg."

    def _best_rotated_object_anchor(
        self,
        current_anchor: tuple[int, int],
        placement: ObjectPlacement,
        rotated: ObjectPlacement,
    ) -> tuple[int, int] | None:
        for candidate in self._rotated_object_anchor_candidates(current_anchor, placement, rotated):
            if self.state._object_fits(candidate, rotated, ignore_anchor=current_anchor):
                return candidate
        return None

    def _rotated_object_anchor_candidates(
        self,
        current_anchor: tuple[int, int],
        placement: ObjectPlacement,
        rotated: ObjectPlacement,
    ) -> list[tuple[int, int]]:
        old_w, old_h = self.state.object_footprint_size(placement)
        new_w, new_h = self.state.object_footprint_size(rotated)
        center_x = current_anchor[0] + old_w / 2.0
        center_y = current_anchor[1] + old_h / 2.0
        desired_x = center_x - new_w / 2.0
        desired_y = center_y - new_h / 2.0

        candidates: list[tuple[int, int]] = []

        def add(anchor: tuple[int, int]) -> None:
            if anchor not in candidates:
                candidates.append(anchor)

        add(current_anchor)
        desired_x_candidates = self._nearby_anchor_values(desired_x)
        desired_y_candidates = self._nearby_anchor_values(desired_y)
        desired_pairs = [
            (x, y)
            for x in desired_x_candidates
            for y in desired_y_candidates
        ]
        desired_pairs.sort(key=lambda item: abs(item[0] - desired_x) + abs(item[1] - desired_y))
        for x, y in desired_pairs:
            add((x, y))

        base_x = int(round(desired_x))
        base_y = int(round(desired_y))
        for radius in range(1, 4):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if abs(dx) + abs(dy) != radius:
                        continue
                    add((base_x + dx, base_y + dy))
        return candidates

    def _nearby_anchor_values(self, value: float) -> list[int]:
        values: list[int] = []
        for candidate in (round(value), math.floor(value), math.ceil(value)):
            candidate = int(candidate)
            if candidate not in values:
                values.append(candidate)
        return values

    def _begin_object_resize_at(self, pos: tuple[int, int]) -> bool:
        handle = self._object_resize_handle_at(pos)
        if handle is None or self.state.selected_object is None:
            return False
        placement = self.state.objects.get(self.state.selected_object)
        if placement is None:
            return False
        self._clear_area_selection()
        self.drag_mode = "resize_object"
        self.drag_initial_object = (self.state.selected_object, replace(placement), handle)
        self.drag_start_cell = self.state.selected_object
        self.drag_current_cell = self.state.selected_object
        self.state.status = "Drag object corner to resize footprint."
        return True

    def _object_resize_handle_at(self, pos: tuple[int, int]) -> str | None:
        anchor = self.state.selected_object
        if anchor is None:
            return None
        placement = self.state.objects.get(anchor)
        if placement is None:
            return None
        for handle, rect in self._object_resize_handle_rects(anchor, placement).items():
            if rect.collidepoint(pos):
                return handle
        return None

    def _object_resize_handle_rects(self, anchor: tuple[int, int], placement: ObjectPlacement) -> dict[str, pygame.Rect]:
        width, height = self.state.object_footprint_size(placement)
        sx, sy = self._screen_from_cell(*anchor)
        rect = pygame.Rect(sx, sy, width * self.cell_size, height * self.cell_size)
        half = OBJECT_HANDLE_SIZE // 2
        points = {
            "nw": rect.topleft,
            "ne": rect.topright,
            "sw": rect.bottomleft,
            "se": rect.bottomright,
        }
        return {
            handle: pygame.Rect(point[0] - half, point[1] - half, OBJECT_HANDLE_SIZE, OBJECT_HANDLE_SIZE)
            for handle, point in points.items()
        }

    def _begin_select_drag(self, cell: tuple[int, int]) -> None:
        if cell in self.state.doors:
            self._clear_area_selection()
            self.state.selected_door = cell
            self.state.selected_room_id = None
            self.state.selected_object = None
            return
        object_anchor = self.state.object_anchor_at(cell)
        if object_anchor is not None:
            self._clear_area_selection()
            self.state.selected_object = object_anchor
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

    def _move_cell_dict_snapshot(self, key: str, dx: int, dy: int) -> dict:
        base = self.selection_move_snapshot.get(f"base_{key}") if self.selection_move_snapshot else None
        selected = self.selection_move_snapshot.get(f"selected_{key}") if self.selection_move_snapshot else None
        moved: dict = dict(base) if isinstance(base, dict) else {}
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

        object_cells = items["objects"]
        for cell, placement in self.state.objects.items():
            if any(self._cell_in_rect(footprint_cell, rect) for footprint_cell in self.state.object_footprint_cells(cell, placement)):
                object_cells.add(cell)
        if object_cells:
            return items

        door_cells = items["doors"]
        for cell in self.state.doors:
            if self._cell_in_rect(cell, rect):
                door_cells.add(cell)
        if door_cells:
            return items

        for cell in self.state.overrides:
            if self._cell_in_rect(cell, rect):
                items["overrides"].add(cell)
        if self.state.start_cell is not None and self._cell_in_rect(self.state.start_cell, rect):
            items["start"] = True
        if items["overrides"] or items["start"]:
            return items

        room_ids = items["rooms"]
        for room in self.state.rooms:
            if self._room_intersects_rect(room, rect):
                room_ids.add(room.room_id)
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

    def _resize_selected_object_from_corner(self, cell: tuple[int, int]) -> None:
        if self.drag_initial_object is None:
            return
        original_anchor, original_placement, handle = self.drag_initial_object
        current_anchor = self.state.selected_object
        if current_anchor is None or current_anchor not in self.state.objects:
            return

        original_width, original_height = self.state.object_footprint_size(original_placement)
        left = original_anchor[0]
        top = original_anchor[1]
        right = left + original_width - 1
        bottom = top + original_height - 1

        if "w" in handle:
            new_left = max(0, min(cell[0], right))
            new_right = right
        else:
            new_left = left
            new_right = max(left, cell[0])

        if "n" in handle:
            new_top = max(0, min(cell[1], bottom))
            new_bottom = bottom
        else:
            new_top = top
            new_bottom = max(top, cell[1])

        visible_width = max(1, new_right - new_left + 1)
        visible_height = max(1, new_bottom - new_top + 1)
        rotation = original_placement.rotation % 360
        if rotation in (90, 270):
            length = float(visible_height)
            width = float(visible_width)
        else:
            length = float(visible_width)
            width = float(visible_height)
        _, original_width, _, _ = self.state.object_dimensions(original_placement)
        object_id = self.state._canonical_object_id(original_placement.object_id)
        if object_id in WALL_FACING_OBJECT_IDS and original_width <= 0.15:
            width = original_width

        if self.state.update_selected_object(anchor=(new_left, new_top), length=length, width=width):
            self.state.status = f"Object footprint resized to {visible_width} x {visible_height}."

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
        elif self.active_tool == "window":
            self.state.place_window(cell)
        elif self.active_tool == "erase":
            self.state.erase_cell(cell)
        elif self.active_tool == "start":
            self.state.place_start(cell)
        elif self.active_tool == "object":
            self._place_active_object(cell)

    def _place_active_object(self, cell: tuple[int, int]) -> None:
        existing_anchor = self.state.object_anchor_at(cell)
        if existing_anchor is not None:
            self._select_object(existing_anchor)
            return
        self.state.place_object(
            cell,
            self.active_object_symbol,
            self.active_object_rotation,
            auto_wall_snap=self.auto_wall_snap,
        )
        if self.state.selected_object is not None:
            placement = self.state.objects.get(self.state.selected_object)
            if placement is not None:
                self.active_object_rotation = placement.rotation

    def _select_object(self, anchor: tuple[int, int]) -> None:
        placement = self.state.objects.get(anchor)
        if placement is None:
            return
        self._clear_area_selection()
        self.state.selected_object = anchor
        self.state.selected_room_id = None
        self.state.selected_door = None
        self.active_object_symbol = placement.object_id
        self.active_object_rotation = placement.rotation
        self.state.status = f"Selected {self.state.object_label(placement.object_id)} at {anchor}."
