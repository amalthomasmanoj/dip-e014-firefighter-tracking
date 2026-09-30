# Codex Project Handover

Last reviewed: 2026-09-30

This document gives future Codex sessions a fast, durable orientation to the
E014 firefighter-tracking repository. It summarizes the current repository
state; it does not replace `AGENTS.md`, contracts, or the detailed engineering
documents linked below.

## Immediate Handover: Live DWM3000 Work

This is the active DWM3000 UWB integration. On 2026-09-29 the real stream was
connected to the repository, passed through the demo estimator, and exposed in
the UI. On 2026-09-30 the user confirmed that the powered real anchors were
showing and updating in the live UI. Do not mistake stale state or simulation
data for a successful test in future sessions.

Current Git state:

```text
branch: feat/dwm3000-udp-adapter
base:   ec2be76 (currently main and origin/main)
state:  implementation is uncommitted; preserve all listed working-tree files
```

The working tree also contains this handover as an untracked file. No commits
or pushes were made during the session. No protected contract, coordinate-frame,
or logging-channel files were changed.

The hardware team's context document is outside the repository at:

```text
/Users/amalthomasmanoj/Downloads/UWB_Project_Context.md
```

It documents the real ESP32/DWM3000 firmware and packet format. It also contains
hotspot credentials: read it when needed, but never copy those credentials into
the repository, logs, commits, or chat output.

### Confirmed Real Hardware Interface

The ESP32 tag broadcasts one JSON sweep over UDP port `7007` on the shared
mobile hotspot. A representative shape is:

```json
{
  "t": 123456,
  "tag_id": 10,
  "anchors": {
    "A1": {"distance": 154.36, "raw": 154.36, "rssi": -80.0, "fp_rssi": -82.0},
    "A2": {"distance": 195.18, "raw": 195.18, "rssi": -81.0, "fp_rssi": -83.0}
  }
}
```

Confirmed semantics:

- `t` is milliseconds since tag boot.
- `tag_id` identifies the mobile tag.
- `distance` and `raw` are centimetres.
- Only anchors that responded during that sweep are present.
- These are tag-to-anchor ranges, not anchor-to-anchor ranges.
- The adapter therefore converts centimetres to metres and milliseconds to
  integer microseconds before forwarding generic measurements.
- Do not assume the diagnostic fields, update rate, or missing anchors are
  stable merely because they appeared in this firmware output.

During the live capture, the sender was observed at `172.20.10.6`. A 15-second
sample received 154 valid sweeps at roughly 10.3 Hz with no invalid JSON. A1
and A2 appeared in every captured sweep; A3 and A4 did not appear. Observed
distances were approximately 143.57-170.31 cm for A1 and 172.19-200.34 cm for
A2. Treat the IP and rate as observations, not hard-coded configuration.

### What Was Implemented

Hardware edge adapter:

- `tools/uwb/dwm3000_udp_adapter.py` listens on `0.0.0.0:7007`.
- It validates the hardware sweep and emits one generic `uwb_range` packet per
  responding anchor to `127.0.0.1:9000`.
- It assigns generic sequence numbers, converts units/timestamps, and keeps
  quality nullable.
- An optional append-only JSONL capture preserves arrival time and the exact
  raw payload for later replay without overwriting raw measurements.
- `tools/uwb/README.md` documents operation.

Backend live state:

- `backend/uwb/live_ranges.py` tracks only fresh UWB ranges. The default stale
  threshold is one second.
- `GET /uwb/ranges` returns the real tag ID, active-anchor count, freshness,
  and current tag-to-anchor ranges.
- `backend/api/live.py` owns a single shared UDP receiver and fans estimator
  state out to all WebSocket subscribers. This avoids each browser tab trying
  to bind UDP port `9000`.
- The shared receiver feeds the existing `DemoSensorEstimator`; it is not the
  final ESKF.
- The FastAPI lifespan starts and stops the shared live receiver in UDP mode.

Frontend live behavior:

- The UI polls `/health` so it knows the backend source before an estimated
  state exists, and polls `/uwb/ranges` every 250 ms in live mode.
