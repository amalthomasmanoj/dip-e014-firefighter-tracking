# Architecture

The system tracks a firefighter indoors using a wearable sensing system and laptop-side estimation.

```text
UWB anchors
    -> firefighter UWB tag
    -> foot-mounted IMU
    -> ESP32 packet transport
    -> Python ingestion
    -> IMU/ZUPT + UWB processing
    -> EKF / ESKF fusion
    -> EstimatedState
    -> logging / replay
    -> FastAPI WebSocket
    -> custom React indoor tracking UI
```

## Baseline Responsibilities

### Firmware

- Initialize sensor interfaces.
- Read IMU and UWB ranging data.
- Timestamp on-node.
- Add sequence numbers.
- Transmit packets to the laptop.

Firmware does not run the production estimator in the baseline.

### Backend

- Parse and validate packets.
- Preserve original measurement timestamps.
- Detect sequence gaps and out-of-order packets.
- Calibrate IMU and detect ZUPT events.
- Process UWB ranges with known anchors.
- Run fusion.
- Publish `EstimatedState`.
- Record raw and processed data.
- Replay experiments.

### UI

The UI is a custom operator display. It shows a metric indoor coordinate layer, anchors, current responder state, trajectory trail, uncertainty, and sensor status.

The UI never performs localization, trilateration, or fusion.

## First Software-Only Target

```text
Fake trajectory generator
    -> EstimatedState model
    -> FastAPI WebSocket
    -> React map
    -> moving responder marker
    -> trajectory trail
```

This target must work without physical hardware.

