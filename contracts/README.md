# Contracts

Contracts are the shared source of truth between firmware, backend, logging, replay, and UI code.

The bootstrap contracts are versioned JSON payloads:

- `packet_schema.json`: transport packet envelope for IMU, tag-to-anchor UWB,
  and anchor-to-anchor UWB range packets.
- `estimated_state.schema.json`: estimator output contract.
- `websocket_state.schema.json`: WebSocket state message contract.

Changing a contract requires updating examples, producers, consumers, tests, and documentation together.

The 2026-10 anchor-survey change adds `uwb_pair_range` to packet version 1.
This is backward compatible: existing `imu` and `uwb_range` packets are
unchanged. The DWM3000 edge adapter produces the new type, backend ingestion
parses it, and the live anchor-map tracker consumes it.
