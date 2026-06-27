from __future__ import annotations

from src.settings import (
    BATTERY_RESTORE,
    BUILDING_BOTTOM_FLOOR,
    BUILDING_TOP_FLOOR,
    TILE_CLASSROOM_DOOR,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
)
from src.systems.interaction_config import (
    LOBBY_EXIT_LOCKED_MESSAGE,
    PICKUP_ELEMENT_TYPE,
    TRANSITION_OBJECT_IDS,
)


class InteractionFlowMixin:
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

        if self.game_map.is_open_door(x, y):
            self.game_map.close_door(x, y)
            game.audio.play("door_open", volume=0.7, cooldown=0.15)
            return "你把门推回去了。"

        if tile == TILE_GUARD_DOOR:
            if game.current_floor == 3 and not player.flags.get("found_3f_security_code", False):
                game.audio.play("error")
                return "保安室是密码锁。得先找到三位密码。"
            self.game_map.open_door(x, y)
            game.audio.play("door_open")
            if game.current_floor == 3:
                return "648。保安室门锁弹开了。"
            return "门卫处门开了。"

        if tile == TILE_LAB_DOOR:
            if role == "server":
                if not game.is_floor_power_restored():
                    game.audio.play("error")
                    return "机房门禁没有反应，电力尚未恢复。"
                self.game_map.open_door(x, y)
                game.audio.play("door_open")
                return "机房门禁亮了一下，门开了。"
            if game.current_floor == BUILDING_TOP_FLOOR:
                self.game_map.open_door(x, y)
                player.flags["left_lab"] = True
                game.audio.play("door_open")
                game.audio.play_loop("ambient_lab", volume=0.35)
                return "门没锁。四楼实验室都能进，只能一间间找。"
            if not player.has_item("lab_key") and not player.has_item("stair_key"):
                game.audio.play("error")
                return "门被锁住了。我得先找能开楼梯间的钥匙。"
            self.game_map.open_door(x, y)
            player.flags["left_lab"] = True
            game.audio.play("door_open")
            game.audio.play_loop("ambient_lab", volume=0.35)
            return "门开了。先找能继续下楼的办法。"

        if tile == TILE_CLASSROOM_DOOR:
            self.game_map.open_door(x, y)
            player.flags["heard_lecture"] = True
            game.audio.play("door_open")
            game.audio.play_loop("lecture_loop", volume=0.55)
            return "教室门开了。里面没有人，但讲课声就在讲台附近。"

        if tile == TILE_POWER_DOOR:
            if game.current_floor == 3:
                self.game_map.open_door(x, y)
                game.audio.play("door_open")
                return "配电室门没锁。真正麻烦的是配电箱。"
            if not player.flags.get("got_blackboard_clue", False):
                game.audio.play("error")
                return "配电室门锁上的数字看不懂，也许黑板上有线索。"
            self.game_map.open_door(x, y)
            game.audio.play("door_open")
            return "黑板上的数字对上了。配电室门锁弹开。"

        if tile == TILE_EXIT_DOOR:
            if game.current_floor == BUILDING_BOTTOM_FLOOR:
                if self._is_stairwell_exit(cell):
                    if not player.has_item("old_corridor_note"):
                        game.audio.play("error")
                        return "我还不知道二楼能不能走。先查查一楼。"
                    self.game_map.open_door(x, y)
                    game.audio.play("door_open")
                    game.open_floor_exit_prompt(cell)
                    return ""
                player.flags["checked_lobby_exit"] = True
                game.audio.play("error")
                return LOBBY_EXIT_LOCKED_MESSAGE
            if game.current_floor == 2 and self._is_stairwell_exit(cell) and player.has_item("old_corridor_note"):
                return self._trigger_old_corridor_door(game)
            if game.current_floor > BUILDING_BOTTOM_FLOOR:
                if not player.has_item("stair_key") and not player.has_item("lab_key"):
                    game.audio.play("error")
                    return "人脸没电了。我得先在四楼实验室里找机械钥匙。"
                self.game_map.open_door(x, y)
                player.flags["safety_exit_opened"] = True
                game.audio.play("door_open")
                game.open_floor_exit_prompt(cell)
                return ""

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

        if trigger_id == "lab_flashlight":
            result = self._trigger_lab_flashlight(game, cell)
        elif trigger_id in {"lab_desk_supplies", "lab_desk", "desk"}:
            result = self._trigger_lab_desk_supplies(game)
        elif trigger_id == "stair_key":
            result = self._trigger_stair_key(game, cell)
        elif trigger_id in {"blackboard_clue", "blackboard", "lectern"}:
            result = self._trigger_blackboard_clue(game)
        elif trigger_id == "security_code_648":
            result = self._trigger_security_code_648(game)
        elif trigger_id == "security_desk":
            result = self._trigger_security_desk(game)
        elif trigger_id == "fuse_cabinet":
            result = self._trigger_fuse_cabinet(game, cell)
        elif trigger_id == "plastic_card_3f":
            result = self._trigger_plastic_card_3f(game, cell)
        elif trigger_id == "power_box":
            result = self._trigger_power_box(game)
        elif trigger_id == "server_terminal":
            result = self._trigger_server_terminal(game)
        elif trigger_id == "lobby_main_exit_locked":
            result = self._trigger_lobby_main_exit_locked(game)
        elif trigger_id == "lobby_register_note":
            result = self._trigger_lobby_register_note(game, cell)
        elif trigger_id == "whiteboard_memo":
            result = self._trigger_whiteboard_memo(game)
        elif trigger_id == "duty_roster":
            result = self._trigger_duty_roster(game)
        elif trigger_id == "staff_code_276":
            result = self._trigger_staff_code_276(game)
        elif trigger_id == "maintenance_pass":
            result = self._trigger_maintenance_pass(game, cell)
        elif trigger_id == "utility_badge":
            result = self._trigger_utility_badge(game, cell)
        elif trigger_id == "magnet_release":
            result = self._trigger_magnet_release(game)
        elif trigger_id == "old_corridor_door":
            result = self._trigger_old_corridor_door(game)
        else:
            result = self._trigger_generic(game, cell, obj, trigger_id)

        if obj.trigger_once:
            player.flags[f"triggered_{trigger_id}"] = True
        return result

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
            if game.current_floor > BUILDING_BOTTOM_FLOOR and not player.has_item("stair_key") and not player.has_item("lab_key"):
                game.audio.play("error")
                return "安全出口需要机械钥匙。四楼实验室里应该有一把。"
            if game.current_floor == BUILDING_BOTTOM_FLOOR:
                if not player.has_item("old_corridor_note"):
                    game.audio.play("error")
                    return "我还不知道二楼旧连廊。先查一楼。"
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

    def _is_stairwell_exit(self, cell: tuple[int, int]) -> bool:
        x, _y = cell
        return x > self.game_map.width * 0.5
