"""The decision rule: one window in, exactly one outcome out.

The table in the design record (§7.3) is the specification. Each test below pins one row or one
boundary of it, because an off-by-one here is the difference between telling someone they are
fine and telling them to see the nurse.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from hinigram.contracts import Thresholds
from hinigram.pipeline.analyze import Analysis
from hinigram.pipeline.rules import (
    STEP_LABELS,
    chip_for,
    decide,
    panel_copy,
    patient_copy,
    stage_label,
    steps_for,
)


def test_quality_gate_forces_unclear(analysis: Callable[..., Analysis], default_thresholds) -> None:
    result = decide(analysis(motion_s=2.5), default_thresholds)
    assert (result.outcome, result.rule) == ("unclear", "low_quality")
    assert result.advice == "try_again"


def test_few_breaths_force_unclear(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    assert decide(analysis(breaths=2), default_thresholds).outcome == "unclear"


def test_quiet_signal_below_the_amplitude_floor_is_unclear(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    assert decide(analysis(amp_db=-60.0), default_thresholds).outcome == "unclear"


def test_apnea_needs_ten_flat_seconds(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    assert decide(analysis(flat_s=9.9), default_thresholds).rule != "apnea"
    apnea = decide(analysis(flat_s=10.1), default_thresholds)
    assert (apnea.outcome, apnea.rule) == ("irregular", "apnea")
    assert apnea.advice == "speak_to_nurse"


def test_tachypnea_needs_both_a_fast_rate_and_a_slipping_rhythm(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    fast_and_steady = decide(analysis(rr_bpm=26.4, plv=0.7), default_thresholds)
    assert fast_and_steady.rule != "tachypnea"
    assert fast_and_steady.outcome == "unclear"
    fast_and_loose = decide(analysis(rr_bpm=26.4, plv=0.5), default_thresholds)
    assert (fast_and_loose.outcome, fast_and_loose.rule) == ("irregular", "tachypnea")


def test_unsteady_needs_plv_below_four_tenths(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    assert decide(analysis(rr_bpm=16, plv=0.45), default_thresholds).rule == "none"
    unsteady = decide(analysis(rr_bpm=16, plv=0.35), default_thresholds)
    assert (unsteady.outcome, unsteady.rule) == ("irregular", "unsteady")


def test_regular_band_is_eight_to_twenty(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    for rr in (8.0, 15.0, 20.0):
        result = decide(analysis(rr_bpm=rr, plv=0.8), default_thresholds)
        assert result.outcome == "regular"
        assert result.advice == "none"


def test_watch_advice_for_a_rate_between_twenty_and_twentyfour(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    result = decide(analysis(rr_bpm=22.0, plv=0.8), default_thresholds)
    assert (result.outcome, result.advice) == ("regular", "watch")


def test_watch_advice_for_a_marginal_plv(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    result = decide(analysis(rr_bpm=15.0, plv=0.5), default_thresholds)
    assert (result.outcome, result.advice) == ("regular", "watch")


def test_low_confidence_never_produces_a_regular_result(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    """Four breaths is not enough to tell someone they are fine (REQ-122)."""
    result = decide(analysis(breaths=4, rr_bpm=15.0, plv=0.9), default_thresholds)
    assert result.outcome == "unclear"
    assert result.confidence == "low"


def test_a_missing_plv_is_never_confident(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    result = decide(analysis(plv=None), default_thresholds)
    assert (result.outcome, result.confidence) == ("unclear", "none")


def test_every_outcome_has_patient_copy() -> None:
    for outcome, advice in (
        ("regular", "none"),
        ("irregular", "speak_to_nurse"),
        ("unclear", "try_again"),
    ):
        headline, lede = patient_copy(outcome, advice)
        assert headline and lede
        assert headline != lede
        assert headline[0].isupper()


def test_the_copy_is_the_screens_copy() -> None:
    headline, lede = patient_copy("irregular", "speak_to_nurse")
    assert headline == "Irregular breathing"
    assert lede == "Please speak to the nurse at the desk before you leave."


def test_a_result_carries_the_numbers_and_the_thresholds_used(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    result = decide(analysis(rr_bpm=26.4, plv=0.31, breaths=7), default_thresholds)
    assert result.rr_bpm == 26.4
    assert result.plv == 0.31
    assert [metric.label for metric in result.metrics] == ["Breathing rate", "Rhythm"]
    assert result.metrics[0].value == "26.4"
    assert result.metrics[0].unit == "breaths / min"
    assert result.metrics[1].value == "Unsteady"
    assert result.rhythm == "Unsteady"
    assert result.flagged is True
    assert result.details.plv_threshold == pytest.approx(0.60)
    assert result.details.plv == 0.31
    assert result.thresholds == default_thresholds


def test_an_unclear_result_does_not_publish_a_rate(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    result = decide(analysis(rr_bpm=15.0, plv=0.9, motion_s=3.0), default_thresholds)
    assert result.rr_bpm is None
    assert result.flagged is False
    assert [metric.label for metric in result.metrics] == ["Breathing rate", "Rhythm"]


def test_stage_labels_are_sentences_a_patient_reads(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    irregular = decide(analysis(rr_bpm=26.4, plv=0.5), default_thresholds)
    regular = decide(analysis(rr_bpm=15.0, plv=0.9), default_thresholds)
    unclear = decide(analysis(motion_s=3.0), default_thresholds)
    assert stage_label("idle", None) == "No one detected"
    assert stage_label("measuring", None) == "Measuring · stand still"
    assert stage_label("result", irregular) == "Irregular breathing detected"
    assert stage_label("result", regular) == "Breathing looks regular"
    assert stage_label("result", unclear) == "Reading not clear"


def test_the_three_step_strip_marks_the_current_step() -> None:
    assert STEP_LABELS == ("Stand on the mark", "Stay still · 30 s", "Result")
    assert [step.status for step in steps_for("idle")] == ["on", "todo", "todo"]
    assert [step.status for step in steps_for("measuring")] == ["done", "on", "todo"]
    assert [step.status for step in steps_for("result")] == ["done", "done", "on"]


def test_the_panel_copy_belongs_to_the_station_not_the_browser() -> None:
    """Every sentence a patient reads is decided here, so a test can hold it in place."""
    headline, lede, hint = panel_copy("idle", None)
    assert headline == "Step onto the mark"
    assert "arm's length" in lede
    assert hint == "Nothing is measured or stored until you press Start."

    measuring = panel_copy("measuring", None, remaining_s=24)
    assert measuring[0] == "24 seconds"
    assert measuring[1] == "Stay still and breathe normally."


def test_the_result_headline_is_the_results_own(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    irregular = decide(analysis(rr_bpm=26.4, plv=0.5), default_thresholds)
    headline, lede, hint = panel_copy("result", irregular)
    assert headline == "Irregular breathing"
    assert lede == irregular.lede
    assert hint is None


def test_the_position_chip_flips_with_quality() -> None:
    assert chip_for("measuring", "ok", None).text == "In position"
    assert chip_for("measuring", "low", None).text == "Keep still"
    assert chip_for("idle", "ok", None) is None


def test_a_flagged_result_carries_a_warning_chip(
    analysis: Callable[..., Analysis], default_thresholds: Thresholds
) -> None:
    irregular = decide(analysis(rr_bpm=26.4, plv=0.5), default_thresholds)
    assert chip_for("result", "ok", irregular).text == "Flagged for assessment"
