from __future__ import annotations

import math

from src.settings import (
    CAMERA_HEIGHT_UNITS,
    CEILING_HEIGHT_UNITS,
    HALF_HEIGHT,
    RAY_NEAR_CLIP,
    SCREEN_HEIGHT,
    VERTICAL_PROJECTION,
)


class RendererProjectionMixin:
    def _horizon(self, player) -> int:
        pitch = self._player_view_pitch(player)
        raw_horizon = HALF_HEIGHT + VERTICAL_PROJECTION * math.tan(pitch)
        limit = SCREEN_HEIGHT * 20
        return int(max(-limit, min(limit, raw_horizon)))

    def _player_view_angle(self, player) -> float:
        view_angle = getattr(player, "view_angle", None)
        if callable(view_angle):
            return view_angle()
        return player.angle

    def _player_view_pitch(self, player) -> float:
        view_pitch = getattr(player, "view_pitch", None)
        if callable(view_pitch):
            return view_pitch()
        return 0.0

    def _view_basis(self, player) -> tuple[float, float, float, float, float, float, float]:
        yaw = self._player_view_angle(player)
        pitch = self._player_view_pitch(player)
        yaw_x = math.cos(yaw)
        yaw_y = math.sin(yaw)
        right_x = -yaw_y
        right_y = yaw_x
        pitch_cos = math.cos(pitch)
        pitch_sin = math.sin(pitch)
        forward_x = yaw_x * pitch_cos
        forward_y = yaw_y * pitch_cos
        up_x = -yaw_x * pitch_sin
        up_y = -yaw_y * pitch_sin
        return forward_x, forward_y, pitch_sin, right_x, right_y, up_x, up_y

    def _plane_row_hit(self, player, screen_y: float, *, is_ceiling: bool) -> tuple[float, float, float] | None:
        forward_x, forward_y, forward_z, _right_x, _right_y, up_x, up_y = self._view_basis(player)
        pitch = self._player_view_pitch(player)
        up_z = math.cos(pitch)
        vertical_offset = (HALF_HEIGHT - screen_y) / VERTICAL_PROJECTION
        ray_z = forward_z + vertical_offset * up_z
        plane_delta = CEILING_HEIGHT_UNITS - CAMERA_HEIGHT_UNITS if is_ceiling else -CAMERA_HEIGHT_UNITS
        if abs(ray_z) <= 1e-6:
            return None
        ray_scale = plane_delta / ray_z
        if ray_scale <= 0:
            return None
        base_x = forward_x + vertical_offset * up_x
        base_y = forward_y + vertical_offset * up_y
        row_distance = math.hypot(base_x * ray_scale, base_y * ray_scale)
        return ray_scale, base_x, base_y

    def _camera_space(self, x: float, y: float, player) -> tuple[float, float, float]:
        dx = x - player.x
        dy = y - player.y
        view_angle = self._player_view_angle(player)
        right = -dx * math.sin(view_angle) + dy * math.cos(view_angle)
        forward = dx * math.cos(view_angle) + dy * math.sin(view_angle)
        return right, 0.0, forward

    def _visible_wall_span(self, top_y: float, bottom_y: float) -> tuple[int, int] | None:
        if bottom_y <= top_y:
            return None
        visible_top = max(0, int(math.floor(top_y)))
        visible_bottom = min(SCREEN_HEIGHT, int(math.ceil(bottom_y)))
        if visible_bottom <= visible_top:
            return None
        return visible_top, visible_bottom - visible_top

    def _visible_wall_slice(self, top_y: float, bottom_y: float, texture_height: int) -> tuple[int, int, int, int] | None:
        span = self._visible_wall_span(top_y, bottom_y)
        if span is None or texture_height <= 0:
            return None
        visible_top, visible_height = span
        full_height = bottom_y - top_y
        source_top_ratio = (visible_top - top_y) / full_height
        source_bottom_ratio = (visible_top + visible_height - top_y) / full_height
        source_y = max(0, min(texture_height - 1, int(source_top_ratio * texture_height)))
        source_bottom = max(source_y + 1, min(texture_height, int(math.ceil(source_bottom_ratio * texture_height))))
        return visible_top, visible_height, source_y, source_bottom - source_y


