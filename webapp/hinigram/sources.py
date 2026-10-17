"""Frame sources: a scripted simulator, a committed replay, and the serial receiver.

The station must run with no hardware, so the simulator is the reference source and the replay
fixture is the reproducibility proof. Both produce exactly the frame contract in
``contracts.Frame``. A scenario's times are seconds from the moment Start was pressed, so a
scripted pause or movement lands inside the capture window rather than wherever the server
happened to be running.
"""

from __future__ import annotations

import gzip
import json
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from hinigram.clock import monotonic_ms
from hinigram.config import PACKAGE_DIR, Settings
from hinigram.contracts import Frame
from hinigram.pipeline.frames import FrameStore, parse_frame_line

#: Where the committed scenario definitions live.
SCENARIOS_PATH = PACKAGE_DIR / "fixtures" / "scenarios.json"

#: The rig: three transmitters at three distances from the mark, with their default relative
#: signal strengths. A scenario may override them.
DEFAULT_GAINS: tuple[float, float, float] = (0.35, 0.18, 0.08)

#: Simulator timing: how often the emit thread wakes, and how long a generated buffer lasts.
EMIT_INTERVAL_S = 0.05
IDLE_BUFFER_S = 20.0
SESSION_BUFFER_S = 45.0


@dataclass(frozen=True)
class Scenario:
    """One scripted screening: a rate, how variable it is, and what happens when.

    ``cv`` is the coefficient of variation of the breath-to-breath interval — the variability a
    distressed rhythm shows. ``apnea`` and ``motion`` are windows in seconds from Start: the
    generator stalls the breath phase during an apnea, and adds movement artefacts during a
    motion window, rather than switching the waveform off and leaving a step for a filter to
    ring on.
    """

    rr_bpm: float
    cv: float = 0.0
    noise: float = 0.02
    gains: tuple[float, float, float] = DEFAULT_GAINS
    apnea: tuple[float, float] | None = None
    motion: tuple[float, float] | None = None
    seed: int = 0
    label: str = ""


def _as_window(raw: Any) -> tuple[float, float] | None:
    if not raw:
        return None
    start, stop = raw
    return (float(start), float(stop))


def scenario_from_dict(name: str, raw: dict[str, Any]) -> Scenario:
    """Build a scenario from its JSON entry, with the documented defaults for what is absent."""
    gains = tuple(float(gain) for gain in raw.get("gains", DEFAULT_GAINS))
    return Scenario(
        rr_bpm=float(raw.get("rr_bpm", 15.0)),
        cv=float(raw.get("cv", 0.0)),
        noise=float(raw.get("noise", 0.02)),
        gains=gains,  # type: ignore[arg-type]
        apnea=_as_window(raw.get("apnea")),
        motion=_as_window(raw.get("motion")),
        seed=int(raw.get("seed", 0)),
        label=str(raw.get("label", name)),
    )


def load_scenarios(path: Path | None = None) -> dict[str, Scenario]:
    """Every scripted scenario, keyed by the name the query parameter uses."""
    raw: dict[str, dict[str, Any]] = json.loads(
        (path or SCENARIOS_PATH).read_text(encoding="utf-8")
    )
    return {name: scenario_from_dict(name, entry) for name, entry in raw.items()}


def _gate(t: np.ndarray, window: tuple[float, float], ramp_s: float = 0.6) -> np.ndarray:
    """A 0-1 gate that is 0 inside ``window`` and 1 outside, with half-cosine edges.

    A hard switch puts a step into the phase series and the detector's filters ring for seconds
    afterwards — an artefact that looks exactly like the paused breathing being simulated.
    """
    start, stop = window
    half = max(ramp_s / 2.0, 1e-6)
    gate = np.ones_like(t)
    gate[(t >= start) & (t <= stop)] = 0.0
    left = (t >= start - half) & (t < start)
    gate[left] = 0.5 * (1.0 + np.cos(np.pi * (t[left] - start + half) / half))
    right = (t > stop) & (t <= stop + half)
    gate[right] = 0.5 * (1.0 - np.cos(np.pi * (t[right] - stop) / half))
    return np.clip(gate, 0.0, 1.0)


