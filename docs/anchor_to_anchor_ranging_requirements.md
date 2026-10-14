# Anchor-to-Anchor Ranging Requirements

## Goal

Allow powered UWB anchors to determine a relative coordinate frame, update
their displayed positions when an anchor moves, and provide current anchor
coordinates for locating tag 10 and future tags such as tag 11.

The desired relative frame is:

```text
A1 = (0, 0)
A2 = (distance(A1, A2), 0)
A3 or the next available anchor = positive-y solution
additional anchors = solved relative to the established anchors
```

This is relative indoor positioning. It does not provide latitude/longitude or
an absolute building coordinate without an additional surveyed transform.

## What Is Needed From The Hardware/Firmware Owner

### 1. Actual Firmware Source

Provide the exact source currently flashed onto:

- anchor A1;
- anchor A2;
- anchor A3/A4 and any other anchors;
- mobile tag 10;
- future mobile tags such as tag 11.

Include all local libraries, configuration headers, board definitions, and
build instructions. The repository currently contains placeholder anchor/tag
firmware, so it is not enough to modify the laptop backend alone.

### 2. Hardware Identification

For every node, provide:

- ESP32 board model;
- DWM3000/DWM3000EVB board model and revision;
- wiring and pin assignments;
- antenna-delay calibration values, if configured;
- node ID and current UWB address;
- whether the node can initiate ranging, respond to ranging, or both;
- whether changing initiator/responder roles is supported by the current
  firmware and library.

Do not assume that an anchor can initiate anchor-to-anchor ranging until this
is confirmed on the real firmware.

### 3. Current UWB Schedule And Protocol

Document the current exchange sequence, including:

- single-sided or double-sided two-way ranging;
- poll, response, and final-message sequence;
- slot duration and complete sweep duration;
- how collisions are prevented;
- which node controls the schedule;
- timeout and retry behavior;
- maximum supported anchors and tags;
- how tag 10 and tag 11 are distinguished;
- timestamp source and wraparound behavior.

### 4. Current Network Output

Provide raw, unedited examples of:

- one normal tag-to-anchor sweep;
- one sweep with an anchor missing;
- one invalid or timed-out range;
- any existing anchor-to-anchor measurement;
- startup and node-discovery messages;
- at least 30 seconds of data while all devices are stationary;
- at least 30 seconds while one anchor is deliberately moved.

The current observed message contains tag-to-anchor ranges only:

```json
{
  "t": 123456,
  "tag_id": 10,
  "anchors": {
    "A1": {"distance": 150.0, "raw": 150.0, "rssi": -80.0, "fp_rssi": -82.0},
    "A2": {"distance": 210.0, "raw": 210.0, "rssi": -81.0, "fp_rssi": -83.0}
  }
}
```

That message alone cannot reveal anchor-to-anchor distances or instantaneous
anchor coordinates.

### 5. Physical Test Information

Provide:

- number of anchors available simultaneously;
- intended maximum floor area;
- approximate anchor and tag antenna heights;
- whether anchors may move during normal tracking;
- expected movement speed of a movable anchor;
- expected number of simultaneous tags;
- whether line-of-sight can be maintained during calibration;
- one surveyed tape-measure dataset for checking UWB accuracy.

The tape-measure dataset should include the true distances for every available
anchor pair, for example:

```text
A1-A2 = ... m
A1-A4 = ... m
A2-A4 = ... m
```

These values are for validation; the final dynamic system should estimate the
same distances from UWB.

## Required Firmware Capability

The firmware must produce fresh pairwise ranges between anchors. With three
anchors, the minimum set is:

```text
A1 <-> A2
A1 <-> A3/A4
A2 <-> A3/A4
```

For more than three anchors, each new anchor should range to at least three
already positioned, non-collinear anchors when possible. Extra pairwise ranges
provide redundancy and make outlier rejection possible.

The schedule must interleave anchor-to-anchor and tag-to-anchor exchanges
without packet collisions or ambiguous timestamps. Raw measurements must not
be replaced by filtered values.

## Proposed Measurement Information

The final wire representation is not approved yet. A pairwise measurement must
at least carry:

