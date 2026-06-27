# 蚊虫动态干扰实体系统设计

## 1. 系统目标

蚊虫系统用于给现有第一人称伪 3D 恐怖解谜流程增加动态压力。蚊子不是地图静态贴图，而是存在于二维地图坐标中的运行时实体，会生成、移动、追踪、绕路、发声、被屏幕点击命中、受伤、死亡，并在接近玩家时扣除 SAN。

系统保持现有 Pygame + Raycasting 技术路线，不引入真 3D、复杂怪物模型、网络服务或大型第三方依赖。

## 2. 为什么是动态干扰实体

蚊子不承担传统怪物的主战斗职责，也不阻挡玩家移动。它的定位是干扰：

- 在停电、黑暗、低 SAN 等条件下提高出现概率；
- 通过嗡嗡声的距离和左右声像制造方向压力；
- 通过接近后的 SAN 扣减影响玩家状态；
- 通过“当前 SAN = 攻击力”的规则形成压力循环；
- 数量受 `MOSQUITO_MAX_ACTIVE` 和 `MOSQUITO_MAX_PER_FLOOR` 限制，避免变成弹幕战斗。

## 3. 状态机

实体定义在 `src/systems/mosquito_system.py`：

- `MosquitoState.WANDER`：随机小范围飞行；
- `MosquitoState.CHASE`：距离玩家较近时尝试寻路接近；
- `MosquitoState.ATTACK`：进入攻击距离并等待 cooldown；
- `MosquitoState.DEAD`：HP 归零后移除。

核心阈值：

- `distance > 8`：游荡；
- `0.75 < distance <= 8`：追踪；
- `distance <= MOSQUITO_ATTACK_RANGE`：攻击；
- `hp <= 0`：死亡。

追踪使用轻量 BFS 网格寻路，格子可通行性由墙和关闭门决定。关闭门会被视为不可通行；若找不到到玩家所在格子的路线，蚊子退回随机游荡。

每层第一次载入时，系统会预生成少量“潜伏点”。这些点只是候选坐标，不是立即存在的蚊子。真正生成时仍受当前同时存在数量、每层累计数量、生成间隔和环境概率限制；若潜伏点当前不可用，则回退到玩家附近随机生成。

## 4. 世界坐标到屏幕坐标

蚊子以二维世界坐标 `(x, y)` 存在。渲染时计算：

```python
dx = mosquito.x - player.x
dy = mosquito.y - player.y
distance = hypot(dx, dy)
world_angle = atan2(dy, dx)
relative_angle = normalize_angle(world_angle - player.angle)
```

若 `abs(relative_angle)` 超出视野范围，或距离超过 `MOSQUITO_VISIBLE_DISTANCE`，则不绘制。

屏幕 x 使用 raycasting 相同投影距离：

```python
screen_x = HALF_WIDTH + tan(relative_angle) * DISTANCE_TO_PROJECTION
```

大小随距离缩放：

```python
screen_size = clamp(int(220 / max(distance, 0.35)), 8, 96)
```

y 轴以 horizon 为中心并叠加轻微正弦浮动，让飞行有小幅抖动感。

## 5. Depth Buffer 遮挡

`RaycastingRenderer.render()` 在墙体 raycasting 阶段生成 `depth_buffer`。动态实体在墙和静态物体之后、打开门之前绘制。

蚊子投影到屏幕后，根据 `screen_x` 找到对应 ray：

```python
ray_index = int(screen_x / SCREEN_WIDTH * NUM_RAYS)
near_depth = min(depth_buffer[ray_index - 2 : ray_index + 3])
```

如果：

```python
distance > near_depth + 0.25
```

说明墙或关闭门在蚊子前方，蚊子不显示，也不能被鼠标命中。

## 6. 鼠标屏幕空间命中

renderer 每帧把可见蚊子的 `screen_rect` 写回 `Mosquito` 实体。左键点击时：