- Keyboard movement is enabled only when the backend source is explicitly
  `simulation`. It must never move the live tag/person.
- In live mode, only fresh anchors actually present in the real sweep are
  shown. Two received anchors means two visible anchors; three means three.
- With fewer than three anchors, no resolved person position is fabricated.
  The map/twin show an unresolved tag status and thin dotted range circles with
  metre labels around each responding anchor.
- Once a position is solvable, the map/twin show thin dotted tag-to-anchor
  lines with range labels and render the tag as a firefighter/person.
- The requested "lines between anchors" were deliberately not implemented,
  because the actual hardware provides tag-to-anchor measurements. Drawing
  anchor-to-anchor lines with those values would misrepresent the data.
- The state WebSocket reconnects automatically after backend interruption.

Files in the current uncommitted implementation:

```text
README.md
backend/api/app.py
backend/api/live.py
backend/api/websocket.py
backend/uwb/live_ranges.py
tests/test_dwm3000_udp_adapter.py
tests/test_live_uwb_ranges.py
tools/uwb/README.md
tools/uwb/__init__.py
tools/uwb/dwm3000_udp_adapter.py
ui/web/src/App.tsx
ui/web/src/api/backend.test.ts
ui/web/src/api/backend.ts
ui/web/src/components/BuildingMap/BuildingMap.tsx
ui/web/src/components/BuildingMap/ResponderMarker.tsx
ui/web/src/components/BuildingMap/UwbRangeLayer.tsx
ui/web/src/components/DigitalTwinView.tsx
ui/web/src/components/SensorStatus.tsx
ui/web/src/demo/keyboardDemo.test.ts
ui/web/src/demo/keyboardDemo.ts
ui/web/src/styles.css
ui/web/src/types/state.ts
docs/dip-codex-handover.md
```

### Verification Completed

The following passed after implementation:

```text
python3 -m pytest tests              75 passed
cd ui/web && npm test               4 files, 11 tests passed
cd ui/web && npm run build          passed (only the existing chunk-size warning)
git diff --check                    passed
targeted Ruff on changed Python     passed
```

Full-repository Ruff still reports pre-existing findings in untouched files;
do not attribute those to this branch without checking the diff.

Integration checks completed:

- A recorded real-format two-anchor sweep passed through the adapter and
  appeared at `/uwb/ranges` as tag `dwm3000_tag_10`, A1 `1.5436 m`, and A2
  `1.9518 m`.
- Two simultaneous WebSocket clients connected successfully to the shared
  receiver.
- A controlled, geometrically consistent three-anchor sweep produced an
  estimated live position near `(1 m, 1 m)`.
- After the anchors were powered again, the user confirmed the real anchors
  were showing and working in the live UI. This confirms the live display path;
  the distinct three-anchor resolved-position case should still be checked when
  three responding anchors are available.

### Restart And Validation Checklist

1. Read `AGENTS.md`, this section, and the external UWB context document.
2. Check `git status --short --branch`. Stay on
   `feat/dwm3000-udp-adapter`; do not discard or overwrite the uncommitted work.
3. Power the anchors and tag/ESP32, connect the laptop to the same mobile
   hotspot, and wait for the devices to finish booting.
4. Check whether ports `7007`, `9000`, `8000`, and `5173` already have the
   expected processes. Do not start duplicate receivers.
5. If needed, start the adapter, live backend, and frontend with the commands
   below.
6. Observe `/uwb/ranges` for several seconds. Confirm timestamps/ages change,
   `active_anchor_count` matches the powered responding anchors, and the ranges
   vary plausibly. A response containing old values with increasing age is not
   live data.
7. Open the UI and verify keyboard input has no effect in live mode.
8. With two responding anchors, verify exactly two anchors plus dotted range
   circles/labels appear, and no positioned person is invented.
9. With three or more responding anchors, verify the estimator publishes a
   position, the firefighter/person appears, and dotted tag-to-anchor lines and
   labels update in both the Cartesian plan and digital twin.
