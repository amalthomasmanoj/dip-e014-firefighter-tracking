# Fake Data

`simulated_walk.py` provides deterministic fake `EstimatedState` samples and contract-valid fake sensor packets for UI, API, logging, parser, and adapter development before hardware arrives.

The path is intentionally simple:

```text
start -> straight segment -> 90-degree turn -> second straight segment -> stop
```

The sensor packet generator is a contract and integration tool. It is not a physics-grade inertial simulator.

Examples:

```bash
python tools/fake_data/simulated_walk.py --kind state --count 10
python tools/fake_data/simulated_walk.py --kind imu --count 10
python tools/fake_data/simulated_walk.py --kind uwb --count 10
python tools/fake_data/simulated_walk.py --kind mixed --count 10
```
