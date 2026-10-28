# 0002 - Use A Waist-Mounted ICM-20948

## Status

Accepted. This supersedes the earlier foot-mounted ICM-42688 planning notes.

## Decision

The project IMU is an ICM-20948 mounted rigidly at the firefighter's waist.
The current baseline uses transformed accelerometer/gyroscope measurements for
relative heading and sustained `lying_down` posture. UWB remains authoritative
for position. It does not apply foot-step ZUPT, propagate waist acceleration,
use magnetometer heading, or claim a validated fall event.

Each deployment records a right-handed sensor-to-body rotation. A responder
configuration associates physical UWB and IMU node IDs with one logical
responder, so shared and separate wearable processors remain supported.

## Consequences

- `docs/coordinate_frames.md` and hardware setup now define waist/body axes.
- Heading starts after stationary gyro-bias calibration and is explicitly
  aligned to the building world frame.
- A horizontal posture must persist before the UI reports “lying down — check
  responder”; brief bending and impacts do not emit `crouching` or a fall event.
- Historical lab handoffs remain as records of the former hardware assumption
  and are marked as superseded rather than rewritten.
