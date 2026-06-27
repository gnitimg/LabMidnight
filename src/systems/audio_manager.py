"""Small resilient audio wrapper around pygame.mixer."""

from __future__ import annotations

from pathlib import Path
import time

import pygame


SOUND_FILES = {
    "ambient_lab": "ambient_lab.wav",
    "ambient_power": "ambient_power.wav",
    "lecture_loop": "lecture_loop.wav",
    "laugh": "laugh_01.wav",
    "cry": "cry_01.wav",
    "knock": "knock_door.wav",
    "door_open": "door_open.wav",
    "elevator_move": "elevator_move.wav",
    "elevator_arrive": "elevator_arrive.wav",
    "item_pick": "item_pick.wav",
    "power_restore": "power_restore.wav",
    "error": "error.wav",
    "sanity_low": "sanity_low.wav",
}


class AudioManager:
    def __init__(self, base_path: str = "assets/sounds") -> None:
        self.base_path = Path(base_path)
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.channels: dict[str, pygame.mixer.Channel] = {}
        self.cooldowns: dict[str, float] = {}
        self.missing_reported: set[str] = set()
        self._init_mixer()
        self._load_sounds()

    def _init_mixer(self) -> None:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except pygame.error as exc:
            print(f"[audio warning] mixer disabled: {exc}")
            self.enabled = False

    def _load_sounds(self) -> None:
        if not self.enabled:
            return
        for key, filename in SOUND_FILES.items():
            path = self.base_path / filename
            if not path.exists():
                continue
            try:
                self.sounds[key] = pygame.mixer.Sound(str(path))
            except pygame.error as exc:
                print(f"[audio warning] failed to load {path}: {exc}")

    def play(self, key: str, *, volume: float = 0.8, cooldown: float = 0.35) -> None:
        if not self.enabled:
            return
        sound = self.sounds.get(key)
        if sound is None:
            self._report_missing(key)
            return
        now = time.monotonic()
        if now - self.cooldowns.get(key, 0.0) < cooldown:
            return
        self.cooldowns[key] = now
        sound.set_volume(volume)
        sound.play()

    def play_loop(self, key: str, *, volume: float = 0.45) -> None:
        if not self.enabled:
            return
        if key in self.channels and self.channels[key].get_busy():
            self.channels[key].set_volume(volume)
            return
        sound = self.sounds.get(key)
        if sound is None:
            self._report_missing(key)
            return
        sound.set_volume(volume)
        channel = sound.play(loops=-1)
        if channel is not None:
            channel.set_volume(volume)
            self.channels[key] = channel

    def stop_loop(self, key: str) -> None:
        channel = self.channels.get(key)
        if channel is not None:
            channel.stop()
            self.channels.pop(key, None)

    def stop_all(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
        self.channels.clear()

    def _report_missing(self, key: str) -> None:
        if key not in self.missing_reported:
            print(f"[audio warning] missing sound: {SOUND_FILES.get(key, key)}")
            self.missing_reported.add(key)
