# IMU-LAB-02 - ICM-20948 UDP Contract Stream

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `IMU-LAB-02`.

Stream borrowed ICM-20948 raw accel/gyro readings from ESP32 to the laptop as generic `imu` packets that match `contracts/packet_schema.json`. Do not add ICM-20948-specific logic to backend parser or fusion.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/icm20948-contract-udp-stream
```

## Dependencies

Complete or read outputs from:

```text
LAB-01
IMU-LAB-01
```

You need:

- Working ESP32 Wi-Fi UDP baseline.
- Working ICM-20948 I2C readout.

## Goal

Prove this path:

```text
ICM-20948 accel/gyro
  -> ESP32 timestamp and sequence number
  -> generic imu JSON packet
  -> UDP port 9000
  -> backend parse_packet()
  -> ImuMeasurement
```

## Required Packet Contract

Emit packets exactly shaped like:

```json
{
  "version": 1,
  "node_id": "imu_lab_01",
  "sequence_number": 42,
  "timestamp_us": 123456789,
  "type": "imu",
  "data": {
    "ax_mps2": 0.1,
    "ay_mps2": 0.2,
    "az_mps2": 9.7,
    "gx_radps": 0.01,
    "gy_radps": 0.02,
    "gz_radps": 0.03
  }
}
```

Rules:

- `version` must be `1`.
- `sequence_number` starts at `0` or `1` and increments by one.
- `timestamp_us` must be non-negative microseconds from ESP32 timer.
- Acceleration must be in `m/s^2`.
- Gyro must be in `rad/s`.
- Values must be finite numbers.
- Do not include magnetometer fields in this packet.

## Required Implementation

Add:

```text
firmware/lab_bringup/icm20948_udp_stream/
```

Firmware should:

- Connect to Wi-Fi using local non-committed config.
- Read ICM-20948 accel/gyro.
- Convert units into contract units.
- Serialize compact JSON.
- Send UDP to laptop backend port `9000`.
- Target 100 Hz if stable; 50 Hz acceptable if documented.
- Print packet rate once per second on serial.

If needed, add:

```text
tools/lab_bringup/receive_udp_packets.py
```

The tool should:

- Listen on UDP port `9000`.
- Use existing backend parser, not a duplicate parser.
- Count valid `imu` packets.
- Count parse failures.
- Print latest accel/gyro sample.

## Repo Context To Read

```text
contracts/packet_schema.json
contracts/examples/imu_packet.json
backend/ingestion/parser.py
backend/models/measurements.py
backend/ingestion/pipeline.py
tests/test_packet_parser.py
tests/test_ingestion_pipeline.py
```

## Important Constraints

- Do not edit the packet schema unless a real blocker is found.
- Do not add ICM-20948 branches to backend parser.
- Do not implement ZUPT here.
- Do not implement ESKF here.
- Do not commit Wi-Fi credentials.

## Acceptance Criteria

- Laptop receives valid `imu` contract packets over UDP.
- Existing backend parser accepts those packets as `ImuMeasurement`.
- Packet rate is reported.
- Parse failure count is zero during a stable 30-second run.
- README explains how to configure laptop IP and Wi-Fi credentials locally.

## Verification

Run:

```bash
python3 -m pytest
```

Manual live test:

```text
Run firmware for 30 seconds.
Run receiver on laptop.
Confirm valid imu packet count increases.
Move IMU and confirm accel/gyro values change.
```

## PR Checklist

PR title:

```text
lab: stream ICM-20948 IMU contract packets
```

PR body must include:

- Sample emitted packet.
- Packet rate observed.
- Parse success/failure counts.
- Firmware environment.
- Tests run.
- Confirmation that backend parser remains hardware-agnostic.
