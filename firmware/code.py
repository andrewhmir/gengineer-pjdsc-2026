"""Sensor node entry point for the PJDSC 2026 firmware lane.

The board runs this file automatically on boot, because CircuitPython executes
``code.py`` at the root of the ``CIRCUITPY`` drive. The filename is required and
must not change.

Deployment is a copy, not a build: this file, ``lib/``, and a real ``secrets.py``
are copied onto the drive. Nothing here may import from the repository root,
because the repository does not travel with the copy.

CircuitPython is not CPython. Only the CircuitPython standard library and the
Adafruit bundle vendored in ``lib/`` are available, so this module avoids
``dataclasses``, ``match`` statements, and ``X | Y`` type unions. ``board`` and
``busio`` exist only on-device, so they are imported behind a guard that lets the
module still be imported on a laptop, where the host-side tests run.
"""

try:
    import board  # noqa: F401  # type: ignore[import-not-found]
    import busio  # noqa: F401  # type: ignore[import-not-found]

    #: True only on a board, where the hardware modules import successfully.
    HARDWARE_AVAILABLE = True
except ImportError:
    #: False on a laptop or in CI, where ``board`` and ``busio`` do not exist.
    HARDWARE_AVAILABLE = False


def run_check() -> str:
    """Return a one-line human-readable status for the node.

    This is the hardware-free seam the host-side tests assert on: it reports
    which mode the module woke up in and never raises when no hardware is
    present, so it can be called on a laptop.
    """
    if HARDWARE_AVAILABLE:
        return "firmware: hardware detected, sensor bus ready"

    return "firmware: no hardware detected, running in host-check mode"


def main() -> None:
    """Report node status. CircuitPython calls this module's top level on boot."""
    print(run_check())
    print("firmware: code.py reached the end of the boot path")


if __name__ == "__main__":
    main()
