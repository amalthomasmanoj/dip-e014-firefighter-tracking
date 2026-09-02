# Agent Instructions

These rules apply to the entire repository.

## Project Scope

Build a wearable indoor firefighter tracking system using UWB, foot-mounted IMU, ZUPT, and laptop-side EKF/ESKF fusion.

Do not introduce baseline scope for path planning, robots, SLAM, LiDAR, visual-inertial odometry, victim detection, route guidance, or unknown-building mapping. Those belong only in future-work discussions unless a human explicitly changes project scope.

## Git

- Never push directly to `main`.
- Use feature or fix branches.
- Never force-push shared branches.
- Do not merge your own PR unless explicitly authorized.
- Keep commits small and descriptive.

Branch examples:

```text
feat/imu-calibration
feat/zupt-detector
feat/uwb-parser
feat/eskf-predict
feat/mcap-logging
feat/building-map
fix/timestamp-wraparound
```

Commit examples:

```text
feat(imu): add stationary gyro bias calibration
feat(fusion): add ZUPT velocity update
fix(uwb): reject invalid range packets
test(ui): add world-to-map transform tests
```

## Protected Architecture

Do not casually modify:

```text
contracts/**
docs/coordinate_frames.md
backend/logging/channels.py
```

Changing a contract requires:

1. Explain why.
2. Update producer.
3. Update consumer.
4. Update tests.
5. Document the breaking change.

## Module Boundaries

- Firmware does not contain UI or estimator logic.
- Ingestion does not contain EKF logic.
- IMU module does not open sockets.
- UWB module does not contain UI code.
- Fusion receives typed/standard measurements; it does not parse ESP32 packets.
- Logging does not implement estimator logic.
- UI never performs localization, trilateration, or fusion.

## Raw Data Preservation

Never overwrite raw measurements with filtered values. Keep these concepts separate:

```text
raw
calibrated
filtered
accepted/rejected
```

MCAP/logging work must preserve enough raw data to replay an experiment through a changed estimator later.

## Hardware Assumptions

Do not invent hardware capabilities.

Do not assume the DWM3000 setup exposes signal quality, NLOS diagnostics, anchor-to-anchor ranging, dynamic role switching, or a specific update rate unless confirmed by hardware documentation or tests.

Do not hard-code whether the foot IMU shares the UWB tag ESP32 or uses a separate wearable node.

Treat barometer support as optional future work until hardware scope confirms it.

## Coordinate Frames and Units

Follow [docs/coordinate_frames.md](docs/coordinate_frames.md). Never silently swap IMU axes in code.

Use SI internally:

```text
distance           metres
velocity           metres/second
acceleration       metres/second^2
angular velocity   radians/second
angles             radians
pressure           pascals
time transport     integer microseconds
```

## Testing

Before PR:

- Run `pytest`.
- Run frontend build/tests where applicable.
- Inspect the diff.
- Remove debug files.
- Ensure no credentials.
- Ensure no large MCAP/log files.

