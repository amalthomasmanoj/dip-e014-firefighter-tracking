import json
import math

import pytest

from backend.api.live import LiveUdpStateHub
from backend.config.responders import ResponderConfig
from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.imu.activity import WaistPostureClassifier
from backend.imu.heading import GyroYawIntegrator
from backend.ingestion.events import IngestedMeasurement
from backend.ingestion.sequencing import SequenceStatus
from backend.models.measurements import ImuMeasurement
from backend.uwb.live_ranges import LiveUwbRangeTracker


def event(node_id: str, timestamp_us: int, gz_radps: float) -> IngestedMeasurement:
    sample = ImuMeasurement(
        timestamp_us=timestamp_us,
        node_id=node_id,
        sequence_number=timestamp_us,
        ax_mps2=0.0,
        ay_mps2=0.0,
        az_mps2=9.80665,
        gx_radps=0.0,
        gy_radps=0.0,
        gz_radps=gz_radps,
    )
    return IngestedMeasurement(
        measurement=sample,
        sequence_status=SequenceStatus(node_id, timestamp_us, False, False, None),
        arrival_time_s=timestamp_us / 1_000_000,
        raw_payload=b"raw imu",
    )


def heading(message: str) -> float:
    quaternion = json.loads(message)["state"]["orientation_xyzw"]
    return math.atan2(
        2 * quaternion["w"] * quaternion["z"],
        1 - 2 * quaternion["z"] ** 2,
    )


def test_live_hub_associates_and_isolates_imu_estimators() -> None:
    responders = (
        ResponderConfig("firefighter_1", "tag_1", "waist_1"),
        ResponderConfig("firefighter_2", "tag_2", "waist_2"),
    )
    hub = LiveUdpStateHub(
        LiveUwbRangeTracker(),
        responders=responders,
        estimator_factory=lambda: DemoSensorEstimator(
            heading_estimator=GyroYawIntegrator(calibration_samples=0),
            activity_classifier=WaistPostureClassifier(dwell_us=0),
        ),
    )

    hub.process(event("waist_1", 0, 1.0))
    hub.process(event("waist_2", 0, 0.0))
    first = hub.process(event("waist_1", 100_000, 1.0))
    second = hub.process(event("waist_2", 100_000, 0.0))

    assert first is not None and second is not None
    assert json.loads(first)["node_id"] == "firefighter_1"
    assert json.loads(second)["node_id"] == "firefighter_2"
    assert heading(first) == pytest.approx(0.1)
    assert heading(second) == pytest.approx(0.0)


def test_heading_alignment_targets_only_requested_responder() -> None:
    responders = (
        ResponderConfig("firefighter_1", "tag_1", "waist_1"),
        ResponderConfig("firefighter_2", "tag_2", "waist_2"),
    )
    hub = LiveUdpStateHub(
        LiveUwbRangeTracker(),
        responders=responders,
        estimator_factory=lambda: DemoSensorEstimator(
            heading_estimator=GyroYawIntegrator(calibration_samples=0)
        ),
    )
    hub.process(event("waist_1", 0, 0.0))
    hub.process(event("waist_2", 0, 0.0))

    hub.align_heading("firefighter_1", math.pi / 2)
    first = hub.process(event("waist_1", 100_000, 0.0))
    second = hub.process(event("waist_2", 100_000, 0.0))

    assert first is not None and second is not None
    assert heading(first) == pytest.approx(math.pi / 2)
    assert heading(second) == pytest.approx(0.0)
