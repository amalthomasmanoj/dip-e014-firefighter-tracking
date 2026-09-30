# UWB Adapter Tools

`dwm3000_udp_adapter.py` receives the current ESP32 + DWM3000 tag sweep
format on UDP port `7007` and emits one contract-valid `uwb_range` packet per
anchor to the backend's generic UDP port `9000`.

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

The current sweep diagnostics (`rssi` and `fp_rssi`) are preserved in optional
raw capture but are not mapped to contract `quality`: no validated conversion
from those two measurements to a generic quality score has been established.

At least three responding anchors with measured coordinates are needed for
the current demo estimator to produce a 2-D position. Receiving one or two
anchors still proves the real range ingestion path but is insufficient for
trilateration.
