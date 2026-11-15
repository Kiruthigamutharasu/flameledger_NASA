"""Markdown report of a Habitat Review: habitat, verdicts, explanations, sources, limitations."""
from __future__ import annotations

import re

from .data import Dataset
from .rules import DISCLAIMER as VERDICT_DISCLAIMER

LIMITATIONS = [
    "The ledger is small and hand-verified. A material that is missing has no verified evidence here; that does not mean it is safe.",
    "Only margins published by the original NASA authors are shown. FlameLedger never computes a margin.",
    "Lunar and Mars values come from short drop-tower tests; their limit criteria differ from the 1g test criteria.",
    "Test-duct and burner flows are not cabin ventilation.",
    "FlameLedger makes no numeric prediction for lunar or Mars gravity. FM2 is planned to give the first long-duration lunar-gravity data.",
    "Verdict thresholds are FlameLedger research thresholds, not NASA criteria.",
]


def _md(text) -> str:
    """Neutralise user or model text for a Markdown table cell or paragraph."""
    s = "" if text is None else str(text)
    s = re.sub(r"[\r\n]+", " ", s)
    return re.sub(r"([\\`*_\[\]<>|#])", r"\\\1", s).strip()


def _num(v) -> str:
    return "n/a" if v is None else f"{v:g}"


def build_report(review: dict, ai: dict | None, ai_status: str, ai_note: str, dataset: Dataset,
                 disclaimer: str, generated: str, commit: str) -> str:
    h = review["habitat"]
    th = review["thresholds"]
    out: list[str] = [
        "# FlameLedger Habitat Review",
        "",
        f"**{VERDICT_DISCLAIMER}**",
        "",
        f"Generated {generated} (UTC) · commit `{commit[:12]}`",
        "",
        "## Habitat",
        "",
        "| O2 (%) | Pressure (psia) | Gravity (g) | Environment |",
        "|---|---|---|---|",
        f"| {_num(h['o2_pct'])} | {_num(h['pressure_psia'])} | {_num(h['gravity_g'])} | {_md(h['gravity_label'])} |",
        "",
        f"Thresholds ({_md(th['label'])}): a reduced-gravity burn at up to habitat O2 + "
        f"{_num(th['red_o2_tolerance_pct'])} % O2 is red; a published margin below "
        f"{_num(th['thin_margin_pct_o2'])} % O2 is thin.",
        "",
        "## Verdicts",
        "",
        "| Material (as entered) | Ledger material | Headline | All verdicts |",
        "|---|---|---|---|",
    ]
    for v in review["verdicts"]:
        allv = "; ".join(f"{x['emoji']} {x['label']}" for x in v["verdicts"])
        out.append(f"| {_md(v['input'])} | {_md(v['material'] or 'not in ledger')} | "
                   f"{v['headline']['emoji']} {_md(v['headline']['label'])} | {_md(allv)} |")
    out.append("")

    explanations = {pm["material_id"]: pm["explanation"] for pm in (ai or {}).get("per_material", [])}
    cited: set[str] = set()
    for v in review["verdicts"]:
        out += [f"### {_md(v['input'])}", ""]
        for x in v["verdicts"]:
            out.append(f"- {x['emoji']} **{_md(x['label'])}**: {_md(x['reason'])}")
        if v["missing"]:
            out.append("- Missing evidence: " + " ".join(_md(m) for m in v["missing"]))
        if v["key"] in explanations:
            out.append(f"- AI explanation (verified): {_md(explanations[v['key']])}")
        if v["evidence"]:
            out += ["", "Evidence used:", ""]
            for e in v["evidence"]:
                cited.add(e["source_id"])
                value = (f"{_num(e['margin_pct_o2'])} % O2 published margin" if e["kind"] == "margin"
                         else f"{_num(e.get('o2_pct'))} % O2" if e.get("o2_pct") is not None else e.get("outcome", ""))
                out.append(f"- {_md(e['id'])}: {_md(e['material'])}, {_md(e['environment'])}, {_md(value)}. "
                           f"[{_md(e['source_id'])}, {_md(e['location'])}]({e['source_url']}). "
                           f"\"{_md(e['short_quote'])}\". {_md(e['caveat'])}")
        out += ["", "Caveats:", ""]
        for c in v["caveats"]:
            src = c.get("source")
            if src:
                cited.add(src["source_id"])
                out.append(f"- {_md(c['text'])} [{_md(src['source_id'])}, {_md(src['location'])}]({src['source_url']})")
            else:
                out.append(f"- {_md(c['text'])}")
        out.append("")

    out += ["## AI explanation", ""]
    if ai:
        out += [f"Status: verified. {_md(ai_note)}", "", _md(ai["summary"]), ""]
    else:
        out += [f"Status: {_md(ai_status)}. {_md(ai_note)} The deterministic verdicts above are complete without it.", ""]

    out += ["## Sources", ""]
    for sid in sorted(cited):
        src = dataset.source(sid)
        if src:
            out.append(f"- {_md(src.short_cite)}. *{_md(src.title)}*. {_md(src.venue)}. {src.landing_url or src.pdf_url}")
    out += ["", "## Limitations", ""] + [f"- {x}" for x in LIMITATIONS]
    out += ["", "---", "", disclaimer, ""]
    return "\n".join(out)
