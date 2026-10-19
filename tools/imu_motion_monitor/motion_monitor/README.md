# motion_monitor — 大腿 IMU 方向 / 低姿态监测原型

独立实现，**不导入、不修改 DIP 根目录的任何代码或记录**。只使用 Python 标准库。
Standalone prototype; it imports nothing from the DIP root and modifies no root file. Standard library only.

它做两件事 / It does two things:

1. **实时运动方向**：输出相对启动朝向的航向，单位度。
   Real-time motion direction: heading relative to the start-up orientation, in degrees.
2. **低姿态 / 静止候选**：检测大腿是否降到低姿态，并用“5 秒内有没有继续移动”区分
   “蹲/爬候选”和“疑似躺倒”。
   Low-posture / immobility candidate: detect a lowered thigh and use "any movement within 5 s"
   to separate a crouch/crawl candidate from a lying candidate.

> 这不是安全认证设备，不能替代 PASS、无线电、人工确认或任何生命安全的唯一依据。
> This is not safety-certified and must not be the sole basis for a life-safety decision.

---

## 1. 先看边界 / Read this first

| 说法 / Claim | 本原型的实际含义 / What this prototype actually means |
|---|---|
| direction（方向） | **相对启动朝向**的航向；停止时冻结，低姿态时隐藏；不是绝对地图方向，不是磁北。 |
| 佩戴位置下降 | 用**大腿长轴相对竖直的倾角**作为代理；单 IMU 不能测绝对高度。 |
| crouching（蹲/爬） | 低姿态 + 最近 `immobile_s` 内有运动；可能是蹲、爬、跪、坐下。 |
| lying（躺倒） | 低姿态 + 连续 `immobile_s` 无运动；是**候选**，不是确认。 |
| 5 秒 | 默认 `--immobile-s 5`，按你的要求设置；这是演示起点，不是验证过的现场参数。 |
| 休息排除 | 你假设“休息的人会脱下设备”；本代码**不验证**这个假设。设备没脱时，坐着不动也会报警。 |

### 为什么方向不是绝对的 / Why direction is not absolute

- 六轴 IMU 没有绝对航向观测；陀螺积分给出相对转角，误差会随时间累积。
  六轴/6-axis has no absolute heading; gyro integration gives relative rotation and drifts.
- 本原型只用**世界竖直轴角速度**积分航向，不把加速度计当航向观测。
  It integrates only world-vertical angular rate; the accelerometer is never a heading observation.
- 大腿在走路时会摆动，瞬时航向会抖；停止后冻结，低姿态时不给方向。
  The thigh swings during gait, so the instantaneous heading wobbles; it is frozen when still and
  hidden in low posture.
- 现有的 L 形录制（计划 90° 右转）回放得到约 90° 的净转角，末值约 **−77°**；直线 3 m 录制
  的航向变化约 **−3°..+16°**。这些是相对航向，不是绝对精度。
  Replay of the L-path gives about a 90° net turn and a final value near −77°; the straight 3 m
  recording varies about −3°..+16°. These are relative headings, not absolute accuracy.

### 为什么“低姿态”不是“高度” / Why low posture is not height

单大腿 IMU 的静态重力只能给出大腿段的两个倾角自由度，不能给出绝对高度。
A single thigh IMU gives two tilt degrees of freedom from gravity, not absolute height.

- 站立：大腿长轴接近竖直，倾角约 0–10°。
- 蹲/坐/躺：大腿接近水平，倾角约 70–90°。
- 这是**姿态代理**，不是“设备下降了多少米”。上下楼梯、站到低处不会触发；反过来，
  坐着、跪着、蹲着不动可能触发。需要真实高度时必须增加气压计、UWB 或其它参考。
  This is a posture proxy, not "how many metres the device descended". Stairs or a lower floor do
  not trigger it; sitting, kneeling or a still crouch can. True height needs a barometer, UWB or
  another reference.

---

## 2. 状态机 / State machine

| 状态 / State | 条件 / Condition | 含义 / Meaning |
|---|---|---|
| `WARMUP` | 还没有找到连续 2 s 的直立静止段 | 等待站稳；不做判断 |
| `UPRIGHT` | 大腿倾角低于退出阈值 50° | 直立/接近直立 |
| `LOW_CHECKING` | 倾角 ≥ 60°，且无运动不足 5 s | 已进入低姿态，正在等“有没有继续移动” |
| `LOW_MOVING` | 倾角 ≥ 60°，最近 5 s 内有运动 | 蹲/爬/跪/坐着的活动候选 |
| `LOW_STILL` | 倾角 ≥ 60°，连续 5 s 无运动 | 疑似躺倒/失能候选 |
| `NO_DATA` | 超过 0.5 s 没有新包 | 不沿用旧状态 |

