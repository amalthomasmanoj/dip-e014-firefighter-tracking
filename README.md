# E014 Firefighter Tracking

Wearable multi-sensor indoor trajectory estimation for firefighters and emergency responders.

Status: repository bootstrap / hardware integration pending.

## Core System

```text
UWB + foot-mounted IMU/ZUPT
    -> EKF / ESKF
    -> real-time responder state
    -> custom indoor tracking UI
    -> MCAP experiment recording
```

The baseline goal is graceful degradation under imperfect sensing. UWB provides absolute range information when available. IMU propagation and foot-mounted ZUPT keep the trajectory moving through temporary UWB dropout while uncertainty grows. When UWB returns, the estimator should correct accumulated inertial drift.

This bootstrap does not implement the production estimator or hardware drivers. It creates the contracts, package structure, fake data path, backend WebSocket, and React map UI needed for teams to work in parallel.

## Quick Start

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Run the fake-data backend:

```bash
uvicorn backend.api.app:app --reload
```

The backend defaults to fake simulation data. Select a startup source with:

```bash
E014_SOURCE=simulation uvicorn backend.api.app:app --reload
```

Supported source modes are `simulation`, `udp`, and `replay`. `simulation`
generates generic fake IMU/UWB packets and estimates state through the backend
pipeline. `udp` listens for generic sensor packets on UDP port `9000`, estimates
state, and streams it to the UI as `live`. `replay` is accepted as a startup
mode, but recorded replay is a placeholder until MCAP replay is implemented.
In live mode, IMU-only packets still publish a held-position state for hardware
bring-up; UWB range packets are required for absolute movement through the map.

Simulation now includes **two independently tracked firefighters**, movable
anchors, and continuous simulated anchor-pair exchanges. Select a firefighter
or anchor in the UI's **Simulation controls**, then use the direction buttons
or arrow keys to move it. Both views show separate firefighter trails and
updated anchor links. See [simulation controls and API](docs/simulation.md)
for the fixed-frame model and hardware limitations.

WebSocket endpoint:

```text
ws://localhost:8000/ws/state
```

Live UDP mode expects devices or adapters to emit the generic packet contracts
from `contracts/packet_schema.json`; no device-specific parsing belongs in the
UI or fusion layer.

The current ESP32 + DWM3000 tag firmware broadcasts one multi-anchor sweep on
UDP port `7007`. Run the hardware-edge adapter alongside the live backend to
convert those centimetre-based sweeps into generic per-anchor packets on port
`9000`:

```bash
python3 -m tools.uwb.dwm3000_udp_adapter
```

See [tools/uwb/README.md](tools/uwb/README.md) for packet details and optional
raw sweep capture. The adapter does not change the shared packet contract.

The estimator can use any three or more configured, non-collinear anchors; the
IDs do not have to be `A1`, `A2`, and `A3`. For real hardware, copy
`backend/config/anchors.example.yaml` to the ignored
`backend/config/anchors.local.yaml`, change the IDs and coordinates to the
measured installation, and start the live backend with:

```bash
E014_SOURCE=udp \
E014_ANCHORS_CONFIG=backend/config/anchors.local.yaml \
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

For example, if the responding devices are `A1`, `A2`, and `A4`, the YAML must
contain those three IDs and their measured coordinates. The backend exposes the
active configuration at `GET /anchors`. One or two ranges identify circles, not
a unique 2-D tag position, so the UI shows them as detected but unresolved.

In live mode the UI disables keyboard demo controls immediately, independently
of whether the estimator has produced a position. It keeps all configured
anchors visible and shows fresh real ranges. With fewer than three mapped
anchors it renders labelled range circles and marks the tag position as
unresolved; with a solvable position it renders the firefighter and thin
dotted, labelled tag-to-anchor range lines. Live IDs missing from the anchor
configuration are listed as unmapped instead of silently disappearing.

Live UWB positions are derived only from synchronized anchor sweeps, using a
short per-anchor median window followed by the constant-velocity 2-D position
EKF in `backend/fusion/position_ekf.py`. The EKF rejects implausible innovation
jumps and applies a low-speed deadband to reduce stationary marker jitter. This
is a UWB position filter, not the final IMU error-state Kalman filter. Raw range
values remain unchanged at `GET /uwb/ranges` for diagnostics and replay.
The backend exposes the current fresh-range view at `GET /uwb/ranges` without
adding hardware-specific fields to the shared measurement contract.

### Frontend

```bash
cd ui/web
npm install
npm run dev
```

The UI expects the backend WebSocket at `ws://localhost:8000/ws/state` by default.

Build:

```bash
npm test
npm run build
```

## IMU Heading and Posture

Heading ("direction") and posture (`standing` / `crouching` / `lying_down`)
are published in every `EstimatedState`. Both are injection points: supply
your own implementation with `E014_HEADING_ESTIMATOR` and
`E014_ACTIVITY_CLASSIFIER` instead of editing the estimator.

```bash
E014_SOURCE=udp E014_ACTIVITY_CLASSIFIER=my_package.posture:MyPosture uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

Drive the UI without hardware using scripted IMU scenarios:

```bash
python -m tools.fake_data.imu_scenario --scenario full --udp --realtime --loop
```

See [docs/imu_heading_posture_integration.md](docs/imu_heading_posture_integration.md)
for the interfaces, the test path, and the IMU wiring/firmware steps.

## Firmware

Lab bring-up firmware for the ESP32 + DWM3000 tag and anchors lives in
[firmware/lab_bringup/](firmware/lab_bringup/README.md), together with the
wiring map, the verified sweep wire format, and the bring-up order. The tag
ships with synthetic ranging so the Wi-Fi, adapter, backend, and UI path can
be proven before the radio works.

## Architecture

Start with [docs/architecture.md](docs/architecture.md), [docs/coordinate_frames.md](docs/coordinate_frames.md), and [contracts/README.md](contracts/README.md).

Important boundaries:

- Firmware samples, timestamps, sequences, and transmits measurements.
- Ingestion parses packets and preserves original measurement timestamps.
- IMU/ZUPT logic produces typed measurements/events.
- UWB logic works with known anchors and individual range measurements.
- Fusion consumes typed measurements and publishes `EstimatedState`.
- Logging records raw and processed channels without overwriting raw measurements.
- UI renders state; it does not perform localization, trilateration, or fusion.

## Development Milestones

- M0: repository / interface freeze.
- M1: fake end-to-end UI.
- M2: real IMU acquisition.
- M3: standalone IMU/ZUPT.
- M4: real UWB.
- M5: baseline fusion.
- M6: failure experiments.
- M7: final product UI / replay.
