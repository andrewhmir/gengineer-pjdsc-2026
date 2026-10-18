"""One window becomes one measurement.

``analyze_window`` is the seam between "some numbers arrived" and "here is what they say": the
transmitter choice, the rate, the rhythm, and the quality flags are all decided here, so the
state machine stays a timer and the rules stay a table.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from hinigram.contracts import Thresholds
from hinigram.pipeline.analyze import analyze_window
from hinigram.pipeline.frames import Window


def test_a_clean_window_yields_numbers(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    windows = {
        "tx1": fake_window(gain=0.35),
        "tx2": fake_window(gain=0.15),
        "tx3": fake_window(gain=0.05),
    }
    result = analyze_window(windows, default_thresholds)
    assert result is not None
    assert abs(result.rr_bpm - 15.0) <= 1.0
    assert result.tx_used == "tx1"
    assert result.plv > 0.6
    assert result.motion_s < 1.0
    assert result.breaths >= 5
    assert result.usable_s == pytest.approx(29.99, abs=0.1)


def test_movement_in_the_window_is_reported(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    result = analyze_window({"tx1": fake_window(burst=(10.0, 14.0))}, default_thresholds)
    assert result is not None
    assert result.motion_s > 2.0


def test_a_breath_pause_is_reported(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    result = analyze_window({"tx1": fake_window(flat=(10.0, 22.0))}, default_thresholds)
    assert result is not None
    assert result.flat_s > 9.0


def test_no_windows_is_no_measurement(default_thresholds: Thresholds) -> None:
    assert analyze_window({}, default_thresholds) is None


def test_a_window_too_short_to_measure_is_refused(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    """A second of data cannot support a claim about a rhythm (REQ-122)."""
    assert analyze_window({"tx1": fake_window(seconds=1.0)}, default_thresholds) is None


def test_the_analysis_keeps_the_phases_the_trace_needs(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    result = analyze_window({"tx1": fake_window()}, default_thresholds)
    assert result is not None
    assert result.phi_breath.shape == result.phi_osc.shape == result.banded.shape
    assert result.t.shape == result.banded.shape
    assert result.t[0] == pytest.approx(0.0)


def test_a_gap_in_the_window_is_measured_as_missing_time(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    """A dropout is missing *data*, not a shorter window: the two must be told apart."""
    full = fake_window()
    mask = np.ones(full.t.shape[0], dtype=bool)
    mask[10 * 100 : 20 * 100] = False
    holed = Window(t=full.t[mask], phase=full.phase[mask], amp=full.amp[mask], fs=full.fs)

    result = analyze_window({"tx1": holed}, default_thresholds)
    assert result is not None
    assert result.gap_s == pytest.approx(10.0, abs=0.3)
    assert result.usable_s == pytest.approx(20.0, abs=0.5)


def test_an_intact_window_reports_no_gap(
    fake_window: Callable[..., Window], default_thresholds: Thresholds
) -> None:
    result = analyze_window({"tx1": fake_window()}, default_thresholds)
    assert result is not None
    assert result.gap_s < 0.05
    assert result.usable_s == pytest.approx(result.usable_s, abs=0.0)  # finite, not NaN
    assert result.usable_s > 29.0
