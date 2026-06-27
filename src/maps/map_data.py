"""Map layout and collision helpers."""

from __future__ import annotations

from src.maps.game_map_build import GameMapBuildMixin
from src.maps.game_map_collision import GameMapCollisionMixin
from src.maps.game_map_doors import GameMapDoorMixin
from src.maps.game_map_spawn import GameMapSpawnMixin
from src.maps.map_objects import MapObject
from src.maps.map_paths import layout_path_for_floor, load_initial_player_config
from src.resources.object_assets import load_object_specs
from src.settings import BUILDING_TOP_FLOOR, TILE_WALL


class GameMap(GameMapBuildMixin, GameMapDoorMixin, GameMapSpawnMixin, GameMapCollisionMixin):
    """A compact fourth-floor slice of the lab building."""

    def __init__(self, floor: int = BUILDING_TOP_FLOOR) -> None:
        self.floor = floor
        self.width = 34
        self.height = 16
        self.grid = [[TILE_WALL for _ in range(self.width)] for _ in range(self.height)]
        self.open_doors: set[tuple[int, int]] = set()
        self.door_open_progress: dict[tuple[int, int], float] = {}
        self.picked_objects: set[tuple[int, int]] = set()
        self.objects: dict[tuple[int, int], MapObject] = {}
        self.door_roles: dict[tuple[int, int], str] = {}
        self.door_groups: dict[tuple[int, int], frozenset[tuple[int, int]]] = {}
        self.object_specs = load_object_specs()
        self.start_position = (3.0, 3.0)
        self.has_explicit_start_position = False
        layout_path = layout_path_for_floor(floor)
        if layout_path.exists():
            self._build_from_layout(layout_path)
        else:
            self._build_layout()
        self._hydrate_existing_objects()
        self._load_object_metadata()
        self._normalize_wall_facing_objects()
        self._apply_random_pickup_drops()
        self._index_door_groups()
