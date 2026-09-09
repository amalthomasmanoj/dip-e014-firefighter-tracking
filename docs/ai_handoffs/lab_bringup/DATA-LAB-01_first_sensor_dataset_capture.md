# DATA-LAB-01 - First Lab Sensor Dataset Capture

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `DATA-LAB-01`.

Create a repeatable process for capturing the first borrowed-hardware sensor datasets. This ticket is about data collection structure and parsing sanity, not estimator implementation.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/first-sensor-dataset-capture
```

## Dependencies

At least one live packet source should be available:

```text
IMU-LAB-02 for imu packets
UWB-LAB-02 for uwb_range packets
BE-LAB-01 for live ingestion smoke tooling
```

## Goal

Create a dataset capture path:

```text
lab hardware packets
  -> UDP receiver or adapter
  -> JSONL/CSV/raw log
  -> manifest
  -> parser sanity check
```

## Repo Context To Read

```text
data/README.md
data/samples/README.md
tools/fake_data/README.md
tools/fake_data/sensor_packets.py
contracts/examples/imu_packet.json
contracts/examples/uwb_range_packet.json
backend/ingestion/parser.py
```

## Required Implementation

Add:

```text
data/lab_bringup/README.md
data/lab_bringup/manifest.example.json
```

If adding capture tooling, place it under:

```text
tools/lab_bringup/capture_udp_jsonl.py
```

The capture tool should:

- Listen on UDP host/port, default `0.0.0.0:9000`.
- Write one raw packet per line as JSONL or raw text with arrival metadata.
- Optionally validate each packet with `parse_packet()`.
- Print packet counts by type.
- Stop after configurable duration.

Do not commit large raw datasets. Commit small samples only if they are clearly useful and small. Otherwise commit manifests and instructions.

## Dataset Runs To Define

Define these first capture scenarios:

```text
lab_stationary_imu_2min
lab_hand_motion_imu_1min
lab_dwm1001_static_tag_1min
lab_dwm1001_walk_between_marks_2min
lab_combined_imu_uwb_30s
```

Each run must record:

- date/time
- operator
- hardware IDs
- firmware/adapters used
- packet types
- expected duration
- actual duration
- file names
- notes about resets, dropouts, or bad data

## Manifest Shape

Use this manifest shape:

```json
{
  "dataset_id": "lab_YYYYMMDD_001",
  "hardware": ["ESP32 DevKit V1", "ICM-20948", "DWM1001"],
  "packet_types": ["imu", "uwb_range"],
  "duration_s": 120,
  "source": "borrowed_lab_hardware",
  "files": [],
  "notes": "stationary IMU on desk"
}
```

## Important Constraints

- Do not add large binary/raw logs unless explicitly approved.
- Do not implement fusion.
- Do not clean or filter raw data silently.
- Do not change packet schema.
- Do not put borrowed lab datasets in final experiment results folders unless documented as lab-only.

## Acceptance Criteria

- There is a clear lab data folder policy.
- Dataset manifest template exists.
- Capture procedure is documented.
- Any included sample parses through existing parser.
- Large data handling is clearly explained.

## Verification

Run:

```bash
python3 -m pytest
```

If a capture script is added, test it with fake UDP packets or a short live run.

PR must include:

```text
dataset scenario list
manifest example
sample parser result if sample data is included
```

## PR Checklist

PR title:

```text
lab: add first sensor dataset capture procedure
```

PR body must include:

- Capture scenarios documented.
- Whether sample data was committed.
- Tests run.
- Any large data intentionally excluded.
