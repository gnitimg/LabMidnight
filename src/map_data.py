"""Map layout and collision helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .settings import (
    DOOR_TILES,
    PLAYER_RADIUS,
    TILE_CLASSROOM_DOOR,
    TILE_DOOR,
    TILE_EMPTY,
    TILE_EXIT_DOOR,
    TILE_LAB_DOOR,
    TILE_POWER_DOOR,
    TILE_SERVER_DOOR,
    TILE_WALL,
)


@dataclass(frozen=True)
class MapObject:
    object_id: str
    name: str
    prompt: str
    description: str = ""


class GameMap:
    """A compact fourth-floor slice of the lab building."""

    def __init__(self) -> None:
        self.width = 24
        self.height = 18
        self.grid = [[TILE_WALL for _ in range(self.width)] for _ in range(self.height)]
        self.open_doors: set[tuple[int, int]] = set()
        self.picked_objects: set[tuple[int, int]] = set()
        self.objects: dict[tuple[int, int], MapObject] = {}
        self._build_layout()

    def _build_layout(self) -> None:
        self._carve_rect(1, 1, 6, 5)      # Initial lab
        self._carve_rect(6, 4, 12, 4)     # Short hall from lab to cross hallway
        self._carve_rect(10, 1, 12, 16)   # Main vertical hallway
        self._carve_rect(1, 7, 22, 9)     # Main corridor
        self._carve_rect(13, 1, 20, 5)    # Abnormal classroom
        self._carve_rect(1, 10, 5, 15)    # Security room
        self._carve_rect(5, 12, 12, 12)   # Side branch to security room
        self._carve_rect(7, 11, 11, 15)   # Power room
        self._carve_rect(13, 11, 17, 15)  # Server room
        self._carve_rect(17, 12, 19, 12)  # Branch to exit
        self._carve_rect(19, 11, 22, 15)  # Exit area

        self._set_tile(6, 4, TILE_LAB_DOOR)
        self._set_tile(13, 4, TILE_CLASSROOM_DOOR)
        self._set_tile(5, 12, TILE_DOOR)
        self._set_tile(9, 10, TILE_POWER_DOOR)
        self._set_tile(13, 12, TILE_SERVER_DOOR)
        self._set_tile(19, 12, TILE_EXIT_DOOR)

        self.objects[(3, 3)] = MapObject(
            "lab_desk",
            "实验桌",
            "按 Space 检查实验桌",
            "电脑还亮着，桌上压着一只旧手电和备用钥匙。",
        )
        self.objects[(17, 3)] = MapObject(
            "blackboard",
            "异常黑板",
            "按 Space 检查黑板",
            "第二节课还没有结束。02:00。第 4 组，进度未完成。",
        )
        self.objects[(16, 4)] = MapObject(
            "lectern",
            "讲台",
            "按 Space 检查讲台",
            "讲台上有一张纸条，边缘像被电流烧焦。",
        )
        self.objects[(3, 12)] = MapObject(
            "security_desk",
            "值班桌",
            "按 Space 检查值班桌",
            "值班记录停在凌晨两点，之后每一行都是同一个时间。",
        )
        self.objects[(4, 14)] = MapObject(
            "fuse_cabinet",
            "工具柜",
            "按 Space 打开工具柜",
            "柜子里放着一枚还能用的保险丝。",
        )
        self.objects[(8, 8)] = MapObject(
            "battery",
            "备用电池",
            "按 Space 拾取电池",
            "地上有一节备用电池，外壳有些磨损。",
        )
        self.objects[(9, 14)] = MapObject(
            "power_box",
            "配电箱",
            "按 Space 检查配电箱",
            "配电箱里缺了一枚保险丝。",
        )
        self.objects[(15, 13)] = MapObject(
            "server_terminal",
            "机房终端",
            "按 Space 检查机房终端",
            "屏幕显示：LabMidnight.map，出口状态等待确认。",
        )
        self.objects[(21, 13)] = MapObject(
            "exit_panel",
            "出口门禁",
            "按 Space 使用门禁",
            "门禁灯闪着红光，像是在等最后一次确认。",
        )

    def _carve_rect(self, x1: int, y1: int, x2: int, y2: int) -> None:
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self._set_tile(x, y, TILE_EMPTY)

    def _set_tile(self, x: int, y: int, tile: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = tile

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return TILE_WALL
        return self.grid[y][x]

    def is_door(self, x: int, y: int) -> bool:
        return self.tile_at(x, y) in DOOR_TILES

    def is_open_door(self, x: int, y: int) -> bool:
        return (x, y) in self.open_doors

    def open_door(self, x: int, y: int) -> None:
        if self.is_door(x, y):
            self.open_doors.add((x, y))

    def is_solid_cell(self, x: int, y: int) -> bool:
        tile = self.tile_at(x, y)
        if tile == TILE_WALL:
            return True
        if tile in DOOR_TILES and not self.is_open_door(x, y):
            return True
        return False

    def can_move_to(self, x: float, y: float) -> bool:
        checks: Iterable[tuple[float, float]] = (
            (x, y),
            (x + PLAYER_RADIUS, y),
            (x - PLAYER_RADIUS, y),
            (x, y + PLAYER_RADIUS),
            (x, y - PLAYER_RADIUS),
        )
        for check_x, check_y in checks:
            if self.is_solid_cell(int(check_x), int(check_y)):
                return False
        return True

    def object_at(self, x: int, y: int) -> MapObject | None:
        if (x, y) in self.picked_objects:
            return None
        return self.objects.get((x, y))

    def remove_object(self, x: int, y: int) -> None:
        self.picked_objects.add((x, y))

    def region_at(self, x: float, y: float) -> str:
        ix, iy = int(x), int(y)
        if 1 <= ix <= 6 and 1 <= iy <= 5:
            return "lab"
        if 13 <= ix <= 20 and 1 <= iy <= 5:
            return "classroom"
        if 1 <= ix <= 5 and 10 <= iy <= 15:
            return "security"
        if 7 <= ix <= 11 and 11 <= iy <= 15:
            return "power"
        if 13 <= ix <= 17 and 11 <= iy <= 15:
            return "server"
        if 19 <= ix <= 22 and 11 <= iy <= 15:
            return "exit"
        return "corridor"
