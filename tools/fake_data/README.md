# Fake Data

`simulated_walk.py` provides deterministic fake `EstimatedState` samples and contract-valid fake sensor packets for UI, API, logging, parser, and adapter development before hardware arrives.

The path is intentionally simple:

```text
start -> straight segment -> 90-degree turn -> second straight segment -> stop
```

The sensor packet generator is a contract and integration tool. It is not a physics-grade inertial simulator.

`imu_scenario.py` generates contract-valid IMU packets for posed body
attitudes, so heading and posture code can be exercised without hardware. It
can print JSON lines or stream over UDP to the live backend:

```bash
python -m tools.fake_data.imu_scenario --scenario fall
python -m tools.fake_data.imu_scenario --scenario full --udp --realtime --loop
```

Scenarios: `standing`, `walking`, `crouching`, `lying_down`, `turn`, `fall`,
`full`. The accelerations are posed attitudes plus light noise, not a physics
simulation; they prove the pipeline and classifier bands, not sensor realism.

Examples:

```bash
python tools/fake_data/simulated_walk.py --kind state --count 10
python tools/fake_data/simulated_walk.py --kind imu --count 10
python tools/fake_data/simulated_walk.py --kind uwb --count 10
python tools/fake_data/simulated_walk.py --kind mixed --count 10
```
