from __future__ import annotations

import math
import statistics
from collections import deque
from collections.abc import Sequence

from backend.fusion.position_ekf import PositionEkf2D
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
        range_sync_tolerance_us: int = 10_000,
        range_median_window: int = 5,
        emit_imu_only_state: bool = True,
    ) -> None:
        if range_sync_tolerance_us < 0:
            raise ValueError("range sync tolerance cannot be negative")
        if range_median_window <= 0:
            raise ValueError("range median window must be positive")
        self._anchors = list(anchors)
        self._configured_anchor_ids = {anchor.anchor_id for anchor in anchors}
        self._range_stale_after_us = range_stale_after_us
        self._range_sync_tolerance_us = range_sync_tolerance_us
        self._emit_imu_only_state = emit_imu_only_state
        self._latest_ranges: dict[str, float] = {}
        self._range_timestamps: dict[str, int] = {}
        self._range_windows: dict[str, deque[tuple[int, float]]] = {}
        self._imu_window: deque[ImuMeasurement] = deque(maxlen=5)
        self._latest_imu: ImuMeasurement | None = None
        self._last_imu_timestamp_us: int | None = None
        self._last_position: tuple[float, float] | None = None
        self._last_position_timestamp_us: int | None = None
        self._yaw_rad = 0.0
        self._uncertainty_m = 1.5
        self._range_median_window = range_median_window
        self._position_filter = PositionEkf2D()

    def set_anchors(self, anchors: Sequence[Anchor]) -> None:
        """Install a known map atomically without mixing ranges from the old map.

        Coordinates remain in the same world frame; retain the position filter.
        This is not anchor self-survey or relative-frame estimation.
        """
        self._anchors = list(anchors)
        self._configured_anchor_ids = {anchor.anchor_id for anchor in anchors}
        self._latest_ranges.clear()
        self._range_timestamps.clear()
        self._range_windows.clear()

    def update(self, measurement: Measurement) -> EstimatedState | None:
        if isinstance(measurement, ImuMeasurement):
            self._observe_imu(measurement)
            if not self._emit_imu_only_state:
                return None
            return self._state_from_imu_only(timestamp_us=measurement.timestamp_us)

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
            self._range_windows.pop(measurement.anchor_id, None)
            return None

        self._latest_ranges[measurement.anchor_id] = measurement.range_m
        self._range_timestamps[measurement.anchor_id] = measurement.timestamp_us
        window = self._range_windows.setdefault(
            measurement.anchor_id,
            deque(maxlen=self._range_median_window),
        )
        window.append((measurement.timestamp_us, measurement.range_m))

        synchronized_ranges = self._synchronized_filtered_ranges(
            measurement.timestamp_us
        )
        if len(synchronized_ranges) < 3:
            return None

        try:
            raw_x_m, raw_y_m = trilaterate_2d(
                self._anchors,
                synchronized_ranges,
            )
        except ValueError:
            self._uncertainty_m = min(5.0, self._uncertainty_m + 0.15)
            return None

        residual_m = self._mean_range_residual(
            point=(raw_x_m, raw_y_m),
            ranges=synchronized_ranges,
        )
        measurement_sigma_m = max(0.2, min(1.0, 0.15 + residual_m))
        estimate = self._position_filter.update(
            timestamp_us=measurement.timestamp_us,
            position_xy_m=(raw_x_m, raw_y_m),
            measurement_sigma_m=measurement_sigma_m,
        )

        self._last_position = (estimate.x_m, estimate.y_m)
        self._last_position_timestamp_us = measurement.timestamp_us

        speed_mps = math.hypot(
            estimate.velocity_x_mps,
            estimate.velocity_y_mps,
        )
        self._uncertainty_m = max(
            0.1,
            min(5.0, max(estimate.sigma_x_m, estimate.sigma_y_m)),
        )

        return self._build_state(
            timestamp_us=measurement.timestamp_us,
            x_m=estimate.x_m,
            y_m=estimate.y_m,
            velocity_x_mps=estimate.velocity_x_mps,
            velocity_y_mps=estimate.velocity_y_mps,
            speed_mps=speed_mps,
            fresh_ranges=synchronized_ranges,
            sigma_x_m=max(0.1, estimate.sigma_x_m),
            sigma_y_m=max(0.1, estimate.sigma_y_m),
        )

    def _state_from_imu_only(self, timestamp_us: int) -> EstimatedState:
        fresh_ranges = self._fresh_ranges(timestamp_us)
        x_m = 0.0
        y_m = 0.0
        if self._last_position is not None:
            x_m, y_m = self._last_position

        sigma_x_m = 5.0 if self._last_position is None else min(5.0, self._uncertainty_m + 0.5)
        sigma_y_m = sigma_x_m

        return self._build_state(
            timestamp_us=timestamp_us,
            x_m=x_m,
            y_m=y_m,
            velocity_x_mps=0.0,
            velocity_y_mps=0.0,
            speed_mps=0.0,
            fresh_ranges=fresh_ranges,
            sigma_x_m=sigma_x_m,
            sigma_y_m=sigma_y_m,
        )

    def _build_state(
        self,
        *,
        timestamp_us: int,
        x_m: float,
        y_m: float,
        velocity_x_mps: float,
        velocity_y_mps: float,
        speed_mps: float,
        fresh_ranges: dict[str, float],
        sigma_x_m: float,
        sigma_y_m: float,
    ) -> EstimatedState:
        zupt_active = detect_zupt_window(self._imu_window) if self._imu_window else False
        activity = self._activity_state(speed_mps=speed_mps, zupt_active=zupt_active)

        return EstimatedState(
            timestamp_us=timestamp_us,
            position_m=Vector3(x=x_m, y=y_m, z=0.0),
            velocity_mps=Vector3(x=velocity_x_mps, y=velocity_y_mps, z=0.0),
            orientation_xyzw=self._heading_to_quaternion(self._yaw_rad),
            uncertainty=Uncertainty(
                sigma_x_m=sigma_x_m,
                sigma_y_m=sigma_y_m,
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
            if anchor_id in self._configured_anchor_ids
            and timestamp_us - self._range_timestamps.get(anchor_id, -1)
            <= self._range_stale_after_us
        }

    def _synchronized_filtered_ranges(self, timestamp_us: int) -> dict[str, float]:
        synchronized: dict[str, float] = {}
        for anchor_id, latest_timestamp_us in self._range_timestamps.items():
            if (
                anchor_id not in self._configured_anchor_ids
                or not 0
                <= timestamp_us - latest_timestamp_us
                <= self._range_sync_tolerance_us
            ):
                continue
            samples = [
                range_m
                for sample_timestamp_us, range_m in self._range_windows.get(
                    anchor_id,
                    (),
                )
                if 0 <= timestamp_us - sample_timestamp_us <= self._range_stale_after_us
            ]
            if samples:
                synchronized[anchor_id] = statistics.median(samples)
        return synchronized

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