def waveform(
    scenario: Scenario,
    n: int,
    fs: float,
    seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """The breathing modulation and the movement artefact for ``n`` samples.

    The breath phase is the integral of an instantaneous rate whose cycle boundaries come from
    lognormal intervals; an apnea window stalls that integral instead of zeroing the output, so
    the phase stays continuous.
    """
    rng = np.random.default_rng(scenario.seed if seed is None else seed)
    seconds = n / fs
    t = np.arange(n) / fs
    mean_interval = 60.0 / scenario.rr_bpm
    onsets = [0.0]
    while onsets[-1] < seconds:
        interval = mean_interval
        if scenario.cv:
            interval *= float(np.exp(rng.normal(0.0, scenario.cv) - 0.5 * scenario.cv**2))
        onsets.append(onsets[-1] + interval)
    cycles = np.interp(t, np.array(onsets), np.arange(len(onsets)))
    increments = np.diff(cycles, prepend=cycles[0])
    if scenario.apnea is not None:
        increments = increments * _gate(t, scenario.apnea)
    breathing = np.sin(2.0 * math.pi * np.cumsum(increments))
    movement = np.zeros(n)
    if scenario.motion is not None:
        # The gate is 1 outside the window, so invert it: movement happens *inside* the window.
        gate = 1.0 - _gate(t, scenario.motion, ramp_s=0.3)
        # A person shifting their weight swings the phase by more than a breath does; the burst
        # has to dominate the residual above 3 Hz or it is indistinguishable from noise.
        movement = gate * (
            1.2 * np.sin(2.0 * math.pi * 6.0 * t) + 0.6 * np.sin(2.0 * math.pi * 8.5 * t + 1.0)
        )
    return breathing, movement


def simulate_frames(
    scenario: Scenario,
    start_ms: int,
    n: int,
    fs: float = 100.0,
    seed: int | None = None,
) -> list[Frame]:
    """Generate ``n`` samples for all three transmitters, in time order.

    Deterministic for a scenario and a seed: the same script runs on every occasion, which is
    what makes the demonstration reproducible and the tests exact. Noise is added *after* the
    per-transmitter gain, so the three nodes differ in signal-to-noise ratio, not only in scale.

    Frames are constructed without pydantic validation: this function is the only producer, the
    values are generated rather than parsed, and ten thousand validations per session would cost
    more than the whole demonstration. ``test_a_generated_frame_validates`` pins the equivalence.
    """
    breathing, movement = waveform(scenario, n, fs, seed=seed)
    rng = np.random.default_rng((scenario.seed if seed is None else seed) + 1_000)
    total = n * 3
    noise = rng.normal(0.0, scenario.noise, (total, 3))
    rssi_noise = rng.normal(0.0, 0.2, total)
    amp_noise = rng.normal(0.0, 0.3, (total, 3))
    names = ("tx1", "tx2", "tx3")
    frames: list[Frame] = []
    row = 0
    for index in range(n):
        timestamp = start_ms + int(round(index * 1000.0 / fs))
        for channel, name in enumerate(names):
            gain = scenario.gains[channel]
            phase = [
                gain * (0.9 + 0.1 * subcarrier) * breathing[index]
                + 0.5 * movement[index]
                + float(noise[row, subcarrier])
                for subcarrier in range(3)
            ]
            frames.append(
                Frame.model_construct(
                    v=1,
                    t=timestamp,
                    tx=name,
                    ch=3,
                    seq=index,
                    rssi=-42.5 - 3.0 * channel + float(rssi_noise[row]),
                    amp=[-20.0 - 3.0 * channel + float(amp_noise[row, s]) for s in range(3)],
                    phase=phase,
                )
            )
            row += 1
    return frames


@runtime_checkable
class Source(Protocol):
    """Anything that can fill a frame store, and be told when a session started."""

    name: str

    def start(self, store: FrameStore) -> None: ...

    def stop(self) -> None: ...

    def on_session_start(self, at_ms: int) -> None: ...

    def set_scenario(self, name: str) -> None: ...


@dataclass
class SimulatorSource:
    """Emits a scripted scenario in real time, restarting the script at every session."""

    scenario: Scenario
    fs: float = 100.0
    name: str = "sim"
    clock: Callable[[], int] = monotonic_ms
    _store: FrameStore | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _index: int = 0
    _epoch_ms: int = 0
    _buffer: list[Frame] = field(default_factory=list, repr=False)
    _buffer_seconds: float = 0.0

    def start(self, store: FrameStore) -> None:
        self._store = store
        self._epoch_ms = self.clock()
        self._buffer = []
        self._buffer_seconds = 0.0
        self._index = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="simulator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def on_session_start(self, at_ms: int) -> None:
        """Restart the script so its pauses and movements land inside this session."""
        with self._lock:
            self._epoch_ms = at_ms
            self._index = 0
            self._buffer = []
            self._buffer_seconds = 0.0

    def set_scenario(self, name: str) -> None:
        """Play a different script from the next session: the demonstration's only control."""
        scenarios = load_scenarios()
        if name not in scenarios:
            raise ValueError(f"unknown scenario {name!r}; choose one of {sorted(scenarios)}")
        with self._lock:
            self.scenario = scenarios[name]
            self._buffer = []
            self._buffer_seconds = 0.0

    def _frames_for(self, seconds: float) -> list[Frame]:
        """Generate (and cache) the script for the given horizon of this epoch."""
        if self._buffer and self._buffer_seconds >= seconds:
            return self._buffer
        self._buffer = simulate_frames(
            self.scenario, self._epoch_ms, int(round(seconds * self.fs)), self.fs
        )
        self._buffer_seconds = seconds
        return self._buffer

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                store = self._store
                if store is not None:
                    horizon = SESSION_BUFFER_S if self._index else IDLE_BUFFER_S
                    frames = self._frames_for(horizon)
                    want = int((self.clock() - self._epoch_ms) * self.fs / 1000.0)
                    if self._index == 0 and want > 0:
                        # Nothing was emitted before Start; begin at the current offset.
                        self._index = max(0, want - int(EMIT_INTERVAL_S * self.fs))
                    if want > self._index:
                        stop = min(want, len(frames) // 3)
                        self._store.push_many(frames[self._index * 3 : stop * 3])  # type: ignore[union-attr]
                        self._index = stop
                    if self._index >= len(frames) // 3:
                        # The scripted buffer is spent. Start a fresh one from now, so a station
                        # left idle for a minute does not report a dead source, and a result
                        # screen left open does not run out of frames before it resets.
                        self._epoch_ms = self.clock()
                        self._index = 0
                        self._buffer = []
                        self._buffer_seconds = 0.0
            time.sleep(EMIT_INTERVAL_S)


@dataclass
class ReplaySource:
    """Replays a committed JSON Lines fixture at its recorded pace, restarting per session."""

    path: Path
    name: str = "replay"
    clock: Callable[[], int] = monotonic_ms
    _store: FrameStore | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _frames: list[Frame] = field(default_factory=list, repr=False)
    _index: int = 0
    _epoch_ms: int = 0

    def start(self, store: FrameStore) -> None:
        self._store = store
        self._frames = iter_replay_fixture(self.path)
        self._epoch_ms = self.clock()
        self._index = 0
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="replay", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def on_session_start(self, at_ms: int) -> None:
        with self._lock:
            self._index = 0
            self._epoch_ms = at_ms

    @property
    def position(self) -> int:
        """How many fixture frames this session has already emitted."""
        return self._index

    def set_scenario(self, name: str) -> None:
        """A recorded session has no script to choose; the request is ignored."""
        return None

    def _run(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                store = self._store
                if store is not None and self._frames:
                    origin = self._frames[0].t
                    now_ms = self.clock()
                    while self._index < len(self._frames):
                        frame = self._frames[self._index]
                        if origin + (now_ms - self._epoch_ms) < frame.t:
                            break
                        store.push(frame)
                        self._index += 1
            time.sleep(EMIT_INTERVAL_S)


@dataclass
class SerialSource:
    """Reads receiver frames from a serial port, counting anything it cannot parse."""

    port: str
    baudrate: int = 115200
    name: str = "serial"
    closed: bool = False
    #: The open stream. A test injects a fake; the thread opens a real port when it is unset.
    stream: Any = None
    _store: FrameStore | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)

    def start(self, store: FrameStore) -> None:
        self._store = store
        self.closed = False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="serial", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.closed = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def on_session_start(self, at_ms: int) -> None:
        """A real receiver has no script to restart; the frames are whatever they are."""

    def set_scenario(self, name: str) -> None:
        """A real receiver has no script to choose either."""
        return None

    def read_frames(self, store: FrameStore | None = None, limit: int = 1000) -> list[Frame]:
        """Read every complete line currently available from ``stream``.

        Kept separate from the thread so a test can feed a fake stream with a good line and a
        malformed one, and assert that the good frame survives while the bad one is counted
        rather than raised.
        """
        frames: list[Frame] = []
        counter = store or self._store
        if self.stream is None:
            return frames
        for _ in range(limit):
            raw = self.stream.readline()
            if not raw:
                break
            frame = parse_frame_line(raw)
            if frame is None:
                if counter is not None:
                    counter.count_malformed()
                continue
            frames.append(frame)
        return frames

    def _run(self) -> None:
        while not self._stop.is_set():
            if self.stream is None:
                try:
                    import serial  # imported lazily: the simulator must run without pyserial

                    self.stream = serial.Serial(self.port, self.baudrate, timeout=0.5)
                except ImportError:
                    self.closed = True
                    return
                except Exception:
                    time.sleep(1.0)
                    continue
            for frame in self.read_frames():
                if self._store is not None:
                    self._store.push(frame)
            time.sleep(0.01)


def build_source(settings: Settings, clock: Callable[[], int] = monotonic_ms) -> Source:
    """Construct the source the settings name, refusing an incomplete configuration."""
    scenarios = load_scenarios()
    if settings.source == "serial":
        if not settings.serial_port:
            raise ValueError("--serial-port is required for --source serial")
        return SerialSource(port=settings.serial_port)
    if settings.source == "replay":
        return ReplaySource(path=settings.replay_file, clock=clock)
    if settings.scenario not in scenarios:
        raise ValueError(
            f"unknown scenario {settings.scenario!r}; choose one of {sorted(scenarios)}"
        )
    return SimulatorSource(scenario=scenarios[settings.scenario], clock=clock)


def iter_replay_fixture(path: Path | None = None) -> list[Frame]:
    """Read the committed replay fixture (JSON Lines, optionally gzipped)."""
    resolved = path or (PACKAGE_DIR / "fixtures" / "replay_session.jsonl.gz")
    opener = gzip.open if resolved.suffix == ".gz" else open
    frames: list[Frame] = []
    with opener(resolved, "rt", encoding="utf-8") as handle:
        for line in handle:
            frame = parse_frame_line(line)
            if frame is not None:
                frames.append(frame)
    return frames
