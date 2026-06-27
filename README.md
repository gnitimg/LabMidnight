# LabMidnight

> 加班累了是吗 —— 基于 Python + Pygame 的第一人称伪 3D 恐怖解谜 RPG MVP

## 项目简介

`LabMidnight（加班累了是吗）` 是一个 PythonGame 课程 Demo。玩家在凌晨两点的实验楼中醒来，发现整栋楼突然停电。走廊陷入黑暗，手机信号异常，一间本应空无一人的教室里传来老师讲课声。

玩家需要依靠手电筒探索实验楼四层局部区域，收集钥匙、纸条、保险丝、门禁卡等道具，破解实验室、异常教室、配电室和出口门禁组成的轻量谜题流程，在理智值耗尽前离开实验楼。

## 已实现内容

| 模块 | 功能 |
|---|---|
| **核心循环** | Pygame 窗口、主菜单、操作说明、暂停、背包、成功结局、失败结局、楼层切换确认 |
| **渲染** | Raycasting 第一人称伪 3D 渲染、NumPy 加速地面透视、3 档画质切换（性能/平衡/清晰） |
| **输入** | W/S 前进后退、A/D 左右移动、鼠标移动控制视角、鼠标右键开关手电筒 |
| **碰撞** | 墙壁碰撞、门碰撞、物体碰撞、不能穿墙或穿过未解锁门 |
| **交互** | Space/鼠标左键交互、开门、拾取、查看线索、门禁检查 |
| **手电筒** | 手电电量管理、低电量闪烁变暗、黑暗中理智值下降 |
| **背包系统** | 道具收集与使用、剧情 flags 管理 |
| **音效** | AudioManager 资源缺失容错、环境音循环、空间声像 |
| **地图系统** | 4 层地图加载、楼层切换持久化、门组管理、物体碰撞检测 |
| **物体系统** | 自定义物体资产、方向贴图、碰撞体积、元素绑定（剧情/拾取/触发/装饰） |
| **蚊虫系统** | 动态蚊子实体、BFS 寻路、状态机（游荡/追踪/攻击/死亡）、鼠标点击击杀、SAN 作为攻击力 |
| **地图编辑器** | 可视化编辑 4 层地图、房间/门/物体/窗户放置、撤销重做、多选移动 |

## 操作方式

| 输入 | 功能 |
|---|---|
| W | 前进 |
| S | 后退 |
| A / D | 向左 / 向右移动 |
| 鼠标移动 | 移动视角（上下左右） |
| Space | 交互、开门、拾取、查看线索 |
| 鼠标左键 | 交互或确认；点击蚊子可造成伤害 |
| 鼠标右键 | 开关手电筒 |
| B / I | 打开或关闭背包 |
| F2 | 切换渲染质量：性能 / 平衡 / 清晰 |
| ESC | 暂停或返回 |

不使用 F 键交互；Space 不用于跳跃。

## 运行方式

```bash
pip install -r requirements.txt
python main.py
```

渲染默认使用 NumPy 加速地面透视采样。入口会设置 SDL/独显相关提示变量，但 Pygame 不能强制选择 NVIDIA 独显；如果笔记本仍使用核显，可在 Windows"设置 > 系统 > 显示 > 图形"中把 `python.exe` 设为高性能。

画质可以在游戏中按 `F2` 切换。性能档更接近 60 FPS；清晰档纹理更锐利但更吃 CPU。

### 音效资源

如果没有音效文件，游戏仍可运行。音效可按以下名称放入 `assets/sounds/`：

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
| `elevator_move.wav` | 电梯运行音效 |
| `elevator_arrive.wav` | 电梯到达音效 |

### 贴图资源

贴图资源放入 `assets/textures/`，缺失时会使用默认纯色绘制。标准名称见 [assets/ASSET_NAMES.md](assets/ASSET_NAMES.md)：

