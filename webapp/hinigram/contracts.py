"""Wire contracts shared by the pipeline, the state machine, and the HTTP surface.

These models are the interface between layers that never import each other's internals: the
pipeline returns them, the state machine stores them, and the API serialises them unchanged.
Every duration in this package is integer milliseconds and every timestamp is epoch
milliseconds; that convention is enforced here, once, rather than remembered at each call site.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

#: The three frame sources a station can run from. ``serial`` means real hardware; the chip in
#: the kiosk header renders this as LIVE/REPLAY/SIM so simulated data never looks live (REQ-103).
SourceName = Literal["sim", "replay", "serial"]

#: The transmitters the rig defines. The receiver is the fourth node and never a frame source.
TxName = Literal["tx1", "tx2", "tx3"]

#: The only frame version this parser accepts. A future firmware bumps it, and an old station
#: must reject the frame rather than mis-read it (design record §18, risk table).
FRAME_VERSION = 1


class Frame(BaseModel):
    """One CSI frame from the receiver, as JSON Lines.

    ``ch`` is the receiver's own channel count and is recorded, not trusted: ``amp`` and
    ``phase`` are the subcarrier vectors the detector uses, and they must be non-empty and the
    same length. An unknown ``v`` is rejected rather than coerced.
    """

    model_config = ConfigDict(frozen=True)

    v: int = FRAME_VERSION
    t: int
    tx: TxName
    ch: int
    seq: int
    rssi: float
    amp: list[float]
    phase: list[float]

    @field_validator("v")
    @classmethod
    def _known_version(cls, value: int) -> int:
        if value != FRAME_VERSION:
            raise ValueError(f"unsupported frame version {value}")
        return value

    @field_validator("amp")
    @classmethod
    def _amp_matches_phase(cls, value: list[float], info: object) -> list[float]:
        data = getattr(info, "data", {})
        phase = data.get("phase")
        if not value:
            raise ValueError("amp must not be empty")
        if phase is not None and len(phase) != len(value):
            raise ValueError("amp and phase must describe the same subcarriers")
        return value


class Thresholds(BaseModel):
    """The prototype decision thresholds, in one object so the API can publish them.

    They are configuration, not constants: an operator can move any of them with a CLI flag,
    and the Method page is required to state where they came from. None of these values is
    clinical (design record §7.3).
    """

    model_config = ConfigDict(frozen=True)

    rr_min: float
    rr_max: float
    rr_watch: float
    plv_min: float
    plv_unsteady: float
    apnea_flat_s: float
    motion_max_s: float
    min_breaths: int
    amp_floor_db: float


class Health(BaseModel):
    """The station's own liveness: is a source producing frames right now?"""

    ok: bool
    source: SourceName
    detail: str
    last_frame_age_ms: int | None = None


#: The session states. A station is in exactly one of them, and the transitions are owned by
#: ``station.Station`` — nothing else may write a state.
StationState = Literal["idle", "settle", "measuring", "result"]

#: The only three things a screening may conclude. There is deliberately no fourth.
Outcome = Literal["regular", "irregular", "unclear"]

#: Which rule produced the outcome. ``none`` means the regular branch with no caveat.
RuleName = Literal["none", "tachypnea", "apnea", "unsteady", "low_quality"]

#: What the patient is asked to do. Kept separate from the outcome so a regular-but-marginal
#: reading can carry ``watch`` without becoming an alarm.
Advice = Literal["none", "watch", "speak_to_nurse", "try_again"]

#: How much the measurement can be trusted. Low or none forces ``unclear`` (REQ-122).
Confidence = Literal["high", "low", "none"]

#: Words, not colours: the panel prints one of these beside the rate.
Rhythm = Literal["Steady", "Unsteady", "Unknown"]

#: Chip tones map to the design tokens; the text is what a person reads.
ChipTone = Literal["ok", "warn", "crit", "neutral"]
StepStatus = Literal["done", "on", "todo"]


class Metric(BaseModel):
    """One number rendered on the result panel, formatted server-side so the copy is tested."""

    label: str
    value: str
    unit: str | None = None


class StaffDetails(BaseModel):
    """The values behind the collapsed "Details for staff" fold."""

    plv: float | None
    plv_threshold: float
    window_s: float
    breaths: int
    tx_used: str | None


class Chip(BaseModel):
    """A small status pill: a word and a tone, never colour alone."""

    text: str
    tone: ChipTone


class StepState(BaseModel):
    """One item of the three-step strip above the action button."""

    label: str
    status: StepStatus


class Result(BaseModel):
    """The outcome of one screening, with the numbers and the rule that produced it."""

    outcome: Outcome
    rule: RuleName
    headline: str
    lede: str
    advice: Advice
    rr_bpm: float | None
    plv: float | None
    breaths: int
    usable_s: float
    confidence: Confidence
    rhythm: Rhythm
    flagged: bool
    metrics: list[Metric]
    details: StaffDetails
    thresholds: Thresholds
