# IMU Motion Monitor

Standalone real-time demo for a thigh-mounted IMU. It reads the existing DIP IMU UDP
packets and shows:

- **direction** — a relative heading arrow and degrees, zeroed at start-up;
- **CROUCHING / LYING candidate** — a state derived from thigh tilt plus a 5 s
  “is there any movement?” rule.

It is intentionally independent of the backend and the main React UI: standard
library only, no contract changes, no database or recording files.

> This is a status prototype, not a safety-certified alarm. `CROUCHING` and
> `LYING` are candidates; read [Limits](#limits) before using them.

## Quick Start

### Real IMU (UDP 9000)

From the repository root:

```powershell
Set-Location tools\imu_motion_monitor
python -m motion_monitor.dashboard --port 9000
```

- Close any other receiver on UDP `9000` first (for example the root
  `live_zupt_receiver.py`).
- Stand upright and still for about 2 s. The state goes `WARMUP` → `UPRIGHT`.
- The arrow’s `0°` is the heading at start-up; positive is a left turn.
- Direction is hidden in low posture: a near-horizontal thigh has no reliable
  single-IMU heading.

If Tkinter is unavailable, use the terminal display:

```powershell
python -m motion_monitor.live --port 9000
```

Save a CSV:

```powershell
python -m motion_monitor.live --port 9000 --csv live.csv
```

### Demo Without Hardware

Use port `9100` so the demo does not collide with the real receiver.

Terminal 1:

```powershell
Set-Location tools\imu_motion_monitor
python -m motion_monitor.dashboard --port 9100
```

Terminal 2:

```powershell
Set-Location tools\imu_motion_monitor
python -m motion_monitor.demo_feed --port 9100
```

Synthetic timeline: stand → turn → low moving → low still → stand up.
The display should pass through `UPRIGHT`, `CROUCHING (candidate)`,
`LOW POSTURE (checking)`, `LYING (candidate)`, then `UPRIGHT`.

### Offline Replay

```powershell
python -m motion_monitor.replay --recording <path-to-a-recorded-session>
```

`<path-to-a-recorded-session>` is a folder containing `packets.jsonl`
(read-only; raw data is never modified).

## What You See

| Display | Meaning |
|---|---|
| Arrow + `direction +12.3°` | Heading relative to start-up; not an absolute compass bearing. |
| `UPRIGHT` | Thigh near vertical. |
| `CROUCHING (candidate)` | Low posture and movement within the last 5 s. |
| `LOW POSTURE (checking)` | Low posture, waiting for the 5 s window. |
| `LYING (candidate)` | Low posture and no movement for 5 s. |
| `WARMUP` | Waiting for 2 s of upright stillness to calibrate. |
| `NO DATA` | No fresh UDP packet for 0.5 s. |

## How It Decides

```text
body_force = R_BS * accel
thigh_tilt = angle(body_force, body +z)     # standing ≈ 0–10°, low ≈ 70–90°

low = thigh_tilt >= 60°                     # exit at 50° (hysteresis)
moving = low-passed |gyro| or |accel| above threshold

if not low:          UPRIGHT
elif moving:         CROUCHING (candidate)
elif 5 s no motion:  LYING (candidate)
else:                LOW POSTURE (checking)
```

Direction is integrated from the measured world-vertical angular rate, only
while moving and not in low posture. It is relative: there is no magnetometer
or UWB absolute heading.

## Limits

- **5 s is short.** A firefighter can stay crouched and still for 5 s while
  observing, listening, or treating a casualty. Use `--immobile-s 15` or `30`
  for a field-like trial.
- **Low posture is a tilt proxy, not height.** Stairs or a lower floor do not
  trigger it; sitting, kneeling, or sliding down a wall can.
- **One thigh IMU cannot uniquely separate sitting, crouching, kneeling and
  lying.** The torso and shank are not observed.
- **The “resting people remove the device” assumption is not verified.** If the
  device stays on, a still seated person can become `LYING`.
- **Direction is body-forward heading, not the velocity vector.** It matches
  normal forward walking; backward, sideways and crawling motion are not
  represented correctly.
- **Direction is hidden in low posture.** Turns made while low are not recorded;
  after standing up the pre-low relative heading is shown.
- **Not safety-certified.** No redundancy, fail-safe, or escalation path. Do not
  use it as the sole basis for a life-safety decision.

## Layout

```text
tools/imu_motion_monitor/
  README.md                  # this file
  motion_monitor/
    core.py                  # attitude, heading, posture state machine
    protocol.py              # read-only IMU packet parser
    live.py                  # UDP terminal
    dashboard.py             # Tkinter arrow + status
    replay.py                # offline replay
    demo_feed.py             # synthetic UDP source
    tests/test_core.py       # 10 synthetic tests
    README.md                # detailed algorithm and measurement notes
```

The package does not import `backend/`, `tools/uwb/`, or other root modules.
`replay.py` only reads `packets.jsonl` when explicitly pointed at a session.

## Tests

From `tools/imu_motion_monitor`:

```powershell
python -m unittest discover -s motion_monitor/tests -v
```

Expected: **10 tests OK**. The repository’s root `pytest` configuration only
collects `tests/`, so these tests do not affect the backend CI.

## Detailed Notes

See [motion_monitor/README.md](motion_monitor/README.md) for the full state
machine, coordinate conventions, replay results and measurement limitations.
