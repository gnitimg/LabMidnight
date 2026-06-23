# LabMidnight 资源标准命名

资源目录使用 `assets/`。如果缺少对应图片或音效，程序会自动使用默认纯色 / 跳过音效，不会崩溃。

## 纹理

放在 `assets/textures/`，支持 `.png`、`.jpg`、`.jpeg`、`.bmp`。

| 文件名 | 用途 |
|---|---|
| `ceiling.png` | 天花板单位纹理，按透视循环采样 |
| `floor.png` | 地面单位纹理，按透视循环采样，近大远小 |
| `wall.png` | 默认墙壁纹理 |
| `door.png` | 门卫处门纹理，也是缺省门纹理 |
| `door_lab.png` | 实验室门 / 机房门纹理 |
| `door_classroom.png` | 教室门纹理 |
| `door_power.png` | 配电室门纹理 |
| `door_exit.png` | 出口门纹理 |

## 音效

放在 `assets/sounds/`。

| 文件名 | 用途 |
|---|---|
| `ambient_lab.wav` | 实验楼低频环境音 |
| `ambient_power.wav` | 恢复供电后的电流环境音 |
| `lecture_loop.wav` | 异常教室讲课声 |
| `laugh_01.wav` | 异常笑声 |
| `cry_01.wav` | 异常哭声 |
| `knock_door.wav` | 敲门声 |
| `door_open.wav` | 开门反馈 |
| `item_pick.wav` | 拾取反馈 |
| `power_restore.wav` | 恢复供电反馈 |
| `error.wav` | 错误反馈 |
| `sanity_low.wav` | 低理智状态音 |
