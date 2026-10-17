"""One window becomes one measurement.

This is the seam between "some frames arrived" and "here is what they say". The transmitter
choice, the rate, the rhythm, and the quality flags are all decided here, which keeps the state
machine a timer and the outcome rules a table.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hinigram.contracts import Thresholds
from hinigram.pipeline import dsp, hopf
from hinigram.pipeline.frames import Window

#: A measurement needs at least this much signal. Two seconds is four samples of a 2 Hz signal
#: and about half a breath at rest — below it, any number would be an invention (REQ-122).
MIN_USABLE_S = 2.0


@dataclass(frozen=True)
class Analysis:
    """Everything one window said, including the series the trace endpoint publishes."""

    tx_used: str | None
    rr_bpm: float | None
    plv: float | None
    breaths: int
    motion_s: float
    flat_s: float
    amp_db: float
    usable_s: float
    banded: np.ndarray
    t: np.ndarray
    phi_breath: np.ndarray
    phi_osc: np.ndarray
    locked: bool
    winding: float

    @property
    def no_breath(self) -> bool:
        """True when the window contains no detectable breath at all."""
        return self.breaths == 0


def analyze_window(
    windows: dict[str, Window],
    thresholds: Thresholds,
) -> Analysis | None:
    """Measure one window, or None when there is nothing worth measuring.

    The transmitter with the strongest respiratory modulation is chosen first: with one person
    in the zone the other two carry noise, and picking the wrong one produces a weak signal that
    reads as an unclear result rather than as a wrong number.
    """
    chosen = dsp.best_transmitter(windows)
    if chosen is None:
        return None
    name, banded, snr = chosen
    window = windows[name]
    if snr < thresholds.presence_snr:
        # Noise only: nobody is breathing in the zone. Reporting a rate here is the failure mode
        # the presence gate exists to prevent, so the window is refused rather than measured.
        return None
    duration_s = float((window.t[-1] - window.t[0]) / 1000.0)
    if duration_s < MIN_USABLE_S:
        return None
    component = dsp.first_component(dsp.unwrap_channels(window.phase))
    locking = hopf.phase_locking(banded, window.fs)
    return Analysis(
        tx_used=name,
        rr_bpm=locking.rr_bpm,
        plv=locking.plv,
        breaths=locking.breaths,
        motion_s=dsp.motion_seconds(window),
        flat_s=dsp.flat_seconds(component, window.fs),
        amp_db=dsp.rms_db(component),
        usable_s=duration_s,
        banded=banded,
        t=(window.t - window.t[0]) / 1000.0,
        phi_breath=locking.phi_breath,
        phi_osc=locking.phi_osc,
        locked=locking.plv >= thresholds.plv_min,
        winding=locking.winding,
    )
