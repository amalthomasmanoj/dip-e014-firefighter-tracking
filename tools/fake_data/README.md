# Fake Data

`simulated_walk.py` provides deterministic fake `EstimatedState` samples for UI, API, logging, and adapter development before hardware arrives.

The path is intentionally simple:

```text
start -> straight segment -> 90-degree turn -> second straight segment -> stop
```

It is not a physically accurate IMU simulator.