| 文件名 | 用途 |
|---|---|
| `ceiling.png` | 天花板纹理 |
| `floor.png` | 地面纹理 |
| `wall.png` | 默认墙壁纹理 |
| `window.png` | 窗户纹理 |
| `door.png` | 门卫处门纹理（也是缺省门纹理） |
| `door_lab.png` | 实验室门 / 机房门纹理 |
| `door_classroom.png` | 教室门纹理 |
| `door_power.png` | 配电室门纹理 |
| `door_exit.png` | 出口门纹理 |
| `elevator.png` | 电梯纹理 |

## 地图编辑

地图支持 1-4 层。编辑器会优先保存到 `data/floors/floor_1.txt` 到 `data/floors/floor_4.txt`；旧的 [data/map_layout.txt](data/map_layout.txt) 仍作为四层兼容入口。一个字符代表一块 `60cm x 60cm` 地砖。

### 地图符号

| 符号 | 含义 |
|---|---|
| `#` | 墙壁 |
| `.` | 地面 |
| `@` | 玩家出生点 |
| `W` | 窗户（阻挡移动，使用窗户贴图渲染） |
| `L` | 实验室门 |
| `M` | 机房门（使用实验室门贴图） |
| `C` | 教室门 |
| `G` | 门卫处门 |
| `P` | 配电室门 |
| `E` | 出口门 |
| `1`-`9` | 剧情物件（具体含义见编辑器 Objects 列表） |

## 最短通关路线

```text
开始游戏
检查实验桌，获得手电筒和实验室钥匙
打开实验室门，进入走廊
进入异常教室，检查黑板或讲台
获得配电室线索
进入保安室，获得实验楼平面图和保险丝
打开配电室门，使用保险丝恢复部分电力
进入机房，获得门禁卡
前往出口，使用门禁卡离开
进入成功结局：回到寝室
```

失败路线：长时间处于黑暗、低电量拖延或理智值降为 0 后进入失败结局：组会还没结束。

## 文件结构

