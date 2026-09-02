# Contracts

Contracts are the shared source of truth between firmware, backend, logging, replay, and UI code.

The bootstrap contracts are versioned JSON payloads:

- `packet_schema.json`: transport packet envelope for IMU and UWB range packets.
- `estimated_state.schema.json`: estimator output contract.
- `websocket_state.schema.json`: WebSocket state message contract.

Changing a contract requires updating examples, producers, consumers, tests, and documentation together.

