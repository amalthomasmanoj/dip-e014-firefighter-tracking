# IMU Heading and Posture Integration

How to plug your own heading ("direction") and posture/fall-detection code
into the live pipeline, and how to test it with and without hardware.

## What The Pipeline Already Does

```text
IMU packet (UDP 9000)
  -> ingestion parser        typed ImuMeasurement
  -> HeadingEstimator        heading in radians  -> state.orientation_xyzw
  -> ActivityClassifier      posture + motion    -> state.activity
  -> WebSocket /ws/state
  -> UI: heading line, heading readout, digital-twin pose, prone alert
```

Both the heading estimator and the activity classifier are **injection
points**. The shipped implementations are deliberately simple bring-up
baselines, not finished algorithms:

- `backend/imu/heading.py` `GyroYawIntegrator` integrates the body-z gyro
  rate. No gravity correction, no magnetometer, so it drifts.
- `backend/imu/activity.py` `TiltActivityClassifier` bands the gravity tilt
  angle into `standing` / `crouching` / `lying_down`. No hysteresis, no
  impact detection, so it is not validated fall detection.

Replace either one without editing repository code.

## Where Your Code Goes

### Heading

Implement `backend.imu.heading.HeadingEstimator`:

```python
class MyHeading:
    def update(self, sample: ImuMeasurement) -> float:
        """One IMU sample in, current heading in radians out."""
        ...

    def reset(self) -> None:
        ...
```

Heading is in the world frame of `docs/coordinate_frames.md`: 0 along +x,
increasing towards +y. Return radians, not degrees. The estimator converts
your heading to the contract quaternion; do not build quaternions yourself.

`ImuMeasurement` fields: `timestamp_us`, `node_id`, `sequence_number`,
`ax_mps2`, `ay_mps2`, `az_mps2`, `gx_radps`, `gy_radps`, `gz_radps`. Derive
`dt` from `timestamp_us`, never from wall-clock time, so replay and live
behave identically.

### Posture and fall detection

Implement `backend.imu.activity.ActivityClassifier`:

```python
from backend.imu.activity import ActivityEstimate

class MyPosture:
    def classify(self, sample, speed_mps: float, zupt_active: bool) -> ActivityEstimate:
        return ActivityEstimate(
            posture="lying_down",   # "standing" | "crouching" | "lying_down"
            motion="stationary",    # "stationary" | "walking"
            confidence=0.9,         # 0.0 .. 1.0
        )

    def reset(self) -> None:
        ...
```

`posture` must be one of the three contract values. A detected fall maps to
`lying_down`. If you need a distinct fall *event* separate from the prone
*state*, that is a further contract change - see "Adding a fall event" below.

Your classifier may hold internal state: windows, filters, hysteresis
timers. It is called once per IMU sample that reaches the estimator.

### Where to put the file

Anywhere importable. A scratch module beside the repo is fine while you are
iterating; `backend/imu/` is the home for code you intend to keep. The IMU
module must not open sockets or import UI code (`AGENTS.md`).

## Loading Your Code

Point the backend at your classes with environment variables, in
`module.path:AttributeName` form. The attribute is constructed with no
arguments.

```bash
E014_SOURCE=udp \
E014_ANCHORS_CONFIG=backend/config/anchors.local.yaml \
E014_HEADING_ESTIMATOR=my_package.heading:MyHeading \
E014_ACTIVITY_CLASSIFIER=my_package.posture:MyPosture \
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

Either variable may be omitted to keep the baseline. If a spec cannot be
imported or constructed the backend fails at startup with a `PluginLoadError`
naming the problem, rather than silently falling back.

If your class needs constructor arguments, expose a zero-argument factory
and point the variable at that:

```python
def build_posture_classifier():
    return MyPosture(window_s=0.8, impact_g=2.4)
```

## Testing Without Hardware

### 1. Unit level

```bash
pytest tests/test_imu_heading.py tests/test_activity_classifier.py
```

Copy those tests and swap in your class. `tests/test_imu_scenario_pipeline.py`
shows the full shape, including `StubHeading` and `StubClassifier` examples of
custom plugins driving published state.

### 2. Scripted scenarios through the real estimator

`tools/fake_data/imu_scenario.py` generates contract-valid IMU packets for
posed body attitudes. Scenarios: `standing`, `walking`, `crouching`,
`lying_down`, `turn`, `fall`, `full`.

Print them:

```bash
python -m tools.fake_data.imu_scenario --scenario fall
```

Run them through your classifier offline:

```python
from backend.fusion.demo_estimator import DemoSensorEstimator
from backend.ingestion.parser import parse_packet
from tools.fake_data.imu_scenario import imu_packet_stream

estimator = DemoSensorEstimator(activity_classifier=MyPosture(), heading_estimator=MyHeading())
for packet in imu_packet_stream(scenario="full"):
    state = estimator.update(parse_packet(packet))
    print(state.activity.posture, state.orientation_xyzw)
```

These are posed attitudes plus light noise, not physics. They prove the
pipeline and the threshold bands. They do not prove your algorithm works on a
real fall.

### 3. Live, in the UI

Three terminals:

```bash
# 1 backend, with your plugins
E014_SOURCE=udp E014_ACTIVITY_CLASSIFIER=my_package.posture:MyPosture \
  uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# 2 UI
cd ui/web && npm run dev

