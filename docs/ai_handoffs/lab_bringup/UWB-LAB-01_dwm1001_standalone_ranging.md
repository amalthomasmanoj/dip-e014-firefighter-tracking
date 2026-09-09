# UWB-LAB-01 - DWM1001 Standalone Anchor/Tag Ranging

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `UWB-LAB-01`.

Configure the borrowed DWM1001 units into a temporary lab UWB network and prove that one tag can range against anchors. This is lab bring-up only. Do not rewrite the repo target from DWM3000 to DWM1001.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/dwm1001-standalone-ranging
```

## Goal

Prove this path outside the backend first:

```text
DWM1001 anchors
  -> DWM1001 tag
  -> vendor shell/API output
  -> observable range or position changes
```

Use at least:

```text
LAB_A1
LAB_A2
LAB_A3
LAB_TAG
```

## Hardware Setup

1. Physically label four DWM1001 units:
   ```text
   LAB_A1
   LAB_A2
   LAB_A3
   LAB_TAG
   ```
2. Place anchors in a simple measured layout, for example:
   ```text
   LAB_A1 at (0.0, 0.0, measured_z)
   LAB_A2 at (4.0, 0.0, measured_z)
   LAB_A3 at (0.0, 3.0, measured_z)
   ```
3. Measure anchor coordinates in metres with tape.
4. Keep anchors stable once configured.
5. Put the tag at two or more known marks and record observed output.

Do not assume final anchor coordinates from `backend/config/anchors.example.yaml` apply to the lab layout.

## Repo Context To Read

```text
docs/hardware_setup.md
docs/sensor_interfaces.md
backend/config/anchors.example.yaml
backend/uwb/anchors.py
backend/uwb/trilateration.py
contracts/packet_schema.json
```

## Required Documentation Output

Add:

```text
docs/lab_dwm1001_ranging_notes.md
```

The doc must include:

- Exact number of DWM1001 units available.
- Physical labels used.
- Which unit is tag.
- Which units are anchors.
- Measured anchor coordinates.
- Access method used:
  ```text
  USB shell, UART shell/API, BLE/mobile app, or other
  ```
- Firmware/version info if visible.
- Configuration commands or UI steps.
- Sample output showing range/position changing.
- Known limitations and problems.

## Required Bring-Up Steps

1. Confirm each DWM1001 powers up.
2. Confirm each DWM1001 can be accessed by the selected method.
3. Configure network identity/settings consistently.
4. Configure three anchors.
5. Configure one tag.
6. Confirm tag emits usable output.
7. Move tag between known marks.
8. Record observed values.

## Important Constraints

- Do not add DWM1001-specific code to backend parser.
- Do not alter `contracts/packet_schema.json`.
- Do not claim final DWM3000 integration is done.
- Do not assume DWM1001 output contains individual anchor ranges until observed.
- If only position output is available, document that clearly and stop before inventing ranges.

## Acceptance Criteria

- Tag output changes when the tag moves.
- At least one range or position output is captured in docs.
- Anchor labels and measured coordinates are documented.
- All DWM1001-specific behavior is documented as lab-only.

## Verification

Run:

```bash
python3 -m pytest
```

Manual evidence for PR:

```text
configuration method
anchor coordinates
sample tag output at mark 1
sample tag output at mark 2
observed issue list
```

## PR Checklist

PR title:

```text
lab: document DWM1001 standalone ranging bring-up
```

PR body must include:

- Device count and labels.
- Anchor layout.
- Configuration method.
- Sample output.
- Tests run.
- Confirmation that final DWM3000 assumptions remain unchanged.
