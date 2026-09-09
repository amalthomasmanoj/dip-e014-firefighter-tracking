# FW-LAB-01 - Combined ESP32 IMU + UWB Packet Bridge Feasibility

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `FW-LAB-01`.

Determine whether one ESP32 DevKit V1 can act as a combined bridge for the borrowed ICM-20948 IMU and DWM1001 UWB output, or whether the lab setup should keep separate packet sources. This ticket is a feasibility decision first; implement only if the evidence supports it.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/esp32-combined-packet-bridge-feasibility
```

## Dependencies

Complete or read outputs from:

```text
LAB-01
IMU-LAB-02
UWB-LAB-01
UWB-LAB-02
```

## Goal

Decide between:

```text
Option A: one ESP32 sends both imu and uwb_range packets
Option B: separate lab streams send imu and uwb_range packets independently
```

The production repo must continue supporting both physical topologies.

## Investigation Required

Check and document:

- ESP32 pins used by ICM-20948 I2C.
- ESP32 UART pins available for DWM1001.
- DWM1001 output voltage/logic compatibility.
- Whether DWM1001 output can be read reliably while IMU samples at 50-100 Hz.
- Whether packet serialization and UDP sending can keep up.
- Whether shared timestamping improves or complicates the lab setup.
- Whether wiring is mechanically practical for corridor walks.

## Required Output

Add:

```text
docs/lab_combined_bridge_feasibility.md
```

If feasible and useful, add:

```text
firmware/lab_bringup/esp32_combined_bridge/
```

If not feasible, do not force implementation. Document the separate-stream architecture:

```text
ESP32 + ICM-20948 -> imu packets
DWM1001 adapter    -> uwb_range packets
backend ingestion  -> typed measurements from both
```

## Combined Firmware Requirements If Implemented

Firmware should:

- Read ICM-20948 on I2C.
- Read DWM1001 data from UART or other proven interface.
- Emit generic `imu` packets.
- Emit generic `uwb_range` packets.
- Use separate sequence counters per node ID or a documented shared counter.
- Print packet rates by type.
- Avoid blocking IMU sampling while waiting on UWB input.

Recommended node IDs:

```text
imu_lab_01
uwb_lab_tag_01
```

## Important Constraints

- Do not hard-code production topology.
- Do not add chip-specific parsing to backend parser.
- Do not implement ESKF.
- Do not merge an unreliable combined bridge just because it compiles.
- Prefer documented separate streams over fragile combined firmware.

## Acceptance Criteria

One of these must be true:

- A reliable combined bridge emits valid `imu` and `uwb_range` packets for 60 seconds.
- Or a clear feasibility doc explains why separate streams are the correct lab path.

Either outcome is acceptable if supported by evidence.

## Verification

Run:

```bash
python3 -m pytest
```

If firmware is implemented, run a 60-second live test and report:

```text
imu packet count
uwb_range packet count
parse failures
sequence gaps
observed packet rates
```

## PR Checklist

PR title:

```text
lab: evaluate combined ESP32 packet bridge
```

PR body must include:

- Decision: combined bridge or separate streams.
- Evidence.
- Wiring/interface notes.
- Tests run.
- Any remaining risks.
