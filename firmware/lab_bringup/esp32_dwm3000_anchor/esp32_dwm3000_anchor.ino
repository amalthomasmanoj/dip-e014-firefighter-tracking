// ESP32 + DWM3000 anchor: respond to ranging polls from the tag.
//
// Lab bring-up firmware. An anchor has NO Wi-Fi and sends nothing to the
// laptop. It exists only as a UWB responder. Its identity reaches the
// backend as a key inside the tag's sweep, so the only thing that must agree
// with the rest of the system is ANCHOR_SHORT_ADDR matching the tag's
// ANCHOR_ADDRS entry for the same label.
//
// On boot it prints its label over USB serial at 115200. That is how you
// tell which physical board is which without a working radio.

#include <SPI.h>

#include "config.h"
#include "dw3000.h"

// Same pin map as the tag. CONFIRM AGAINST YOUR BOARD.
static const uint8_t PIN_SCK = 18;
static const uint8_t PIN_MISO = 19;
static const uint8_t PIN_MOSI = 23;
static const uint8_t PIN_SS = 4;
static const uint8_t PIN_RST = 27;
static const uint8_t PIN_IRQ = 34;

static dwt_config_t dw_config = {
    5,                // channel 5 - must match the tag
    DWT_PLEN_128,
    DWT_PAC8,
    9,                // TX preamble code - must match the tag
    9,                // RX preamble code - must match the tag
    1,
    DWT_BR_6M8,       // data rate - must match the tag
    DWT_PHRMODE_STD,
    DWT_PHRRATE_STD,
    (129 + 8 - 8),
    DWT_STS_MODE_OFF,
    DWT_STS_LEN_64,
    DWT_PDOA_M0,
};

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("\nE014 DWM3000 anchor %s, short addr 0x%04X\n", ANCHOR_LABEL,
                ANCHOR_SHORT_ADDR);

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_SS);
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

  // An anchor listens indefinitely rather than timing out.
  dwt_setrxtimeout(0);
  Serial.printf("anchor %s ready, listening\n", ANCHOR_LABEL);
}

void loop() {
  // IMPLEMENT FROM YOUR LIBRARY'S SS-TWR or DS-TWR *responder* example
  // (Makerfabs/Qorvo: ss_twr_responder). The standard flow is:
  //
  //   1. dwt_rxenable(DWT_START_RX_IMMEDIATE)
  //   2. poll the status register until a frame arrives
  //   3. dwt_readrxdata(); ignore frames not addressed to ANCHOR_SHORT_ADDR
  //   4. read the poll RX timestamp, compute the scheduled response TX time
  //   5. dwt_writetxdata()/dwt_writetxfctrl() with the response, then
  //      dwt_starttx(DWT_START_TX_DELAYED)
  //   6. on any error: dwt_rxreset() and go back to step 1
  //
  // The responder must never initiate. Only the tag drives the schedule, so
  // two anchors can never collide on their own.

  static uint32_t last_log_ms = 0;
  if (millis() - last_log_ms > 5000) {
    Serial.printf("anchor %s alive\n", ANCHOR_LABEL);
    last_log_ms = millis();
  }
  delay(10);
}
