from __future__ import annotations

import pygame

from src.maps.map_editor_config import *
from src.maps.map_editor_state import MapEditorState


class MapEditorEventMixin:
    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_up(event)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)
            elif event.type == pygame.MOUSEWHEEL:
                self._handle_mouse_wheel(event)

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        mods = pygame.key.get_mods()
        if event.key == pygame.K_z and mods & pygame.KMOD_CTRL:
            if self.editing_field is not None:
                self._cancel_editing_field()
            if mods & pygame.KMOD_SHIFT:
                self._redo()
            else:
                self._undo()
            return

        if self.editing_field is not None:
            if event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
                self._commit_editing_field()
                self.state.save()
                return
            if event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
                self._cancel_editing_field()
                self.state = MapEditorState.load(self.state.floor)
                return
            self._edit_text(event)
            return

        if event.key == pygame.K_c and mods & pygame.KMOD_CTRL:
            self._copy_selection()
            return
        if event.key == pygame.K_v and mods & pygame.KMOD_CTRL:
            self._paste_clipboard()
            return

        if event.key == pygame.K_ESCAPE:
            self.state.selected_room_id = None
            self.state.selected_door = None
            self.state.selected_object = None
            self._clear_area_selection()
            self.drag_mode = None
            self._cancel_editing_field()
        elif event.key == pygame.K_DELETE:
            self._push_history()
            if self.selection_rect is not None:
                self._delete_area_selection()
            else:
                self.state.delete_selection()
        elif event.key == pygame.K_s and mods & pygame.KMOD_CTRL:
            self.state.save()
        elif event.key == pygame.K_l and mods & pygame.KMOD_CTRL:
            self.state = MapEditorState.load(self.state.floor)
            self._clear_area_selection()
            self.undo_stack.clear()
            self.redo_stack.clear()
        elif event.key == pygame.K_q:
            self._push_history()
            self._rotate_active_object(-90)
        elif event.key == pygame.K_e:
            self._push_history()
            self._rotate_active_object(90)
        elif event.unicode in "123456789":
            self.active_object_symbol = event.unicode
            if self.active_tool == "object":
                self.state.status = f"Object tool uses symbol {self.active_object_symbol}."

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        if event.button == 4:
            if self.viewport_rect.collidepoint(event.pos):
                self._zoom_view_at(event.pos, 1)
                return
            self._scroll_area_at(event.pos, -SIDE_SCROLL_STEP)
            return
        if event.button == 5:
            if self.viewport_rect.collidepoint(event.pos):
                self._zoom_view_at(event.pos, -1)
                return
            self._scroll_area_at(event.pos, SIDE_SCROLL_STEP)
            return
        if event.button != 1:
            return

        pos = event.pos
        if self.editing_field is not None and not self.panel_rect.collidepoint(pos):
            self._commit_editing_field()
        if self._handle_side_scrollbar_down(pos):
            return
        button = self._button_at(pos)
        if button is not None:
            _, _, action, payload = button
            self._activate_button(action, payload)
            if action != "command":
                self.drag_mode = "toolbar"
            return

        if self._handle_panel_click(pos):
            return
        if self._handle_horizontal_scrollbar_down(pos):
            return

        cell = self._cell_from_pos(pos)
        if cell is None:
            return
        self.paste_anchor_cell = cell

        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            self.active_tool = "select"
            self._begin_box_selection(cell)
        elif self.active_tool == "select" and self._begin_object_resize_at(pos):
            self._push_drag_history()
            return
        elif self.active_tool == "select" and self._begin_area_move(cell):
            self._push_drag_history()
            return
        elif self.active_tool == "select":
            self._begin_select_drag(cell)
            if self.drag_mode in {"move_room", "resize_room"}:
                self._push_drag_history()
        elif self.active_tool == "room":
            self._clear_area_selection()
            self.drag_mode = "create_room"
            self.drag_start_cell = cell
            self.drag_current_cell = cell
        elif self.active_tool == "door":
            self._clear_area_selection()
            self.drag_mode = "place_door"
            self.drag_current_cell = cell
        else:
            self._clear_area_selection()
            self.drag_mode = "paint"
            self._push_drag_history()
            self._paint_cell(cell)

    def _handle_mouse_wheel(self, event: pygame.event.Event) -> None:
        pos = pygame.mouse.get_pos()
        if self.viewport_rect.collidepoint(pos):
            self._zoom_view_at(pos, event.y)
            return
        self._scroll_area_at(pos, -event.y * SIDE_SCROLL_STEP)

    def _zoom_view_at(self, pos: tuple[int, int], wheel_delta: int) -> None:
        if wheel_delta == 0:
            return
        old_size = self.cell_size
        factor = VIEW_ZOOM_STEP if wheel_delta > 0 else 1.0 / VIEW_ZOOM_STEP
        new_size = int(round(old_size * factor))
        new_size = max(MIN_VIEW_CELL_SIZE, min(MAX_VIEW_CELL_SIZE, new_size))
        if new_size == old_size:
            return

        viewport = self.viewport_rect
        world_x = (pos[0] - viewport.x + self.scroll_x) / old_size
        world_y = (pos[1] - viewport.y + self.scroll_y) / old_size
        self.cell_size = new_size
        self.scroll_x = int(round(world_x * new_size - (pos[0] - viewport.x)))
        self.scroll_y = int(round(world_y * new_size - (pos[1] - viewport.y)))
        self._clamp_scroll()
        self.state.status = f"Canvas zoom: {self.cell_size}px per cell."

    def _scroll_area_at(self, pos: tuple[int, int], amount: int) -> None:
        if self.toolbar_rect.collidepoint(pos):
            self.toolbar_scroll_y += amount
            self._clamp_side_scrolls()
            return
        if self.panel_rect.collidepoint(pos):
            self.panel_scroll_y += amount
            self._clamp_side_scrolls()
            return
        self.scroll_y += amount
        self._clamp_scroll()

    def _button_at(self, pos: tuple[int, int]) -> tuple[pygame.Rect, str, str, str | None] | None:
        if not self.toolbar_rect.collidepoint(pos):
            return None
        content_pos = (pos[0], pos[1] + self.toolbar_scroll_y)
        for button in self.buttons:
            if button[0].collidepoint(content_pos):
                return button
        return None

    def _activate_button(self, action: str, payload: str | None) -> None:
        if action == "command":
            self._commit_editing_field()
            if payload == "save":
                self.state.save()
            elif payload == "load":
                self.state = MapEditorState.load(self.state.floor)
                self._clear_area_selection()
                self.undo_stack.clear()
                self.redo_stack.clear()
            elif payload == "clear":
                self._push_history()
                self._clear_area_selection()
                self.drag_mode = None
                self.state.clear_map()
                self.active_tool = "select"
            elif payload == "rotate_ccw":
                self._push_history()
                self._rotate_active_object(-90)
            elif payload == "rotate_cw":
                self._push_history()
                self._rotate_active_object(90)
            return
        self.active_tool = action
        if action == "door" and payload is not None:
            self.active_door_symbol = payload
        self.state.status = f"Tool: {self._tool_label()}."

    def _handle_panel_click(self, pos: tuple[int, int]) -> bool:
        if not self.panel_rect.collidepoint(pos):
            return False
        for floor, rect in self.floor_buttons.items():
            if rect.collidepoint(pos):
                self._commit_editing_field()
                self._switch_floor(floor)
                return True
        if self.object_dropdown_rect.collidepoint(pos):
            self._commit_editing_field()
            self.object_dropdown_open = not self.object_dropdown_open
            return True
        if self.object_dropdown_open:
            for object_id, rect in self.object_buttons.items():
                if rect.collidepoint(pos):
                    self._commit_editing_field()
                    if self.state.selected_object is not None:
                        self._push_history()
                        self.state.update_selected_object_asset(object_id)
                    self.active_tool = "object"
                    self.active_object_symbol = object_id
                    self.object_dropdown_open = False
                    self.state.status = f"Object tool uses {self.state.object_label(object_id)}."
                    return True
            self.object_dropdown_open = False
        if self.auto_wall_snap_rect.collidepoint(pos):
            self._commit_editing_field()
            self.auto_wall_snap = not self.auto_wall_snap
            state = "on" if self.auto_wall_snap else "off"
            self.state.status = f"Auto wall snap {state}."
            return True
        for field, rect in self.panel_toggles.items():
            if rect.collidepoint(pos):
                self._commit_editing_field()
                self._toggle_object_field(field)
                return True
        for field, rect in self.panel_fields.items():
            if rect.collidepoint(pos):
                self._begin_editing_field(field)
                return True
        self._commit_editing_field()
        return True

    def _toggle_object_field(self, field: str) -> None:
        if self.state.selected_object is None:
            return
        placement = self.state.objects.get(self.state.selected_object)
        if placement is None:
            return
        before = self._state_snapshot()
        if field == "object_is_pickup":
            next_type = ELEMENT_STORY if placement.element_type == ELEMENT_PICKUP else ELEMENT_PICKUP
            updates = {"element_type": next_type}
            if next_type == ELEMENT_STORY:
                updates["random_drop"] = False
            self.state.update_selected_object_binding(**updates)
        elif field == "object_random_drop":
            self.state.update_selected_object_binding(random_drop=not placement.random_drop, element_type=ELEMENT_PICKUP)
        elif field == "object_remove_on_pickup":
            self.state.update_selected_object_binding(remove_on_pickup=not placement.remove_on_pickup)
        elif field == "object_is_trigger":
            is_trigger = not placement.is_trigger
            element_type = ELEMENT_TRIGGER if is_trigger else ELEMENT_STORY
            self.state.update_selected_object_binding(is_trigger=is_trigger, element_type=element_type)
        elif field == "object_trigger_once":
            self.state.update_selected_object_binding(trigger_once=not placement.trigger_once)
        if self._state_snapshot() != before:
            self.undo_stack.append(before)
            if len(self.undo_stack) > HISTORY_LIMIT:
                self.undo_stack.pop(0)
            self.redo_stack.clear()

    def _switch_floor(self, floor: int) -> None:
        self._commit_editing_field()
        floor = max(BOTTOM_FLOOR, min(TOP_FLOOR, floor))
        if floor == self.state.floor:
            return
        self.state.save()
        self.state = MapEditorState.load(floor)
        self._cancel_editing_field()
        self.drag_mode = None
        self.scroll_x = 0
        self.scroll_y = 0
        self.undo_stack.clear()
        self.redo_stack.clear()

    def _handle_side_scrollbar_down(self, pos: tuple[int, int]) -> bool:
        if self._max_toolbar_scroll_y() > 0 and self._side_scrollbar_track_rect(self.toolbar_rect).collidepoint(pos):
            thumb = self._side_scrollbar_thumb_rect(self.toolbar_rect, self.toolbar_scroll_y, self.toolbar_content_height)
            if thumb.collidepoint(pos):
                self.side_scrollbar_drag_offset = pos[1] - thumb.y
            else:
                self.side_scrollbar_drag_offset = thumb.height // 2
                self._set_toolbar_scroll_from_thumb(pos[1] - self.side_scrollbar_drag_offset)
            self.drag_mode = "toolbar_v_scrollbar"
            return True
        if self._max_panel_scroll_y() > 0 and self._side_scrollbar_track_rect(self.panel_rect).collidepoint(pos):
            thumb = self._side_scrollbar_thumb_rect(self.panel_rect, self.panel_scroll_y, self.panel_content_height)
            if thumb.collidepoint(pos):
                self.side_scrollbar_drag_offset = pos[1] - thumb.y
            else:
                self.side_scrollbar_drag_offset = thumb.height // 2
                self._set_panel_scroll_from_thumb(pos[1] - self.side_scrollbar_drag_offset)
            self.drag_mode = "panel_v_scrollbar"
            return True
        return False

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button != 1:
            return
        if self.drag_mode == "box_select" and self.drag_start_cell and self.drag_current_cell:
            self._finish_box_selection()
        elif self.drag_mode == "move_selection":
            self._finish_area_move()
        elif self.drag_mode == "create_room" and self.drag_start_cell and self.drag_current_cell:
            self._push_drag_history()
            self.state.add_room(*self.drag_start_cell, *self.drag_current_cell)
        elif self.drag_mode == "place_door" and self.drag_current_cell:
            self._push_drag_history()
            self.state.place_door(self.drag_current_cell, self.active_door_symbol)
        elif self.drag_mode == "toolbar":
            cell = self._cell_from_pos(event.pos)
            if cell is not None and self.active_tool == "door":
                self._push_drag_history()
                self.state.place_door(cell, self.active_door_symbol)
            elif cell is not None and self.active_tool == "room":
                self._push_drag_history()
                self.state.add_room(cell[0], cell[1], cell[0] + MIN_ROOM_SIZE - 1, cell[1] + MIN_ROOM_SIZE - 1)
            elif cell is not None and self.active_tool == "object":
                self._push_drag_history()
                self._place_active_object(cell)
        self.drag_mode = None
        self.drag_history_pushed = False
        self.drag_start_cell = None
        self.drag_current_cell = None
        self.drag_initial_room = None
        self.drag_initial_object = None
        self.selection_move_snapshot = None

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        self.hover_cell = self._cell_from_pos(event.pos)
        if self.drag_mode == "toolbar_v_scrollbar":
            self._set_toolbar_scroll_from_thumb(event.pos[1] - self.side_scrollbar_drag_offset)
            return
        if self.drag_mode == "panel_v_scrollbar":
            self._set_panel_scroll_from_thumb(event.pos[1] - self.side_scrollbar_drag_offset)
            return
        if self.drag_mode == "h_scrollbar":
            self._set_scroll_x_from_thumb(event.pos[0] - self.scrollbar_drag_offset)
            return
        if event.buttons[1] or event.buttons[2]:
            self.scroll_x = max(0, self.scroll_x - event.rel[0])
            self.scroll_y = max(0, self.scroll_y - event.rel[1])
            self._clamp_scroll()
            return
        if not event.buttons[0]:
            return

        cell = self._cell_from_pos(event.pos)
        if cell is None:
            return
        if self.drag_mode == "box_select":
            self.drag_current_cell = cell
            return
        if self.drag_mode == "move_selection":
            self.drag_current_cell = cell
            self._move_area_selection(cell)
            return
        if self.drag_mode == "resize_object":
            self.drag_current_cell = cell
            self._resize_selected_object_from_corner(cell)
            return
        if self.drag_mode == "toolbar":
            if self.active_tool == "room":
                self.drag_mode = "create_room"
                self.drag_start_cell = cell
                self.drag_current_cell = cell
            elif self.active_tool == "door":
                self.drag_mode = "place_door"
                self.drag_current_cell = cell
            elif self.active_tool == "object":
                self._push_drag_history()
                self._place_active_object(cell)
            return
        self.drag_current_cell = cell
        if self.drag_mode == "move_room":
            self._move_selected_room(cell)
        elif self.drag_mode == "resize_room":
            self._resize_selected_room(cell)
        elif self.active_tool in {"wall", "window", "erase", "start", "object"}:
            self._paint_cell(cell)

