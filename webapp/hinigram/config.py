"""Configuration: one settings object, from CLI flags or ``HINIGRAM_*`` environment variables.

Defaults are the design record's documented values (§7.3, D-9). They are reachable from the
command line so a demonstration can change a threshold without editing code, and from the
environment so a deployment can do the same without a shell wrapper.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from hinigram.contracts import Thresholds

#: Directory holding this package: fixtures, templates, and static assets are resolved from it,
#: never from the process working directory.
PACKAGE_DIR = Path(__file__).parent


class Settings(BaseSettings):
    """Station configuration.

    ``source`` selects the frame producer; the timing values are the session shape; the
    ``rr_*``/``plv_*``/threshold fields are the detector's decision rule. Nothing here is a
    secret, so nothing here belongs in ``.env``.
    """

    model_config = SettingsConfigDict(env_prefix="HINIGRAM_", env_file=None, extra="ignore")

    # Frame source.
    source: Literal["sim", "replay", "serial"] = "sim"
    serial_port: str | None = None
    replay_file: Path = PACKAGE_DIR / "fixtures" / "replay_session.jsonl.gz"
    scenario: str = "regular"
    sample_hz: float = 100.0

    # Serve.
    host: str = "127.0.0.1"
    port: int = 8765

    # Session shape: a person is at the station for about 35 seconds.
    settle_s: float = 3.0
    capture_s: float = 30.0
    result_hold_s: float = 20.0

    # Detector thresholds. Prototype values, not clinical ones.
    rr_min: float = 8.0
    rr_max: float = 24.0
    rr_watch: float = 20.0
    plv_min: float = 0.60
    plv_unsteady: float = 0.40
    apnea_flat_s: float = 10.0
    motion_max_s: float = 2.0
    min_breaths: int = 3
    amp_floor_db: float = -40.0
    presence_snr: float = 0.15
    #: The largest hole in a capture that is still a measurement. One second is a hundred
    #: missing frames: a dropped packet is not that, and a link outage is.
    max_gap_s: float = 1.0

    def thresholds(self) -> Thresholds:
        """The subset of settings the decision rules depend on, as a published contract."""
        return Thresholds(
            rr_min=self.rr_min,
            rr_max=self.rr_max,
            rr_watch=self.rr_watch,
            plv_min=self.plv_min,
            plv_unsteady=self.plv_unsteady,
            apnea_flat_s=self.apnea_flat_s,
            motion_max_s=self.motion_max_s,
            min_breaths=self.min_breaths,
            amp_floor_db=self.amp_floor_db,
            presence_snr=self.presence_snr,
            max_gap_s=self.max_gap_s,
        )

    @property
    def source_token(self) -> str:
        """The word shown next to the clock: ``SIM``, ``REPLAY``, or ``LIVE`` (REQ-103)."""
        return {"sim": "SIM", "replay": "REPLAY", "serial": "LIVE"}[self.source]
