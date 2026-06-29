# LabMidnight 资源标准命名

资源目录使用 `assets/`。如果缺少对应图片或音效，程序会自动使用默认纯色 / 跳过音效，不会崩溃。

## 纹理

放在 `assets/textures/`，支持 `.png`、`.jpg`、`.jpeg`、`.bmp`。

| 文件名 | 用途 | 对应 Tile ID |
|---|---|---|
| `ceiling.png` | 天花板单位纹理，按透视循环采样 | — |
| `floor.png` | 地面单位纹理，按透视循环采样 | — |
| `wall.png` | 默认墙壁纹理 | `TILE_WALL` (1) |
| `window.png` | 窗户纹理，阻挡移动但渲染为窗户 | `TILE_WINDOW` (8) |
| `door.png` | 门卫处门纹理，也是缺省门纹理 | `TILE_GUARD_DOOR` (2) |
| `door_lab.png` | 实验室门 / 机房门纹理 | `TILE_LAB_DOOR` (3) |
| `door_classroom.png` | 教室门纹理 | `TILE_CLASSROOM_DOOR` (4) |
| `door_power.png` | 配电室门纹理 | `TILE_POWER_DOOR` (5) |
| `door_exit.png` | 出口门纹理 | `TILE_EXIT_DOOR` (6) |
| `elevator.png` | 电梯贴图（物体渲染） | — |

## 音效

放在 `assets/sounds/`。

| 文件名 | 音效键 | 用途 |
|---|---|---|
| `ambient_lab.wav` | `ambient_lab` | 实验楼低频环境音（循环） |
| `ambient_power.wav` | `ambient_power` | 恢复供电后的电流环境音（循环） |
| `lecture_loop.wav` | `lecture_loop` | 异常教室讲课声（循环） |
| `laugh_01.wav` | `laugh` | 异常笑声 |
| `cry_01.wav` | `cry` | 异常哭声 |
| `knock_door.wav` | `knock` | 敲门声 |
| `door_open.wav` | `door_open` | 开门反馈 |
| `item_pick.wav` | `item_pick` | 拾取反馈 |
| `power_restore.wav` | `power_restore` | 恢复供电反馈 |
| `error.wav` | `error` | 错误反馈 |
| `sanity_low.wav` | `sanity_low` | 低理智状态音 |
| `elevator_move.wav` | `elevator_move` | 电梯运行音效 |
| `elevator_arrive.wav` | `elevator_arrive` | 电梯到达音效 |
| `mosquito_buzz.wav` | `mosquito_buzz` | 蚊子嗡嗡声（空间声像） |
| `mosquito_hit.wav` | `mosquito_hit` | 蚊子被拍中音效 |
| `mosquito_die.wav` | `mosquito_die` | 蚊子死亡音效 |
| `mosquito_bite.wav` | `mosquito_bite` | 蚊子咬击音效 |

音效键用于 `AudioManager.play()` 调用。缺失文件时 AudioManager 静默跳过。

## 物体资产

放在 `assets/objects/<object_id>/`。每个文件夹包含方向贴图和可选的 `object.json`。

### 已有物体

| 文件夹名 | 说明 |
|---|---|
| `battery` | 备用电池 |
| `blackboard` | 黑板 |
| `card` | 卡片 |
| `desk` | 实验桌 |
| `elevator` | 电梯 |
| `exit_lock` | 出口门禁 |
| `flashlight` | 手电筒 |
| `fuse` | 保险丝 |
| `key` | 钥匙 |
| `note` | 纸条 |
| `pass_card` | 通行牌 |
| `register_book` | 登记册 |
| `switch_box` | 配电箱 |
| `whiteboard` | 白板 |

### 方向贴图命名

```text
<object_id>_front.png
<object_id>_back.png
<object_id>_left.png
<object_id>_right.png
<object_id>_top.png
```

### object.json 格式

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

单位为地图格（1 格 = 60cm）。缺失贴图或元数据时自动回退。
