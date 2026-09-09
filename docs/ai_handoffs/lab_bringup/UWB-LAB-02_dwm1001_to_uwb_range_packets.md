# UWB-LAB-02 - DWM1001 Output To Generic UWB Range Packets

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `UWB-LAB-02`.

Adapt observed DWM1001 lab output into the repo's generic `uwb_range` packet format and send it to the laptop/backend over UDP. Keep DWM1001-specific parsing inside lab adapter code only.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/dwm1001-uwb-range-packets
```

## Dependencies

Complete or read outputs from:

```text
UWB-LAB-01
LAB-01
```

You need confirmed DWM1001 output format before writing the adapter.

## Goal

Prove this path:

```text
DWM1001 vendor output
  -> lab-only adapter parser
  -> generic uwb_range JSON packet
  -> UDP port 9000
  -> backend parse_packet()
  -> UwbRangeMeasurement
```

## Required Packet Contract

Emit packets exactly shaped like:

```json
{
  "version": 1,
  "node_id": "uwb_lab_tag_01",
  "sequence_number": 99,
  "timestamp_us": 123456789,
  "type": "uwb_range",
  "data": {
    "anchor_id": "LAB_A1",
    "range_m": 3.42,
    "valid": true,
    "quality": null
  }
}
```

Rules:

- `version` must be `1`.
- `range_m` must be finite and non-negative.
- `anchor_id` must be a non-empty string.
- `quality` may be `null` if unavailable.
- Use `valid: false` only when the input explicitly reports invalid/unusable range.
- Drop malformed lines or count them as parse errors; do not fabricate data.

## Required Implementation

Preferred first implementation:

```text
tools/lab_bringup/dwm1001_to_udp.py
```

The tool should:

- Read from a serial port or input file.
- Parse the DWM1001 output format documented in `docs/lab_dwm1001_ranging_notes.md`.
- Map lab anchor labels to contract `anchor_id` values.
- Assign a monotonic `sequence_number`.
- Assign `timestamp_us` when packet is created if DWM1001 output does not include a usable timestamp.
- Send JSON UDP packets to host/port arguments, defaulting to `127.0.0.1:9000`.
- Print summary counts on exit:
  ```text
  raw lines read
  packets emitted
  parse failures
  invalid ranges
  anchor IDs observed
  ```

If DWM1001 output only provides tag position and not individual anchor ranges, do not force it into `uwb_range`. Instead, document the blocker and add a tiny parser test around the observed output format if useful.

## Repo Context To Read

```text
docs/lab_dwm1001_ranging_notes.md
contracts/packet_schema.json
contracts/examples/uwb_range_packet.json
backend/ingestion/parser.py
backend/models/measurements.py
tests/test_packet_parser.py
tests/test_ingestion_pipeline.py
```

## Required Tests

Add focused tests if adapter code is added:

```text
tests/test_lab_dwm1001_adapter.py
```

Tests should cover:

- Valid observed DWM1001 range line converts to `uwb_range` packet.
- Negative range is rejected.
- Missing anchor ID is rejected.
- Non-finite range is rejected.
- Generated packet is accepted by existing `parse_packet()`.

## Important Constraints

- Do not modify backend parser for DWM1001-specific strings.
- Do not change packet schema unless there is a real, documented missing generic field.
- Do not add raw vendor fields to the contract packet.
- Do not implement trilateration in the adapter.

## Acceptance Criteria

- Adapter emits valid `uwb_range` packets from observed DWM1001 output.
- Existing backend parser accepts emitted packets.
- Adapter summary counts are printed.
- Tests cover the conversion and validation.

## Verification

Run:

```bash
python3 -m pytest
```

Manual live test:

```text
Run DWM1001 tag output for 60 seconds.
Run adapter.
Confirm packets emitted.
Confirm backend parser accepts packets.
Move tag and confirm range changes.
```

## PR Checklist

PR title:

```text
lab: adapt DWM1001 output to UWB range packets
```

PR body must include:

- Observed DWM1001 input format.
- Sample generated `uwb_range` packet.
- Live packet counts.
- Tests run.
- Any blockers if individual ranges are unavailable.
