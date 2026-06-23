"""Context interaction logic."""

from __future__ import annotations

import math

from .settings import (
    BATTERY_RESTORE,
    DOOR_TILES,
    INTERACT_DISTANCE,
    TILE_CLASSROOM_DOOR,
    TILE_EXIT_DOOR,
    TILE_GUARD_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
)


class InteractionSystem:
    def __init__(self, game_map) -> None:
        self.game_map = game_map

    def focused_target(self, player):
        cos_a = math.cos(player.angle)
        sin_a = math.sin(player.angle)
        distance = 0.25
        while distance <= INTERACT_DISTANCE:
            cell = (int(player.x + cos_a * distance), int(player.y + sin_a * distance))
            obj = self.game_map.object_at(*cell)
            if obj is not None:
                return ("object", cell, obj)
            tile = self.game_map.tile_at(*cell)
            if tile in DOOR_TILES and not self.game_map.is_open_door(*cell):
                return ("door", cell, tile)
            distance += 0.08
        return None

    def prompt_for(self, player) -> str:
        target = self.focused_target(player)
        if target is None:
            return ""
        kind, cell, payload = target
        if kind == "object":
            return payload.prompt
        tile = payload
        role = self.game_map.door_role_at(*cell)
        if tile == TILE_EXIT_DOOR:
            return "按 Space 使用门禁"
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
                if not player.flags.get("power_restored", False):
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
            if not player.flags.get("power_restored", False):
                game.audio.play("error")
                return "出口门禁没有反应，电力尚未恢复。"
            if not player.has_item("access_card"):
                game.audio.play("error")
                return "门禁灯闪着红光，需要门禁卡。"
            player.flags["exit_opened"] = True
            player.flags["success_ending"] = True
            game.audio.play("door_open")
            game.enter_success()
            return "门禁灯由红变绿。"

        game.audio.play("error")
        return "打不开。"

    def _interact_object(self, game, cell: tuple[int, int], obj) -> str:
        player = game.player
        x, y = cell

        if obj.object_id == "lab_desk":
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

        if obj.object_id in {"blackboard", "lectern"}:
            if not player.has_item("note_a"):
                player.add_item("note_a")
                player.sanity = max(0, player.sanity - 7)
                game.audio.play("laugh", volume=0.7, cooldown=1.0)
                return "黑板上写着 0204。你获得纸条 A：不要回答点名。"
            return "黑板上的数字仍停在 0204，像刚写上去。"

        if obj.object_id == "security_desk":
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

        if obj.object_id == "fuse_cabinet":
            if not player.has_item("fuse"):
                player.add_item("fuse")
                self.game_map.remove_object(x, y)
                game.audio.play("item_pick")
                return "你从工具柜中拿到一枚保险丝。"
            return "工具柜已经空了。"

        if obj.object_id == "battery":
            player.add_item("battery")
            player.restore_flashlight(BATTERY_RESTORE)
            self.game_map.remove_object(x, y)
            game.audio.play("item_pick")
            return "你拾起备用电池，手电电量恢复了一些。"

        if obj.object_id == "power_box":
            if not player.has_item("fuse"):
                game.audio.play("error")
                return "配电箱里少了一枚保险丝。"
            if player.flags.get("power_restored", False):
                return "电力已经恢复了一部分，机房门禁现在应该能用了。"
            player.flags["power_restored"] = True
            player.sanity = min(100, player.sanity + 6)
            game.audio.stop_loop("lecture_loop")
            game.audio.play_loop("ambient_power", volume=0.42)
            game.audio.play("power_restore", volume=0.85, cooldown=1.0)
            return "保险丝装上后，整栋楼像是短暂地醒了一下。"

        if obj.object_id == "server_terminal":
            if not player.flags.get("power_restored", False):
                game.audio.play("error")
                return "屏幕没有亮，机房还没有供电。"
            if not player.has_item("access_card"):
                player.add_item("access_card")
                player.sanity = max(0, player.sanity - 6)
                game.audio.play("cry", volume=0.65, cooldown=1.0)
                return "屏幕显示 LabMidnight.map。你在键盘旁找到一张门禁卡。"
            return "屏幕上显示：玩家位置，四层实验楼。出口状态：等待确认。"

        if obj.object_id == "exit_panel":
            if not player.flags.get("power_restored", False):
                game.audio.play("error")
                return "电力尚未恢复，出口门禁没有反应。"
            if not player.has_item("access_card"):
                game.audio.play("error")
                return "需要门禁卡。"
            player.flags["exit_opened"] = True
            player.flags["success_ending"] = True
            game.audio.play("door_open")
            game.enter_success()
            return "门禁灯由红变绿。"

        game.audio.play("error")
        return obj.description or "这里没有更多线索。"
