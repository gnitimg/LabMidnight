from __future__ import annotations

from src.maps.map_data import GameMap
from src.rendering.renderer import RaycastingRenderer
from src.settings import (
    BUILDING_BOTTOM_FLOOR,
    BUILDING_TOP_FLOOR,
    STATE_FLOOR_CONFIRM,
    STATE_PLAYING,
)
from src.systems.interaction import InteractionSystem


class GameFloorMixin:
    def _bind_floor_systems(self) -> None:
        self._sync_current_floor_power_flag()
        self.renderer = RaycastingRenderer(self.screen, self.game_map)
        self.interaction = InteractionSystem(self.game_map)

    def _save_current_floor_map_state(self) -> None:
        if hasattr(self, "game_map"):
            self.floor_picked_objects[self.current_floor] = set(self.game_map.picked_objects)

    def _load_current_floor_map(self) -> None:
        self.game_map = GameMap(self.current_floor)
        picked = self.floor_picked_objects.get(self.current_floor)
        if picked is None:
            self.floor_picked_objects[self.current_floor] = set(self.game_map.picked_objects)
        else:
            self.game_map.picked_objects = set(picked)

    def floor_power_flag(self, floor: int | None = None) -> str:
        target_floor = self.current_floor if floor is None else floor
        return f"power_restored_floor_{target_floor}"

    def is_floor_power_restored(self, floor: int | None = None) -> bool:
        return bool(self.player.flags.get(self.floor_power_flag(floor), False))

    def restore_current_floor_power(self) -> None:
        self.player.flags[self.floor_power_flag()] = True
        self._sync_current_floor_power_flag()

    def _sync_current_floor_power_flag(self) -> None:
        if not hasattr(self, "player"):
            return
        self.player.flags["power_restored"] = self.is_floor_power_restored(self.current_floor)

    def _clear_floor_transition(self) -> None:
        self.floor_transition_options = []
        self.floor_transition_entry_kind = ""
        self.floor_transition_source_cell = None

    def open_floor_exit_prompt(self, source_cell: tuple[int, int] | None = None) -> None:
        targets: list[int] = []
        if self.current_floor > BUILDING_BOTTOM_FLOOR:
            targets.append(self.current_floor - 1)
        if self.current_floor < BUILDING_TOP_FLOOR:
            targets.append(self.current_floor + 1)
        self.open_floor_transition_prompt(targets, "安全出口", entry_kind="exit", source_cell=source_cell)

    def open_floor_transition_prompt(
        self,
        target_floors: list[int],
        title: str,
        entry_kind: str = "",
        source_cell: tuple[int, int] | None = None,
    ) -> None:
        options = self._allowed_floor_transition_options(target_floors, entry_kind)
        if not options:
            self.set_message("这里没有可去的楼层。", 2.0)
            self._clear_floor_transition()
            self.set_state(STATE_PLAYING)
            return
        self.floor_transition_options = options
        self.floor_transition_title = title
        self.floor_transition_entry_kind = entry_kind
        self.floor_transition_source_cell = source_cell
        self.floor_choice_selected = 0
        self.set_state(STATE_FLOOR_CONFIRM)

    def _allowed_floor_transition_options(self, target_floors: list[int], entry_kind: str) -> list[int]:
        options = [
            floor
            for floor in target_floors
            if BUILDING_BOTTOM_FLOOR <= floor <= BUILDING_TOP_FLOOR and floor != self.current_floor
        ]
        entry_kind = entry_kind.strip().lower()
        if entry_kind == "exit":
            allowed = set(self._allowed_exit_floors())
            return [floor for floor in options if floor in allowed]
        if entry_kind == "elevator":
            allowed = set(self._allowed_elevator_floors())
            return [floor for floor in options if floor in allowed]
        return options

    def _allowed_exit_floors(self) -> list[int]:
        if self.current_floor == BUILDING_TOP_FLOOR:
            return [BUILDING_TOP_FLOOR - 1] if self.player.has_item("stair_key") or self.player.has_item("lab_key") else []
        if self.current_floor == 3:
            return [BUILDING_TOP_FLOOR]
        if self.current_floor == BUILDING_BOTTOM_FLOOR:
            return [2] if self.player.has_item("old_corridor_note") else []
        if self.current_floor == 2:
            return [BUILDING_BOTTOM_FLOOR]
        return []

    def _allowed_elevator_floors(self) -> list[int]:
        if self.current_floor == 3 and self.is_floor_power_restored():
            return [BUILDING_BOTTOM_FLOOR]
        return []

    def _confirm_floor_choice(self) -> None:
        if not self.floor_transition_options:
            self._clear_floor_transition()
            self.set_state(STATE_PLAYING)
            return
        if not (0 <= self.floor_choice_selected < len(self.floor_transition_options)):
            self.floor_choice_selected = 0
        target_floor = self.floor_transition_options[self.floor_choice_selected]
        if self.floor_transition_entry_kind == "elevator":
            self.audio.play("elevator_move", volume=0.75, cooldown=0.0)
        self.change_floor(target_floor, self.floor_transition_entry_kind, self.floor_transition_source_cell)

    def change_floor(self, target_floor: int, entry_kind: str = "", source_cell: tuple[int, int] | None = None) -> None:
        if target_floor < BUILDING_BOTTOM_FLOOR or target_floor > BUILDING_TOP_FLOOR or target_floor == self.current_floor:
            self._clear_floor_transition()
            self.set_state(STATE_PLAYING)
            return
        self._save_current_floor_map_state()
        self.current_floor = target_floor
        self._load_current_floor_map()
        entry_pose = self.game_map.entry_spawn_pose(entry_kind, source_cell) if entry_kind else None
        if entry_pose is not None:
            x, y, angle = entry_pose
        elif self.game_map.has_explicit_start_position:
            x, y = self.game_map.start_position
            angle = 0.0
        else:
            x, y, angle = self.game_map.exit_spawn_pose()
        self.player.x = x
        self.player.y = y
        self.player.angle = angle
        self.player.reset_vertical_look()
        self._bind_floor_systems()
        self._clear_floor_transition()
        self.set_state(STATE_PLAYING)
        self.set_message(f"你到了 {self.current_floor} 层。", 3.0)
        if entry_kind == "elevator":
            self.audio.play("elevator_arrive", volume=0.8, cooldown=0.0)

    def descend_floor(self) -> None:
        self.change_floor(max(BUILDING_BOTTOM_FLOOR, self.pending_floor), "exit")
