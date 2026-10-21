// Copy to config.h and fill in. config.h is gitignored - never commit
// credentials or hotspot details.
#pragma once

#define WIFI_SSID "your-hotspot-ssid"
#define WIFI_PASS "your-hotspot-password"

// The laptop running tools.uwb.dwm3000_udp_adapter.
// Find it with `ipconfig` on Windows, `ip addr` on Linux.
#define LAPTOP_IP "192.168.137.1"
#define LAPTOP_PORT 7007

// Integer tag identity. The backend sees this as node_id
// "dwm3000_tag_<TAG_ID>". Each tag on the network needs a distinct value.
#define TAG_ID 10

// Sweep rate. 10 Hz is a reasonable bring-up default.
#define SWEEP_PERIOD_MS 100

// Anchors this tag ranges against, in sweep order. The string IDs MUST match
// the anchor_id values in backend/config/anchors.local.yaml, and MUST match
// the pattern A<digits> - "A1" is valid, "a1" and "ANCHOR1" are rejected by
// the adapter. ANCHOR_ADDR is the UWB short address each anchor is flashed
// with; it must match ANCHOR_SHORT_ADDR in that anchor's config.h.
#define ANCHOR_COUNT 4
#define ANCHOR_IDS \
  { "A1", "A2", "A3", "A4" }
#define ANCHOR_ADDRS \
  { 0x0001, 0x0002, 0x0003, 0x0004 }

// Antenna delay calibration. These shift every range by a constant offset and
// are the single biggest source of systematic UWB error. Start with the
// library default, then calibrate against a tape measure.
#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

// Set to 1 once real DW3000 ranging is implemented in rangeToAnchor().
// Leaving it 0 streams synthetic distances so the Wi-Fi, JSON, adapter,
// backend and UI path can be proven before the radio works.
#define USE_REAL_RANGING 0
