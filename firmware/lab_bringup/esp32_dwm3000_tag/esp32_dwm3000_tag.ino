// ESP32 + DWM3000 tag: range against anchors and broadcast one sweep per
// cycle as UDP JSON on port 7007.
//
// Lab bring-up firmware. The wire format below is the one
// tools/uwb/dwm3000_udp_adapter.py parses; it is verified against that
// parser. Do not change field names, units, or anchor ID spelling without
// changing the adapter and its tests together.
//
// Emitted transport-fixture payload, distances in CENTIMETRES:
//   {"t":12345,"tag_id":10,"synthetic":true,"anchors":{
//      "A1":{"distance":150.23,"raw":151.07}}}
//
// Signal diagnostics are intentionally omitted: their availability has not
// been confirmed on the project hardware. The adapter rejects an anchor ID
// outside A<digits>, a distance sent as a string, a negative
// distance, or has an empty anchors object.

#include <WiFi.h>
#include <WiFiUdp.h>

#include "config.h"

#if USE_REAL_RANGING
#include "dw3000.h"
#endif

// ---------------------------------------------------------------------------
// Pin map: ESP32 DevKit V1 <-> DWM3000EVB over VSPI.
// CONFIRM THESE AGAINST YOUR BOARD before first power-on. A Makerfabs
// "ESP32 UWB DW3000" integrated board uses exactly these; a bare DevKit with
// a DWM3000EVB shield may differ.
// ---------------------------------------------------------------------------
static const uint8_t PIN_SCK = 18;
static const uint8_t PIN_MISO = 19;
static const uint8_t PIN_MOSI = 23;
static const uint8_t PIN_SS = 4;   // SPI chip select
static const uint8_t PIN_RST = 27; // DW3000 reset
static const uint8_t PIN_IRQ = 34; // DW3000 interrupt, input-only pin

static const char *kAnchorIds[ANCHOR_COUNT] = ANCHOR_IDS;
static const uint16_t kAnchorAddrs[ANCHOR_COUNT] = ANCHOR_ADDRS;

static WiFiUDP udp;
static char payload[768];

struct RangeResult {
  float distance_cm; // filtered/corrected range reported to the backend
  float raw_cm;      // uncorrected range, preserved for diagnostics
};

// ---------------------------------------------------------------------------
// THE ONE FUNCTION YOU MUST IMPLEMENT.
//
// Perform one two-way ranging exchange with the anchor at `anchor_addr`.
// Return true and fill `out` on success; return false if the anchor did not
// answer, and it is simply left out of this sweep.
//
// Fill this from your DW3000 library's SS-TWR or DS-TWR *initiator* example
// (Makerfabs/Qorvo: the ss_twr_initiator sketch). The standard flow is:
//
//   1. dwt_writetxdata() / dwt_writetxfctrl() with a poll frame addressed to
//      anchor_addr, then dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED)
//   2. poll the status register for RX good or timeout/error
//   3. on good RX: dwt_readrxdata(), recover poll TX and response RX
//      timestamps, compute time-of-flight, multiply by SPEED_OF_LIGHT
  //   4. on timeout/error: dwt_rxreset() and return false
//
// Keep the per-anchor timeout short (a few ms). ANCHOR_COUNT timeouts in a
// row must still fit inside SWEEP_PERIOD_MS.
// ---------------------------------------------------------------------------
static bool rangeToAnchor(uint16_t anchor_addr, RangeResult &out) {
#if USE_REAL_RANGING
  // TODO: implement with your DW3000 library. Until then this returns false
  // so the firmware does not report fabricated ranges as real measurements.
  (void)anchor_addr;
  (void)out;
  return false;
#else
  // Transport-test mode: synthetic but plausible distances that drift slowly,
  // so the whole path can be proven before the radio works. These are NOT
  // measurements. USE_REAL_RANGING must be 1 for any recorded experiment.
  const float base_cm = 150.0f + 60.0f * (float)(anchor_addr & 0x0F);
  const float wobble_cm = 25.0f * sinf((float)millis() / 1000.0f + anchor_addr);
  out.raw_cm = base_cm + wobble_cm;
  out.distance_cm = out.raw_cm;
  return true;
#endif
}

