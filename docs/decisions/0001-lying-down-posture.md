# 0001 - Add `lying_down` To The Posture Contract

## Status

Accepted.

## Context

`contracts/estimated_state.schema.json` allowed two postures, `standing` and
`crouching`. A firefighter who has fallen or is crawling under smoke is
neither, and a prone responder is the single most operationally important
posture the system can report.

The classifier already derived a tilt angle from the gravity vector and
thresholded it once. Reporting a horizontal body as `crouching` loses the
distinction that matters most to an incident commander.

## Decision

Extend the `activity.posture` enum to:

```text
standing | crouching | lying_down
```

`lying_down` is a *posture state*, not a fall *event*. A responder can be
prone without having fallen, and a fall event carries a time and a severity
that a state field cannot express. A separate `fall_detected` field remains
possible future work and is deliberately not added here.

## Consequences

Per the `AGENTS.md` contract-change procedure:

- **Producer**: `backend/imu/activity.py` gains a second tilt threshold
  (`DEFAULT_LYING_TILT_THRESHOLD_RAD`, 1.22 rad / ~70 degrees) and the
  `lying_down` branch.
- **Consumer**: `ui/web/src/types/state.ts` widens the posture union;
  `StatePanel` shows a prone alert; `DigitalTwinView` lays the avatar flat in
  both the three.js and canvas-fallback renderers.
- **Tests**: `tests/test_activity_classifier.py`, `tests/test_contracts.py`,
  `tests/test_imu_scenario_pipeline.py`, and
  `ui/web/src/components/StatePanel.test.ts`.
- **Breaking change**: a consumer that exhaustively matches on posture must
  handle the third value. Within this repository the UI is the only consumer
  and it has been updated. Any external consumer pinned to the two-value enum
  will reject states from a prone responder.

The tilt threshold is a bring-up default, not a validated clinical value. It
is chosen so a clearly horizontal trunk classifies as prone and a deep crouch
does not. Validate it against real foot/trunk IMU recordings before relying
on it operationally.