进入低姿态用 60°，退出用 50°（滞回），避免在阈值附近抖动。5 秒计时从**进入低姿态**开始；
中途检测到运动就重置。`LOW_STILL` 后再次运动，会回到 `LOW_MOVING`。
Entry 60°, exit 50° hysteresis. The 5 s timer starts at low-posture entry and resets on movement.
Movement after `LOW_STILL` returns to `LOW_MOVING`.

### 这个 5 秒规则的真实风险 / Real risks of the 5 s rule

- 消防员蹲着不动 5 秒很常见：观察、听指令、处理伤员、等待。会被判成 `LOW_STILL`。
  A firefighter can easily stay crouched and still for 5 s; it will be labelled `LOW_STILL`.
- 坐着休息、跪下、靠墙滑坐，也可能满足“低姿态 + 静止”。你假设休息会脱设备，但这不是
  硬件能验证的事实。设备没脱时就是误报。
  Sitting, kneeling or sliding down a wall can also satisfy low + still. The "rest removes the
  device" assumption is not something the IMU can verify; if the device stays on, this is a false
  positive.
- 反过来，昏迷但大腿仍接近竖直（靠墙、半跪、被物体支撑）不会触发；屈膝躺下也可能不触发。
  Conversely, an unconscious person whose thigh stays near vertical, or lies with bent knees, may
  not trigger.
- 如果用于真实安全告警，建议把 `--immobile-s` 调到 15–30 s，并增加人工确认/取消；5 s 只适合
  演示“规则能跑通”。
  For a real alert, use 15–30 s and add human confirmation/cancel; 5 s is a demo setting.

---

## 3. 快速开始 / Quick start

在 `imu_motion_monitor/` 目录运行 / Run from the `imu_motion_monitor/` directory:

```powershell
# 终端实时显示；默认 UDP 9000，与现有固件端口一致
python -m motion_monitor.live --port 9000

# 可选：Tkinter 方向箭头 + 状态面板
python -m motion_monitor.dashboard --port 9000

# 没有硬件时：合成数据 -> 另一个端口，避免和真实接收器冲突
python -m motion_monitor.demo_feed --port 9100
python -m motion_monitor.live --port 9100
# 或
python -m motion_monitor.dashboard --port 9100

# 离线回放一份录制（只读 packets.jsonl）
python -m motion_monitor.replay --recording <录制目录>

# 单元测试
python -m unittest discover -s motion_monitor/tests -v
```

注意 / Notes:

- 不要和同端口的其他接收器同时监听 9000；先关闭其中一个（例如本地 DIP 的
  `live_zupt_receiver.py`）。
  Do not run another receiver on port 9000 at the same time; close it first (for example the
  local DIP `live_zupt_receiver.py`).
- 开始时要**直立站稳约 2 秒**，让程序找到静止段并标定陀螺零偏；如果一开始在走/在躺，
  会一直显示 `WARMUP`，直到出现连续 2 秒的直立静止段。
  Start by standing upright and still for about 2 s. If you start walking or lying, it stays in
  `WARMUP` until a 2 s upright still window appears.
- 桌面/非佩戴测试可能一直停在 `WARMUP`：代码要求“直立静止”才标定，桌面平放不算直立。
  这是有意的，不是故障；真实佩戴测试请先站稳。
  A table/non-worn test may stay in `WARMUP`: calibration requires upright stillness, and a board
  lying flat is not upright. This is intentional, not a fault; stand upright for a worn test.
- `--csv path.csv` 可保存逐包状态；`--duration 60` 可限制录制时长。
  `--csv` saves per-packet status; `--duration` limits the run.

---

## 4. 文件 / Files

```text
motion_monitor/
  core.py          # 姿态、航向积分、低姿态/运动状态机
  protocol.py      # DIP IMU 包只读解析
  live.py          # UDP 实时终端
  dashboard.py     # 可选 Tkinter 仪表盘
  replay.py        # 离线回放 packets.jsonl
  demo_feed.py     # 合成 UDP 数据源
  tests/
    test_core.py   # 10 项合成测试
  README.md
```

