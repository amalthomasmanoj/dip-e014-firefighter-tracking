# Two-firefighter simulation

Run the backend with `E014_SOURCE=simulation` (the default) and run the web UI:

```bash
E014_SOURCE=simulation uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
# Separate terminal:
cd ui/web
npm run dev -- --port 5173
```

The scene starts with firefighter 1 (`sim_tag_10`) at `(1, 1)` metres and
firefighter 2 (`sim_tag_11`) at `(5, 3)` metres. Both remain stationary until
moved. Each has its own IMU history, range windows, sequence tracker, position
EKF, marker, and bounded trajectory. Orange/red identifies firefighter 1;
teal identifies firefighter 2. Both appear in the XY map and digital twin,
including the canvas fallback when WebGL is unavailable.

## Controls

- In **Simulation controls → Move**, choose either firefighter or an anchor.
- Use the direction buttons, arrow keys, or numpad 8/2/4/6 to move that node
  in 0.2 metre increments. Keyboard input is ignored while a form control has
  focus; click the map before using arrow keys.
- For a firefighter, use **Toggle lying posture** or `L` to hold the synthetic
  waist IMU horizontally. The two-second dwell still applies.
- Use **Inspect firefighter** to select the state, sensor summary, and experiment
  trail statistics shown in the sidebar.
- Restart the simulation backend to reset the scene. Browser tabs share one
  scenario; opening another tab does not start another simulation clock.

Movement is bounded to `x = [-0.5, 8.5] m`, `y = [-0.5, 6.5] m` for the default
map viewport. An anchor can move while both firefighters remain tracked. The
anchor map revision increments on movement. Collinear/insufficient geometry
produces an unresolved state and warning until a usable layout returns.

## Continuous anchor communication

Every simulation tick (nominally 10 Hz) models a successful request/response
exchange for every unordered anchor pair. Three anchors produce three links;
four produce six. The links, metre labels, and exchange counters continue to
update with all nodes stationary. Moving an anchor changes the affected pair
ranges and tag ranges on the next tick. Animated links disappear on a failed
snapshot request or when the received clock stops advancing for 1.5 seconds;
the panel labels retained readings stale and pauses controls.

These are ideal, synthetic exchanges. They do not claim a tested DWM3000
schedule, role switching, packet collision handling, RF noise, NLOS diagnostics,
or a hardware update rate. No radio firmware is changed.

## Architecture and frame choice

`backend/simulation/world.py` owns scenario inputs, synthetic measurements,
and the shared clock. It emits the existing generic IMU/UWB packet format
through ingestion into a separate `DemoSensorEstimator` for each firefighter.
The UI sends commands and renders backend results; it does not localize tags
or anchors. The synthetic IMU signal is a bring-up stimulus, not a physical
foot-motion model or a production ESKF implementation.

Anchor coordinates are **known scenario inputs in the fixed world frame**.
Pairwise telemetry visualizes communication; it does not self-survey anchors.
Moving A1 or A2 therefore does not redefine the origin or rotate the map.
All anchors, pair ranges, tag ranges, and tag estimates in a snapshot refer to
one anchor-map revision. On anchor movement the estimator clears old range
windows before consuming the next sweep, retaining its tag filter in the
unchanged world frame. Old trajectories remain valid.

Tag ranging is explicitly planar (horizontal XY distances), matching the
current 2-D demo estimator. Pair ranges are Euclidean distances between the
configured anchor coordinates. The default anchors have zero height. This
scenario must not be used to validate 3-D/slant-range localization accuracy.

The relative-frame self-survey described in
[anchor-to-anchor ranging requirements](anchor_to_anchor_ranging_requirements.md)
remains separate future hardware work. No protected contracts, coordinate-frame
document, or logging channels change in this implementation.

## Simulation API

`GET /simulation` returns an atomic latest-frame snapshot:

- `source: "simulation"`, integer-microsecond `timestamp_us`, `map_version`,
  `frame: "fixed_world"`, and `geometry_valid`;
- `anchors`: current known coordinates;
- `firefighters`: `node_id`, `label`, nullable existing `EstimatedState` in
  `state`, and that tag's raw `ranges`;
- `anchor_links`: `initiator_id`, `responder_id`, `timestamp_us`,
  `sequence_number`, `raw_range_m`, and `valid`;
- `raw_packets`: unchanged generic IMU/UWB packets for this tick, kept separate
  from filtered state.

`POST /simulation/command` accepts, for example:

```json
{"kind":"anchor","node_id":"A3","action":"move","dx_m":0.2,"dy_m":0}
```

```json
{"kind":"firefighter","node_id":"sim_tag_11","action":"toggle_lying"}
```

Movement values must be finite and at most 0.2 metres per axis per request.
Commands return `{"accepted": true}`; their results appear on the next tick.
Unknown nodes return 404, invalid commands return 422. Both endpoints return
409 in UDP or replay mode. `GET /anchors` exposes current simulation coordinates.
The existing `/ws/state` envelope remains unchanged and exposes the first
firefighter for legacy consumers; the UI uses `/simulation` for both tags.

The snapshot contains the latest raw frame, not a durable experiment recording.
MCAP recording/replay remains unimplemented. Consumers recording these frames
must retain raw packets, pair ranges, timestamps, and each version's anchor map
alongside estimated state; polling can skip frames and is not lossless capture.

## Verification

`tests/test_simulation_world.py` checks tag isolation, repeated pair exchanges,
movement of all three anchors without false tag displacement, degenerate
geometry/recovery, unchanged measurement/state schemas, rejected commands,
source-mode isolation, and shared-clock lifecycle. Frontend tests check independent,
bounded trails, reconnect reset, unresolved states, and command transport.

```bash
python3 -m pytest
cd ui/web
npm test
npm run build
```
