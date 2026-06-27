from __future__ import annotations

import math

import pygame

from src.rendering.renderer_config import (
    DEFAULT_OCCLUSION_SLACK,
    OBJECT_STABLE_VERTICAL_DISTANCE,
    SMALL_OBJECT_TOP_HIDE_DISTANCE,
    SMALL_OBJECT_TOP_MAX_HEIGHT,
    THIN_PANEL_NEAR_CLIP,
    THIN_PANEL_OCCLUSION_SLACK,
    THIN_PANEL_RENDER_OFFSET,
    TOP_FACE_NEAR_CLIP,
    WALL_PANEL_OBJECT_IDS,
    WORLD_PANEL_MIN_VERTICAL_DISTANCE,
)
from src.resources.asset_manager import TEXTURE_ELEVATOR
from src.settings import (
    CAMERA_HEIGHT_UNITS,
    CEILING_HEIGHT_UNITS,
    DOOR_PANEL_NEAR_CLIP,
    HALF_WIDTH,
    NUM_RAYS,
    RAY_NEAR_CLIP,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_WALL,
    VERTICAL_PROJECTION,
    VERTICAL_UNITS_PER_TILE,
)


class RendererObjectMixin:
    def _draw_objects(self, player, elapsed: float, horizon: int, depth_buffer: list[float]) -> None:
        drawables: list[tuple[float, str, tuple]] = []
        object_depth_buffer = depth_buffer[:]
        for anchor, obj in self.game_map.objects.items():
            if anchor in self.game_map.picked_objects:
                continue
            x0, y0, x1, y1 = self.game_map.object_bounds(anchor, obj)
            bottom_z = obj.placement_height * VERTICAL_UNITS_PER_TILE
            asset_id = obj.asset_id or obj.object_id
            object_height = self._object_height_units(obj)
            object_top_z = bottom_z + object_height
            if object_top_z <= bottom_z:
                continue

            thin_panel = self._object_is_thin_panel(obj, x0, y0, x1, y1)
            for face, normal, p0, p1, side_light in self._object_face_data(anchor, obj):
                face_span = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
                if thin_panel and face_span <= 0.15:
                    continue
                center_x = (p0[0] + p1[0]) * 0.5
                center_y = (p0[1] + p1[1]) * 0.5
                to_player_x = player.x - center_x
                to_player_y = player.y - center_y
                if to_player_x * normal[0] + to_player_y * normal[1] <= 0:
                    continue
                if thin_panel:
                    p0 = (
                        p0[0] + normal[0] * THIN_PANEL_RENDER_OFFSET,
                        p0[1] + normal[1] * THIN_PANEL_RENDER_OFFSET,
                    )
                    p1 = (
                        p1[0] + normal[0] * THIN_PANEL_RENDER_OFFSET,
                        p1[1] + normal[1] * THIN_PANEL_RENDER_OFFSET,
                    )
                texture = self._object_face_texture(asset_id, face)
                distance_key = (center_x - player.x) ** 2 + (center_y - player.y) ** 2
                occlusion_slack = THIN_PANEL_OCCLUSION_SLACK if thin_panel else DEFAULT_OCCLUSION_SLACK
                near_clip = THIN_PANEL_NEAR_CLIP if thin_panel else DOOR_PANEL_NEAR_CLIP
                stable_vertical = thin_panel or distance_key <= OBJECT_STABLE_VERTICAL_DISTANCE * OBJECT_STABLE_VERTICAL_DISTANCE
                drawables.append((distance_key, "panel", (texture, p0, p1, bottom_z, object_top_z, side_light, occlusion_slack, near_clip, stable_vertical)))

            if not thin_panel:
                top_texture = self._object_face_texture(asset_id, "top")
                top_points = [(x, y, object_top_z) for x, y in self._object_top_points(anchor, obj)]
                center_x = sum(point[0] for point in top_points) / len(top_points)
                center_y = sum(point[1] for point in top_points) / len(top_points)
                top_distance_key = (center_x - player.x) ** 2 + (center_y - player.y) ** 2
                if not self._hide_close_small_object_top(obj, top_distance_key):
                    drawables.append((top_distance_key, "top", (top_texture, top_points, 0.82)))

        for _, kind, payload in sorted(drawables, key=lambda item: item[0], reverse=True):
            if kind == "top":
                texture, points, side_light = payload
                self._draw_world_top(texture, points, player, elapsed, horizon, depth_buffer, side_light, object_depth_buffer)
            else:
                texture, p0, p1, bottom_z, top_z, side_light, occlusion_slack, near_clip, stable_vertical = payload
                self._draw_world_panel(
                    texture,
                    TILE_WALL,
                    p0,
                    p1,
                    player,
                    elapsed,
                    horizon,
                    depth_buffer,
                    bottom_z=bottom_z,
                    top_z=top_z,
                    side_light=side_light,
                    occlusion_slack=occlusion_slack,
                    near_clip=near_clip,
                    stable_vertical=stable_vertical,
                    object_depth_buffer=object_depth_buffer,
                )

    def _object_height_units(self, obj) -> float:
        return max(0.05, obj.height) * VERTICAL_UNITS_PER_TILE

    def _hide_close_small_object_top(self, obj, distance_key: float) -> bool:
        if obj.solid:
            return False
        if self._object_height_units(obj) > SMALL_OBJECT_TOP_MAX_HEIGHT:
            return False
        return distance_key <= SMALL_OBJECT_TOP_HIDE_DISTANCE * SMALL_OBJECT_TOP_HIDE_DISTANCE

    def _object_is_thin_panel(self, obj, x0: float, y0: float, x1: float, y1: float) -> bool:
        footprint_width = max(0.0, x1 - x0)
        footprint_depth = max(0.0, y1 - y0)
        thin_side = min(footprint_width, footprint_depth)
        long_side = max(footprint_width, footprint_depth)
        return thin_side <= 0.15 and long_side >= 1.0 and (obj.placement_height > 0.0 or obj.object_id in WALL_PANEL_OBJECT_IDS)

    def _object_face_data(
        self,
        anchor: tuple[int, int],
        obj,
    ) -> list[tuple[str, tuple[float, float], tuple[float, float], tuple[float, float], float]]:
        length = max(0.05, obj.length)
        width = max(0.05, obj.width)
        local_faces = [
            ("front", (0.0, 1.0), (length, width), (0.0, width), 0.92),
            ("back", (0.0, -1.0), (0.0, 0.0), (length, 0.0), 0.70),
            ("left", (-1.0, 0.0), (0.0, width), (0.0, 0.0), 0.78),
            ("right", (1.0, 0.0), (length, 0.0), (length, width), 0.86),
        ]
        return [
            (
                face,
                self._object_local_vector_to_world(normal[0], normal[1], obj.rotation),
                self._object_local_point_to_world(anchor, length, width, p0[0], p0[1], obj.rotation),
                self._object_local_point_to_world(anchor, length, width, p1[0], p1[1], obj.rotation),
                side_light,
            )
            for face, normal, p0, p1, side_light in local_faces
        ]

    def _object_top_points(self, anchor: tuple[int, int], obj) -> list[tuple[float, float]]:
        length = max(0.05, obj.length)
        width = max(0.05, obj.width)
        return [
            self._object_local_point_to_world(anchor, length, width, 0.0, 0.0, obj.rotation),
            self._object_local_point_to_world(anchor, length, width, length, 0.0, obj.rotation),
            self._object_local_point_to_world(anchor, length, width, length, width, obj.rotation),
            self._object_local_point_to_world(anchor, length, width, 0.0, width, obj.rotation),
        ]

    def _object_local_point_to_world(
        self,
        anchor: tuple[int, int],
        length: float,
        width: float,
        local_x: float,
        local_y: float,
        rotation: int,
    ) -> tuple[float, float]:
        x, y = anchor
        quarter_turn = (rotation // 90) % 4
        if quarter_turn == 1:
            return x + local_y, y + length - local_x
        if quarter_turn == 2:
            return x + length - local_x, y + width - local_y
        if quarter_turn == 3:
            return x + width - local_y, y + local_x
        return x + local_x, y + local_y

    def _object_local_vector_to_world(self, x: float, y: float, rotation: int) -> tuple[float, float]:
        quarter_turn = (rotation // 90) % 4
        if quarter_turn == 1:
            return y, -x
        if quarter_turn == 2:
            return -x, -y
        if quarter_turn == 3:
            return -y, x
        return x, y

    def _object_face_texture(self, object_id: str, face: str) -> pygame.Surface:
        texture = self.textures.for_object_face(object_id, face)
        if texture is not None:
            return texture
        if object_id == "elevator" and face == "front":
            elevator_texture = self.textures.get(TEXTURE_ELEVATOR)
            if elevator_texture is not None:
                return elevator_texture
        key = (object_id, face)
        cached = self._fallback_object_texture_cache.get(key)
        if cached is not None:
            return cached
        base = sum(ord(ch) for ch in object_id + face)
        color = (90 + base % 45, 82 + (base // 3) % 45, 68 + (base // 7) % 45)
        surface = pygame.Surface((48, 48)).convert()
        surface.fill(color)
        pygame.draw.rect(surface, tuple(max(0, channel - 28) for channel in color), surface.get_rect(), 2)
        self._fallback_object_texture_cache[key] = surface
        return surface

    def _draw_world_top(
        self,
        texture: pygame.Surface,
        points: list[tuple[float, float, float]],
        player,
        elapsed: float,
        horizon: int,
        depth_buffer: list[float],
        side_light: float,
        object_depth_buffer: list[float] | None = None,
    ) -> None:
        if not points:
            return
        near = TOP_FACE_NEAR_CLIP
        camera_points: list[tuple[float, float]] = []
        for x, y, _z in points:
            right, _unused, forward = self._camera_space(x, y, player)
            camera_points.append((right, forward))
        clipped_points = self._clip_camera_polygon_near(camera_points, near)
        if len(clipped_points) < 3:
            return

        top_z = points[0][2]
        projected: list[tuple[float, float, float]] = []
        for right, forward in clipped_points:
            screen_x = HALF_WIDTH + right / forward * VERTICAL_PROJECTION
            screen_y = horizon - VERTICAL_PROJECTION * (top_z - CAMERA_HEIGHT_UNITS) / forward
            projected.append((screen_x, screen_y, forward))

        min_x = max(0, int(math.floor(min(point[0] for point in projected))))
        max_x = min(SCREEN_WIDTH - 1, int(math.ceil(max(point[0] for point in projected))))
        min_y = max(0, int(math.floor(min(point[1] for point in projected))))
        max_y = min(SCREEN_HEIGHT - 1, int(math.ceil(max(point[1] for point in projected))))
        if max_x <= min_x or max_y <= min_y:
            return
        center_distance = sum(point[2] for point in projected) / len(projected)
        center_ray = min(NUM_RAYS - 1, max(0, int(((min_x + max_x) * 0.5) * NUM_RAYS / SCREEN_WIDTH)))
        occlusion_buffer = object_depth_buffer if object_depth_buffer is not None else depth_buffer
        if center_distance > occlusion_buffer[center_ray] + 0.04:
            return

        target = pygame.Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
        patch = pygame.transform.smoothscale(texture, target.size).convert_alpha()
        shade = self._shade_factor(center_distance, self._player_view_angle(player), player, elapsed) * side_light
        shade_value = max(0, min(255, int(255 * min(1.0, shade))))
        patch.fill((shade_value, shade_value, shade_value, 255), special_flags=pygame.BLEND_RGBA_MULT)
        mask = pygame.Surface(target.size, pygame.SRCALPHA)
        polygon = [(int(x - target.x), int(y - target.y)) for x, y, _forward in projected]
        pygame.draw.polygon(mask, (255, 255, 255, 255), polygon)
        patch.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if object_depth_buffer is None:
            self.screen.blit(patch, target)
            return

        visible_ranges: list[tuple[int, int]] = []
        range_start: int | None = None
        for screen_x in range(target.left, target.right):
            ray_index = min(NUM_RAYS - 1, max(0, int(screen_x * NUM_RAYS / SCREEN_WIDTH)))
            distance = self._projected_polygon_column_depth(projected, screen_x, center_distance)
            if distance <= object_depth_buffer[ray_index] + 0.04:
                object_depth_buffer[ray_index] = min(object_depth_buffer[ray_index], distance)
                if range_start is None:
                    range_start = screen_x
            elif range_start is not None:
                visible_ranges.append((range_start, screen_x))
                range_start = None
        if range_start is not None:
            visible_ranges.append((range_start, target.right))

        for start_x, end_x in visible_ranges:
            source = pygame.Rect(start_x - target.x, 0, end_x - start_x, target.height)
            self.screen.blit(patch, (start_x, target.y), source)

    def _projected_polygon_column_depth(
        self,
        projected: list[tuple[float, float, float]],
        screen_x: float,
        fallback: float,
    ) -> float:
        intersections: list[float] = []
        previous = projected[-1]
        for current in projected:
            x0, _y0, z0 = previous
            x1, _y1, z1 = current
            if abs(x1 - x0) < 1e-6:
                if abs(screen_x - x0) < 0.5:
                    intersections.extend((z0, z1))
            elif min(x0, x1) <= screen_x <= max(x0, x1):
                t = (screen_x - x0) / (x1 - x0)
                intersections.append(z0 + (z1 - z0) * t)
            previous = current
        if not intersections:
            return fallback
        return max(RAY_NEAR_CLIP, min(intersections))

    def _clip_camera_polygon_near(self, points: list[tuple[float, float]], near: float) -> list[tuple[float, float]]:
        if not points:
            return []

        clipped: list[tuple[float, float]] = []
        previous = points[-1]
        previous_inside = previous[1] >= near
        for current in points:
            current_inside = current[1] >= near
            if current_inside != previous_inside:
                delta_forward = current[1] - previous[1]
                if abs(delta_forward) > 1e-8:
                    t = (near - previous[1]) / delta_forward
                    right = previous[0] + (current[0] - previous[0]) * t
                    clipped.append((right, near))
            if current_inside:
                clipped.append(current)
            previous = current
            previous_inside = current_inside
        return clipped

    def _draw_world_panel(
        self,
        texture: pygame.Surface,
        tile: int,
        p0: tuple[float, float],
        p1: tuple[float, float],
        player,
        elapsed: float,
        horizon: int,
        depth_buffer: list[float],
        *,
        texture_start: float = 0.0,
        texture_span: float = 1.0,
        bottom_z: float = 0.0,
        top_z: float = CEILING_HEIGHT_UNITS,
        side_light: float = 1.0,
        occlusion_slack: float = DEFAULT_OCCLUSION_SLACK,
        near_clip: float = DOOR_PANEL_NEAR_CLIP,
        stable_vertical: bool = False,
        object_depth_buffer: list[float] | None = None,
    ) -> None:
        ax, ay, az = self._camera_space(p0[0], p0[1], player)
        bx, by, bz = self._camera_space(p1[0], p1[1], player)
        texture_u0 = max(0.0, min(1.0, texture_start))
        texture_u1 = max(0.0, min(1.0, texture_start + texture_span))
        near = near_clip
        if az <= near and bz <= near:
            return
        if az <= near:
            t = (near - az) / (bz - az)
            ax = ax + (bx - ax) * t
            texture_u0 = texture_u0 + (texture_u1 - texture_u0) * t
            az = near
        elif bz <= near:
            t = (near - bz) / (az - bz)
            bx = bx + (ax - bx) * t
            texture_u1 = texture_u1 + (texture_u0 - texture_u1) * t
            bz = near

        sx0 = HALF_WIDTH + ax / az * VERTICAL_PROJECTION
        sx1 = HALF_WIDTH + bx / bz * VERTICAL_PROJECTION
        if abs(sx1 - sx0) < 1.0:
            return
        if sx0 > sx1:
            sx0, sx1 = sx1, sx0
            az, bz = bz, az
            texture_u0, texture_u1 = texture_u1, texture_u0

        vertical_distance = max(RAY_NEAR_CLIP, (az + bz) * 0.5) if stable_vertical else None

        start_x = max(0, int(math.floor(sx0)))
        end_x = min(SCREEN_WIDTH - 1, int(math.ceil(sx1)))
        if end_x < 0 or start_x >= SCREEN_WIDTH:
            return

        texture_width, texture_height = texture.get_size()
        span = max(1.0, sx1 - sx0)
        inv_z0 = 1.0 / max(RAY_NEAR_CLIP, az)
        inv_z1 = 1.0 / max(RAY_NEAR_CLIP, bz)
        u_over_z0 = texture_u0 * inv_z0
        u_over_z1 = texture_u1 * inv_z1
        occlusion_buffer = object_depth_buffer if object_depth_buffer is not None else depth_buffer
        for screen_x in range(start_x, end_x + 1):
            t = (screen_x - sx0) / span
            if not 0.0 <= t <= 1.0:
                continue
            inv_z = inv_z0 + (inv_z1 - inv_z0) * t
            if inv_z <= 1e-6:
                continue
            distance = max(RAY_NEAR_CLIP, 1.0 / inv_z)
            ray_index = min(NUM_RAYS - 1, max(0, int(screen_x * NUM_RAYS / SCREEN_WIDTH)))
            if distance > occlusion_buffer[ray_index] + occlusion_slack:
                continue

            height_distance = vertical_distance if vertical_distance is not None else distance
            height_distance = max(WORLD_PANEL_MIN_VERTICAL_DISTANCE, height_distance)
            top_y = horizon - VERTICAL_PROJECTION * (top_z - CAMERA_HEIGHT_UNITS) / height_distance
            bottom_y = horizon - VERTICAL_PROJECTION * (bottom_z - CAMERA_HEIGHT_UNITS) / height_distance
            texture_u = (u_over_z0 + (u_over_z1 - u_over_z0) * t) / inv_z
            texture_x = max(0, min(texture_width - 1, int(texture_u * texture_width)))
            slice_info = self._visible_wall_slice(top_y, bottom_y, texture_height)
            if slice_info is None:
                continue
            visible_top, visible_height, source_y, source_height = slice_info
            source = pygame.Rect(texture_x, source_y, 1, source_height)
            column = texture.subsurface(source)
            column = pygame.transform.scale(column, (2, visible_height))
            shade = self._shade_factor(distance, self._player_view_angle(player), player, elapsed) * side_light
            shade_value = max(0, min(255, int(255 * min(1.0, shade))))
            if column.get_flags() & pygame.SRCALPHA:
                column.fill((shade_value, shade_value, shade_value, 255), special_flags=pygame.BLEND_RGBA_MULT)
            else:
                column.fill((shade_value, shade_value, shade_value), special_flags=pygame.BLEND_RGB_MULT)
            self.screen.blit(column, (screen_x, visible_top))
            if object_depth_buffer is not None:
                object_depth_buffer[ray_index] = min(object_depth_buffer[ray_index], distance)
