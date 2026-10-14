# Backend

Python backend for packet ingestion, measurement processing, fusion, logging, replay, and API publishing.

Current bootstrap status:

- typed packet/state models
- packet parser
- sequence tracker
- stationary IMU detection with zero-velocity updates on the 2-D UWB EKF
- synthetic UWB trilateration utility
- shared two-firefighter simulation with movable known anchors
- continuous synthetic anchor-pair ranges and per-tag estimators
- FastAPI WebSocket endpoint

The live estimator performs median UWB filtering, 2-D constant-velocity EKF
smoothing, innovation gating, and foot-stationary zero-velocity updates. It
does not propagate accelerometer measurements because the physical IMU mounting
transform and calibration are not established. Production ESKF, real hardware
drivers, Foxglove SDK, and MCAP writer integration are not implemented yet.


The simulation-only API and fixed-frame behavior are documented in [simulation.md](../docs/simulation.md).
