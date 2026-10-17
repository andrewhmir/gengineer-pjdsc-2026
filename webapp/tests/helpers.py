"""A clock a test moves by hand.

Kept outside ``conftest`` so a test module can import the type without importing pytest's
fixture machinery twice.
"""

from __future__ import annotations


class FakeClock:
    """A monotonic clock in milliseconds, advanced explicitly by the test."""

    def __init__(self, start_ms: int = 1_000_000) -> None:
        self._now = start_ms

    def now(self) -> int:
        return self._now

    def advance(self, ms: int) -> int:
        self._now += ms
        return self._now
