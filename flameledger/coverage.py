"""Summaries computed from the ledger: coverage grid, headline metrics, gravity profile.

Nothing here creates a new scientific value. Margins come only from margins.csv
(published values); this module never subtracts one ledger row from another.
"""
from __future__ import annotations

from .data import Dataset, LedgerRow

ENVIRONMENTS: list[tuple[str, str, str]] = [
    ("1g", "Normal gravity (1g)", "Ground tests, including NASA-STD-6001B Test 1 style screening"),
    ("microgravity", "Microgravity", "ISS experiments and microgravity ground facilities"),
    ("lunar", "Lunar gravity", "Short-duration ground tests at lunar gravity"),
    ("mars", "Mars gravity", "Short-duration ground tests at Martian gravity"),
    ("fm2", "FM2 on the Moon", "Planned long-duration tests on the lunar surface"),
]
ENV_LABEL = {e[0]: e[1] for e in ENVIRONMENTS}


def fmt(value: float) -> str:
    return f"{value:g}"


def _range(values: list[float]) -> str:
    lo, hi = min(values), max(values)
    return f"{fmt(lo)}% O2" if lo == hi else f"{fmt(lo)} to {fmt(hi)}% O2"


def _cell(rows: list[LedgerRow], ds: Dataset) -> dict:
    if not rows:
        return {"status": "none", "summary": "No data", "n_rows": 0, "row_ids": [], "sources": []}
    values = [r.o2_pct for r in rows if r.o2_pct is not None]
    if all(r.outcome == "planned" for r in rows):
        status, summary = "planned", "Planned: " + (_range(values) if values else "no result yet")
    elif values:
        status = "data"
        summary = _range(values) + (f" ({len(values)} values)" if len(values) > 1 else "")
    else:
        status = "qualitative"
        words = {"burned": "Burned", "extinguished": "Self-extinguished"}
        summary = " / ".join(dict.fromkeys(words.get(r.outcome, "Observed") for r in rows)) + " (qualitative)"
    sources = []
    for sid in dict.fromkeys(r.source_id for r in rows):
        src = ds.source(sid)
        sources.append({"source_id": sid, "short_cite": src.short_cite if src else sid,
                        "url": src.pdf_url if src else ""})
    return {"status": status, "summary": summary, "n_rows": len(rows),
            "row_ids": [r.row_id for r in rows], "sources": sources}


def build_coverage(ds: Dataset) -> dict:
    materials: dict[str, str] = {}
    for row in ds.material_rows:
        materials.setdefault(row.material_id, row.material)

    grid = []
    for mid, name in materials.items():
        cells = {env: _cell([r for r in ds.material_rows if r.material_id == mid and r.environment == env], ds)
                 for env, _, _ in ENVIRONMENTS}
        grid.append({"material_id": mid, "material": name, "cells": cells})

    def count(*envs: str, statuses=("data", "qualitative")) -> int:
        return sum(1 for m in grid if any(m["cells"][e]["status"] in statuses for e in envs))

    total_cells = len(grid) * len(ENVIRONMENTS)
    empty_cells = sum(1 for m in grid for c in m["cells"].values() if c["status"] == "none")
    with_margin = {m.material_id for m in ds.margins}
    metrics = {
        "materials": len(grid),
        "with_1g": count("1g"),
        "with_microgravity": count("microgravity"),
        "with_partial_gravity": count("lunar", "mars"),
        "with_published_margin": len(with_margin),
        "with_long_duration_lunar": count("fm2"),
        "fm2_planned": count("fm2", statuses=("planned",)),
        "published_margins": len(ds.margins),
        "cells_total": total_cells,
        "cells_empty": empty_cells,
        "evidence_rows": len(ds.rows),
        "sources": len(ds.sources),
        "rows_held_back": ds.hidden_rows,
    }
    return {
        "environments": [{"id": e, "label": label, "description": desc} for e, label, desc in ENVIRONMENTS],
        "materials": grid,
        "metrics": metrics,
    }


def build_gravity_profile(ds: Dataset) -> dict:
    """Published limits at all four gravity levels from a single source, per material.

    Only rows that share one evidence_id are grouped, so every panel compares values
    the original authors tabulated together.
    """
    needed = ("microgravity", "lunar", "mars", "1g")
    groups: dict[tuple[str, str], list[LedgerRow]] = {}
    for row in ds.material_rows:
        if row.o2_pct is not None and row.measure in ("moc", "moc_star", "uloi", "uloi_star"):
            groups.setdefault((row.evidence_id, row.material_id), []).append(row)

    materials = []
    for (evidence_id, mid), rows in groups.items():
        points = []
        for env in needed:
            moc = next((r for r in rows if r.environment == env and r.measure.startswith("moc")), None)
            uloi = next((r for r in rows if r.environment == env and r.measure.startswith("uloi")), None)
            if moc is None or uloi is None:
                break
            points.append({"environment": env, "label": ENV_LABEL[env], "gravity_g": moc.gravity_g,
                           "moc_pct_o2": moc.o2_pct, "uloi_pct_o2": uloi.o2_pct,
                           "moc_row_id": moc.row_id, "uloi_row_id": uloi.row_id, "caveat": moc.caveat})
        if len(points) != len(needed):
            continue
        by_env = {p["environment"]: p["moc_pct_o2"] for p in points}
        first = rows[0]
        materials.append({
            "material_id": mid, "material": first.material, "evidence_id": evidence_id,
            "pressure_psia": first.pressure_psia, "source_id": first.source_id, "source_url": first.source_url,
            "location": first.location, "points": points,
            "lunar_below_both": by_env["lunar"] < by_env["microgravity"] and by_env["lunar"] < by_env["1g"],
        })
    return {
        "materials": materials,
        "n_materials": len(materials),
        "n_lunar_below_both": sum(1 for m in materials if m["lunar_below_both"]),
        "measure_note": "Points are the published MOC (1g) and MOC* (low gravity): the highest O2 level at which the flame self-extinguished.",
    }
