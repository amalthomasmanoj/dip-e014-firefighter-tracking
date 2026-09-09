# LAB-00 - Borrowed Hardware Boundary Doc

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `LAB-00`.

Create documentation that clearly separates the official project hardware target from temporary borrowed lab hardware. The final project target remains DWM3000 + ICM-42688. The borrowed lab hardware is ESP32 DevKit V1 + DWM1001 + ICM-20948. Do not rewrite the repo as if the borrowed lab parts are the final target.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c docs/lab-borrowed-hardware-boundary
```

## Goal

Prevent future teammates and AI sessions from accidentally changing the repo's final hardware assumptions to the borrowed lab hardware.

## Repo Context

Read these files before editing:

```text
docs/hardware_setup.md
firmware/README.md
firmware/wearable_node/README.md
firmware/anchor_node/README.md
contracts/packet_schema.json
docs/sensor_interfaces.md
AGENTS.md
```

The existing architecture is intentionally generic:

```text
hardware-specific drivers/adapters
  -> generic packet contract
  -> backend parser
  -> typed measurements
  -> fusion/UI/logging
```

Your documentation must preserve that boundary.

## Required Changes

Add:

```text
docs/lab_borrowed_hardware.md
```

The doc must include:

- Official target hardware:
  ```text
  DWM3000 + ICM-42688
  ```
- Borrowed lab hardware:
  ```text
  ESP32 DevKit V1 + DWM1001 + ICM-20948
  ```
- Clear statement that borrowed hardware is for temporary lab validation only.
- What borrowed hardware can validate:
  - ESP32 flashing and serial logs
  - Wi-Fi UDP transport
  - timestamping
  - sequence numbers
  - generic packet serialization
  - backend UDP ingestion
  - raw IMU logging
  - UWB range adapter flow
- What borrowed hardware must not change:
  - final DWM3000 planning docs
  - final ICM-42688 planning docs
  - generic packet contracts
  - backend parser hardware independence
  - fusion design assumptions

Also update `docs/hardware_setup.md` with one short note pointing to `docs/lab_borrowed_hardware.md`. Do not change the current final-hardware list.

## Out Of Scope

- No firmware implementation.
- No backend code.
- No contract schema changes.
- No UI changes.
- No renaming DWM3000 or ICM-42688 references.

## Acceptance Criteria

- A teammate can read the docs and understand that DWM1001/ICM-20948 are temporary lab substitutes.
- The final target hardware in `docs/hardware_setup.md` remains DWM3000 + ICM-42688.
- Lab code paths are named clearly:
  ```text
  firmware/lab_bringup/
  tools/lab_bringup/
  data/lab_bringup/
  ```
- The docs explicitly say hardware-specific lab adapters must emit the same generic packets as final hardware.

## Verification

Run:

```bash
python3 -m pytest
```

If frontend packages are installed, also run:

```bash
cd ui/web
npm test
npm run build
```

## PR Checklist

PR title:

```text
docs: document borrowed lab hardware boundary
```

PR body must include:

- Summary of docs added.
- Confirmation that final hardware assumptions were not changed.
- Tests run.
