# Experiment Protocol

The baseline experiments should measure graceful degradation and recovery:

- UWB noise
- UWB unreliable ranges / NLOS-like behavior where possible
- UWB dropout
- UWB latency
- IMU noise
- IMU bias and drift
- initialization error
- recovery after UWB returns

Raw measurements must be preserved so the same recording can be replayed through later estimator versions.

Latency experiments must preserve both the measurement timestamp and delayed arrival time.

