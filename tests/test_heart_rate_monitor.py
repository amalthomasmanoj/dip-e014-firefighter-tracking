import pytest
from pydantic import ValidationError

from backend.heart_rate.monitor import AlertSettings, HeartRateMonitor


@pytest.fixture
def setup_monitor():
    clock = [0.0]
    monitor = HeartRateMonitor(clock=lambda: clock[0])
    monitor.configure(AlertSettings(enabled=True, high_duration_s=3, low_duration_s=2))
    return monitor, clock


def sample(monitor, clock, second, bpm=170, contact=True):
    clock[0] = second
    monitor.observe(bpm, int(second * 1_000_000), contact)


def test_new_samples_required_and_hysteresis(setup_monitor):
    monitor, clock = setup_monitor
    sample(monitor, clock, 0)
    clock[0] = 3
    monitor.tick(available=True, configured=True)
    assert monitor.active is None  # repeated HTTP polls/ticks cannot confirm high HR
    assert monitor.snapshot()["pending"]["elapsed_s"] == 0
    sample(monitor, clock, 3)
    assert monitor.active["kind"] == "high"
    event_id = monitor.active["id"]
    assert monitor.acknowledge(event_id)
    sample(monitor, clock, 4, 158)  # below trigger, still inside recovery band
    assert monitor.active["id"] == event_id
    assert monitor.active["acknowledged"]
    sample(monitor, clock, 5, 155)
    assert monitor.active is None
    assert monitor.events[0]["end_reason"] == "reading_recovered"
    sample(monitor, clock, 6)
    sample(monitor, clock, 9)
    assert monitor.active["id"] != event_id
    assert not monitor.active["acknowledged"]


def test_low_persistence_resets_on_normal_sample(setup_monitor):
    monitor, clock = setup_monitor
    sample(monitor, clock, 0, 40)
    sample(monitor, clock, 1, 60)
    assert monitor.pending is None
    sample(monitor, clock, 2, 40)
    sample(monitor, clock, 3, 40)
    assert monitor.active is None
    sample(monitor, clock, 4, 40)
    assert monitor.active["kind"] == "low"
    sample(monitor, clock, 5, 53)
    assert monitor.active["kind"] == "low"
    sample(monitor, clock, 6, 55)
    assert monitor.active is None


def test_gap_contact_and_zero_are_not_cardiac_evidence(setup_monitor):
    monitor, clock = setup_monitor
    sample(monitor, clock, 0)
    sample(monitor, clock, 6)  # do not bridge an unobserved interval
    assert monitor.active is None
    assert monitor.pending["elapsed_s"] == 0
    sample(monitor, clock, 7, 40, contact=False)
    assert monitor.pending is None
    sample(monitor, clock, 8, 0)
    assert monitor.pending is None
    assert [p["bpm"] for p in monitor.snapshot()["history"]] == [170, 170]


def test_signal_loss_is_separate_and_valid_reading_recovers(setup_monitor):
    monitor, clock = setup_monitor
    sample(monitor, clock, 0)
    sample(monitor, clock, 3)
    assert monitor.active["kind"] == "high"
    clock[0] = 9
    monitor.tick(available=False, configured=True)
    assert monitor.events[1]["end_reason"] == "data_unavailable"
    assert monitor.active["kind"] == "signal_loss"
    assert monitor.active["bpm"] is None
    sample(monitor, clock, 10, 80)
    assert monitor.active is None
    assert monitor.events[0]["end_reason"] == "reading_recovered"


def test_startup_loss_requires_enabled_and_configured_sensor(setup_monitor):
    monitor, clock = setup_monitor
    clock[0] = 30
    monitor.tick(available=False, configured=False)
    assert monitor.active is None
    monitor.tick(available=False, configured=True)
    assert monitor.active["kind"] == "signal_loss"
    monitor.configure(AlertSettings(enabled=False))
    clock[0] = 60
    monitor.tick(available=False, configured=True)
    assert monitor.active is None


def test_settings_reset_pending_keep_event_history(setup_monitor):
    monitor, clock = setup_monitor
    sample(monitor, clock, 0)
    sample(monitor, clock, 3)
    monitor.configure(AlertSettings(enabled=False))
    assert monitor.active is None
    assert monitor.pending is None
    assert monitor.events[0]["end_reason"] == "settings_changed"
    assert monitor.snapshot()["settings"]["enabled"] is False
    assert not monitor.acknowledge(999)


def test_history_expires_by_time_and_has_hard_bound(setup_monitor):
    monitor, clock = setup_monitor
    sample(monitor, clock, 0, 80)
    sample(monitor, clock, 301, 85)
    assert len(monitor.snapshot()["history"]) == 1
    for i in range(4000):
        sample(monitor, clock, 302 + i * 0.001, 80)
    assert len(monitor.points) == 3600


@pytest.mark.parametrize(
    "settings",
    [
        {"low_bpm": 160},
        {"hysteresis_bpm": 60},
        {"high_duration_s": 0},
        {"signal_loss_s": 1},
        {"low_duration_s": float("nan")},
        {"high_bpm": 0},
    ],
)
def test_settings_validation(settings):
    with pytest.raises(ValidationError):
        AlertSettings(**settings)


def test_watchdog_monitors_without_browser_polling(monkeypatch):
    import asyncio

    from backend.heart_rate.receiver import HeartRateReceiver

    async def scenario():
        receiver = HeartRateReceiver("configured-test-sensor")
        clock = [0.0]
        receiver.monitor = HeartRateMonitor(clock=lambda: clock[0])
        receiver.monitor.configure(AlertSettings(enabled=True))
        receiver.status = "disconnected"
        blocked = asyncio.Event()

        async def fake_transport():
            await blocked.wait()

        monkeypatch.setattr(receiver, "_run", fake_transport)
        await receiver.start()
        try:
            clock[0] = 6
            # No HTTP request or monitor.snapshot call is needed to generate the event.
            await asyncio.sleep(0.6)
            assert receiver.monitor.active["kind"] == "signal_loss"
        finally:
            await receiver.stop()
        assert receiver._watchdog is None

    asyncio.run(scenario())
