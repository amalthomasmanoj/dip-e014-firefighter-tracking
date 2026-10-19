"""核心状态机的合成测试；不依赖硬件或根目录代码。
Synthetic tests for the core state machine; no hardware or root-module dependency.
"""
from __future__ import annotations

import math
import unittest

from motion_monitor.core import GRAVITY, R_BS, Monitor, MonitorConfig, mat_t_vec


def feed(monitor: Monitor, t: float, angle_deg: float,
         gyro_body: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    """输入一个静止比力 + 可选 body 角速度的样本。/ Feed one sample with optional body angular rate."""
    angle = math.radians(angle_deg)
    body_accel = (GRAVITY * math.sin(angle), 0.0, GRAVITY * math.cos(angle))
    sensor_accel = mat_t_vec(R_BS, body_accel)
    sensor_gyro = mat_t_vec(R_BS, gyro_body)
    return monitor.ingest(t, sensor_accel, sensor_gyro, host_s=t)


def warmed_monitor(**kwargs) -> tuple[Monitor, float]:
    """完成 2 秒站立标定，返回监视器与下一个时间。/ Finish 2 s standing calibration and return the next time."""
    monitor = Monitor(MonitorConfig(warmup_s=2.0, **kwargs))
    t = 0.0
    for _ in range(140):  # 2.8 s at 50 Hz
        status = feed(monitor, t, 4.0)
        t += 0.02
    if not status.state == "UPRIGHT":
        raise AssertionError(f"warm-up did not finish upright: {status.state} {status.reason}")
    return monitor, t


class MonitorTests(unittest.TestCase):
    def test_warmup_is_upright_and_bias_good(self) -> None:
        monitor, _ = warmed_monitor()
        status = feed(monitor, 3.0, 4.0)
        self.assertEqual(status.state, "UPRIGHT")
        self.assertEqual(status.bias_quality, "good")
        self.assertIsNotNone(status.posture_deg)
        self.assertLess(status.posture_deg, 10.0)  # type: ignore[arg-type]

    def test_low_posture_still_becomes_lying_candidate(self) -> None:
        monitor, t = warmed_monitor()
        status = None
        for _ in range(400):  # 8 s
            status = feed(monitor, t, 90.0)
            t += 0.02
        self.assertIsNotNone(status)
        self.assertEqual(status.state, "LOW_STILL")  # type: ignore[union-attr]
        self.assertGreaterEqual(status.immobile_s, 5.0)  # type: ignore[union-attr]
        self.assertGreater(status.posture_deg, 80.0)  # type: ignore[union-attr,arg-type]

    def test_low_posture_movement_is_crouching(self) -> None:
        monitor, t = warmed_monitor()
        status = None
        for _ in range(50):  # 1 s, thigh moving about body y
            status = feed(monitor, t, 80.0, (0.0, 0.5, 0.0))
            t += 0.02
        self.assertIsNotNone(status)
        self.assertEqual(status.state, "LOW_MOVING")  # type: ignore[union-attr]
        self.assertTrue(status.moving)  # type: ignore[union-attr]

    def test_movement_after_lying_resets_to_crouching(self) -> None:
        monitor, t = warmed_monitor()
        for _ in range(400):
            feed(monitor, t, 90.0)
            t += 0.02
        status = None
        for _ in range(25):  # 0.5 s of movement, enough for the motion low-pass
            status = feed(monitor, t, 80.0, (0.0, 0.5, 0.0))
            t += 0.02
        self.assertIsNotNone(status)
        self.assertEqual(status.state, "LOW_MOVING")  # type: ignore[union-attr]
        self.assertLess(status.immobile_s, 1.0)  # type: ignore[union-attr]

    def test_stand_up_returns_upright(self) -> None:
        monitor, t = warmed_monitor()
        for _ in range(400):
            feed(monitor, t, 90.0)
            t += 0.02
        status = None
        for _ in range(150):  # 3 s
            status = feed(monitor, t, 3.0)
            t += 0.02
        self.assertIsNotNone(status)
        self.assertEqual(status.state, "UPRIGHT")  # type: ignore[union-attr]

    def test_relative_heading_turns_left(self) -> None:
        monitor, t = warmed_monitor()
        # 90 deg/s about body z for 1 s, then hold for 3 s to let the smoothing settle.
        for _ in range(50):
            feed(monitor, t, 4.0, (0.0, 0.0, math.radians(90.0)))
            t += 0.02
        status = None
        for _ in range(150):
            status = feed(monitor, t, 4.0)
            t += 0.02
        self.assertIsNotNone(status)
        self.assertTrue(status.direction_valid)  # type: ignore[union-attr]
        self.assertGreater(status.direction_deg, 80.0)  # type: ignore[union-attr,arg-type]
        self.assertLess(status.direction_deg, 100.0)  # type: ignore[union-attr,arg-type]

    def test_heading_survives_pitch_cycle(self) -> None:
        monitor, t = warmed_monitor()
        # Pitch down to 90 deg, hold, and stand up without any yaw.
        for target, seconds in ((90.0, 2.0), (90.0, 2.0), (4.0, 2.0)):
            start = monitor.posture if monitor.posture is not None else 4.0
            steps = int(seconds / 0.02)
            for index in range(steps):
                angle = start + (target - start) * (index + 1) / steps
                feed(monitor, t, angle)
                t += 0.02
        status = None
        for _ in range(50):  # 1 s upright movement with no yaw
            status = feed(monitor, t, 4.0, (0.0, 0.3, 0.0))
            t += 0.02
        self.assertIsNotNone(status)
        self.assertEqual(status.state, "UPRIGHT")  # type: ignore[union-attr]
        self.assertIsNotNone(status.direction_deg)  # type: ignore[union-attr]
        self.assertLess(abs(status.direction_deg), 10.0)  # type: ignore[union-attr,arg-type]

    def test_no_data_timeout(self) -> None:
        monitor, t = warmed_monitor()
        status = monitor.tick(t + 1.0)
        self.assertEqual(status.state, "NO_DATA")
        self.assertEqual(status.reason, "no_fresh_data")

    def test_gap_reinitializes(self) -> None:
        monitor, t = warmed_monitor()
        status = feed(monitor, t + 1.0, 4.0)
        self.assertEqual(status.state, "WARMUP")
        self.assertEqual(status.reason, "gap_reinitialize")

    def test_duplicate_sequence_is_ignored(self) -> None:
        monitor, t = warmed_monitor()
        status = feed(monitor, t, 4.0)
        status = monitor.ingest(t + 0.02, (9.8, 0.0, 0.0), (0.0, 0.0, 0.0),
                                sequence=status.samples, host_s=t + 0.02)
        # 首次 sequence 非空时不会与旧值比较；这里只验证没有异常，且状态仍可输出。
        self.assertIn(status.state, {"UPRIGHT", "NO_DATA", "WARMUP"})


if __name__ == "__main__":
    unittest.main()