本包不导入仓库其它模块（`backend/`、`tools/uwb/` 等）；`replay.py` 只在你显式给出路径时
只读 `packets.jsonl`。没有修改任何其它文件或原始录制。
The package does not import other repository modules; `replay.py` only reads `packets.jsonl` when
you pass a path. No other file or raw recording is modified.

---

## 5. 算法 / Algorithm

### 5.1 坐标与安装 / Frames and mounting

与 DIP 当前确认的名义安装一致 / matches the currently confirmed nominal mounting:

```text
sensor +X -> body +z (up)
sensor +Y -> body +y (left)
sensor +Z -> body -x (back)
R_BS = ((0, 0, -1),
        (0, 1,  0),
        (1, 0,  0))
```

世界系 +z 向上；航向 0 是启动时的 body 朝向。`R_BS` 是名义映射，不是精密安装标定；
绑带转动、模块滑动会改变结果。
World +z is up; heading zero is the body heading at start. `R_BS` is nominal, not a precision
mounting calibration; strap rotation or a loose module changes the result.

### 5.2 倾角与低姿态 / Tilt and low posture

```text
body_force = R_BS * accel
tilt = angle(body_force, body +z)
```

静止时 `tilt` 就是大腿长轴相对竖直的夹角。低通时间常数 0.4 s，进入 60°、退出 50°。
At rest this is the thigh long-axis angle from vertical. 0.4 s low-pass, enter 60°, exit 50°.

### 5.3 航向 / Heading

- Mahony 互补滤波只用于**倾角**；加速度计不参与航向。
  Mahony complementary filter is used for tilt only; the accelerometer never updates heading.
- 航向只积分**世界竖直轴**的测量角速度：
  `world_rate = R(q) * (gyro - bias)`, `heading += world_rate.z * dt`。
  Heading integrates only the measured world-vertical rate.
- 只在“有运动且不是低姿态”时积分；静止时冻结，低姿态时冻结。
  Integrate only while moving and not in low posture; freeze when still or low.
- 因此航向穿过蹲/躺的大角度姿态变化时不会被 Euler 奇异性直接翻掉；但低姿态期间的转身
  不会被记录，站起来后仍是低姿态前的相对航向。这是有意的保守处理。
  This avoids Euler flips through large posture changes, but turns made while low are not
  recorded; after standing up the heading is still the pre-low relative heading. This is
  deliberate conservatism.

### 5.4 运动检测 / Motion detection

```text
gyro_rate = |gyro - bias|
accel_dynamic = ||accel|| - g
moving = lowpass(gyro_rate) > 0.12 rad/s
      or lowpass(accel_dynamic) > 0.35 m/s^2
```

阈值是可调演示起点，不是从多受试者数据得到的验收值。低姿态下做精细动作、但大腿几乎不动，
可能被判成“无运动”；躺着发抖可能被判成“有运动”。
Thresholds are tunable demo starting points, not multi-subject validated values. Fine hand work
with a nearly still thigh may look "no motion"; trembling while lying may look "moving".

### 5.5 启动、断流与无效数据 / Startup, gaps and invalid data

- 启动标定要求连续 `warmup_s`（默认 2 s）的**直立静止**样本；否则继续等待。
  Startup calibration requires a continuous upright still window (2 s default).
- 节点时间间隔 >0.5 s 或时间倒退：不跨间断积分，重新进入 `WARMUP`。
  Node gap >0.5 s or time reversal: do not integrate; re-enter `WARMUP`.
- 0.5 s 没有新包：`NO_DATA`，不沿用旧状态。
  No packet for 0.5 s: `NO_DATA`, never reuse the old state as current.
- 重复/乱序序号：不参与状态更新。
  Duplicate/reordered sequence numbers do not update the state.

---

## 6. 当前验证 / Current validation

已运行 / Run on 2026-10-19:

- `python -m unittest discover -s motion_monitor/tests -v` → **10 tests OK**。
- L 形录制回放：`20261018_212645_195445_live`，全程 `UPRIGHT`，相对航向范围约
  **−93°..+10°**，末值约 **−77°**；与计划 90° 右转同量级，但不是独立航向真值。
- 3 m 直线录制回放：`20261017_221331_355310_live`，全程 `UPRIGHT`，相对航向范围约
  **−3°..+16°**，末值约 **+15°**；包含真实步态摆动、残余零偏和可能的轻微转身。
- 合成 UDP 演示：`UPRIGHT → LOW_MOVING → LOW_CHECKING → LOW_STILL → LOW_MOVING → UPRIGHT`，
  5 秒规则和状态转换按预期工作。
