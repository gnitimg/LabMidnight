"""Developer map editor for LabMidnight.

The editor writes the same text layout consumed by GameMap. Room labels are
stored in a sidecar JSON file because the runtime map format is intentionally
kept compact and character based.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pygame

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.maps.map_editor_config import *
from src.maps.map_editor_draw_canvas import MapEditorDrawCanvasMixin
from src.maps.map_editor_draw_panel import MapEditorDrawPanelMixin
from src.maps.map_editor_editing import MapEditorEditingMixin
from src.maps.map_editor_events import MapEditorEventMixin
from src.maps.map_editor_history import MapEditorHistoryMixin
from src.maps.map_editor_selection import MapEditorSelectionMixin
from src.maps.map_editor_state import MapEditorState
from src.maps.map_editor_viewport import MapEditorViewportMixin


class MapEditor(
    MapEditorHistoryMixin,
    MapEditorEditingMixin,
    MapEditorEventMixin,
    MapEditorSelectionMixin,
    MapEditorViewportMixin,
    MapEditorDrawCanvasMixin,
    MapEditorDrawPanelMixin,
):
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("LabMidnight Map Editor")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 19)
        self.big_font = pygame.font.Font(None, 30)
        self.state = MapEditorState.load(TOP_FLOOR)
        self.running = True
        self.active_tool = "select"
        self.active_door_symbol = "L"
        self.active_object_symbol = "1"
        self.active_object_rotation = 0
        self.auto_wall_snap = False
        if self.state.object_specs:
            self.active_object_symbol = next(iter(sorted(self.state.object_specs)))
        self.buttons: list[tuple[pygame.Rect, str, str, str | None]] = []
        self.object_buttons: dict[str, pygame.Rect] = {}
        self.object_dropdown_open = False
        self.object_dropdown_rect = pygame.Rect(0, 0, 0, 0)
        self.auto_wall_snap_rect = pygame.Rect(0, 0, 0, 0)
        self.editing_field: str | None = None
        self.edit_buffer = ""
        self.drag_mode: str | None = None
        self.drag_history_pushed = False
        self.drag_start_cell: tuple[int, int] | None = None
        self.drag_current_cell: tuple[int, int] | None = None
        self.drag_initial_room: tuple[int, int, int, int] | None = None
        self.drag_initial_object: tuple[tuple[int, int], ObjectPlacement, str] | None = None
        self.selection_rect: tuple[int, int, int, int] | None = None
        self.selection_items = self._empty_selection_items()
        self.selection_move_snapshot: dict[str, object] | None = None
        self.clipboard: dict[str, object] | None = None
        self.paste_anchor_cell: tuple[int, int] | None = None
        self.hover_cell: tuple[int, int] | None = None
        self.panel_fields: dict[str, pygame.Rect] = {}
        self.panel_toggles: dict[str, pygame.Rect] = {}
        self.floor_buttons: dict[int, pygame.Rect] = {}
        self.scrollbar_drag_offset = 0
        self.side_scrollbar_drag_offset = 0
        self.cell_size = CELL_SIZE
        self.scroll_x = 0
        self.scroll_y = 0
        self.toolbar_scroll_y = 0
        self.panel_scroll_y = 0
        self.toolbar_help_y = 0
        self.toolbar_content_height = 0
        self.panel_content_height = WINDOW_HEIGHT - STATUS_HEIGHT
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []
        self._build_buttons()

    def run(self) -> None:
        while self.running:
            self._handle_events()
            self._draw()
            self.clock.tick(60)
        pygame.quit()

    def _build_buttons(self) -> None:
        self.buttons.clear()
        y = 18
        self._add_button("Select", "select", None, y)
        y += 36
        self._add_button("Room", "room", None, y)
        y += 36
        self._add_button("Wall", "wall", None, y)
        y += 36
        self._add_button("Window W", "window", None, y)
        y += 36
        self._add_button("Erase", "erase", None, y)
        y += 36
        self._add_button("Start", "start", None, y)
        y += 36
        self._add_button("Object", "object", None, y)
        y += 36
        self._add_button("Rotate CCW", "command", "rotate_ccw", y)
        y += 36
        self._add_button("Rotate CW", "command", "rotate_cw", y)
        y += 50
        for symbol, (name, _) in DOOR_SYMBOLS.items():
            self._add_button(f"Door {symbol} {name}", "door", symbol, y)
            y += 32
        y += 18
        self._add_button("Save Ctrl+S", "command", "save", y)
        y += 36
        self._add_button("Reload Ctrl+L", "command", "load", y)
        y += 36
        self._add_button("Clear Map", "command", "clear", y)
        y += 42
        self.toolbar_help_y = y
        self.toolbar_content_height = self.toolbar_help_y + len(self._toolbar_help_lines()) * 20 + 18

    def _add_button(self, label: str, action: str, payload: str | None, y: int) -> None:
        self.buttons.append((pygame.Rect(14, y, TOOLBAR_WIDTH - 28, 28), label, action, payload))

    def _toolbar_help_lines(self) -> list[str]:
        return [
            "Drag Room from toolbar or canvas.",
            "Drag bottom-right handle to resize.",
            "Doors snap to valid wall cells.",
            "Window W paints a wall-height window.",
            "Ctrl+drag box-selects items.",
            "Bottom bar scrolls left/right.",
            "Middle/right drag pans the grid.",
            "Mouse wheel zooms the canvas.",
            "Keys: Ctrl+S save, Del delete.",
            "Undo: Ctrl+Z / Ctrl+Shift+Z.",
            "Objects: click list or press 1-9.",
            "Rotate object: Q/E or buttons.",
            "Map scale is in Properties.",
        ]


def main() -> None:
    MapEditor().run()


if __name__ == "__main__":
    main()
