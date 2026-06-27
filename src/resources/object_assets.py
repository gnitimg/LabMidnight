"""Object asset metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


OBJECT_ASSET_DIR = Path("assets/objects")
OBJECT_DEF_FILE = "object.json"
OBJECT_FACES = ("front", "back", "left", "right", "top")


@dataclass(frozen=True)
class ObjectSpec:
    object_id: str
    name: str
    length: float = 1.0
    width: float = 1.0
    height: float = 1.0
    placement_height: float = 0.0
    solid: bool = True
    prompt: str = ""
    description: str = ""

    def footprint_size(self, rotation: int = 0) -> tuple[float, float]:
        normalized = rotation % 360
        if normalized in (90, 270):
            return self.width, self.length
        return self.length, self.width


def load_object_specs(object_dir: Path = OBJECT_ASSET_DIR) -> dict[str, ObjectSpec]:
    if not object_dir.exists():
        return {}
    specs: dict[str, ObjectSpec] = {}
    for folder in sorted(path for path in object_dir.iterdir() if path.is_dir()):
        spec = load_object_spec(folder)
        if spec is not None:
            specs[spec.object_id] = spec
    return specs


def load_object_spec(folder: Path) -> ObjectSpec | None:
    object_id = folder.name
    payload = _read_definition(folder / OBJECT_DEF_FILE)
    if payload is None:
        payload = {}

    name = str(payload.get("name") or object_id.replace("_", " ").title())
    length = _positive_float(payload, "length", 1.0)
    width = _positive_float(payload, "width", 1.0)
    height = _positive_float(payload, "height", 1.0)
    placement_height = _non_negative_float(
        payload,
        ("placement_height", "place_height", "z"),
        0.0,
    )
    solid = bool(payload.get("solid", True))
    prompt = str(payload.get("prompt") or f"Press Space to inspect {name}")
    description = str(payload.get("description") or "")
    return ObjectSpec(
        object_id=object_id,
        name=name,
        length=length,
        width=width,
        height=height,
        placement_height=placement_height,
        solid=solid,
        prompt=prompt,
        description=description,
    )


def object_texture_path(object_id: str, face: str, object_dir: Path = OBJECT_ASSET_DIR) -> Path | None:
    folder = object_dir / object_id
    for extension in (".png", ".jpg", ".jpeg", ".bmp"):
        path = folder / f"{object_id}_{face}{extension}"
        if path.exists():
            return path
    return None


def _read_definition(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _positive_float(payload: dict, key: str, fallback: float) -> float:
    try:
        value = float(payload.get(key, fallback))
    except (TypeError, ValueError):
        return fallback
    return max(0.05, value)


def _non_negative_float(payload: dict, keys: tuple[str, ...], fallback: float) -> float:
    for key in keys:
        if key not in payload:
            continue
        try:
            return max(0.0, float(payload[key]))
        except (TypeError, ValueError):
            return fallback
    return fallback