```text
measurement timestamp in integer microseconds
sequence number
initiator node ID
responder node ID
range in metres
valid/invalid flag
optional hardware diagnostics only when confirmed and documented
```

Illustrative payload only:

```json
{
  "version": 1,
  "node_id": "A1",
  "sequence_number": 123,
  "timestamp_us": 123456789,
  "type": "uwb_pair_range",
  "data": {
    "peer_id": "A2",
    "range_m": 1.967,
    "valid": true
  }
}
```

This example is not yet part of `contracts/**`. Changing the protected packet
contract requires coordinated producer, parser, consumer, test, and breaking-
change documentation updates.

## Relative Coordinate Solution

For three anchors with filtered pairwise distances `d12`, `d13`, and `d23`:

```text
A1 = (0, 0)
A2 = (d12, 0)

A3.x = (d13^2 - d23^2 + d12^2) / (2 * d12)
A3.y = +sqrt(d13^2 - A3.x^2)
```

The positive-y choice fixes the otherwise mirrored solution. Invalid triangle
geometry must be rejected rather than forced into coordinates:

```text
abs(d13 - d23) <= d12 <= d13 + d23
```

For four or more anchors, coordinates should be estimated with robust
least-squares multilateration using all accepted pairwise measurements.

## Filtering And Anchor-Movement Detection

The implementation should keep these concepts separate:

```text
raw pairwise range
calibrated pairwise range
filtered pairwise range
accepted/rejected range
estimated anchor coordinate
```

Recommended processing:

1. Preserve every raw measurement for replay.
2. Reject invalid, stale, or physically impossible triangle measurements.
3. Apply a short robust range filter.
4. Estimate anchor coordinates in the relative frame.
5. Smooth anchor coordinates with an anchor-state filter.
6. Declare an anchor as moving only after sustained displacement, not one
   noisy range.
7. Recompute tag positions using one internally consistent anchor-map version.

When A1 moves, the whole relative frame changes because A1 is the origin. When
A2 moves, the frame rotation and scale baseline change. The UI and tag
trajectory must handle those frame changes explicitly instead of displaying a
false tag movement.

## Laptop-Side Work After Firmware Is Available

The implementation will require coordinated changes to:

- hardware-edge adapter for the confirmed pairwise packet format;
- typed measurement model and parser;
- sequencing and stale-measurement handling;
- raw logging/replay channels;
- pairwise range outlier rejection;
- relative anchor-coordinate estimator;
- per-tag estimator state for tag 10, tag 11, and later tags;
- `/anchors` API so coordinates can update at runtime;
- WebSocket state or a separate anchor-state stream;
- Cartesian and digital-twin anchor updates;
- unit, integration, replay, and frontend tests;
- packet-contract and breaking-change documentation.

The UI must only render coordinates produced by the backend. It must not
perform anchor localization or tag trilateration.

## Acceptance Tests

### Stationary Test

- Keep all anchors and tag 10 stationary for at least 60 seconds.
- Confirm pairwise ranges remain available.
- Confirm displayed anchors do not visibly wander.
- Confirm the filtered tag position remains stable.

### Anchor Movement Test

- Move one non-reference anchor by a measured distance.
- Confirm only that anchor moves in the relative map.
- Confirm the new coordinate agrees with the tape measurement within the
  agreed tolerance.
- Confirm tag tracking recovers without a large false trajectory.

### Reference-Anchor Test

- Move A1 or A2 deliberately.
- Confirm the system reports a relative-frame change.
- Confirm all tag and anchor states use the same new frame version.

### Multiple-Tag Test

- Operate tag 10 and tag 11 simultaneously.
- Confirm ranges and estimator states are never mixed between tags.
- Confirm each tag has an independent marker and trajectory.

### Dropout And Outlier Test

- Power off one anchor temporarily.
- Inject or observe an invalid pairwise measurement.
- Confirm the last reliable map is marked degraded rather than silently
  replaced with impossible coordinates.
- Confirm raw measurements remain available for replay.

## Immediate Next Step

Provide the exact ESP32/DWM3000 firmware project currently flashed on the
anchors and tag. After reviewing its ranging roles and timing schedule, the
pairwise ranging design can be finalized without inventing unsupported hardware
behavior.
