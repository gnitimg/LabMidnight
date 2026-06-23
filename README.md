# LabMidnight

> 加班累了是吗 —— 基于 Python + Pygame 的第一人称伪 3D 恐怖解谜 RPG MVP

## 项目简介

`LabMidnight（加班累了是吗）` 是一个 PythonGame 课程 Demo。玩家在凌晨两点的实验楼中醒来，发现整栋楼突然停电。走廊陷入黑暗，手机信号异常，一间本应空无一人的教室里传来老师讲课声。

玩家需要依靠手电筒探索实验楼四层局部区域，收集钥匙、纸条、保险丝、门禁卡等道具，破解实验室、异常教室、配电室和出口门禁组成的轻量谜题流程，在理智值耗尽前离开实验楼。

## 已实现内容

- Pygame 窗口、主菜单、操作说明、暂停、背包、成功结局、失败结局
- 2D 网格地图 + Raycasting 第一人称伪 3D 渲染
- W/S 前进后退，A/D 或鼠标移动左右转向
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
| A / D | 向左 / 向右转向 |
| 鼠标移动 | 左右移动视角 |
| Space | 交互、开门、拾取、查看线索 |
| 鼠标左键 | 交互或确认 |
| 鼠标右键 | 开关手电筒 |
| B / I | 打开或关闭背包 |
| ESC | 暂停或返回 |

不使用 F 键交互；Space 不用于跳跃。

## 运行方式

```bash
pip install -r requirements.txt
python main.py
```

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