1. 只检查 `visible == True` 且 `screen_rect != None` 的蚊子；
2. 使用 `screen_rect.collidepoint(mouse_pos)`；
3. 多只命中时选择离玩家最近的一只；
4. 命中后扣血并播放 hit 音效；
5. HP 归零则移除实体并播放 death 音效。

Space 仍只执行原有交互，不攻击蚊子。

## 7. SAN 作为攻击力

玩家攻击蚊子的伤害在 `MosquitoSystem.handle_mouse_attack()` 中计算：

```python
damage = int(game.player.sanity)
```

这条规则不消耗 SAN。它让玩家当前状态直接影响清除干扰的效率：

- SAN 100：150 HP 蚊子需要 2 次；
- SAN 75：150 HP 蚊子需要 2 次；
- SAN 50：150 HP 蚊子需要 3 次；
- SAN 更低时，击杀效率继续下降。

蚊子 HP 定义为：

```python
MOSQUITO_HP = 150
```

## 8. 距离衰减和角度声像

系统每帧从活着的蚊子中选择威胁最高的一只作为主 buzz 声源：

```python
threat = (1.0 / max(distance, 0.1)) + (0.35 if mosquito.visible else 0.0)
```

距离衰减：

```python
distance_factor = clamp(1.0 - distance / MOSQUITO_AUDIO_DISTANCE, 0.0, 1.0)
base_volume = 0.08 + 0.72 * (distance_factor ** 1.4)
```

左右声道：

```python
pan = sin(relative)
left = base_volume * (1.0 - max(0.0, pan) * 0.75)
right = base_volume * (1.0 + min(0.0, pan) * 0.75)
```

- 蚊子在右侧：右声道更明显；
- 蚊子在左侧：左声道更明显；
- 正前方：左右接近；
- 正后方：左右接近，并整体乘以 `0.55`，模拟更闷、更低的听感。

Pygame mixer 不做实时滤波，当前版本用音量衰减模拟后方闷低感。

## 9. 数值表

| 常量 | 数值 |
|---|---:|
| `MOSQUITO_HP` | 150 |
| `MOSQUITO_MAX_ACTIVE` | 10 |
| `MOSQUITO_MAX_PER_FLOOR` | 6 |
| `MOSQUITO_SPAWN_INTERVAL_MIN` | 8.0 |
| `MOSQUITO_SPAWN_INTERVAL_MAX` | 15.0 |
| `MOSQUITO_BASE_SPEED` | 1.65 |
| `MOSQUITO_BURST_SPEED_MULTIPLIER` | 2.20 |
| `MOSQUITO_ORBIT_RANGE` | 2.25 |
| `MOSQUITO_BITE_INTENT_RANGE` | 5.5 |
| `MOSQUITO_LUNGE_SPEED_MULTIPLIER` | 3.00 |
| `MOSQUITO_ATTACK_RANGE` | 1.30 |
| `MOSQUITO_ATTACK_SAN_DAMAGE` | 18 |
| `MOSQUITO_ATTACK_COOLDOWN` | 1.6 |
| `MOSQUITO_HIT_RADIUS_SCREEN` | 36 |
| `MOSQUITO_VISIBLE_DISTANCE` | 16.0 |
| `MOSQUITO_AUDIO_DISTANCE` | 12.0 |

## 10. 测试方法

命令行自检：

```bash
python -m compileall .
```

运行检查：

```bash
python main.py
```

游戏内检查：

1. 开始游戏后等待 8-15 秒，确认蚊子会生成；
2. 观察蚊子在视野中随距离缩放，并有亮边、血条和短拖尾；
3. 切换楼层后等待生成，确认该层会使用预生成潜伏点激活蚊子；
4. 躲到墙或关闭门后，确认蚊子不明显穿墙显示；
5. 左键点击蚊子，确认伤害等于当前 SAN；
6. SAN 100 时 150 HP 蚊子需要两次击杀；
7. 让蚊子贴近玩家，确认 SAN 扣减、提示、咬击音效和 SAN 条红色动画；
8. 站在蚊子左/右侧，确认 buzz 左右声道差异；
9. 打开门后再次点击门，确认门可关闭，蚊子不能穿过关闭门。
