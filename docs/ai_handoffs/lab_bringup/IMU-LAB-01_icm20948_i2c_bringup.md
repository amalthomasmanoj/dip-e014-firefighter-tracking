# IMU-LAB-01 - ICM-20948 Electrical And I2C Bring-Up

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `IMU-LAB-01`.

Bring up the borrowed ICM-20948 IMU with the ESP32 DevKit V1 over I2C. This ticket proves wiring and raw sensor communication only. Do not implement navigation, ZUPT, calibration models, or production ICM-42688 drivers.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/icm20948-i2c-bringup
```

## Goal

Prove this path:

```text
ICM-20948
  -> ESP32 I2C
  -> serial logs
  -> detected address
  -> WHO_AM_I read
  -> raw accel/gyro values
```

## Hardware Wiring

Default ESP32 DevKit V1 I2C wiring:

```text
ESP32 3V3    -> ICM-20948 VCC/VIN
ESP32 GND    -> ICM-20948 GND
ESP32 GPIO21 -> ICM-20948 SDA
ESP32 GPIO22 -> ICM-20948 SCL
```

Before powering:

- Confirm the breakout board supports 3.3V logic.
- Use 3.3V unless the exact breakout documentation says otherwise.
- Check whether the breakout has pull-up resistors on SDA/SCL.
- Keep wires short for first test.

Expected I2C address is usually one of:

```text
0x68
0x69
```

Expected ICM-20948 identity value is commonly `0xEA`. If the observed value differs, document it with the exact board model and library used.

## Repo Context To Read

```text
docs/coordinate_frames.md
docs/sensor_interfaces.md
contracts/packet_schema.json
tools/imu_calibration/README.md
backend/imu/frames.py
backend/imu/zupt_detector.py
```

The current repo target IMU is ICM-42688. This ticket must not replace that target. ICM-20948 is temporary borrowed lab hardware.

## Required Implementation

Add:

```text
firmware/lab_bringup/icm20948_i2c_scan/
```

Include:

```text
README.md
firmware source/sketch
```

Firmware should:

- Initialize serial logging at `115200`.
- Initialize I2C on SDA `GPIO21`, SCL `GPIO22`.
- Scan I2C addresses and print detected devices.
- Try to read ICM-20948 `WHO_AM_I`.
- Print accel and gyro readings once per second.
- Print units clearly, even if raw register units are used initially.

If using a third-party Arduino library, document:

- Library name.
- Version if known.
- Install method.
- Any board-manager dependency.

## Important Constraints

- Do not edit `backend/imu` algorithms.
- Do not edit `contracts/packet_schema.json`.
- Do not claim production ICM-42688 work is complete.
- Do not silently swap axes to "make it look right."
- If axes look unexpected, document observations only.

## Acceptance Criteria

- ESP32 detects the IMU on I2C.
- Firmware reads and prints an identity value.
- Raw accel/gyro values change when the board moves.
- README includes wiring diagram in text.
- README includes troubleshooting notes for no I2C device found.

## Verification

Run:

```bash
python3 -m pytest
```

Manual evidence for PR:

```text
I2C scanner output
WHO_AM_I output
one stationary accel/gyro sample
one moved accel/gyro sample
```

## PR Checklist

PR title:

```text
lab: add ICM-20948 I2C bring-up
```

PR body must include:

- Exact wiring used.
- I2C address found.
- Identity value read.
- Firmware/library environment.
- Sample serial output.
- Tests run.
- Confirmation that final ICM-42688 assumptions were not changed.
