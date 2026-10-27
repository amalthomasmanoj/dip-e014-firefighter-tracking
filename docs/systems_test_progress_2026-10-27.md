# Systems Test Progress — 2026-10-27

Integration session bringing ESP32 + DWM3000 UWB, IMU, and the COOSPO H808S
heart-rate strap into the live dashboard. This records what works, what was
fixed, and what is still open, so the next session can resume without
re-deriving any of it.

Branch: `preview/hr-systems-test`

## Summary

| Subsystem | State |
|---|---|
| UWB ranging (ESP32 → adapter → backend → UI) | **Working end to end with real hardware** |
| Heart rate (H808S → BLE → backend → UI) | **Working, ~70–81 BPM observed** |
| IMU heading + posture | Pipeline works; **mounting frame unresolved** |
| IMU → position (dead reckoning) | **Not implemented** in any branch |
| Anchor coordinates | **Still placeholder values** |

## What was fixed this session

### Silent death of UDP ingestion (root cause of "nothing reaches the UI")

`ingest_datagrams` had no exception handling. A single unparseable datagram
raised out of the async generator, which ended the `LiveUdpStateHub._run`
task permanently. The backend stayed healthy, `/health` kept returning `ok`,
and the UI simply showed nothing — the failure was invisible.

The trigger was found only after adding logging:

```
rejected datagram #1: Expecting value: line 1 column 1 (char 0)
payload=b'DIP_PING 69ce316f0dc8a1f2'
```

Something on the network sends plain-text `DIP_PING` keepalives to UDP 9000.
The first one killed ingestion before any sweep arrived.

**Origin of the `DIP_PING` traffic is still unidentified** — worth tracking
down, but no longer fatal.

Changes:

- `backend/ingestion/pipeline.py` — `ingest_datagrams` catches `ValueError`
  and `UnicodeDecodeError` per datagram, counts rejections, and logs the
  first five plus every hundredth with a truncated payload.
- `backend/api/live.py` — `_run` guards `process(event)` so one bad sample
  cannot end the stream.
- `tests/test_ingestion_pipeline.py` — three regression tests covering a
  non-JSON datagram, an unknown packet `type`, and non-UTF-8 bytes.

165 tests pass. Lint is at the pre-existing baseline of 8 errors (none new).

### Heart rate merged in

`origin/feat/h808s-heart-rate` merged into this branch. Two conflicts, both
pure append-collisions (`README.md`, `ui/web/src/styles.css`); both sides
kept. `bleak` installed via `pip install -e ".[heart-rate]"`.

## Verified working

### Live hardware (UWB)

```json
{"source":"live","tag_node_id":"dwm3000_tag_10","tag_present":true,
 "active_anchor_count":3,
 "ranges":[{"anchor_id":"A1","range_m":4.1006,"age_s":0.00088},
           {"anchor_id":"A2","range_m":2.6978,"age_s":0.00084},
           {"anchor_id":"A3","range_m":3.7112,"age_s":0.00079}]}
```

All 1137 captured sweeps parsed cleanly through the adapter. The firmware and
adapter were never at fault.

### Synthetic end-to-end (UI display proof)

A synthetic ESP32 walking a known rectangle, run through the real adapter:

```
=== /ws/state : 600 frames ===
position x   : min=1.98 max=6.22   (truth 2.0..6.0)
position y   : min=1.46 max=4.70   (truth 1.5..4.5)
distinct pos : 98
speed  m/s   : min=0.00 max=1.05   (truth 1.0)
heading deg  : min=-0.1 max=44.3
sigma_x m    : min=0.10 max=0.70
anchor count : [0, 4]
motions      : ['stationary', 'walking']
```

Position tracked truth within ~20 cm with 4 cm range noise. Every field in
`ui/web/src/types/state.ts` was checked against live payloads, including
`measurement_timestamp_us` and `age_s`. The UI display path is sound.

### IMU heading and posture

Driving `tools/fake_data/imu_scenario --scenario full` through the live
backend:

```
frames=1300
yaw deg: first=1.0 min=-179.9 max=179.3 last=-178.4
postures seen: ['crouching', 'lying_down', 'standing']
zupt seen    : [False, True]
motions seen : ['stationary']      <- never 'walking' without UWB
position set : [(0.0, 0.0)]        <- IMU never moves the responder
```

