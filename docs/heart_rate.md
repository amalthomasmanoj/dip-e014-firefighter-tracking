# Live heart rate from a COOSPO H808S on a MacBook

The H808S connects directly to the MacBook over Bluetooth Low Energy. An optional
Python receiver subscribes to the standard Heart Rate Measurement characteristic
(2A37). The dashboard polls `GET /heart-rate` every 500 ms, independently of the
position stream. Measurement frequency is determined by the strap; polling does
not increase its sampling rate. No COOSPO app or ESP32 is needed for this setup.

## 1. Install in your backend Python environment

From the repository root (activate your existing `dip3104` environment first):

```bash
conda activate dip3104
python -m pip install -e ".[heart-rate]"
```

## 2. Wear and identify the sensor

Moisten the strap electrodes and wear the strap against your chest. Turn on Mac
Bluetooth and close phone/watch apps that may already be connected to the strap.
Grant Bluetooth access to Terminal, VS Code, or your Python launcher if macOS asks;
check System Settings > Privacy & Security > Bluetooth if access was denied.
Connect through this program rather than trying to pair in macOS settings.

```bash
python -m backend.heart_rate.receiver
```

The scan prints an identifier and advertised name for nearby devices. On macOS
the identifier is normally a UUID, not a MAC address. Copy the identifier for your
H808S. If unsure which device is yours, remove the strap, scan again, then wear it
and repeat. An exact advertised name also works, but duplicate names are rejected
rather than choosing someone else's sensor.

## 3. Start the backend with your sensor selected

Replace `PASTE_SENSOR_IDENTIFIER` with the identifier printed by the scan:

```bash
E014_HR_DEVICE="PASTE_SENSOR_IDENTIFIER" \
E014_HR_WEARER="Min" \
E014_HR_RESPONDER_ID="firefighter_1" \
uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
```

This uses the normal default simulation for the map and **real** heart rate for
Min. To use real UWB/IMU too, add `E014_SOURCE=udp` and your usual anchor
configuration to the same command. Run a single backend worker: multiple workers
would compete to connect to the same Bluetooth sensor. Stop any older backend
process first. Reload is optional; code reloads disconnect/reconnect the strap.

`E014_HR_WEARER` is the human-readable label and `E014_HR_RESPONDER_ID` binds
the strap to the logical responder published by the localization pipeline. The
dashboard hides BPM when a different firefighter is selected. This integration
supports one strap/wearer per backend.

## 4. Start your dashboard in another terminal

```bash
cd ui/web
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally http://localhost:5173).
The **Heart rate** panel shows BPM and the wearer. It works even when no position
has been estimated. Check http://localhost:8000/heart-rate for telemetry directly.

## Connection behavior

- Without `E014_HR_DEVICE`, Bluetooth stays disabled and the app works normally.
- A configured device without `E014_HR_RESPONDER_ID` remains in an error state
  rather than displaying an unassigned health reading.
- The receiver retries after missing sensors, disconnects, and Bluetooth errors.
- A connected sensor without a measurement shows **Waiting for reading**.
- Readings older than five seconds show **Reading stale** and hide BPM.
- If the sensor reports lost skin contact, BPM is hidden until contact returns.
- Backend request failures hide BPM and show **Backend offline**.
- Reconnecting requires a new reading; a previous session's value is never live.

Keep the wearer near the laptop for initial testing. Range depends on the radio,
body obstruction, and building; distant tracking needs a wearable network gateway.
This displays BPM telemetry, not raw ECG, and does not add alarm thresholds or
heart-rate recording to the existing MCAP/localization contracts.

`received_timestamp_us` is the laptop wall-clock arrival time. The standard BLE
measurement used here does not provide a device measurement timestamp.

## Validation

Wear the strap, verify a changing BPM value, remove it or move out of range, and
confirm BPM disappears. Return within range and confirm it reconnects. Test again
with UWB/IMU stopped to confirm heart rate remains independent of localization.
Hardware behavior must be validated on your MacBook; automated tests use synthetic
Bluetooth packets and a fake transport, not a physical H808S.
