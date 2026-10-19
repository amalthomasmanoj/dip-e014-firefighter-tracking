"""实时运动方向 + 低姿态/静止候选状态机。
Real-time motion direction plus a low-posture / immobility candidate state machine.

定义 / Definitions
------------------
- direction（方向）: 相对本次启动朝向的平滑航向；不是绝对地图方向。
  Direction: smoothed heading relative to the heading at start-up, not an absolute map bearing.
- low posture（低姿态）: 大腿长轴相对竖直方向的倾角超过阈值。它是“佩戴位置降低”的
  姿态代理，不是绝对高度测量。
  Low posture: thigh long-axis angle from vertical above a threshold. This is a posture proxy
  for a lowered wearing position, not an absolute height measurement.
- crouching（蹲/爬）: 低姿态且最近 `immobile_s` 内检测到运动。
  Crouching: low posture with movement inside the last `immobile_s`.
- lying candidate（疑似躺倒）: 低姿态且连续 `immobile_s` 没有运动迹象。
  Lying candidate: low posture with no movement for `immobile_s`.

重要限制 / Important limits
---------------------------
- 六轴 IMU 没有绝对航向；航向会漂移，且大腿摆动会让瞬时航向抖动。
  A six-axis IMU has no absolute heading; yaw drifts and the thigh swing makes it wobble.
- 单大腿 IMU 不能测绝对高度，也不能单独区分坐、蹲、跪、躺。本模块输出的是候选状态。
  A single thigh IMU cannot measure absolute height or uniquely separate sitting, crouching,
  kneeling and lying. The output is a candidate state.
- 这不是安全认证设备，不能替代 PASS、无线电或人工确认。
  This is not safety-certified and is not a replacement for PASS, radio or human confirmation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

GRAVITY = 9.80665

# 传感器系 -> 身体系；与 DIP 根目录当前确认的名义安装一致。
# sensor -> body; matches the currently confirmed nominal mounting in the DIP root.
# sensor +X -> body +z (up), +Y -> body +y (left), +Z -> body -x (back).
R_BS = (
    (0.0, 0.0, -1.0),
    (0.0, 1.0, 0.0),
    (1.0, 0.0, 0.0),
)

STATE_LABELS = {
    "WARMUP": "WARMUP",
    "UPRIGHT": "UPRIGHT",
    "LOW_CHECKING": "LOW POSTURE (checking)",
    "LOW_MOVING": "CROUCHING (candidate)",
    "LOW_STILL": "LYING (candidate)",
    "NO_DATA": "NO DATA",
}


def _vector3(value: Sequence[float], name: str) -> tuple[float, float, float]:
    """校验并转换为三元浮点向量。/ Validate and convert a 3-vector to floats."""
    if len(value) != 3:
        raise ValueError(f"{name} must have three components")
    out = (float(value[0]), float(value[1]), float(value[2]))
    if not all(math.isfinite(x) for x in out):
        raise ValueError(f"{name} must be finite")
    return out


def _norm(value: Sequence[float]) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in value))


def _unit(value: Sequence[float]) -> tuple[float, float, float]:
    n = _norm(value)
    if n < 1e-12:
        raise ValueError("cannot normalize a zero vector")
    return tuple(float(x) / n for x in value)  # type: ignore[return-value]


def mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> tuple[float, float, float]:
    """矩阵乘向量，行主序。/ Matrix-vector product, row-major."""
    return tuple(sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def mat_t_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> tuple[float, float, float]:
    """矩阵转置乘向量。/ Transpose(matrix) times vector."""
    return tuple(sum(matrix[j][i] * vector[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def q_normalize(q: Sequence[float]) -> tuple[float, float, float, float]:
    if len(q) != 4:
        raise ValueError("quaternion must have four components")
    values = tuple(float(x) for x in q)
    if not all(math.isfinite(x) for x in values):
        raise ValueError("quaternion must be finite")
    n = math.sqrt(sum(x * x for x in values))
    if n < 1e-12:
        raise ValueError("zero quaternion")
    return tuple(x / n for x in values)  # type: ignore[return-value]


def q_multiply(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float, float]:
    """Hamilton 四元数乘法 (w, x, y, z)。
    Hamilton quaternion product.

    输入不强制单位化：q_dot = 0.5 * q * (0, omega) 中的第二个四元数不是单位四元数。
    Inputs are not normalized: the second quaternion in q_dot = 0.5 * q * (0, omega) is not unit.
    """
    aw, ax, ay, az = (float(x) for x in a)
    bw, bx, by, bz = (float(x) for x in b)
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def q_to_matrix(q: Sequence[float]) -> tuple[tuple[float, ...], ...]:
    """四元数 (w, x, y, z) 转 body->world 旋转矩阵。/ Quaternion to body-to-world matrix."""
    w, x, y, z = q_normalize(q)
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
        (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
        (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)),
    )


def q_rotate(q: Sequence[float], vector: Sequence[float]) -> tuple[float, float, float]:
    """把 body 系向量旋转到 world 系。/ Rotate a body-frame vector into the world frame."""
    return mat_vec(q_to_matrix(q), vector)


def q_align_body_z(q: Sequence[float], body_vector: Sequence[float]) -> tuple[float, float, float, float]:
    """用重力把 body +z 对齐到 world +z，只影响倾角，不改变航向。
    Align body +z with world +z using gravity; this corrects tilt only, not heading.
    """
    measured = _unit(body_vector)
    world = q_rotate(q, measured)
    dot = max(-1.0, min(1.0, world[2]))
    if dot > 1.0 - 1e-12:
        return q_normalize(q)
    if dot < -1.0 + 1e-12:
        # 完全倒置：绕 body x 轴转 180°。/ Fully inverted: rotate 180 degrees about body x.
        return q_normalize(q_multiply((0.0, 1.0, 0.0, 0.0), q))
    axis = (world[1], -world[0], 0.0)
    axis_norm = _norm(axis)
    if axis_norm < 1e-12:
        return q_normalize(q)
    angle = math.acos(dot)
    half = 0.5 * angle
    scale = math.sin(half) / axis_norm
    delta = (math.cos(half), axis[0] * scale, axis[1] * scale, axis[2] * scale)
    return q_normalize(q_multiply(delta, q))


def q_integrate(q: Sequence[float], omega_body: Sequence[float], dt: float) -> tuple[float, float, float, float]:
    """按 body 角速度右乘积分四元数。/ Integrate the quaternion with body angular rate on the right."""
    if not math.isfinite(dt) or dt <= 0.0:
        return q_normalize(q)
    derivative = q_multiply(q, (0.0, omega_body[0], omega_body[1], omega_body[2]))
    return q_normalize(tuple(q[i] + 0.5 * dt * derivative[i] for i in range(4)))


def yaw_from_quat(q: Sequence[float]) -> float:
    """返回相对航向，单位度；yaw 的零点是初始化时刻的 body 朝向。
    Return relative heading in degrees; zero is the body heading at initialization.

    注意：pitch 接近 ±90° 时 Euler yaw 不稳定，因此对外方向使用 heading_from_quat。
    Note: Euler yaw is ill-conditioned near pitch ±90°, so the public direction uses
    heading_from_quat instead.
    """
    w, x, y, z = q_normalize(q)
    return math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))


def heading_from_quat(q: Sequence[float]) -> float | None:
    """用 body +x 在水平面的投影求航向；投影过短时返回 None。
    Heading from the horizontal projection of body +x; return None when the projection is too short.

    大腿接近水平时 body +x 接近竖直，单 IMU 无法可靠定义航向；这与 Euler 奇异性无关。
    When the thigh is near horizontal, body +x is near vertical and a single IMU cannot define a
    reliable heading; this is not merely an Euler-angle singularity.
    """
    forward = q_rotate(q, (1.0, 0.0, 0.0))
    horizontal = math.hypot(forward[0], forward[1])
    if horizontal < 0.25:
        return None
    return math.degrees(math.atan2(forward[1], forward[0]))


def wrap_deg(angle: float) -> float:
    """把角度折到 [-180, 180)。/ Wrap an angle to [-180, 180)."""
    value = (float(angle) + 180.0) % 360.0 - 180.0
    return 180.0 if value == -180.0 else value


def angle_from_vertical(body_force: Sequence[float]) -> float | None:
    """比力方向与 body +z 的夹角（度）；静止时即大腿相对竖直的倾角。
    Angle in degrees between specific force and body +z; at rest this is thigh tilt from vertical.
    """
    n = _norm(body_force)
    if n < 1e-9:
        return None
    cosine = max(-1.0, min(1.0, float(body_force[2]) / n))
    return math.degrees(math.acos(cosine))


def _alpha(dt: float, tau: float) -> float:
    if tau <= 0.0:
        return 1.0
    return 1.0 - math.exp(-max(0.0, float(dt)) / float(tau))


def _cross(a: Sequence[float], b: Sequence[float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


@dataclass(frozen=True)
class MonitorConfig:
    """可调阈值；默认值只是演示起点，不是经过验证的现场参数。
    Tunable thresholds; defaults are demo starting points, not validated field settings.
    """

    low_enter_deg: float = 60.0       # 进入低姿态的倾角 / enter low posture (degrees)
    low_exit_deg: float = 50.0        # 退出低姿态的倾角 / leave low posture (degrees)
    immobile_s: float = 5.0           # 低姿态后无运动多久判为静止候选 / stillness before candidate
    motion_gyro_radps: float = 0.12   # 角速度运动阈值 / angular-rate motion threshold
    motion_accel_mps2: float = 0.35   # 加速度动态阈值 / acceleration-dynamics threshold
    posture_tau_s: float = 0.40       # 姿态倾角低通时间常数 / posture low-pass time constant
    motion_tau_s: float = 0.25        # 运动量低通时间常数 / motion low-pass time constant
    warmup_s: float = 2.0             # 初始静止标定时间 / initial still calibration time
    max_gap_s: float = 0.50           # 超过此间隔不积分 / do not integrate across a longer gap
    no_data_s: float = 0.50           # 无新包判定超时 / no-fresh-data timeout
    accel_trust_window: float = 0.35  # 重力校正信任窗口 / gravity-correction trust window
    kp: float = 0.5                   # 倾角校正增益 / tilt correction gain

    def __post_init__(self) -> None:
        if not (0.0 < self.low_exit_deg < self.low_enter_deg <= 180.0):
            raise ValueError("require 0 < low_exit_deg < low_enter_deg <= 180")
        if self.immobile_s <= 0.0:
            raise ValueError("immobile_s must be positive")
        if self.motion_gyro_radps <= 0.0 or self.motion_accel_mps2 <= 0.0:
            raise ValueError("motion thresholds must be positive")
        if self.warmup_s < 0.0 or self.max_gap_s <= 0.0 or self.no_data_s <= 0.0:
            raise ValueError("invalid timing parameters")
        if not (0.0 < self.accel_trust_window < 1.0):
            raise ValueError("accel_trust_window must be in (0, 1)")


@dataclass(frozen=True)
class Status:
    """一次监测输出；原始测量不被修改。/ One monitor output; raw measurements are not modified."""

    t_s: float                          # 电脑接收相对秒 / host receive-relative seconds
    node_s: float                       # 节点时间相对秒 / node-relative seconds
    state: str
    label: str
    direction_deg: float | None         # 相对航向 / relative heading
    direction_valid: bool
    posture_deg: float | None           # 低通后的大腿倾角 / low-passed thigh tilt
    posture_raw_deg: float | None
    low_posture: bool
    moving: bool
    motion_score: float                 # 1.0 = 运动阈值 / 1.0 means at threshold
    gyro_rate_radps: float
    accel_dynamic_mps2: float
    immobile_s: float
    low_duration_s: float
    bias_quality: str
    reason: str
    samples: int
    gap_s: float | None = None


class Monitor:
    """把逐包六轴数据转换为方向与低姿态状态。/ Convert per-packet six-axis data into direction and posture status."""

    def __init__(self, config: MonitorConfig | None = None):
        self.config = config or MonitorConfig()
        self.reset()

    def reset(self) -> None:
        """完全重置，包括会话起点。/ Full reset, including the session origin."""
        self.q = (1.0, 0.0, 0.0, 0.0)
        self.bias = (0.0, 0.0, 0.0)
        self.bias_quality = "uncalibrated"
        self.samples = 0
        self.start_host: float | None = None
        self.start_node: float | None = None
        self.last_host: float | None = None
        self.last_node: float | None = None
        self.prev_node: float | None = None
        self.last_seq: int | None = None
        self.warmup = True
        self.warmup_start: float | None = None
        self.warmup_accel: list[tuple[float, float, float]] = []
        self.warmup_gyro: list[tuple[float, float, float]] = []
        self.posture: float | None = None
        self.posture_raw: float | None = None
        self.gyro_lp = 0.0
        self.accel_lp = 0.0
        self.moving = False
        self.heading = 0.0
        self.heading_valid = False
        self.low = False
        self.low_since: float | None = None
        self.last_motion: float | None = None
        self.last_status: Status | None = None

    def _begin_warmup(self, node_s: float, host_s: float) -> None:
        """数据间断后重新初始化姿态与零偏。/ Reinitialize attitude and bias after a data gap."""
        self.q = (1.0, 0.0, 0.0, 0.0)
        self.warmup = True
        self.warmup_start = node_s
        self.warmup_accel = []
        self.warmup_gyro = []
        self.posture = None
        self.posture_raw = None
        self.gyro_lp = 0.0
        self.accel_lp = 0.0
        self.moving = False
        self.heading = 0.0
        self.heading_valid = False
        self.low = False
        self.low_since = None
        self.last_motion = node_s
        self.prev_node = node_s
        self.last_node = node_s
        self.last_host = host_s
        self.last_seq = None

    def _finish_warmup(self, node_s: float, host_s: float) -> None:
        """完成初始静止标定；运动中的标定会标记为 poor。/ Finish initial still calibration; moving data is marked poor."""
        gyro_mean = tuple(
            sum(sample[i] for sample in self.warmup_gyro) / len(self.warmup_gyro)
            for i in range(3)
        )
        accel_mean = tuple(
            sum(sample[i] for sample in self.warmup_accel) / len(self.warmup_accel)
            for i in range(3)
        )
        # 用各轴标准差判断这段是否真的静止；运动时的均值不能当零偏。
        # Use per-axis standard deviation to decide whether the interval was really still.
        still = len(self.warmup_gyro) >= 5
        if still:
            for axis in range(3):
                mean = gyro_mean[axis]
                variance = sum((sample[axis] - mean) ** 2 for sample in self.warmup_gyro) / len(self.warmup_gyro)
                if math.sqrt(max(0.0, variance)) > 0.05:
                    still = False
                    break
        if still and abs(_norm(accel_mean) - GRAVITY) > 0.5:
            still = False
        if still:
            self.bias = gyro_mean  # type: ignore[assignment]
            self.bias_quality = "good"
        else:
            self.bias = (0.0, 0.0, 0.0)
            self.bias_quality = "poor"

        body_accel = mat_vec(R_BS, accel_mean)
        self.q = q_align_body_z((1.0, 0.0, 0.0, 0.0), body_accel)
        self.posture_raw = angle_from_vertical(body_accel)
        self.posture = self.posture_raw
        # 航向从 0 开始，之后只用世界竖直轴角速度积分；不把静止时的 yaw 当绝对方向。
        # Heading starts at zero and is integrated only from world-vertical angular rate;
        # still-period yaw is never treated as an absolute bearing.
        self.heading = 0.0
        self.heading_valid = False
        self.warmup = False
        self.moving = False
        self.prev_node = node_s
        self.last_node = node_s
        self.last_host = host_s
        self.last_motion = node_s
        # 如果一开始就处于低姿态，从判断开始计时；否则直立。
        # If starting low, start the judgement timer now; otherwise upright.
        if self.posture is not None and self.posture >= self.config.low_enter_deg:
            self.low = True
            self.low_since = node_s
        else:
            self.low = False
            self.low_since = None

    def _state(self, node_s: float) -> tuple[str, str, float, float]:
        """返回 (state, reason, immobile_s, low_duration_s)。/ Return state, reason and durations."""
        if self.warmup:
            return "WARMUP", "initial_still_calibration", 0.0, 0.0
        if not self.low:
            return "UPRIGHT", "thigh_above_low_threshold", 0.0, 0.0
        low_duration = max(0.0, node_s - (self.low_since if self.low_since is not None else node_s))
        anchor = max(self.low_since if self.low_since is not None else node_s,
                     self.last_motion if self.last_motion is not None else node_s)
        immobile = max(0.0, node_s - anchor)
        if self.moving:
            return "LOW_MOVING", "low_posture_with_motion", immobile, low_duration
        if immobile >= self.config.immobile_s:
            return "LOW_STILL", "low_posture_no_motion", immobile, low_duration
        return "LOW_CHECKING", "low_posture_waiting_for_motion", immobile, low_duration

    def _status(self, state: str, reason: str, gap_s: float | None = None) -> Status:
        t_s = 0.0
        node_s = 0.0
        if self.start_host is not None and self.last_host is not None:
            t_s = max(0.0, self.last_host - self.start_host)
        if self.start_node is not None and self.last_node is not None:
            node_s = max(0.0, self.last_node - self.start_node)
        _, _, immobile, low_duration = self._state(self.last_node if self.last_node is not None else node_s)
        motion_score = max(
            self.gyro_lp / self.config.motion_gyro_radps if self.config.motion_gyro_radps else 0.0,
            self.accel_lp / self.config.motion_accel_mps2 if self.config.motion_accel_mps2 else 0.0,
        )
        # 低姿态时大腿接近水平，单 IMU 的航向不可靠；这时只给姿态/静止状态，不给方向。
        # In low posture the thigh is near horizontal, so a single-IMU heading is unreliable;
        # show posture/stillness but not a direction.
        direction_ok = self.heading_valid and not self.low and state not in ("NO_DATA", "WARMUP")
        status = Status(
            t_s=t_s,
            node_s=node_s,
            state=state,
            label=STATE_LABELS.get(state, state),
            direction_deg=self.heading if direction_ok else None,
            direction_valid=direction_ok,
            posture_deg=self.posture,
            posture_raw_deg=self.posture_raw,
            low_posture=self.low,
            moving=self.moving,
            motion_score=motion_score,
            gyro_rate_radps=self.gyro_lp,
            accel_dynamic_mps2=self.accel_lp,
            immobile_s=immobile,
            low_duration_s=low_duration,
            bias_quality=self.bias_quality,
            reason=reason,
            samples=self.samples,
            gap_s=gap_s,
        )
        self.last_status = status
        return status

    def ingest(
        self,
        node_s: float,
        acceleration: Sequence[float],
        angular_rate: Sequence[float],
        sequence: int | None = None,
        host_s: float | None = None,
    ) -> Status:
        """输入一帧 SI 单位的六轴测量，返回状态。
        Feed one SI-unit six-axis sample and return a status.
        """
        node_s = float(node_s)
        if not math.isfinite(node_s):
            raise ValueError("node timestamp must be finite")
        accel = _vector3(acceleration, "acceleration")
        gyro = _vector3(angular_rate, "angular_rate")
        if host_s is None:
            host_s = node_s
        host_s = float(host_s)
        if not math.isfinite(host_s):
            raise ValueError("host timestamp must be finite")
        if self.start_host is None:
            self.start_host = host_s
            self.start_node = node_s
        if self.last_host is not None and host_s < self.last_host:
            host_s = self.last_host
        self.samples += 1

        if sequence is not None and self.last_seq is not None:
            if sequence == self.last_seq:
                # 重复包不参与状态更新。/ Duplicate packet does not update the state.
                return self._status("NO_DATA", "duplicate_sequence")
            if sequence < self.last_seq:
                # 节点重启后序号回到 0；不能永远丢弃后续包。
                # Node restart resets sequence to 0; do not drop every later packet.
                self._begin_warmup(node_s, host_s)
                self.last_seq = sequence
                return self._status("WARMUP", "sequence_reset")
        gap = None if self.prev_node is None else node_s - self.prev_node
        self.last_seq = sequence if sequence is not None else self.last_seq

        if self.warmup:
            if gap is not None and (gap <= 0.0 or gap > self.config.max_gap_s):
                # 标定期间也不能跨断流拼接样本。/ Do not join samples across a gap during calibration.
                self._begin_warmup(node_s, host_s)
                return self._status("WARMUP", "gap_reinitialize", gap_s=gap)
            if self.warmup_start is None:
                self.warmup_start = node_s
            # 自动寻找一段真正静止且接近直立的起始窗口；运动/安装/躺姿不进入零偏标定。
            # Find a genuinely still, near-upright start window; motion/handling/lying is not calibrated.
            body_accel_start = mat_vec(R_BS, accel)
            posture_start = angle_from_vertical(body_accel_start)
            still_sample = (
                _norm(gyro) < 0.20
                and abs(_norm(accel) - GRAVITY) < 0.60
                and posture_start is not None
                and posture_start < 45.0
            )
            if not still_sample:
                self.warmup_start = node_s
                self.warmup_accel = []
                self.warmup_gyro = []
                self.last_node = node_s
                self.last_host = host_s
                self.prev_node = node_s
                return self._status("WARMUP", "waiting_for_upright_still_start", gap_s=gap)
            self.warmup_accel.append(accel)
            self.warmup_gyro.append(gyro)
            self.last_node = node_s
            self.last_host = host_s
            self.prev_node = node_s
            if node_s - self.warmup_start >= self.config.warmup_s:
                self._finish_warmup(node_s, host_s)
                state, reason, _, _ = self._state(node_s)
                return self._status(state, reason, gap_s=gap)
            return self._status("WARMUP", "collecting_initial_still_data", gap_s=gap)

        if gap is not None and (gap <= 0.0 or gap > self.config.max_gap_s):
            # 断流或时间倒退：不跨间断积分，重新初始化。
            # Gap or time reversal: do not integrate across it; reinitialize.
            self._begin_warmup(node_s, host_s)
            return self._status("WARMUP", "gap_reinitialize", gap_s=gap)

        dt = gap if gap is not None else 0.0
        body_accel = mat_vec(R_BS, accel)
        body_gyro = mat_vec(R_BS, gyro)
        bias_body = mat_vec(R_BS, self.bias)

        # 保留“测量减去零偏”的 body 角速度，用于世界竖直轴航向积分。
        # Keep measured-minus-bias body rate for world-vertical heading integration.
        omega_meas = tuple(body_gyro[i] - bias_body[i] for i in range(3))
        # Mahony 倾角修正：只用加速度约束垂直于重力的两个方向，不用它测航向。
        # Mahony tilt correction: gravity constrains only the two directions perpendicular to it;
        # it is never used as a heading observation.
        accel_norm = _norm(body_accel)
        omega = omega_meas
        if accel_norm > 1e-9:
            trust = max(
                0.0,
                min(
                    1.0,
                    1.0 - abs(accel_norm - GRAVITY) / (self.config.accel_trust_window * GRAVITY),
                ),
            )
            measured = tuple(x / accel_norm for x in body_accel)
            expected = mat_t_vec(q_to_matrix(self.q), (0.0, 0.0, 1.0))
            error = _cross(measured, expected)
            omega = tuple(omega[i] + self.config.kp * trust * error[i] for i in range(3))
        self.q = q_integrate(self.q, omega, dt)

        posture_raw = angle_from_vertical(body_accel)
        if posture_raw is not None:
            self.posture_raw = posture_raw
            if self.posture is None:
                self.posture = posture_raw
            else:
                self.posture += _alpha(dt, self.config.posture_tau_s) * (posture_raw - self.posture)

        gyro_rate = _norm(tuple(gyro[i] - self.bias[i] for i in range(3)))
        accel_dynamic = abs(_norm(accel) - GRAVITY)
        self.gyro_lp += _alpha(dt, self.config.motion_tau_s) * (gyro_rate - self.gyro_lp)
        self.accel_lp += _alpha(dt, self.config.motion_tau_s) * (accel_dynamic - self.accel_lp)
        self.moving = (
            self.gyro_lp > self.config.motion_gyro_radps
            or self.accel_lp > self.config.motion_accel_mps2
        )

        if self.posture is not None:
            if not self.low and self.posture >= self.config.low_enter_deg:
                # 判断起点：从这里开始计算“5 秒内有没有继续移动”。
                # Judgement origin: start the "any movement within 5 s" timer here.
                self.low = True
                self.low_since = node_s
                self.last_motion = node_s
            elif self.low and self.posture <= self.config.low_exit_deg:
                self.low = False
                self.low_since = None

        if self.moving:
            self.last_motion = node_s
            # 只在直立/非低姿态时积分航向。大腿接近水平时竖直轴不可靠，宁可冻结也不编造。
            # Integrate heading only while not in low posture. Near a horizontal thigh the vertical
            # axis is unreliable; freeze rather than invent a direction.
            if not self.low:
                world_rate = q_rotate(self.q, omega_meas)
                self.heading = wrap_deg(
                    self.heading + math.degrees(world_rate[2]) * dt
                )
                self.heading_valid = True

        self.prev_node = node_s
        self.last_node = node_s
        self.last_host = host_s
        state, reason, _, _ = self._state(node_s)
        return self._status(state, reason, gap_s=gap)

    def tick(self, host_s: float) -> Status:
        """在没有新包时推进超时状态；不修改原始测量。
        Advance the no-data state without a packet; raw measurements are untouched.
        """
        host_s = float(host_s)
        if self.last_host is None:
            return self._status("NO_DATA", "no_data_yet")
        if host_s - self.last_host > self.config.no_data_s:
            return self._status("NO_DATA", "no_fresh_data")
        return self.last_status or self._status("NO_DATA", "no_data_yet")
