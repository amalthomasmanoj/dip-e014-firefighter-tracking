// Copy to config.h and fill in, once per anchor board. config.h is
// gitignored.
#pragma once

// This anchor's UWB short address. MUST match the entry for this anchor in
// the tag's ANCHOR_ADDRS list. Flash each board with a different value:
//   A1 -> 0x0001, A2 -> 0x0002, A3 -> 0x0003, A4 -> 0x0004
#define ANCHOR_SHORT_ADDR 0x0001

// Human label, printed on boot so a board can be identified over USB serial
// without a UWB network. Write the same label on the physical board.
#define ANCHOR_LABEL "A1"

// Antenna delay calibration for this specific board. Anchors and tags each
// need their own calibrated value; the default is a starting point only.
#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385
