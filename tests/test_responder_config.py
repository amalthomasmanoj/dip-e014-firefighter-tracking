from pathlib import Path

import pytest

from backend.config.responders import ResponderRegistry, load_responders
from backend.models.measurements import ImuMeasurement, UwbRangeMeasurement


def write_config(tmp_path: Path, matrix: str = "- [0, -1, 0]\n      - [1, 0, 0]\n      - [0, 0, 1]") -> Path:
    path = tmp_path / "responders.yaml"
    path.write_text(
        "responders:\n"
        "  - responder_id: firefighter_1\n"
        "    uwb_node_id: tag_10\n"
        "    imu_node_id: waist_10\n"
        "    imu_sensor_to_body:\n"
        f"      {matrix}\n",
        encoding="utf-8",
    )
    return path


def imu() -> ImuMeasurement:
    return ImuMeasurement(1, "waist_10", 1, 1, 2, 3, 4, 5, 6)


def test_registry_associates_sources_and_rotates_imu(tmp_path: Path) -> None:
    registry = ResponderRegistry(load_responders(write_config(tmp_path)))

    responder_id, transformed = registry.resolve(imu())
    uwb_id, transformed_uwb = registry.resolve(
        UwbRangeMeasurement(1, "tag_10", 2, "A1", 1.0, True, None)
    )

    assert responder_id == uwb_id == "firefighter_1"
    assert isinstance(transformed, ImuMeasurement)
    assert (transformed.ax_mps2, transformed.ay_mps2, transformed.az_mps2) == (-2, 1, 3)
    assert (transformed.gx_radps, transformed.gy_radps, transformed.gz_radps) == (-5, 4, 6)
    assert transformed_uwb.node_id == "firefighter_1"


def test_unconfigured_node_passes_through() -> None:
    sample = imu()
    responder_id, transformed = ResponderRegistry().resolve(sample)
    assert responder_id == "waist_10"
    assert transformed is sample


def test_shared_uwb_and_imu_node_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "shared.yaml"
    path.write_text(
        "responders:\n"
        "  - responder_id: firefighter_1\n"
        "    uwb_node_id: wearable_1\n"
        "    imu_node_id: wearable_1\n",
        encoding="utf-8",
    )

    assert load_responders(path)[0].uwb_node_id == "wearable_1"


def test_transform_must_be_right_handed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="right-handed"):
        load_responders(
            write_config(tmp_path, "- [-1, 0, 0]\n      - [0, 1, 0]\n      - [0, 0, 1]")
        )
