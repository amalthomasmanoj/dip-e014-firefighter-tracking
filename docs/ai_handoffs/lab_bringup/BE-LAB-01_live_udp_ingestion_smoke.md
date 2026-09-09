# BE-LAB-01 - Live UDP Ingestion Smoke Test With Borrowed Hardware

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `BE-LAB-01`.

Add a lab smoke-test tool that receives live UDP packets from borrowed hardware and proves they enter the existing backend ingestion path as typed measurements. Do not redesign backend ingestion.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/backend-live-ingestion-smoke
```

## Dependencies

At least one of these should be available:

```text
IMU-LAB-02 emits generic imu packets
UWB-LAB-02 emits generic uwb_range packets
```

## Goal

Prove this path:

```text
UDP datagrams from lab hardware
  -> backend.ingestion.udp_receiver
  -> backend.ingestion.pipeline
  -> backend.ingestion.parser
  -> typed ImuMeasurement / UwbRangeMeasurement
  -> live terminal summary
```

## Repo Context To Read

```text
backend/ingestion/udp_receiver.py
backend/ingestion/pipeline.py
backend/ingestion/parser.py
backend/ingestion/events.py
backend/ingestion/sequencing.py
backend/models/measurements.py
tests/test_ingestion_pipeline.py
tests/test_packet_parser.py
```

## Required Implementation

Add:

```text
tools/lab_bringup/live_ingestion_smoke.py
```

The tool should:

- Listen on UDP host/port, default `0.0.0.0:9000`.
- Reuse existing backend ingestion/parser functions.
- Run for a configurable duration, default 60 seconds.
- Print periodic status once per second.
- Print final summary on exit.

Summary must include:

```text
total datagrams
valid imu measurements
valid uwb_range measurements
parse errors
sequence gaps
duplicate or old packets if tracked by existing sequencing
latest node IDs
latest anchor IDs
latest packet age estimate if available
```

If the existing ingestion pipeline throws on malformed packets, catch exceptions in the lab tool and count them. Do not hide parse errors.

## Optional Tests

Add tests only if non-trivial logic is introduced:

```text
tests/test_lab_live_ingestion_smoke.py
```

Test pure helper functions, not real sockets, unless the repo already has socket test patterns.

## Important Constraints

- Do not change packet contracts.
- Do not make backend parser hardware-specific.
- Do not implement estimator updates.
- Do not make this tool required for normal backend startup.
- Keep it a lab tool.

## Acceptance Criteria

- Tool receives valid `imu` packets and counts them.
- Tool receives valid `uwb_range` packets and counts them if available.
- Tool reports parse errors without crashing.
- Tool reports sequence anomalies using existing sequencing logic where possible.
- README or docstring shows exact command to run.

## Verification

Run:

```bash
python3 -m pytest
```

Manual live test:

```bash
python3 tools/lab_bringup/live_ingestion_smoke.py --duration-s 60 --port 9000
```

PR must include a sample final summary from a real or fake packet run.

## PR Checklist

PR title:

```text
lab: add live UDP ingestion smoke tool
```

PR body must include:

- What packet sources were tested.
- Sample summary output.
- Tests run.
- Confirmation that backend parser remains hardware-agnostic.
