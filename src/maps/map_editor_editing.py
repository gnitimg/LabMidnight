from __future__ import annotations

import pygame

from src.maps.map_editor_config import *


class MapEditorEditingMixin:
    def _edit_text(self, event: pygame.event.Event) -> None:
        if self.editing_field in NUMERIC_FIELDS:
            self._edit_number(event)
            return

        if self.editing_field in OBJECT_TEXT_FIELDS:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._commit_editing_field()
                return
            if event.key == pygame.K_ESCAPE:
                self._cancel_editing_field()
                return
            if event.key == pygame.K_BACKSPACE:
                self.edit_buffer = self.edit_buffer[:-1]
                return
            typed = getattr(event, "unicode", "")
            if typed and typed.isprintable():
                limit = 120 if self.editing_field in {"object_interaction_message", "object_failure_message"} else 48
                self.edit_buffer = (self.edit_buffer + typed)[:limit]
            return

        room = self.state.selected_room()
        if room is None or self.editing_field is None:
            self._cancel_editing_field()
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._commit_editing_field()
            return
        if event.key == pygame.K_ESCAPE:
            self._cancel_editing_field()
            return
        if event.key == pygame.K_BACKSPACE:
            self.edit_buffer = self.edit_buffer[:-1]
            return
        typed = getattr(event, "unicode", "")
        if typed and typed.isprintable():
            limit = 32 if self.editing_field == "name" else 16
            self.edit_buffer = (self.edit_buffer + typed)[:limit]

    def _edit_number(self, event: pygame.event.Event) -> None:
        if self.editing_field is None:
            return
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._commit_editing_field()
            return
        if event.key == pygame.K_ESCAPE:
            self._cancel_editing_field()
            return

        if event.key == pygame.K_BACKSPACE:
            self.edit_buffer = self.edit_buffer[:-1]
            return

        typed = getattr(event, "unicode", "")
        if typed and typed.isdigit():
            max_digits = 4 if self.editing_field in {"grid_width", "grid_height", "object_x", "object_y", "room_x", "room_y", "room_w", "room_h"} else 5
            if len(self.edit_buffer) < max_digits:
                self.edit_buffer += typed
            return
        if self.editing_field in FLOAT_NUMERIC_FIELDS:
            if typed == "." and "." not in self.edit_buffer and self.edit_buffer:
                self.edit_buffer += typed

    def _begin_editing_field(self, field: str) -> None:
        if self.editing_field == field:
            return
        self._commit_editing_field()
        if field in {"name", "number"} and self.state.selected_room() is None:
            return
        if field in ROOM_NUMERIC_FIELDS and self.state.selected_room() is None:
            return
        if field in OBJECT_NUMERIC_FIELDS and self.state.selected_object is None:
            return
        if field in DOOR_NUMERIC_FIELDS and self.state.selected_door is None:
            return
        if field in OBJECT_TEXT_FIELDS and self.state.selected_object is None:
            return
        self.editing_field = field
        self.edit_buffer = self._editing_field_value(field)

    def _commit_editing_field(self) -> None:
        field = self.editing_field
        if field is None:
            return
        before = self._state_snapshot()
        if field in OBJECT_NUMERIC_FIELDS:
            self._set_object_numeric_field(field, self.edit_buffer)
        elif field in OBJECT_TEXT_FIELDS:
            self._set_object_text_field(field, self.edit_buffer)
        elif field in NUMERIC_FIELDS:
            if field in FLOAT_NUMERIC_FIELDS:
                try:
                    value = float(self.edit_buffer) if self.edit_buffer else 0.0
                except ValueError:
                    self.state.status = "Field needs a number."
                    self._cancel_editing_field()
                    return
            else:
                value = int(self.edit_buffer) if self.edit_buffer else 0
            self._set_numeric_field(field, value)
        else:
            room = self.state.selected_room()
            if room is not None:
                if field == "name":
                    room.name = self.edit_buffer[:32]
                elif field == "number":
                    room.number = self.edit_buffer[:16]
                self.state.status = "Room metadata updated."
        if self._state_snapshot() != before:
            self.undo_stack.append(before)
            if len(self.undo_stack) > HISTORY_LIMIT:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
        self._cancel_editing_field()

    def _cancel_editing_field(self) -> None:
        self.editing_field = None
        self.edit_buffer = ""

    def _editing_field_value(self, field: str) -> str:
        if field in NUMERIC_FIELDS:
            return self._numeric_field_value(field)
        if field in OBJECT_TEXT_FIELDS:
            return self._object_text_field_value(field)
        room = self.state.selected_room()
        if room is None:
            return ""
        if field == "name":
            return room.name
        if field == "number":
            return room.number
        return ""

    def _numeric_field_value(self, field: str) -> str:
        if field in ROOM_NUMERIC_FIELDS:
            return self._room_numeric_field_value(field)
        if field in OBJECT_NUMERIC_FIELDS:
            return self._object_numeric_field_value(field)
        if field in DOOR_NUMERIC_FIELDS:
            return self._door_numeric_field_value(field)
        values = {
            "grid_width": self.state.grid_width,
            "grid_height": self.state.grid_height,
            "initial_hp": self.state.initial_hp,
            "initial_sanity": self.state.initial_sanity,
            "initial_battery": self.state.initial_battery,
            "player_speed": self.state.player_speed,
        }
        value = values.get(field, 0)
        return self._format_number(value) if isinstance(value, float) else str(value)

    def _room_numeric_field_value(self, field: str) -> str:
        room = self.state.selected_room()
        if room is None:
            return "0"
        values = {
            "room_x": room.x,
            "room_y": room.y,
            "room_w": room.w,
            "room_h": room.h,
        }
        return str(values.get(field, 0))

    def _door_numeric_field_value(self, field: str) -> str:
        cell = self.state.selected_door
        if cell is None:
            return "0"
        if field == "door_length":
            return str(self.state.door_span_length(cell))
        return "0"

    def _object_text_field_value(self, field: str) -> str:
        cell = self.state.selected_object
        if cell is None:
            return ""
        placement = self.state.objects.get(cell)
        if placement is None:
            return ""
        values = {
            "object_pickup_item": placement.pickup_item,
            "object_pickup_flag": placement.pickup_flag,
            "object_trigger_id": placement.trigger_id,
            "object_resource_role": placement.resource_role,
            "object_interaction_prompt": placement.interaction_prompt,
            "object_interaction_message": placement.interaction_message,
            "object_required_item": placement.required_item,
            "object_required_flag": placement.required_flag,
            "object_failure_message": placement.failure_message,
        }
        return values.get(field, "")

    def _object_numeric_field_value(self, field: str) -> str:
        cell = self.state.selected_object
        if cell is None:
            return "0"
        placement = self.state.objects.get(cell)
        if placement is None:
            return "0"
        length, width, height, placement_height = self.state.object_dimensions(placement)
        values = {
            "object_x": cell[0],
            "object_y": cell[1],
            "object_footprint_w": length,
            "object_footprint_d": width,
            "object_height": height,
            "object_z": placement_height,
            "object_drop_count": placement.drop_count,
        }
        return self._format_number(values.get(field, 0))

    def _format_number(self, value: float | int) -> str:
        if isinstance(value, int) or abs(value - int(value)) < 0.001:
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _set_numeric_field(self, field: str, value: int | float) -> None:
        if field == "grid_width":
            self.state.resize_grid(max(MIN_GRID_WIDTH, int(value)), self.state.grid_height)
        elif field == "grid_height":
            self.state.resize_grid(self.state.grid_width, max(MIN_GRID_HEIGHT, int(value)))
        elif field == "initial_hp":
            self.state.initial_hp = max(0, min(999, int(value)))
        elif field == "initial_sanity":
            self.state.initial_sanity = max(0, min(999, int(value)))
        elif field == "initial_battery":
            self.state.initial_battery = max(0, min(999, int(value)))
        elif field == "player_speed":
            self.state.player_speed = max(PLAYER_SPEED_MIN, min(PLAYER_SPEED_MAX, float(value)))
        elif field == "door_length":
            self.state.resize_selected_door(max(1, int(value)))
        elif field == "room_x":
            self.state.update_selected_room(x=max(0, int(value)))
        elif field == "room_y":
            self.state.update_selected_room(y=max(0, int(value)))
        elif field == "room_w":
            self.state.update_selected_room(w=max(MIN_ROOM_SIZE, int(value)))
        elif field == "room_h":
            self.state.update_selected_room(h=max(MIN_ROOM_SIZE, int(value)))

    def _set_object_numeric_field(self, field: str, text: str) -> None:
        cell = self.state.selected_object
        if cell is None:
            return
        try:
            raw_value = float(text) if text else 0.0
        except ValueError:
            self.state.status = "Object field needs a number."
            return

        if field == "object_x":
            self.state.update_selected_object(anchor=(max(0, int(raw_value)), cell[1]))
        elif field == "object_y":
            self.state.update_selected_object(anchor=(cell[0], max(0, int(raw_value))))
        elif field == "object_footprint_w":
            self.state.update_selected_object(length=max(0.05, raw_value))
        elif field == "object_footprint_d":
            self.state.update_selected_object(width=max(0.05, raw_value))
        elif field == "object_height":
            self.state.update_selected_object(height=max(0.05, raw_value))
        elif field == "object_z":
            self.state.update_selected_object(placement_height=max(0.0, raw_value))
        elif field == "object_drop_count":
            self.state.update_selected_object_binding(drop_count=max(1, int(raw_value)))

    def _set_object_text_field(self, field: str, text: str) -> None:
        updates = {
            "object_pickup_item": {"pickup_item": text},
            "object_pickup_flag": {"pickup_flag": text},
            "object_trigger_id": {"trigger_id": text, "is_trigger": bool(text.strip())},
            "object_resource_role": {"resource_role": text},
            "object_interaction_prompt": {"interaction_prompt": text},
            "object_interaction_message": {"interaction_message": text},
            "object_required_item": {"required_item": text},
            "object_required_flag": {"required_flag": text},
            "object_failure_message": {"failure_message": text},
        }.get(field)
        if updates is not None:
            self.state.update_selected_object_binding(**updates)


