"""The simulator, the replay source, and the scenario script.

The scenario table is the demonstration: each entry must reach exactly one outcome, and the test
that checks it prints the measured numbers when it fails, so tuning is done against evidence
rather than by guessing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest

from hinigram import sources
from hinigram.clock import monotonic_ms
from hinigram.config import PACKAGE_DIR, Settings
from hinigram.contracts import Frame
from hinigram.pipeline.analyze import Analysis, analyze_window
from hinigram.pipeline.frames import FrameStore
from hinigram.pipeline.rules import decide
from hinigram.sources import (
    ReplaySource,
    Scenario,
    SerialSource,
    SimulatorSource,
    build_source,
    iter_replay_fixture,
    load_scenarios,
    simulate_frames,
)
from tests.helpers import FakeClock

#: The committed synthetic session, kept next to `scenarios.json` inside the package.
REPLAY_FIXTURE = PACKAGE_DIR / "fixtures" / "replay_session.jsonl.gz"


def test_the_scenario_set_covers_every_outcome() -> None:
    scenarios = load_scenarios()
    assert {"regular", "watch", "tachypnea", "unsteady", "apnea", "motion", "absent"} <= set(
        scenarios
    )
    assert all(scenario.label for scenario in scenarios.values())


def test_frames_are_deterministic_for_a_seed() -> None:
    scenario = load_scenarios()["regular"]
    first = simulate_frames(scenario, start_ms=0, n=501)
    second = simulate_frames(scenario, start_ms=0, n=501)
    assert [frame.phase for frame in first] == [frame.phase for frame in second]
    assert simulate_frames(scenario, start_ms=0, n=501, seed=7)[90].phase != first[90].phase


def test_frames_cover_three_transmitters_and_three_subcarriers() -> None:
    frames = simulate_frames(load_scenarios()["regular"], start_ms=0, n=330)
    assert {"tx1", "tx2", "tx3"} == {frame.tx for frame in frames}
    assert {len(frame.phase) for frame in frames} == {3}
    assert [frame.t for frame in frames if frame.tx == "tx1"][:3] == [0, 10, 20]


def test_a_generated_frame_validates() -> None:
    """``simulate_frames`` skips validation for speed; the contract must still accept its output."""
    frame = simulate_frames(load_scenarios()["regular"], start_ms=0, n=2)[0]
    assert Frame.model_validate(frame.model_dump()) == frame


def test_the_receiver_is_quieter_than_the_nearest_transmitter() -> None:
    """The three nodes differ in signal strength, which is what best-transmitter selection reads."""
    frames = simulate_frames(load_scenarios()["regular"], start_ms=0, n=200)
    first_phase = {}
    for frame in frames[:3]:
        first_phase[frame.tx] = max(abs(value) for value in frame.phase)
    assert first_phase["tx1"] > first_phase["tx3"]


@pytest.mark.parametrize(
    "name,outcome,rule",
    [
        ("regular", "regular", "none"),
        ("watch", "regular", "none"),
        ("tachypnea", "irregular", "tachypnea"),
        ("unsteady", "irregular", "unsteady"),
        ("apnea", "irregular", "apnea"),
        ("motion", "unclear", "low_quality"),
    ],
)
def test_each_scenario_reaches_its_outcome(
    analyse_scenario: Callable[..., Analysis],
    name: str,
    outcome: str,
    rule: str,
) -> None:
    analysis = analyse_scenario(name)
    result = decide(analysis, Settings().thresholds())
    assert (result.outcome, result.rule) == (outcome, rule), (
        f"{name}: rr={analysis.rr_bpm:.1f} plv={analysis.plv:.3f} "
        f"motion={analysis.motion_s:.1f} flat={analysis.flat_s:.1f} "
        f"breaths={analysis.breaths} amp={analysis.amp_db:.1f}"
    )


@pytest.mark.parametrize(
    "name,bpm",
    [("regular", 15.0), ("watch", 22.0), ("tachypnea", 28.0), ("unsteady", 22.0)],
)
def test_the_measured_rate_is_close_to_the_scripted_rate(
    analyse_scenario: Callable[..., Analysis], name: str, bpm: float
) -> None:
    rr = analyse_scenario(name).rr_bpm
    assert rr is not None
    assert abs(rr - bpm) <= 2.0, f"{name}: measured {rr:.1f} against scripted {bpm:.1f}"


def test_an_empty_zone_is_not_a_measurement() -> None:
    """No respiratory modulation means no reading at all — not a regular one (REQ-122)."""
    scenario = load_scenarios()["absent"]
    store = FrameStore()
    store.push_many(simulate_frames(scenario, 0, 3301))
    windows = store.window(3000.0, 33000.0)
    assert analyze_window(windows, Settings().thresholds()) is None


def test_the_apnea_scenario_stalls_the_breath_phase(
    analyse_scenario: Callable[..., Analysis],
) -> None:
    analysis = analyse_scenario("apnea")
    assert analysis.flat_s >= 10.0


def test_the_simulator_keeps_streaming_after_its_buffer_is_spent() -> None:
    """Regression: an idle station reported a dead source once the first buffer ran out."""
    original = sources.IDLE_BUFFER_S
    sources.IDLE_BUFFER_S = 0.3
    source = SimulatorSource(load_scenarios()["regular"])
    store = FrameStore()
    source.start(store)
    try:
        source.on_session_start(monotonic_ms())
        deadline = time.time() + 3.0
        while time.time() < deadline:
            last = store.counters().last_t
            if last is not None and monotonic_ms() - last < 200:
                break
            time.sleep(0.05)
        # Wait past the buffer horizon and confirm frames are still arriving.
        time.sleep(0.6)
    finally:
        source.stop()
        sources.IDLE_BUFFER_S = original
    last = store.counters().last_t
    assert last is not None
    assert monotonic_ms() - last < 2_000


def test_build_source_selects_the_named_source() -> None:
    assert isinstance(build_source(Settings(source="sim")), SimulatorSource)
    replay = build_source(Settings(source="replay", replay_file=Path("fixtures/x.jsonl.gz")))
    assert isinstance(replay, ReplaySource)
    serial = build_source(Settings(source="serial", serial_port="COM9"))
    assert isinstance(serial, SerialSource)


def test_every_source_shares_the_stations_clock() -> None:
    """A source on wall-clock time and a station on monotonic time never agree on a window."""
    marker = FakeClock()
    now = marker.now
    for source in (
        build_source(Settings(source="sim"), clock=now),
        build_source(Settings(source="replay"), clock=now),
    ):
        assert source.clock is now


def test_the_running_simulator_stamps_frames_in_the_station_clock() -> None:
    """Regression: the simulator once stamped frames with epoch time, so settle saw nothing."""
    source = SimulatorSource(load_scenarios()["regular"])
    store = FrameStore()
    source.start(store)
    start_ms = monotonic_ms()
    try:
        source.on_session_start(start_ms)
        deadline = time.time() + 2.0
        while store.counters().frames == 0 and time.time() < deadline:
            time.sleep(0.02)
    finally:
        source.stop()
    counters = store.counters()
    assert counters.frames > 0
    assert counters.last_t is not None
    assert abs(counters.last_t - monotonic_ms()) < 60_000


def test_build_source_refuses_an_unknown_scenario() -> None:
    with pytest.raises(ValueError, match="unknown scenario"):
        build_source(Settings(source="sim", scenario="not-a-scenario"))


def test_build_source_refuses_serial_without_a_port() -> None:
    with pytest.raises(ValueError, match="serial-port"):
        build_source(Settings(source="serial", serial_port=None))


def test_a_scenario_defaults_are_the_documented_ones() -> None:
    scenario = Scenario(rr_bpm=15.0)
    assert scenario.cv == 0.0
    assert scenario.gains == (0.35, 0.18, 0.08)
    assert scenario.apnea is None and scenario.motion is None


# --- the committed replay fixture -------------------------------------------------------


@cache
def replay_frames() -> tuple[Frame, ...]:
    """Parse the committed fixture once; three tests read it and it is nearly ten thousand lines."""
    return tuple(iter_replay_fixture())


def test_the_replay_fixture_is_a_full_session() -> None:
    frames = replay_frames()
    assert len(frames) > 9000
    assert {"tx1", "tx2", "tx3"} == {frame.tx for frame in frames}
    assert all(later.t >= earlier.t for earlier, later in zip(frames, frames[1:], strict=False))


def test_the_replay_fixture_is_small_enough_to_commit() -> None:
    """A fixture over the repository's 1 MB ceiling would fail the root suite."""
    assert REPLAY_FIXTURE.stat().st_size < 1_000_000