# 3 scripted IMU over UDP, paced in real time
python -m tools.fake_data.imu_scenario --scenario full --udp --realtime --loop
```

Open http://localhost:5173. Watch the heading readout and heading line turn
during the `turn` segment, the digital twin crouch, and the prone alert
appear when the scenario reaches `lying_down`.

### Windows PowerShell

PowerShell has no inline `VAR=value command` prefix; that form is a
`CommandNotFoundException`. Set each variable on its own line first, and use
`;` rather than `&&` to chain (Windows PowerShell 5.1 has no pipeline chain
operators).

```powershell
# 1 backend, with your plugins
cd C:\path\to\dip-e014-firefighter-tracking
$env:E014_SOURCE = "udp"
$env:E014_ANCHORS_CONFIG = "backend/config/anchors.local.yaml"
$env:E014_ACTIVITY_CLASSIFIER = "my_package.posture:MyPosture"
.venv\Scripts\python.exe -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# 2 UI
cd ui\web; npm run dev

# 3 scripted IMU over UDP
.venv\Scripts\python.exe -m tools.fake_data.imu_scenario --scenario full --udp --realtime --loop
```

`$env:` variables persist for the lifetime of that terminal. Clear one with
`$env:E014_SOURCE = $null` before restarting the backend in a different
mode, or it silently keeps the old setting.

IMU-only packets hold the last known position, so the responder will not move
across the map without UWB. That is expected; posture and heading still work.

### Known limitation: `motion` needs UWB

`speed_mps` is produced by the UWB position filter. On an IMU-only stream the
estimator passes `speed_mps=0.0`, so `motion` is decided by ZUPT alone and
reports `stationary` even through the walking segments. A posture/fall
classifier that keys off `motion` will therefore behave differently with and
without UWB present.

If you want step detection from the IMU alone, derive it inside your
classifier from the accelerometer samples you already receive, rather than
relying on `speed_mps`. Verified behaviour of the shipped baseline over the
`full` scenario, IMU only:

```text
t=  1.00s  posture=standing    motion=stationary  heading=  0.0deg
t= 14.00s  posture=crouching   motion=stationary  heading=180.1deg
t= 19.00s  posture=standing    motion=stationary  heading=180.3deg
t= 22.00s  posture=lying_down  motion=stationary  heading=180.3deg
```

Heading tracked the scenario's 45 deg/s turn correctly; posture followed each
segment; `motion` never left `stationary` for the reason above.

## Adding A Fall Event Later

`posture: "lying_down"` is a *state*. A fall is an *event* with a time and a
severity, and a responder can be prone without having fallen. Adding
`fall_detected` to the state contract means, per `AGENTS.md`:

1. Explain why. 2. Update the producer (`ActivityEstimate`, the estimator).
3. Update the consumer (UI types, panels). 4. Update tests. 5. Document the
breaking change.

Do that as its own change, not bundled with algorithm work.

## Hardware Next Steps

Nothing currently emits `type: "imu"` packets. The IMU half of the pipeline
has no live source yet. In order:

### 1. Confirm which IMU you actually have

`docs/hardware_setup.md` specifies an **ICM-42688-P**. The lab bring-up
handoffs `IMU-LAB-01` and `IMU-LAB-02` are written for an **ICM-20948**.
Different chip, different WHO_AM_I register and register map. Resolve this
before writing firmware.

### 2. Wire the IMU to an ESP32 over I2C

```text
IMU VCC  -> ESP32 3V3        (not 5V)
IMU GND  -> ESP32 GND
IMU SDA  -> ESP32 GPIO21
IMU SCL  -> ESP32 GPIO22
```

Confirm the board's default I2C pins; they vary between ESP32 variants. Keep
the foot-mounted IMU's orientation fixed and documented - never silently swap
axes in code (`AGENTS.md`). Record which physical axis points up, forward,
and left, because that mapping is what `backend/imu/frames.py` will encode.

Follow `IMU-LAB-01`: scan the bus, read the identity register, prove the chip
answers before streaming anything.

### 3. Stream IMU packets over UDP

Follow `IMU-LAB-02`. The firmware must emit the generic contract to UDP 9000,
one packet per sample:

```json
{
  "version": 1,
  "node_id": "wearable_01",
  "sequence_number": 1001,
  "timestamp_us": 123456789,
  "type": "imu",
  "data": {
    "ax_mps2": 0.12, "ay_mps2": -0.03, "az_mps2": 9.78,
    "gx_radps": 0.01, "gy_radps": -0.02, "gz_radps": 0.1
  }
}
```

Requirements that matter to the estimator:

- **SI units.** m/s^2 and rad/s, converted on the device. Not raw LSBs, not g,
  not deg/s.
- **Device timestamps** in integer microseconds, monotonic, from the device's
  own clock. The backend derives `dt` from these.
- **Monotonic `sequence_number`** per node, so dropped packets are detectable.
- **A stable `node_id`.** The UWB tag uses `dwm3000_tag_<tag_id>`; pick
  something distinct for the foot node, e.g. `wearable_01`.
- **100 Hz or better** if you intend to do ZUPT. The scenario generator
  defaults to 50 Hz (`--dt-s 0.02`).

Chip-specific parsing stays on the device or in a `tools/` adapter, never in
the backend parser - the same boundary the DWM3000 adapter respects.

### 4. Decide the wearable topology

`AGENTS.md` forbids hard-coding whether the foot IMU shares the UWB tag's
ESP32 or runs on its own node. Both work: the backend keys on `node_id`, and
IMU and UWB packets arrive on the same UDP port from either source.
`FW-LAB-01` covers the combined-bridge feasibility question.

### 5. Calibrate before trusting posture

Capture the IMU stationary and level for 30 s and record the mean gyro bias
and the accelerometer's measured gravity vector. Without bias removal, an
integrated heading drifts quickly and tilt thresholds sit at the wrong angle.
`backend/imu/calibration.py` holds the bias dataclass; `tools/imu_calibration/`
is where the procedure belongs.