## Open issues

### 1. IMU mounting frame is contradicted between branches — BLOCKING for posture

`backend/imu/frames.py` is an identity stub, and `tilt_from_vertical_rad`
reads `az_mps2` directly as the up-axis. But `feat/imu-motion-monitor`
hard-codes a different mounting, commented as matching "the currently
confirmed nominal mounting in the DIP root":

```python
# sensor +X -> body +z (up), +Y -> body +y (left), +Z -> body -x (back)
R_BS = ((0,0,-1), (0,1,0), (1,0,0))
```

These cannot both be right. Measured consequence:

```
Person STANDING STILL:
  backend assumption (sensor +z up): accel=(0,0,+g)  tilt=0.000 rad -> standing
  motion_monitor R_BS (sensor +x up): accel=(+g,0,0) tilt=1.571 rad -> lying_down
  thresholds: crouch>=0.65, lying>=1.22
```

If the IMU is mounted as the motion monitor documents, the backend reports a
standing firefighter as `lying_down` permanently.

**To resolve:** mount the IMU, stand still, capture one raw sample. Whichever
axis reads ≈ +9.8 is the up-axis.

### 2. Anchor coordinates are placeholders

`backend/config/anchors.local.yaml` is an unedited copy of the example — the
8 m × 6 m rectangle. Positions will be self-consistent and will move
correctly, but mapped to the wrong geometry. Survey the real installation
and replace every coordinate.

### 3. Only 3 of 4 anchors are ranging

No `A4` appeared in any of the 1137 sweeps — only A1, A2, A3. Three is the
bare minimum for 2D trilateration, so there is no redundancy and the geometry
is poor. Check A4 is powered and flashed with short address `0x0004`.

### 4. Firmware emits a non-contract packet type

The tag sends `"type":"uwb"` with a hybrid of contract and sweep fields:

```json
{"version":1,"node_id":"dwm3000_tag_10","sequence_number":14379,
 "timestamp_us":661988249,"type":"uwb","t":661988,"tag_id":10,
 "anchors":{"A1":{"distance":418.97,"raw":418.97,"rssi":-81.83,
                  "fp_rssi":-93.83,"t_us":661967147}, ...}}
```

Harmless today — the adapter ignores unknown top-level keys and rewrites the
type. But `"uwb"` is not a valid contract type, so pointing this firmware
straight at port 9000 would have every packet rejected. The ingestion guard
now makes that visible in the log instead of fatal.

### 5. IMU cannot move the responder

`eskf.py`, `imu_prediction.py`, `zupt_update.py` and `ins.py` are all
no-op placeholders returning `state` unchanged, and `demo_estimator.py`
imports none of them. `ImuBias` is defined and never used. No branch
anywhere uses `ax_mps2`/`ay_mps2` in fusion — accelerometer feeds only ZUPT
detection and tilt classification.

Consequences: IMU-only mode holds the last position rather than dead
reckoning, and `motion` can never report `walking` without UWB because it is
thresholded on `speed_mps`, which is UWB-derived. The README's "graceful
degradation under UWB dropout" goal is not implemented.

### 6. Heading drifts

`GyroYawIntegrator` is raw gyro-z integration with no gravity correction and
no magnetometer — self-documented as a bring-up reference only.

`feat/imu-motion-monitor` has a materially better implementation (quaternion
integration with gravity-based tilt correction, gyro bias estimation with a
2 s warmup, and `heading_from_quat` avoiding the pitch-±90° singularity), and
its 10 tests pass. It is **not wired in**: it is a standalone Tkinter/terminal
tool, it binds UDP 9000 itself so it cannot run alongside the backend, it is
thigh-mounted, and it returns degrees of heading relative to startup rather
than radians of absolute bearing.

An adapter implementing `backend.imu.heading.HeadingEstimator` would be
roughly 30 lines: hold a `Monitor`, call
`ingest(ts_us/1e6, accel, gyro, seq)`, convert `direction_deg` to radians,
hold the last good value when it returns `None`.

## Environment notes

- **Laptop IP changes.** On the "Xiaomi 15" phone hotspot it moved from
  `10.91.106.71` to `10.61.52.129` mid-session. Re-check with `ipconfig` each
  session and update `LAPTOP_IP` in the ESP32 `config.h`.
