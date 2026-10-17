"""Wire contracts shared by the pipeline, the state machine, and the HTTP surface.

These models are the interface between layers that never import each other's internals: the
pipeline returns them, the state machine stores them, and the API serialises them unchanged.
Every duration in this package is integer milliseconds and every timestamp is epoch
milliseconds; that convention is enforced here, once, rather than remembered at each call site.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

#: The three frame sources a station can run from. ``serial`` means real hardware; the chip in
#: the kiosk header renders this as LIVE/REPLAY/SIM so simulated data never looks live (REQ-103).
SourceName = Literal["sim", "replay", "serial"]


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
