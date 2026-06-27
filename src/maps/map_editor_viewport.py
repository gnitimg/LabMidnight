from __future__ import annotations

import pygame

from src.maps.map_editor_config import *


class MapEditorViewportMixin:
    @property
    def toolbar_rect(self) -> pygame.Rect:
        return pygame.Rect(0, 0, TOOLBAR_WIDTH, WINDOW_HEIGHT - STATUS_HEIGHT)

    @property
    def canvas_rect(self) -> pygame.Rect:
        return pygame.Rect(TOOLBAR_WIDTH, 0, WINDOW_WIDTH - TOOLBAR_WIDTH - PANEL_WIDTH, WINDOW_HEIGHT - STATUS_HEIGHT)

    @property
    def viewport_rect(self) -> pygame.Rect:
        canvas = self.canvas_rect
        return pygame.Rect(canvas.x, canvas.y, canvas.width, max(0, canvas.height - H_SCROLLBAR_HEIGHT))

    @property
    def panel_rect(self) -> pygame.Rect:
        return pygame.Rect(WINDOW_WIDTH - PANEL_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT - STATUS_HEIGHT)

    def _handle_horizontal_scrollbar_down(self, pos: tuple[int, int]) -> bool:
        track = self._horizontal_scrollbar_track_rect()
        if not track.collidepoint(pos) or self._max_scroll_x() <= 0:
            return False
        thumb = self._horizontal_scrollbar_thumb_rect()
        if thumb.collidepoint(pos):
            self.scrollbar_drag_offset = pos[0] - thumb.x
        else:
            self.scrollbar_drag_offset = thumb.width // 2
            self._set_scroll_x_from_thumb(pos[0] - self.scrollbar_drag_offset)
        self.drag_mode = "h_scrollbar"
        return True

    def _horizontal_scrollbar_track_rect(self) -> pygame.Rect:
        canvas = self.canvas_rect
        return pygame.Rect(canvas.x + 8, canvas.bottom - H_SCROLLBAR_HEIGHT + 4, canvas.width - 16, H_SCROLLBAR_HEIGHT - 8)

    def _horizontal_scrollbar_thumb_rect(self) -> pygame.Rect:
        track = self._horizontal_scrollbar_track_rect()
        content_width = max(1, self.state.grid_width * self.cell_size)
        visible_width = max(1, self.viewport_rect.width)
        if content_width <= visible_width:
            return track.copy()
        thumb_width = max(H_SCROLLBAR_MIN_THUMB_WIDTH, int(track.width * visible_width / content_width))
        thumb_width = min(track.width, thumb_width)
        travel = max(1, track.width - thumb_width)
        thumb_x = track.x + int((self.scroll_x / self._max_scroll_x()) * travel)
        return pygame.Rect(thumb_x, track.y, thumb_width, track.height)

    def _set_scroll_x_from_thumb(self, thumb_left: int) -> None:
        max_scroll = self._max_scroll_x()
        if max_scroll <= 0:
            self.scroll_x = 0
            return
        track = self._horizontal_scrollbar_track_rect()
        thumb = self._horizontal_scrollbar_thumb_rect()
        travel = max(1, track.width - thumb.width)
        clamped_left = max(track.x, min(track.x + travel, thumb_left))
        self.scroll_x = int(round((clamped_left - track.x) / travel * max_scroll))
        self._clamp_scroll()

    def _side_scrollbar_track_rect(self, area: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(area.right - V_SCROLLBAR_WIDTH + 2, area.y + 8, V_SCROLLBAR_WIDTH - 4, max(1, area.height - 16))

    def _side_scrollbar_thumb_rect(self, area: pygame.Rect, scroll_y: int, content_height: int) -> pygame.Rect:
        track = self._side_scrollbar_track_rect(area)
        if content_height <= area.height:
            return track.copy()
        thumb_height = max(V_SCROLLBAR_MIN_THUMB_HEIGHT, int(track.height * area.height / max(1, content_height)))
        thumb_height = min(track.height, thumb_height)
        travel = max(1, track.height - thumb_height)
        max_scroll = max(1, content_height - area.height)
        thumb_y = track.y + int((scroll_y / max_scroll) * travel)
        return pygame.Rect(track.x, thumb_y, track.width, thumb_height)

    def _set_toolbar_scroll_from_thumb(self, thumb_top: int) -> None:
        self.toolbar_scroll_y = self._scroll_from_side_thumb(self.toolbar_rect, self.toolbar_content_height, thumb_top)
        self._clamp_side_scrolls()

    def _set_panel_scroll_from_thumb(self, thumb_top: int) -> None:
        self.panel_scroll_y = self._scroll_from_side_thumb(self.panel_rect, self.panel_content_height, thumb_top)
        self._clamp_side_scrolls()

    def _scroll_from_side_thumb(self, area: pygame.Rect, content_height: int, thumb_top: int) -> int:
        max_scroll = max(0, content_height - area.height)
        if max_scroll <= 0:
            return 0
        track = self._side_scrollbar_track_rect(area)
        thumb = self._side_scrollbar_thumb_rect(area, 0, content_height)
        travel = max(1, track.height - thumb.height)
        clamped_top = max(track.y, min(track.y + travel, thumb_top))
        return int(round((clamped_top - track.y) / travel * max_scroll))

    def _draw_side_scrollbar(self, area: pygame.Rect, scroll_y: int, content_height: int, active: bool) -> None:
        if content_height <= area.height:
            return
        track = self._side_scrollbar_track_rect(area)
        pygame.draw.rect(self.screen, (35, 43, 45), track, border_radius=3)
        thumb = self._side_scrollbar_thumb_rect(area, scroll_y, content_height)
        pygame.draw.rect(self.screen, COLOR_ACCENT if active else (102, 119, 121), thumb, border_radius=3)

    def _max_scroll_x(self) -> int:
        return max(0, self.state.grid_width * self.cell_size - self.viewport_rect.width)

    def _max_scroll_y(self) -> int:
        return max(0, self.state.grid_height * self.cell_size - self.viewport_rect.height)

    def _max_toolbar_scroll_y(self) -> int:
        return max(0, self.toolbar_content_height - self.toolbar_rect.height)

    def _max_panel_scroll_y(self) -> int:
        return max(0, self.panel_content_height - self.panel_rect.height)

    def _clamp_scroll(self) -> None:
        self.scroll_x = max(0, min(self.scroll_x, self._max_scroll_x()))
        self.scroll_y = max(0, min(self.scroll_y, self._max_scroll_y()))

    def _clamp_side_scrolls(self) -> None:
        self.toolbar_scroll_y = max(0, min(self.toolbar_scroll_y, self._max_toolbar_scroll_y()))
        self.panel_scroll_y = max(0, min(self.panel_scroll_y, self._max_panel_scroll_y()))

    def _cell_from_pos(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        viewport = self.viewport_rect
        if not viewport.collidepoint(pos):
            return None
        x = (pos[0] - viewport.x + self.scroll_x) // self.cell_size
        y = (pos[1] - viewport.y + self.scroll_y) // self.cell_size
        if x < 0 or y < 0:
            return None
        if x >= self.state.grid_width or y >= self.state.grid_height:
            return None
        return int(x), int(y)

    def _screen_from_cell(self, x: int, y: int) -> tuple[int, int]:
        viewport = self.viewport_rect
        return viewport.x + x * self.cell_size - self.scroll_x, viewport.y + y * self.cell_size - self.scroll_y

