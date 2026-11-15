"""FastAPI application: JSON API plus the static frontend, served as one web service."""
from __future__ import annotations

import csv
import io
import logging
import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api import build_router
from .config import ROOT, Settings, get_settings
from .coverage import build_coverage, build_gravity_profile
from .data import LedgerRow, Margin, Preset, Source, load_dataset

log = logging.getLogger(__name__)

DISCLAIMER = ("Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. "
              "Uses public NASA data.")
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
DOCS_PATHS = ("/docs", "/openapi.json")

DESCRIPTION = f"""
Open, read-only API for the FlameLedger evidence ledger: published flammability limits for
spacecraft materials across gravity levels, each with its NASA source, page and a short quote.

**Research decision support, not certification.** {DISCLAIMER}
"""


@lru_cache
def git_commit() -> str:
    commit = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    if commit:
        return commit
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=2)
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "n/a"
    except (OSError, subprocess.SubprocessError):
        return "n/a"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    dataset = load_dataset(settings.data_dir)  # raises DataError: a bad ledger must not start
    coverage = build_coverage(dataset)
    profile = build_gravity_profile(dataset)
    web = settings.web_dir

    app = FastAPI(title="FlameLedger API", version=__version__, description=DESCRIPTION,
                  docs_url="/docs", redoc_url=None)
    app.state.dataset = dataset
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=web / "assets"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not request.url.path.startswith(DOCS_PATHS):  # the interactive API docs load their own assets
            response.headers["Content-Security-Policy"] = CSP
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=300"
        elif request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404 and not request.url.path.startswith("/api/"):
            return FileResponse(web / "404.html", status_code=404)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    # ---------- pages ----------
    @app.get("/", include_in_schema=False)
    async def page_ledger():
        return FileResponse(web / "index.html")

    @app.get("/review", include_in_schema=False)
    async def page_review():
        return FileResponse(web / "review.html")

    @app.get("/fm2", include_in_schema=False)
    async def page_fm2():
        return FileResponse(web / "fm2.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(web / "assets" / "favicon.svg", media_type="image/svg+xml")

    # ---------- API ----------
    @app.get("/api/health", tags=["meta"], summary="Service health")
    async def health():
        return {"status": "ok", "rows": len(dataset.rows), "ai_enabled": settings.ai_enabled, "version": __version__}

    @app.get("/api/meta", tags=["meta"], summary="Build information and disclaimer")
    async def meta():
        return {"date": datetime.now(timezone.utc).date().isoformat(), "commit": git_commit(),
                "version": __version__, "disclaimer": DISCLAIMER}

    @app.get("/api/ledger", tags=["evidence"], response_model=list[LedgerRow],
             summary="Verified evidence rows")
    async def ledger(material_id: str | None = None, environment: str | None = None, evidence_id: str | None = None):
        """Every verified row. Rows that are still being checked are never returned."""
        rows = dataset.rows
        if material_id:
            rows = tuple(r for r in rows if r.material_id == material_id)
        if environment:
            rows = tuple(r for r in rows if r.environment == environment)
        if evidence_id:
            rows = tuple(r for r in rows if r.evidence_id == evidence_id)
        return rows

    @app.get("/api/ledger.csv", tags=["evidence"], summary="Verified evidence rows as CSV")
    async def ledger_csv():
        fields = list(LedgerRow.model_fields)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in dataset.rows:
            writer.writerow({k: ("" if v is None else v) for k, v in row.model_dump().items()})
        return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="flameledger_evidence.csv"'})

    @app.get("/api/margins", tags=["evidence"], response_model=list[Margin],
             summary="Published oxygen margins of safety")
    async def margins():
        """Only margins published by the original authors. FlameLedger never computes a margin."""
        return dataset.margins

    @app.get("/api/sources", tags=["evidence"], response_model=list[Source], summary="Cited sources")
    async def sources():
        return dataset.sources

    @app.get("/api/presets", tags=["evidence"], response_model=list[Preset], summary="Habitat atmosphere presets")
    async def presets():
        return dataset.presets

    @app.get("/api/coverage", tags=["analysis"], summary="Materials by environment coverage grid and metrics")
    async def coverage_grid():
        return coverage

    @app.get("/api/gravity-profile", tags=["analysis"],
             summary="Published limits at 0g, lunar, Mars and 1g for materials with all four")
    async def gravity_profile():
        return profile

    @app.get("/api/hypotheses", tags=["analysis"], summary="Pre-registered FM2 hypotheses")
    async def hypotheses():
        return {**dataset.hypotheses, "sha256": dataset.hypotheses_sha256, "commit": git_commit()}

    review_router = build_router(dataset, settings, DISCLAIMER, git_commit)
    app.state.explainer = review_router.explainer
    app.include_router(review_router)

    @app.get("/api/{rest:path}", include_in_schema=False)
    async def api_not_found(rest: str):
        raise HTTPException(status_code=404, detail="Unknown API endpoint. See /docs.")

    return app


app = create_app()
