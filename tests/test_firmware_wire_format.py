"""Pin the exact sweep bytes the ESP32 tag firmware emits.

`firmware/lab_bringup/esp32_dwm3000_tag` builds its payload with snprintf
format strings. These tests reproduce that formatting in Python and push the
result through the real adapter parser, so a change on either side that
breaks the other fails here instead of silently on the bench.
"""

from __future__ import annotations

import pytest

from tools.uwb.dwm3000_udp_adapter import (
    Dwm3000SweepError,
    generic_packets_from_sweep,
    parse_dwm3000_sweep,
)


def firmware_sweep_bytes(
    timestamp_ms: int,
    tag_id: int,
    anchors: list[tuple[str, float, float, float, float]],
) -> bytes:
    """Reproduce the firmware's snprintf output byte for byte."""
    head = f'{{"t":{timestamp_ms},"tag_id":{tag_id},"anchors":{{'
    body = ",".join(
        f'"{anchor_id}":{{"distance":{distance_cm:.2f},"raw":{raw_cm:.2f},'
        f'"rssi":{rssi:.2f},"fp_rssi":{fp_rssi:.2f}}}'
        for anchor_id, distance_cm, raw_cm, rssi, fp_rssi in anchors
    )
    return (head + body + "}}").encode("utf-8")


def test_full_firmware_sweep_parses_and_converts() -> None:
    payload = firmware_sweep_bytes(
        12345,
        10,
        [
            ("A1", 150.23, 151.07, -80.12, -82.34),
            ("A2", 210.55, 211.01, -81.00, -83.20),
            ("A3", 305.90, 306.44, -84.50, -86.10),
            ("A4", 412.08, 412.63, -86.75, -88.90),
        ],
    )

    sweep = parse_dwm3000_sweep(payload)
    packets = generic_packets_from_sweep(sweep, start_sequence_number=0)

    assert sweep.tag_id == 10
    assert [sample.anchor_id for sample in sweep.anchors] == ["A1", "A2", "A3", "A4"]
    assert [packet["data"]["range_m"] for packet in packets] == [
        pytest.approx(1.5023),
        pytest.approx(2.1055),
        pytest.approx(3.0590),
        pytest.approx(4.1208),
    ]
    assert {packet["node_id"] for packet in packets} == {"dwm3000_tag_10"}


def test_firmware_skips_silent_anchors_without_padding() -> None:
    """A dropped anchor is absent, never zero-filled or stale."""
    payload = firmware_sweep_bytes(
        900,
        10,
        [("A1", 150.00, 150.00, -80.00, -82.00), ("A4", 412.08, 412.63, -86.75, -88.90)],
    )

    sweep = parse_dwm3000_sweep(payload)

    assert [sample.anchor_id for sample in sweep.anchors] == ["A1", "A4"]


def test_single_anchor_sweep_is_still_valid_transport() -> None:
    payload = firmware_sweep_bytes(1, 10, [("A1", 150.00, 150.00, -80.00, -82.00)])

    assert len(parse_dwm3000_sweep(payload).anchors) == 1


def test_sweep_with_no_responding_anchors_is_rejected() -> None:
    """Why the firmware stays silent instead of sending an empty sweep."""
    payload = firmware_sweep_bytes(1, 10, [])

    with pytest.raises(Dwm3000SweepError):
        parse_dwm3000_sweep(payload)


@pytest.mark.parametrize(
    "anchor_id",
    ["a1", "ANCHOR1", "A", "1A", "anchor_1"],
)
def test_anchor_ids_outside_the_pattern_are_rejected(anchor_id: str) -> None:
    """The firmware's ANCHOR_IDS entries must be A<digits>, uppercase."""
    payload = firmware_sweep_bytes(1, 10, [(anchor_id, 150.0, 150.0, -80.0, -82.0)])

    with pytest.raises(Dwm3000SweepError):
        parse_dwm3000_sweep(payload)


def test_diagnostics_fields_are_mandatory() -> None:
    """Dropping rssi/fp_rssi from the firmware breaks the whole sweep."""
    payload = (
        b'{"t":1,"tag_id":10,"anchors":{"A1":{"distance":150.00,"raw":150.00}}}'
    )

    with pytest.raises(Dwm3000SweepError):
        parse_dwm3000_sweep(payload)


def test_centimetre_to_metre_conversion_is_the_adapter_s_job() -> None:
    """The firmware sends centimetres; nothing on the device converts."""
    payload = firmware_sweep_bytes(1, 10, [("A1", 100.00, 100.00, -80.0, -82.0)])

    packets = generic_packets_from_sweep(parse_dwm3000_sweep(payload), 0)

    assert packets[0]["data"]["range_m"] == pytest.approx(1.0)
