"""Habitat Review endpoints: deterministic verdicts, verified AI explanation, Markdown report."""
from __future__ import annotations

import csv
import io
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .ask import Asker
from .config import Settings
from .data import Dataset
from .investigations import Catalogue, compare, rank
from .llm import Explainer
from .report import build_report
from .report_pdf import build_pdf
from .rules import Habitat, RulesEngine, Thresholds

log = logging.getLogger(__name__)

MaterialText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class ThresholdsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    red_o2_tolerance_pct: float = Field(default=0.0, ge=0, le=5)
    thin_margin_pct_o2: float = Field(default=0.5, ge=0, le=5)


class ReviewRequest(BaseModel):
    o2_pct: float = Field(gt=0, le=100, description="Habitat oxygen, % by volume")
    pressure_psia: float = Field(gt=0, le=30, description="Habitat total pressure, psia")
    gravity_g: float = Field(ge=0, le=1.5, description="Gravity level in Earth g")
    materials: list[MaterialText] = Field(min_length=1, max_length=20)
    preset_id: str | None = Field(default=None, max_length=40, pattern=r"^[a-z0-9_]+$")
    thresholds: ThresholdsIn | None = None

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, json_schema_extra={"example": {
        "o2_pct": 34, "pressure_psia": 8.2, "gravity_g": 0.165, "preset_id": "lunar_habitat_nominal",
        "materials": ["PMMA rod", "cotton-fiberglass fabric", "silicone", "Synergy Pro Navy fabric"]}})


class MatrixRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    materials: list[MaterialText] = Field(min_length=1, max_length=20)
    preset_ids: list[Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]+$", max_length=40)]] = Field(min_length=2, max_length=6)
    thresholds: ThresholdsIn | None = None