static void connectWifi() {
  Serial.printf("connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.printf("\nconnected, tag IP %s -> laptop %s:%d\n",
                WiFi.localIP().toString().c_str(), LAPTOP_IP, LAPTOP_PORT);
}

#if USE_REAL_RANGING
static dwt_config_t dw_config = {
    5,                // channel 5
    DWT_PLEN_128,     // preamble length
    DWT_PAC8,         // preamble acquisition chunk size
    9,                // TX preamble code
    9,                // RX preamble code
    1,                // SFD type
    DWT_BR_6M8,       // data rate
    DWT_PHRMODE_STD,  // PHY header mode
    DWT_PHRRATE_STD,  // PHY header rate
    (129 + 8 - 8),    // SFD timeout
    DWT_STS_MODE_OFF, // STS disabled
    DWT_STS_LEN_64,
    DWT_PDOA_M0,
};

static void initDw3000() {
  spiBegin(PIN_IRQ, PIN_RST);
  spiSelect(PIN_SS);
  delay(2);

  while (!dwt_checkidlerc()) {
    Serial.println("DW3000 not in IDLE_RC - check wiring and 3V3 power");
    delay(1000);
  }
  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) {
    Serial.println("dwt_initialise failed - halting");
    while (true) {
      delay(1000);
    }
  }
  if (dwt_configure(&dw_config)) {
    Serial.println("dwt_configure failed - halting");
    while (true) {
      delay(1000);
    }
  }
  dwt_configuretxrf(&txconfig_options);
  dwt_setrxantennadelay(RX_ANT_DLY);
  dwt_settxantennadelay(TX_ANT_DLY);
  dwt_setrxaftertxdelay(240);
  dwt_setrxtimeout(400);
  Serial.println("DW3000 ready");
}
#endif

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("\nE014 DWM3000 tag %d, real ranging %s\n", TAG_ID,
                USE_REAL_RANGING ? "ON" : "OFF (synthetic transport test)");

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_SS);
  connectWifi();
#if USE_REAL_RANGING
  initDw3000();
#endif
  udp.begin(0);
}

void loop() {
  const uint32_t sweep_start_ms = millis();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("wifi dropped, reconnecting");
    connectWifi();
  }

  // Build the sweep object incrementally, skipping anchors that did not
  // answer. An anchor missing from the object is how a dropout is reported;
  // never substitute a zero or a stale distance.
  int offset = 0;
  offset += snprintf(payload + offset, sizeof(payload) - offset,
                     "{\"t\":%lu,\"tag_id\":%d,\"synthetic\":true,\"anchors\":{",
                     (unsigned long)sweep_start_ms, TAG_ID);

  int responded = 0;
  for (int i = 0; i < ANCHOR_COUNT; i++) {
    RangeResult result;
    if (!rangeToAnchor(kAnchorAddrs[i], result)) {
      continue;
    }
    if (result.distance_cm < 0.0f || result.raw_cm < 0.0f) {
      continue; // the adapter rejects negative distances outright
    }
    offset += snprintf(payload + offset, sizeof(payload) - offset,
                       "%s\"%s\":{\"distance\":%.2f,\"raw\":%.2f}",
                       responded ? "," : "", kAnchorIds[i], result.distance_cm,
                       result.raw_cm);
    responded++;
  }
  offset += snprintf(payload + offset, sizeof(payload) - offset, "}}");

  // An empty anchors object is rejected by the adapter, so stay quiet rather
  // than sending a sweep nobody can use.
  if (responded > 0 && offset > 0 && offset < (int)sizeof(payload)) {
    udp.beginPacket(LAPTOP_IP, LAPTOP_PORT);
    udp.write((const uint8_t *)payload, offset);
    udp.endPacket();
  }

  static uint32_t last_log_ms = 0;
  if (millis() - last_log_ms > 1000) {
    Serial.printf("%d/%d anchors responded: %s\n", responded, ANCHOR_COUNT,
                  responded ? payload : "(silent)");
    last_log_ms = millis();
  }

  const uint32_t elapsed_ms = millis() - sweep_start_ms;
  if (elapsed_ms < SWEEP_PERIOD_MS) {
    delay(SWEEP_PERIOD_MS - elapsed_ms);
  }
}
