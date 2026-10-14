# Web UI

Vite React TypeScript UI for the indoor firefighter tracking display.

Current bootstrap features:

- XY metric map
- movable simulated anchors with continuous pair-exchange visualization
- two independently tracked simulation firefighters in the map and digital twin
- backend movement controls and separate trajectory trails
- live responder marker from WebSocket state
- uncertainty ellipse
- state and sensor status panels

The UI renders `EstimatedState` and does not perform localization, trilateration, or fusion.


See [simulation controls and API](../../docs/simulation.md) for operation and limitations.
