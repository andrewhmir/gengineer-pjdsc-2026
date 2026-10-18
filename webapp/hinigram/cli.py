"""Command line entry point: parse flags, build settings, serve the station.

One command from a clean clone (``cd webapp && uv sync && uv run hinigram``) is a scored
requirement, so this module stays free of optional imports at module scope: a missing pyserial
must not stop the simulator from starting.
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from hinigram.app import create_app
from hinigram.config import Settings

#: Loopback names a single-operator prototype may bind without a warning.
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hinigram",
        description="Self-service respiratory screening station.",
    )
    parser.add_argument(
        "--source",
        choices=("sim", "replay", "serial"),
        default=None,
        help="where frames come from (default: sim)",
    )
    parser.add_argument("--serial-port", default=None, help="receiver port, e.g. COM5")
    parser.add_argument("--replay-file", default=None, help="JSONL (or .jsonl.gz) replay file")
    parser.add_argument("--scenario", default=None, help="demo scenario the simulator plays")
    parser.add_argument("--host", default=None, help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: 8765)")
    parser.add_argument("--settle-s", type=float, default=None, help="settle seconds (default: 3)")
    parser.add_argument(
        "--capture-s", type=float, default=None, help="capture seconds (default: 30)"
    )
    parser.add_argument(
        "--plv-threshold", type=float, default=None, help="PLV that counts as locked (default: 0.6)"
    )
    parser.add_argument(
        "--rr-max", type=float, default=None, help="tachypnea rate threshold (default: 24)"
    )
    parser.add_argument("--verbose", action="store_true", help="log every request")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    """Overlay the flags that were actually given on top of the defaults."""
    overrides: dict[str, object] = {}
    if args.source is not None:
        overrides["source"] = args.source
    if args.serial_port is not None:
        overrides["serial_port"] = args.serial_port
    if args.replay_file is not None:
        overrides["replay_file"] = args.replay_file
    if args.scenario is not None:
        overrides["scenario"] = args.scenario
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    if args.settle_s is not None:
        overrides["settle_s"] = args.settle_s
    if args.capture_s is not None:
        overrides["capture_s"] = args.capture_s
    if args.plv_threshold is not None:
        overrides["plv_min"] = args.plv_threshold
    if args.rr_max is not None:
        overrides["rr_max"] = args.rr_max
    return Settings(**overrides)  # type: ignore[arg-type]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = settings_from_args(args)

    if settings.host not in LOOPBACK:
        print(
            f"warning: binding {settings.host}; this is not the documented single-operator "
            f"configuration (the station has no authentication)",
            file=sys.stderr,
        )

    url = f"http://{settings.host}:{settings.port}"
    print(f"Hinigram station - {url} (source: {settings.source})")
    print("Press Ctrl+C to stop. Open the URL and press Start on the station.")

    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="info" if args.verbose else "warning",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by the console script
    raise SystemExit(main())
