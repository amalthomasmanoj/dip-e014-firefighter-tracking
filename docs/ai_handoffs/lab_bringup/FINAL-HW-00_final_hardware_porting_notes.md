# FINAL-HW-00 - Final Hardware Porting Notes

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `FINAL-HW-00`.

Write documentation that explains how lab bring-up work should be ported later when the final DWM3000 + ICM-42688 hardware arrives. Do not implement final hardware drivers in this ticket.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c docs/final-hardware-porting-notes
```

## Goal

Capture the migration path from borrowed lab hardware to final project hardware while keeping the contracts and backend architecture stable.

## Repo Context

Read:

```text
docs/hardware_setup.md
docs/lab_borrowed_hardware.md
docs/sensor_interfaces.md
contracts/packet_schema.json
backend/ingestion/parser.py
backend/models/measurements.py
firmware/README.md
AGENTS.md
```

The core rule is:

```text
hardware-specific driver details stay at the edge
generic measurement contracts stay stable in the middle
fusion/UI/logging consume typed measurements only
```

## Required Changes

Add:

```text
docs/final_hardware_porting_notes.md
```

The doc must explain:

- DWM1001 lab UWB adapters are temporary.
- ICM-20948 lab IMU adapters are temporary.
- Final DWM3000 work must emit the same generic `uwb_range` packets.
- Final ICM-42688 work must emit the same generic `imu` packets.
- Backend parser should not gain chip-specific branches.
- Fusion should not parse UDP, serial, DWM1001 output, DWM3000 registers, or IMU driver payloads.
- Any future contract change must be justified by a missing measurement field, not by chip naming.

Include a porting checklist:

```text
1. Prove final sensor electrical bring-up.
2. Prove raw sensor readout.
3. Convert raw readout to generic packet contract.
4. Run backend parser tests.
5. Capture short dataset.
6. Compare packet rates and timestamp quality against lab data.
7. Only then update production firmware paths.
```

## Out Of Scope

- No firmware code.
- No backend parser changes.
- No schema changes.
- No estimator implementation.

## Acceptance Criteria

- The doc gives future teammates a clear path from lab substitute code to final hardware code.
- The doc protects the hardware-agnostic backend boundary.
- The doc does not claim DWM3000 or ICM-42688 integration is complete.

## Verification

Run:

```bash
python3 -m pytest
```

If frontend packages are installed:

```bash
cd ui/web
npm test
npm run build
```

## PR Checklist

PR title:

```text
docs: add final hardware porting notes
```

PR body must include:

- Summary of porting guidance.
- Confirmation that no final hardware implementation was added.
- Tests run.
