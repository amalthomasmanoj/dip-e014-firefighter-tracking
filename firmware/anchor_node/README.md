# Anchor Node

ESP32 + DWM3000EVB anchor role.

The supplied anchor-v2 sketch confirms two supported radio roles:

- normal DS-TWR response to a tag or another anchor;
- stage-5 commanded DS-TWR initiation to a peer anchor, followed by a stage-6
  result sent back to the commanding tag.

Set a unique `ANCHOR_ID` for each flashed unit. The laptop-side stage-6 format,
tag forwarding JSON, and continuous three-pair schedule are documented in
[`tools/uwb/README.md`](../../tools/uwb/README.md).

The repository does not yet contain a reproducible Arduino/PlatformIO build
for this sketch because the exact ESP32 board definition and build settings
were not supplied. Keep those settings with the source before treating a flash
as reproducible.
