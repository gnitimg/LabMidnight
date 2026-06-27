"""Main game orchestration."""

from __future__ import annotations

import math
import time

import pygame

from src.core.player import Player
from src.maps.map_data import load_initial_player_config
from src.core.game_floors import GameFloorMixin
from src.core.game_input import GameInputMixin
from src.core.game_runtime import GameRuntimeMixin
from src.settings import (
    BUILDING_BOTTOM_FLOOR,
    BUILDING_TOP_FLOOR,
    COLOR_BLACK,
    FPS,
    MOUSE_PITCH_SENSITIVITY,
    MOUSE_SENSITIVITY,
    SANITY_DARK_DRAIN_PER_SEC,
    SANITY_LOW_AUDIO_THRESHOLD,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATE_FAILURE,
    STATE_FLOOR_CONFIRM,
    STATE_INVENTORY,
    STATE_MENU,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_SUCCESS,
    TITLE,
)
from src.systems.audio_manager import AudioManager
from src.ui.ui import UI


class Game(GameInputMixin, GameFloorMixin, GameRuntimeMixin):
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.ui = UI()
        self.audio = AudioManager()
        self.running = True
        self.mouse_captured = False
        self.mouse_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.state = STATE_MENU
        self.menu_selected = 0
        self.show_instructions = False
        self.started_at = time.monotonic()
        self.message = ""
        self.message_until = 0.0
        self.low_sanity_warned = False
        self.current_floor = BUILDING_TOP_FLOOR
        self.pending_floor = BUILDING_TOP_FLOOR - 1
        self.floor_choice_selected = 0
        self.floor_transition_options: list[int] = []
        self.floor_transition_title = "楼层选择"
        self.floor_transition_entry_kind = ""
        self.floor_transition_source_cell: tuple[int, int] | None = None
        self.floor_picked_objects: dict[int, set[tuple[int, int]]] = {}
        self.new_game()
        self.set_mouse_capture(False)

    def new_game(self) -> None:
        self.current_floor = BUILDING_TOP_FLOOR
        self.floor_picked_objects = {}
        self._load_current_floor_map()
        start_x, start_y = self.game_map.start_position
        self._clear_floor_transition()
        initial = load_initial_player_config()
        self.player = Player(
            x=start_x,
            y=start_y,
            hp=int(initial["hp"]),
            sanity=initial["sanity"],
            flashlight_power=initial["flashlight_power"],
            speed=initial["speed"],
        )
        self._bind_floor_systems()
        self.started_at = time.monotonic()
        self.message = "凌晨两点，空调停了。断电了，我得出去。"
        self.message_until = time.monotonic() + 5.0
        self.low_sanity_warned = False

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        self.set_mouse_capture(False)
        self.audio.stop_all()
        pygame.quit()