class RateLimiter:
    """Sliding-window limit per client IP, in memory (one process on Render)."""

    def __init__(self, limit: int, window_s: float = 60.0, max_clients: int = 10_000):
        self.limit, self.window, self.max_clients = limit, window_s, max_clients
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > self.max_clients:  # drop idle clients so memory stays bounded
                for ip in [ip for ip, q in self._hits.items() if not q or now - q[-1] > self.window]:
                    del self._hits[ip]
            q = self._hits.setdefault(client, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def build_router(dataset: Dataset, settings: Settings, disclaimer: str, commit) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["habitat review"])
    engine = RulesEngine(dataset)
    explainer = Explainer(settings)
    review_limit = RateLimiter(10)
    report_limit = RateLimiter(20)
    presets = {p.preset_id: p for p in dataset.presets}
    router.explainer = explainer  # exposed for tests

    def run_rules(req: ReviewRequest) -> dict:
        preset = presets.get(req.preset_id) if req.preset_id else None
        matches = preset and (preset.o2_pct, preset.pressure_psia, preset.gravity_g) == (req.o2_pct, req.pressure_psia, req.gravity_g)
        habitat = Habitat(req.o2_pct, req.pressure_psia, req.gravity_g, preset.label if matches else "Custom habitat")
        th = Thresholds(**req.thresholds.model_dump()) if req.thresholds else Thresholds()
        review = engine.review(habitat, list(req.materials), th)
        if matches:
            review["habitat"].update({"preset_id": preset.preset_id, "source_note": preset.source_note,
                                      "source_url": preset.source_url or None})
        return review

    def guard(limiter: RateLimiter, request: Request):
        if not limiter.allow(client_ip(request)):
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")

    @router.post("/review", summary="Review a habitat atmosphere and a list of materials")
    def review(req: ReviewRequest, request: Request):
        """Deterministic verdicts from the ledger, plus a Gemini explanation that is shown only if it passes
        the verifier. `ai_status` is one of verified, failed_verification, unavailable, not_configured."""
        guard(review_limit, request)
        result = run_rules(req)
        ai = explainer.explain(result)
        return {**result, "ai": ai.ai, "ai_status": ai.status, "ai_note": ai.note}

    @router.post("/review/matrix", summary="Check the same materials across several habitat atmospheres")
    def review_matrix(req: MatrixRequest, request: Request):
        """Deterministic verdicts only (no AI): one row per material, one column per preset atmosphere."""
        guard(report_limit, request)
        chosen = [presets[p] for p in req.preset_ids if p in presets]
        if len(chosen) != len(req.preset_ids):
            raise HTTPException(status_code=422, detail="Unknown preset id.")
        th = Thresholds(**req.thresholds.model_dump()) if req.thresholds else Thresholds()
        columns, per_preset = [], []
        for p in chosen:
            columns.append({"preset_id": p.preset_id, "label": p.label, "o2_pct": p.o2_pct,
                            "pressure_psia": p.pressure_psia, "gravity_g": p.gravity_g})
            per_preset.append(engine.review(Habitat(p.o2_pct, p.pressure_psia, p.gravity_g, p.label), list(req.materials), th))
        rows = []
        for idx, item in enumerate(per_preset[0]["verdicts"]):
            cells = []
            for res in per_preset:
                v = res["verdicts"][idx]
                cells.append({"level": v["headline"]["level"], "emoji": v["headline"]["emoji"], "label": v["headline"]["label"],
                              "reason": v["headline"]["reason"], "n_verdicts": len(v["verdicts"])})
            rows.append({"input": item["input"], "material": item["material"], "material_id": item["material_id"], "cells": cells})
        return {"columns": columns, "rows": rows, "thresholds": th.as_dict(),
                "disclaimer": "Research decision support, not certification."}

    @router.post("/report", summary="Download the Habitat Review as Markdown",
                 response_class=Response, responses={200: {"content": {"text/markdown": {}}}})
    def report(req: ReviewRequest, request: Request):
        """Same input as /api/review. Uses an AI explanation only if one was already verified for this input."""
        guard(report_limit, request)
        result = run_rules(req)
        ai = explainer.explain(result, cache_only=True)
        text = build_report(result, ai.ai, ai.status, ai.note, dataset, disclaimer,
                            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), commit())
        return Response(text, media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="flameledger_habitat_review.md"'})

    @router.post("/report.pdf", summary="Download the Habitat Review as PDF",
                 response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
    def report_pdf(req: ReviewRequest, request: Request):
        """Same input and content as /api/report, laid out as a PDF with clickable source links."""
        guard(report_limit, request)
        result = run_rules(req)
        ai = explainer.explain(result, cache_only=True)
        try:
            data = build_pdf(result, ai.ai, ai.status, ai.note, dataset, disclaimer,
                             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), commit())
        except Exception:  # noqa: BLE001 - never surface a stack trace; Markdown stays available
            log.exception("PDF report failed")
            raise HTTPException(status_code=500, detail="The PDF report could not be created. "
                                                        "Please download the Markdown report instead.")
        return Response(data, media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="flameledger_habitat_review.pdf"'})

    return router


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=300)


def build_investigations_router(cat: Catalogue, dataset: Dataset, explainer: Explainer) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["investigations"])
    asker = Asker(cat, dataset, explainer)
    ask_limit = RateLimiter(10)
    profile_ids = [p.id for p in cat.habitat_profiles]

    @router.get("/investigations", summary="NASA combustion investigations relevant to fire safety")
    def investigations(area: str | None = None, fuel_type: str | None = None, flag: str | None = None):
        """The full catalogue (or a filtered part of it), with the sources behind every field."""
        items = list(cat.investigations)
        if area:
            items = [i for i in items if area in i.areas]
        if fuel_type:
            items = [i for i in items if i.fuel_type.lower().startswith(fuel_type.lower())]
        if flag:
            items = [i for i in items if flag in i.flags]
        return {"compiled_on": cat.compiled_on, "statement": cat.statement, "flags": cat.flags,
                "habitat_profiles": [p.model_dump() for p in cat.habitat_profiles],
                "sources": [s.model_dump() for s in cat.sources],
                "earth_applications": [a.model_dump() for a in cat.earth_applications],
                "investigations": [i.model_dump() for i in items]}

    @router.get("/investigations.csv", summary="The investigation catalogue as CSV")
    def investigations_csv():
        """One row per investigation; list fields are joined with '; ' and every row keeps its sources."""
        cols = ["id", "acronym", "name", "project", "areas", "fuel_type", "platform", "hardware", "status", "objective",
                "fuels", "conditions", "variables", "measurements", "o2_min_pct", "o2_max_pct", "o2_note",
                "relevance_tags", "earth_application", "ledger_rows", "sources"]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        for i in cat.investigations:
            o2 = i.o2_range
            writer.writerow({
                "id": i.id, "acronym": i.acronym, "name": i.name, "project": i.project, "areas": "; ".join(i.areas),
                "fuel_type": i.fuel_type, "platform": i.platform, "hardware": i.hardware, "status": i.status,
                "objective": i.objective, "fuels": i.fuels, "conditions": i.conditions, "variables": i.variables,
                "measurements": i.measurements,
                "o2_min_pct": "" if not o2 or o2.min is None else f"{o2.min:g}", "o2_max_pct": f"{o2.max:g}" if o2 else "",
                "o2_note": f"{o2.label} [{o2.source_id}, {o2.location}]" if o2 else "",
                "relevance_tags": "; ".join(i.flags), "earth_application": i.earth_application,
                "ledger_rows": "; ".join(i.ledger_rows),
                "sources": "; ".join(f"{c.source_id} ({c.location}) {cat.source(c.source_id).url}" for c in i.sources)})
        return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="flameledger_investigations.csv"'})

    @router.get("/investigations/rank", summary="Rank investigations by relevance to a habitat type")
    def investigations_rank(habitat: str = "lunar_base"):
        """Transparent weighted sum of sourced relevance flags. Weights are FlameLedger research settings."""
        if habitat not in profile_ids:
            raise HTTPException(status_code=422, detail=f"habitat must be one of: {', '.join(profile_ids)}")
        return rank(cat, habitat)

    @router.get("/investigations/compare", summary="Compare two or three investigations side by side")
    def investigations_compare(ids: str):
        wanted = [i.strip() for i in ids.split(",") if i.strip()]
        if not 2 <= len(wanted) <= 3 or len(set(wanted)) != len(wanted):
            raise HTTPException(status_code=422, detail="Give two or three different investigation ids, comma-separated.")
        try:
            return compare(cat, wanted)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown investigation id.")

    @router.get("/investigations/{inv_id}", summary="One investigation")
    def investigation(inv_id: str):
        inv = cat.get(inv_id)
        if inv is None:
            raise HTTPException(status_code=404, detail="Unknown investigation id.")
        return inv.model_dump()

    @router.post("/ask", summary="Ask a question; answered only from the catalogue and the verified ledger")
    def ask(req: AskRequest, request: Request):
        """Returns the most relevant sourced evidence and, when Gemini is available and the answer passes the
        verifier, a short answer. `ai_status` is verified, failed_verification, unavailable, not_configured or no_match."""
        if not ask_limit.allow(client_ip(request)):
            raise HTTPException(status_code=429, detail="Too many questions. Please wait a minute and try again.")
        return asker.ask(req.question)

    return router
