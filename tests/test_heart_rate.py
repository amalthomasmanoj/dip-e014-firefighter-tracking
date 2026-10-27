import asyncio
import sys
from types import SimpleNamespace

import pytest

from backend.api.app import create_app
from backend.config.source import SourceMode
from backend.heart_rate import receiver as hr


@pytest.mark.parametrize(
    ("packet", "bpm", "contact"),
    [
        (b"\x00\x48", 72, None),
        (b"\x01\x2c\x01", 300, None),
        (b"\x06\x50", 80, True),
        (b"\x04\x50", 80, False),
        (b"\x18\x48\x00\x00\x00\x04", 72, None),
    ],
)
def test_decode(packet, bpm, contact):
    assert hr.parse_measurement(packet) == hr.Measurement(bpm, contact)


@pytest.mark.parametrize("packet", [b"", b"\x00", b"\x01\x48", b"\x08\x48", b"\x10\x48\x01"])
def test_truncated(packet):
    with pytest.raises(ValueError):
        hr.parse_measurement(packet)


def test_freshness_and_contact(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(hr.time, "monotonic", lambda: clock[0])
    receiver = hr.HeartRateReceiver("sensor", "Min")
    receiver.status = "connected"
    assert receiver.snapshot()["status"] == "waiting"
    receiver.receive(None, bytearray([6, 72]))
    receiver.receive(None, bytearray([1]))  # malformed packet cannot replace a reading
    assert receiver.snapshot()["bpm"] == 72
    clock[0] += 6
    assert receiver.snapshot()["status"] == "stale"
    assert receiver.snapshot()["bpm"] is None
    receiver.receive(None, bytearray([4, 72]))
    assert receiver.snapshot()["status"] == "no_contact"
    assert receiver.snapshot()["bpm"] is None
    receiver.receive(None, bytearray([6, 75]))
    assert receiver.snapshot()["bpm"] == 75
    receiver.status = "disconnected"
    assert receiver.snapshot()["bpm"] is None


def test_endpoint_independent_of_localization(monkeypatch):
    monkeypatch.delenv("E014_HR_DEVICE", raising=False)
    app = create_app(source_mode=SourceMode.REPLAY)
    route = next(r for r in app.routes if getattr(r, "path", None) == "/heart-rate")
    assert route.endpoint()["status"] == "disabled"
    assert route.endpoint()["bpm"] is None


def test_reconnect_and_shutdown(monkeypatch):
    async def scenario():
        notified = asyncio.Queue()
        sessions = []

        class Scanner:
            @staticmethod
            async def discover(**_kwargs):
                return [SimpleNamespace(address="sensor-id", name="H808S")]

        class Client:
            def __init__(self, device, disconnected_callback):
                assert device.address == "sensor-id"
                self.disconnected = disconnected_callback
                self.closed = False
                sessions.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                self.closed = True

            async def start_notify(self, uuid, callback):
                assert uuid == hr.HEART_RATE_MEASUREMENT
                self.notify = callback
                await notified.put(self)

        async def retry_immediately(_seconds):
            return

        monkeypatch.setitem(
            sys.modules, "bleak", SimpleNamespace(BleakScanner=Scanner, BleakClient=Client)
        )
        monkeypatch.setattr(hr.asyncio, "sleep", retry_immediately)
        receiver = hr.HeartRateReceiver("sensor-id")
        await receiver.start()
        try:
            first = await asyncio.wait_for(notified.get(), 1)
            first.notify(None, bytearray([0, 72]))
            assert receiver.snapshot()["bpm"] == 72
            first.disconnected(first)
            second = await asyncio.wait_for(notified.get(), 1)
            assert first.closed
            assert receiver.snapshot()["bpm"] is None
            second.notify(None, bytearray([0, 83]))
            assert receiver.snapshot()["bpm"] == 83
        finally:
            await receiver.stop()
        assert sessions[-1].closed
        assert receiver.snapshot()["bpm"] is None

    asyncio.run(scenario())


def test_ambiguous_sensor_never_connects(monkeypatch):
    async def scenario():
        scanned = asyncio.Event()
        block = asyncio.Event()

        class Scanner:
            @staticmethod
            async def discover(**_kwargs):
                return [SimpleNamespace(address=key, name="H808S") for key in ("a", "b")]

        async def pause(_seconds):
            scanned.set()
            await block.wait()

        monkeypatch.setitem(
            sys.modules,
            "bleak",
            SimpleNamespace(
                BleakScanner=Scanner, BleakClient=lambda *_a, **_k: pytest.fail("ambiguous sensor")
            ),
        )
        monkeypatch.setattr(hr.asyncio, "sleep", pause)
        receiver = hr.HeartRateReceiver("H808S")
        await receiver.start()
        try:
            await asyncio.wait_for(scanned.wait(), 1)
            assert "Multiple" in receiver.snapshot()["error"]
            assert receiver.snapshot()["bpm"] is None
        finally:
            await receiver.stop()

    asyncio.run(scenario())
