from __future__ import annotations

import math

from backend.ingestion.parser import parse_packet
from backend.models.measurements import ImuMeasurement


def test_icm20948_firmware_packet_uses_contract_units() -> None:
    acceleration_mg = (12.5, -24.0, 1001.0)
    angular_velocity_dps = (1.5, -2.5, 90.0)
    packet = {
        "version": 1,
        "node_id": "imu_waist_01",
        "sequence_number": 42,
        "timestamp_us": 123456789,
        "type": "imu",
        "data": {
            "ax_mps2": acceleration_mg[0] * 9.80665 / 1000.0,
            "ay_mps2": acceleration_mg[1] * 9.80665 / 1000.0,
            "az_mps2": acceleration_mg[2] * 9.80665 / 1000.0,
            "gx_radps": math.radians(angular_velocity_dps[0]),
            "gy_radps": math.radians(angular_velocity_dps[1]),
            "gz_radps": math.radians(angular_velocity_dps[2]),
        },
    }

    measurement = parse_packet(packet)

    assert isinstance(measurement, ImuMeasurement)
    assert measurement.node_id == "imu_waist_01"
    assert measurement.az_mps2 == packet["data"]["az_mps2"]
    assert measurement.gz_radps == packet["data"]["gz_radps"]