10. If A3/A4 remain absent, diagnose hardware response/configuration before
    changing localization or UI code. The adapter correctly omits anchors that
    were not present in the sweep.
11. Re-run Python tests, frontend tests/build, diff/credential checks, then make
    small descriptive commits only after the live behavior is confirmed.

Commands when no matching process is already running:

```bash
# terminal 1, repository root
python3 tools/uwb/dwm3000_udp_adapter.py

# terminal 2, repository root
E014_SOURCE=udp uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# terminal 3
cd ui/web
npm run dev -- --port 5173
```

Useful checks:

```text
UI                 http://localhost:5173/
health             http://localhost:8000/health
live UWB snapshot  http://localhost:8000/uwb/ranges
state WebSocket    ws://localhost:8000/ws/state
hardware UDP       0.0.0.0:7007
generic UDP        127.0.0.1:9000
```

At handover-writing time, the old dev processes were still listening: Vite PID
`24099` on TCP `5173`, adapter PID `69116` on UDP `7007`, and backend PID
`69696` on UDP `9000` and TCP `8000`. These PIDs are diagnostic history only;
they may not exist tomorrow. The hardware was off, so their presence alone
does not prove that live data is flowing.

## Session Start Checklist

Before changing anything:

1. Read `AGENTS.md`.
2. Check `git status --short --branch` and preserve unrelated user changes.
3. Read the documents relevant to the task, especially protected architecture
   and contract files.
4. Start from current `main` and create a feature or fix branch. Never push
   directly to `main`.
5. Confirm whether the task concerns final hardware, borrowed lab hardware,
   simulation, or backend/UI infrastructure. Do not blur these contexts.

Useful entry points:

```text
README.md
docs/architecture.md
docs/coordinate_frames.md
docs/hardware_setup.md
docs/sensor_interfaces.md
contracts/README.md
docs/ai_handoffs/lab_bringup/README.md
```

## Project Goal And Scope

Build a wearable indoor firefighter tracking system:

```text
UWB ranges + foot-mounted IMU/ZUPT
  -> laptop-side EKF/ESKF fusion
  -> real-time EstimatedState
  -> custom indoor tracking UI
  -> raw and processed experiment recording/replay
```

The baseline is localization and trajectory estimation with graceful
degradation during imperfect or missing UWB. Do not add path planning, robots,
SLAM, LiDAR, visual-inertial odometry, victim detection, route guidance, or
unknown-building mapping except as explicitly labelled future work.

## Hardware Boundary

Final project target:

```text
4 x Qorvo DWM3000EVB
4 x ESP32-WROOM development boards
1 x ICM-42688-P foot-mounted IMU
```

The software must allow the foot IMU to share the UWB-tag ESP32 or use a
separate wearable node. Do not hard-code either physical topology. Barometer
support remains optional future work.

Temporary borrowed lab hardware:

```text
ESP32 DevKit V1
DWM1001 modules (4 or more)
ICM-20948 IMU
```

Borrowed hardware is only for transport, timing, packet, ingestion, raw-data,
and early ranging validation. Keep its code and data isolated under paths such
as:

```text
firmware/lab_bringup/
tools/lab_bringup/
data/lab_bringup/
experiments/lab_*.md
docs/lab_*.md
```

Do not rename or replace DWM3000/ICM-42688 final-hardware planning with
DWM1001/ICM-20948 details.

## Protected Architecture And Module Boundaries

Treat these as protected:

```text
contracts/**
docs/coordinate_frames.md
backend/logging/channels.py
```

A contract change requires a written reason plus coordinated producer,
consumer, test, example, and documentation updates.

Architecture boundaries:

- Firmware initializes sensors, samples, timestamps, adds sequence numbers,
  and transmits. It does not contain UI or production estimator logic.
- Ingestion receives datagrams, validates generic packets, preserves the raw
  payload and measurement timestamp, and tracks sequencing. It does not run
  EKF logic.
- IMU code does not open sockets.
- UWB code does not contain UI code.
- Fusion consumes typed measurements. It never parses ESP32, serial, DWM1001,
  DWM3000, or other device-specific payloads.
