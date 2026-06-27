"""Immersive ending video playback with safe static-scene fallback."""

from __future__ import annotations

import random
import time
from pathlib import Path

import pygame

from src.settings import SCREEN_HEIGHT, SCREEN_WIDTH

try:  # OpenCV is optional; missing decoders must not break the game.
    import cv2
except ImportError:  # pragma: no cover - depends on the local environment.
    cv2 = None


FAILURE_BLACKEN_SECONDS = 1.2
FAILURE_LAST_FRAME_HOLD_SECONDS = 4.0
FAILURE_FADE_OUT_SECONDS = 1.0


class EndingVideoPlayer:
    """Draw full-screen ending videos without exposing video-player UI."""

    def __init__(self) -> None:
        self.paths = {
            True: Path("assets/videos/successful.mp4"),
            False: Path("assets/videos/defeat.mp4"),
        }
        self._captures: dict[bool, object] = {}
        self._frame_intervals: dict[bool, float] = {}
        self._current_success: bool | None = None
        self._next_frame_at = 0.0
        self._cached_frame: pygame.Surface | None = None
        self._last_frame: pygame.Surface | None = None
        self._sequence_started_at = 0.0
        self._failure_video_finished_at: float | None = None
        self._failure_ready_for_input = False
        self._failure_fallback_active = False
        self._warned: set[str] = set()
        self._vignette = self._build_vignette()
        self._grain = self._build_grain()

    def reset(self, success: bool) -> None:
        self._current_success = success
        self._next_frame_at = 0.0
        self._cached_frame = None
        self._last_frame = None
        self._sequence_started_at = time.monotonic()
        self._failure_video_finished_at = None
        self._failure_ready_for_input = success
        self._failure_fallback_active = False
        capture = self._captures.get(success)
        if capture is not None:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def draw(self, surface: pygame.Surface, success: bool) -> bool:
        if self._current_success is not success:
            self.reset(success)

        if not success:
            return self._draw_failure_sequence(surface)
        return self._draw_looping_video(surface, success)

    def accepts_input(self, success: bool) -> bool:
        if success:
            return True
        if cv2 is None or not self.paths[False].exists():
            return True
        return self._failure_ready_for_input or self._failure_fallback_active

    def _draw_looping_video(self, surface: pygame.Surface, success: bool) -> bool:
        capture = self._capture_for(success)
        if capture is None:
            return False

        now = time.monotonic()
        if self._cached_frame is None or now >= self._next_frame_at:
            frame_surface = self._read_frame(success, capture)
            if frame_surface is None:
                return False
            self._cached_frame = frame_surface
            self._next_frame_at = now + self._frame_intervals.get(success, 1.0 / 30.0)

        surface.blit(self._cached_frame, (0, 0))
        surface.blit(self._vignette, (0, 0))
        surface.blit(self._grain, (0, 0))
        return True

    def _draw_failure_sequence(self, surface: pygame.Surface) -> bool:
        now = time.monotonic()
        elapsed = now - self._sequence_started_at
        if elapsed < FAILURE_BLACKEN_SECONDS:
            self._draw_black_overlay(surface, int(255 * self._smoothstep(elapsed / FAILURE_BLACKEN_SECONDS)))
            return True

        capture = self._capture_for(False)
        if capture is None:
            self._failure_fallback_active = True
            self._failure_ready_for_input = True
            return False

        if self._failure_video_finished_at is None:
            if self._cached_frame is None or now >= self._next_frame_at:
                frame_surface = self._read_frame_once(False, capture)
                if frame_surface is None:
                    self._failure_video_finished_at = now
                else:
                    self._cached_frame = frame_surface
                    self._last_frame = frame_surface
                    self._next_frame_at = now + self._frame_intervals.get(False, 1.0 / 30.0)
            if self._cached_frame is None:
                surface.fill((0, 0, 0))
            else:
                self._draw_immersive_frame(surface, self._cached_frame)
            return True

        hold_elapsed = now - self._failure_video_finished_at
        if self._last_frame is not None and hold_elapsed < FAILURE_LAST_FRAME_HOLD_SECONDS + FAILURE_FADE_OUT_SECONDS:
            self._draw_immersive_frame(surface, self._last_frame)
            if hold_elapsed >= FAILURE_LAST_FRAME_HOLD_SECONDS:
                fade = (hold_elapsed - FAILURE_LAST_FRAME_HOLD_SECONDS) / FAILURE_FADE_OUT_SECONDS
                self._draw_black_overlay(surface, int(255 * self._smoothstep(fade)))
            return True

        surface.fill((0, 0, 0))
        self._failure_ready_for_input = True
        return True

    def _draw_immersive_frame(self, surface: pygame.Surface, frame: pygame.Surface) -> None:
        surface.blit(frame, (0, 0))
        surface.blit(self._vignette, (0, 0))
        surface.blit(self._grain, (0, 0))

    def _capture_for(self, success: bool):
        if cv2 is None:
            self._warn_once("cv2", "[video warning] OpenCV is unavailable; using static ending scene.")
            return None

        if success in self._captures:
            return self._captures[success]

        path = self.paths[success]
        if not path.exists():
            self._warn_once(str(path), f"[video warning] missing ending video: {path}")
            return None

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            self._warn_once(str(path), f"[video warning] unable to open ending video: {path}")
            return None

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        if fps <= 1.0 or fps > 144.0:
            fps = 30.0
        self._captures[success] = capture
        self._frame_intervals[success] = 1.0 / fps
        return capture

    def _read_frame_once(self, success: bool, capture) -> pygame.Surface | None:
        ok, frame = capture.read()
        if not ok or frame is None:
            return None
        return self._frame_to_surface(frame)

    def _read_frame(self, success: bool, capture) -> pygame.Surface | None:
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = capture.read()
            if not ok or frame is None:
                path = self.paths[success]
                self._warn_once(str(path), f"[video warning] unable to decode ending video frame: {path}")
                return None

        return self._frame_to_surface(frame)

    def _frame_to_surface(self, frame) -> pygame.Surface:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        source = pygame.image.frombuffer(rgb.tobytes(), (rgb.shape[1], rgb.shape[0]), "RGB").copy()
        return self._cover_scale(source)

    def _cover_scale(self, source: pygame.Surface) -> pygame.Surface:
        source_width, source_height = source.get_size()
        if source_width <= 0 or source_height <= 0:
            return pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        scale = max(SCREEN_WIDTH / source_width, SCREEN_HEIGHT / source_height)
        scaled_size = (max(1, int(source_width * scale)), max(1, int(source_height * scale)))
        scaled = pygame.transform.smoothscale(source, scaled_size)
        crop = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        crop.center = scaled.get_rect().center
        return scaled.subsurface(crop).copy()

    def _build_vignette(self) -> pygame.Surface:
        vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        center_x = SCREEN_WIDTH * 0.5
        center_y = SCREEN_HEIGHT * 0.48
        max_distance = (center_x * center_x + center_y * center_y) ** 0.5
        step = 8
        for y in range(0, SCREEN_HEIGHT, step):
            for x in range(0, SCREEN_WIDTH, step):
                dx = x + step * 0.5 - center_x
                dy = y + step * 0.5 - center_y
                distance = min(1.0, (dx * dx + dy * dy) ** 0.5 / max_distance)
                alpha = int(max(0.0, distance - 0.38) ** 1.8 * 210)
                if alpha:
                    pygame.draw.rect(vignette, (0, 0, 0, alpha), (x, y, step, step))
        return vignette

    def _build_grain(self) -> pygame.Surface:
        grain = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for _ in range(900):
            shade = random.randint(180, 255)
            alpha = random.randint(5, 13)
            grain.set_at(
                (random.randrange(SCREEN_WIDTH), random.randrange(SCREEN_HEIGHT)),
                (shade, shade, shade, alpha),
            )
        return grain

    def _draw_black_overlay(self, surface: pygame.Surface, alpha: int) -> None:
        if alpha <= 0:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, max(0, min(255, alpha))))
        surface.blit(overlay, (0, 0))

    def _smoothstep(self, value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        print(message)
