"""The phase-locking value: does the breath stay on the rhythm the window measured?

The statistic is deliberately a *phase-diffusion* measure, not a filter-lag measure. A damped
oscillator driven by the observed waveform simply tracks that waveform, so the phase difference
between the two stays constant no matter how irregular the rhythm is; that version of the
statistic reads about 0.9 for every signal, including random noise (recorded as a deviation in
the plan). The reference used here is the rhythm the window itself measured, so the value falls
when the breath slips off that rhythm and stays high when it does not — at any rate.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from hinigram.pipeline import dsp, hopf

FS = 100.0


def test_plv_is_one_for_identical_phase() -> None:
    phi = np.linspace(0.0, 20 * np.pi, 3000)
    assert hopf.plv(phi, phi) > 0.999


def test_plv_is_near_zero_for_independent_phase() -> None:
    rng = np.random.default_rng(1)
    a = rng.uniform(0.0, 2 * np.pi, 3000)
    b = rng.uniform(0.0, 2 * np.pi, 3000)
    assert hopf.plv(a, b) < 0.1


def test_plv_of_an_empty_window_is_zero() -> None:
    assert hopf.plv(np.zeros(0), np.zeros(0)) == 0.0


def test_a_steady_rhythm_has_high_plv_and_winding_near_one(
    synth: Callable[..., np.ndarray],
) -> None:
    banded = dsp.bandpass(synth(bpm=15.0, seconds=30.0, noise=0.01), FS)
    locking = hopf.phase_locking(banded, FS)
    assert locking.plv > 0.85
    assert 0.85 < locking.winding < 1.15


def test_plv_does_not_depend_on_the_rate(synth: Callable[..., np.ndarray]) -> None:
    """A steady 26 breaths per minute is a regular rhythm, not a badly-locked one."""
    steady_slow = hopf.phase_locking(dsp.bandpass(synth(bpm=15.0, seconds=30.0), FS), FS)
    steady_fast = hopf.phase_locking(dsp.bandpass(synth(bpm=26.4, seconds=30.0), FS), FS)
    assert steady_fast.plv > 0.85
    assert abs(steady_fast.plv - steady_slow.plv) < 0.15


def test_plv_falls_when_breaths_are_irregular(synth: Callable[..., np.ndarray]) -> None:
    steady = hopf.phase_locking(dsp.bandpass(synth(bpm=22.0, seconds=30.0), FS), FS)
    irregular = hopf.phase_locking(
        dsp.bandpass(synth(bpm=22.0, seconds=30.0, cv=0.40, seed=3), FS), FS
    )
    assert steady.plv > 0.8
    assert irregular.plv < 0.7
    assert steady.plv - irregular.plv > 0.25


def test_the_reference_oscillator_advances_at_the_learned_rate() -> None:
    phi = np.linspace(0.0, 2 * np.pi * 1.2, 600)  # 1.2 cycles over 6 s = 0.2 Hz
    reference, omega = hopf.reference_phase(phi, FS)
    assert omega == pytest.approx(2 * np.pi * 0.2, rel=0.02)
    advance = np.unwrap(reference)[-1] - np.unwrap(reference)[0]
    assert advance == pytest.approx(omega * (phi.shape[0] - 1) / FS, rel=0.02)


def test_the_reference_oscillator_stays_on_its_limit_cycle() -> None:
    phi = np.linspace(0.0, 2 * np.pi * 6.0, 600)
    reference, _ = hopf.reference_phase(phi, FS)
    assert np.all(np.isfinite(reference))


def test_winding_is_one_when_no_breath_was_detected() -> None:
    phi = np.zeros(100)
    assert hopf.winding(phi, phi, breaths=0) == 1.0
