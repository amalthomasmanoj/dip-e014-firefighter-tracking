# EXP-LAB-01 - First Corridor Walk Protocol With Borrowed Hardware

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `EXP-LAB-01`.

Write the first repeatable corridor-walk experiment protocol for borrowed lab hardware. This is a protocol document only unless a tiny helper script is clearly needed.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/corridor-walk-protocol
```

## Goal

Create a procedure another teammate can follow to collect comparable walking data:

```text
measured anchor layout
  -> tagged start/end marks
  -> repeatable walking path
  -> synchronized packet capture
  -> notes/screenshots/photos
  -> dataset manifest
```

No estimator accuracy claims should be made from this first protocol.

## Repo Context To Read

```text
docs/experiment_protocol.md
docs/coordinate_frames.md
docs/hardware_setup.md
docs/lab_borrowed_hardware.md
data/README.md
data/lab_bringup/README.md
```

If `docs/lab_borrowed_hardware.md` or `data/lab_bringup/README.md` does not exist yet, write the protocol so it can link to those once created, or mention the dependency clearly.

## Required Output

Add:

```text
experiments/lab_corridor_walk_protocol.md
```

The protocol must include:

- Purpose.
- Required hardware.
- Pre-run checklist.
- Anchor placement.
- Coordinate-frame convention.
- Tag/IMU mounting notes.
- Walking path.
- Trial list.
- Data files to save.
- Manual notes to record.
- Failure handling.
- Post-run sanity checks.

## Minimum Trial Set

Define these trials:

```text
T00_stationary_all_sensors_60s
T01_slow_straight_walk_out_10m
T02_slow_straight_walk_back_10m
T03_turn_at_mark_walk
T04_stationary_after_walk_60s
```

Each trial should specify:

- start condition
- operator action
- expected duration
- expected packet types
- notes to record

## Coordinate Notes

Use the repo convention:

```text
+x = chosen local forward/east-like map direction
+y = left/north-like map direction
+z = up
```

For the corridor, define:

```text
origin = chosen start mark
+x = down corridor direction
+y = left when facing +x
```

Anchor coordinates must be measured in metres from that origin.

## Important Constraints

- Do not implement fusion.
- Do not claim firefighter tracking accuracy.
- Do not use final DWM3000/ICM-42688 wording for borrowed hardware runs.
- Do not put large datasets in git.
- Do not silently change coordinate conventions.

## Acceptance Criteria

- A teammate can run the experiment from the protocol alone.
- The protocol states exactly where anchors and marks go.
- The protocol says what to record before, during, and after each run.
- The protocol separates borrowed lab hardware from final project hardware.

## Verification

Manual docs review. If no code is added, no code test is required, but running this is preferred:

```bash
python3 -m pytest
```

## PR Checklist

PR title:

```text
lab: add corridor walk experiment protocol
```

PR body must include:

- Protocol file added.
- Assumed corridor layout.
- Tests run or reason skipped.
- Confirmation no estimator claims were added.
