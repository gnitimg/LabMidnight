from __future__ import annotations

from src.settings import BATTERY_RESTORE
from src.systems.interaction_config import LOBBY_EXIT_LOCKED_MESSAGE


class InteractionTriggerMixin:
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
        if not player.has_item("flashlight"):
            player.add_item("flashlight")
            player.flashlight_on = True
            game.audio.play("item_pick")
            return "手电拿到了。四楼实验室都没锁，只能一间间找钥匙。"
        return "手电已经拿了。电量还得省着用。"

    def _trigger_lab_flashlight(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("flashlight"):
            player.add_item("flashlight")
            player.flashlight_on = True
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "手电拿到了。四楼实验室都没锁，只能一间间找钥匙。"
        return "手电已经拿了。电量还得省着用。"

    def _trigger_stair_key(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("stair_key"):
            player.add_item("stair_key")
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "钥匙找到了。别高兴太早，它只够我下到三楼。"
        return "钥匙已经在我手里。"

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

    def _trigger_security_code_648(self, game) -> str:
        game.player.flags["found_3f_security_code"] = True
        game.audio.play("item_pick")
        return "密码条写着 648。昨天刚充过，怎么又是你。"

    def _trigger_fuse_cabinet(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("fuse"):
            player.add_item("fuse")
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "保安室没钥匙，倒摸到一截保险丝。也许能救命。"
        return "工具盒已经空了。"

    def _trigger_plastic_card_3f(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("plastic_card"):
            player.add_item("plastic_card")
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "几张塑料卡片。撬配电箱应该够硬。"
        return "卡片已经拿了。"

    def _trigger_power_box(self, game) -> str:
        player = game.player
        if not player.has_item("plastic_card"):
            game.audio.play("error")
            return "配电箱锁着。得找张硬卡片撬开。"
        if not player.has_item("fuse"):
            game.audio.play("error")
            return "保险丝槽是空的。先找保险丝。"
        if game.is_floor_power_restored():
            return "这一层已经来电。电梯还能撑一会儿。"
        game.restore_current_floor_power()
        player.sanity = min(100, player.sanity + 6)
        game.audio.stop_loop("lecture_loop")
        game.audio.play_loop("ambient_power", volume=0.42)
        game.audio.play("power_restore", volume=0.85, cooldown=1.0)
        return "滴。整层门禁闪了一下。现在，冲去电梯。"

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

    def _trigger_lobby_main_exit_locked(self, game) -> str:
        game.player.flags["checked_lobby_exit"] = True
        game.audio.play("error")
        return LOBBY_EXIT_LOCKED_MESSAGE

    def _trigger_lobby_register_note(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("old_corridor_note"):
            player.add_item("old_corridor_note")
            player.flags["found_old_corridor_note"] = True
            game.audio.play("item_pick")
            return "登记册夹着便签：二楼旧连廊。只能再上去。"
        return "二楼旧连廊。二层值班点。别走东侧。"

    def _trigger_whiteboard_memo(self, game) -> str:
        game.player.flags["found_2f_shift_hint"] = True
        game.audio.play("item_pick")
        return "白板背面写着“值班表”。密码大概在那。"

    def _trigger_duty_roster(self, game) -> str:
        player = game.player
        player.flags["checked_2f_roster"] = True
        game.audio.play("error", volume=0.45, cooldown=0.4)
        return "6、12、18？我试了 618。错。冷笑话也太冷了。"

    def _trigger_staff_code_276(self, game) -> str:
        player = game.player
        player.flags["found_2f_code"] = True
        game.audio.play("item_pick")
        return "灭火器后面压着工号：276。总算像个密码。"

    def _trigger_maintenance_pass(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.flags.get("found_2f_code", False):
            game.audio.play("error")
            return "值班点锁着。我还缺三位密码。"
        if not player.has_item("maintenance_pass"):
            player.add_item("maintenance_pass")
            player.flags["opened_2f_duty_point"] = True
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "276，锁开了。抽屉里是旧连廊通行牌。"
        return "通行牌已经拿了。"

    def _trigger_utility_badge(self, game, cell: tuple[int, int]) -> str:
        player = game.player
        if not player.has_item("utility_badge"):
            player.add_item("utility_badge")
            self.game_map.remove_object(*cell)
            game.audio.play("item_pick")
            return "废弃工牌，够薄。今晚全靠童年歪门邪道。"
        return "工牌已经拿了。"

    def _trigger_magnet_release(self, game) -> str:
        player = game.player
        if not player.flags.get("old_corridor_stuck", False):
            game.audio.play("error")
            return "先去试试西侧安全门。别乱按。"
        if not player.has_item("utility_badge"):
            game.audio.play("error")
            return "箱门被铁丝缠住。得找张硬卡撬开。"
        if player.flags.get("magnet_released", False):
            return "磁吸已经松了。别站着，跑。"
        player.flags["magnet_released"] = True
        game.audio.play("power_restore", volume=0.8, cooldown=1.0)
        return "我按下释放开关。走廊尽头“砰”地松了一下。"

    def _trigger_old_corridor_door(self, game) -> str:
        player = game.player
        if not player.has_item("maintenance_pass"):
            game.audio.play("error")
            return "西侧安全门不认我。先找旧连廊通行牌。"
        if not player.flags.get("old_corridor_stuck", False):
            player.flags["old_corridor_stuck"] = True
            game.audio.play("error")
            return "绿灯亮了，门没开。磁吸扣死了，得去配电箱。"
        if not player.flags.get("magnet_released", False):
            game.audio.play("error")
            return "门还被磁吸吸住。配电箱旁应该有手动释放。"
        player.flags["escaped_old_corridor"] = True
        player.flags["success_ending"] = True
        game.audio.play("door_open")
        game.enter_success()
        return "门缝够了。我挤出去，外面的风终于吹到脸上。"


