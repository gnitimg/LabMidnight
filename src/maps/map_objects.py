"""Map object models, templates, and metadata normalization."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.resources.object_assets import ObjectSpec, load_object_specs


SOLID_TEMPLATE_OBJECT_IDS = {
    "lab_desk",
    "blackboard",
    "lectern",
    "security_desk",
    "fuse_cabinet",
    "power_box",
    "server_terminal",
    "exit_panel",
    "elevator",
}

LEGACY_OBJECT_ASSET_ALIASES = {
    "lab_desk": "desk",
}
LEGACY_OBJECT_SYMBOL_ASSET_ALIASES = {
    "1": "desk",
}
ELEMENT_STORY = "story_required"
ELEMENT_PICKUP = "pickup"
ELEMENT_TRIGGER = "trigger"
ELEMENT_DECORATION = "decoration"
VALID_ELEMENT_TYPES = {ELEMENT_STORY, ELEMENT_PICKUP, ELEMENT_TRIGGER, ELEMENT_DECORATION}
RESOURCE_ROLES = {"", "required", "optional", "decor"}
FIXED_OBJECT_STYLES = {
    "blackboard": {
        "width": 0.08,
        "height": 2.0,
        "placement_height": 1.5,
    },
    "elevator": {
        "height": 3.0,
        "placement_height": 0.0,
    },
}
WALL_FACING_OBJECT_IDS = {"blackboard", "elevator", "exit_lock", "switch_box", "whiteboard"}
WALL_FACING_ROTATIONS = (
    (0, -1, 0),
    (1, 0, 270),
    (0, 1, 180),
    (-1, 0, 90),
)


@dataclass(frozen=True)
class MapObject:
    object_id: str
    name: str
    prompt: str
    description: str = ""
    asset_id: str = ""
    length: float = 1.0
    width: float = 1.0
    height: float = 1.0
    placement_height: float = 0.0
    rotation: int = 0
    solid: bool = False
    element_type: str = ELEMENT_STORY
    pickup_item: str = ""
    pickup_flag: str = ""
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

    def footprint_size(self) -> tuple[float, float]:
        normalized = self.rotation % 360
        if normalized in (90, 270):
            return self.width, self.length
        return self.length, self.width


def object_templates() -> dict[str, MapObject]:
    return {
        "1": MapObject(
            "lab_desk",
            "实验桌",
            "按 Space 检查实验桌",
            "电脑还亮着，桌上压着一只旧手电和备用钥匙。",
        ),
        "2": MapObject(
            "blackboard",
            "异常黑板",
            "按 Space 检查黑板",
            "第二节课还没有结束。02:00。第 4 组，进度未完成。",
        ),
        "3": MapObject(
            "lectern",
            "讲台",
            "按 Space 检查讲台",
            "讲台上有一张纸条，边缘像被电流烧焦。",
        ),
        "4": MapObject(
            "security_desk",
            "值班桌",
            "按 Space 检查值班桌",
            "值班记录停在凌晨两点，之后每一行都是同一个时间。",
        ),
        "5": MapObject(
            "fuse_cabinet",
            "工具柜",
            "按 Space 打开工具柜",
            "柜子里放着一枚还能用的保险丝。",
        ),
        "6": MapObject(
            "battery",
            "备用电池",
            "按 Space 拾取电池",
            "地上有一节备用电池，外壳有些磨损。",
        ),
        "7": MapObject(
            "power_box",
            "配电箱",
            "按 Space 检查配电箱",
            "配电箱里缺了一枚保险丝。",
        ),
        "8": MapObject(
            "server_terminal",
            "机房终端",
            "按 Space 检查机房终端",
            "屏幕显示：LabMidnight.map，出口状态等待确认。",
        ),
        "9": MapObject(
            "elevator",
            "东11C货梯",
            "按 Space 使用东11C货梯",
            "货梯面板亮着，楼层按钮停在 1 到 4。",
        ),
    }


def _object_from_spec(spec: ObjectSpec, rotation: int = 0) -> MapObject:
    return _object_with_fixed_style(MapObject(
        object_id=spec.object_id,
        name=spec.name,
        prompt=spec.prompt,
        description=spec.description,
        asset_id=spec.object_id,
        length=spec.length,
        width=spec.width,
        height=spec.height,
        placement_height=spec.placement_height,
        rotation=rotation % 360,
        solid=spec.solid,
    ))


def _template_with_asset(template: MapObject, specs: dict[str, ObjectSpec], rotation: int = 0) -> MapObject:
    spec = specs.get(template.object_id)
    if spec is None:
        alias = LEGACY_OBJECT_ASSET_ALIASES.get(template.object_id)
        spec = specs.get(alias) if alias is not None else None
    if spec is None:
        return _object_with_fixed_style(replace(
            template,
            asset_id=template.asset_id or template.object_id,
            rotation=rotation % 360,
            solid=_legacy_template_solid(template),
        ))
    return _object_with_fixed_style(replace(
        template,
        asset_id=spec.object_id,
        length=spec.length,
        width=spec.width,
        height=spec.height,
        placement_height=spec.placement_height,
        rotation=rotation % 360,
        solid=spec.solid,
    ))


def _legacy_template_solid(template: MapObject) -> bool:
    if template.object_id in SOLID_TEMPLATE_OBJECT_IDS:
        return True
    return template.solid


def _object_with_metadata_overrides(obj: MapObject, raw: dict) -> MapObject:
    updates: dict[str, object] = {}
    length = _optional_positive_float(raw, "length")
    width = _optional_positive_float(raw, "width")
    height = _optional_positive_float(raw, "height")
    placement_height = _optional_non_negative_float(raw, "placement_height")
    if length is not None:
        updates["length"] = length
    if width is not None:
        updates["width"] = width
    if height is not None:
        updates["height"] = height
    if placement_height is not None:
        updates["placement_height"] = placement_height
    element_type = str(raw.get("element_type", obj.element_type))
    if element_type in VALID_ELEMENT_TYPES:
        updates["element_type"] = element_type
    for key in ("pickup_item", "pickup_flag", "interaction_message", "required_item", "required_flag", "failure_message"):
        value = str(raw.get(key, "")).strip()
        if value:
            updates[key] = value
    trigger_id = str(raw.get("trigger_id", "")).strip()
    if trigger_id:
        updates["trigger_id"] = trigger_id
    if "is_trigger" in raw:
        updates["is_trigger"] = _bool_value(raw.get("is_trigger"))
    elif trigger_id or element_type == ELEMENT_TRIGGER:
        updates["is_trigger"] = True
    if "trigger_once" in raw:
        updates["trigger_once"] = _bool_value(raw.get("trigger_once"))
    resource_role = str(raw.get("resource_role", "")).strip().lower()
    if resource_role in RESOURCE_ROLES:
        updates["resource_role"] = resource_role
    prompt = str(raw.get("interaction_prompt", "")).strip()
    if prompt:
        updates["prompt"] = prompt
    if "remove_on_pickup" in raw:
        updates["remove_on_pickup"] = _bool_value(raw.get("remove_on_pickup"))
    if "random_drop" in raw:
        updates["random_drop"] = _bool_value(raw.get("random_drop"))
    if "drop_count" in raw:
        try:
            updates["drop_count"] = max(1, int(raw["drop_count"]))
        except (TypeError, ValueError):
            pass
    return replace(obj, **updates) if updates else obj


def _object_with_fixed_style(obj: MapObject) -> MapObject:
    style = FIXED_OBJECT_STYLES.get(obj.object_id)
    if style is None:
        return obj
    return replace(obj, **style)


def _optional_positive_float(payload: dict, key: str) -> float | None:
    if key not in payload:
        return None
    try:
        return max(0.05, float(payload[key]))
    except (TypeError, ValueError):
        return None


def _optional_non_negative_float(payload: dict, key: str) -> float | None:
    if key not in payload:
        return None
    try:
        return max(0.0, float(payload[key]))
    except (TypeError, ValueError):
        return None


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


