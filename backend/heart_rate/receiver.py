from __future__ import annotations

import asyncio
import os
import time
from contextlib import suppress
from dataclasses import dataclass

HEART_RATE_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class Measurement:
    bpm: int
    contact: bool | None


def parse_measurement(data: bytes | bytearray) -> Measurement:
    """Decode the SIG Heart Rate Measurement flags and 8/16-bit BPM field."""
    if not data:
        raise ValueError("empty heart-rate measurement")
    flags = data[0]
    width = 2 if flags & 1 else 1
    if len(data) < 1 + width:
        raise ValueError("truncated heart-rate measurement")
    bpm = int.from_bytes(data[1 : 1 + width], "little")
    contact = bool(flags & 2) if flags & 4 else None
    # Check optional fields too, so malformed packets never replace a valid reading.
    offset = 1 + width + (2 if flags & 8 else 0)
    if len(data) < offset or (flags & 16 and (len(data) - offset) % 2):
        raise ValueError("truncated optional heart-rate fields")
    return Measurement(bpm, contact)


class HeartRateReceiver:
    def __init__(self, device: str = "", wearer: str = "Wearer", stale_s: float = 5.0):
        self.device = device.strip()
        self.wearer = wearer
        self.stale_s = stale_s
        self.status = "disabled" if not self.device else "disconnected"
        self.error: str | None = None
        self.device_name: str | None = None
        self.measurement: Measurement | None = None
        self.timestamp_us: int | None = None
        self._received_at: float | None = None
        self._task: asyncio.Task | None = None

    @classmethod
    def from_env(cls) -> HeartRateReceiver:
        return cls(os.getenv("E014_HR_DEVICE", ""), os.getenv("E014_HR_WEARER", "Wearer"))

    async def start(self) -> None:
        if self.device and self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self.device:
            self.status = "disconnected"

    def receive(self, _characteristic: object, data: bytearray) -> None:
        try:
            measurement = parse_measurement(data)
        except ValueError:
            return
        self.measurement = measurement
        self.timestamp_us = time.time_ns() // 1_000
        self._received_at = time.monotonic()

    def snapshot(self) -> dict:
        age = None if self._received_at is None else time.monotonic() - self._received_at
        status = self.status
        if status == "connected":
            if self.measurement is not None and self.measurement.contact is False:
                status = "no_contact"
            elif age is None:
                status = "waiting"
            elif age > self.stale_s:
                status = "stale"
        live = status == "connected" and self.measurement is not None
        return {
            "source": "ble",
            "wearer": self.wearer,
            "device_name": self.device_name,
            "status": status,
            "bpm": self.measurement.bpm if live else None,
            "timestamp_us": self.timestamp_us,
            "age_s": age,
            "error": self.error,
        }

    async def _run(self) -> None:
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError:
            self.status = "error"
            self.error = 'Install Bluetooth support: python -m pip install -e ".[heart-rate]"'
            return
        while True:
            try:
                self.status = "scanning"
                self.error = None
                devices = await BleakScanner.discover(timeout=5.0)
                matches = [
                    d
                    for d in devices
                    if d.address.casefold() == self.device.casefold()
                    or (d.name or "").casefold() == self.device.casefold()
                ]
                if len(matches) != 1:
                    raise RuntimeError(
                        "Sensor not found; wear the strap and close other heart-rate apps."
                        if not matches
                        else "Multiple matching sensors; use the sensor identifier from the scan."
                    )
                self.device_name = matches[0].name
                self.status = "connecting"
                disconnected = asyncio.Event()
                async with BleakClient(
                    matches[0],
                    disconnected_callback=lambda _client, event=disconnected: event.set(),
                ) as client:
                    # Reconnection must not revive a reading from the previous session.
                    self.measurement = None
                    self._received_at = None
                    self.timestamp_us = None
                    await client.start_notify(HEART_RATE_MEASUREMENT, self.receive)
                    self.status = "connected"
                    await disconnected.wait()
                self.status = "disconnected"
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - isolate platform Bluetooth failures
                self.status = "error"
                self.error = str(exc)
            await asyncio.sleep(3.0)


async def scan() -> None:
    from bleak import BleakScanner

    print("Wear the strap. Scanning for 10 seconds...")
    for device in await BleakScanner.discover(timeout=10.0):
        print(f"{device.address}\t{device.name or '(unnamed)'}")


if __name__ == "__main__":
    asyncio.run(scan())