- Logging records measurements and state without implementing estimation.
- The UI renders backend state. It never performs localization,
  trilateration, or fusion.

Hardware-specific drivers and adapters must convert their output into the
stable generic packet contract at the system edge.

## Contracts, Frames, And Data Rules

Transport packets are version 1 JSON objects with:

```text
version
node_id
sequence_number
timestamp_us
type
data
```

Supported measurement packet types are `imu` and `uwb_range`. IMU acceleration
is in metres/second squared; angular velocity is in radians/second. UWB ranges
are in metres. Transport timestamps are non-negative integer microseconds.
`quality` is nullable because actual UWB diagnostic support is not confirmed.

The world frame is right-handed:

```text
+x = chosen local forward/east-like direction
+y = left/north-like direction
+z = up
```

SVG display coordinates invert world `y`. Never silently swap IMU axes. Each
physical mounting must document the raw sensor axes, shoe/body axes, and fixed
transform between them.

Always keep these concepts distinct:

```text
raw
calibrated
filtered
accepted/rejected
```

Preserve raw measurements and arrival timing so a recording can be replayed
through a changed estimator. Latency experiments need both original
measurement time and delayed arrival time.

## Current Implementation State

The repository is beyond the initial static bootstrap but is not yet a
production tracking system.

Implemented:

- Versioned IMU, UWB range, estimated-state, and WebSocket contracts.
- Generic packet parsing and typed measurement models.
- UDP reception on port `9000`, raw payload preservation, arrival-time
  tracking, and sequence status.
- Source modes selected with `E014_SOURCE`: `simulation`, `udp`, and `replay`.
- Deterministic fake IMU/UWB packet generation and UWB fault injection.
- A demo sensor-to-state estimator using recent UWB ranges, 2-D
  trilateration, simple yaw integration, ZUPT detection, and activity
  classification.
- IMU-only live-state publishing for hardware bring-up. Until UWB provides an
  absolute position, it holds position and reports large uncertainty.
- A DWM3000/ESP32 edge adapter for the confirmed UDP sweep format, with unit
  conversion and optional exact raw JSONL capture.
- A shared live UDP state hub plus a fresh-range snapshot API, allowing several
  UI clients without competing for the same UDP socket.
- FastAPI health, anchor, and state WebSocket interfaces.
- React UI with metric map, anchors, responder, trail, uncertainty, sensor
  summary, experiment plot, keyboard demo controls, and Three.js digital twin.
- Source-aware live UWB visualization: active real anchors, labelled range
  circles/lines, unresolved-position handling, and a firefighter/person marker.
- Backend and frontend tests plus GitHub Actions workflows.

Not yet production-complete:

- Production-grade DWM3000 and ICM-42688 drivers. The new DWM3000 UDP adapter
  supports the currently observed tag firmware output but is not a radio
  driver or proof of final hardware robustness.
- Borrowed-hardware lab firmware/adapters described by the handoff tickets.
- Production inertial navigation and ESKF. `backend/fusion/eskf.py` is an
  explicit placeholder, and `DemoSensorEstimator` must not be presented as the
  final fusion algorithm.
- MCAP writer, reader, and replay workflow.
- Complete packet-health telemetry panel with rates, packet ages, parse errors,
  anchor IDs, and sequence gaps.
- Final dataset capture and controlled hardware experiments.

`replay` is accepted as a source setting but streaming replay is not
implemented. The UI should show `EstimatedState`; it must not compensate for
missing estimator functionality.

## Running The Current Demo

Install and test Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python3 -m pytest
```

Simulation backend:

```bash
E014_SOURCE=simulation uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

Live generic UDP backend:

```bash
E014_SOURCE=udp uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd ui/web
npm install
npm run dev -- --port 5173
```

Endpoints:

```text
UI                 http://localhost:5173/
health             http://localhost:8000/health
anchors            http://localhost:8000/anchors
live UWB ranges     http://localhost:8000/uwb/ranges
API docs           http://localhost:8000/docs
state WebSocket    ws://localhost:8000/ws/state
sensor UDP         0.0.0.0:9000
```

