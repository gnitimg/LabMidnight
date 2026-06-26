"""UI rendering helpers."""

from __future__ import annotations

from pathlib import Path

import pygame

from src.ui.ending import FAILURE_TITLE, SUCCESS_TITLE
from src.settings import (
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PANEL,
    COLOR_PANEL_EDGE,
    COLOR_TEXT,
    COLOR_WARNING,
    COLOR_WHITE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


ITEM_NAMES = {
    "flashlight": "手电筒",
    "lab_key": "实验室钥匙",
    "note_a": "纸条 A",
    "note_b": "纸条 B",
    "fuse": "保险丝",
    "access_card": "门禁卡",
    "map": "实验楼平面图",
    "battery": "电池",
}

ITEM_DESCRIPTIONS = {
    "flashlight": "一只旧手电，电量不多，但总比什么都看不见好。",
    "lab_key": "实验室备用钥匙。",
    "note_a": "第二节课还没有结束。如果你听见点名，不要回答。",
    "note_b": "灯灭之后，配电室的门只认得黑板上的数字。",
    "fuse": "看起来正好能装进配电室的空槽里。",
    "access_card": "卡面上没有姓名，只有一串被刮花的编号。",
    "map": "四层平面图，有几处房间被红笔圈了出来。",
    "battery": "备用电池，已经自动给手电补充了电量。",
}


class UI:
    def __init__(self) -> None:
        self.font_cache: dict[tuple[int, bool], pygame.font.Font] = {}

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key in self.font_cache:
            return self.font_cache[key]

        # Avoid pygame.font.SysFont on Windows: some font registries contain
        # non-string values that can crash Pygame's system font scanner.
        font = self._load_font_file(size)
        if font is None:
            font = pygame.font.Font(None, size)
        self.font_cache[key] = font
        return font

    def _load_font_file(self, size: int) -> pygame.font.Font | None:
        font_paths = [
            Path("assets/fonts/msyh.ttc"),
            Path("assets/fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/msyh.ttf"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simsun.ttc"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
        for path in font_paths:
            if not path.exists():
                continue
            try:
                return pygame.font.Font(str(path), size)
            except (pygame.error, OSError, TypeError):
                continue
        return None

    def draw_text(
        self,
        surface: pygame.Surface,
        text: str,
        pos: tuple[int, int],
        size: int = 22,
        color: tuple[int, int, int] = COLOR_TEXT,
        bold: bool = False,
        center: bool = False,
    ) -> pygame.Rect:
        rendered = self.font(size, bold).render(text, True, color)
        rect = rendered.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        surface.blit(rendered, rect)
        return rect

    def draw_hud(self, surface: pygame.Surface, player, message: str, prompt: str, floor: int = 4) -> None:
        self._draw_bar(surface, 18, 16, "HP", player.hp, 100, (91, 153, 112))
        self._draw_bar(surface, 18, 44, "SAN", player.sanity, 100, (92, 143, 190))
        self._draw_bar(surface, 18, 72, "电量", player.flashlight_power, 100, (216, 184, 92))

        flashlight = "开" if player.flashlight_on and player.flashlight_power > 0 else "关"
        self.draw_text(surface, f"手电：{flashlight}", (18, 102), 19, COLOR_MUTED)
        self.draw_text(surface, f"{floor}F", (SCREEN_WIDTH - 58, 18), 25, COLOR_WARNING, bold=True)
        self.draw_text(surface, "W/S 前后  A/D 左右移动  鼠标视角  Space/左键交互  右键手电  B 背包  F2画质  ESC 暂停", (18, SCREEN_HEIGHT - 32), 18, COLOR_MUTED)

        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        pygame.draw.line(surface, (205, 218, 205), (cx - 6, cy), (cx + 6, cy), 1)
        pygame.draw.line(surface, (205, 218, 205), (cx, cy - 6), (cx, cy + 6), 1)

        if prompt:
            self._draw_center_panel(surface, prompt, SCREEN_HEIGHT - 96, COLOR_WARNING)
        elif message:
            self._draw_center_panel(surface, message, SCREEN_HEIGHT - 96, COLOR_TEXT)

    def _draw_bar(self, surface: pygame.Surface, x: int, y: int, label: str, value: float, maximum: float, color: tuple[int, int, int]) -> None:
        width, height = 180, 16
        self.draw_text(surface, label, (x, y - 2), 17, COLOR_TEXT, bold=True)
        back_rect = pygame.Rect(x + 54, y, width, height)
        pygame.draw.rect(surface, (23, 28, 28), back_rect)
        fill_width = int(width * max(0.0, min(1.0, value / maximum)))
        pygame.draw.rect(surface, color, (x + 54, y, fill_width, height))
        pygame.draw.rect(surface, COLOR_PANEL_EDGE, back_rect, 1)

    def _draw_center_panel(self, surface: pygame.Surface, text: str, y: int, color: tuple[int, int, int]) -> None:
        rendered = self.font(22, False).render(text, True, color)
        rect = rendered.get_rect(center=(SCREEN_WIDTH // 2, y))
        panel = rect.inflate(32, 18)
        pygame.draw.rect(surface, (9, 12, 13), panel, border_radius=6)
        pygame.draw.rect(surface, COLOR_PANEL_EDGE, panel, 1, border_radius=6)
        surface.blit(rendered, rect)

    def draw_menu(self, surface: pygame.Surface, selected: int, instructions: bool) -> None:
        surface.fill((7, 10, 11))
        self.draw_text(surface, "LabMidnight", (SCREEN_WIDTH // 2, 104), 58, COLOR_WHITE, bold=True, center=True)
        self.draw_text(surface, "加班累了是吗", (SCREEN_WIDTH // 2, 160), 28, COLOR_WARNING, center=True)
        self.draw_text(surface, "凌晨两点，实验楼停电。你只想回寝室。", (SCREEN_WIDTH // 2, 205), 22, COLOR_MUTED, center=True)

        if instructions:
            lines = [
                "操作说明",
                "W/S：前进/后退",
                "A/D：向左/向右移动",
                "鼠标移动：移动视角",
                "Space 或鼠标左键：交互、拾取、确认",
                "鼠标右键：开关手电筒",
                "B 或 I：背包",
                "F2：切换画质",
                "ESC：暂停或返回",
                "按 ESC 返回主菜单",
            ]
            top = 228
            for index, line in enumerate(lines):
                size = 28 if index == 0 else 22
                color = COLOR_WARNING if index == 0 else COLOR_TEXT
                self.draw_text(surface, line, (SCREEN_WIDTH // 2, top + index * 30), size, color, center=True)
            return

        options = ["开始游戏", "操作说明", "退出游戏"]
        for index, option in enumerate(options):
            y = 270 + index * 54
            color = COLOR_WARNING if index == selected else COLOR_TEXT
            prefix = "> " if index == selected else "  "
            self.draw_text(surface, prefix + option, (SCREEN_WIDTH // 2, y), 28, color, bold=index == selected, center=True)
        self.draw_text(surface, "↑/↓ 选择，Enter 或左键确认", (SCREEN_WIDTH // 2, 466), 19, COLOR_MUTED, center=True)

    def draw_pause(self, surface: pygame.Surface) -> None:
        self._overlay(surface, 170)
        self.draw_text(surface, "暂停", (SCREEN_WIDTH // 2, 190), 48, COLOR_WARNING, bold=True, center=True)
        self.draw_text(surface, "ESC 继续游戏", (SCREEN_WIDTH // 2, 258), 25, COLOR_TEXT, center=True)
        self.draw_text(surface, "R 重新开始", (SCREEN_WIDTH // 2, 300), 25, COLOR_TEXT, center=True)
        self.draw_text(surface, "Q 回到主菜单", (SCREEN_WIDTH // 2, 342), 25, COLOR_TEXT, center=True)

    def draw_floor_confirm(self, surface: pygame.Surface, title: str, options: list[int], selected: int) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 235))
        surface.blit(overlay, (0, 0))
        panel = pygame.Rect(SCREEN_WIDTH // 2 - 240, SCREEN_HEIGHT // 2 - 116, 480, 232)
        pygame.draw.rect(surface, COLOR_PANEL, panel, border_radius=8)
        pygame.draw.rect(surface, COLOR_PANEL_EDGE, panel, 1, border_radius=8)
        self.draw_text(surface, title, (SCREEN_WIDTH // 2, panel.y + 44), 30, COLOR_WARNING, bold=True, center=True)
        self.draw_text(surface, "请选择目的楼层", (SCREEN_WIDTH // 2, panel.y + 78), 21, COLOR_TEXT, center=True)

        button_width = 80 if len(options) >= 4 else 100 if len(options) == 3 else 118
        button_gap = 12 if len(options) >= 3 else 18
        total_width = button_width * len(options) + button_gap * (len(options) - 1)
        start_x = panel.centerx - total_width // 2
        for index, floor in enumerate(options):
            rect = pygame.Rect(start_x + index * (button_width + button_gap), panel.y + 128, button_width, 42)
            fill = (48, 58, 58) if index == selected else (22, 28, 29)
            pygame.draw.rect(surface, fill, rect, border_radius=5)
            pygame.draw.rect(surface, COLOR_WARNING if index == selected else COLOR_PANEL_EDGE, rect, 1, border_radius=5)
            self.draw_text(surface, str(floor), rect.center, 24, COLOR_TEXT if index != selected else COLOR_WARNING, bold=index == selected, center=True)

        self.draw_text(surface, "A/D 或方向键选择，数字键直选，Enter 确认", (SCREEN_WIDTH // 2, panel.bottom - 28), 18, COLOR_MUTED, center=True)

    def draw_inventory(self, surface: pygame.Surface, player) -> None:
        self._overlay(surface, 195)
        panel = pygame.Rect(120, 70, SCREEN_WIDTH - 240, SCREEN_HEIGHT - 140)
        pygame.draw.rect(surface, COLOR_PANEL, panel, border_radius=8)
        pygame.draw.rect(surface, COLOR_PANEL_EDGE, panel, 1, border_radius=8)
        self.draw_text(surface, "背包", (panel.x + 32, panel.y + 26), 34, COLOR_WARNING, bold=True)
        self.draw_text(surface, "B / I / ESC 返回", (panel.right - 190, panel.y + 34), 19, COLOR_MUTED)

        if not player.inventory:
            self.draw_text(surface, "什么都没有。", (panel.x + 34, panel.y + 92), 24, COLOR_MUTED)
            return

        y = panel.y + 88
        for item_id in sorted(player.inventory):
            name = ITEM_NAMES.get(item_id, item_id)
            desc = ITEM_DESCRIPTIONS.get(item_id, "")
            self.draw_text(surface, f"- {name}", (panel.x + 34, y), 23, COLOR_TEXT, bold=True)
            self.draw_text(surface, desc, (panel.x + 62, y + 28), 19, COLOR_MUTED)
            y += 66

    def draw_ending(self, surface: pygame.Surface, success: bool) -> None:
        if success:
            self._draw_success_scene(surface)
        else:
            self._draw_failure_scene(surface)

    def _draw_success_scene(self, surface: pygame.Surface) -> None:
        surface.fill((214, 221, 210))
        pygame.draw.rect(surface, (24, 31, 32), (0, 0, SCREEN_WIDTH, 92))
        pygame.draw.rect(surface, (54, 66, 67), (92, 108, 184, 154), border_radius=6)
        pygame.draw.rect(surface, (11, 16, 18), (108, 124, 152, 122), border_radius=4)
        pygame.draw.circle(surface, (238, 228, 166), (184, 184), 32)
        pygame.draw.rect(surface, (42, 47, 47), (332, 316, 372, 84), border_radius=8)
        pygame.draw.rect(surface, (98, 111, 105), (356, 278, 130, 52), border_radius=6)
        pygame.draw.rect(surface, (183, 168, 103), (554, 330, 108, 18), border_radius=9)
        pygame.draw.circle(surface, (244, 224, 132), (668, 338), 22)
        pygame.draw.line(surface, (244, 224, 132), (556, 339), (640, 339), 5)
        self.draw_text(surface, SUCCESS_TITLE, (SCREEN_WIDTH // 2, 64), 36, (36, 46, 42), bold=True, center=True)
        self.draw_text(surface, "按 Enter 回到主菜单，按 R 重新开始", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 44), 20, (70, 82, 78), center=True)

    def _draw_failure_scene(self, surface: pygame.Surface) -> None:
        surface.fill((3, 5, 6))
        pygame.draw.rect(surface, (18, 22, 23), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.draw.rect(surface, (215, 222, 206), (260, 92, 440, 214), border_radius=4)
        pygame.draw.rect(surface, (31, 39, 38), (284, 116, 392, 166), border_radius=2)
        pygame.draw.line(surface, (90, 126, 108), (320, 244), (390, 196), 2)
        pygame.draw.line(surface, (90, 126, 108), (390, 196), (452, 232), 2)
        pygame.draw.line(surface, (90, 126, 108), (452, 232), (526, 172), 2)
        pygame.draw.line(surface, (90, 126, 108), (526, 172), (616, 230), 2)
        pygame.draw.rect(surface, (74, 82, 75), (410, 284, 140, 10))
        pygame.draw.rect(surface, (22, 16, 14), (0, 408, SCREEN_WIDTH, 132))
        pygame.draw.rect(surface, (35, 25, 20), (340, 362, 300, 52), border_radius=5)
        pygame.draw.circle(surface, (11, 9, 8), (480, 348), 34)
        self.draw_text(surface, "LabMidnight", (480, 148), 28, (116, 162, 134), bold=True, center=True)
        self.draw_text(surface, FAILURE_TITLE, (SCREEN_WIDTH // 2, 58), 36, COLOR_WARNING, bold=True, center=True)
        self.draw_text(surface, "按 Enter 回到主菜单，按 R 重新开始", (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 44), 20, COLOR_MUTED, center=True)

    def _overlay(self, surface: pygame.Surface, alpha: int) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        surface.blit(overlay, (0, 0))