```text
LabMidnight/
├── main.py                              # 游戏入口
├── map_editor.py                        # 地图编辑器入口
├── src/
│   ├── settings.py                      # 全局常量、Tile ID、颜色定义
│   ├── core/
│   │   ├── game.py                      # 主游戏循环、状态机、渲染调度
│   │   ├── game_floors.py               # 楼层切换、地图加载、系统绑定
│   │   ├── game_input.py                # 键盘/鼠标事件处理
│   │   ├── game_runtime.py              # 帧更新、玩家状态、故事触发
│   │   └── player.py                    # 玩家数据类（位置、背包、flags）
│   ├── maps/
│   │   ├── map_data.py                  # GameMap 主类（组合 Mixin）
│   │   ├── game_map_build.py            # 地图构建（从文件解析 grid）
│   │   ├── game_map_collision.py        # 碰撞检测（墙壁/门/物体）
│   │   ├── game_map_doors.py            # 门状态管理（开/关/动画）
│   │   ├── game_map_spawn.py            # 出生点计算（入口/出口）
│   │   ├── map_objects.py               # MapObject 数据类、模板、元数据
│   │   ├── map_paths.py                 # 地图文件路径、初始玩家配置
│   │   ├── map_editor.py                # 地图编辑器主类（组合 Mixin）
│   │   ├── map_editor_config.py         # 编辑器常量、颜色、字段定义
│   │   ├── map_editor_models.py         # Room / ObjectPlacement 数据类
│   │   ├── map_editor_state.py          # 编辑器可变状态（组合 Mixin）
│   │   ├── map_editor_state_doors.py    # 编辑器门操作
│   │   ├── map_editor_state_grid.py     # 编辑器 grid 重建
│   │   ├── map_editor_state_load.py     # 编辑器加载/保存
│   │   ├── map_editor_state_objects.py  # 编辑器物体操作
│   │   ├── map_editor_editing.py        # 编辑器编辑逻辑
│   │   ├── map_editor_events.py         # 编辑器事件处理
│   │   ├── map_editor_history.py        # 编辑器撤销/重做
│   │   ├── map_editor_selection.py      # 编辑器多选/框选
│   │   ├── map_editor_viewport.py       # 编辑器视口/缩放/滚动
│   │   ├── map_editor_draw_canvas.py    # 编辑器画布绘制
│   │   ├── map_editor_draw_panel.py     # 编辑器右侧面板绘制
│   │   └── MAP_EDITOR_GUIDE.md          # 编辑器使用指南
│   ├── rendering/
│   │   ├── renderer.py                  # RaycastingRenderer 主类（组合 Mixin）
│   │   ├── renderer_config.py           # 渲染常量（遮挡、面板等）
│   │   ├── renderer_raycast.py          # DDA 光线投射算法
│   │   ├── renderer_doors.py            # 开门渲染
│   │   ├── renderer_lighting.py         # 手电筒光束、暗度遮罩
│   │   ├── renderer_objects.py          # 物体/蚊子投影、深度遮挡
│   │   ├── renderer_planes.py           # 天花板/地面透视纹理渲染
│   │   └── renderer_projection.py       # 视角投影（yaw/pitch/horizon）
│   ├── resources/
│   │   ├── asset_manager.py             # TextureStore 纹理加载与回退
│   │   └── object_assets.py             # ObjectSpec 加载、物体贴图路径
│   ├── systems/
│   │   ├── audio_manager.py             # AudioManager 音效加载/播放/空间声像
│   │   ├── interaction.py               # InteractionSystem 主类（组合 Mixin）
│   │   ├── interaction_config.py        # 交互常量（过渡物体、填充等）
│   │   ├── interaction_targeting.py     # 目标检测（射线检测门/物体）
│   │   ├── interaction_flow.py          # 交互流程（门/物体/电梯/出口）
│   │   ├── interaction_triggers.py      # 触发器（剧情/拾取/特殊事件）
│   │   └── mosquito_system.py           # 蚊虫动态干扰实体系统
│   └── ui/
│       ├── ui.py                        # HUD、菜单、背包、楼层切换 UI
│       └── ending.py                    # 结局标题文本
├── assets/
│   ├── textures/                        # 墙壁/地面/天花板/门贴图
│   ├── objects/                         # 自定义物体文件夹（含 object.json）
│   ├── sounds/                          # 音效文件
│   ├── sprites/                         # 精灵图
│   └── fonts/                           # 字体文件
├── data/
│   ├── floors/                          # floor_N.txt 和 floor_N_rooms.json
│   ├── map_layout.txt                   # 旧版四层兼容入口
│   ├── map_rooms.json                   # 旧版四层元数据兼容
│   └── map_config.json                  # 全局初始玩家配置
├── requirements.txt
└── README.md
```

## 架构说明

### 模块化设计

游戏采用 **Mixin 组合** 模式拆分复杂模块：

| 主类 | 组合的 Mixin | 职责 |
|---|---|---|
| `Game` | `GameInputMixin` + `GameFloorMixin` + `GameRuntimeMixin` | 游戏主循环 |
| `GameMap` | `GameMapBuildMixin` + `GameMapDoorMixin` + `GameMapSpawnMixin` + `GameMapCollisionMixin` | 地图数据 |
| `RaycastingRenderer` | `RendererRaycastMixin` + `RendererDoorMixin` + `RendererLightingMixin` + `RendererObjectMixin` + `RendererPlaneMixin` + `RendererProjectionMixin` | 渲染管线 |
| `InteractionSystem` | `InteractionTargetingMixin` + `InteractionFlowMixin` + `InteractionTriggerMixin` | 交互系统 |
| `MapEditor` | `MapEditorHistoryMixin` + `MapEditorEditingMixin` + `MapEditorEventMixin` + `MapEditorSelectionMixin` + `MapEditorViewportMixin` + `MapEditorDrawCanvasMixin` + `MapEditorDrawPanelMixin` | 地图编辑器 |

### 游戏状态

| 状态 | 常量 | 说明 |
|---|---|---|
| `menu` | `STATE_MENU` | 主菜单 |
| `playing` | `STATE_PLAYING` | 游戏进行中 |
| `paused` | `STATE_PAUSED` | 暂停 |
| `inventory` | `STATE_INVENTORY` | 背包界面 |
| `floor_confirm` | `STATE_FLOOR_CONFIRM` | 楼层切换确认 |
| `success` | `STATE_SUCCESS` | 成功结局 |
| `failure` | `STATE_FAILURE` | 失败结局 |

