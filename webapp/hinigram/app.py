"""The HTTP shell: one process, one page, one polling endpoint.

This module is the only place that knows about FastAPI. ``pipeline/``, ``station.py`` and
``sources.py`` import no web framework, which keeps the detector and the state machine testable
without an HTTP client and keeps this file small enough to read in one screen.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hinigram import __version__
from hinigram.config import PACKAGE_DIR, Settings
from hinigram.contracts import Health

#: Frame source and clock are injectable so tests never wait on wall time or hardware; Task 9
#: wires the real source and the session state machine into this factory.
SourceFactory = Callable[[Settings], object]


def create_app(
    settings: Settings | None = None,
    *,
    source: object | None = None,
    clock: Callable[[], int] | None = None,
) -> FastAPI:
    """Build the station application.

    ``source`` and ``clock`` are accepted here rather than read from globals because the whole
    suite runs on a fake clock and injected frames. Until the session wiring lands they are
    stored and unused; passing them must never be required.
    """
    resolved = settings or Settings()
    templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved
        app.state.source = source
        app.state.clock = clock
        yield

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

    @app.get("/", response_class=HTMLResponse)
    def station(request: Request) -> HTMLResponse:
        """The patient surface. Nothing on this page measures anything by itself."""
        return templates.TemplateResponse(
            request,
            "kiosk.html",
            {"source_token": resolved.source_token},
        )

    @app.get("/healthz/station", response_model=Health)
    def station_health() -> Health:
        """Liveness of the frame source, as the header's status dot reports it."""
        return Health(
            ok=False,
            source=resolved.source,
            detail="starting",
            last_frame_age_ms=None,
        )

    return app
