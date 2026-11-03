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

## HR graph and responder-check alerts

The heart-rate panel now plots the last five minutes of valid readings. History
is collected per BLE notification on the backend, including when the browser is
closed. The trace is split across notification gaps longer than five seconds.
It does not invent readings during missing periods or smooth raw BPM values.

Open **Configure thresholds** to set low/high limits, a separate persistence
period for each, a recovery margin (hysteresis), and a signal-loss delay. Tick
**Enable monitoring**, then **Apply settings**. Alerts start disabled. The initial
50/160 BPM and 30-second values are editable demonstration settings, not medically
validated danger limits. There is no BPM/duration rule here that diagnoses
fainting, unconsciousness, or cardiac arrest. Configure limits for your approved
prototype test, not for operational rescue decisions.

Only new valid notifications advance the high/low countdown. Repeated dashboard
polls do not count as new measurements. High means strictly above the upper
limit; low means strictly below the lower limit. An active high alert recovers
at or below (high limit - margin); an active low alert recovers at or above
(low limit + margin). A single valid in-range reading resets a pending timer;
a missing-data period or lost contact also resets it. A gap over five seconds
cannot bridge two threshold episodes. Zero BPM is treated as unavailable input,
not as evidence of cardiac arrest. Missing contact support does not by itself
invalidate a reading.

On disconnection, stale data, or poor contact, the high/low episode is marked
**data became unavailable**, not recovered. A separate signal-loss event follows
when valid data has been absent for the configured delay (minimum five seconds).
Monitoring requires a configured `E014_HR_DEVICE`; a deliberately disabled receiver
does not generate a signal-loss event. Real readings are required to recover
from signal loss. Sustained abnormal readings after reconnection start a new
persistence period.

**Acknowledge / silence** records acknowledgement and silences browser sound for
that event; it does not change the physiological condition or reset detection.
An active alert remains visible until its recovery condition, a data loss, or a
settings change. Event history records the trigger time, BPM at trigger,
duration at trigger, acknowledgement, and end reason. Up to 100 events and 3,600
samples are held in backend memory; the UI lists the latest 20 events and plots
at most five minutes. Data/settings/events reset when the backend restarts or
reloads. Changing settings ends the existing episode with **settings changed**
and requires a fresh confirmation period. Settings are shared by every dashboard
connected to this backend. There is no file recording/export in this change.

Choose **Enable browser sound** and allow browser audio to hear a short tone
repeating every five seconds during an unacknowledged active alert. The backend
evaluates alerts while it is running, but sound/visual notifications require an
open, functioning dashboard. Browser background throttling and audio policies
can delay or suppress tones. There are no phone, SMS, or email notifications.
A backend request failure hides live BPM and reports monitoring status unknown.

### Repeatable test without pushing HR to extremes

Use synthetic packets in automated tests; do not try to induce fainting or
unsafe heart rates. With the real strap, you can test the mechanics by setting
an example high limit below your current comfortable resting BPM and a short
persistence period, then restoring settings/disabling alerts afterward. This
only demonstrates threshold logic, not detection of a dangerous condition.

1. Confirm a live trace appears, then enable monitoring using your test settings.
2. Confirm the pending countdown advances with new readings and triggers one event.
3. Enable browser sound; acknowledge the event and check that it stays visible
   while the condition persists but the sound stops.
4. Remove the strap or disconnect it: BPM must disappear, the original episode
   must not be called recovered, and a separate signal-loss alert must follow.
5. Reconnect: confirm a new reading is needed, and a new threshold episode needs
   the full configured persistence period.
6. Restart the backend: confirm monitoring is disabled and session history resets.

API additions: `POST /heart-rate/settings` accepts the settings shown above;
`POST /heart-rate/alerts/{event_id}/acknowledge` acknowledges an event.
`GET /heart-rate` preserves its existing fields and adds `monitor` with settings,
valid sample history, pending condition, active alert, and event history. The
shared localization contracts are unchanged.
