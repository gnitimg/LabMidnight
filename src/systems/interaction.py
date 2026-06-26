"""Context interaction logic."""

from __future__ import annotations

import math

from src.settings import (
    BATTERY_RESTORE,
    BUILDING_BOTTOM_FLOOR,
    BUILDING_TOP_FLOOR,
    DOOR_TILES,
    INTERACT_DISTANCE,
    TILE_CLASSROOM_DOOR,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
    WALL_TILES,
)


TRANSITION_OBJECT_IDS = {"elevator", "exit_panel"}
PICKUP_ELEMENT_TYPE = "pickup"
TRIGGER_ELEMENT_TYPE = "trigger"


class InteractionSystem:
    def __init__(self, game_map) -> None:
        self.game_map = game_map

    def focused_target(self, player):
        cos_a = math.cos(player.angle)
        sin_a = math.sin(player.angle)
        object_hit = self._pointed_object(player.x, player.y, cos_a, sin_a, INTERACT_DISTANCE)
        tile_hit = self._pointed_blocking_tile(player.x, player.y, cos_a, sin_a, INTERACT_DISTANCE)

        if tile_hit is not None:
            kind, distance, cell, tile = tile_hit
            if object_hit is None or distance <= object_hit[0] + 0.02:
                if kind == "door":
                    return ("door", cell, tile)
                return None

        if object_hit is not None:
            _distance, anchor, obj = object_hit
            return ("object", anchor, obj)
        return None

    def _pointed_object(self, x: float, y: float, dx: float, dy: float, max_distance: float):
        best = None
        for anchor, obj in self.game_map.objects.items():
            if anchor in self.game_map.picked_objects or not self._object_has_interaction(obj):
                continue
            min_x, min_y, max_x, max_y = self.game_map.object_bounds(anchor, obj)
            distance = self._ray_box_distance(x, y, dx, dy, min_x, min_y, max_x, max_y)
            if distance is None or distance > max_distance:
                continue
            if best is None or distance < best[0]:
                best = (distance, anchor, obj)
        return best

    def _pointed_blocking_tile(self, x: float, y: float, dx: float, dy: float, max_distance: float):
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
            if self.game_map.floor > BUILDING_BOTTOM_FLOOR:
                if player.has_item("access_card"):
                    return "按 Space 进入安全出口"
                return "安全出口需要门禁卡"
            return "向前离开实验楼"
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

    def interact(self, game) -> str:
        player = game.player
        target = self.focused_target(player)
        if target is None:
            game.audio.play("error", volume=0.45, cooldown=0.4)
            return "前面没有可以交互的东西。"
        kind, cell, payload = target
        if kind == "door":
            return self._interact_door(game, cell, payload)
        return self._interact_object(game, cell, payload)

    def _interact_door(self, game, cell: tuple[int, int], tile: int) -> str:
        player = game.player
        x, y = cell
        role = self.game_map.door_role_at(x, y)

        if tile == TILE_GUARD_DOOR:
            self.game_map.open_door(x, y)
            game.audio.play("door_open")
            return "门卫处门开了。"

        if tile == TILE_LAB_DOOR:
            if role == "server":
                if not game.is_floor_power_restored():
                    game.audio.play("error")
                    return "机房门禁没有反应，电力尚未恢复。"
                self.game_map.open_door(x, y)
                game.audio.play("door_open")
                return "机房门禁亮了一下，门开了。"
            if not player.has_item("lab_key"):
                game.audio.play("error")
                return "门被锁住了。钥匙应该还在实验室里。"
            self.game_map.open_door(x, y)
            player.flags["left_lab"] = True
            game.audio.play("door_open")
            game.audio.play_loop("ambient_lab", volume=0.35)
            return "实验室门打开了。走廊里传来很远的讲课声。"

        if tile == TILE_CLASSROOM_DOOR:
            self.game_map.open_door(x, y)
            player.flags["heard_lecture"] = True
            game.audio.play("door_open")
            game.audio.play_loop("lecture_loop", volume=0.55)
            return "教室门开了。里面没有人，但讲课声就在讲台附近。"

        if tile == TILE_POWER_DOOR:
            if not player.flags.get("got_blackboard_clue", False):
                game.audio.play("error")
                return "配电室门锁上的数字看不懂，也许黑板上有线索。"
            self.game_map.open_door(x, y)
            game.audio.play("door_open")
            return "黑板上的数字对上了。配电室门锁弹开。"

        if tile == TILE_EXIT_DOOR:
            if game.current_floor > BUILDING_BOTTOM_FLOOR:
                if not player.has_item("access_card"):
                    game.audio.play("error")
                    return "安全出口门禁没有反应，需要门禁卡。"
                self.game_map.open_door(x, y)
                player.flags["safety_exit_opened"] = True
                game.audio.play("door_open")
                game.open_floor_exit_prompt(cell)
                return ""
            player.flags["exit_opened"] = True
            player.flags["success_ending"] = True
            game.audio.play("door_open")
            game.enter_success()
            return "你冲出一层出口，夜风一下子灌进来。"

        game.audio.play("error")
        return "打不开。"

    def _interact_configured_object(self, game, cell: tuple[int, int], obj) -> str | None:
        if self._object_is_trigger(obj):
            return self._interact_trigger_object(game, cell, obj)
        if self._object_is_pickup(obj):
            return self._interact_pickup_object(game, cell, obj)
        return None

    def _interact_pickup_object(self, game, cell: tuple[int, int], obj) -> str:
        player = game.player
        if obj.required_item and not player.has_item(obj.required_item):
            game.audio.play("error")
            return obj.failure_message or f"Need {obj.required_item}."
        if obj.required_flag and not player.flags.get(obj.required_flag, False):
            game.audio.play("error")
            return obj.failure_message or f"Story condition not met: {obj.required_flag}."

        item_id = obj.pickup_item.strip() if obj.pickup_item else ""
        if obj.element_type == PICKUP_ELEMENT_TYPE and not item_id:
            item_id = obj.object_id

        gained_item = False
        if item_id == "battery":
            player.add_item(item_id)
            player.restore_flashlight(BATTERY_RESTORE)
            gained_item = True
        elif item_id and not player.has_item(item_id):
            player.add_item(item_id)
            gained_item = True
            if item_id == "flashlight":
                player.flashlight_on = True

        flag_set = False
        if obj.pickup_flag:
            player.flags[obj.pickup_flag] = True
            flag_set = True

        if obj.remove_on_pickup and (gained_item or flag_set or not item_id):
            self.game_map.remove_object(*cell)

        if gained_item or flag_set:
            game.audio.play("item_pick")
            if obj.interaction_message:
                return obj.interaction_message
            if item_id and obj.pickup_flag:
                return f"Picked up {item_id}. Story flag set: {obj.pickup_flag}."
            if item_id:
                return f"Picked up {item_id}."
            return "Story state updated."

        if item_id and player.has_item(item_id):
            return obj.interaction_message or f"{item_id} already picked up."

        return obj.interaction_message or obj.description or "Nothing else here."

    def _interact_trigger_object(self, game, cell: tuple[int, int], obj) -> str:
        player = game.player
        trigger_id = str(obj.trigger_id).strip() or obj.object_id

        if obj.required_item and not player.has_item(obj.required_item):
            game.audio.play("error")
            return obj.failure_message or f"Need {obj.required_item}."
        if obj.required_flag and not player.flags.get(obj.required_flag, False):
            game.audio.play("error")
            return obj.failure_message or f"Story condition not met: {obj.required_flag}."

        if trigger_id in {"lab_desk_supplies", "lab_desk", "desk"}:
            result = self._trigger_lab_desk_supplies(game)
        elif trigger_id in {"blackboard_clue", "blackboard", "lectern"}:
            result = self._trigger_blackboard_clue(game)
        elif trigger_id == "security_desk":
            result = self._trigger_security_desk(game)
        elif trigger_id == "fuse_cabinet":
            result = self._trigger_fuse_cabinet(game, cell)
        elif trigger_id == "power_box":
            result = self._trigger_power_box(game)
        elif trigger_id == "server_terminal":
            result = self._trigger_server_terminal(game)
        else:
            result = self._trigger_generic(game, cell, obj, trigger_id)

        if obj.trigger_once:
            player.flags[f"triggered_{trigger_id}"] = True
        return result

    def _trigger_generic(self, game, cell: tuple[int, int], obj, trigger_id: str) -> str:
        player = game.player
        triggered_flag = f"triggered_{trigger_id}"
        if obj.trigger_once and player.flags.get(triggered_flag, False):
            return obj.interaction_message or obj.description or "这里已经没有新的反应。"

        item_id = obj.pickup_item.strip() if obj.pickup_item else ""
        gained_item = False
        if item_id == "battery":
            player.add_item(item_id)
            player.restore_flashlight(BATTERY_RESTORE)
            gained_item = True
        elif item_id and not player.has_item(item_id):
            player.add_item(item_id)
            gained_item = True
            if item_id == "flashlight":
                player.flashlight_on = True

        flag_set = False
        if obj.pickup_flag:
            player.flags[obj.pickup_flag] = True
            flag_set = True

        if obj.remove_on_pickup and (gained_item or flag_set or not item_id):
            self.game_map.remove_object(*cell)

        if gained_item or flag_set:
            game.audio.play("item_pick")

        return obj.interaction_message or obj.description or "这里的状态被触发了。"

    def _trigger_lab_desk_supplies(self, game) -> str:
        player = game.player
        gained = []
        if not player.has_item("flashlight"):
            player.add_item("flashlight")
            player.flashlight_on = True
            gained.append("手电筒")
        if not player.has_item("lab_key"):
            player.add_item("lab_key")
            gained.append("实验室钥匙")
        if gained:
            game.audio.play("item_pick")
            return "你检查实验桌，获得了：" + "、".join(gained) + "。"
        return "桌面只剩电脑错误提示：运行超时。"

    def _trigger_blackboard_clue(self, game) -> str:
        player = game.player
        if not player.has_item("note_a"):
            player.add_item("note_a")
            player.flags["got_blackboard_clue"] = True
            player.sanity = max(0, player.sanity - 7)
            game.audio.play("laugh", volume=0.7, cooldown=1.0)
            return "黑板上写着 0204。你获得纸条 A：不要回答点名。"
        player.flags["got_blackboard_clue"] = True
        return "黑板上的数字仍停在 0204，像刚写上去。"

    def _trigger_security_desk(self, game) -> str:
        player = game.player
        gained = []
        if not player.has_item("map"):
            player.add_item("map")
            gained.append("实验楼平面图")
        if not player.has_item("note_b"):
            player.add_item("note_b")
            gained.append("纸条 B")
        if gained:
            game.audio.play("item_pick")
            return "值班记录停在 02:00。你获得了：" + "、".join(gained) + "。"
        return "值班记录从 02:00 开始不断重复。"

    def _trigger_fuse_cabinet(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("fuse"):
            player.add_item("fuse")
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "你从工具柜中拿到一枚保险丝。"
        return "工具柜已经空了。"

    def _trigger_power_box(self, game) -> str:
        player = game.player
        if not player.has_item("fuse"):
            game.audio.play("error")
            return "配电箱里少了一枚保险丝。"
        if game.is_floor_power_restored():
            return "本层电力已经恢复，机房门禁和电梯现在应该能用了。"
        game.restore_current_floor_power()
        player.sanity = min(100, player.sanity + 6)
        game.audio.stop_loop("lecture_loop")
        game.audio.play_loop("ambient_power", volume=0.42)
        game.audio.play("power_restore", volume=0.85, cooldown=1.0)
        return f"{game.current_floor}F 的保险丝接上后，本层电力恢复了。"

    def _trigger_server_terminal(self, game) -> str:
        player = game.player
        if not game.is_floor_power_restored():
            game.audio.play("error")
            return "屏幕没有亮，机房还没有供电。"
        if not player.has_item("access_card"):
            player.add_item("access_card")
            player.sanity = max(0, player.sanity - 6)
            game.audio.play("cry", volume=0.65, cooldown=1.0)
            return "屏幕显示 LabMidnight.map。你在键盘旁找到一张门禁卡。"
        return "屏幕上显示：玩家位置，四层实验楼。出口状态：等待确认。"

    def _interact_object(self, game, cell: tuple[int, int], obj) -> str:
        if obj.object_id in TRANSITION_OBJECT_IDS:
            return self._interact_transition_panel(game, cell, obj)

        configured = self._interact_configured_object(game, cell, obj)
        if configured is not None:
            return configured

        game.audio.play("error")
        return obj.description or "这里没有更多线索。"

    def _interact_transition_panel(self, game, cell: tuple[int, int], obj) -> str:
        player = game.player
        if obj.object_id == "exit_panel":
            if game.current_floor > BUILDING_BOTTOM_FLOOR and not player.has_item("access_card"):
                game.audio.play("error")
                return "安全出口门禁需要门禁卡。"
            if game.current_floor == BUILDING_BOTTOM_FLOOR:
                player.flags["exit_opened"] = True
                player.flags["success_ending"] = True
                game.audio.play("door_open")
                game.enter_success()
                return "你冲出一层出口，夜风一下子灌进来。"
            targets = []
            if game.current_floor > BUILDING_BOTTOM_FLOOR:
                targets.append(game.current_floor - 1)
            if game.current_floor < BUILDING_TOP_FLOOR:
                targets.append(game.current_floor + 1)
            game.audio.play("door_open")
            game.open_floor_transition_prompt(targets, "安全出口", entry_kind="exit", source_cell=cell)
            return ""

        targets = [floor for floor in range(BUILDING_BOTTOM_FLOOR, BUILDING_TOP_FLOOR + 1) if floor != game.current_floor]
        if obj.object_id == "elevator" and not game.is_floor_power_restored():
            game.audio.play("error")
            return "电梯没有供电。先在本层接上保险丝。"
        game.audio.play("door_open")
        game.open_floor_transition_prompt(targets, "东11C货梯", entry_kind="elevator", source_cell=cell)
        return ""