def test_the_replay_fixture_reaches_a_regular_result() -> None:
    store = FrameStore()
    store.push_many(list(replay_frames()))
    thresholds = Settings().thresholds()
    analysis = analyze_window(store.window(3000.0, 33000.0), thresholds)
    assert analysis is not None
    assert decide(analysis, thresholds).outcome == "regular"


def test_the_replay_source_restarts_at_each_session() -> None:
    source = ReplaySource(path=REPLAY_FIXTURE)
    source.start(FrameStore())
    try:
        source.on_session_start(4_000)
    finally:
        source.stop()
    assert source.position == 0


# --- the serial source ------------------------------------------------------------------


class FakeStream:
    """Minimal stand-in for ``serial.Serial``: one buffered line per ``readline``."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    def readline(self) -> bytes:
        return self._lines.pop(0) if self._lines else b""


def test_the_serial_parser_keeps_good_frames_and_counts_bad_ones() -> None:
    good = (
        '{"v": 1, "t": 10, "tx": "tx1", "ch": 3, "seq": 0, "rssi": -40, '
        '"amp": [1, 2, 3], "phase": [0, 0, 0]}'
    )
    store = FrameStore()
    source = SerialSource(
        port="FAKE",
        stream=FakeStream([good.encode() + b"\n", b'{"t": 11, "tx": "tx1"}\n', b"garbage\n"]),
    )
    frames = source.read_frames(store=store)
    assert len(frames) == 1
    assert store.counters().malformed == 2


def test_the_serial_source_does_not_invent_frames_without_a_stream() -> None:
    assert SerialSource(port="FAKE").read_frames() == []
