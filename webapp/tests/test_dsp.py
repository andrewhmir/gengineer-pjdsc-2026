"""The DSP primitives: filter, choose a transmitter, estimate the rate, judge quality.

Each test here names one numeric promise the design record makes, so a regression shows up as a
failing number rather than as a wrong outcome three layers up.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from hinigram.pipeline import dsp
from hinigram.pipeline.frames import Window

FS = 100.0


def test_rr_is_within_one_bpm_at_15(synth: Callable[..., np.ndarray]) -> None:
    x = dsp.bandpass(synth(bpm=15.0, seconds=30.0, noise=0.02), FS)
    rr, breaths = dsp.estimate_rr(x, FS)
    assert abs(rr - 15.0) <= 1.0
    assert breaths >= 5


def test_rr_is_within_one_bpm_at_26_4(synth: Callable[..., np.ndarray]) -> None:
    x = dsp.bandpass(synth(bpm=26.4, seconds=30.0, noise=0.02), FS)
    rr, _ = dsp.estimate_rr(x, FS)
    assert abs(rr - 26.4) <= 1.0


def test_hampel_removes_an_injected_spike(synth: Callable[..., np.ndarray]) -> None:
    clean = synth(bpm=15.0, seconds=10.0, noise=0.0)
    spiked = clean.copy()
    spiked[500] += 6.0
    filtered = dsp.hampel(spiked)
    assert abs(filtered[500] - clean[500]) < 0.5
    assert np.abs(filtered - clean).max() < 0.5


@pytest.mark.parametrize("hz", [0.05, 2.0])
def test_bandpass_rejects_out_of_band_tones(hz: float) -> None:
    t = np.arange(0.0, 30.0, 1 / FS)
    tone = np.sin(2 * np.pi * hz * t)
    filtered = dsp.bandpass(tone, FS)
    assert np.sqrt(np.mean(filtered**2)) < 0.1 * np.sqrt(np.mean(tone**2))


def test_best_transmitter_prefers_the_stronger_stream(
    fake_window: Callable[..., Window],
) -> None:
    windows = {
        "tx1": fake_window(gain=0.35),
        "tx2": fake_window(gain=0.15),
        "tx3": fake_window(gain=0.05),
    }
    chosen = dsp.best_transmitter(windows)
    assert chosen is not None
    assert chosen.name == "tx1"
    assert chosen.snr > 0.5
    assert chosen.banded.shape == (windows["tx1"].t.shape[0],)
    assert chosen.component.shape == (windows["tx1"].t.shape[0],)


def test_band_power_ranks_the_transmitters_by_signal_strength(
    fake_window: Callable[..., Window],
) -> None:
    """The fraction saturates near one; the amount of modulation is what ranks nodes."""
    strong = dsp.band_power(dsp.first_component(fake_window(gain=0.35).phase), FS)
    weak = dsp.band_power(dsp.first_component(fake_window(gain=0.05).phase), FS)
    assert strong > 10 * weak


def test_best_transmitter_needs_enough_samples(fake_window: Callable[..., Window]) -> None:
    assert dsp.best_transmitter({"tx1": fake_window(gain=0.35, seconds=1.0)}) is None


def test_first_component_recovers_the_shared_signal() -> None:
    rng = np.random.default_rng(0)
    shared = np.sin(2 * np.pi * 0.25 * np.arange(3000) / FS)
    series = shared[:, None] + rng.normal(0.0, 0.05, (3000, 3))
    recovered = dsp.first_component(series)
    assert np.corrcoef(recovered, shared)[0, 1] > 0.95


def test_first_component_is_sign_stable() -> None:
    """The sign of a principal component is arbitrary; the function's must not be."""
    shared = np.sin(2 * np.pi * 0.25 * np.arange(1000) / FS)
    series = shared[:, None] * np.array([1.0, 2.0, 3.0])
    first = dsp.first_component(series)
    assert np.array_equal(first, dsp.first_component(series))
    inverted = dsp.first_component(-series)
    assert np.corrcoef(first, -inverted)[0, 1] > 0.99


def test_motion_seconds_ignores_a_still_person(fake_window: Callable[..., Window]) -> None:
    assert dsp.motion_seconds(fake_window(gain=0.35)) < 0.5


def test_motion_seconds_counts_a_four_second_burst(fake_window: Callable[..., Window]) -> None:
    burst = fake_window(gain=0.35, burst=(10.0, 14.0))
    assert dsp.motion_seconds(burst) > 2.5


def test_flat_seconds_ignores_normal_breathing(
    fake_series: Callable[..., np.ndarray],
) -> None:
    assert dsp.flat_seconds(fake_series(gain=0.35), FS) < 1.0


def test_flat_seconds_measures_a_breath_pause(fake_series: Callable[..., np.ndarray]) -> None:
    """A twelve-second pause measures as roughly twelve: edges cost a fraction of a second,
    never the several seconds a narrow filter's ringing would cost."""
    paused = fake_series(gain=0.35, flat=(10.0, 22.0))
    measured = dsp.flat_seconds(paused, FS)
    assert 9.0 < measured < 12.5


def test_decimate_keeps_every_tenth_sample_of_a_100_hz_stream() -> None:
    t = np.arange(0.0, 30.0, 1 / FS)  # seconds, the unit the trace publishes
    x = np.zeros_like(t)
    decimated_t, decimated_x = dsp.decimate(t, x, hz=10.0)
    assert decimated_t.shape == decimated_x.shape
    assert 295 <= decimated_t.shape[0] <= 305


def test_rms_db_reports_a_quiet_signal_as_more_negative_than_a_loud_one() -> None:
    loud = 0.5 * np.sin(2 * np.pi * 0.25 * np.arange(1000) / FS)
    quiet = loud / 100.0
    assert dsp.rms_db(quiet) < dsp.rms_db(loud) - 30.0
