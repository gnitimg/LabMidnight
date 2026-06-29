# LabMidnight Object Assets

Place each object in its own folder under `assets/objects/`:

```text
assets/objects/<object_id>/
```

## Directional Textures

```text
<object_id>_front.png
<object_id>_back.png
<object_id>_left.png
<object_id>_right.png
<object_id>_top.png
```

Missing textures fall back to solid-color placeholders. Only existing textures are rendered.

## object.json

Each folder may include `object.json` for metadata:

```json
{
  "name": "Lab Desk",
  "length": 2.0,
  "width": 1.0,
  "height": 1.2,
  "placement_height": 0.0,
  "solid": true,
  "prompt": "Press Space to inspect Lab Desk",
  "description": "Optional interaction text."
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | folder name | Display name |
| `length` | float | 1.0 | Size along map x-axis (tiles) |
| `width` | float | 1.0 | Size along map y-axis (tiles) |
| `height` | float | 1.0 | Vertical size (tiles) |
| `placement_height` | float | 0.0 | Distance above floor (tiles). Use for wall-mounted objects. |
| `solid` | bool | true | Whether the object blocks player movement |
| `prompt` | string | "" | Interaction prompt text |
| `description` | string | "" | Description shown after interaction |

Units are map tiles. One tile = 60 cm.

## Element Binding

Objects can be configured as gameplay elements in the map editor:

| Element Type | Description |
|---|---|
| `story_required` | Fixed plot objects. Can grant items and set flags. |
| `pickup` | Optional pickable objects. Supports random drop. |
| `trigger` | Custom trigger events. |
| `decoration` | Non-interactive decoration. |

## Existing Objects

| Folder | Name | Solid | Notes |
|---|---|---|---|
| `battery` | 备用电池 | no | Restores flashlight power |
| `blackboard` | 黑板 | yes | Wall-facing, fixed width 0.08 |
| `card` | 卡片 | no | Generic card object |
| `desk` | 实验桌 | yes | Legacy "1" template |
| `elevator` | 电梯 | yes | Wall-facing, height 3.0 |
| `exit_lock` | 出口门禁 | yes | Wall-facing |
| `flashlight` | 手电筒 | no | Starting item |
| `fuse` | 保险丝 | no | Used in power room |
| `key` | 钥匙 | no | Door keys |
| `note` | 纸条 | no | Story clues |
| `pass_card` | 通行牌 | no | Old corridor pass |
| `register_book` | 登记册 | no | Lobby register |
| `switch_box` | 配电箱 | yes | Wall-facing |
| `whiteboard` | 白板 | yes | Wall-facing |
