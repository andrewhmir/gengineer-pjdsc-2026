"""The session state machine: one person, one measurement, then idle again.

The machine owns the clock, the session id, and the transitions; it owns no signal processing and
no HTTP. That split is what lets a 33-second session be tested in milliseconds, and what keeps
"nothing is measured before Start" a property of one small class rather than of a request handler.
"""

from __future__ import annotations

import math
import secrets
import threading
from collections.abc import Callable

import numpy as np

from hinigram.clock import monotonic_ms
from hinigram.config import Settings
from hinigram.contracts import (
    Health,
    LiveMetrics,
    Result,
    SessionState,
    StationState,
    Trace,
)
from hinigram.pipeline import dsp
from hinigram.pipeline.analyze import Analysis, analyze_window
from hinigram.pipeline.frames import FrameStore
from hinigram.pipeline.rules import chip_for, decide, panel_copy, stage_label, steps_for
from hinigram.sources import Source

#: How soon after a frame stops arriving the station treats the window as stale. A laptop that
#: slept for ten minutes must produce an unclear reading, not a result from ten minutes ago.
STALE_MS = 2_000

#: Live metrics need at least this much of the capture before they mean anything.
LIVE_MIN_MS = 5_000

#: How often the live rate is recomputed while measuring. The state machine still advances at the
#: polling rate; only the expensive analysis is throttled.
LIVE_REFRESH_MS = 1_000

#: A placeholder analysis for "there is nothing to measure". It deliberately carries no rate and
#: no PLV, so the rules' quality gate produces ``unclear`` rather than inventing a reading.
NO_MEASUREMENT = Analysis(
    tx_used=None,
    rr_bpm=None,
    plv=None,
    breaths=0,
    motion_s=0.0,
    flat_s=0.0,
    gap_s=0.0,
    amp_db=-120.0,
    usable_s=0.0,
    banded=np.zeros(1),
    t=np.zeros(1),
    phi_breath=np.zeros(1),
    phi_osc=np.zeros(1),
    locked=False,
    winding=1.0,
)


class StationError(RuntimeError):
    """Base class for a transition the station refuses."""


class SessionBusy(StationError):
    """Start was pressed while a session was already running."""


class NotInResult(StationError):
    """Done was pressed when there was no result to acknowledge."""


def _new_id() -> str:
    return f"s-{secrets.token_hex(3)}"


