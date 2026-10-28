# Lab Bring-Up Firmware

Lab-only ESP32 firmware for the borrowed hardware. Per `LAB-01`, nothing here
is production firmware and nothing here belongs under `firmware/wearable_node/`
or `firmware/anchor_node/` yet.

```text
esp32_dwm3000_tag/      synthetic UDP transport fixture
esp32_dwm3000_anchor/   non-functional library-integration reference
```

These sketches are not the project firmware. The existing tag-v3 and
anchor-v2 sources remain authoritative for real ranging and anchor surveys.
Nothing in this directory should be used to record an experiment as hardware
data.

## Before You Flash: Is This Even Needed?

`docs/anchor_to_anchor_ranging_requirements.md` records that working tag
firmware already exists somewhere in the project - the observed sweep format
with `tag_id: 10` came from a real device. **Ask the firmware owner for the
flashed source before rewriting it.** If you already have working firmware,
the only things you need from this directory are the wire format (below) and
the anchor-ID agreement.

## Roles

The two boards are physically identical. The role is entirely in the
firmware:

| | Tag | Anchor |
|---|---|---|
| Wi-Fi | yes, sends to the laptop | none |
| UWB | initiates ranging | responds only |
| Identity | `TAG_ID` integer, e.g. 10 | `ANCHOR_SHORT_ADDR` + label `A1` |
| Appears to backend as | `node_id: dwm3000_tag_10` | a key inside the tag's sweep |

Only the tag drives the schedule, so anchors cannot collide on their own.

## Wiring: ESP32 DevKit V1 <-> DWM3000EVB

```text
DWM3000        ESP32        note
VCC/3V3   ->   3V3          3.3V only - 5V will damage the module
GND       ->   GND
SCK       ->   GPIO18       VSPI clock
MISO      ->   GPIO19
MOSI      ->   GPIO23
CS/SS     ->   GPIO4
RST       ->   GPIO27
IRQ       ->   GPIO34       input-only pin, correct for an interrupt
```

Confirm against your own board before power-on. A Makerfabs "ESP32 UWB
DW3000" integrated board matches this map; a bare DevKit plus a DWM3000EVB
shield may not. Keep SPI leads short - long jumpers cause intermittent
`dwt_checkidlerc` failures that look like dead modules.

## Configuration

Each sketch reads a gitignored `config.h`. Copy the example and edit:

```bash
cp esp32_dwm3000_tag/config_example.h esp32_dwm3000_tag/config.h
cp esp32_dwm3000_anchor/config_example.h esp32_dwm3000_anchor/config.h
```

Never commit `config.h`; it holds Wi-Fi credentials.

Flash each anchor with a **different** `ANCHOR_SHORT_ADDR` and `ANCHOR_LABEL`,
and make the tag's `ANCHOR_IDS` / `ANCHOR_ADDRS` lists agree with them. The
label strings must also match `anchor_id` in your
`backend/config/anchors.local.yaml`.

## Synthetic Wire Format (Verified Against The Adapter)

The tag emits one UDP datagram per sweep to port 7007, distances in
**centimetres**:

```json
{"t":12345,"tag_id":10,"synthetic":true,"anchors":{
  "A1":{"distance":150.23,"raw":151.07}}}
```

`tests/test_firmware_wire_format.py` reproduces this formatting and pushes it
through the real parser. Rules the adapter enforces:

- `rssi` and `fp_rssi` are optional. Do not fabricate them when the selected
  DWM3000 path does not expose validated diagnostics.
- Anchor IDs must match `A<digits>`, uppercase. `a1` and `ANCHOR1` are
  rejected.
- Distances must be numeric and non-negative. Never send a string.
- An empty `anchors` object is rejected, so the firmware stays silent when no
  anchor answers rather than sending an unusable sweep.
- A non-responding anchor is **absent** from the object. Never substitute a
  zero or the previous sweep's value.

Distances stay in centimetres on the wire; the laptop-side adapter converts
to metres. Do not convert on the device.

## Bring-Up Order

Prove the transport before the radio. The fixture ships with
`USE_REAL_RANGING 0`. Its packets carry `"synthetic": true`, and the adapter
maps them to `dwm3000_sim_tag_<id>` so they cannot be mistaken for tag-v3 data.

1. **Flash the tag with `USE_REAL_RANGING 0`.** Watch the serial log at
   115200 for a Wi-Fi connection and a sweep line.
2. **Confirm packets reach the laptop.** Run the adapter and look for
   forwarded packets, or watch the live table from the node sniffer. No
   traffic almost always means the firewall is blocking inbound UDP for
   `python.exe`, or `LAPTOP_IP` is stale.
3. **Confirm the backend and UI react** with the synthetic distances. At this
   point the whole laptop-side path is proven.
4. **Flash the anchors.** Identify each board by its boot label over USB
   serial and write the label on the board physically.
5. **Switch to the authoritative tag-v3/anchor-v2 firmware** for real radio
   work. Do not turn this fixture into a second production implementation.
6. **Calibrate antenna delay in the authoritative firmware.** Place the tag at a tape-measured distance and
   adjust `TX_ANT_DLY`/`RX_ANT_DLY` until the reported range matches. This is
   the largest systematic error in a DW3000 setup; uncalibrated boards are
   routinely tens of centimetres out.
7. **Measure and record anchor coordinates** into
   `backend/config/anchors.local.yaml`. Three or more non-collinear anchors
   are required before any position appears.

## Known Gaps

- `rangeToAnchor()` and the anchor responder loop are deliberately not
  implemented here. These files only preserve the electrical and integration
  seams used during transport bring-up.
- The sweep carries tag-to-anchor ranges only. Anchor-to-anchor ranging,
  which `docs/anchor_to_anchor_ranging_requirements.md` specifies, is not
  supported by this firmware.
- Signal diagnostics are not emitted by the fixture because their hardware
  availability and meaning have not been validated.
