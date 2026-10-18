"""The station's clock, in one place.

Everything that compares a timestamp inside the station uses this clock. The sources stamp their
frames with it too — a simulator on wall-clock time and a state machine on monotonic time produce
frames that are forty years away from the window being measured, which reads as "no signal" and
returns the station to idle. That bug is why this module exists.
"""

from __future__ import annotations

import time


def monotonic_ms() -> int:
    """Milliseconds from an arbitrary origin; never jumps when the system clock is adjusted."""
    return int(time.monotonic() * 1000)
