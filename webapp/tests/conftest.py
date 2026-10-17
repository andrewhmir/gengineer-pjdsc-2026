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
from hinigram.contracts import Frame
from hinigram.pipeline.frames import Window

#: Sample rate every synthetic signal in the suite is generated at.
FS = 100.0


def respiration(
    bpm: float,
    seconds: float,
    *,
    fs: float = FS,
    noise: float = 0.0,
    jitter: float = 0.0,
    seed: int = 0,
) -> np.ndarray:
    """A respiratory waveform at ``bpm`` with optional rate jitter and additive noise.

    ``jitter`` is a fraction of the rate: 0.06 is a rate that wanders by about six percent,
    which is what an unsteady or distressed rhythm looks like to the phase-locking detector.
    """
    rng = np.random.default_rng(seed)
    n = int(round(seconds * fs))
    t = np.arange(n) / fs
    modulation = np.zeros(n)
    if jitter:
        modulation = jitter * (
            0.6 * np.sin(2 * np.pi * 0.03 * t) + 0.4 * np.sin(2 * np.pi * 0.07 * t + 1.1)
        )
    instantaneous = (bpm / 60.0) * (1.0 + modulation)
    phase = 2 * np.pi * np.cumsum(instantaneous) / fs
    signal = np.sin(phase)
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