class Station:
    """The session state machine, its buffers, and the last measurement."""

    def __init__(
        self,
        store: FrameStore,
        settings: Settings,
        *,
        clock: Callable[[], int] = monotonic_ms,
        source: Source | None = None,
        id_factory: Callable[[], str] = _new_id,
    ) -> None:
        self.store = store
        self.settings = settings
        self.clock = clock
        self.source = source
        self.id_factory = id_factory
        self._lock = threading.Lock()
        self._state: StationState = "idle"
        self._id = ""
        self._scenario: str | None = None
        self._started: int | None = None
        self._settle_until = 0
        self._capture_start = 0
        self._capture_end = 0
        self._result_at = 0
        self._result: Result | None = None
        self._analysis: Analysis | None = None
        self._live: LiveMetrics | None = None
        self._live_at = 0
        self._live_motion = 0.0
        self._quality: str = "ok"
        self._presence = False

    # -- transitions ------------------------------------------------------------------

    @property
    def state(self) -> StationState:
        return self._state

    def start(self, scenario: str | None = None) -> None:
        """Open a session. Nothing is measured before this call, and nothing here measures."""
        with self._lock:
            if self._state != "idle":
                raise SessionBusy(f"the station is {self._state}, not idle")
            now = self.clock()
            self._id = self.id_factory()
            # A script only exists on the simulator; on a recording or a live receiver the
            # payload must not claim one is playing.
            self._scenario = scenario if self.settings.source == "sim" else None
            self._started = now
            self._settle_until = now + int(self.settings.settle_s * 1000)
            self._capture_start = self._settle_until
            self._capture_end = self._capture_start + int(self.settings.capture_s * 1000)
            self._result = None
            self._analysis = None
            self._live = None
            self._live_at = 0
            self._live_motion = 0.0
            self._quality = "ok"
            self._presence = True
            self._state = "settle"
            # The previous person's frames must not be in the buffers this session reads.
            self.store.reset()
            if self.source is not None:
                if scenario:
                    self.source.set_scenario(scenario)
                self.source.on_session_start(now)

    def stop(self) -> None:
        """Abandon the session. Allowed from any running or finished state."""
        with self._lock:
            if self._state != "idle":
                self._to_idle()

    def done(self) -> None:
        """Acknowledge a result and return to idle."""
        with self._lock:
            if self._state != "result":
                raise NotInResult(f"the station is {self._state}, not result")
            self._to_idle()

    def tick(self) -> None:
        """Advance the machine to the current time, through every transition that is due.

        A single call may cross several boundaries — a test jumps straight to the end of a
        session, and a laptop that was suspended wakes up minutes later — so the loop keeps
        stepping while a boundary has been passed. Each branch moves the state forward, so it
        terminates.
        """
        with self._lock:
            now = self.clock()
            while True:
                if self._state == "settle" and now >= self._settle_until:
                    self._finish_settle(now)
                    continue
                if self._state == "measuring" and now >= self._capture_end:
                    self._finish_capture(now)
                    continue
                if self._state == "result" and now - self._result_at >= (
                    self.settings.result_hold_s * 1000
                ):
                    self._to_idle()
                    continue
                if self._state == "measuring":
                    self._refresh_live(now)
                break

    # -- measurement ------------------------------------------------------------------

    def _window_analysis(
        self,
        start_ms: float,
        end_ms: float,
        expected_end_ms: float | None = None,
    ) -> Analysis | None:
        """Measure a window, or None when the frames that window needs never arrived.

        The staleness check compares the last frame against the moment the window *should* have
        ended, not against the wall clock. A laptop that suspends during the capture wakes up
        with a window whose frames stop early, and that must read as unclear rather than as a
        rate computed from fewer seconds than the result claims.
        """
        counters = self.store.counters()
        last = counters.last_t
        expected = end_ms if expected_end_ms is None else expected_end_ms
        if last is None or (expected - last) > STALE_MS:
            return None
        return analyze_window(self.store.window(start_ms, end_ms), self.settings.thresholds())

    def _finish_settle(self, now: int) -> None:
        analysis = self._window_analysis(self._started or now, self._settle_until)
        motion = analysis.motion_s if analysis is not None else 0.0
        if analysis is None or motion > self.settings.motion_max_s:
            # No respiratory signal, or the person is moving: measuring now would be measuring
            # noise. Go back to idle and let the screen ask them to step on the mark again.
            self._to_idle()
            return
        self._presence = True
        self._quality = "ok"
        self._state = "measuring"
        self._live = None

    def _refresh_live(self, now: int) -> None:
        """Recompute the live rate at most once a second.

        The state machine is cheap and runs at the polling rate; the detector is not. A full
        window costs tens of milliseconds, so running it on every tick and every poll would put
        the event loop at a quarter of a core and add hundreds of milliseconds to a response.
        """
        if now - self._capture_start < LIVE_MIN_MS:
            self._live = None
            return
        if self._live is not None and now - self._live_at < LIVE_REFRESH_MS:
            return
        self._live_at = now
        analysis = self._window_analysis(self._capture_start, now)
        if analysis is None:
            # The frames stopped arriving mid-capture: there is nobody measurable in the zone.
            self._live = None
            self._presence = False
            self._quality = "low"
            return
        self._presence = True
        self._analysis = analysis
        self._live_motion = analysis.motion_s
        self._live = LiveMetrics(
            rr_bpm=analysis.rr_bpm,
            amp_db=analysis.amp_db,
            breaths=analysis.breaths,
        )
        self._quality = "low" if analysis.motion_s > 0.5 else "ok"

    def _finish_capture(self, now: int) -> None:
        analysis = self._window_analysis(
            self._capture_start, self._capture_end, expected_end_ms=self._capture_end
        )
        measured = analysis if analysis is not None else NO_MEASUREMENT
        self._analysis = analysis
        self._result = decide(measured, self.settings.thresholds())
        self._live = None
        self._state = "result"
        self._result_at = now

    def _to_idle(self) -> None:
        self._state = "idle"
        self._id = ""
        self._scenario = None
        self._started = None
        self._result = None
        self._analysis = None
        self._live = None
        self._live_motion = 0.0
        self._quality = "ok"
        self._presence = False
        # The previous person's frames leave with them: nothing lingers in the buffers while
        # the station is idle, so the next Start cannot inherit a single sample (REQ-121).
        self.store.reset()

    # -- read-only views --------------------------------------------------------------

    def snapshot(self) -> SessionState:
        """The whole station as one payload, safe to serialise from any state."""
        with self._lock:
            now = self.clock()
            elapsed = 0 if self._started is None else max(0, now - self._started)
            duration = int((self.settings.settle_s + self.settings.capture_s) * 1000)
            remaining_s = max(0, math.ceil((duration - elapsed) / 1000)) if elapsed else None
            headline, lede, hint = panel_copy(self._state, self._result, remaining_s)
            return SessionState(
                id=self._id,
                state=self._state,
                source=self.settings.source,
                scenario=self._scenario,
                started_ms=self._started,
                elapsed_ms=elapsed,
                duration_ms=duration,
                presence=self._presence,
                quality="low" if self._quality == "low" else "ok",
                motion=self._live_motion > 0.5,
                stage_label=stage_label(self._state, self._result),
                headline=headline,
                lede=lede,
                hint=hint,
                chip=chip_for(self._state, self._quality, self._result),
                steps=steps_for(self._state),
                live=self._live,
                result=self._result,
            )

    def trace(self) -> Trace | None:
        """The series behind the result, for the collapsed staff fold."""
        with self._lock:
            analysis = self._analysis
            if self._state != "result" or analysis is None or analysis.t.shape[0] < 2:
                return None
            t, amp = dsp.decimate(analysis.t, analysis.banded)
            _, phi = dsp.decimate(analysis.t, analysis.phi_breath)
            return Trace(
                t=[float(value) for value in t],
                amp=[float(value) for value in amp],
                phi_breath=[float(value) for value in phi],
                plv=float(analysis.plv or 0.0),
                rr_bpm=analysis.rr_bpm,
                amp_db=analysis.amp_db,
                locked=analysis.locked,
                winding=analysis.winding,
                no_breath=analysis.no_breath,
                tx_used=analysis.tx_used,
            )

    def health(self) -> Health:
        """Is a source producing frames right now? The header's status dot reads this."""
        with self._lock:
            counters = self.store.counters()
            last = counters.last_t
            age = None if last is None else max(0, self.clock() - last)
            ok = counters.frames > 0 and age is not None and age <= STALE_MS
            if ok:
                detail = "Source connected"
            elif last is None:
                detail = "No frames yet"
            else:
                detail = f"Last frame {age} ms ago"
            return Health(
                ok=ok,
                source=self.settings.source,
                detail=detail,
                last_frame_age_ms=age,
            )
