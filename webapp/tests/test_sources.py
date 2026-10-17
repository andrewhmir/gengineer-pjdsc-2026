"""The simulator, the replay source, and the scenario script.

The scenario table is the demonstration: each entry must reach exactly one outcome, and the test
that checks it prints the measured numbers when it fails, so tuning is done against evidence
rather than by guessing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from hinigram.config import Settings
from hinigram.pipeline.analyze import Analysis, analyze_window
from hinigram.pipeline.frames import FrameStore
from hinigram.pipeline.rules import decide
from hinigram.sources import (
    ReplaySource,
    Scenario,
    SerialSource,
    SimulatorSource,
    build_source,
    load_scenarios,
    simulate_frames,
)


def test_the_scenario_set_covers_every_outcome() -> None:
    scenarios = load_scenarios()
    assert {"regular", "watch", "tachypnea", "unsteady", "apnea", "motion", "absent"} <= set(
        scenarios
    )
    assert all(scenario.label for scenario in scenarios.values())


def test_frames_are_deterministic_for_a_seed() -> None:
    scenario = load_scenarios()["regular"]
    first = simulate_frames(scenario, start_ms=0, n=3301)
    second = simulate_frames(scenario, start_ms=0, n=3301)
    assert [frame.phase for frame in first] == [frame.phase for frame in second]
    assert simulate_frames(scenario, start_ms=0, n=3301, seed=7)[900].phase != first[900].phase


def test_frames_cover_three_transmitters_and_three_subcarriers() -> None:
    frames = simulate_frames(load_scenarios()["regular"], start_ms=0, n=330)
    assert {"tx1", "tx2", "tx3"} == {frame.tx for frame in frames}
    assert {len(frame.phase) for frame in frames} == {3}
    assert [frame.t for frame in frames if frame.tx == "tx1"][:3] == [0, 10, 20]


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
    for frame in simulate_frames(scenario, 0, 3301):
        store.push(frame)
    windows = store.window(3000.0, 33000.0)
    assert analyze_window(windows, Settings().thresholds()) is None


def test_the_apnea_scenario_stalls_the_breath_phase(
    analyse_scenario: Callable[..., Analysis],
) -> None:
    analysis = analyse_scenario("apnea")
    assert analysis.flat_s >= 10.0


def test_build_source_selects_the_named_source() -> None:
    assert isinstance(build_source(Settings(source="sim")), SimulatorSource)
    replay = build_source(Settings(source="replay", replay_file=Path("fixtures/x.jsonl.gz")))
    assert isinstance(replay, ReplaySource)
    serial = build_source(Settings(source="serial", serial_port="COM9"))
    assert isinstance(serial, SerialSource)


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
