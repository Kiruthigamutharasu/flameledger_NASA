"""Habitat Review endpoints: deterministic verdicts, verified AI explanation, Markdown report."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .config import Settings
from .data import Dataset
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
