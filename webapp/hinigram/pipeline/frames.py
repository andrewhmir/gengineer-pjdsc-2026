"""Frame parsing and the time-indexed buffers the detector reads.

The station asks for *windows by time*, never by index: a session is defined by the moment Start
was pressed, and a test can preload a whole scripted session, move a fake clock, and get exactly
the frames that would have arrived by then. That is why the buffers are ring arrays paired with
their own timestamps rather than queues with a separate clock.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import ValidationError

from hinigram.contracts import Frame

#: Forty seconds at 100 Hz: the 30 s capture plus the 3 s settle, with margin.
DEFAULT_CAPACITY = 4000

#: Fallback sample rate for a window with fewer than three samples, where a median interval
#: cannot be computed. It is the station's documented rate, not a guess about the data.
DEFAULT_FS = 100.0

TX_NAMES: tuple[str, ...] = ("tx1", "tx2", "tx3")


def parse_frame_line(line: str | bytes) -> Frame | None:
    """Parse one JSON Lines frame, or return None when the line is not a usable frame.

    Malformed input is expected on a serial link, so this never raises: the caller counts the
    rejection and keeps reading. A frame from an unknown version is malformed, not coerced.
    """
    try:
        text = line.decode("utf-8") if isinstance(line, bytes) else line
        text = text.strip()
        if not text:
            return None
        payload: Any = json.loads(text)
        if not isinstance(payload, dict):
            return None
        return Frame.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError):
        return None


@dataclass(frozen=True)
class Window:
    """A time slice of one transmitter's frames.

    ``t`` is epoch milliseconds; ``phase`` is radians per subcarrier and ``amp`` is dB. The
    arrays are aligned on the first axis and sorted by time.
    """

    t: np.ndarray
    phase: np.ndarray
    amp: np.ndarray
    fs: float


@dataclass(frozen=True)
class SourceCounters:
    """What the source layer has seen, for the health endpoint and the staff surface later."""

    frames: int
    malformed: int
    per_tx: dict[str, int]
    last_t: int | None


def _sample_rate(t: np.ndarray) -> float:
    """Median sample rate of a sorted timestamp array, in Hz."""
    if t.shape[0] < 3:
        return DEFAULT_FS
    deltas = np.diff(t)
    median = float(np.median(deltas))
    if median <= 0:
        return DEFAULT_FS
    return 1000.0 / median


class TxRing:
    """A fixed-capacity ring of frames for one transmitter.

    The ring keeps the most recent ``capacity`` frames and drops the oldest; the counters keep
    counting everything ever accepted, so a dropped frame is invisible to the detector and still
    visible to the health surface.
    """

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._t = np.zeros(capacity, dtype=np.float64)
        self._phase = np.zeros((capacity, 0), dtype=np.float64)
        self._amp = np.zeros((capacity, 0), dtype=np.float64)
        self._head = 0
        self._size = 0
        self._total = 0
        self._last_t: int | None = None

    def _widen(self, width: int) -> None:
        """Give every slot room for ``width`` subcarriers, zero-padding earlier frames."""
        current = self._phase.shape[1]
        if width <= current:
            return
        pad = width - current
        self._phase = np.pad(self._phase, ((0, 0), (0, pad)))
        self._amp = np.pad(self._amp, ((0, 0), (0, pad)))

    def push(self, frame: Frame) -> None:
        width = len(frame.phase)
        self._widen(width)
        self._t[self._head] = frame.t
        self._phase[self._head, :width] = frame.phase
        self._amp[self._head, :width] = frame.amp
        self._head = (self._head + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)
        self._total += 1
        if self._last_t is None or frame.t > self._last_t:
            self._last_t = frame.t

    def window(self, start_ms: float, end_ms: float) -> Window | None:
        """Frames with ``start_ms <= t <= end_ms``, or None when there are none."""
        if self._size == 0:
            return None
        indices = (np.arange(self._size) + (self._head - self._size)) % self.capacity
        t = self._t[indices]
        mask = (t >= start_ms) & (t <= end_ms)
        if not mask.any():
            return None
        selected = indices[mask]
        t = self._t[selected]
        order = np.argsort(t, kind="stable")
        ordered = selected[order]
        ordered_t = t[order]
        return Window(
            t=ordered_t,
            phase=self._phase[ordered].copy(),
            amp=self._amp[ordered].copy(),
            fs=_sample_rate(ordered_t),
        )

    @property
    def total(self) -> int:
        return self._total

    @property
    def last_t(self) -> int | None:
        return self._last_t


class FrameStore:
    """The three transmitter rings plus the counters the rest of the app reads."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._rings = {name: TxRing(capacity) for name in TX_NAMES}
        self._malformed = 0

    def push(self, frame: Frame) -> None:
        self._rings[frame.tx].push(frame)

    def count_malformed(self) -> None:
        """Record a line the source could not parse; the reader keeps going."""
        self._malformed += 1

    def window(self, start_ms: float, end_ms: float) -> dict[str, Window]:
        """Every transmitter with at least one frame in the range."""
        windows: dict[str, Window] = {}
        for name, ring in self._rings.items():
            window = ring.window(start_ms, end_ms)
            if window is not None:
                windows[name] = window
        return windows

    def reset(self) -> None:
        """Empty every ring. A new session never inherits the previous person's frames."""
        for name, ring in self._rings.items():
            self._rings[name] = TxRing(ring.capacity)
        self._malformed = 0

    def counters(self) -> SourceCounters:
        per_tx = {name: ring.total for name, ring in self._rings.items() if ring.total}
        last_times = [ring.last_t for ring in self._rings.values() if ring.last_t is not None]
        return SourceCounters(
            frames=sum(ring.total for ring in self._rings.values()),
            malformed=self._malformed,
            per_tx=per_tx,
            last_t=max(last_times) if last_times else None,
        )