- 单元测试覆盖：直立、低姿态静止、低姿态运动、起身、俯仰循环、相对航向、无数据、断流、
  重复序号。

**没有**真实 crouch/lying 标签数据，没有多受试者、PPE、跌倒、模块脱落、跨佩戴实验。
所以当前只能证明“代码按定义工作”，不能证明“能识别真实躺倒”。
There is **no** labelled real crouch/lying data, no multi-subject/PPE/fall/loose-mount data.
The current evidence shows the code implements the definition, not that it recognises real lying.

---

## 7. 已知限制 / Known limitations

1. **方向是相对的**：没有磁力计/UWB 绝对参考；航向误差会累积。
   Direction is relative; no magnetometer/UWB absolute reference; error accumulates.
2. **低姿态 ≠ 高度**：不能测“下降了几米”；楼梯/平台不触发，坐/跪可能误触发。
   Low posture is not height; stairs do not trigger, sitting/kneeling can.
3. **单大腿不能唯一区分坐/蹲/跪/躺**：躯干和小腿不在观测内。
   A single thigh cannot uniquely separate sitting/crouching/kneeling/lying; torso and shank are
   not observed.
4. **5 秒太短**：蹲着不动、坐着休息、处理伤员都可能误报；建议现场用 15–30 s 并加人工确认。
   5 s is short; use 15–30 s and human confirmation for field use.
5. **“休息会脱设备”是假设**：代码无法验证设备是否还佩戴；设备放在桌上也可能触发。
   "Rest removes the device" is an assumption; the code cannot verify wearing, and a device on a
   table can also trigger.
6. **安装与滑动**：名义 `R_BS`；绑带转动、模块松动会同时破坏倾角和航向。
   Nominal `R_BS`; strap rotation or a loose module corrupts both tilt and heading.
7. **不是安全认证**：没有冗余、没有失效保护、没有告警升级流程；不能作为唯一安全依据。
   Not safety-certified; no redundancy, fail-safe or escalation process.
8. **多人/节点关联**：本原型只处理一个发送者；多节点关联、时钟同步、UWB 融合不在范围内。
   Single sender only; multi-node association, clock sync and UWB fusion are out of scope.
9. **方向是身体前向，不是瞬时速度矢量**：正常向前走时两者近似一致；倒退、横走、爬行时
   不能用它代表实际位移方向。
   Direction is body-forward heading, not the instantaneous velocity vector. It matches normal
   forward walking; backward, sideways or crawling motion is not represented correctly.
10. **低姿态时方向被隐藏**：大腿接近水平时航向不可靠；代码冻结而不是编造。站起来后显示的是
    低姿态前的相对航向；低姿态期间的转身不会被记录。
    Direction is hidden in low posture because a near-horizontal thigh has no reliable heading.
    After standing up the code shows the pre-low relative heading; turns made while low are not
    recorded.

---

## 8. 可调参数 / Tunable options

`live.py` / `dashboard.py` / `replay.py` 共有：

```text
--low-enter-deg 60      # 进入低姿态
--low-exit-deg 50       # 退出低姿态
--immobile-s 5          # 低姿态后无运动多久判 LOW_STILL
--motion-gyro 0.12      # rad/s
--motion-accel 0.35     # m/s^2
--warmup-s 2            # 启动直立静止标定
```

`live.py` / `dashboard.py` 还有 `--port`、`--bind`、`--duration`、`--csv`。
`replay.py` 还有 `--recording`、`--start`、`--end`、`--every`、`--csv`。

调参前先固定一份录制，保留原始数据；不要用“让演示好看”反推阈值。
Fix a recording and keep the raw data before tuning; do not tune thresholds to make a demo look
good.

---

## 9. 安全声明 / Safety statement

本代码输出的是**状态候选**，不是已经确认的“人员躺倒”或“人员安全”。任何真实安全用途都需要：
This code outputs candidates, not a confirmed "person is lying" or "person is safe". Any real
safety use needs:

- 独立冗余（例如躯干 IMU、PASS、无线电、人工确认）；
- 多受试者、PPE、不同佩戴、跌倒/静止/爬行/坐跪的标注数据；
- 漏报/误报指标、检测延迟、失效保护（脱设备、低电量、断流）；
- 明确的告警升级与取消流程。

在这些完成之前，请把它当作**演示和状态提示**，不要称为 safety warning。
Until then, treat it as a demo/status indicator, not a safety warning.
