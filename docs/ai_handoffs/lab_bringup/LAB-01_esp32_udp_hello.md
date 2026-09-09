# LAB-01 - ESP32 DevKit V1 UDP Hello Baseline

## Copy This Into The AI Session

You are working in the `dip-e014-firefighter-tracking` repo. Your ticket is `LAB-01`.

Bring up the borrowed ESP32 DevKit V1 as a lab-only UDP sender. This proves flashing, serial logs, Wi-Fi, and laptop UDP receive before any sensor work starts. Keep all code under `firmware/lab_bringup/`; do not touch production firmware assumptions.

## Branch

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c lab/esp32-devkit-baseline
```

## Goal

Prove this path:

```text
ESP32 DevKit V1
  -> serial boot logs
  -> Wi-Fi connection
  -> UDP JSON hello packet
  -> laptop receiver
```

This ticket establishes the transport baseline used by later IMU and UWB lab tickets.

## Hardware Steps

1. Connect ESP32 DevKit V1 to the Mac with USB.
2. Find the serial port:
   ```bash
   ls /dev/cu.*
   ```
3. Use the board setting appropriate for ESP32 DevKit V1 / ESP32-WROOM.
4. Confirm serial monitor baud rate, normally `115200`.
5. Confirm the ESP32 can reboot and print logs.

Do not connect ICM-20948 or DWM1001 during this ticket.

## Repo Context To Read

```text
firmware/README.md
firmware/wearable_node/README.md
docs/hardware_setup.md
contracts/packet_schema.json
backend/ingestion/udp_receiver.py
backend/ingestion/parser.py
```

The production packet contract is for real measurements. This hello ticket may use a diagnostic packet that is not parsed by the production parser.

## Required Implementation

Add:

```text
firmware/lab_bringup/esp32_udp_hello/
```

Include:

```text
README.md
config.example.h
src or sketch file for the firmware
```

The firmware should:

- Start serial output at `115200`.
- Print boot message, chip/board label, and reset reason if easy.
- Connect to Wi-Fi.
- Print assigned ESP32 IP address.
- Send one UDP JSON heartbeat per second to the laptop.
- Increment a sequence number.
- Include uptime in milliseconds.

Do not commit real Wi-Fi credentials. Use a local ignored config file and an example file.

Example diagnostic UDP packet:

```json
{
  "kind": "lab_hello",
  "node_id": "esp32_lab_01",
  "sequence_number": 1,
  "uptime_ms": 1234
}
```

Add or document a simple laptop receive command. A minimal Python receiver may be placed under:

```text
tools/lab_bringup/udp_hello_receiver.py
```

Only add the script if it is useful and small. It should print sender address and decoded JSON.

## Important Constraints

- Do not modify `contracts/packet_schema.json`.
- Do not modify backend parser behavior just to accept `lab_hello`.
- Do not put borrowed lab code under `firmware/wearable_node/` yet.
- Do not include secrets.
- Do not claim sensor bring-up is complete.

## Acceptance Criteria

- ESP32 serial monitor shows Wi-Fi connection and target UDP address.
- Laptop receives one hello packet per second.
- Sequence number increases monotonically.
- README explains how to set local Wi-Fi config without committing secrets.
- Lab code is clearly isolated under `firmware/lab_bringup/`.

## Verification

Run repo checks:

```bash
python3 -m pytest
```

If frontend packages are installed:

```bash
cd ui/web
npm test
npm run build
```

Also verify manually:

```text
ESP32 serial output shows connected Wi-Fi.
Laptop terminal shows UDP packets from ESP32 IP.
```

## PR Checklist

PR title:

```text
lab: add ESP32 UDP hello bring-up
```

PR body must include:

- ESP32 board used.
- Serial port used.
- Firmware environment used.
- Sample serial output.
- Sample received UDP packet.
- Tests run.
- Confirmation that no production hardware assumptions changed.
