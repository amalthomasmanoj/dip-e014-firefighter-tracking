"""Prototype threshold monitoring. No consciousness or diagnosis inference."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AlertSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    enabled: bool = False
    low_bpm: int = Field(default=50, ge=1, le=299)
    high_bpm: int = Field(default=160, ge=2, le=300)
    low_duration_s: float = Field(default=30, ge=1, le=600)
    high_duration_s: float = Field(default=30, ge=1, le=600)
    hysteresis_bpm: int = Field(default=5, ge=0, le=50)
    signal_loss_s: float = Field(default=5, ge=5, le=120)

    @model_validator(mode="after")
    def valid_band(self):
        if self.low_bpm + 2 * self.hysteresis_bpm >= self.high_bpm:
            raise ValueError("Low and high limits must leave room for hysteresis")
        return self


class HeartRateMonitor:
    def __init__(self, clock: Callable[[], float] | None = None):
        self.clock = clock or time.monotonic
        self.settings = AlertSettings()
        self.points: deque[dict] = deque(maxlen=3600)
        self.events: deque[dict] = deque(maxlen=100)
        self.pending: dict | None = None
        self.active: dict | None = None
        self._last_sample: float | None = None
        self._unavailable_since: float | None = None
        self._next_id = 1

    def configure(self, settings: AlertSettings) -> None:
        self._end("settings_changed")
        self.settings = settings
        self.pending = None
        self._unavailable_since = self.clock()

    def _start(self, kind: str, bpm: int | None, duration: float) -> None:
        event = {
            "id": self._next_id,
            "kind": kind,
            "bpm": bpm,
            "started_us": time.time_ns() // 1000,
            "duration_s": duration,
            "acknowledged": False,
            "ended_us": None,
            "end_reason": None,
        }
        self._next_id += 1
        self.events.appendleft(event)
        self.active = event

    def _end(self, reason: str) -> None:
        if self.active is not None:
            self.active["ended_us"] = time.time_ns() // 1000
            self.active["end_reason"] = reason
            self.active = None

    def acknowledge(self, event_id: int) -> bool:
        for event in self.events:
            if event["id"] == event_id:
                event["acknowledged"] = True
                return True
        return False

    def observe(self, bpm: int, timestamp_us: int, contact: bool | None) -> None:
        now = self.clock()
        # Zero/poor-contact readings are not valid evidence of cardiac status.
        if contact is False or bpm <= 0:
            self.unavailable()
            return
        gap = self._last_sample is not None and now - self._last_sample > 5
        self.points.append({"timestamp_us": timestamp_us, "bpm": bpm, "received_s": now})
        self._last_sample = now
        self._unavailable_since = None
        if not self.settings.enabled:
            return
        if gap:
            self.pending = None
            self._end("data_unavailable")
        if self.active is not None:
            kind = self.active["kind"]
            recovered = (
                kind == "signal_loss"
                or kind == "high"
                and bpm <= self.settings.high_bpm - self.settings.hysteresis_bpm
                or kind == "low"
                and bpm >= self.settings.low_bpm + self.settings.hysteresis_bpm
            )
            if recovered:
                self._end("reading_recovered")
            else:
                return
        kind = (
            "high"
            if bpm > self.settings.high_bpm
            else ("low" if bpm < self.settings.low_bpm else None)
        )
        if kind is None:
            self.pending = None
            return
        if self.pending is None or self.pending["kind"] != kind:
            self.pending = {"kind": kind, "since_s": now, "elapsed_s": 0.0}
        elapsed = now - self.pending["since_s"]
        self.pending["elapsed_s"] = elapsed
        required = self.settings.high_duration_s if kind == "high" else self.settings.low_duration_s
        # Only a NEW valid notification can satisfy a persistence threshold.
        if elapsed >= required:
            self._start(kind, bpm, elapsed)
            self.pending = None

    def unavailable(self) -> None:
        self.pending = None
        if self._unavailable_since is None:
            self._unavailable_since = (
                self._last_sample if self._last_sample is not None else self.clock()
            )
        self._last_sample = None
        if self.active is not None and self.active["kind"] != "signal_loss":
            self._end("data_unavailable")

    def tick(self, available: bool, configured: bool) -> None:
        if not available:
            self.unavailable()
        if not self.settings.enabled or not configured:
            return
        if self._unavailable_since is not None:
            duration = self.clock() - self._unavailable_since
            if duration >= self.settings.signal_loss_s and self.active is None:
                self._start("signal_loss", None, duration)

    def snapshot(self) -> dict:
        now = self.clock()
        return {
            "settings": self.settings.model_dump(),
            "pending": None
            if self.pending is None
            else {"kind": self.pending["kind"], "elapsed_s": self.pending["elapsed_s"]},
            "active": None if self.active is None else dict(self.active),
            "events": [dict(event) for event in self.events],
            "history": [
                {"timestamp_us": p["timestamp_us"], "bpm": p["bpm"]}
                for p in self.points
                if now - p["received_s"] <= 300
            ],
        }
