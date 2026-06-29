# LabMidnight

[]()

> 加班累了是吗 -- 基于 Python + Pygame 的第一人称伪 3D 恐怖解谜 RPG Demo

## 1. 项目概览

`LabMidnight（加班累了是吗）` 是一个 PythonGame 课程项目。玩家在凌晨两点从实验楼四层醒来，停电、讲课声、手电电量、SAN 值和动态蚊虫共同形成压力。玩家需要收集关键物资，恢复三楼供电，确认一楼正门被锁，最后从二楼西侧旧连廊逃离。

| 项目项 | 当前设计 |
|---|---|
| 项目类型 | 第一人称伪 3D 恐怖解谜 RPG Demo |
| 技术路线 | `Python + Pygame + 2D 网格地图 + Raycasting` |
| 场景范围 | 实验楼 1F-4F 局部区域 |
| 核心体验 | 黑暗探索、手电资源、SAN 压力、异常音效、动态蚊虫、道具解谜 |
| 成功路线 | 4F -> 3F -> 1F -> 2F 西侧安全出口 |
| 失败条件 | SAN 降为 0 |
| 结局表现 | 成功/失败视频均先黑场，再淡入播放一次；视频结束停最后一帧 |

## 2. 当前功能

| 模块 | 当前能力 | 关键文件 |
|---|---|---|
| 主循环 | 菜单、暂停、背包、楼层选择、成功/失败状态 | `src/core/game.py` |
| 输入 | WASD、鼠标视角、Space/左键交互、右键手电、F2 画质 | `src/core/game_input.py` |
| 渲染 | Raycasting 墙体、地面、天花板、门、二维贴图物件、动态实体 | `src/rendering/` |
| 地图 | 1F-4F 文本地图和 JSON 元数据 | `data/floors/` |
| 交互 | 门锁、拾取、剧情触发、楼层切换、最终逃离 | `src/systems/interaction_*.py` |
| 状态 | HP、SAN、手电电量、背包、剧情 flag | `src/core/player.py` |
| 蚊虫 | 动态生成、BFS 寻路、追咬、血条、拖尾、空间嗡嗡声 | `src/systems/mosquito_system.py` |
| 音效 | 普通音效、循环环境音、空间声像循环 | `src/systems/audio_manager.py` |
| 结局视频 | 成功/失败 mp4 一次性播放，缺资源 fallback | `src/ui/ending_video.py` |
| 地图编辑器 | 楼层、房间、门、窗、对象、剧情绑定编辑 | `map_editor.py` |

## 3. 运行方式

| 场景 | 命令 |
|---|---|
| 安装依赖 | `pip install -r requirements.txt` |
| 启动游戏 | `python main.py` |
| 启动地图编辑器 | `python map_editor.py` |
| 编译自检 | `python -m compileall main.py map_editor.py src` |

## 4. 操作方式

| 输入 | 功能 | 说明 |
|---|---|---|
| W / S | 前进 / 后退 | 第一人称移动 |
| A / D | 左右平移 | 不负责转向 |
| 鼠标移动 | 控制视角 | 支持水平和有限垂直视角 |
| Space | 交互 | 开门、关门、拾取、查看线索 |
| 鼠标左键 | 攻击可见蚊子 / 普通交互 | 优先攻击命中的蚊子；未命中时执行交互 |
| 鼠标右键 | 开关手电 | 无手电或没电时会提示 |
| B / I | 背包 | 查看已有道具说明 |
| F2 | 画质切换 | 性能 / 平衡 / 清晰 |
| ESC | 暂停或返回 | 结局视频播放完前会拦截退出 |

## 5. 最短通关路线

| 阶段 | 楼层 | 目标 | 关键触发器 / 道具 |
|---|---:|---|---|
| 1 | 4F | 拿手电 | `lab_flashlight` |
| 2 | 4F | 拿楼梯钥匙 | `stair_key` |
| 3 | 4F -> 3F | 使用安全出口下楼 | `E` 出口门 |
| 4 | 3F | 找密码条 | `security_code_648` |
| 5 | 3F | 拿保险丝 | `fuse_cabinet` |
| 6 | 3F | 拿塑料卡片 | `plastic_card_3f` |
| 7 | 3F | 修复配电箱 | `power_box`，需要 `plastic_card` + `fuse` |
| 8 | 3F -> 1F | 坐电梯 | `elevator`，需要三楼供电 |
| 9 | 1F | 查看正门锁 | `lobby_main_exit_locked`，剧情提示 |
| 10 | 1F | 翻登记册 | `lobby_register_note`，获得 `old_corridor_note` |
| 11 | 1F -> 2F | 从安全出口到二楼 | 需要 `old_corridor_note` |
| 12 | 2F | 找工号 276 | `staff_code_276` |
| 13 | 2F | 拿旧连廊通行牌 | `maintenance_pass` |
| 14 | 2F | 试西侧安全出口 | `old_corridor_door`，发现磁吸卡死 |
| 15 | 2F | 拾取废弃工牌 | `utility_badge`，位于西侧小厅 |
| 16 | 2F | 拉下磁吸释放开关 | `magnet_release`，位于西墙 |
| 17 | 2F | 再次检查西侧安全出口 | 触发成功结局 |

详细路线见 [docs/shortest_clear_route.md](docs/shortest_clear_route.md)。

## 6. 动态蚊虫系统

蚊子不是地图静态物体，而是运行时动态实体。它们在二维地图坐标中生成和移动，再由渲染器作为 2.5D billboard 投影到屏幕。

