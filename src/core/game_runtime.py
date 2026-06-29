from __future__ import annotations

import math
import time

import pygame

from src.settings import (
    COLOR_BLACK,
    SANITY_DARK_DRAIN_PER_SEC,
    SANITY_LOW_AUDIO_THRESHOLD,
    STATE_FAILURE,
    STATE_FLOOR_CONFIRM,
    STATE_INVENTORY,
    STATE_MENU,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_SUCCESS,
    BUILDING_BOTTOM_FLOOR,
)


FLOOR_AMBIENT_DELAY_SECONDS = 5.0
FLOOR_AMBIENT_SOURCES = {
    1: {
        "sound": "laugh",
        "channel": "floor_1_laugh_source",
        "position": (65.0, 26.0),
        "max_distance": 90.0,
        "max_volume": 0.62,
    },
    2: {
        "sound": "cry",
        "channel": "floor_2_cry_source",
        "position": (58.0, 25.0),
        "max_distance": 90.0,
        "max_volume": 0.62,
    },
}


class GameRuntimeMixin:
    def update(self, dt: float) -> None:
        if self.state != STATE_PLAYING:
            return
        self._update_mouse_look()
        self._handle_continuous_input(dt)
        self.game_map.update_doors(dt)
        self._update_player_state(dt)
        if self.state != STATE_PLAYING:
            return
        self.mosquito_system.update(self, dt)
        if self.state != STATE_PLAYING:
            return
        self._update_story_triggers()
        self._update_floor_ambient_sources()

    def _handle_continuous_input(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        forward = 0.0
        strafe = 0.0
        if keys[pygame.K_w]:
            forward += 1.0
        if keys[pygame.K_s]:
            forward -= 1.0
        if keys[pygame.K_d]:
            strafe += 1.0
        if keys[pygame.K_a]:
            strafe -= 1.0
        self.player.move_vector(forward, strafe, dt, self.game_map)

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
        if self.current_floor == BUILDING_BOTTOM_FLOOR and self.game_map.reached_ground_exit(player.x, player.y):
            if not player.flags.get("checked_lobby_exit", False):
                player.flags["checked_lobby_exit"] = True
                self.set_message("门外挂着铁锁。门禁通过了，门没通过。", 3.0)
            return

        region = self.game_map.region_at(player.x, player.y)
        if region != "lab" and not player.flags.get("left_lab", False):
            player.flags["left_lab"] = True
            self.audio.play_loop("ambient_lab", volume=0.35)
        if region == "corridor" and player.flags.get("left_lab", False) and not player.flags.get("heard_lecture", False):
            player.flags["heard_lecture"] = True
            self.set_message("走廊也安静了。没有服务器声，只有我的脚步声。", 4.0)
        if region == "classroom" and not player.flags.get("entered_classroom", False):
            player.flags["entered_classroom"] = True
            player.sanity = max(0.0, player.sanity - 5.0)
            self.set_message("这里闷得像蒸笼。手电电量还在往下掉。", 4.0)
        if region == "exit" and self.is_floor_power_restored() and player.has_item("maintenance_pass"):
            self.audio.play("knock", volume=0.5, cooldown=5.0)

    def _update_floor_ambient_sources(self) -> None:
        for floor, source in FLOOR_AMBIENT_SOURCES.items():
            if self.current_floor != floor:
                self.audio.stop_channel(str(source["channel"]))
                continue
            if time.monotonic() - getattr(self, "floor_entered_at", self.started_at) < FLOOR_AMBIENT_DELAY_SECONDS:
                self.audio.stop_channel(str(source["channel"]))
                continue
            self._play_spatial_floor_source(source)

    def _play_spatial_floor_source(self, source: dict) -> None:
        source_x, source_y = source["position"]
        dx = float(source_x) - self.player.x
        dy = float(source_y) - self.player.y
        distance = math.hypot(dx, dy)
        max_distance = float(source["max_distance"])
        if distance >= max_distance:
            self.audio.stop_channel(str(source["channel"]))
            return

        distance_factor = max(0.0, min(1.0, 1.0 - distance / max_distance))
        volume = float(source["max_volume"]) * (0.18 + 0.82 * distance_factor)
        angle_to_source = math.atan2(dy, dx)
        relative = (angle_to_source - self.player.angle + math.pi) % math.tau - math.pi
        pan = math.sin(relative)
        left = volume * (1.0 - max(0.0, pan) * 0.78)
        right = volume * (1.0 + min(0.0, pan) * 0.78)
        if abs(relative) > math.pi * 0.65:
            left *= 0.62
            right *= 0.62
        self.audio.play_spatial_loop(str(source["sound"]), str(source["channel"]), left, right)

    def set_message(self, text: str, duration: float = 3.0) -> None:
        self.message = text
        self.message_until = time.monotonic() + duration

    def current_message(self) -> str:
        return self.message if time.monotonic() <= self.message_until else ""

    def enter_success(self) -> None:
        self.player.flags["success_ending"] = True
        self.audio.stop_all()
        self.ui.reset_ending_video(True)
        self.set_state(STATE_SUCCESS)

    def enter_failure(self) -> None:
        self.player.flags["failure_ending"] = True
        self.audio.stop_all()
        self.audio.play("sanity_low", volume=0.8, cooldown=0.0)
        self.ui.reset_ending_video(False)
        self.set_state(STATE_FAILURE)

    def draw(self) -> None:
        if self.state == STATE_MENU:
            self.ui.draw_menu(self.screen, self.menu_selected, self.show_instructions)
        elif self.state in (STATE_PLAYING, STATE_PAUSED, STATE_INVENTORY, STATE_FLOOR_CONFIRM):
            elapsed = time.monotonic() - self.started_at
            self.renderer.render(self.player, elapsed, dynamic_entities=self.mosquito_system.dynamic_entities())
            self.renderer.draw_dark_overlay(self.player, elapsed)
            self.renderer.draw_dynamic_entity_overlays()
            prompt = self.interaction.prompt_for(self.player) if self.state == STATE_PLAYING else ""
            self.ui.draw_hud(self.screen, self.player, self.current_message(), prompt, self.current_floor)
            if self.state == STATE_PAUSED:
                self.ui.draw_pause(self.screen)
            elif self.state == STATE_INVENTORY:
                self.ui.draw_inventory(self.screen, self.player)
            elif self.state == STATE_FLOOR_CONFIRM:
                self.ui.draw_floor_confirm(self.screen, self.floor_transition_title, self.floor_transition_options, self.floor_choice_selected)
        elif self.state == STATE_SUCCESS:
            self.ui.draw_ending(self.screen, True)
        elif self.state == STATE_FAILURE:
            self.ui.draw_ending(self.screen, False)
        else:
            self.screen.fill(COLOR_BLACK)
        pygame.display.flip()
