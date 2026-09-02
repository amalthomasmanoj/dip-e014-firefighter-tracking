# Contributing

## Development Environment

Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Frontend:

```bash
cd ui/web
npm install
npm run build
```

## Workflow

```text
GitHub issue
    -> feature branch
    -> implementation
    -> tests
    -> PR
    -> human review
    -> main
```

Use descriptive branches such as `feat/uwb-parser` or `fix/timestamp-wraparound`.

## Pull Requests

- Link the issue.
- State what changed and how it was tested.
- Include screenshots for UI changes.
- Call out contract changes explicitly.
- Do not include real credentials, large recordings, or generated debug files.

## Contracts

Contracts in `contracts/` are shared boundaries between firmware, backend, logging, replay, and UI work. A contract change must update examples, producers, consumers, tests, and docs in the same PR.

## Experiment Data

Do not commit real experiment recordings. Large logs, MCAP files, ROS bags, and raw captures are ignored. Small deterministic fixtures may live in `data/samples/`.

## Issues

Prefer scoped issue titles with acceptance criteria:

```text
IMU-01: Receive 100 Hz raw ICM-42688 accel/gyro stream
```

Example labels:

```text
area:firmware
area:imu
area:uwb
area:fusion
area:logging
area:ui
area:contracts
area:experiments
type:feature
type:bug
type:test
type:docs
priority:critical
priority:high
priority:normal
blocked
```

