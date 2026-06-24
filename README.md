# LabMidnight

> 加班累了是吗 —— 基于 Python + Pygame 的第一人称伪 3D 恐怖解谜 RPG MVP

## 项目简介

`LabMidnight（加班累了是吗）` 是一个 PythonGame 课程 Demo。玩家在凌晨两点的实验楼中醒来，发现整栋楼突然停电。走廊陷入黑暗，手机信号异常，一间本应空无一人的教室里传来老师讲课声。

玩家需要依靠手电筒探索实验楼四层局部区域，收集钥匙、纸条、保险丝、门禁卡等道具，破解实验室、异常教室、配电室和出口门禁组成的轻量谜题流程，在理智值耗尽前离开实验楼。

## 已实现内容

- Pygame 窗口、主菜单、操作说明、暂停、背包、成功结局、失败结局
- 2D 网格地图 + Raycasting 第一人称伪 3D 渲染
- W/S 前进后退，A/D 左右移动，鼠标移动控制视角
- 碰撞检测，不能穿墙或穿过未解锁门
- Space 和鼠标左键交互
- 鼠标右键开关手电筒
- 手电电量、低电量变暗、黑暗中理智值下降
- 背包与剧情 flags
- 实验室脱出、异常教室线索、配电室恢复供电、机房门禁卡、出口通关
- 音效管理器，资源缺失时只输出 warning，不会导致游戏崩溃

## 操作方式

| 输入 | 功能 |
|---|---|
| W | 前进 |
| S | 后退 |
| A / D | 向左 / 向右移动 |
| 鼠标移动 | 移动视角 |
| Space | 交互、开门、拾取、查看线索 |
| 鼠标左键 | 交互或确认 |
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

渲染默认使用 NumPy 加速地面透视采样。入口会设置 SDL/独显相关提示变量，但 Pygame 不能强制选择 NVIDIA 独显；如果笔记本仍使用核显，可在 Windows“设置 > 系统 > 显示 > 图形”中把 `python.exe` 设为高性能。

画质可以在游戏中按 `F2` 切换。性能档更接近 60 FPS；清晰档纹理更锐利但更吃 CPU。

如果没有音效文件，游戏仍可运行。音效可按以下名称放入 `assets/sounds/`：

```text
ambient_lab.wav
ambient_power.wav
lecture_loop.wav
laugh_01.wav
cry_01.wav
knock_door.wav
door_open.wav
item_pick.wav
power_restore.wav
error.wav
sanity_low.wav
```

贴图资源放入 `assets/textures/`，缺失时会使用默认纯色绘制。标准名称见 [assets/ASSET_NAMES.md](assets/ASSET_NAMES.md)，常用文件包括：

```text
ceiling.png
floor.png
wall.png
door.png
door_lab.png
door_classroom.png
door_power.png
door_exit.png
```

## 地图编辑

地图支持 1-4 层。编辑器会优先保存到 `data/floors/floor_1.txt` 到 `data/floors/floor_4.txt`；旧的 [data/map_layout.txt](data/map_layout.txt) 仍作为四层兼容入口。一个字符代表一块 `60cm x 60cm` 地砖。

常用符号：

```text
# 墙
. 地面
@ 玩家出生点
L 实验室门
M 机房门，使用实验室门贴图
C 教室门
G 门卫处门
P 配电室门
E 出口门
1-9 剧情物件，具体含义见 map_layout.txt 顶部说明
```

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
├── main.py
├── src/
│   ├── __init__.py
│   ├── settings.py
│   ├── game.py
│   ├── player.py
│   ├── renderer.py
│   ├── map_data.py
│   ├── interaction.py
│   ├── audio_manager.py
│   ├── ui.py
│   └── ending.py
├── assets/
│   ├── textures/
│   ├── sprites/
│   ├── sounds/
│   └── fonts/
├── data/
├── requirements.txt
└── README.md
```
## 开发者地图编辑器

运行：

```bash
python map_editor.py
```

编辑器只用于开发阶段，不会改变 `python main.py` 的游戏入口。主要规则：

- 从左侧工具栏选择或拖出 `Room`，在网格上拖拽生成房间。
- 选中房间后，拖拽房间右下角的小方块可以修改房间大小；拖拽房间内部可以移动房间。
- 右侧属性栏可以编辑房间 `Name` 和 `Number`，这些信息保存到 `data/map_rooms.json`。
- 选择 `Door L/G/C/P/E/M` 后，把门拖到墙上释放；编辑器会吸附到最近的墙格，并把该墙格替换成门符号。
- `M` 是机房门角色，使用实验室门贴图；门类型仍按实验室门、门卫处门、配电室门、出口门、教室门这五类资源管理。
- `Start` 放置玩家出生点，`Obj 1-9` 放置剧情物件，按数字键 `1-9` 切换当前物件编号。
- 右侧可以切换正在编辑的 `1-4` 层，切换前会自动保存当前层。
- 右侧可以输入楼层尺寸 `W/H`，以及初始 `HP`、`SAN`、`电量`。
- 右侧 `Objects` 列表展示 `1-9` 剧情物件编号对应名称。
- `Ctrl+S` 保存，输出当前楼层到 `data/floors/floor_N.txt`，四层会同时同步旧的 `data/map_layout.txt`。

游戏内机制：

- 2-4 层的安全出口门打开后会黑屏弹出“下了楼，就回不来了哦”。
- 选择“走吧”进入下一层，选择“等等”留在当前层。
- 1-3 层下楼后的出生点会自动放在该层安全出口门前。
