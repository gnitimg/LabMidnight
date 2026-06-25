"""Player state and movement."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from src.settings import (
    FLASHLIGHT_MAX,
    FLASHLIGHT_START,
    PLAYER_ROTATION_SPEED,
    PLAYER_SPEED,
    SANITY_MAX,
)


def default_flags() -> dict[str, bool]:
    return {
        "intro_seen": False,
        "got_flashlight": False,
        "got_lab_key": False,
        "left_lab": False,
        "heard_lecture": False,
        "entered_classroom": False,
        "got_blackboard_clue": False,
        "got_note_a": False,
        "got_note_b": False,
        "got_fuse": False,
        "power_restored": False,
        "got_access_card": False,
        "exit_opened": False,
        "success_ending": False,
        "failure_ending": False,
    }


@dataclass
class Player:
    x: float = 3.0
    y: float = 3.0
    angle: float = 0.0
    pitch_offset: float = 0.0
    hp: int = 100
    sanity: float = SANITY_MAX
    flashlight_power: float = FLASHLIGHT_START
    flashlight_on: bool = False
    speed: float = PLAYER_SPEED
    rotation_speed: float = PLAYER_ROTATION_SPEED
    inventory: set[str] = field(default_factory=set)
    flags: dict[str, bool] = field(default_factory=default_flags)

    def rotate(self, direction: float, dt: float) -> None:
        self.angle = (self.angle + direction * self.rotation_speed * dt) % (math.tau)

    def look_vertical(self, delta: float) -> None:
        self.pitch_offset += delta

    def move(self, direction: float, dt: float, game_map) -> None:
        self.move_vector(direction, 0.0, dt, game_map)

    def move_vector(self, forward: float, strafe: float, dt: float, game_map) -> None:
        length = math.hypot(forward, strafe)
        if length <= 0:
            return

        forward /= length
        strafe /= length
        distance = self.speed * dt
        dx = (math.cos(self.angle) * forward - math.sin(self.angle) * strafe) * distance
        dy = (math.sin(self.angle) * forward + math.cos(self.angle) * strafe) * distance

        next_x = self.x + dx
        if game_map.can_move_to(next_x, self.y):
            self.x = next_x

        next_y = self.y + dy
        if game_map.can_move_to(self.x, next_y):
            self.y = next_y

    def add_item(self, item_id: str) -> None:
        self.inventory.add(item_id)
        if item_id == "flashlight":
            self.flags["got_flashlight"] = True
        elif item_id == "lab_key":
            self.flags["got_lab_key"] = True
        elif item_id == "note_a":
            self.flags["got_note_a"] = True
            self.flags["got_blackboard_clue"] = True
        elif item_id == "note_b":
            self.flags["got_note_b"] = True
        elif item_id == "fuse":
            self.flags["got_fuse"] = True
        elif item_id == "access_card":
            self.flags["got_access_card"] = True

    def has_item(self, item_id: str) -> bool:
        return item_id in self.inventory

    def restore_flashlight(self, amount: float) -> None:
        self.flashlight_power = min(FLASHLIGHT_MAX, self.flashlight_power + amount)
