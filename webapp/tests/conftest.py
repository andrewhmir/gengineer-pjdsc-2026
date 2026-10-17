"""Shared fixtures for the lane suite.

Clocks and frame sources are always injected: the suite must be deterministic and finish in
seconds, so no test waits on wall-clock time or on a background thread for real frames.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import cache
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from hinigram.app import create_app
from hinigram.config import Settings
from hinigram.contracts import Frame, Thresholds
from hinigram.pipeline.analyze import Analysis, analyze_window
from hinigram.pipeline.frames import FrameStore, Window
from hinigram.sources import load_scenarios, simulate_frames
from hinigram.station import Station
from tests.helpers import FakeClock

#: Sample rate every synthetic signal in the suite is generated at.
FS = 100.0


@cache
def cached_frames(scenario_name: str, at_ms: int, n: int) -> tuple[Frame, ...]:
    """A scripted session, generated once and reused.

    The generator is deterministic, so caching it changes no test's meaning and keeps the lane
    suite inside its fifteen-second budget: a station fixture needs a whole session, and every
    test that builds one would otherwise regenerate ten thousand frames.

    The cache is cleared between runs by process exit; a stale entry cannot exist because the
    key carries the scenario name, the session start, and the frame count.
    """
    scenario = load_scenarios()[scenario_name]
    return tuple(simulate_frames(scenario, at_ms, n))


def respiration(
    bpm: float,
    seconds: float,
    *,
    fs: float = FS,
    noise: float = 0.0,
    cv: float = 0.0,
    seed: int = 0,
) -> np.ndarray:
    """A respiratory waveform at ``bpm`` breaths per minute.

    ``cv`` is the coefficient of variation of the breath-to-breath interval: 0 is metronomic,
    0.4 is a rhythm whose next breath is a coin toss between half and double the last one. This
    is the variability a distressed or unsteady rhythm shows, and it is what the phase-locking
    statistic actually measures — a smooth frequency wobble changes the rate without ever
    letting the phase slip, so it cannot move the statistic at all.
    """
    rng = np.random.default_rng(seed)
    n = int(round(seconds * fs))
    t = np.arange(n) / fs
    mean_interval = 60.0 / bpm
    onsets = [0.0]
    while onsets[-1] < seconds:
        interval = mean_interval
        if cv:
            interval *= float(np.exp(rng.normal(0.0, cv) - 0.5 * cv * cv))
        onsets.append(onsets[-1] + interval)
    cycles = np.interp(t, np.array(onsets), np.arange(len(onsets)))
    signal = np.sin(2 * np.pi * cycles)
    if noise:
        signal = signal + rng.normal(0.0, noise, n)
    return signal


@pytest.fixture
def settings_factory(tmp_path: Path) -> Callable[..., Settings]:
    """Build a ``Settings`` whose file paths stay inside the test's temp directory."""

    def factory(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "source": "sim",
            "replay_file": tmp_path / "replay_session.jsonl.gz",
        }
        values.update(overrides)
        return Settings(**values)  # type: ignore[arg-type]

    return factory


@pytest.fixture
def client(station: Station) -> Iterator[TestClient]:
    """An HTTP client over the real app, wired to the scripted station and the fake clock."""
    with TestClient(
        create_app(station.settings, station=station, clock=station.clock)
    ) as test_client:
        yield test_client


@pytest.fixture
def synth() -> Callable[..., np.ndarray]:
    """The respiration generator, exposed as a fixture so tests read as data, not as maths."""

    def factory(bpm: float, seconds: float, **kwargs: object) -> np.ndarray:
        return respiration(bpm, seconds, **kwargs)  # type: ignore[arg-type]

    return factory


@pytest.fixture
def default_thresholds() -> Thresholds:
    """The documented prototype thresholds, in the shape the rules consume."""
    return Settings().thresholds()


@pytest.fixture
def analysis() -> Callable[..., Analysis]:
    """An ``Analysis`` with plausible defaults; tests override only the field under test."""

    def factory(**overrides: object) -> Analysis:
        values: dict[str, object] = {
            "tx_used": "tx1",
            "rr_bpm": 15.0,
            "plv": 0.9,
            "breaths": 7,
            "motion_s": 0.0,
            "flat_s": 0.0,
            "amp_db": -20.0,
            "usable_s": 30.0,
            "banded": np.zeros(8, dtype=np.float64),
            "t": np.arange(8, dtype=np.float64),
            "phi_breath": np.zeros(8, dtype=np.float64),
            "phi_osc": np.zeros(8, dtype=np.float64),
            "locked": True,
            "winding": 1.0,
        }
        values.update(overrides)
        return Analysis(**values)  # type: ignore[arg-type]

    return factory


