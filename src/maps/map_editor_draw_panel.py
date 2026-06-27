from __future__ import annotations

import pygame

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement


class MapEditorDrawPanelMixin:
    def _draw_panel(self) -> None:
        panel = self.panel_rect
        pygame.draw.rect(self.screen, COLOR_PANEL, panel)
        self.panel_fields.clear()
        self.panel_toggles.clear()
        self.floor_buttons.clear()
        self.object_buttons.clear()
        self._clamp_side_scrolls()
        clip = self.screen.get_clip()
        self.screen.set_clip(panel)

        def py(value: int) -> int:
            return panel.y + value - self.panel_scroll_y

        self._draw_text("Properties", (panel.x + 20, py(20)), self.big_font, COLOR_TEXT)
        self._draw_text("Floor", (panel.x + 20, py(58)), self.small_font, COLOR_MUTED)
        for index, floor in enumerate(range(BOTTOM_FLOOR, TOP_FLOOR + 1)):
            rect = pygame.Rect(panel.x + 68 + index * 42, py(52), 32, 28)
            self.floor_buttons[floor] = rect
            active = floor == self.state.floor
            pygame.draw.rect(self.screen, (54, 64, 65) if active else (31, 38, 40), rect, border_radius=4)
            pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=4)
            self._draw_centered_text(str(floor), rect, self.small_font, COLOR_WARNING if active else COLOR_TEXT)

        self._draw_text(f"Tool: {self._tool_label()}", (panel.x + 20, py(92)), self.font, COLOR_ACCENT)
        self._draw_number_input("grid_width", "W", self.state.grid_width, pygame.Rect(panel.x + 42, py(126), 58, 28))
        self._draw_number_input("grid_height", "H", self.state.grid_height, pygame.Rect(panel.x + 132, py(126), 58, 28))
        self._draw_number_input("initial_hp", "HP", self.state.initial_hp, pygame.Rect(panel.x + 42, py(180), 58, 28))
        self._draw_number_input("initial_sanity", "SAN", self.state.initial_sanity, pygame.Rect(panel.x + 132, py(180), 58, 28))
        self._draw_number_input("initial_battery", "BAT", self.state.initial_battery, pygame.Rect(panel.x + 222, py(180), 58, 28))
        self._draw_number_input("player_speed", "SPD", self._format_number(self.state.player_speed), pygame.Rect(panel.x + 42, py(234), 58, 28))

        object_y = 280
        self._draw_text("Object Asset", (panel.x + 20, py(object_y)), self.small_font, COLOR_MUTED)
        self.object_dropdown_rect = pygame.Rect(panel.x + 24, py(object_y + 22), PANEL_WIDTH - 48, 28)
        pygame.draw.rect(self.screen, (35, 43, 45), self.object_dropdown_rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if self.object_dropdown_open else COLOR_PANEL_EDGE, self.object_dropdown_rect, 1, border_radius=3)
        active_object_label = f"{self.active_object_symbol}  {self.state.object_label(self.active_object_symbol)}"
        self._draw_text_in_rect(active_object_label, self.object_dropdown_rect.inflate(-14, -4), self.small_font, COLOR_TEXT)
        arrow_x = self.object_dropdown_rect.right - 18
        arrow_y = self.object_dropdown_rect.centery
        pygame.draw.polygon(self.screen, COLOR_MUTED, [(arrow_x - 5, arrow_y - 3), (arrow_x + 5, arrow_y - 3), (arrow_x, arrow_y + 4)])

        option_y = object_y + 52
        if self.object_dropdown_open:
            for object_id, label in self._object_list_items():
                option_rect = pygame.Rect(panel.x + 24, py(option_y), PANEL_WIDTH - 48, 22)
                self.object_buttons[object_id] = option_rect
                active = object_id == self.active_object_symbol
                pygame.draw.rect(self.screen, (54, 64, 65) if active else (30, 36, 38), option_rect)
                pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, option_rect, 1)
                color = COLOR_ACCENT if active else COLOR_TEXT
                self._draw_text_in_rect(label, option_rect.inflate(-12, -2), self.small_font, color)
                option_y += 22

        snap_y = option_y + 8 if self.object_dropdown_open else object_y + 60
        self.auto_wall_snap_rect = pygame.Rect(panel.x + 24, py(snap_y), 18, 18)
        pygame.draw.rect(self.screen, (35, 43, 45), self.auto_wall_snap_rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if self.auto_wall_snap else COLOR_PANEL_EDGE, self.auto_wall_snap_rect, 1, border_radius=3)
        if self.auto_wall_snap:
            pygame.draw.line(self.screen, COLOR_ACCENT, (self.auto_wall_snap_rect.x + 4, self.auto_wall_snap_rect.centery), (self.auto_wall_snap_rect.x + 8, self.auto_wall_snap_rect.bottom - 4), 2)
            pygame.draw.line(self.screen, COLOR_ACCENT, (self.auto_wall_snap_rect.x + 8, self.auto_wall_snap_rect.bottom - 4), (self.auto_wall_snap_rect.right - 4, self.auto_wall_snap_rect.y + 4), 2)
        self._draw_text("Auto wall snap", (panel.x + 48, py(snap_y + 1)), self.small_font, COLOR_TEXT)

        selection_y = max(380, snap_y + 42)

        room = self.state.selected_room()
        if room is not None:
            self._draw_text("Selected room", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_input("name", room.name, pygame.Rect(panel.x + 24, py(selection_y + 28), PANEL_WIDTH - 48, 28))
            self._draw_input("number", room.number, pygame.Rect(panel.x + 24, py(selection_y + 92), PANEL_WIDTH - 48, 28))
            self._draw_number_input("room_x", "X", room.x, pygame.Rect(panel.x + 24, py(selection_y + 146), 58, 28))
            self._draw_number_input("room_y", "Y", room.y, pygame.Rect(panel.x + 112, py(selection_y + 146), 58, 28))
            self._draw_number_input("room_w", "W", room.w, pygame.Rect(panel.x + 24, py(selection_y + 200), 58, 28))
            self._draw_number_input("room_h", "H", room.h, pygame.Rect(panel.x + 112, py(selection_y + 200), 58, 28))
        elif self.state.selected_door is not None:
            cell = self.state.selected_door
            symbol = self.state.doors.get(cell, "?")
            orientation = self.state.door_orientation_at(cell)
            length = self.state.door_span_length(cell)
            self._draw_text("Selected door", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_text(f"Type: {symbol} {DOOR_SYMBOLS.get(symbol, ('Unknown',))[0]}", (panel.x + 24, py(selection_y + 32)), self.font, COLOR_ACCENT)
            self._draw_text(f"Cell: {cell[0]}, {cell[1]}", (panel.x + 24, py(selection_y + 62)), self.small_font, COLOR_MUTED)
            self._draw_text(f"Orientation: {orientation}", (panel.x + 24, py(selection_y + 92)), self.small_font, COLOR_MUTED)
            self._draw_number_input("door_length", "Len", length, pygame.Rect(panel.x + 24, py(selection_y + 124), 58, 28))
            self._draw_text("Delete removes the selected cell.", (panel.x + 24, py(selection_y + 174)), self.small_font, COLOR_MUTED)
        elif self.state.selected_object is not None:
            cell = self.state.selected_object
            placement = self.state.objects.get(cell)
            object_id = placement.object_id if placement is not None else "?"
            rotation = placement.rotation if placement is not None else 0
            self._draw_text("Selected object", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_text(f"{object_id}: {self.state.object_label(object_id)}", (panel.x + 24, py(selection_y + 32)), self.font, COLOR_ACCENT)
            self._draw_text(f"Rotation: {rotation} deg", (panel.x + 24, py(selection_y + 62)), self.small_font, COLOR_MUTED)
            if placement is not None:
                footprint_w, footprint_h = self.state.object_footprint_size(placement)
                self._draw_number_input("object_x", "X", cell[0], pygame.Rect(panel.x + 24, py(selection_y + 102), 58, 28))
                self._draw_number_input("object_y", "Y", cell[1], pygame.Rect(panel.x + 112, py(selection_y + 102), 58, 28))
                length, width, height, placement_height = self.state.object_dimensions(placement)
                self._draw_number_input("object_footprint_w", "Len", self._format_number(length), pygame.Rect(panel.x + 24, py(selection_y + 156), 58, 28))
                self._draw_number_input("object_footprint_d", "Wid", self._format_number(width), pygame.Rect(panel.x + 112, py(selection_y + 156), 58, 28))
                self._draw_number_input("object_height", "H", self._format_number(height), pygame.Rect(panel.x + 200, py(selection_y + 156), 58, 28))
                self._draw_number_input("object_z", "Z", self._format_number(placement_height), pygame.Rect(panel.x + 24, py(selection_y + 210), 58, 28))
                self._draw_text(f"Rotated footprint: {footprint_w} x {footprint_h}", (panel.x + 24, py(selection_y + 250)), self.small_font, COLOR_MUTED)
                self._draw_object_story_editor(panel, py, selection_y + 288, placement)
        elif self.selection_rect is not None:
            min_x, min_y, max_x, max_y = self.selection_rect
            count = self._selection_item_count(self.selection_items)
            self._draw_text("Selected area", (panel.x + 20, py(selection_y)), self.font, COLOR_TEXT)
            self._draw_text(f"Items: {count}", (panel.x + 24, py(selection_y + 32)), self.font, COLOR_ACCENT)
            self._draw_text(f"From: {min_x}, {min_y}", (panel.x + 24, py(selection_y + 62)), self.small_font, COLOR_MUTED)
            self._draw_text(f"To: {max_x}, {max_y}", (panel.x + 24, py(selection_y + 86)), self.small_font, COLOR_MUTED)
            self._draw_text("Drag inside box to move.", (panel.x + 24, py(selection_y + 120)), self.small_font, COLOR_MUTED)
        else:
            self._draw_text("No selection", (panel.x + 20, py(selection_y)), self.font, COLOR_MUTED)
            self._draw_text("Create or select a room to edit metadata.", (panel.x + 20, py(selection_y + 30)), self.small_font, COLOR_MUTED)

        content_bottom = selection_y + 880 if self.state.selected_object is not None else selection_y + 290
        self.panel_content_height = max(WINDOW_HEIGHT - STATUS_HEIGHT, content_bottom)
        self._clamp_side_scrolls()
        self.screen.set_clip(clip)
        self._draw_side_scrollbar(panel, self.panel_scroll_y, self.panel_content_height, self.drag_mode == "panel_v_scrollbar")
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, panel, 1)

    def _draw_object_story_editor(self, panel: pygame.Rect, py, y: int, placement: ObjectPlacement) -> None:
        is_pickup = placement.element_type == ELEMENT_PICKUP
        is_trigger = placement.is_trigger or placement.element_type == ELEMENT_TRIGGER
        title = "Pickup Element" if is_pickup else "Trigger Element" if is_trigger else "Story Element"
        self._draw_text(title, (panel.x + 20, py(y)), self.font, COLOR_TEXT)
        self._draw_checkbox("object_is_pickup", "Pickup", is_pickup, pygame.Rect(panel.x + 24, py(y + 34), 18, 18))
        self._draw_checkbox("object_is_trigger", "Trigger", is_trigger, pygame.Rect(panel.x + 126, py(y + 34), 18, 18))
        self._draw_checkbox("object_remove_on_pickup", "Remove", placement.remove_on_pickup, pygame.Rect(panel.x + 24, py(y + 62), 18, 18))
        self._draw_checkbox("object_trigger_once", "Once", placement.trigger_once, pygame.Rect(panel.x + 126, py(y + 62), 18, 18))

        field_y = y + 114
        self._draw_text_input("object_trigger_id", "Trigger ID", placement.trigger_id, pygame.Rect(panel.x + 24, py(field_y), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_resource_role", "Role", placement.resource_role, pygame.Rect(panel.x + 24, py(field_y + 62), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_pickup_item", "Item", placement.pickup_item, pygame.Rect(panel.x + 24, py(field_y + 124), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_pickup_flag", "Flag", placement.pickup_flag, pygame.Rect(panel.x + 24, py(field_y + 186), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_interaction_prompt", "Prompt", placement.interaction_prompt, pygame.Rect(panel.x + 24, py(field_y + 248), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_interaction_message", "Message", placement.interaction_message, pygame.Rect(panel.x + 24, py(field_y + 310), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_required_item", "Need Item", placement.required_item, pygame.Rect(panel.x + 24, py(field_y + 372), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_required_flag", "Need Flag", placement.required_flag, pygame.Rect(panel.x + 24, py(field_y + 434), PANEL_WIDTH - 48, 28))
        self._draw_text_input("object_failure_message", "Fail Msg", placement.failure_message, pygame.Rect(panel.x + 24, py(field_y + 496), PANEL_WIDTH - 48, 28))

        if is_pickup:
            self._draw_checkbox("object_random_drop", "Random drop", placement.random_drop, pygame.Rect(panel.x + 24, py(field_y + 548), 18, 18))
            self._draw_number_input("object_drop_count", "Count", placement.drop_count, pygame.Rect(panel.x + 156, py(field_y + 542), 58, 28))
            self._draw_text("Count is per same item on this floor.", (panel.x + 24, py(field_y + 582)), self.small_font, COLOR_MUTED)
        else:
            self._draw_text("Triggers run by Trigger ID; pickups grant Item or Flag.", (panel.x + 24, py(field_y + 548)), self.small_font, COLOR_MUTED)

    def _draw_checkbox(self, field: str, label: str, checked: bool, rect: pygame.Rect) -> None:
        self.panel_toggles[field] = rect
        pygame.draw.rect(self.screen, (35, 43, 45), rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if checked else COLOR_PANEL_EDGE, rect, 1, border_radius=3)
        if checked:
            pygame.draw.line(self.screen, COLOR_ACCENT, (rect.x + 4, rect.centery), (rect.x + 8, rect.bottom - 4), 2)
            pygame.draw.line(self.screen, COLOR_ACCENT, (rect.x + 8, rect.bottom - 4), (rect.right - 4, rect.y + 4), 2)
        self._draw_text(label, (rect.right + 8, rect.y + 1), self.small_font, COLOR_TEXT)

    def _draw_text_input(self, field: str, label: str, value: str, rect: pygame.Rect) -> None:
        self.panel_fields[field] = rect
        active = self.editing_field == field
        self._draw_text(label, (rect.x, rect.y - 18), self.small_font, COLOR_MUTED)
        pygame.draw.rect(self.screen, (35, 43, 45), rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=3)
        suffix = "|" if active else ""
        display = self.edit_buffer if active else value
        self._draw_text_in_rect(display + suffix, rect.inflate(-12, -4), self.small_font, COLOR_TEXT)

    def _draw_number_input(self, field: str, label: str, value: int | float | str, rect: pygame.Rect) -> None:
        self.panel_fields[field] = rect
        active = self.editing_field == field
        self._draw_text(label, (rect.x, rect.y - 18), self.small_font, COLOR_MUTED)
        pygame.draw.rect(self.screen, (35, 43, 45), rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=3)
        suffix = "|" if active else ""
        display = self.edit_buffer if active else str(value)
        self._draw_text_in_rect(display + suffix, rect.inflate(-12, -4), self.small_font, COLOR_TEXT)

    def _draw_input(self, field: str, value: str, rect: pygame.Rect) -> None:
        self.panel_fields[field] = rect
        label = "Name" if field == "name" else "Number"
        active = self.editing_field == field
        self._draw_text(label, (rect.x, rect.y - 20), self.small_font, COLOR_MUTED)
        pygame.draw.rect(self.screen, (35, 43, 45), rect, border_radius=3)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else COLOR_PANEL_EDGE, rect, 1, border_radius=3)
        suffix = "|" if active else ""
        display = self.edit_buffer if active else value
        self._draw_text_in_rect(display + suffix, rect.inflate(-14, -4), self.small_font, COLOR_TEXT)

    def _tool_label(self) -> str:
        if self.active_tool == "door":
            return f"Door {self.active_door_symbol}"
        if self.active_tool == "object":
            return f"Object {self.active_object_symbol} {self.active_object_rotation}deg"
        return self.active_tool.title()

    def _object_list_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for object_id, spec in sorted(self.state.object_specs.items()):
            if object_id not in LEGACY_OBJECT_IDS:
                items.append((object_id, object_id))
        items.extend((symbol, f"Legacy {symbol}: {label}") for symbol, label in OBJECT_LABELS.items())
        return items


