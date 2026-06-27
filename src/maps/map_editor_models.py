"""Map editor data models."""

from __future__ import annotations

from dataclasses import dataclass

from src.maps.map_editor_config import ELEMENT_STORY, LEGACY_OBJECT_IDS


@dataclass
class Room:
    room_id: int
    x: int
    y: int
    w: int
    h: int
    name: str
    number: str

    def contains(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h

    def handle_cell(self) -> tuple[int, int]:
        return self.x + self.w - 1, self.y + self.h - 1


@dataclass
class ObjectPlacement:
    object_id: str
    rotation: int = 0
    length: float | None = None
    width: float | None = None
    height: float | None = None
    placement_height: float | None = None
    element_type: str = ELEMENT_STORY
    pickup_item: str = ""
    pickup_flag: str = ""
    interaction_prompt: str = ""
    interaction_message: str = ""
    required_item: str = ""
    required_flag: str = ""
    failure_message: str = ""
    remove_on_pickup: bool = False
    random_drop: bool = False
    drop_count: int = 1
    is_trigger: bool = False
    trigger_id: str = ""
    trigger_once: bool = True
    resource_role: str = ""

    def label_char(self) -> str:
        return self.object_id if self.object_id in LEGACY_OBJECT_IDS else "O"


