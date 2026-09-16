from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence

from backend.imu.activity import classify_activity
from backend.imu.zupt_detector import detect_zupt_window
from backend.models.measurements import ImuMeasurement, Measurement, UwbRangeMeasurement
from backend.models.state import (
    ActivityState,
    EstimatedState,
    Quaternion,
    SensorStatus,
    Uncertainty,
    Vector3,
)
from backend.uwb.anchors import DEFAULT_ANCHORS, Anchor
from backend.uwb.trilateration import distance_2d, trilaterate_2d


class DemoSensorEstimator:
    """Small packet-to-state pipeline for simulation and hardware bring-up.

    This is not the production ESKF. It intentionally uses the same generic
    measurement types that real devices must emit, so simulation exercises the
    parser, sequencing, UWB, IMU, and state contract path end to end.
    """

    def __init__(
        self,
        anchors: Sequence[Anchor] = DEFAULT_ANCHORS,
        range_stale_after_us: int = 500_000,
    ) -> None:
        self._anchors = list(anchors)
        self._range_stale_after_us = range_stale_after_us
        self._latest_ranges: dict[str, float] = {}
        self._range_timestamps: dict[str, int] = {}
        self._imu_window: deque[ImuMeasurement] = deque(maxlen=5)
        self._latest_imu: ImuMeasurement | None = None
        self._last_imu_timestamp_us: int | None = None
        self._last_position: tuple[float, float] | None = None
        self._last_position_timestamp_us: int | None = None
        self._yaw_rad = 0.0
        self._uncertainty_m = 1.5

    def update(self, measurement: Measurement) -> EstimatedState | None:
        if isinstance(measurement, ImuMeasurement):
            self._observe_imu(measurement)
            return None

        if isinstance(measurement, UwbRangeMeasurement):
            return self._observe_uwb(measurement)

        return None

    def _observe_imu(self, measurement: ImuMeasurement) -> None:
        if self._last_imu_timestamp_us is not None:
            dt_s = (measurement.timestamp_us - self._last_imu_timestamp_us) / 1_000_000
            if dt_s > 0:
                self._yaw_rad += measurement.gz_radps * dt_s
        self._last_imu_timestamp_us = measurement.timestamp_us
        self._latest_imu = measurement
        self._imu_window.append(measurement)

    def _observe_uwb(self, measurement: UwbRangeMeasurement) -> EstimatedState | None:
        if not measurement.valid:
            self._latest_ranges.pop(measurement.anchor_id, None)
            self._range_timestamps.pop(measurement.anchor_id, None)
            return None

        self._latest_ranges[measurement.anchor_id] = measurement.range_m
        self._range_timestamps[measurement.anchor_id] = measurement.timestamp_us
        fresh_ranges = self._fresh_ranges(measurement.timestamp_us)
        if len(fresh_ranges) < 3:
            return None

        try:
            x_m, y_m = trilaterate_2d(self._anchors, fresh_ranges)
        except ValueError:
            self._uncertainty_m = min(5.0, self._uncertainty_m + 0.15)
            return None

        velocity_x_mps = 0.0
        velocity_y_mps = 0.0
        if self._last_position is not None and self._last_position_timestamp_us is not None:
            dt_s = (measurement.timestamp_us - self._last_position_timestamp_us) / 1_000_000
            if dt_s > 0:
                velocity_x_mps = (x_m - self._last_position[0]) / dt_s
                velocity_y_mps = (y_m - self._last_position[1]) / dt_s

        self._last_position = (x_m, y_m)
        self._last_position_timestamp_us = measurement.timestamp_us

        zupt_active = detect_zupt_window(self._imu_window) if self._imu_window else False
        speed_mps = math.hypot(velocity_x_mps, velocity_y_mps)
        activity = self._activity_state(speed_mps=speed_mps, zupt_active=zupt_active)
        residual_m = self._mean_range_residual(point=(x_m, y_m), ranges=fresh_ranges)
        self._uncertainty_m = max(0.15, min(5.0, 0.2 + residual_m))

        return EstimatedState(
            timestamp_us=measurement.timestamp_us,
            position_m=Vector3(x=x_m, y=y_m, z=0.0),
            velocity_mps=Vector3(x=velocity_x_mps, y=velocity_y_mps, z=0.0),
            orientation_xyzw=self._heading_to_quaternion(self._yaw_rad),
            uncertainty=Uncertainty(
                sigma_x_m=self._uncertainty_m,
                sigma_y_m=self._uncertainty_m * 1.2,
                sigma_z_m=1.0,
            ),
            status=SensorStatus(
                zupt_active=zupt_active,
                uwb_available=bool(fresh_ranges),
                active_anchor_count=len(fresh_ranges),
            ),
            activity=activity,
        )

    def _fresh_ranges(self, timestamp_us: int) -> dict[str, float]:
        return {
            anchor_id: range_m
            for anchor_id, range_m in self._latest_ranges.items()
            if timestamp_us - self._range_timestamps.get(anchor_id, -1) <= self._range_stale_after_us
        }

    def _activity_state(self, speed_mps: float, zupt_active: bool) -> ActivityState:
        if self._latest_imu is None:
            return ActivityState(
                posture="standing",
                motion="stationary",
                confidence=0.0,
            )

        activity = classify_activity(
            sample=self._latest_imu,
            speed_mps=speed_mps,
            zupt_active=zupt_active,
        )
        return ActivityState(
            posture=activity.posture,
            motion=activity.motion,
            confidence=activity.confidence,
        )

    def _mean_range_residual(
        self,
        point: tuple[float, float],
        ranges: dict[str, float],
    ) -> float:
        anchors_by_id = {anchor.anchor_id: anchor for anchor in self._anchors}
        residuals = [
            abs(distance_2d(anchor, point) - ranges[anchor_id])
            for anchor_id, anchor in anchors_by_id.items()
            if anchor_id in ranges
        ]
        if not residuals:
            return 1.0
        return sum(residuals) / len(residuals)

    @staticmethod
    def _heading_to_quaternion(yaw_rad: float) -> Quaternion:
        half = yaw_rad / 2.0
        return Quaternion(x=0.0, y=0.0, z=math.sin(half), w=math.cos(half))
