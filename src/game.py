"""Main game orchestration."""

from __future__ import annotations

import math
import time

import pygame

from .audio_manager import AudioManager
from .interaction import InteractionSystem
from .map_data import GameMap
from .player import Player
from .renderer import RaycastingRenderer
from .settings import (
    COLOR_BLACK,
    FPS,
    MOUSE_SENSITIVITY,
    SANITY_DARK_DRAIN_PER_SEC,
    SANITY_LOW_AUDIO_THRESHOLD,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATE_FAILURE,
    STATE_INVENTORY,
    STATE_MENU,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_SUCCESS,
    TITLE,
)
from .ui import UI


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.ui = UI()
        self.audio = AudioManager()
        self.running = True
        self.mouse_captured = False
        self.state = STATE_MENU
        self.menu_selected = 0
        self.show_instructions = False
        self.started_at = time.monotonic()
        self.message = ""
        self.message_until = 0.0
        self.low_sanity_warned = False
        self.new_game()
        self.set_mouse_capture(False)

    def new_game(self) -> None:
        self.game_map = GameMap()
        self.player = Player()
        self.renderer = RaycastingRenderer(self.screen, self.game_map)
        self.interaction = InteractionSystem(self.game_map)
        self.started_at = time.monotonic()
        self.message = "我怎么睡着了……已经两点了，得回寝室了。"
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

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse(event.button)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event.rel)

    def _handle_keydown(self, key: int) -> None:
        if self.state == STATE_MENU:
            self._handle_menu_key(key)
            return
        if self.state == STATE_PLAYING:
            if key == pygame.K_ESCAPE:
                self.set_state(STATE_PAUSED)
            elif key in (pygame.K_b, pygame.K_i):
                self.set_state(STATE_INVENTORY)
            elif key == pygame.K_SPACE:
                self.set_message(self.interaction.interact(self), 4.0)
            return
        if self.state == STATE_PAUSED:
            if key == pygame.K_ESCAPE:
                self.set_state(STATE_PLAYING)
            elif key == pygame.K_r:
                self.audio.stop_all()
                self.new_game()
                self.set_state(STATE_PLAYING)
            elif key == pygame.K_q:
                self.audio.stop_all()
                self.set_state(STATE_MENU)
            return
        if self.state == STATE_INVENTORY:
            if key in (pygame.K_ESCAPE, pygame.K_b, pygame.K_i):
                self.set_state(STATE_PLAYING)
            return
        if self.state in (STATE_SUCCESS, STATE_FAILURE):
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.audio.stop_all()
                self.set_state(STATE_MENU)
            elif key == pygame.K_r:
                self.audio.stop_all()
                self.new_game()
                self.set_state(STATE_PLAYING)
            elif key == pygame.K_ESCAPE:
                self.audio.stop_all()
                self.set_state(STATE_MENU)

    def _handle_menu_key(self, key: int) -> None:
        if self.show_instructions:
            if key == pygame.K_ESCAPE:
                self.show_instructions = False
            return
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_selected = (self.menu_selected - 1) % 3
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_selected = (self.menu_selected + 1) % 3
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm_menu()
        elif key == pygame.K_ESCAPE:
            self.running = False

    def _handle_mouse(self, button: int) -> None:
        if self.state == STATE_PLAYING:
            if button == 1:
                self.set_message(self.interaction.interact(self), 4.0)
            elif button == 3:
                self.toggle_flashlight()
        elif self.state == STATE_MENU and button == 1 and not self.show_instructions:
            self._confirm_menu()

    def _handle_mouse_motion(self, rel: tuple[int, int]) -> None:
        if self.state != STATE_PLAYING:
            return
        dx, _dy = rel
        if dx:
            self.player.angle = (self.player.angle + dx * MOUSE_SENSITIVITY) % math.tau

    def _confirm_menu(self) -> None:
        if self.menu_selected == 0:
            self.audio.stop_all()
            self.new_game()
            self.set_state(STATE_PLAYING)
        elif self.menu_selected == 1:
            self.show_instructions = True
        else:
            self.running = False

    def set_state(self, state: str) -> None:
        self.state = state
        self.set_mouse_capture(state == STATE_PLAYING)

    def set_mouse_capture(self, enabled: bool) -> None:
        if self.mouse_captured == enabled:
            return
        self.mouse_captured = enabled
        try:
            pygame.event.set_grab(enabled)
            pygame.mouse.set_visible(not enabled)
            pygame.mouse.get_rel()
        except pygame.error:
            pass

    def toggle_flashlight(self) -> None:
        if not self.player.has_item("flashlight"):
            self.set_message("我还没有手电。", 2.0)
            self.audio.play("error")
            return
        if self.player.flashlight_power <= 0:
            self.set_message("手电电量不足。", 2.0)
            self.audio.play("error")
            return
        self.player.flashlight_on = not self.player.flashlight_on
        state = "打开" if self.player.flashlight_on else "关闭"
        self.set_message(f"手电已{state}。", 1.6)

    def update(self, dt: float) -> None:
        if self.state != STATE_PLAYING:
            return
        self._handle_continuous_input(dt)
        self._update_player_state(dt)
        self._update_story_triggers()

    def _handle_continuous_input(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            self.player.rotate(-1.0, dt)
        if keys[pygame.K_d]:
            self.player.rotate(1.0, dt)
        if keys[pygame.K_w]:
            self.player.move(1.0, dt, self.game_map)
        if keys[pygame.K_s]:
            self.player.move(-1.0, dt, self.game_map)

    def _update_player_state(self, dt: float) -> None:
        player = self.player
        if player.flashlight_on and player.has_item("flashlight"):
            player.flashlight_power = max(0.0, player.flashlight_power - 2.2 * dt)
            if player.flashlight_power <= 0:
                player.flashlight_on = False
                self.set_message("手电熄灭了。", 2.2)

        in_dark = (not player.flashlight_on or player.flashlight_power <= 0) and not player.flags.get("power_restored", False)
        if in_dark:
            player.sanity = max(0.0, player.sanity - SANITY_DARK_DRAIN_PER_SEC * dt)
        if player.flashlight_power < 15 and player.has_item("flashlight"):
            player.sanity = max(0.0, player.sanity - 0.25 * dt)

        if player.sanity <= 0:
            self.enter_failure()
            return
        if player.sanity < SANITY_LOW_AUDIO_THRESHOLD and not self.low_sanity_warned:
            self.low_sanity_warned = True
            self.audio.play("sanity_low", volume=0.65, cooldown=3.0)
            self.set_message("不要回答点名。声音越来越近。", 3.5)

    def _update_story_triggers(self) -> None:
        player = self.player
        region = self.game_map.region_at(player.x, player.y)
        if region != "lab" and not player.flags.get("left_lab", False):
            player.flags["left_lab"] = True
            self.audio.play_loop("ambient_lab", volume=0.35)
        if region == "corridor" and player.flags.get("left_lab", False) and not player.flags.get("heard_lecture", False):
            player.flags["heard_lecture"] = True
            self.audio.play_loop("lecture_loop", volume=0.35)
            self.set_message("远处有老师讲课的声音。这个时间怎么会有课？", 4.0)
        if region == "classroom" and not player.flags.get("entered_classroom", False):
            player.flags["entered_classroom"] = True
            player.sanity = max(0.0, player.sanity - 5.0)
            self.audio.play_loop("lecture_loop", volume=0.58)
            self.set_message("教室里没有人，但讲课声确实在这里。", 4.0)
        if region == "exit" and player.flags.get("power_restored", False) and player.has_item("access_card"):
            self.audio.play("knock", volume=0.5, cooldown=5.0)

    def set_message(self, text: str, duration: float = 3.0) -> None:
        self.message = text
        self.message_until = time.monotonic() + duration

    def current_message(self) -> str:
        return self.message if time.monotonic() <= self.message_until else ""

    def enter_success(self) -> None:
        self.player.flags["success_ending"] = True
        self.audio.stop_all()
        self.set_state(STATE_SUCCESS)

    def enter_failure(self) -> None:
        self.player.flags["failure_ending"] = True
        self.audio.stop_all()
        self.audio.play("sanity_low", volume=0.8, cooldown=0.0)
        self.set_state(STATE_FAILURE)

    def draw(self) -> None:
        if self.state == STATE_MENU:
            self.ui.draw_menu(self.screen, self.menu_selected, self.show_instructions)
        elif self.state in (STATE_PLAYING, STATE_PAUSED, STATE_INVENTORY):
            elapsed = time.monotonic() - self.started_at
            self.renderer.render(self.player, elapsed)
            self.renderer.draw_dark_overlay(self.player)
            prompt = self.interaction.prompt_for(self.player) if self.state == STATE_PLAYING else ""
            self.ui.draw_hud(self.screen, self.player, self.current_message(), prompt)
            if self.state == STATE_PAUSED:
                self.ui.draw_pause(self.screen)
            elif self.state == STATE_INVENTORY:
                self.ui.draw_inventory(self.screen, self.player)
        elif self.state == STATE_SUCCESS:
            self.ui.draw_ending(self.screen, True)
        elif self.state == STATE_FAILURE:
            self.ui.draw_ending(self.screen, False)
        else:
            self.screen.fill(COLOR_BLACK)
        pygame.display.flip()
