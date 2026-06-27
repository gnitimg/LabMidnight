# LabMidnight

> 加班累了是吗 —— 基于 Python + Pygame 的第一人称伪 3D 恐怖解谜 RPG Demo

## 项目简介

`LabMidnight（加班累了是吗）` 是一个 PythonGame 课程项目。玩家在凌晨两点的实验楼中醒来，发现整栋楼突然停电。走廊陷入黑暗，手机信号异常，一间本应空无一人的教室里传来老师讲课声。

玩家需要依靠手电筒探索 1F-4F 实验楼，收集手电、钥匙、纸条、保险丝、门禁卡等道具，破解异常教室、配电室、机房和安全出口组成的轻量谜题流程，在 SAN 耗尽前离开实验楼。

项目保持 `Pygame + 2D 网格地图 + Raycasting 伪 3D` 技术路线，不使用真 3D 引擎，不引入网络、数据库或大型外部服务。

## 当前实现

| 模块 | 当前能力 |
|---|---|
| 核心循环 | 主菜单、操作说明、暂停、背包、楼层切换确认、成功/失败结局 |
| 渲染 | 第一人称 Raycasting、地面/天花板透视、贴图墙面、门面板、深度缓冲、3 档画质 |
| 输入 | W/S 前后移动、A/D 左右平移、鼠标视角、Space/左键交互、右键手电、F2 画质切换 |
| 地图 | 1F-4F 外部地图文件、门组、楼层切换、出生点和出口点管理 |
| 门与碰撞 | 墙体、窗户、关闭门、物体碰撞；已打开的门可再次点击关闭 |
| 主线交互 | 实验桌、黑板/讲台、工具柜、配电箱、机房终端、安全出口、一楼出口 |
| 状态 | HP、SAN、手电电量、背包、剧情 flag、SAN 受击抖动和红色减少动画 |
| 音效 | Pygame mixer、环境循环音、一次性反馈音、资源缺失 warning fallback |
| 动态蚊虫 | 运行时实体、潜伏点生成、BFS 寻路、主动追咬、空间嗡嗡声、屏幕点击命中 |
| 结局视频 | `assets/videos/successful.mp4` 与 `assets/videos/defeat.mp4` 全屏沉浸式播放 |
| 地图编辑器 | 可视化编辑楼层、房间、门、窗户、物体、出生点，支持撤销/重做 |

## 运行方式

```bash
pip install -r requirements.txt
python main.py
```

开发阶段地图编辑器：

```bash
python map_editor.py
```

基础自检：

```bash
python -m compileall .
```

## 操作方式

| 输入 | 功能 |
|---|---|
| W / S | 前进 / 后退 |
| A / D | 左右平移 |
| 鼠标移动 | 控制视角 |
| Space | 交互、开门、关门、拾取、查看线索 |
| 鼠标左键 | 优先攻击可见蚊子；未命中蚊子时执行普通交互 |
| 鼠标右键 | 开关手电筒 |
| B / I | 打开或关闭背包 |
| F2 | 切换渲染质量：性能 / 平衡 / 清晰 |
| ESC | 暂停或返回 |

不使用 F 键交互；Space 不用于跳跃，也不攻击蚊子。

## 主线流程

最短通关路线：

```text
开始游戏
检查实验桌，获得 flashlight 和 lab_key
打开实验室门，进入走廊
进入异常教室，检查黑板或讲台，获得 note_a 并设置 got_blackboard_clue
进入工具柜区域，获得 fuse
打开配电室门，使用 fuse 恢复 power_restored
进入机房终端，获得 access_card
通过 2F-4F 安全出口逐层下楼
到达 1F 出口，触发成功结局
```

失败路线：SAN 因黑暗、低电量、剧情事件或蚊虫叮咬降为 0 后进入失败结局。

## 动态蚊虫系统

蚊子不是地图文件里的静态贴图，而是运行时生成的动态干扰实体。核心代码位于 `src/systems/mosquito_system.py`。

当前关键数值：

| 常量 | 当前值 | 说明 |
|---|---:|---|
| `MOSQUITO_HP` | 150 | 每只蚊子生命值 |
| `MOSQUITO_MAX_ACTIVE` | 10 | 同时存在上限 |
| `MOSQUITO_MAX_PER_FLOOR` | 6 | 每层累计生成上限 |
| `MOSQUITO_BASE_SPEED` | 1.65 | 基础速度 |
| `MOSQUITO_ATTACK_RANGE` | 1.30 | 叮咬距离 |
| `MOSQUITO_ATTACK_SAN_DAMAGE` | 5 | 每次叮咬扣除 SAN |
| `MOSQUITO_ATTACK_COOLDOWN` | 1.6 | 叮咬冷却 |
| `MOSQUITO_TARGET_LOST_DISTANCE` | 50.0 | 超出后放弃追踪 |

玩家左键点击可见蚊子时，伤害等于点击瞬间的当前 SAN：

```python
damage = int(game.player.sanity)
```

