"""The outcome rules, and every word the patient reads.

The table in the design record (§7.3) is implemented here exactly, first match wins. Two things
are deliberately not in JavaScript: which outcome a measurement produces, and what the screen
says about it. Both live in this module so they can be tested without a browser, and so the
kiosk cannot drift from the rules.
"""

from __future__ import annotations

from hinigram.contracts import (
    Advice,
    Chip,
    Confidence,
    Metric,
    Outcome,
    Result,
    Rhythm,
    RuleName,
    StaffDetails,
    StationState,
    StepState,
    Thresholds,
)
from hinigram.pipeline.analyze import Analysis

#: The three-step strip. The same three words appear at every state, with the current one marked.
STEP_LABELS: tuple[str, ...] = ("Stand on the mark", "Stay still · 30 s", "Result")

_STEP_INDEX: dict[str, int] = {"idle": 1, "settle": 1, "measuring": 2, "result": 3}

#: Patient copy, one entry per (outcome, advice) pair the rules can produce. Keeping it keyed
#: this way means a new branch that forgets its copy raises a KeyError in a test, not a blank
#: screen at the station.
_COPY: dict[tuple[str, str], tuple[str, str]] = {
    ("regular", "none"): (
        "Breathing looks regular",
        "No action needed. You can step away.",
    ),
    ("regular", "watch"): (
        "Breathing looks regular",
        "Worth mentioning to staff if you feel unwell. Otherwise you can step away.",
    ),
    ("irregular", "speak_to_nurse"): (
        "Irregular breathing",
        "Please speak to the nurse at the desk before you leave.",
    ),
    ("unclear", "try_again"): (
        "Reading not clear",
        "Please try again. Stand still and breathe normally.",
    ),
}

#: A reading below five breaths is a weak estimate, not a screening result: confidence drops and
#: the outcome becomes unclear rather than a clinical statement.
CONFIDENT_BREATHS = 5


def patient_copy(outcome: Outcome, advice: Advice) -> tuple[str, str]:
    """The headline and the one line of advice for an outcome."""
    return _COPY[(outcome, advice)]


def _confidence(analysis: Analysis, thresholds: Thresholds) -> Confidence:
    if analysis.plv is None or analysis.breaths < thresholds.min_breaths:
        return "none"
    if analysis.breaths < CONFIDENT_BREATHS:
        return "low"
    return "high"


def _advice_for(outcome: Outcome, rr_bpm: float | None, plv: float | None, t: Thresholds) -> Advice:
    if outcome == "unclear":
        return "try_again"
    if outcome == "irregular":
        return "speak_to_nurse"
    watch = rr_bpm is not None and t.rr_watch < rr_bpm <= t.rr_max
    marginal = plv is not None and t.plv_unsteady <= plv < t.plv_min
    return "watch" if watch or marginal else "none"


def _rhythm(outcome: Outcome, plv: float | None, t: Thresholds) -> Rhythm:
    if outcome == "unclear" or plv is None:
        return "Unknown"
    return "Unsteady" if plv < t.plv_min else "Steady"


def _in_regular_band(rr: float | None, plv: float, t: Thresholds) -> bool:
    """The table's plain regular row: an ordinary rate with a locked rhythm."""
    return rr is not None and t.rr_min <= rr <= t.rr_watch and plv >= t.plv_min


def _regular_but_watchful(rr: float | None, plv: float, t: Thresholds) -> bool:
    """The table's watch row: a rate or a rhythm near the edge of ordinary."""
    fast_side = rr is not None and t.rr_watch < rr <= t.rr_max
    marginal_rhythm = t.plv_unsteady <= plv < t.plv_min
    return fast_side or marginal_rhythm


def decide(analysis: Analysis, thresholds: Thresholds) -> Result:
    """Apply the rule table to one analysis. First match wins; exactly one outcome is returned."""
    confidence = _confidence(analysis, thresholds)
    plv = analysis.plv
    rr = analysis.rr_bpm

    if (
        analysis.motion_s > thresholds.motion_max_s
        or analysis.breaths < thresholds.min_breaths
        or analysis.amp_db < thresholds.amp_floor_db
        or plv is None
    ):
        outcome: Outcome = "unclear"
        rule: RuleName = "low_quality"
    elif analysis.flat_s >= thresholds.apnea_flat_s:
        outcome, rule = "irregular", "apnea"
    elif rr is not None and rr > thresholds.rr_max and plv < thresholds.plv_min:
        outcome, rule = "irregular", "tachypnea"
    elif plv < thresholds.plv_unsteady:
        outcome, rule = "irregular", "unsteady"
    elif _in_regular_band(rr, plv, thresholds) or _regular_but_watchful(rr, plv, thresholds):
        outcome, rule = "regular", "none"
    else:
        outcome, rule = "unclear", "low_quality"

    # A weak estimate never becomes a clinical outcome, whichever branch produced it.
    if confidence != "high" and outcome != "unclear":
        outcome, rule = "unclear", "low_quality"

    advice = _advice_for(outcome, rr, plv, thresholds)
    headline, lede = patient_copy(outcome, advice)
    rhythm = _rhythm(outcome, plv, thresholds)
    shown_rr = None if outcome == "unclear" else rr
    return Result(
        outcome=outcome,
        rule=rule,
        headline=headline,
        lede=lede,
        advice=advice,
        rr_bpm=shown_rr,
        plv=plv,
        breaths=analysis.breaths,
        usable_s=analysis.usable_s,
        confidence=confidence,
        rhythm=rhythm,
        flagged=outcome == "irregular",
        metrics=[
            Metric(
                label="Breathing rate",
                value="—" if shown_rr is None else f"{shown_rr:.1f}",
                unit="breaths / min",
            ),
            Metric(label="Rhythm", value=rhythm, unit=None),
        ],
        details=StaffDetails(
            plv=plv,
            plv_threshold=thresholds.plv_min,
            window_s=analysis.usable_s,
            breaths=analysis.breaths,
            tx_used=analysis.tx_used,
        ),
        thresholds=thresholds,
    )


def stage_label(state: StationState, result: Result | None) -> str:
    """The one line printed over the scene. Idle says nobody is there; the rest say what is true."""
    if state == "idle":
        return "No one detected"
    if state in ("settle", "measuring"):
        return "Measuring · stand still"
    if result is None:
        return "Result"
    return {
        "regular": "Breathing looks regular",
        "irregular": "Irregular breathing detected",
        "unclear": "Reading not clear",
    }[result.outcome]


def steps_for(state: StationState) -> list[StepState]:
    """The three-step strip, with the current step marked."""
    current = _STEP_INDEX[state]
    return [
        StepState(
            label=label,
            status="done" if position < current else ("on" if position == current else "todo"),
        )
        for position, label in enumerate(STEP_LABELS, start=1)
    ]


def chip_for(state: StationState, quality: str, result: Result | None) -> Chip | None:
    """The small pill under the headline: where to stand, or why the result is flagged."""
    if state in ("settle", "measuring"):
        if quality == "ok":
            return Chip(text="In position", tone="ok")
        return Chip(text="Keep still", tone="warn")
    if state == "result" and result is not None:
        if result.outcome == "irregular":
            return Chip(text="Flagged for assessment", tone="warn")
        if result.outcome == "unclear":
            return Chip(text="Try again", tone="warn")
    return None
