# Waist IMU Heading And Posture Integration

The project target is an ICM-20948 mounted rigidly at the waist. UWB remains
authoritative for position; the IMU supplies relative facing direction and a
sustained lying posture.

## Configuration

Copy `backend/config/responders.example.yaml` to an ignored local file, map the
physical UWB and IMU node IDs to one logical responder, and replace the example
identity matrix with the measured sensor-to-body rotation:

```bash
E014_SOURCE=udp \
E014_RESPONDERS_CONFIG=backend/config/responders.local.yaml \
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

The transform must be a finite, orthonormal, right-handed 3-by-3 matrix. The
backend rejects invalid transforms instead of silently swapping IMU axes.

## Heading

The default estimator collects 50 stationary body-frame gyro samples to
estimate z-axis bias. It then integrates bias-corrected `gz_radps`, rejects
non-monotonic samples, and skips integration across gaps longer than 0.5 s.
This is relative heading and will drift; it does not use the ICM-20948
magnetometer or claim magnetic north.

At session start, face a known building direction and use the dashboard's
**Align facing to building +X** control. It calls:

```text
POST /responders/{responder_id}/heading-alignment
{"heading_rad": 0.0}
```

Angles are SI radians in the project world frame: zero along `+x`, increasing
toward `+y`. Each logical responder owns an independent estimator.

## Lying Posture

The classifier low-pass filters waist tilt derived from gravity. It enters
`lying_down` after tilt remains at or above 1.22 rad (about 70 degrees) for two
seconds. It returns to `standing` after remaining below 0.96 rad (about 55
degrees) for two seconds. Samples whose acceleration magnitude is too far from
gravity do not advance a posture transition.

This is a posture state, not proof that a fall occurred. The UI wording is
“lying down — check responder.” `crouching` remains in the shared contract for
compatibility but the waist classifier does not emit it.

## Test Without Hardware

Start the backend and UI, then stream a contract-valid scenario:

```bash
python -m tools.fake_data.imu_scenario --scenario full --udp --realtime --loop
```

The generator includes a stationary calibration segment before turns. It
validates packet-to-UI plumbing, not physical ICM-20948 accuracy. Hardware
acceptance requires recorded stationary, turn, bending, walking, and sustained
lying datasets with the actual enclosure transform.