攻击不消耗 SAN。SAN 越低，清除蚊子的效率越低。蚊子会从每层预生成的潜伏点激活；如果潜伏点不可达，则尝试在玩家附近可通行位置生成。蚊子寻路时会避开墙体和关闭门，已关闭的门会阻断追踪路线。

渲染器会把蚊子作为 2.5D billboard 投影到屏幕中，使用 depth buffer 判断墙体/门遮挡；可见蚊子始终显示红色血条，并带亮边和短拖尾。嗡嗡声只选威胁最高的一只作为主声源，按距离衰减并按相对角度设置左右声道。

详细设计见 [docs/mosquito_system_design.md](docs/mosquito_system_design.md)。

## 结局视频

结局视频由 `src/ui/ending_video.py` 管理，使用可选 OpenCV 解码 mp4 画面，再交给 Pygame 全屏绘制。缺少 OpenCV、缺少视频文件或解码失败时，游戏会 warning 一次并回退到原静态结局画面。

| 文件 | 用途 | 当前行为 |
|---|---|---|
| `assets/videos/successful.mp4` | 成功结局 | 全屏沉浸式播放，可循环显示 |
| `assets/videos/defeat.mp4` | 失败结局 | 眼前渐黑后播放一次，停最后一帧 4 秒，再全黑并显示重试/退出 |

当前视频播放器只负责画面帧显示；结局音效仍建议通过 `AudioManager` 和 `assets/sounds/` 单独管理。

## 资源文件

### 音效

音效文件放入 `assets/sounds/`。缺失时不会崩溃，只会输出 warning 并跳过播放。

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
| `sanity_low.wav` | 低理智音效 |
| `elevator_move.wav` | 电梯运行 |
| `elevator_arrive.wav` | 电梯到达 |
| `mosquito_buzz.wav` | 蚊子空间嗡嗡声 |
| `mosquito_hit.wav` | 蚊子被击中 |
| `mosquito_die.wav` | 蚊子死亡 |
| `mosquito_bite.wav` | 蚊子叮咬 |

### 贴图与图片

贴图放入 `assets/textures/`，物体资产放入 `assets/objects/`，精灵放入 `assets/sprites/`。缺失时使用默认绘制。

可选蚊子贴图：

```text
assets/sprites/mosquito.png
```

缺少该文件时，渲染器会绘制程序生成的蚊子外观。

### 视频

```text
assets/videos/successful.mp4
assets/videos/defeat.mp4
```

视频文件不是必需资源。缺失时结局仍可进入，并回退到静态绘制。

## 地图编辑

地图支持 1-4 层。编辑器优先保存到：

```text
data/floors/floor_1.txt
data/floors/floor_2.txt
data/floors/floor_3.txt
data/floors/floor_4.txt
```

一个字符代表一块 `60cm x 60cm` 地砖。

| 符号 | 含义 |
|---|---|
| `#` | 墙壁 |
| `.` | 地面 |
| `@` | 玩家出生点 |
| `W` | 窗户 |
| `L` | 实验室门 |
| `M` | 机房门 |
| `C` | 教室门 |
| `G` | 门卫处门 |
| `P` | 配电室门 |
| `E` | 出口门 |
| `1`-`9` | 剧情物件 |

详细使用说明见 [src/maps/MAP_EDITOR_GUIDE.md](src/maps/MAP_EDITOR_GUIDE.md)。

## 文件结构

```text
LabMidnight/
├── main.py
├── map_editor.py
├── README.md
├── requirements.txt
├── assets/
│   ├── fonts/
│   ├── objects/
│   ├── sounds/
│   ├── sprites/
│   ├── textures/
│   └── videos/
│       ├── successful.mp4
│       └── defeat.mp4
├── data/
│   └── floors/
├── docs/
│   └── mosquito_system_design.md
└── src/
    ├── core/
    │   ├── game.py
    │   ├── game_floors.py
    │   ├── game_input.py
    │   ├── game_runtime.py
    │   └── player.py
    ├── maps/
    ├── rendering/
    ├── resources/
    ├── systems/
    │   ├── audio_manager.py
    │   ├── interaction.py
    │   └── mosquito_system.py
    └── ui/
        ├── ending.py
        ├── ending_video.py
        └── ui.py
```

## 验收检查

建议每次合并前至少运行：

```bash
python -m compileall .
```

可交互环境下再运行：

```bash
python main.py
```

重点手测：

1. 主菜单、操作说明、暂停、背包可用；
2. W/S、A/D、鼠标视角、右键手电、F2 画质切换正常；
3. 实验桌、黑板/讲台、工具柜、配电箱、机房终端、出口流程正常；
4. 打开的门可再次关闭，关闭门仍阻挡玩家和蚊子；
5. 蚊子会生成、追踪、绕路、显示血条、叮咬扣 SAN；
6. 左键点击可见蚊子时伤害等于当前 SAN；
7. 蚊子在墙或关闭门后不会明显穿墙显示；
8. 成功/失败结局视频资源存在时正常播放，缺失时 fallback 不崩溃。
