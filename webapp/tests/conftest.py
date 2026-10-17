"""Shared fixtures for the lane suite.

Clocks and frame sources are always injected: the suite must be deterministic and finish in
seconds, so no test waits on wall-clock time or on a background thread for real frames.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from hinigram.app import create_app
from hinigram.config import Settings
from hinigram.contracts import Frame, Thresholds
from hinigram.pipeline.analyze import Analysis
from hinigram.pipeline.frames import Window

#: Sample rate every synthetic signal in the suite is generated at.
FS = 100.0


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


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, start_ms: int = 1_000_000) -> None:
        self._now = start_ms

    def now(self) -> int:
        return self._now

    def advance(self, ms: int) -> int:
        self._now += ms
        return self._now


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
def client(settings_factory: Callable[..., Settings]) -> Iterator[TestClient]:
    """An HTTP client over the real app, with the lifespan entered."""
    with TestClient(create_app(settings_factory())) as test_client:
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
