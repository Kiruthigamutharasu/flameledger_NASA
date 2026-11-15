"""Deterministic habitat verdicts. This module, not the LLM, decides every verdict.

Every verdict is derived from verified ledger rows and published margins only.
No margin is ever computed here: margins come straight from margins.csv.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .data import AGGREGATE, Dataset, LedgerRow, Margin

DISCLAIMER = "Research decision support, not certification."
THRESHOLD_LABEL = "FlameLedger research thresholds, not NASA criteria"

LEVELS = {
    "red": {"rank": 3, "emoji": "\U0001F534", "label": "Burns in reduced gravity at or below this O2"},
    "orange": {"rank": 2, "emoji": "\U0001F7E0", "label": "Thin or negative published margin"},
    "green": {"rank": 1, "emoji": "\U0001F7E2", "label": "Reduced-gravity evidence of no burning at this O2"},
    "grey": {"rank": 0, "emoji": "⚪", "label": "No space data for this habitat: test needed"},
}

# Aliases use only names that appear in the ledger or in the project brief.
# Each entry is matched as a whole word or phrase, case-insensitively.
ALIASES: dict[str, tuple[str, ...]] = {
    "pmma_rod": ("pmma", "acrylic", "plexiglas", "plexiglass", "polymethyl methacrylate"),
    "sibal_fabric": ("sibal", "cotton-fiberglass", "cotton fiberglass", "cotton/fiberglass"),
    "silicone_mq": ("silicone", "mq"),
    "mylar_g": ("mylar",),
    "ultem_1000": ("ultem",),
    "nomex_ht90_40": ("nomex",),
    "synergy_pro_navy": ("synergy pro navy", "synergy pro", "synergy"),
    "polyimide_pi": ("polyimide", "pi"),
    "peek": ("peek", "polyether ether ketone"),
    "nbr": ("nbr", "nitrile"),
    "pvc_sheet": ("pvc", "polyvinyl chloride"),
    "pom_rod": ("pom", "acetal", "acetron", "delrin", "polyoxymethylene"),
    "pp_rod": ("polypropylene",),
    "nylon_rod": ("nylon",),
    "epoxy_glass": ("epoxy/glass", "epoxy glass", "epoxy"),
}
_ALIAS_RE = [(mid, re.compile(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])"))
             for mid, aliases in ALIASES.items() for a in sorted(aliases, key=len, reverse=True)]

# Guidance for common spacecraft materials that are NOT in the ledger. Every statement comes from a
# NASA source in data/investigations.json (SAME and BRE fact sheets / ISS combustion guide). They never
# map a product onto a ledger entry and never give a value.
HINTS: list[tuple[re.Pattern, str, list[str]]] = [
    (re.compile(r"(?<![a-z])kapton(?![a-z])", re.I),
     "NASA's SAME experiment heated Kapton to study the smoke it makes, for smoke-detector design; that is not a "
     "flammability limit. The ledger's polyimide (PI) entry is a different product, so its values do not apply.", ["same"]),
    (re.compile(r"(?<![a-z])(teflon|ptfe)(?![a-z])", re.I),
     "NASA's SAME experiment heated Teflon to study its smoke (mostly particles under 1 micron), for smoke-detector "
     "design; that is not a flammability limit.", ["same"]),
    (re.compile(r"(?<![a-z])(paper|cellulose)(?![a-z])", re.I),
     "NASA's SAME experiment studied smoke from cellulose, and the BRE experiment emulated burning materials such as "
     "paper with a gas burner; neither gives a flammability limit for this habitat.", ["same", "bre"]),
    (re.compile(r"(?<![a-z])silicone rubber(?![a-z])", re.I),
     "NASA's SAME experiment also heated silicone rubber to study its smoke.", ["same"]),
]


def material_hint(text: str) -> dict | None:
    for pattern, hint_text, ids in HINTS:
        if pattern.search(text or ""):
            return {"text": hint_text, "investigation_ids": ids}
    return None


REDUCED = ("microgravity", "lunar", "mars")
MEASURE_LABEL = {"uloi": "ULOI", "moc": "MOC", "uloi_star": "ULOI*", "moc_star": "MOC*",
                 "blowoff_limit": "Blowoff limit", "steady_spread": "Steady spread"}
ENV_LABEL = {"microgravity": "microgravity", "lunar": "lunar gravity", "mars": "Mars gravity", "1g": "normal gravity (1g)"}


@dataclass(frozen=True)
class Thresholds:
    """FlameLedger research thresholds, not NASA criteria."""
    red_o2_tolerance_pct: float = 0.0   # a burn at up to (habitat O2 + tolerance) counts as red
    thin_margin_pct_o2: float = 0.5     # a published margin below this counts as thin

    def as_dict(self) -> dict:
        return {"red_o2_tolerance_pct": self.red_o2_tolerance_pct,
                "thin_margin_pct_o2": self.thin_margin_pct_o2, "label": THRESHOLD_LABEL}


@dataclass(frozen=True)
class Habitat:
    o2_pct: float
    pressure_psia: float
    gravity_g: float
    label: str = "Custom habitat"


def fmt(value: float) -> str:
    return f"{value:g}"


def match_material(text: str) -> str | None:
    """Map free text to a ledger material_id via the alias table. Unknown text returns None."""
    norm = re.sub(r"\s+", " ", (text or "").lower()).strip()
    if not norm:
        return None
    for mid, pattern in _ALIAS_RE:
        if pattern.search(norm):
            return mid
    return None


def gravity_environment(g: float) -> str | None:
    """The ledger environment that matches a habitat gravity, or None for an in-between value."""
    if g <= 0.01:
        return "microgravity"
    if abs(g - 0.165) <= 0.02:
        return "lunar"
    if abs(g - 0.38) <= 0.03:
        return "mars"
    if g >= 0.9:
        return "1g"
    return None


def gravity_label(g: float) -> str:
    env = gravity_environment(g)
    return {"microgravity": "Microgravity", "lunar": "Lunar gravity", "mars": "Mars gravity",
            "1g": "Normal gravity"}.get(env, "Partial gravity with no matching ledger environment")


def _evidence_row(r: LedgerRow) -> dict:
    return {"id": r.row_id, "kind": "row", "evidence_id": r.evidence_id, "material": r.material,
            "environment": r.environment, "measure": r.measure, "o2_pct": r.o2_pct,
            "pressure_psia": r.pressure_psia, "gravity_g": r.gravity_g, "outcome": r.outcome,
            "flow_note": r.flow_note, "source_id": r.source_id, "source_url": r.source_url,
            "location": r.location, "short_quote": r.short_quote, "caveat": r.caveat}


def _evidence_margin(m: Margin) -> dict:
    return {"id": m.margin_id, "kind": "margin", "evidence_id": m.evidence_id, "material": m.material,
            "environment": m.environment, "measure": "published_margin", "margin_pct_o2": m.margin_pct_o2,
            "gravity_g": m.gravity_g, "basis": m.basis, "source_id": m.source_id, "source_url": m.source_url,
            "location": m.location, "short_quote": m.short_quote, "caveat": m.caveat}


def _press(r: LedgerRow) -> str:
    return f", {fmt(r.pressure_psia)} psia" if r.pressure_psia is not None else ""


class RulesEngine:
    def __init__(self, dataset: Dataset):
        self.ds = dataset
        self.names = {}
        for row in dataset.material_rows:
            self.names.setdefault(row.material_id, row.material)
        self._e11 = next((r for r in dataset.rows if r.evidence_id == "E11"), None)

    # ---------- caveats shared by every verdict ----------
    def _general_caveats(self) -> list[dict]:
        caveats = [{"text": "Test-duct and burner flows are not cabin ventilation. A limit measured in forced "
                            "flow does not transfer directly to a ventilated cabin.", "source": None}]
        if self._e11:
            caveats.append({"text": "NASA authors expect certain partial-gravity environments to increase "
                                    "flammability limits for some materials, so lunar or Mars behaviour can be "
                                    "worse than both 0g and 1g.",
                            "source": {"id": self._e11.row_id, "source_id": self._e11.source_id,
                                       "source_url": self._e11.source_url, "location": self._e11.location}})
        return caveats

    def _pressure_caveat(self, habitat: Habitat, rows: list[LedgerRow]) -> dict | None:
        if not rows:
            return None
        known = sorted({r.pressure_psia for r in rows if r.pressure_psia is not None})
        unknown = [r.row_id for r in rows if r.pressure_psia is None]
        parts = []
        differs = [p for p in known if abs(p - habitat.pressure_psia) > 0.05]
        if differs:
            parts.append(f"The habitat pressure ({fmt(habitat.pressure_psia)} psia) differs from the test "
                         f"pressure of the evidence used ({', '.join(fmt(p) for p in known)} psia). "
                         "Flammability depends on pressure.")
        if unknown:
            parts.append(f"Test pressure is not recorded in the ledger for {', '.join(unknown)}.")
        return {"text": " ".join(parts), "source": None} if parts else None

    # ---------- per material ----------
    def assess(self, text: str, habitat: Habitat, th: Thresholds, key: str) -> dict:
        mid = match_material(text)
        base = {"key": key, "input": text, "material_id": mid, "material": self.names.get(mid) if mid else None}
        if mid is None or mid not in self.names:
            hint = material_hint(text)
            reason = ("This material is not in the FlameLedger ledger. Its reduced-gravity behaviour is "
                      "unknown here; check the NASA materials database and the original test reports.")
            grey = {"level": "grey", **self._level("grey"),
                    "reason": reason + (" " + hint["text"] if hint else ""), "evidence_ids": []}
            return {**base, "headline": grey, "verdicts": [grey], "evidence": [], "hint": hint,
                    "missing": ["No verified evidence for this material in the ledger."],
                    "caveats": self._general_caveats()}

        rows = [r for r in self.ds.material_rows if r.material_id == mid]
        margins = [m for m in self.ds.margins if m.material_id == mid]
        hab_env = gravity_environment(habitat.gravity_g)
        envs = ["microgravity"] + ([hab_env] if hab_env in ("lunar", "mars") else [])
        verdicts: list[dict] = []
        used: dict[str, dict] = {}
        used_rows: list[LedgerRow] = []

        def use(r: LedgerRow):
            if r.row_id not in used:
                used[r.row_id] = _evidence_row(r)
                used_rows.append(r)

        # RED: a reduced-gravity burn at or below the habitat O2
        burns = [r for r in rows if r.environment in envs and r.outcome == "burned" and r.o2_pct is not None
                 and r.o2_pct <= habitat.o2_pct + th.red_o2_tolerance_pct]
        if burns:
            burns.sort(key=lambda r: r.o2_pct)
            for r in burns:
                use(r)
            lines = "; ".join(f"{ENV_LABEL[r.environment]} at {fmt(r.o2_pct)}% O2{_press(r)} ({r.row_id})" for r in burns)
            verdicts.append({"level": "red", **self._level("red"),
                             "reason": f"Burned in {lines}, at or below this habitat's {fmt(habitat.o2_pct)}% O2.",
                             "evidence_ids": [r.row_id for r in burns]})

        # ORANGE: a published margin that is negative or thin
        thin = sorted((m for m in margins if m.environment in envs and m.margin_pct_o2 < th.thin_margin_pct_o2),
                      key=lambda m: m.margin_pct_o2)
        if thin:
            for m in thin:
                used[m.margin_id] = _evidence_margin(m)
            lines = "; ".join(f"{'+' if m.margin_pct_o2 > 0 else ''}{fmt(m.margin_pct_o2)}% O2 in "
                              f"{ENV_LABEL[m.environment]} ({m.margin_id})" for m in thin)
            verdicts.append({"level": "orange", **self._level("orange"),
                             "reason": f"Published margin against the 1g limit: {lines}. Margins are as published "
                                       "by NASA authors; FlameLedger does not compute margins.",
                             "evidence_ids": [m.margin_id for m in thin]})

        # GREEN: extinction at the habitat's own reduced-gravity level, at or above the habitat O2
        if hab_env in REDUCED:
            quench = [r for r in rows if r.environment == hab_env and r.outcome == "extinguished"
                      and r.o2_pct is not None and r.o2_pct >= habitat.o2_pct]
            if quench:
                for r in quench:
                    use(r)
                lines = "; ".join(f"{fmt(r.o2_pct)}% O2{_press(r)} ({r.row_id})" for r in quench)
                verdicts.append({"level": "green", **self._level("green"),
                                 "reason": f"Self-extinguished in {ENV_LABEL[hab_env]} at {lines}, at or above "
                                           f"this habitat's {fmt(habitat.o2_pct)}% O2. This is evidence only, not a safety clearance.",
                                 "evidence_ids": [r.row_id for r in quench]})

        # GREY: nothing above applies
        missing = [f"No {ENV_LABEL[e]} data in the ledger for this material."
                   for e in REDUCED if not any(r.environment == e for r in rows)]
        if hab_env is None:
            missing.append(f"No ledger environment matches {fmt(habitat.gravity_g)} g.")
        planned = [r for r in rows if r.environment == "fm2" and r.outcome == "planned"]
        if planned:
            missing.append("FM2 plans the first long-duration lunar-gravity data for this material; no result yet.")
        elif not any(r.environment == "fm2" for r in rows):
            missing.append("No long-duration lunar-gravity data (FM2 does not test this material).")

        if not verdicts:
            reasons = []
            qual = [r for r in rows if r.environment in REDUCED and r.outcome == "burned" and r.o2_pct is None]
            for r in qual:
                use(r)
            if qual:
                reasons.append("Burned in microgravity (qualitative); O2 not in ledger, cannot compare to this habitat.")
            if planned:
                for r in planned:
                    use(r)
                reasons.append("FM2 plans to test this material in lunar gravity at "
                               + ", ".join(f"{fmt(r.o2_pct)}% O2" for r in sorted(planned, key=lambda r: -r.o2_pct))
                               + f" ({fmt(planned[0].pressure_psia)} psia). No result exists yet.")
            if not reasons:
                reasons.append("The ledger has no reduced-gravity result for this material that can be compared "
                               "with this habitat.")
            nearest = sorted((r for r in rows if r.o2_pct is not None and r.outcome != "planned"),
                             key=lambda r: abs(r.o2_pct - habitat.o2_pct))[:3]
            for r in nearest:
                use(r)
            if nearest:
                reasons.append("Nearest evidence: " + "; ".join(
                    f"{MEASURE_LABEL.get(r.measure, r.measure)} {fmt(r.o2_pct)}% O2 in {ENV_LABEL.get(r.environment, r.environment)}"
                    f"{_press(r)} ({r.row_id})" for r in nearest) + ".")
            verdicts.append({"level": "grey", **self._level("grey"), "reason": " ".join(reasons),
                             "evidence_ids": [i for i in used]})

        verdicts.sort(key=lambda v: -LEVELS[v["level"]]["rank"])
        caveats = []
        pc = self._pressure_caveat(habitat, used_rows)
        if pc:
            caveats.append(pc)
        caveats += self._general_caveats()
        return {**base, "headline": verdicts[0], "verdicts": verdicts, "evidence": list(used.values()),
                "missing": missing, "caveats": caveats}

    @staticmethod
    def _level(level: str) -> dict:
        return {"emoji": LEVELS[level]["emoji"], "label": LEVELS[level]["label"], "disclaimer": DISCLAIMER}

    def review(self, habitat: Habitat, materials: list[str], th: Thresholds | None = None) -> dict:
        th = th or Thresholds()
        seen: set[str] = set()
        unique = []
        for text in materials:
            k = text.strip().lower()
            if k and k not in seen:
                seen.add(k)
                unique.append(text.strip())
        verdicts = []
        for i, text in enumerate(unique, start=1):
            item = self.assess(text, habitat, th, key=f"m{i}")
            if item["material_id"]:
                item["key"] = item["material_id"] if all(v.get("material_id") != item["material_id"] for v in verdicts) else f"{item['material_id']}_{i}"
            verdicts.append(item)
        return {
            "habitat": {"label": habitat.label, "o2_pct": habitat.o2_pct, "pressure_psia": habitat.pressure_psia,
                        "gravity_g": habitat.gravity_g, "gravity_label": gravity_label(habitat.gravity_g)},
            "thresholds": th.as_dict(),
            "verdicts": verdicts,
            "disclaimer": DISCLAIMER,
        }
