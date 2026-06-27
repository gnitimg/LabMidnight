"""Dynamic mosquito disturbance entities for the raycasting game."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import math
import random
import time

import pygame

from src.settings import STATE_PLAYING


MOSQUITO_HP = 150
MOSQUITO_MAX_ACTIVE = 10
MOSQUITO_MAX_PER_FLOOR = 6
MOSQUITO_SPAWN_INTERVAL_MIN = 8.0
MOSQUITO_SPAWN_INTERVAL_MAX = 15.0
MOSQUITO_BASE_SPEED = 1.65
MOSQUITO_ATTACK_RANGE = 1.30
MOSQUITO_ATTACK_SAN_DAMAGE = 18
MOSQUITO_ATTACK_COOLDOWN = 1.6
MOSQUITO_HIT_RADIUS_SCREEN = 36
MOSQUITO_VISIBLE_DISTANCE = 16.0
MOSQUITO_AUDIO_DISTANCE = 12.0
MOSQUITO_CHASE_DISTANCE = 8.0
MOSQUITO_TARGET_LOST_DISTANCE = 50.0
MOSQUITO_BURST_SPEED_MULTIPLIER = 2.20
MOSQUITO_ORBIT_RANGE = 2.25
MOSQUITO_BITE_INTENT_RANGE = 5.5
MOSQUITO_LUNGE_SPEED_MULTIPLIER = 3.00


class MosquitoState(Enum):
    IDLE = "idle"
    WANDER = "wander"
    CHASE = "chase"
    ATTACK = "attack"
    DEAD = "dead"


@dataclass
class Mosquito:
    mosquito_id: int
    x: float
    y: float
    hp: float = float(MOSQUITO_HP)
    state: MosquitoState = MosquitoState.WANDER
    speed: float = MOSQUITO_BASE_SPEED
    attack_cooldown: float = 0.0
    age: float = 0.0
    wander_angle: float = 0.0
    wander_timer: float = 0.0
    screen_rect: pygame.Rect | None = None
    visible: bool = False
    distance_to_player: float = 999.0
    angle_to_player: float = 0.0
    last_hit_flash: float = 0.0
    route_path: list[tuple[int, int]] = field(default_factory=list)
    route_refresh: float = 0.0
    trail: list[tuple[float, float, float]] = field(default_factory=list)
    trail_sample_timer: float = 0.0
    burst_timer: float = 0.0
    burst_cooldown: float = 0.0
    orbit_direction: int = 1
    agility: float = 1.0


class MosquitoSystem:
    def __init__(self, game_map, audio_manager) -> None:
        self.game_map = game_map
        self.audio = audio_manager
        self.current_floor = getattr(game_map, "floor", 4)
        self.mosquitoes: list[Mosquito] = []
        self.spawned_per_floor: dict[int, int] = {}
        self.lurking_points_by_floor: dict[int, list[tuple[float, float]]] = {}
        self._next_id = 1
        self._spawn_timer = self._first_spawn_delay()

    def reset_for_floor(self, game_map, current_floor: int) -> None:
        self.game_map = game_map
        self.current_floor = current_floor
        self.mosquitoes.clear()
        self._spawn_timer = self._first_spawn_delay()
        self.audio.stop_channel("mosquito_buzz_main")

    def _first_spawn_delay(self) -> float:
        return random.uniform(2.0, 4.0)

    def update(self, game, dt: float) -> None:
        self.game_map = game.game_map
        self.current_floor = game.current_floor
        self._ensure_lurking_points_for_floor(game)
        dt = max(0.0, min(dt, 0.12))
        self._update_spawn(game, dt)

        for mosquito in list(self.mosquitoes):
            self._update_mosquito(game, mosquito, dt)
            if game.state != STATE_PLAYING:
                self.audio.stop_channel("mosquito_buzz_main")
                return

        self.mosquitoes = [mosquito for mosquito in self.mosquitoes if mosquito.hp > 0 and mosquito.state is not MosquitoState.DEAD]
        self.update_spatial_audio(game)

    def handle_mouse_attack(self, game, mouse_pos: tuple[int, int]) -> bool:
        candidates = [
            mosquito
            for mosquito in self.mosquitoes
            if mosquito.hp > 0 and mosquito.visible and mosquito.screen_rect is not None and mosquito.screen_rect.collidepoint(mouse_pos)
        ]
        if not candidates:
            return False

        mosquito = min(candidates, key=lambda item: item.distance_to_player)
        # Mosquito attack damage is intentionally equal to the player's current SAN.
        # The click does not consume SAN; low SAN simply makes each hit weaker.
        damage = int(game.player.sanity)
        mosquito.hp -= damage
        mosquito.last_hit_flash = time.monotonic()
        game.audio.play("mosquito_hit", volume=0.75, cooldown=0.08)

        if mosquito.hp <= 0:
            mosquito.hp = 0
            mosquito.state = MosquitoState.DEAD
            mosquito.visible = False
            mosquito.screen_rect = None
            if mosquito in self.mosquitoes:
                self.mosquitoes.remove(mosquito)
            game.audio.play("mosquito_die", volume=0.7, cooldown=0.08)
            if not self.mosquitoes:
                game.audio.stop_channel("mosquito_buzz_main")
            game.set_message("蚊子掉了下去，耳边终于安静了一点。", 3.2)
            return True

        game.set_message(f"你拍中了蚊子，造成 {damage} 点伤害。", 2.2)
        return True

    def dynamic_entities(self) -> list[dict]:
        return [
            {
                "kind": "mosquito",
                "ref": mosquito,
                "x": mosquito.x,
                "y": mosquito.y,
                "height": 0.7,
                "size": 0.38,
                "hp": mosquito.hp,
                "max_hp": MOSQUITO_HP,
                "hit_flash": mosquito.last_hit_flash,
                "trail": mosquito.trail,
            }
            for mosquito in self.mosquitoes
            if mosquito.hp > 0 and mosquito.state is not MosquitoState.DEAD
        ]

    def update_spatial_audio(self, game) -> None:
        living = [mosquito for mosquito in self.mosquitoes if mosquito.hp > 0 and mosquito.state is not MosquitoState.DEAD]
        if not living:
            game.audio.stop_channel("mosquito_buzz_main")
            return

        source = max(
            living,
            key=lambda mosquito: (1.0 / max(mosquito.distance_to_player, 0.1)) + (0.35 if mosquito.visible else 0.0),
        )
        distance = max(0.0, source.distance_to_player)
        distance_factor = _clamp(1.0 - distance / MOSQUITO_AUDIO_DISTANCE, 0.0, 1.0)
        base_volume = 0.08 + 0.72 * (distance_factor**1.4)

        angle_to_mosquito = math.atan2(source.y - game.player.y, source.x - game.player.x)
        relative = _normalize_angle(angle_to_mosquito - game.player.angle)
        pan = math.sin(relative)
        left = base_volume * (1.0 - max(0.0, pan) * 0.75)
        right = base_volume * (1.0 + min(0.0, pan) * 0.75)
        if abs(relative) > math.pi * 0.65:
            left *= 0.55
            right *= 0.55

        game.audio.play_spatial_loop(
            "mosquito_buzz",
            "mosquito_buzz_main",
            _clamp(left, 0.0, 0.9),
            _clamp(right, 0.0, 0.9),
        )

    def _update_spawn(self, game, dt: float) -> None:
        self._spawn_timer -= dt
        if self._spawn_timer > 0:
            return
        self._spawn_timer = random.uniform(MOSQUITO_SPAWN_INTERVAL_MIN, MOSQUITO_SPAWN_INTERVAL_MAX)

        if len(self.mosquitoes) >= MOSQUITO_MAX_ACTIVE:
            return
        if self.spawned_per_floor.get(self.current_floor, 0) >= MOSQUITO_MAX_PER_FLOOR:
            return
        first_spawn_for_floor = self.spawned_per_floor.get(self.current_floor, 0) <= 0
        if not first_spawn_for_floor and random.random() > self._spawn_probability(game):
            return
        self._spawn_near_player(game)

    def _ensure_lurking_points_for_floor(self, game) -> None:
        if self.current_floor in self.lurking_points_by_floor:
            return

        target_count = max(1, min(MOSQUITO_MAX_PER_FLOOR, 6))
        candidates: list[tuple[float, float]] = []
        for cell_y in range(1, self.game_map.height - 1):
            for cell_x in range(1, self.game_map.width - 1):
                x = cell_x + 0.5
                y = cell_y + 0.5
                if not self.game_map.can_move_to(x, y):
                    continue
                if math.hypot(x - game.player.x, y - game.player.y) < 4.0:
                    continue
                candidates.append((x, y))

        random.shuffle(candidates)
        selected: list[tuple[float, float]] = []
        for point in candidates:
            if all(math.hypot(point[0] - other[0], point[1] - other[1]) >= 2.5 for other in selected):
                selected.append(point)
                if len(selected) >= target_count:
                    break

        if len(selected) < target_count:
            for point in candidates:
                if point not in selected:
                    selected.append(point)
                    if len(selected) >= target_count:
                        break

        self.lurking_points_by_floor[self.current_floor] = selected

    def _spawn_probability(self, game) -> float:
        floor_base = {4: 0.35, 3: 0.55, 2: 0.75, 1: 0.32}
        probability = floor_base.get(self.current_floor, 0.45)
        if game.player.flags.get("power_restored", False):
            probability *= 0.65
        else:
            probability *= 1.25
        if not game.player.flashlight_on or game.player.flashlight_power <= 0:
            probability *= 1.15
        if game.player.sanity < 55:
            probability *= 1.0 + (55.0 - game.player.sanity) / 110.0
        return _clamp(probability, 0.12, 0.90)

    def _spawn_near_player(self, game) -> None:
        if self._spawn_from_lurking_point(game):
            return

        player = game.player
        player_cell = (int(player.x), int(player.y))
        for _attempt in range(32):
            angle = random.uniform(0.0, math.tau)
            distance = random.uniform(4.0, 9.0)
            x = player.x + math.cos(angle) * distance
            y = player.y + math.sin(angle) * distance
            if math.hypot(x - player.x, y - player.y) < 2.0:
                continue
            if not self._find_path((int(x), int(y)), player_cell):
                continue
            if self._activate_mosquito_at(x, y):
                return

        for _attempt in range(24):
            angle = random.uniform(0.0, math.tau)
            distance = random.uniform(2.6, 5.2)
            x = player.x + math.cos(angle) * distance
            y = player.y + math.sin(angle) * distance
            if not self._find_path((int(x), int(y)), player_cell):
                continue
            if self._activate_mosquito_at(x, y):
                return

    def _spawn_from_lurking_point(self, game) -> bool:
        self._ensure_lurking_points_for_floor(game)
        points = list(self.lurking_points_by_floor.get(self.current_floor, []))
        if not points:
            return False

        random.shuffle(points)
        preferred = []
        fallback = []
        player_cell = (int(game.player.x), int(game.player.y))
        for x, y in points:
            distance = math.hypot(x - game.player.x, y - game.player.y)
            if distance < 2.0 or distance > MOSQUITO_TARGET_LOST_DISTANCE:
                continue
            if not self._find_path((int(x), int(y)), player_cell):
                continue
            if 3.2 <= distance <= 7.0:
                preferred.append((x, y))
            else:
                fallback.append((x, y))

        for base_x, base_y in preferred + fallback:
            for _attempt in range(6):
                x = base_x + random.uniform(-0.35, 0.35)
                y = base_y + random.uniform(-0.35, 0.35)
                if math.hypot(x - game.player.x, y - game.player.y) < 2.0:
                    continue
                if self._activate_mosquito_at(x, y):
                    return True
        return False

    def _activate_mosquito_at(self, x: float, y: float) -> bool:
        if not self.game_map.can_move_to(x, y):
            return False
        for mosquito in self.mosquitoes:
            if math.hypot(mosquito.x - x, mosquito.y - y) < 0.85:
                return False

        mosquito = Mosquito(
            mosquito_id=self._next_id,
            x=x,
            y=y,
            speed=random.uniform(MOSQUITO_BASE_SPEED * 0.88, MOSQUITO_BASE_SPEED * 1.12),
            wander_angle=random.uniform(0.0, math.tau),
            wander_timer=random.uniform(0.6, 1.6),
            orbit_direction=random.choice((-1, 1)),
            agility=random.uniform(0.85, 1.25),
        )
        mosquito.trail.append((mosquito.x, mosquito.y, mosquito.age))
        self._next_id += 1
        self.mosquitoes.append(mosquito)
        self.spawned_per_floor[self.current_floor] = self.spawned_per_floor.get(self.current_floor, 0) + 1
        return True

    def _update_mosquito(self, game, mosquito: Mosquito, dt: float) -> None:
        if mosquito.hp <= 0:
            mosquito.state = MosquitoState.DEAD
            return

        mosquito.age += dt
        mosquito.attack_cooldown = max(0.0, mosquito.attack_cooldown - dt)
        mosquito.route_refresh = max(0.0, mosquito.route_refresh - dt)
        mosquito.trail_sample_timer = max(0.0, mosquito.trail_sample_timer - dt)
        mosquito.burst_timer = max(0.0, mosquito.burst_timer - dt)
        mosquito.burst_cooldown = max(0.0, mosquito.burst_cooldown - dt)
        self._refresh_player_metrics(game, mosquito)

        distance = mosquito.distance_to_player
        if distance > MOSQUITO_TARGET_LOST_DISTANCE:
            mosquito.state = MosquitoState.WANDER
        elif distance <= MOSQUITO_ATTACK_RANGE:
            mosquito.state = MosquitoState.ATTACK
        elif distance <= MOSQUITO_TARGET_LOST_DISTANCE:
            mosquito.state = MosquitoState.CHASE
        else:
            mosquito.state = MosquitoState.WANDER

        if mosquito.state is MosquitoState.ATTACK:
            self._attack_player_if_ready(game, mosquito)
            if mosquito.attack_cooldown > 0:
                self._move_chase(game, mosquito, dt * 0.35)
        elif mosquito.state is MosquitoState.CHASE:
            if not self._move_chase(game, mosquito, dt):
                mosquito.state = MosquitoState.WANDER
                self._move_wander(mosquito, dt)
        elif mosquito.state is MosquitoState.WANDER:
            self._move_wander(mosquito, dt)

        self._sample_trail(mosquito)
        self._refresh_player_metrics(game, mosquito)

    def _refresh_player_metrics(self, game, mosquito: Mosquito) -> None:
        dx = game.player.x - mosquito.x
        dy = game.player.y - mosquito.y
        mosquito.distance_to_player = math.hypot(dx, dy)
        mosquito.angle_to_player = math.atan2(dy, dx)

    def _move_wander(self, mosquito: Mosquito, dt: float) -> None:
        mosquito.wander_timer -= dt
        if mosquito.wander_timer <= 0:
            mosquito.wander_angle = random.uniform(0.0, math.tau)
            mosquito.wander_timer = random.uniform(0.55, 1.35)
            if mosquito.burst_cooldown <= 0 and random.random() < 0.35:
                self._start_burst(mosquito)
        flutter = math.sin(mosquito.age * 10.0 + mosquito.mosquito_id) * 0.55
        move_angle = mosquito.wander_angle + flutter
        distance = mosquito.speed * mosquito.agility * 0.55 * self._burst_multiplier(mosquito) * dt
        if not self._try_move(mosquito, move_angle, distance):
            mosquito.wander_angle = random.uniform(0.0, math.tau)
            mosquito.wander_timer = random.uniform(0.3, 0.8)

    def _move_chase(self, game, mosquito: Mosquito, dt: float) -> bool:
        target = self._route_target(game, mosquito)
        if target is None:
            return False

        target_x, target_y = target
        base_angle = math.atan2(target_y - mosquito.y, target_x - mosquito.x)
        direct_bite_angle = math.atan2(game.player.y - mosquito.y, game.player.x - mosquito.x)
        if mosquito.distance_to_player <= MOSQUITO_BITE_INTENT_RANGE:
            if mosquito.burst_cooldown <= 0 and mosquito.distance_to_player > MOSQUITO_ATTACK_RANGE:
                self._start_burst(mosquito)
            lunge_jitter = math.sin(mosquito.age * 18.0 + mosquito.mosquito_id) * 0.16
            lunge_distance = (
                mosquito.speed
                * mosquito.agility
                * MOSQUITO_LUNGE_SPEED_MULTIPLIER
                * self._burst_multiplier(mosquito)
                * dt
            )
            if self._try_move(mosquito, direct_bite_angle + lunge_jitter, lunge_distance):
                return True
            if self._try_move(mosquito, direct_bite_angle, lunge_distance * 0.85):
                return True

        if mosquito.burst_cooldown <= 0 and mosquito.distance_to_player > MOSQUITO_ATTACK_RANGE * 1.2:
            self._start_burst(mosquito)

        wiggle = (
            math.sin(mosquito.age * 13.0 + mosquito.mosquito_id) * 0.28
            + math.sin(mosquito.age * 5.7 + mosquito.mosquito_id * 1.9) * 0.22
        )
        orbit_blend = _clamp((MOSQUITO_ORBIT_RANGE - mosquito.distance_to_player) / MOSQUITO_ORBIT_RANGE, 0.0, 1.0)
        bite_commit = _clamp((MOSQUITO_BITE_INTENT_RANGE - mosquito.distance_to_player) / MOSQUITO_BITE_INTENT_RANGE, 0.0, 1.0)
        lateral = (
            math.sin(mosquito.age * 11.0 + mosquito.mosquito_id) * 0.55
            + mosquito.orbit_direction * orbit_blend * 0.95
        ) * (1.0 - bite_commit * 0.78)
        forward_weight = 1.0 + max(0.0, mosquito.distance_to_player - MOSQUITO_ORBIT_RANGE) * 0.06
        forward_weight += bite_commit * 1.35
        direction_x = math.cos(base_angle) * forward_weight + math.cos(base_angle + math.pi / 2) * lateral
        direction_y = math.sin(base_angle) * forward_weight + math.sin(base_angle + math.pi / 2) * lateral
        move_angle = math.atan2(direction_y, direction_x) + wiggle
        distance = mosquito.speed * mosquito.agility * self._chase_speed_multiplier(mosquito) * self._burst_multiplier(mosquito) * dt
        if self._try_move(mosquito, move_angle, distance):
            return True
        if self._try_move(mosquito, base_angle, distance * 0.75):
            return True

        mosquito.route_path = []
        mosquito.route_refresh = 0.0
        mosquito.wander_angle = random.uniform(0.0, math.tau)
        mosquito.orbit_direction *= -1
        return False

    def _route_target(self, game, mosquito: Mosquito) -> tuple[float, float] | None:
        if mosquito.route_refresh <= 0:
            start = (int(mosquito.x), int(mosquito.y))
            goal = (int(game.player.x), int(game.player.y))
            mosquito.route_path = self._find_path(start, goal)
            mosquito.route_refresh = random.uniform(0.25, 0.45)

        if not mosquito.route_path:
            return None

        current = (int(mosquito.x), int(mosquito.y))
        path = mosquito.route_path
        if len(path) == 1:
            return game.player.x, game.player.y
        next_cell = path[1] if path[0] == current else path[0]
        if len(path) > 2 and next_cell == current:
            next_cell = path[2]
        return next_cell[0] + 0.5, next_cell[1] + 0.5

    def _find_path(self, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
        if start == goal:
            return [start]
        if not self._cell_is_flyable(start) or not self._cell_is_flyable(goal):
            return []

        queue: deque[tuple[int, int]] = deque([start])
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        while queue:
            cell = queue.popleft()
            if cell == goal:
                break
            x, y = cell
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in came_from or not self._cell_is_flyable(neighbor):
                    continue
                came_from[neighbor] = cell
                queue.append(neighbor)

        if goal not in came_from:
            return []

        path: list[tuple[int, int]] = []
        cell: tuple[int, int] | None = goal
        while cell is not None:
            path.append(cell)
            cell = came_from[cell]
        path.reverse()
        return path

    def _cell_is_flyable(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return self.game_map.in_bounds(x, y) and not self.game_map.is_solid_cell(x, y)

    def _try_move(self, mosquito: Mosquito, angle: float, distance: float) -> bool:
        if distance <= 0:
            return True
        dx = math.cos(angle) * distance
        dy = math.sin(angle) * distance
        next_x = mosquito.x + dx
        next_y = mosquito.y + dy
        if self.game_map.can_move_to(next_x, next_y):
            mosquito.x = next_x
            mosquito.y = next_y
            return True
        if self.game_map.can_move_to(next_x, mosquito.y):
            mosquito.x = next_x
            return True
        if self.game_map.can_move_to(mosquito.x, next_y):
            mosquito.y = next_y
            return True
        return False

    def _start_burst(self, mosquito: Mosquito) -> None:
        mosquito.burst_timer = random.uniform(0.28, 0.55)
        mosquito.burst_cooldown = random.uniform(1.25, 2.2)

    def _burst_multiplier(self, mosquito: Mosquito) -> float:
        if mosquito.burst_timer <= 0:
            return 1.0
        pulse = 0.82 + 0.18 * abs(math.sin(mosquito.age * 24.0 + mosquito.mosquito_id))
        return MOSQUITO_BURST_SPEED_MULTIPLIER * pulse

    def _chase_speed_multiplier(self, mosquito: Mosquito) -> float:
        distance = mosquito.distance_to_player
        if distance > 7.0:
            return 1.90
        if distance > 3.0:
            return 1.85
        if distance > MOSQUITO_ATTACK_RANGE:
            return 1.70
        return 0.80

    def _attack_player_if_ready(self, game, mosquito: Mosquito) -> None:
        if mosquito.attack_cooldown > 0:
            return

        before = game.player.sanity
        game.player.sanity = max(0.0, game.player.sanity - MOSQUITO_ATTACK_SAN_DAMAGE)
        mosquito.attack_cooldown = MOSQUITO_ATTACK_COOLDOWN
        game.audio.play("mosquito_bite", volume=0.85, cooldown=0.25)
        game.set_message("被蚊虫击中，你的SAN值减少了。", 3.0)
        self._trigger_sanity_feedback(game.player, before)

        knockback_angle = math.atan2(mosquito.y - game.player.y, mosquito.x - game.player.x)
        self._try_move(mosquito, knockback_angle, 0.18)
        if game.player.sanity <= 0:
            game.enter_failure()

    def _trigger_sanity_feedback(self, player, previous_sanity: float) -> None:
        now = time.monotonic()
        player.sanity_damage_from = max(previous_sanity, player.sanity)
        player.sanity_damage_flash_until = now + 0.7
        player.sanity_shake_until = now + 0.45

    def _sample_trail(self, mosquito: Mosquito) -> None:
        if mosquito.trail_sample_timer > 0:
            return
        mosquito.trail_sample_timer = 0.07
        mosquito.trail.append((mosquito.x, mosquito.y, mosquito.age))
        if len(mosquito.trail) > 8:
            del mosquito.trail[: len(mosquito.trail) - 8]


def _normalize_angle(angle: float) -> float:
    return (angle + math.pi) % math.tau - math.pi


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
