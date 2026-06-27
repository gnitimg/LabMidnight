from __future__ import annotations

import math

from src.settings import (
    BUILDING_BOTTOM_FLOOR,
    CAMERA_HEIGHT_UNITS,
    DOOR_TILES,
    INTERACT_DISTANCE,
    TILE_EXIT_DOOR,
    TILE_POWER_DOOR,
    VERTICAL_UNITS_PER_TILE,
    WALL_TILES,
)
from src.systems.interaction_config import (
    LOW_OBJECT_AIM_HEIGHT,
    OBJECT_AIM_PADDING_XY,
    OBJECT_AIM_PADDING_Z,
    PICKUP_ELEMENT_TYPE,
    TRANSITION_OBJECT_IDS,
    TRIGGER_ELEMENT_TYPE,
)


class InteractionTargetingMixin:
    def focused_target(self, player):
        dir_x, dir_y, dir_z = player.view_direction()
        object_hit = self._pointed_object(player, dir_x, dir_y, dir_z, INTERACT_DISTANCE)
        tile_hit = self._pointed_blocking_tile(player.x, player.y, dir_x, dir_y, INTERACT_DISTANCE)

        if tile_hit is not None:
            kind, distance, cell, tile = tile_hit
            if object_hit is None or distance <= object_hit[0] + 0.02:
                if kind == "door":
                    return ("door", cell, tile)
                return None

        if object_hit is not None:
            _distance, _ray_distance, anchor, obj = object_hit
            return ("object", anchor, obj)
        return None

    def _pointed_object(self, player, dx: float, dy: float, dz: float, max_distance: float):
        best = None
        for anchor, obj in self.game_map.objects.items():
            if anchor in self.game_map.picked_objects or not self._object_has_interaction(obj):
                continue
            min_x, min_y, max_x, max_y = self.game_map.object_bounds(anchor, obj)
            min_z, max_z = self._object_aim_z_bounds(obj)
            hit = self._ray_box_hit_3d(
                player.x,
                player.y,
                CAMERA_HEIGHT_UNITS,
                dx,
                dy,
                dz,
                min_x,
                min_y,
                min_z,
                max_x,
                max_y,
                max_z,
            )
            if hit is None:
                continue
            horizontal_distance, ray_distance = hit
            if horizontal_distance > max_distance:
                continue
            if best is None or horizontal_distance < best[0] or (
                abs(horizontal_distance - best[0]) <= 1e-5 and ray_distance < best[1]
            ):
                best = (horizontal_distance, ray_distance, anchor, obj)
        return best

    def _pointed_blocking_tile(self, x: float, y: float, dx: float, dy: float, max_distance: float):
        horizontal = math.hypot(dx, dy)
        if horizontal <= 1e-6:
            return None
        dx /= horizontal
        dy /= horizontal
        distance = 0.05
        seen: set[tuple[int, int]] = set()
        while distance <= max_distance:
            cell = (int(x + dx * distance), int(y + dy * distance))
            if cell in seen:
                distance += 0.03
                continue
            seen.add(cell)
            tile = self.game_map.tile_at(*cell)
            if tile in DOOR_TILES:
                if not self.game_map.is_open_door(*cell) or tile == TILE_EXIT_DOOR:
                    return ("door", distance, cell, tile)
            elif tile in WALL_TILES:
                return ("wall", distance, cell, tile)
            distance += 0.03
        return None

    def _object_aim_z_bounds(self, obj) -> tuple[float, float]:
        min_z = max(0.0, obj.placement_height * VERTICAL_UNITS_PER_TILE)
        height = max(0.05, obj.height) * VERTICAL_UNITS_PER_TILE
        max_z = min_z + height
        if self._object_is_pickup(obj):
            max_z = max(max_z, min_z + LOW_OBJECT_AIM_HEIGHT)
        return min_z, max_z

    def _ray_box_hit_3d(
        self,
        origin_x: float,
        origin_y: float,
        origin_z: float,
        dir_x: float,
        dir_y: float,
        dir_z: float,
        min_x: float,
        min_y: float,
        min_z: float,
        max_x: float,
        max_y: float,
        max_z: float,
    ) -> tuple[float, float] | None:
        min_x -= OBJECT_AIM_PADDING_XY
        min_y -= OBJECT_AIM_PADDING_XY
        min_z -= OBJECT_AIM_PADDING_Z
        max_x += OBJECT_AIM_PADDING_XY
        max_y += OBJECT_AIM_PADDING_XY
        max_z += OBJECT_AIM_PADDING_Z

        t_min = 0.0
        t_max = float("inf")
        for origin, direction, lower, upper in (
            (origin_x, dir_x, min_x, max_x),
            (origin_y, dir_y, min_y, max_y),
            (origin_z, dir_z, min_z, max_z),
        ):
            if abs(direction) <= 1e-8:
                if origin < lower or origin > upper:
                    return None
                continue
            t1 = (lower - origin) / direction
            t2 = (upper - origin) / direction
            near = min(t1, t2)
            far = max(t1, t2)
            t_min = max(t_min, near)
            t_max = min(t_max, far)
            if t_max < t_min:
                return None

        if t_max < 0:
            return None
        ray_distance = max(0.0, t_min)
        horizontal_distance = math.hypot(dir_x * ray_distance, dir_y * ray_distance)
        return horizontal_distance, ray_distance

    def _ray_box_distance(
        self,
        origin_x: float,
        origin_y: float,
        dir_x: float,
        dir_y: float,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> float | None:
        padding = 0.025
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding
        t_min = 0.0
        t_max = float("inf")
        for origin, direction, lower, upper in (
            (origin_x, dir_x, min_x, max_x),
            (origin_y, dir_y, min_y, max_y),
        ):
            if abs(direction) <= 1e-8:
                if origin < lower or origin > upper:
                    return None
                continue
            t1 = (lower - origin) / direction
            t2 = (upper - origin) / direction
            near = min(t1, t2)
            far = max(t1, t2)
            t_min = max(t_min, near)
            t_max = min(t_max, far)
            if t_max < t_min:
                return None
        if t_max < 0:
            return None
        return max(0.0, t_min)

    def _object_has_interaction(self, obj) -> bool:
        return bool(
            obj.object_id in TRANSITION_OBJECT_IDS
            or self._object_is_trigger(obj)
            or self._object_is_pickup(obj)
        )

    def _object_is_trigger(self, obj) -> bool:
        return bool(
            getattr(obj, "is_trigger", False)
            or str(getattr(obj, "trigger_id", "")).strip()
            or getattr(obj, "element_type", "") == TRIGGER_ELEMENT_TYPE
        )

    def _object_is_pickup(self, obj) -> bool:
        return bool(
            getattr(obj, "element_type", "") == PICKUP_ELEMENT_TYPE
            or getattr(obj, "resource_role", "") == "optional"
            or str(getattr(obj, "pickup_item", "")).strip()
            or str(getattr(obj, "pickup_flag", "")).strip()
        )

    def prompt_for(self, player) -> str:
        target = self.focused_target(player)
        if target is None:
            return ""
        kind, cell, payload = target
        if kind == "object":
            if payload.object_id == "elevator" and not player.flags.get("power_restored", False):
                return "电梯未通电"
            if payload.object_id in TRANSITION_OBJECT_IDS:
                return "按 Space 使用东11C货梯"
            if payload.prompt:
                return payload.prompt
            if self._object_is_pickup(payload):
                return f"按 Space 拾取{payload.name}"
            return f"按 Space 检查{payload.name}"
        tile = payload
        role = self.game_map.door_role_at(*cell)
        if tile == TILE_EXIT_DOOR:
            if self.game_map.floor == BUILDING_BOTTOM_FLOOR:
                if self._is_stairwell_exit(cell):
                    if player.has_item("old_corridor_note"):
                        return "按 Space 上二楼"
                    return "楼梯间。先看看大厅有没有线索"
                return "按 Space 推大厅玻璃门"
            if self.game_map.floor == 2 and self._is_stairwell_exit(cell) and player.has_item("old_corridor_note"):
                return "按 Space 检查西侧安全门"
            if not player.has_item("stair_key") and not player.has_item("lab_key"):
                return "安全出口需要机械钥匙"
            return "按 Space 进入安全出口"
        if tile == TILE_POWER_DOOR:
            return "按 Space 检查配电室门"
        if role == "server":
            return "按 Space 检查机房门"
        if role == "lab":
            return "按 Space 开实验室门"
        if role == "classroom":
            return "按 Space 开教室门"
        if role == "guard":
            return "按 Space 开门卫处门"
        return "按 Space 开门"