| 设计点 | 当前实现 |
|---|---|
| 定位 | 动态干扰，不是传统战斗怪物 |
| 生成 | 每层生成潜伏点，按时间和环境概率激活 |
| 移动 | 游荡、BFS 追踪、近距离盘旋、冲刺扑咬 |
| 攻击玩家 | 进入攻击距离后扣 5 点 SAN |
| 玩家反击 | 鼠标左键点击可见蚊子 |
| 命中规则 | 只命中 `visible` 且有 `screen_rect` 的蚊子 |
| 伤害规则 | 伤害 = 当前 SAN，不额外消耗 SAN |
| 遮挡 | 使用 raycasting depth buffer，墙体和关闭门可遮挡 |
| 音效 | 选择威胁最高的蚊子播放空间嗡嗡声 |

| 常量 | 当前值 | 含义 |
|---|---:|---|
| `MOSQUITO_HP` | 150 | 单只蚊子 HP |
| `MOSQUITO_MAX_ACTIVE` | 6 | 同时存在上限 |
| `MOSQUITO_MAX_PER_FLOOR` | 6 | 每层累计生成上限 |
| `MOSQUITO_SPAWN_INTERVAL_MIN/MAX` | 8-15 秒 | 后续生成间隔 |
| `MOSQUITO_ATTACK_RANGE` | 1.30 | 叮咬距离 |
| `MOSQUITO_ATTACK_SAN_DAMAGE` | 5 | 每次叮咬扣 SAN |
| `MOSQUITO_VISIBLE_DISTANCE` | 16.0 | 可见投影距离 |
| `MOSQUITO_AUDIO_DISTANCE` | 12.0 | 嗡嗡声衰减距离 |
| `MOSQUITO_TARGET_LOST_DISTANCE` | 50.0 | 超距后放弃追踪 |

详细设计见 [docs/mosquito_system_design.md](docs/mosquito_system_design.md)。

## 7. 结局视频

| 结局 | 视频文件 | 当前播放方式 | fallback |
|---|---|---|---|
| 成功 | `assets/videos/successful.mp4` | 黑场约 1 秒，淡入播放一次，结束停最后一帧 | 静态成功画面 |
| 失败 | `assets/videos/defeat.mp4` | 黑场约 1 秒，淡入播放一次，结束停最后一帧 | 静态失败画面 |

| 规则 | 说明 |
|---|---|
| 不循环 | 视频结束后不从头播放 |
| 输入拦截 | 视频播放完前，成功/失败结局都不响应返回或重开 |
| 资源容错 | 缺少 OpenCV、视频文件或解码失败时不崩溃 |

## 8. 资源清单

| 类型 | 路径 | 说明 |
|---|---|---|
| 墙体贴图 | `assets/textures/` | Raycasting 墙、门、电梯等 |
| 物体贴图 | `assets/objects/<object_id>/` | 黑板、白板、电梯等固定二维贴图 |
| 蚊子精灵 | `assets/sprites/mosquito.png` | 可选；缺失时使用程序绘制 |
| 音效 | `assets/sounds/` | 环境音、交互音、蚊子音效 |
| 结局视频 | `assets/videos/` | `successful.mp4`、`defeat.mp4` |
| 字体 | `assets/fonts/` | 可选；缺失时使用 fallback |

| 蚊子音效 | 作用 |
|---|---|
| `mosquito_buzz.wav` | 空间嗡嗡声 |
| `mosquito_hit.wav` | 被拍中反馈 |
| `mosquito_die.wav` | 死亡反馈 |
| `mosquito_bite.wav` | 叮咬反馈 |

## 9. 地图和物件注意事项

| 对象 | 当前规则 |
|---|---|
| 电梯 | 固定二维贴图；不渲染 3D 侧面和顶面 |
| 黑板 | 固定二维贴图；1F/2F/3F/4F 高度统一为 `height=2.0` |
| 白板 | 固定二维贴图；交互提示为“查看白板背面” |
| 1F 西侧安全出口 | 提示正门/出口已上锁，不触发成功 |
| 2F 西侧安全出口 | 通行牌 + 磁吸释放后触发成功 |
| 2F 磁吸释放 | 先试门，再拿废弃工牌，再拉释放开关 |

## 10. 文档入口

| 文档 | 用途 |
|---|---|
| [docs/development_overview.md](docs/development_overview.md) | 表格版开发文档总览 |
| [docs/mosquito_system_design.md](docs/mosquito_system_design.md) | 蚊虫系统专题设计 |
| [docs/shortest_clear_route.md](docs/shortest_clear_route.md) | 最短通关路线和地图条件检查 |
| [.doc/LabMidnight开发文档.md](.doc/LabMidnight开发文档.md) | 课程提交用开发文档 |
| [.doc/mosquito_system_design.md](.doc/mosquito_system_design.md) | 课程文档目录下的蚊虫系统设计 |

## 11. 验收建议

| 检查项 | 通过标准 |
|---|---|
| 启动 | `python main.py` 能进入主菜单 |
| 编译 | `python -m compileall main.py map_editor.py src` 无错误 |
| 主线 | 能按 4F -> 3F -> 1F -> 2F 路线通关 |
| 手电 | 电量条按 `FLASHLIGHT_MAX=200` 显示 |
| 蚊子 | 能生成、追踪、叮咬、被点击击杀 |
| 遮挡 | 蚊子在墙或关闭门后不可见，不可被点中 |
| 音效 | 蚊子嗡嗡声有距离和左右声道变化 |
| 结局 | 成功/失败视频只播一遍，播放前有黑场淡入 |
| 容错 | 缺少非关键资源时不崩溃 |
