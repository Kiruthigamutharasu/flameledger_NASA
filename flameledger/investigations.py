"""NASA combustion investigations: catalogue, habitat relevance ranking and side-by-side comparison.

The catalogue (data/investigations.json) is loaded and validated once at startup, like the ledger.
Ranking is a transparent weighted sum of sourced relevance flags; the weights are FlameLedger's
own research settings, not NASA criteria, and every score comes with its reasons.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .data import MAX_QUOTE_WORDS, DataError

NOT_SUMMARISED = "Not yet summarised"
RANKING_LABEL = "FlameLedger ranking weights, not NASA criteria"
Area = Literal["prevention", "detection", "suppression", "fundamental"]
Flag = Literal["solid_materials", "ventilation_flow", "habitat_atmosphere", "partial_gravity",
               "large_scale", "detection", "suppression"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class InvSource(_Strict):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://")


class Citation(_Strict):
    source_id: str = Field(min_length=1)
    location: str = Field(min_length=1)


class Quote(_Strict):
    text: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    location: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _short(cls, v: str) -> str:
        if len(v.split()) > MAX_QUOTE_WORDS:
            raise ValueError(f"quote is longer than {MAX_QUOTE_WORDS} words")
        return v


class Investigation(_Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    acronym: str = Field(min_length=1)
    name: str = Field(min_length=1)
    project: str
    areas: list[Area] = Field(min_length=1)
    fuel_type: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    hardware: str = Field(min_length=1)
    status: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    fuels: str = Field(min_length=1)
    conditions: str = Field(min_length=1)
    variables: str = Field(min_length=1)
    measurements: str = Field(min_length=1)
    flags: dict[Flag, str]
    quotes: list[Quote] = Field(min_length=1)
    earth_application: str
    ledger_rows: list[str]
    sources: list[Citation] = Field(min_length=1)


class EarthApplication(_Strict):
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    investigation_ids: list[str]
    source_id: str = Field(min_length=1)
    location: str = Field(min_length=1)


class HabitatProfile(_Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1)
    weights: dict[Flag, int]

    @model_validator(mode="after")
    def _range(self):
        if any(not 0 <= w <= 5 for w in self.weights.values()):
            raise ValueError("weights must be between 0 and 5")
        return self


class Catalogue(_Strict):
    compiled_on: str
    statement: str
    sources: list[InvSource]
    flags: dict[Flag, str]
    habitat_profiles: list[HabitatProfile] = Field(min_length=1)
    investigations: list[Investigation] = Field(min_length=1)
    earth_applications: list[EarthApplication]

    def source(self, source_id: str) -> InvSource | None:
        return next((s for s in self.sources if s.source_id == source_id), None)

    def get(self, inv_id: str) -> Investigation | None:
        return next((i for i in self.investigations if i.id == inv_id), None)

    def profile(self, profile_id: str) -> HabitatProfile | None:
        return next((p for p in self.habitat_profiles if p.id == profile_id), None)


def load_catalogue(data_dir: Path, ledger_row_ids: set[str]) -> Catalogue:
    path = Path(data_dir) / "investigations.json"
    try:
        cat = Catalogue.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise DataError([f"investigations.json: {exc}"]) from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        raise DataError([f"investigations.json: {str(exc)[:800]}"]) from exc

    problems: list[str] = []
    known = {s.source_id for s in cat.sources}
    ids = [i.id for i in cat.investigations]
    if len(ids) != len(set(ids)):
        problems.append("investigations.json: duplicate investigation id")
    for inv in cat.investigations:
        for ref in [q.source_id for q in inv.quotes] + [c.source_id for c in inv.sources]:
            if ref not in known:
                problems.append(f"investigations.json {inv.id}: unknown source_id '{ref}'")
        for row in inv.ledger_rows:
            if row not in ledger_row_ids:
                problems.append(f"investigations.json {inv.id}: ledger row '{row}' is not a verified ledger row")
        for flag in inv.flags:
            if flag not in cat.flags:
                problems.append(f"investigations.json {inv.id}: undefined flag '{flag}'")
    for app in cat.earth_applications:
        if app.source_id not in known:
            problems.append(f"investigations.json earth application '{app.title}': unknown source_id")
        for inv_id in app.investigation_ids:
            if inv_id not in ids:
                problems.append(f"investigations.json earth application '{app.title}': unknown investigation '{inv_id}'")
    if problems:
        raise DataError(problems)
    return cat


def rank(cat: Catalogue, profile_id: str) -> dict:
    """Score every investigation for one habitat profile; ties keep catalogue order."""
    profile = cat.profile(profile_id)
    if profile is None:
        raise KeyError(profile_id)
    rows = []
    for order, inv in enumerate(cat.investigations):
        reasons = [{"flag": f, "label": cat.flags[f], "weight": profile.weights.get(f, 0), "evidence": note}
                   for f, note in inv.flags.items() if profile.weights.get(f, 0) > 0]
        reasons.sort(key=lambda r: -r["weight"])
        rows.append({"id": inv.id, "acronym": inv.acronym, "name": inv.name, "areas": inv.areas,
                     "score": sum(r["weight"] for r in reasons), "reasons": reasons, "_order": order})
    rows.sort(key=lambda r: (-r["score"], r["_order"]))
    for pos, r in enumerate(rows, start=1):
        r["rank"] = pos
        del r["_order"]
    return {"profile": profile.model_dump(), "label": RANKING_LABEL,
            "max_score": sum(profile.weights.values()), "results": rows}


COMPARE_FIELDS = ["areas", "platform", "hardware", "fuel_type", "fuels", "conditions", "variables",
                  "measurements", "status"]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower())} - {"the", "and", "with", "for", "not", "yet", "summarised"}


def compare(cat: Catalogue, ids: list[str]) -> dict:
    items = [cat.get(i) for i in ids]
    if any(i is None for i in items):
        raise KeyError(",".join(i for i, it in zip(ids, items) if it is None))
    rows = []
    for field in COMPARE_FIELDS:
        values = [getattr(i, field) for i in items]
        shown = [", ".join(v) if isinstance(v, list) else v for v in values]
        known = [v for v in shown if v != NOT_SUMMARISED]
        rows.append({"field": field, "values": shown,
                     "same": len(known) == len(shown) and len(set(known)) == 1})
    shared_areas = sorted(set.intersection(*(set(i.areas) for i in items)))
    shared_flags = sorted(set.intersection(*(set(i.flags) for i in items)))
    shared_hw = sorted(set.intersection(*(_words(i.hardware) for i in items)) & {"mdca", "cir", "msg", "acme", "spice", "glovebox"})
    return {"ids": ids, "acronyms": [i.acronym for i in items], "rows": rows,
            "similarities": {"areas": shared_areas, "flags": [cat.flags[f] for f in shared_flags],
                             "hardware_terms": shared_hw},
            "note": "Similarities are computed from the catalogue fields; 'Not yet summarised' never counts as a match."}
