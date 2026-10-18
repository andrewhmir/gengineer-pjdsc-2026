"""The session state machine: one person, one session, one outcome, then idle again.

Every test here uses a fake clock and a scripted source, so a 33-second session runs in
milliseconds and the transition that is being tested is the only thing that happens.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from hinigram.station import NotInResult, SessionBusy, Station
from tests.helpers import FakeClock


def test_idle_before_start(station: Station) -> None:
    snapshot = station.snapshot()
    assert snapshot.state == "idle"
    assert snapshot.result is None
    assert snapshot.started_ms is None
    assert snapshot.elapsed_ms == 0


def test_start_settles_then_measures(station: Station, clock: FakeClock) -> None:
    station.start()
    assert station.snapshot().state == "settle"
    clock.advance(3_100)
    station.tick()
    assert station.snapshot().state == "measuring"


def test_nothing_is_measured_before_start(station: Station) -> None:
    station.tick()
    assert station.snapshot().result is None
    assert station.trace() is None


def test_stop_returns_to_idle_from_measuring(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(5_000)
    station.tick()
    station.stop()
    assert station.snapshot().state == "idle"
    assert station.snapshot().result is None


def test_a_result_arrives_after_the_capture_and_resets_itself(
    station: Station, clock: FakeClock
) -> None:
    station.start()
    clock.advance(33_500)
    station.tick()
    finished = station.snapshot()
    assert finished.state == "result"
    assert finished.result is not None
    assert finished.result.outcome == "regular"
    clock.advance(20_100)
    station.tick()
    assert station.snapshot().state == "idle"
    assert station.snapshot().result is None


def test_done_clears_the_result_immediately(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(33_500)
    station.tick()
    station.done()
    assert station.snapshot().state == "idle"
    assert station.snapshot().result is None


def test_a_second_start_while_busy_is_refused(station: Station) -> None:
    station.start()
    with pytest.raises(SessionBusy):
        station.start()


def test_done_outside_a_result_is_refused(station: Station) -> None:
    with pytest.raises(NotInResult):
        station.done()


def test_the_next_session_gets_a_new_id(station: Station, clock: FakeClock) -> None:
    station.start()
    first = station.snapshot().id
    clock.advance(33_500)
    station.tick()
    station.done()
    station.start()
    assert station.snapshot().id != first


def test_the_next_session_cannot_see_the_previous_frames(
    station: Station, clock: FakeClock
) -> None:
    station.start()
    clock.advance(33_500)
    station.tick()
    station.done()
    assert station.store.window(0, clock.now()) == {}


def test_settle_without_respiration_returns_to_idle(
    empty_station: Station, clock: FakeClock
) -> None:
    empty_station.start()
    assert empty_station.snapshot().state == "settle"
    clock.advance(3_200)
    empty_station.tick()
    assert empty_station.snapshot().state == "idle"
    assert empty_station.snapshot().result is None


def test_motion_during_the_capture_is_unclear(
    make_station: Callable[..., Station], clock: FakeClock
) -> None:
    moving = make_station(scenario="motion")
    moving.start()
    clock.advance(33_500)
    moving.tick()
    result = moving.snapshot().result
    assert result is not None
    assert result.outcome == "unclear"
    assert result.rule == "low_quality"


def test_the_countdown_is_reported_from_the_start(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(10_000)
    snapshot = station.snapshot()
    assert snapshot.elapsed_ms == pytest.approx(10_000, abs=50)
    assert snapshot.duration_ms == 33_000


def test_live_metrics_appear_while_measuring(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(12_000)
    station.tick()
    live = station.snapshot().live
    assert live is not None
    assert live.rr_bpm is not None
    assert 10.0 < live.rr_bpm < 20.0


def test_the_trace_is_available_only_after_a_result(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(12_000)
    station.tick()
    assert station.trace() is None
    clock.advance(21_500)
    station.tick()
    trace = station.trace()
    assert trace is not None
    assert trace.tx_used == "tx1"
    assert len(trace.t) == len(trace.amp) == len(trace.phi_breath)
    assert 290 <= len(trace.t) <= 310


def test_health_reports_a_live_source(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(2_000)
    health = station.health()
    assert health.ok is True
    assert health.source == "sim"
    assert health.last_frame_age_ms is not None


def test_health_before_any_frame_is_not_ok(station: Station) -> None:
    health = station.health()
    assert health.ok is False


def test_the_stage_label_and_chip_follow_the_state(station: Station, clock: FakeClock) -> None:
    assert station.snapshot().stage_label == "No one detected"
    station.start()
    clock.advance(5_000)
    station.tick()
    measuring = station.snapshot()
    assert measuring.stage_label == "Measuring · stand still"
    assert measuring.chip is not None


def test_a_capture_that_lost_its_frames_is_unclear(
    make_station: Callable[..., Station], clock: FakeClock
) -> None:
    """If the source went quiet two thirds of the way through, the rate is not trustworthy."""
    truncated = make_station(scenario="regular", seconds=20.0)
    truncated.start()
    clock.advance(33_500)
    truncated.tick()
    result = truncated.snapshot().result
    assert result is not None
    assert result.outcome == "unclear"
    assert result.rule == "low_quality"


def test_a_dropout_inside_the_capture_is_unclear(
    make_station: Callable[..., Station], clock: FakeClock
) -> None:
    """A hole in the middle is the failure an ESP-NOW link will actually produce."""
    holed = make_station(scenario="regular", hole=(10.0, 20.0))
    holed.start()
    clock.advance(33_500)
    holed.tick()
    result = holed.snapshot().result
    assert result is not None
    assert result.outcome == "unclear"
    assert result.rule == "low_quality"


def test_a_short_dropout_does_not_corrupt_the_result(
    make_station: Callable[..., Station], clock: FakeClock
) -> None:
    """A fifth of a second is a dropped packet, not a lost measurement."""
    almost = make_station(scenario="regular", hole=(12.0, 12.2))
    almost.start()
    clock.advance(33_500)
    almost.tick()
    result = almost.snapshot().result
    assert result is not None
    assert result.outcome == "regular"


def test_a_delay_after_the_capture_is_not_missing_data(station: Station, clock: FakeClock) -> None:
    """A laptop that slept *after* the capture still has a complete window to measure."""
    station.start()
    clock.advance(600_000)
    station.tick()
    result = station.snapshot().result
    assert result is not None
    assert result.outcome == "regular"


def test_evaluation_is_under_four_hundred_milliseconds(station: Station, clock: FakeClock) -> None:
    station.start()
    clock.advance(33_500)
    started = time.perf_counter()
    station.tick()
    assert time.perf_counter() - started < 0.4
