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

WebSocket endpoint:

```text
ws://localhost:8000/ws/state
```

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