Do not assume servers from a previous Codex session are still running. Check
ports before starting new instances.

In simulation mode, arrow keys or numpad directions move the responder and `C`
toggles crouching. Keyboard demo input is intentionally disabled in live and
replay modes.

## Lab Bring-Up Roadmap

The detailed, copyable ticket prompts live in
`docs/ai_handoffs/lab_bringup/`. Their recommended order is:

1. `LAB-00`: document the borrowed/final hardware boundary.
2. `LAB-01`: prove ESP32 flashing, serial, Wi-Fi, and UDP hello packets.
3. `IMU-LAB-01`: prove ICM-20948 electrical/I2C/raw readout.
4. `IMU-LAB-02`: emit contract-valid generic `imu` UDP packets.
5. `UWB-LAB-01`: prove standalone DWM1001 anchor/tag output.
6. `UWB-LAB-02`: adapt observed individual ranges into `uwb_range` packets.
7. `BE-LAB-01`: run live ingestion smoke tests and report errors/sequencing.
8. `DATA-LAB-01`: define and capture small, manifest-backed raw datasets.
9. `EXP-LAB-01`: run the measured corridor-walk protocol without premature
   accuracy claims.
10. `FW-LAB-01`: decide from evidence whether one ESP32 should bridge both
    streams or separate sources are more reliable.
11. `UI-LAB-01`: expose generic sensor packet health in the UI.
12. `FINAL-HW-00`: document porting from lab substitutes to final sensors.

Important dependencies and stop conditions:

- Do not write a DWM1001 range adapter until its actual output format is
  observed.
- If DWM1001 exposes only position and not per-anchor ranges, document the
  blocker; never fabricate ranges.
- Target IMU streaming at 100 Hz if stable; 50 Hz is acceptable when
  documented.
- Prefer reliable separate IMU/UWB sources over a fragile combined bridge.
- Do not commit Wi-Fi credentials or large datasets/logs.

At the time of this review, the handover ticket documents exist, but their
specified lab output paths do not appear to have been implemented.

## GitHub And Verification Expectations

Use small descriptive commits and PRs. Current CI runs:

```bash
python -m pip install -e ".[dev]"
pytest

cd ui/web
npm ci
npm test
npm run build
```

Before a PR:

- Run `pytest`.
- Run frontend tests/build when applicable.
- Inspect the diff.
- Remove debug artifacts.
- Check for credentials and large MCAP/log files.
- Explicitly document any skipped check.
- State whether contracts changed.

As of 2026-09-23, `main` contains nine merged PRs covering map visibility,
backend source modes, UDP ingestion, fake packets/fault injection, map/heading
coordinates, lab handover docs, digital-twin activity, keyboard-controlled
sensor simulation, and IMU-only live-state output. There were no open GitHub
issues or pull requests when reviewed.

## Known Traps

- Some older prose may still describe UDP as a placeholder. Current code and
  tests are authoritative: generic live UDP ingestion is implemented.
- The live `SensorStatus.tsx` now shows source, real tag/anchor counts, and
  ranges, but it is still not the complete packet-health panel described by
  `UI-LAB-01` (rates, parse errors, sequence gaps, and richer timing telemetry
  remain future work).
- A WebSocket connection being live does not mean hardware localization is
  available. Check message `source`, UWB availability, active anchors, and
  uncertainty.
- IMU-only live state is intentionally a held-position bring-up view, not
  dead-reckoned navigation.
- Do not infer DWM3000 signal quality/NLOS fields, ranging rate, anchor-to-anchor
  ranging, or dynamic role switching without documentation or test evidence.
- Do not infer DWM1001 per-anchor ranges until actual output proves they exist.

## Handover Discipline

At the end of a future substantial session, update this document only when the
repository's durable implementation status or workflow has changed. Keep
ticket-specific measurements, wiring, commands, datasets, and evidence in the
ticket's intended lab documentation instead of turning this file into a raw
session log.
