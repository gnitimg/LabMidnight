from __future__ import annotations

import math

import pygame

from src.settings import (
    MOUSE_PITCH_SENSITIVITY,
    MOUSE_SENSITIVITY,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STATE_FAILURE,
    STATE_FLOOR_CONFIRM,
    STATE_INVENTORY,
    STATE_MENU,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_SUCCESS,
)


class GameInputMixin:
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse(event.button, event.pos)
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
            elif key == pygame.K_F2:
                quality = self.renderer.cycle_quality()
                names = {"performance": "性能", "balanced": "平衡", "sharp": "清晰"}
                self.set_message(f"渲染质量：{names.get(quality, quality)}", 1.8)
            elif key == pygame.K_SPACE:
                self.set_message(self.interaction.interact(self), 4.0)
            return
        if self.state == STATE_FLOOR_CONFIRM:
            self._handle_floor_confirm_key(key)
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

    def _handle_floor_confirm_key(self, key: int) -> None:
        options = self.floor_transition_options
        if not options:
            self._clear_floor_transition()
            self.set_state(STATE_PLAYING)
            return
        if key in (pygame.K_LEFT, pygame.K_UP, pygame.K_a, pygame.K_w):
            self.floor_choice_selected = (self.floor_choice_selected - 1) % len(options)
        elif key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_d, pygame.K_s):
            self.floor_choice_selected = (self.floor_choice_selected + 1) % len(options)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            requested_floor = key - pygame.K_0
            if requested_floor in options:
                self.floor_choice_selected = options.index(requested_floor)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm_floor_choice()
        elif key == pygame.K_ESCAPE:
            self._clear_floor_transition()
            self.set_state(STATE_PLAYING)
            self.set_message("你停在原地。", 2.0)

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

    def _handle_mouse(self, button: int, pos: tuple[int, int]) -> None:
        if self.state == STATE_FLOOR_CONFIRM:
            if button == 1:
                for index, rect in enumerate(self._floor_confirm_button_rects()):
                    if rect.collidepoint(pos):
                        self.floor_choice_selected = index
                        self._confirm_floor_choice()
                        break
            return
        if self.state == STATE_PLAYING:
            if button == 1:
                if self.mosquito_system.handle_mouse_attack(self, pos):
                    return
                self.set_message(self.interaction.interact(self), 4.0)
            elif button == 3:
                self.toggle_flashlight()
        elif self.state == STATE_MENU and button == 1 and not self.show_instructions:
            self._confirm_menu()

    def _handle_mouse_motion(self, rel: tuple[int, int]) -> None:
        if self.state != STATE_PLAYING or self.mouse_captured:
            return
        self._apply_mouse_look(*rel)

    def _apply_mouse_look(self, dx: int, dy: int) -> None:
        if dx:
            self.player.angle = (self.player.angle + dx * MOUSE_SENSITIVITY) % math.tau
        if dy:
            self.player.look_vertical(-dy * MOUSE_PITCH_SENSITIVITY)

    def _update_mouse_look(self) -> None:
        if self.state != STATE_PLAYING or not self.mouse_captured:
            return
        try:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            center_x, center_y = self.mouse_center
            dx = mouse_x - center_x
            dy = mouse_y - center_y
            if dx or dy:
                self._apply_mouse_look(dx, dy)
                pygame.mouse.set_pos(self.mouse_center)
                pygame.mouse.get_rel()
                return
            rel_x, rel_y = pygame.mouse.get_rel()
            if rel_x or rel_y:
                self._apply_mouse_look(rel_x, rel_y)
        except pygame.error:
            pass

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

    def _floor_confirm_button_rects(self) -> list[pygame.Rect]:
        options = self.floor_transition_options
        panel = pygame.Rect(SCREEN_WIDTH // 2 - 240, SCREEN_HEIGHT // 2 - 116, 480, 232)
        if not options:
            return []
        button_width = 80 if len(options) >= 4 else 100 if len(options) == 3 else 118
        button_gap = 12 if len(options) >= 3 else 18
        total_width = button_width * len(options) + button_gap * (len(options) - 1)
        start_x = panel.centerx - total_width // 2
        y = panel.y + 128
        return [pygame.Rect(start_x + index * (button_width + button_gap), y, button_width, 42) for index in range(len(options))]

    def set_mouse_capture(self, enabled: bool) -> None:
        if self.mouse_captured == enabled:
            return
        self.mouse_captured = enabled
        try:
            pygame.event.set_grab(enabled)
            pygame.mouse.set_visible(not enabled)
            if enabled:
                pygame.mouse.set_pos(self.mouse_center)
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

