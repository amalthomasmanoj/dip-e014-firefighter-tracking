# Backend

Python backend for packet ingestion, measurement processing, fusion, logging, replay, and API publishing.

Current bootstrap status:

- typed packet/state models
- packet parser
- sequence tracker
- simple ZUPT detector API
- synthetic UWB trilateration utility
- deterministic fake state stream
- FastAPI WebSocket endpoint

Production ESKF, real hardware drivers, Foxglove SDK, and MCAP writer integration are not implemented yet.

