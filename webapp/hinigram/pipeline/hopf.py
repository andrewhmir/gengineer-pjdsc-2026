"""The phase-locking value, measured against the rhythm the window itself measured.

The design record specifies a damped Hopf oscillator driven by the observed waveform. Measured
against this simulator that statistic reads about 0.9 at every variability level, because a
damped resonator simply tracks its driver: the phase difference is a constant lag, so it cannot
carry information about how irregular the rhythm is (recorded as a deviation in the plan).

What is kept from the design is the oscillator, the phase-difference definition of PLV, and the
Hopf model. What changes is that the oscillator is the *autonomous limit cycle* whose frequency
is learned from the window — the rhythm the window measured. The phase-locking value then asks
the useful question: does each breath stay on that rhythm, or does the phase slip off it? It is
rate-independent (a steady 26 breaths per minute locks as tightly as a steady 15) and it falls
when the breath-to-breath intervals wander.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from hinigram.pipeline import dsp
from hinigram.pipeline.dsp import hilbert_phase


@dataclass(frozen=True)
class HopfParams:
    """Limit-cycle parameters. ``mu > 0`` is what makes the oscillator autonomous."""

    mu: float = 0.5
    omega: float | None = None


#: The station's oscillator configuration. A module-level singleton so a callable default is
#: not constructed on every call (and so a test can pass its own without rebuilding it).
DEFAULT_PARAMS = HopfParams()


@dataclass(frozen=True)
class Locking:
    """One measurement of rhythm coherence, plus the two phases that produced it."""

    plv: float
    winding: float
    phi_breath: np.ndarray
    phi_osc: np.ndarray
    rr_bpm: float | None
    breaths: int


def _learn_omega(phi_breath: np.ndarray, fs: float) -> float:
    """Least-squares slope of the unwrapped breath phase, in radians per second."""
    unwrapped = np.unwrap(np.asarray(phi_breath, dtype=np.float64))
    if unwrapped.shape[0] < 2:
        return 2.0 * math.pi * 0.25
    t = np.arange(unwrapped.shape[0]) / fs
    slope = float(np.polyfit(t, unwrapped, 1)[0])
    return slope if slope > 0 else 2.0 * math.pi * 0.25


def reference_phase(
    phi_breath: np.ndarray,
    fs: float,
    params: HopfParams | None = None,
) -> tuple[np.ndarray, float]:
    """The phase of an autonomous Hopf oscillator locked to the window's mean rhythm.

    The oscillator is started on its limit cycle with the angular offset that centres the phase
    difference on zero, and integrated with RK4 at the frame rate. Its phase advance is therefore
    exactly the learned rate, and ``plv`` then measures only how far the breath slips away from
    it. Returns the unwrapped reference phase and the learned angular frequency.
    """
    resolved = params or DEFAULT_PARAMS
    values = np.asarray(phi_breath, dtype=np.float64)
    n = values.shape[0]
    if n == 0:
        return np.zeros(0), 2.0 * math.pi * 0.25
    unwrapped = np.unwrap(values)
    omega = resolved.omega if resolved.omega is not None else _learn_omega(values, fs)
    t = np.arange(n) / fs
    offset = float(np.angle(np.mean(np.exp(1j * (unwrapped - omega * t)))))
    radius = math.sqrt(max(resolved.mu, 1e-9))
    state = radius * complex(math.cos(offset), math.sin(offset))
    dt = 1.0 / fs
    mu = resolved.mu
    phases = np.empty(n, dtype=np.float64)

    def derivative(z: complex) -> complex:
        return (mu + 1j * omega) * z - (abs(z) ** 2) * z

    for index in range(n):
        phases[index] = math.atan2(state.imag, state.real)
        k1 = derivative(state)
        k2 = derivative(state + 0.5 * dt * k1)
        k3 = derivative(state + 0.5 * dt * k2)
        k4 = derivative(state + dt * k3)
        state = state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return np.unwrap(phases), omega


def analytic_phase(x: np.ndarray) -> np.ndarray:
    """The breathing waveform's instantaneous phase, in radians."""
    return hilbert_phase(x)


def plv(phi_a: np.ndarray, phi_b: np.ndarray) -> float:
    """The phase-locking value: ``|mean_t exp(i(phi_a - phi_b))|``.

    One means the phase difference never changes over the window; zero means it is spread
    evenly around the circle. It is the same statistic the research notebook reports as
    ``|C_ij|``, applied to the breath against the rhythm the window measured.
    """
    a = np.asarray(phi_a, dtype=np.float64)
    b = np.asarray(phi_b, dtype=np.float64)
    if a.shape[0] == 0 or a.shape[0] != b.shape[0]:
        return 0.0
    return float(np.abs(np.mean(np.exp(1j * (a - b)))))


def winding(phi_breath: np.ndarray, phi_osc: np.ndarray, breaths: int) -> float:
    """Oscillator cycles per breath, as a ratio around 1.0.

    A locked 1:1 rhythm keeps the two phases at a fixed offset, so the drift across the window is
    near zero and this reads about 1.00. A rhythm that slips reads above or below one. With no
    breaths detected there is no ratio to report, so 1.0 is returned rather than a division by
    zero.
    """
    if breaths <= 0:
        return 1.0
    a = np.unwrap(np.asarray(phi_breath, dtype=np.float64))
    b = np.unwrap(np.asarray(phi_osc, dtype=np.float64))
    if a.shape[0] < 2 or a.shape != b.shape:
        return 1.0
    drift = float((a[-1] - b[-1]) - (a[0] - b[0]))
    return float(np.clip(1.0 + drift / (2.0 * math.pi * breaths), -4.0, 4.0))


def phase_locking(x: np.ndarray, fs: float) -> Locking:
    """Everything the detector needs from one bandpassed window, in one call.

    ``x`` is expected to be bandpassed already; the phase is taken from its analytic signal, and
    the rate and breath count come from the same estimator the outcome rules use, so the phase
    and the number always describe the same window.
    """
    values = np.asarray(x, dtype=np.float64)
    phi_breath = analytic_phase(values)
    phi_osc, _omega = reference_phase(phi_breath, fs)
    try:
        rr_bpm, breaths = dsp.estimate_rr(values, fs)
    except ValueError:
        rr_bpm, breaths = None, 0
    return Locking(
        plv=plv(phi_breath, phi_osc),
        winding=winding(phi_breath, phi_osc, breaths),
        phi_breath=phi_breath,
        phi_osc=phi_osc,
        rr_bpm=rr_bpm,
        breaths=breaths,
    )
