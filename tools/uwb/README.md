# UWB Adapter Tools

`dwm3000_udp_adapter.py` receives the current ESP32 + DWM3000 tag sweep
format on UDP port `7007` and emits one contract-valid `uwb_range` packet per
anchor to the backend's generic UDP port `9000`.

The adapter also accepts anchor-v2 survey results forwarded by the tag and
emits `uwb_pair_range` packets. The supplied anchor firmware sends stage 6 in
this byte layout after a stage-5 command:

```text
RX byte 1  initiating anchor ID
RX byte 2  commanding tag ID
RX byte 3  stage = 6
RX byte 4  target anchor ID
RX byte 5  success flag
RX byte 6  distance millimetres, low byte
RX byte 7  distance millimetres, high byte
RX byte 8  RSSI-to-first-path gap in dB
RX byte 9  negated RSSI in dBm
```

The tag must preserve its existing sweep fields and append each decoded result
to `surveys`. A survey-only datagram may use an empty `anchors` object:

```json
{
  "t": 512900,
  "tag_id": 10,
  "anchors": {},
  "surveys": [
    {
      "initiator_id": 1,
      "target_id": 2,
      "ok": true,
      "distance_mm": 1967,
      "rssi_gap_db": 5,
      "rssi_dbm": -78
    }
  ]
}
```

Failed stage-6 results use `ok: false`, `distance_mm: 0`, and `null` for both
RSSI fields. The supplied tag-v3 firmware round-robins the three required pairs
`A1-A2`, `A1-A3`, and `A2-A3` and uses a tag-to-tag token to keep its normal
ranging and survey exchanges serialized. Both tags may report pair ranges when
they follow that shared token schedule. The laptop cannot initiate stage 5
through the existing one-way UDP broadcast; the tag scheduler/forwarder must be
flashed for live anchor movement.

The adapter is intentionally outside the backend parser. DWM3000-specific
field names, centimetre-to-metre conversion, and sweep expansion stay at the
hardware edge; backend ingestion and fusion continue to consume the generic
packet contract.

Run the backend and adapter in separate terminals:

```bash
E014_SOURCE=udp uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
python3 -m tools.uwb.dwm3000_udp_adapter
```

Defaults:

```text
DWM3000 listen address    0.0.0.0:7007
generic packet target     127.0.0.1:9000
node ID                   dwm3000_tag_<tag_id>
```

To preserve the original sweep payload and PC arrival time for later replay,
provide an ignored JSONL output path outside the repository or under an
ignored data directory:

```bash
python3 -m tools.uwb.dwm3000_udp_adapter \
  --raw-jsonl /path/to/dwm3000_raw.jsonl
```

The raw capture is optional and append-only. It records the original payload,
sender address, and wall-clock arrival time before conversion. Do not commit
real recordings or hotspot credentials.

Sweep diagnostics (`rssi` and `fp_rssi`) are accepted when the authoritative
firmware provides them, but they are optional and are not mapped to contract
`quality`: no validated conversion to a generic score has been established.
Transport fixtures set `"synthetic": true`; the adapter then uses a
`dwm3000_sim_tag_<id>` node ID so that data cannot be confused with a real tag.

At least three responding anchors with measured coordinates are needed for
the current demo estimator to produce a 2-D position. Receiving one or two
anchors still proves the real range ingestion path but is insufficient for
trilateration.

Anchor IDs are not fixed to `A1`/`A2`/`A3`. Put every installed anchor and its
measured coordinates in a YAML file, then set `E014_ANCHORS_CONFIG` when
starting the backend. For example, a responding `A4` is usable only when `A4`
has a coordinate entry. See the repository README for the launch command.

With three configured anchors, the first three IDs establish the surveyed
relative frame. Three complete accepted survey cycles initialize the map.
Movement must persist for three more complete cycles and exceed 0.25 m before
the backend commits a new map version. Check live survey state at
`GET /uwb/anchor-map`; `GET /anchors` returns the latest committed coordinates.
If more than three anchors are configured, only the first three enter the
self-surveyed map for now; the others are excluded after the first map commit
so fixed-frame coordinates are never mixed with the new relative frame.