### 渲染管线

1. **天花板/地面** — `RendererPlaneMixin._draw_background()` 透视纹理或纯色
2. **墙壁** — `RendererRaycastMixin` DDA 光线投射
3. **开门** — `RendererDoorMixin._draw_open_doors()` 从远到近绘制
4. **物体** — `RendererObjectMixin` 投影到屏幕、深度遮挡、蚊子实体
5. **光照** — `RendererLightingMixin._cut_flashlight_beam()` 手电筒光束

### 蚊虫系统

蚊子是运行时动态实体，状态机驱动：

| 状态 | 触发条件 | 行为 |
|---|---|---|
| `IDLE` | 初始/重置 | 等待激活 |
| `WANDER` | 距离 > 8 | 随机小范围飞行 |
| `CHASE` | 0.75 < 距离 ≤ 8 | BFS 寻路追踪玩家 |
| `ATTACK` | 距离 ≤ 1.30 | 扣除玩家 SAN |
| `DEAD` | HP ≤ 0 | 移除实体 |

玩家攻击蚊子的伤害 = 当前 SAN 值（不消耗 SAN）。

## 开发者地图编辑器

运行：

```bash
python map_editor.py
```

编辑器只用于开发阶段，不会改变 `python main.py` 的游戏入口。

### 编辑器工具

| 工具 | 功能 |
|---|---|
| Select | 点击选择、拖拽移动、拖拽右下角调整大小、Ctrl+拖拽框选 |
| Room | 拖拽生成矩形房间（最小 3×3） |
| Wall | 绘制墙壁覆盖 `#` |
| Window | 绘制窗户覆盖 `W`（阻挡移动，使用窗户贴图） |
| Erase | 绘制地面覆盖 `.` |
| Start | 放置玩家出生点 `@` |
| Door | 选择门类型后拖到墙上放置 |
| Object | 选择物体后点击放置 |

### 门类型

| 符号 | 类型 | 说明 |
|---|---|---|
| `L` | 实验室门 | 使用 `door_lab.png` |
| `M` | 机房门 | 使用实验室门贴图 |
| `C` | 教室门 | 使用 `door_classroom.png` |
| `G` | 门卫处门 | 使用 `door.png` |
| `P` | 配电室门 | 使用 `door_power.png` |
| `E` | 出口门 | 使用 `door_exit.png` |

### 物体元素绑定

选中物体后，右侧面板可配置：

| 属性 | 说明 |
|---|---|
| Element Type | `story_required`（剧情必需）/ `pickup`（可拾取）/ `trigger`（触发器）/ `decoration`（装饰） |
| Item | 拾取获得的道具 ID（如 `flashlight`、`fuse`、`access_card`） |
| Flag | 交互设置的玩家 flag |
| Prompt | 自定义交互提示文本 |
| Message | 交互后显示的消息 |
| Need Item | 需要的前置道具 |
| Need Flag | 需要的前置 flag |
| Random Drop | 随机掉落（配合 Count 使用） |
| Remove after pickup | 拾取后隐藏物体 |

### 快捷键

| 快捷键 | 功能 |
|---|---|
| `Ctrl+S` | 保存当前楼层 |
| `Ctrl+Z` | 撤销 |
| `Ctrl+Shift+Z` | 重做 |
| `Ctrl+L` | 从磁盘重新加载 |
| `Delete` | 删除选中项 |
| `1`-`9` | 切换当前物件编号 |
| `Q` / `E` | 旋转物体（逆时针/顺时针） |
| 鼠标滚轮 | 缩放画布 |

详细使用说明见 [src/maps/MAP_EDITOR_GUIDE.md](src/maps/MAP_EDITOR_GUIDE.md)。

### 游戏内楼层机制

- 2-4 层的安全出口门打开后会黑屏弹出"下了楼，就回不来了哦"。
- 选择"走吧"进入下一层，选择"等等"留在当前层。
- 1-3 层下楼后的出生点会自动放在该层安全出口门前。
