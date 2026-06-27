# 蚊虫动态干扰实体系统设计

## 1. 系统目标

蚊虫系统用于给现有第一人称伪 3D 恐怖解谜流程增加动态压力。蚊子不是地图静态贴图，而是存在于二维地图坐标中的运行时实体，会生成、移动、追踪、绕路、发声、被屏幕点击命中、受伤、死亡，并在接近玩家时扣除 SAN。

系统保持现有 Pygame + Raycasting 技术路线，不引入真 3D、复杂怪物模型、网络服务或大型第三方依赖。

## 2. 为什么是动态干扰实体

蚊子不承担传统怪物的主战斗职责，也不阻挡玩家移动。它的定位是干扰：

- 在停电、黑暗、低 SAN 等条件下提高出现概率；
- 通过嗡嗡声的距离和左右声像制造方向压力；
- 通过接近后的 SAN 扣减影响玩家状态；
- 通过"当前 SAN = 攻击力"的规则形成压力循环；
- 数量受 `MOSQUITO_MAX_ACTIVE` 和 `MOSQUITO_MAX_PER_FLOOR` 限制，避免变成弹幕战斗。

## 3. 状态机

实体定义在 `src/systems/mosquito_system.py`：

| 状态 | 触发条件 | 行为 |
|---|---|---|
| `IDLE` | 初始/重置 | 等待激活，不参与更新 |
| `WANDER` | 距离 > 8 或寻路失败 | 随机小范围飞行，带 flutter 抖动 |
| `CHASE` | 0.75 < 距离 ≤ 50 | BFS 寻路追踪，带轨道偏移和 wiggle |
| `ATTACK` | 距离 ≤ 1.30 | 扣除玩家 SAN，冷却期间减速移动 |
| `DEAD` | HP ≤ 0 | 移除实体，播放死亡音效 |

状态转换在 `_update_mosquito()` 中每帧执行：

```python
distance = mosquito.distance_to_player
if distance > MOSQUITO_TARGET_LOST_DISTANCE:      # 50.0
    state = WANDER
elif distance <= MOSQUITO_ATTACK_RANGE:            # 1.30
    state = ATTACK
elif distance <= MOSQUITO_TARGET_LOST_DISTANCE:
    state = CHASE
```

## 4. 生成与潜伏点

每层第一次载入时，系统预生成 6 个"潜伏点"（`_ensure_lurking_points_for_floor()`）。这些点是候选坐标，要求：

- 在地图可行走区域内
- 距离玩家 > 4.0
- 彼此间距 ≥ 2.5

真正生成时仍受以下限制：

| 限制 | 常量 | 说明 |
|---|---|---|
| 全局同时存在上限 | `MOSQUITO_MAX_ACTIVE` = 10 | 超过则跳过生成 |
| 每层累计上限 | `MOSQUITO_MAX_PER_FLOOR` = 6 | 超过则跳过生成 |
| 生成间隔 | 8.0 ~ 15.0 秒 | 随机 |
| 首次延迟 | 2.0 ~ 4.0 秒 | 每层切换后的首次等待 |
| 环境概率 | 见下表 | 受楼层、供电、手电、SAN 影响 |

### 生成概率计算

```python
floor_base = {4: 0.35, 3: 0.55, 2: 0.75, 1: 0.32}
probability = floor_base[current_floor]
if power_restored:   probability *= 0.65
else:                probability *= 1.25
if flashlight_off:   probability *= 1.15
if sanity < 55:      probability *= 1.0 + (55 - sanity) / 110
# clamp to [0.12, 0.90]
```

生成优先从潜伏点激活，失败则在玩家附近随机生成（先远距离 4-9 格，再近距离 2.6-5.2 格）。

## 5. 移动与寻路

### 游荡

游荡方向每 0.55-1.35 秒随机切换，叠加 flutter 抖动：

```python
flutter = sin(age * 10.0 + id) * 0.55
move_angle = wander_angle + flutter
distance = speed * agility * 0.55 * burst_multiplier * dt
```

### 追踪

追踪使用轻量 BFS 网格寻路（`_find_path()`），格子可通行性由墙和关闭门决定。寻路每 0.25-0.45 秒刷新一次。

追踪移动叠加：

- **wiggle** — 双频正弦抖动，模拟蚊子飞行的不规则性
- **orbit** — 靠近玩家时偏移轨道方向，模拟盘旋
- **bite_commit** — 极近距离时放弃轨道，直扑玩家
- **burst** — 随机加速冲刺（持续 0.28-0.55 秒，冷却 1.25-2.2 秒）

### 追踪速度倍率

| 距离 | 倍率 |
|---|---|
| > 7.0 | 1.90 |
| > 3.0 | 1.85 |
| > 1.30 | 1.70 |
| ≤ 1.30 | 0.80 |

### 冲刺倍率

冲刺期间乘以 `MOSQUITO_BURST_SPEED_MULTIPLIER` = 2.20，叠加脉冲抖动：

```python
pulse = 0.82 + 0.18 * abs(sin(age * 24.0 + id))
return 2.20 * pulse
```

## 6. 世界坐标到屏幕坐标

蚊子以二维世界坐标 `(x, y)` 存在。渲染时计算：

```python
dx = mosquito.x - player.x
dy = mosquito.y - player.y
distance = hypot(dx, dy)
world_angle = atan2(dy, dx)
relative_angle = normalize_angle(world_angle - player.angle)
```

