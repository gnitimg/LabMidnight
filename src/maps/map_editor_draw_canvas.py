from __future__ import annotations

import pygame

from src.maps.map_editor_config import *
from src.maps.map_editor_models import ObjectPlacement, Room


class MapEditorDrawCanvasMixin:
    def _draw(self) -> None:
        self.screen.fill(COLOR_BG)
        self._draw_toolbar()
        self._draw_canvas()
        self._draw_panel()
        self._draw_status()
        pygame.display.flip()

    def _draw_toolbar(self) -> None:
        toolbar = self.toolbar_rect
        self._clamp_side_scrolls()
        pygame.draw.rect(self.screen, COLOR_TOOLBAR, toolbar)
        clip = self.screen.get_clip()
        self.screen.set_clip(toolbar)
        self._draw_text("Map Editor", (16, 8 - self.toolbar_scroll_y), self.big_font, COLOR_TEXT)
        for rect, label, action, payload in self.buttons:
            draw_rect = rect.move(0, -self.toolbar_scroll_y)
            if not draw_rect.colliderect(toolbar):
                continue
            selected = action == self.active_tool
            if action == "door" and payload != self.active_door_symbol:
                selected = False
            color = (58, 68, 70) if selected else (38, 45, 48)
            pygame.draw.rect(self.screen, color, draw_rect, border_radius=4)
            pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, draw_rect, 1, border_radius=4)
            self._draw_text(label, (draw_rect.x + 8, draw_rect.y + 6), self.small_font, COLOR_TEXT)

        y = self.toolbar_help_y - self.toolbar_scroll_y
        for line in self._toolbar_help_lines():
            self._draw_text(line, (14, y), self.small_font, COLOR_MUTED)
            y += 20
        self.screen.set_clip(clip)
        self._draw_side_scrollbar(toolbar, self.toolbar_scroll_y, self.toolbar_content_height, self.drag_mode == "toolbar_v_scrollbar")
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, toolbar, 1)

    def _draw_canvas(self) -> None:
        canvas = self.canvas_rect
        viewport = self.viewport_rect
        self._clamp_scroll()
        pygame.draw.rect(self.screen, (14, 17, 18), canvas)
        clip = self.screen.get_clip()
        self.screen.set_clip(viewport)

        start_x = max(0, self.scroll_x // self.cell_size)
        start_y = max(0, self.scroll_y // self.cell_size)
        end_x = min(self.state.grid_width, start_x + viewport.width // self.cell_size + 3)
        end_y = min(self.state.grid_height, start_y + viewport.height // self.cell_size + 3)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                sx, sy = self._screen_from_cell(x, y)
                char = self.state.grid[y][x]
                rect = pygame.Rect(sx, sy, self.cell_size, self.cell_size)
                pygame.draw.rect(self.screen, self._cell_color(char), rect)
                pygame.draw.rect(self.screen, COLOR_GRID, rect, 1)
                if char in DOOR_SYMBOLS or char in {WINDOW_SYMBOL, "@"} or (char in "123456789" and (x, y) not in self.state.objects):
                    self._draw_centered_text(char, rect, self.small_font, COLOR_TEXT)

        self._draw_objects_overlay()
        for room in self.state.rooms:
            self._draw_room_overlay(room)
        self._draw_drag_preview()
        self._draw_door_preview()
        self._draw_area_selection()
        self.screen.set_clip(clip)
        self._draw_horizontal_scrollbar()
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, canvas, 1)

    def _draw_horizontal_scrollbar(self) -> None:
        track = self._horizontal_scrollbar_track_rect()
        pygame.draw.rect(self.screen, (19, 24, 26), track.inflate(8, 8), border_radius=4)
        pygame.draw.rect(self.screen, (45, 54, 56), track, border_radius=4)
        thumb = self._horizontal_scrollbar_thumb_rect()
        active = self.drag_mode == "h_scrollbar"
        thumb_color = COLOR_ACCENT if active else (111, 128, 130)
        pygame.draw.rect(self.screen, thumb_color, thumb, border_radius=4)
        pygame.draw.rect(self.screen, COLOR_PANEL_EDGE, track, 1, border_radius=4)

    def _cell_color(self, char: str) -> tuple[int, int, int]:
        if char == "#":
            return COLOR_WALL
        if char == WINDOW_SYMBOL:
            return (50, 90, 104)
        if char == "@":
            return COLOR_START
        if char in "123456789":
            return COLOR_OBJECT
        if char in DOOR_SYMBOLS:
            return DOOR_SYMBOLS[char][1]
        return COLOR_FLOOR

    def _draw_room_overlay(self, room: Room) -> None:
        sx, sy = self._screen_from_cell(room.x, room.y)
        rect = pygame.Rect(sx, sy, room.w * self.cell_size, room.h * self.cell_size)
        selected = room.room_id == self.state.selected_room_id
        color = COLOR_SELECTED if selected else (92, 104, 105)
        pygame.draw.rect(self.screen, color, rect, 2 if selected else 1)
        if selected:
            hx, hy = self._screen_from_cell(*room.handle_cell())
            handle_size = min(8, max(5, self.cell_size // 2))
            handle = pygame.Rect(
                hx + self.cell_size - handle_size,
                hy + self.cell_size - handle_size,
                handle_size,
                handle_size,
            )
            pygame.draw.rect(self.screen, COLOR_SELECTED, handle)

    def _draw_objects_overlay(self) -> None:
        for anchor, placement in self.state.objects.items():
            width, height = self.state.object_footprint_size(placement)
            sx, sy = self._screen_from_cell(*anchor)
            rect = pygame.Rect(sx, sy, width * self.cell_size, height * self.cell_size)
            selected = anchor == self.state.selected_object
            color = COLOR_SELECTED if selected else COLOR_OBJECT
            fill = self._object_fill_color(placement)
            for cell in self.state.object_footprint_cells(anchor, placement):
                if not self._cell_visible(cell):
                    continue
                cell_sx, cell_sy = self._screen_from_cell(*cell)
                cell_rect = pygame.Rect(cell_sx, cell_sy, self.cell_size, self.cell_size)
                pygame.draw.rect(self.screen, fill, cell_rect)
                pygame.draw.rect(self.screen, COLOR_GRID, cell_rect, 1)
            pygame.draw.rect(self.screen, color, rect, 2 if selected else 1)
            self._draw_centered_text(placement.label_char(), rect, self.small_font, COLOR_TEXT)
            self._draw_rotation_marker(rect, placement.rotation, color)
            if selected:
                self._draw_object_resize_handles(anchor, placement)

    def _object_fill_color(self, placement: ObjectPlacement) -> tuple[int, int, int]:
        if placement.is_trigger or placement.element_type == ELEMENT_TRIGGER:
            return (136, 92, 66)
        if placement.element_type == ELEMENT_PICKUP:
            return (82, 128, 86)
        if placement.object_id in LEGACY_OBJECT_IDS:
            return COLOR_OBJECT
        return (122, 104, 58)

    def _cell_visible(self, cell: tuple[int, int]) -> bool:
        sx, sy = self._screen_from_cell(*cell)
        return self.viewport_rect.colliderect(pygame.Rect(sx, sy, self.cell_size, self.cell_size))

    def _draw_object_resize_handles(self, anchor: tuple[int, int], placement: ObjectPlacement) -> None:
        for rect in self._object_resize_handle_rects(anchor, placement).values():
            if not self.viewport_rect.colliderect(rect):
                continue
            pygame.draw.rect(self.screen, COLOR_PANEL, rect)
            pygame.draw.rect(self.screen, COLOR_SELECTED, rect, 2)

    def _draw_rotation_marker(self, rect: pygame.Rect, rotation: int, color: tuple[int, int, int]) -> None:
        center = rect.center
        normalized = rotation % 360
        directions = {
            0: (0, -1),
            90: (1, 0),
            180: (0, 1),
            270: (-1, 0),
        }
        dx, dy = directions.get(normalized, (0, -1))
        end = (center[0] + dx * 7, center[1] + dy * 7)
        pygame.draw.line(self.screen, color, center, end, 2)

    def _draw_drag_preview(self) -> None:
        if self.drag_mode != "create_room" or self.drag_start_cell is None or self.drag_current_cell is None:
            return
        x1, y1 = self.drag_start_cell
        x2, y2 = self.drag_current_cell
        min_x, max_x = sorted((x1, x2))
        min_y, max_y = sorted((y1, y2))
        sx, sy = self._screen_from_cell(min_x, min_y)
        rect = pygame.Rect(sx, sy, (max_x - min_x + 1) * self.cell_size, (max_y - min_y + 1) * self.cell_size)
        pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 2)

    def _draw_door_preview(self) -> None:
        if self.active_tool != "door" or self.hover_cell is None:
            return
        target = self.state.nearest_wall_for_door(self.hover_cell)
        if target is None:
            return
        sx, sy = self._screen_from_cell(*target)
        rect = pygame.Rect(sx, sy, self.cell_size, self.cell_size)
        pygame.draw.rect(self.screen, COLOR_ACCENT, rect, 3)

    def _draw_area_selection(self) -> None:
        rect_cells: tuple[int, int, int, int] | None = None
        color = COLOR_SELECTED
        if self.drag_mode == "box_select" and self.drag_start_cell is not None and self.drag_current_cell is not None:
            rect_cells = self._normalized_cell_rect(self.drag_start_cell, self.drag_current_cell)
            color = COLOR_ACCENT
        elif self.selection_rect is not None:
            rect_cells = self.selection_rect
        if rect_cells is None:
            return
        min_x, min_y, max_x, max_y = rect_cells
        sx, sy = self._screen_from_cell(min_x, min_y)
        rect = pygame.Rect(sx, sy, (max_x - min_x + 1) * self.cell_size, (max_y - min_y + 1) * self.cell_size)
        pygame.draw.rect(self.screen, color, rect, 2)

    def _draw_status(self) -> None:
        y = WINDOW_HEIGHT - STATUS_HEIGHT
        pygame.draw.rect(self.screen, (10, 13, 14), (0, y, WINDOW_WIDTH, STATUS_HEIGHT))
        status = self.state.status or "Ready."
        color = COLOR_ERROR if status.startswith("Door must") or status.startswith("Room needs") else COLOR_MUTED
        self._draw_text(status, (14, y + 9), self.small_font, color)
        if self.hover_cell is not None:
            text = f"Cell {self.hover_cell[0]}, {self.hover_cell[1]}"
            surface = self.small_font.render(text, True, COLOR_MUTED)
            self.screen.blit(surface, (WINDOW_WIDTH - surface.get_width() - 18, y + 9))

    def _draw_text(self, text: str, pos: tuple[int, int], font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)

    def _draw_text_in_rect(self, text: str, rect: pygame.Rect, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        visible_text = self._fit_text_to_width(text, font, rect.width)
        surface = font.render(visible_text, True, color)
        pos = (rect.x, rect.y + (rect.height - surface.get_height()) // 2)
        old_clip = self.screen.get_clip()
        self.screen.set_clip(rect.clip(old_clip) if old_clip is not None else rect)
        self.screen.blit(surface, pos)
        self.screen.set_clip(old_clip)

    def _fit_text_to_width(self, text: str, font: pygame.font.Font, max_width: int) -> str:
        if max_width <= 0:
            return ""
        if font.size(text)[0] <= max_width:
            return text
        prefix = "..."
        trimmed = text
        while trimmed and font.size(prefix + trimmed)[0] > max_width:
            trimmed = trimmed[1:]
        if trimmed:
            return prefix + trimmed
        while prefix and font.size(prefix)[0] > max_width:
            prefix = prefix[:-1]
        return prefix

    def _draw_centered_text(self, text: str, rect: pygame.Rect, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))


def main() -> None:
    MapEditor().run()


if __name__ == "__main__":
    main()

