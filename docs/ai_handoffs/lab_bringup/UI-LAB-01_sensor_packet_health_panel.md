# UI-LAB-01 - Sensor Packet Health Panel

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `UI-LAB-01`.

Add a simple UI/backend path that helps the team see whether live or fake IMU/UWB packets are arriving. This is a bring-up visibility feature, not a production estimator feature.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/ui-sensor-health-panel
```

## Dependencies

Read or coordinate with:

```text
BE-LAB-01
IMU-LAB-02
UWB-LAB-02
SIM-01 if fake sensor packets are already available
```

This ticket should wait until the backend health shape is clear enough to avoid duplicate UI/backend contracts.

## Goal

Show this information in the browser:

```text
IMU stream live/stale/offline
UWB stream live/stale/offline
packet rates
latest packet age
parse error count
active anchor IDs
sequence gaps
```

The UI should help teammates debug hardware without reading backend logs constantly.

## Repo Context To Read

```text
ui/web/src/App.tsx
ui/web/src/components/SensorStatus.tsx
ui/web/src/components/ExperimentPlot.tsx
ui/web/src/api/websocket.ts
ui/web/src/types/state.ts
backend/api/app.py
backend/api/websocket.py
backend/ingestion/events.py
backend/ingestion/pipeline.py
tools/fake_data/sensor_packets.py
```

## Backend Interface

Prefer a small endpoint or WebSocket message that reports packet health. Keep the shape generic, for example:

```json
{
  "imu": {
    "packet_rate_hz": 97.5,
    "latest_age_s": 0.03,
    "sequence_gaps": 0,
    "status": "live"
  },
  "uwb": {
    "packet_rate_hz": 12.0,
    "latest_age_s": 0.08,
    "sequence_gaps": 1,
    "status": "live",
    "active_anchor_ids": ["LAB_A1", "LAB_A2", "LAB_A3"]
  },
  "parse_error_count": 0
}
```

Exact implementation may use REST or WebSocket, but document it. Do not mix this with estimated-state schema unless deliberately extending a typed message.

## UI Requirements

Update or add a compact panel that shows:

- IMU status.
- UWB status.
- Packet rates.
- Latest packet ages.
- Parse errors.
- Active anchors.
- Sequence gaps.

Use clear status states:

```text
live
stale
offline
unknown
```

Do not create a marketing page. Keep the UI practical and dense.

## Fake Data Requirement

If live hardware is not available during development, provide fake packet-health values from simulation or a small local fixture so the UI can be tested.

## Important Constraints

- Do not implement full reconnect handling unless explicitly scoped.
- Do not implement production ESKF.
- Do not make UI parse UDP packets.
- Do not hard-code DWM1001 or ICM-20948 into UI labels except in lab-only debug text if necessary.
- Keep final hardware path generic.

## Acceptance Criteria

- Browser shows packet health from backend/fake data.
- IMU and UWB can independently show live/stale/offline.
- UI builds cleanly.
- Backend tests pass.
- No contract confusion with final hardware.

## Verification

Run:

```bash
python3 -m pytest
cd ui/web
npm test
npm run build
```

Manual check:

```text
Start backend in simulation/fake mode.
Open UI.
Confirm health panel renders non-empty packet status.
If live lab packets exist, confirm rates and active anchors update.
```

## PR Checklist

PR title:

```text
lab: add sensor packet health panel
```

PR body must include:

- Backend health interface chosen.
- UI screenshots or description.
- Fake/live test mode used.
- Tests run.
- Known limitations.