- **Windows Firewall** blocked inbound UDP. There were Allow rules for
  `python313\python.exe` but none for `.venv\Scripts\python.exe`. Fixed with
  a port-scoped rule (admin PowerShell):
  ```powershell
  New-NetFirewallRule -DisplayName "E014 UDP" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 7007,9000
  ```
  Loopback bypasses the firewall, which is why synthetic tests passed while
  real hardware failed.
- **PowerShell:** use `curl.exe`, not `curl` (an alias for
  `Invoke-WebRequest`). Relative paths need `.\` — `.venv\Scripts\python.exe`
  fails with a module-load error, `.\.venv\Scripts\python.exe` works. No
  `&&` chaining in Windows PowerShell 5.1.
- **Heart-rate strap:** `D4:DA:7E:F6:A3:61`, advertised name `808S 0009484`.

## Startup sequence

Three processes, each in its own terminal, from the repo root.

**1. Backend**

```powershell
cd C:\Users\joshu\dip-e014-firefighter-tracking
$env:E014_SOURCE = "udp"
$env:E014_ANCHORS_CONFIG = "backend/config/anchors.local.yaml"
$env:E014_HR_DEVICE = "D4:DA:7E:F6:A3:61"
$env:E014_HR_WEARER = "Joshua"
.\.venv\Scripts\python.exe -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

**2. UWB adapter** (ESP32 sends sweeps on 7007; the backend reads contract
packets on 9000 — nothing arrives without this bridge)

```powershell
cd C:\Users\joshu\dip-e014-firefighter-tracking
.\.venv\Scripts\python.exe -m tools.uwb.dwm3000_udp_adapter --raw-jsonl C:\Users\joshu\e014_runs\raw_sweeps.jsonl
```

**3. UI**

```powershell
cd C:\Users\joshu\dip-e014-firefighter-tracking\ui\web
npm run dev
```

Then open <http://localhost:5173>.

**Verify:**

```powershell
curl.exe http://127.0.0.1:8000/uwb/ranges    # want "tag_present":true
curl.exe http://127.0.0.1:8000/heart-rate    # want "status":"connected"
```

Backend log: `C:\Users\joshu\AppData\Local\Temp\e014_backend.log`. Rejected
datagrams now appear there with their payload.

## Data path

```text
ESP32 tag ──UDP:7007──> tools.uwb.dwm3000_udp_adapter ──UDP:9000──> backend ──WS──> UI
  (sweep JSON, cm)          (rewrites to contract packets)

IMU (no firmware yet) ─────────────UDP:9000───────────────────────> backend ──WS──> UI
  (must emit contract "imu" packets directly, NOT via 7007)

H808S strap ──BLE──> HeartRateReceiver ──GET /heart-rate (500 ms poll)──> UI
  (direct to laptop; does not involve the ESP32)
```

There is **no IMU firmware in this repo**. Only two `.ino` files exist, both
UWB-only; `firmware/wearable_node/` is a placeholder README and `IMU-LAB-02`
is an unstarted handoff ticket. IMU packets must match
`contracts/packet_schema.json` exactly — accel in m/s², gyro in **radians**/s.

## Branch state

Unmerged remote branches relative to `origin/main`:

| Branch | Commits | In this branch? |
|---|---|---|
| `feat/imu-heading-posture-pipeline` | +2 | yes |
| `feat/esp32-dwm3000-lab-bringup` | +1 | yes |
| `feat/h808s-heart-rate` | +1 | yes (merged this session) |
| `feat/live-anchor-survey` | +5 | no |
| `feat/imu-motion-monitor` | +1 | no |

`feat/live-anchor-survey` adds anchor self-survey, a `uwb_pair_range` packet
type, multi-tag isolation, and ZUPT zero-velocity updates. It changes
`contracts/packet_schema.json` and `backend/models/measurements.py`, so it
needs a careful merge.

## Suggested next steps

1. Resolve the IMU mounting frame (one raw sample settles it).
2. Survey the real anchor coordinates into `anchors.local.yaml`.
3. Get A4 ranging.
4. Write the `HeadingEstimator` adapter around the motion monitor's algorithm.
5. Identify the source of the `DIP_PING` traffic on UDP 9000.
