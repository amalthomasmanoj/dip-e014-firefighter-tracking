# Lab Bring-Up AI Handoffs

These handoff docs are meant to be copied into separate AI coding sessions. Each file is scoped to one ticket so teammates can work independently without confusing borrowed lab hardware with the final project hardware.

## Current Hardware Context

Official project target hardware remains:

```text
DWM3000 + ICM-42688
```

Borrowed lab hardware available for temporary bring-up:

```text
ESP32 DevKit V1
DWM1001 UWB modules, 4 or more units
ICM-20948 IMU
```

Borrowed-hardware code and notes must stay isolated under lab-specific paths:

```text
docs/lab_*.md
firmware/lab_bringup/
tools/lab_bringup/
data/lab_bringup/
experiments/lab_*.md
```

Do not replace final-hardware docs with borrowed-hardware details. Do not rename DWM3000 or ICM-42688 references unless the ticket explicitly asks for a lab-only note.

## Shared Git Rules For Every Ticket

Start from current `main`:

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c <ticket-branch-name>
```

Before opening a PR:

```bash
python3 -m pytest
cd ui/web && npm test && npm run build
```

If a ticket only touches docs or firmware and a check is not relevant or cannot run, say exactly why in the PR description.

All repo changes must go through a PR into `main`. Do not push directly to `main`.

## Ticket Order

Recommended order:

1. `LAB-00` - Borrowed hardware boundary doc
2. `LAB-01` - ESP32 UDP hello baseline
3. `IMU-LAB-01` - ICM-20948 I2C bring-up
4. `IMU-LAB-02` - ICM-20948 UDP contract stream
5. `UWB-LAB-01` - DWM1001 standalone anchor/tag ranging
6. `UWB-LAB-02` - DWM1001 output to generic `uwb_range` packets
7. `BE-LAB-01` - Backend live UDP ingestion smoke test
8. `DATA-LAB-01` - First lab sensor dataset capture
9. `EXP-LAB-01` - Corridor-walk experiment protocol
10. `FW-LAB-01` - Combined ESP32 IMU + UWB bridge feasibility
11. `UI-LAB-01` - Sensor packet health panel
12. `FINAL-HW-00` - Porting notes for final hardware arrival

Parallel-safe work:

- `LAB-00` and `EXP-LAB-01` can run in parallel.
- `IMU-LAB-01` and `UWB-LAB-01` can run in parallel if different teammates have hardware.
- `UI-LAB-01` should wait until `BE-LAB-01` defines or confirms the packet-health shape.
- `FW-LAB-01` should wait until separate IMU and UWB paths are proven.

## Shared Engineering Rules

- Keep backend contracts hardware-agnostic.
- Do not implement production ESKF during lab bring-up.
- Do not add DWM1001-specific behavior to the backend parser.
- Do not add ICM-20948-specific behavior to the fusion layer.
- Firmware may be chip-specific inside `firmware/lab_bringup/`.
- Adapter scripts may be chip-specific inside `tools/lab_bringup/`.
- Fusion, UI, and backend ingestion should see only typed generic packets.