若 `abs(relative_angle)` 超出视野范围，或距离超过 `MOSQUITO_VISIBLE_DISTANCE`（16.0），则不绘制。

屏幕 x 使用 raycasting 相同投影距离：

```python
screen_x = HALF_WIDTH + tan(relative_angle) * DISTANCE_TO_PROJECTION
```

大小随距离缩放：

```python
screen_size = clamp(int(220 / max(distance, 0.35)), 8, 96)
```

y 轴以 horizon 为中心并叠加轻微正弦浮动，让飞行有小幅抖动感。

## 7. Depth Buffer 遮挡

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

## 8. 鼠标屏幕空间命中

renderer 每帧把可见蚊子的 `screen_rect` 写回 `Mosquito` 实体。左键点击时：

1. 只检查 `visible == True` 且 `screen_rect != None` 的蚊子；
2. 使用 `screen_rect.collidepoint(mouse_pos)`；
3. 多只命中时选择离玩家最近的一只；
4. 命中后扣血并播放 `mosquito_hit` 音效；
5. HP 归零则移除实体并播放 `mosquito_die` 音效。

Space 仍只执行原有交互，不攻击蚊子。

## 9. SAN 作为攻击力

玩家攻击蚊子的伤害在 `MosquitoSystem.handle_mouse_attack()` 中计算：

```python
damage = int(game.player.sanity)
```

这条规则不消耗 SAN。它让玩家当前状态直接影响清除干扰的效率：

| 当前 SAN | 蚊子 HP | 击杀次数 |
|---|---:|---:|
| 100 | 150 | 2 次 |
| 75 | 150 | 2 次 |
| 50 | 150 | 3 次 |
| 30 | 150 | 5 次 |

蚊子 HP 定义为：

```python
MOSQUITO_HP = 150
```

## 10. 距离衰减和角度声像

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

## 11. 数值表

| 常量 | 数值 | 说明 |
|---|---:|---|
| `MOSQUITO_HP` | 150 | 蚊子生命值 |
| `MOSQUITO_MAX_ACTIVE` | 10 | 全局同时存在上限 |
| `MOSQUITO_MAX_PER_FLOOR` | 6 | 每层累计上限 |
| `MOSQUITO_SPAWN_INTERVAL_MIN` | 8.0 | 最小生成间隔（秒） |
| `MOSQUITO_SPAWN_INTERVAL_MAX` | 15.0 | 最大生成间隔（秒） |
| `MOSQUITO_BASE_SPEED` | 1.65 | 基础移动速度 |
| `MOSQUITO_BURST_SPEED_MULTIPLIER` | 2.20 | 冲刺速度倍率 |
| `MOSQUITO_ORBIT_RANGE` | 2.25 | 轨道偏移范围 |
| `MOSQUITO_BITE_INTENT_RANGE` | 5.5 | 直扑意图范围 |
| `MOSQUITO_LUNGE_SPEED_MULTIPLIER` | 3.00 | 突刺速度倍率 |
| `MOSQUITO_ATTACK_RANGE` | 1.30 | 攻击距离 |
| `MOSQUITO_ATTACK_SAN_DAMAGE` | 18 | 每次攻击 SAN 扣减 |
| `MOSQUITO_ATTACK_COOLDOWN` | 1.6 | 攻击冷却（秒） |
| `MOSQUITO_HIT_RADIUS_SCREEN` | 36 | 屏幕点击命中半径（像素） |
| `MOSQUITO_VISIBLE_DISTANCE` | 16.0 | 可见距离上限 |
| `MOSQUITO_AUDIO_DISTANCE` | 12.0 | 音频距离上限 |
| `MOSQUITO_CHASE_DISTANCE` | 8.0 | 追踪触发距离 |
| `MOSQUITO_TARGET_LOST_DISTANCE` | 50.0 | 放弃追踪距离 |

## 12. 音效资源

蚊子系统使用以下音效：

| 音效键 | 文件名 | 用途 |
|---|---|---|
| `mosquito_buzz` | `mosquito_buzz.wav` | 持续嗡嗡声（空间声像） |
| `mosquito_hit` | `mosquito_hit.wav` | 被拍中音效 |
| `mosquito_die` | `mosquito_die.wav` | 死亡音效 |
| `mosquito_bite` | `mosquito_bite.wav` | 蚊子咬击音效 |

音效文件放入 `assets/sounds/`，缺失时 AudioManager 会静默跳过。

## 13. 测试方法

### 编译检查

```bash
python -m compileall .
```

### 运行检查

```bash
python main.py
```

### 游戏内检查清单

| 序号 | 检查项 | 预期结果 |
|---|---|---|
| 1 | 开始游戏后等待 8-15 秒 | 蚊子生成 |
| 2 | 观察蚊子在视野中 | 随距离缩放，有亮边、血条和短拖尾 |
| 3 | 切换楼层后等待生成 | 该层会使用预生成潜伏点激活蚊子 |
| 4 | 躲到墙或关闭门后 | 蚊子不明显穿墙显示 |
| 5 | 左键点击蚊子 | 伤害等于当前 SAN |
| 6 | SAN 100 时测试 | 150 HP 蚊子需要两次击杀 |
| 7 | 让蚊子贴近玩家 | SAN 扣减、提示、咬击音效和 SAN 条红色动画 |
| 8 | 站在蚊子左/右侧 | buzz 左右声道差异 |
| 9 | 打开门后再次点击门 | 门可关闭，蚊子不能穿过关闭门 |
