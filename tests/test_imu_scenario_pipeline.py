"""End-to-end checks from scripted IMU packets to published estimator state."""

from __future__ import annotations

import math

import pytest

from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.imu.activity import ActivityEstimate
from backend.ingestion.parser import parse_packet
from backend.models.measurements import ImuMeasurement
from backend.models.state import EstimatedState
from tools.fake_data.imu_scenario import SCENARIOS, imu_packet_stream


def final_state_for(scenario: str, **estimator_kwargs: object) -> EstimatedState:
    estimator = DemoSensorEstimator(**estimator_kwargs)  # type: ignore[arg-type]
    state: EstimatedState | None = None
    for packet in imu_packet_stream(scenario=scenario):
        state = estimator.update(parse_packet(packet))
    assert state is not None
    return state


def heading_rad(state: EstimatedState) -> float:
    q = state.orientation_xyzw
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_scenario_produces_contract_valid_postures(scenario: str) -> None:
    estimator = DemoSensorEstimator()
    postures = set()
    for packet in imu_packet_stream(scenario=scenario):
        state = estimator.update(parse_packet(packet))
        assert state is not None
        postures.add(state.activity.posture)

    assert postures <= {"standing", "crouching", "lying_down"}


def test_standing_scenario_reports_standing() -> None:
    assert final_state_for("standing").activity.posture == "standing"


def test_crouching_scenario_remains_upright_for_waist_classifier() -> None:
    assert final_state_for("crouching").activity.posture == "standing"


def test_lying_down_scenario_reports_lying_down() -> None:
    assert final_state_for("lying_down").activity.posture == "lying_down"


def test_fall_scenario_ends_lying_down_after_starting_upright() -> None:
    estimator = DemoSensorEstimator()
    postures = []
    for packet in imu_packet_stream(scenario="fall"):
        state = estimator.update(parse_packet(packet))
        assert state is not None
        postures.append(state.activity.posture)

    assert postures[0] == "standing"
    assert postures[-1] == "lying_down"


def test_turn_scenario_rotates_published_heading() -> None:
    # 45 deg/s for 8 s is a full turn, so the wrapped heading returns near zero
    # while having passed through the intermediate quadrants.
    estimator = DemoSensorEstimator()
    headings = []
    for packet in imu_packet_stream(scenario="turn"):
        state = estimator.update(parse_packet(packet))
        assert state is not None
        headings.append(heading_rad(state))

    assert max(headings) > 2.0
    assert min(headings) < -2.0
    assert headings[-1] == pytest.approx(0.0, abs=0.2)


def test_standing_scenario_leaves_heading_near_zero() -> None:
    assert heading_rad(final_state_for("standing")) == pytest.approx(0.0, abs=0.1)


class StubHeading:
    """Minimal custom heading estimator, as a user plugin would be written."""

    def __init__(self) -> None:
        self.samples = 0

    def update(self, sample: ImuMeasurement) -> float:
        self.samples += 1
        return 1.234

    def reset(self) -> None:
        self.samples = 0


class StubClassifier:
    """Minimal custom activity classifier, as a user plugin would be written."""

    def __init__(self) -> None:
        self.samples = 0

    def classify(
        self,
        sample: ImuMeasurement,
        speed_mps: float,
        zupt_active: bool,
    ) -> ActivityEstimate:
        self.samples += 1
        return ActivityEstimate(posture="lying_down", motion="stationary", confidence=0.42)

    def reset(self) -> None:
        self.samples = 0


def test_injected_heading_estimator_drives_published_orientation() -> None:
    heading = StubHeading()
    state = final_state_for("standing", heading_estimator=heading)

    assert heading.samples > 0
    assert heading_rad(state) == pytest.approx(1.234, abs=1e-9)


def test_injected_activity_classifier_drives_published_activity() -> None:
    classifier = StubClassifier()
    state = final_state_for("standing", activity_classifier=classifier)

    assert classifier.samples > 0
    assert state.activity.posture == "lying_down"
    assert state.activity.confidence == pytest.approx(0.42)