@pytest.fixture
def fake_series() -> Callable[..., np.ndarray]:
    """One transmitter's phase series, optionally with a suppressed stretch (a breath pause)."""

    def factory(
        gain: float = 0.35,
        *,
        seconds: float = 30.0,
        flat: tuple[float, float] | None = None,
        noise: float = 0.02,
        seed: int = 0,
    ) -> np.ndarray:
        rng = np.random.default_rng(seed)
        n = int(round(seconds * FS))
        signal = gain * respiration(15.0, seconds, noise=0.0, seed=seed)
        signal = signal + rng.normal(0.0, noise, n)
        if flat is not None:
            start = int(flat[0] * FS)
            stop = int(flat[1] * FS)
            signal[start:stop] = noise * rng.normal(0.0, 1.0, stop - start)
        return signal

    return factory


@pytest.fixture
def fake_window() -> Callable[..., Window]:
    """A three-subcarrier window, optionally with a movement burst inside it."""

    def factory(
        gain: float = 0.35,
        *,
        seconds: float = 30.0,
        burst: tuple[float, float] | None = None,
        flat: tuple[float, float] | None = None,
        noise: float = 0.02,
        seed: int = 0,
    ) -> Window:
        n = int(round(seconds * FS))
        t = np.arange(n) / FS
        phase = np.zeros((n, 3))
        for channel in range(3):
            # Noise is added after the gain, so a weaker transmitter is a noisier one — that is
            # the whole point of choosing a transmitter by in-band SNR.
            rng = np.random.default_rng(seed + channel)
            phase[:, channel] = gain * respiration(15.0, seconds, noise=0.0, seed=seed + channel)
            phase[:, channel] += rng.normal(0.0, noise, n)
            if flat is not None:
                start = int(flat[0] * FS)
                stop = int(flat[1] * FS)
                phase[start:stop, channel] = rng.normal(0.0, noise, stop - start)
        if burst is not None:
            start = int(burst[0] * FS)
            stop = int(burst[1] * FS)
            phase[start:stop] += 0.6 * np.sin(2 * np.pi * 6.0 * t[start:stop])[:, None]
        amp = np.full((n, 3), -20.0)
        return Window(t=t * 1000.0, phase=phase, amp=amp, fs=FS)

    return factory


@pytest.fixture
def analyse_scenario() -> Callable[[str], Analysis]:
    """Run one scripted scenario through the real pipeline and return its analysis.

    The window is exactly the capture window of a real session — settle is 3 s, capture 30 s —
    so a scenario's outcome here is the outcome the station would show.
    """

    def factory(name: str, settle_s: float = 3.0, capture_s: float = 30.0) -> Analysis:
        store = FrameStore()
        total_ms = int((settle_s + capture_s) * FS) + 1
        store.push_many(list(cached_frames(name, 0, total_ms)))
        windows = store.window(settle_s * 1000.0, (settle_s + capture_s) * 1000.0)
        result = analyze_window(windows, Settings().thresholds())
        assert result is not None, f"scenario {name!r} produced no usable analysis"
        return result

    return factory


class ScriptedSource:
    """A source that dumps a whole session into the store the moment Start is pressed.

    This is the test stand-in for the simulator thread: it obeys the same contract (it is told
    when the session began and fills the store), but it fills it at once so the test can move a
    fake clock instead of sleeping for 33 seconds.
    """

    name = "sim"

    def __init__(self, scenario: str, seconds: float = 35.0) -> None:
        self.scenario = scenario
        self.seconds = seconds
        self.store: FrameStore | None = None
        self.started_at: int | None = None

    def start(self, store: FrameStore) -> None:
        self.store = store

    def stop(self) -> None:
        return None

    def on_session_start(self, at_ms: int) -> None:
        self.started_at = at_ms
        assert self.store is not None
        total = int(round(self.seconds * FS))
        self.store.push_many(list(cached_frames(self.scenario, at_ms, total)))

    def set_scenario(self, name: str) -> None:
        self.scenario = name


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_station(
    settings_factory: Callable[..., Settings], clock: FakeClock
) -> Callable[..., object]:
    """A station wired to a scripted source and a hand-moved clock."""

    def factory(scenario: str = "regular", seconds: float = 35.0, **overrides: object) -> object:
        from hinigram.station import Station

        settings = settings_factory(**overrides)
        store = FrameStore()
        source = ScriptedSource(scenario, seconds=seconds)
        source.start(store)
        station = Station(store, settings, clock=clock.now, source=source)
        return station

    return factory


@pytest.fixture
def station(make_station: Callable[..., object]) -> object:
    return make_station()


@pytest.fixture
def empty_station(make_station: Callable[..., object]) -> object:
    return make_station(scenario="absent")


@pytest.fixture
def make_frame() -> Callable[..., Frame]:
    """Build a valid CSI frame; tests override only the fields they care about."""

    def factory(
        t: int,
        tx: str = "tx1",
        phase: list[float] | None = None,
        amp: list[float] | None = None,
        ch: int = 3,
    ) -> Frame:
        return Frame(
            v=1,
            t=t,
            tx=tx,  # type: ignore[arg-type]
            ch=ch,
            seq=0,
            rssi=-42.0,
            amp=amp if amp is not None else [1.0] * ch,
            phase=phase if phase is not None else [0.0] * ch,
        )

    return factory
