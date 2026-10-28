# Backend

Python backend for packet ingestion, measurement processing, fusion, logging, replay, and API publishing.

Current bootstrap status:

- typed packet/state models
- packet parser
- sequence tracker
- waist-IMU heading and sustained posture classification
- synthetic UWB trilateration utility
- shared two-firefighter simulation with movable known anchors
- continuous synthetic anchor-pair ranges and per-tag estimators
- FastAPI WebSocket endpoint

Production ESKF, real hardware drivers, Foxglove SDK, and MCAP writer integration are not implemented yet.


The simulation-only API and fixed-frame behavior are documented in [simulation.md](../docs/simulation.md).
