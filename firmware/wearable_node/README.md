# Wearable Node

ESP32 wearable/tag firmware placeholder.

This may eventually read both UWB and foot-mounted IMU data, or it may coordinate with a separate shoe node. Do not hard-code the physical topology into estimator logic.

The supplied tag-v3 sketch is compatible with the laptop adapter. It:

- uses unique tag IDs 10 and 11;
- alternates radio turns between the two tags;
- keeps peer ranges outside the anchor range object;
- commands stage-5 anchor surveys and emits stage-6 results in `surveys`;
- retains single-tag operation when the peer is absent.

Apply the same SPI transaction-length correction described in the anchor-node
README before flashing. For two-tag operation, increase `TOKEN_TIMEOUT_MS` from
150 to at least 500 ms. A turn can include three 30 ms anchor timeouts, a peer
timeout, and an 80 ms survey wait, so 150 ms can make the passive tag take over
while the active tag is still using the radio.

Flash one tag with `TAG_ID 10` and the other with `TAG_ID 11`. Do not commit the
hotspot name or password from a local sketch.
