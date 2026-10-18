"""The HTTP shell: one process, one page, one polling endpoint.

This module is the only place that knows about FastAPI. ``pipeline/``, ``station.py`` and
``sources.py`` import no web framework, which keeps the detector and the state machine testable
without an HTTP client and keeps this file small enough to read in one screen.

Polling, not server-sent events: a kiosk on loopback polls one small JSON document four times a
second while it measures, and once a second otherwise. A stream would add reconnection semantics
for no gain, and a stalled stream can wedge a station that a poll simply recovers from.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hinigram import __version__
from hinigram.clock import monotonic_ms
from hinigram.config import PACKAGE_DIR, Settings
from hinigram.contracts import Health, SessionState, Trace
from hinigram.pipeline.frames import FrameStore
from hinigram.sources import build_source, load_scenarios
from hinigram.station import NotInResult, SessionBusy, Station

#: How often the server advances the state machine on its own. Requests also advance it, so the
#: station is correct even if nothing is polling; this only keeps the clock honest in between.
TICK_INTERVAL_S = 0.25


async def _tick_forever(station: Station) -> None:
    while True:
        # A tick can run a full analysis at a session boundary; keep it off the event loop so a
        # poll never waits behind it.
        await asyncio.to_thread(station.tick)
        await asyncio.sleep(TICK_INTERVAL_S)


def create_app(
    settings: Settings | None = None,
    *,
    source: object | None = None,
    clock: Callable[[], int] | None = None,
    station: Station | None = None,
) -> FastAPI:
    """Build the station application.

    ``station`` is injected by tests so a whole session runs on a fake clock; without it the app
    builds a real one from the settings, starts its source, and advances it on a timer. Nothing
    here measures anything by itself: every route delegates to the state machine.
    """
    resolved = settings or Settings()
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        built_station = station
        built_source = source
        if built_station is None:
            store = FrameStore()
            built_source = source or build_source(resolved, clock=clock or monotonic_ms)
            built_source.start(store)  # type: ignore[attr-defined]
            built_station = Station(
                store,
                resolved,
                clock=clock or monotonic_ms,
                source=built_source,  # type: ignore[arg-type]
            )
        app.state.settings = resolved
        app.state.station = built_station
        ticker = asyncio.create_task(_tick_forever(built_station))
        try:
            yield
        finally:
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker
            if station is None and built_source is not None:
                built_source.stop()  # type: ignore[attr-defined]

    app = FastAPI(
        title="Hinigram screening station",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    app.mount(
        "/static",
        StaticFiles(directory=str(PACKAGE_DIR / "static")),
        name="static",
    )

    def current(request: Request) -> Station:
        return request.app.state.station

    @app.get("/", response_class=HTMLResponse)
    def station_page(request: Request) -> HTMLResponse:
        """The patient surface. Nothing on this page measures anything by itself."""
        return templates.TemplateResponse(
            request,
            "kiosk.html",
            {"source_token": resolved.source_token},
        )

    @app.get("/api/v1/session", response_model=SessionState)
    def read_session(request: Request) -> SessionState:
        """The whole station as one document. The page polls this and renders it."""
        machine = current(request)
        machine.tick()
        return machine.snapshot()

    @app.post("/api/v1/session", response_model=SessionState)
    def start_session(
        request: Request,
        scenario: str | None = Query(default=None),
    ) -> SessionState:
        """Press Start. The only way a measurement ever begins."""
        machine = current(request)
        if scenario is not None:
            if resolved.source != "sim":
                raise HTTPException(
                    status_code=400,
                    detail="a scenario can only be chosen on the simulator source",
                )
            if scenario not in load_scenarios():
                raise HTTPException(status_code=400, detail=f"unknown scenario {scenario!r}")
        try:
            machine.start(scenario)
        except SessionBusy as busy:
            raise HTTPException(status_code=409, detail=str(busy)) from busy
        return machine.snapshot()

    @app.post("/api/v1/session/stop", response_model=SessionState)
    def stop_session(request: Request) -> SessionState:
        machine = current(request)
        machine.stop()
        return machine.snapshot()

    @app.post("/api/v1/session/done", response_model=SessionState)
    def finish_session(request: Request) -> SessionState:
        machine = current(request)
        try:
            machine.done()
        except NotInResult as not_in_result:
            raise HTTPException(status_code=409, detail=str(not_in_result)) from not_in_result
        return machine.snapshot()

    @app.get("/api/v1/session/trace", response_model=Trace)
    def read_trace(request: Request) -> Trace:
        """The measured series behind a finished result, for the staff fold."""
        machine = current(request)
        machine.tick()
        trace = machine.trace()
        if trace is None:
            raise HTTPException(status_code=409, detail="no finished session to trace")
        return trace

    @app.get("/healthz/station", response_model=Health)
    def station_health(request: Request) -> Health:
        """Liveness of the frame source, as the header's status dot reports it."""
        return current(request).health()

    return app
