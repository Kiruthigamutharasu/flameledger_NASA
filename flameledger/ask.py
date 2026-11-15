"""Ask FlameLedger: questions answered only from the investigation catalogue and the verified ledger.

1. retrieve: keyword search (with a few domain synonyms) picks the most relevant context items;
2. Gemini answers in JSON, citing context item ids and listing every number as a claim;
3. verifier.verify_answer checks citations, claim values and prose numbers; one retry with the errors;
4. without AI, or if verification fails, the user still gets the ranked evidence with sources.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import OrderedDict

from .data import AGGREGATE, Dataset, canonical_hash
from .investigations import NOT_SUMMARISED, Catalogue
from .llm import (CACHE_SIZE, FAILED_VERIFICATION, NOT_CONFIGURED, TOTAL_BUDGET_S, UNAVAILABLE, VERIFIED,
                  Explainer, _loads)
from .verifier import ANSWER_WORDS, verify_answer

log = logging.getLogger(__name__)

MAX_INVESTIGATIONS = 6
MAX_ROWS = 6
STOP = {"the", "and", "for", "with", "what", "which", "how", "does", "did", "are", "was", "were", "from",
        "that", "this", "about", "into", "have", "has", "can", "could", "would", "should", "there", "their",
        "any", "all", "most", "more", "less", "than", "when", "where", "who", "why", "tell", "show", "give",
        "list", "data", "nasa", "test", "tests", "tested", "experiment", "experiments", "investigation",
        "investigations", "study", "studies", "space", "you", "our", "use", "used", "using", "between"}
SYNONYMS = {
    "moon": ["lunar"], "lunar": ["moon", "partial"], "mars": ["martian", "partial"], "martian": ["mars"],
    "smoke": ["detection", "detector", "particle"], "detect": ["detection", "detector", "smoke"],
    "detector": ["detection", "smoke"], "detectors": ["detection", "smoke"],
    "extinguish": ["suppression", "suppressant", "extinction"], "extinguisher": ["suppression", "mist"],
    "suppress": ["suppression", "suppressant"], "suppressant": ["suppression"],
    "fabric": ["cotton", "sibal", "nomex", "textile"], "cloth": ["fabric", "cotton"],
    "plastic": ["pmma", "acrylic", "polymer"], "acrylic": ["pmma"], "plexiglas": ["pmma"],
    "oxygen": ["o2", "atmosphere"], "o2": ["oxygen"], "airflow": ["flow", "ventilation"],
    "ventilation": ["flow", "airflow"], "droplet": ["droplets", "liquid"], "liquid": ["droplet", "droplets"],
    "gravity": ["microgravity", "partial"], "earth": ["terrestrial", "earth_application"],
    "habitat": ["atmosphere", "lunar"], "rover": ["lunar", "atmosphere"], "soot": ["sooty", "smoke"],
}
SYSTEM_INSTRUCTION = f"""You answer questions about spacecraft fire safety for researchers, students and engineers.
Rules you must follow:
- Use ONLY the context items provided. Do not use outside knowledge. If the context does not answer the
  question, say plainly that the FlameLedger catalogue and ledger do not cover it.
- Cite the "id" of every context item you rely on in "citations".
- Every number you write must appear in a cited context item. Add each one to "claims" with its exact value
  and the "id" of the item it came from as "source_id".
- Never compute new margins, differences or predictions. Never give a numeric prediction for lunar or Mars gravity.
- Never claim certification or that a material is safe. Never say NASA's tests are wrong. Never use the word "bounds".
- If the context says "Not yet summarised" for something, say it is not summarised yet.
- Plain English, complete sentences, at most {ANSWER_WORDS} words.
Return JSON only, with exactly this shape:
{{"answer": str, "citations": [str], "claims": [{{"text": str, "value": number|null, "source_id": str}}]}}"""


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9\-*]*", text.lower())
    out: list[str] = []
    for w in words:
        if w in STOP or (len(w) < 3 and w not in ("o2", "1g", "0g")):
            continue
        out.append(w)
        out.extend(SYNONYMS.get(w, []))
    return list(dict.fromkeys(out))


def build_index(cat: Catalogue, ds: Dataset) -> list[dict]:
    items: list[dict] = []
    for inv in cat.investigations:
        cite = inv.sources[0]
        src = cat.source(cite.source_id)
        parts = [inv.objective, f"Fuels: {inv.fuels}", f"Conditions: {inv.conditions}",
                 f"Measurements: {inv.measurements}", f"Hardware: {inv.hardware}", f"Status: {inv.status}"]
        parts += [f"{cat.flags[f]}: {note}" for f, note in inv.flags.items()]
        if inv.earth_application:
            parts.append(f"Earth application: {inv.earth_application}")
        text = " ".join(p for p in parts if NOT_SUMMARISED not in p)
        items.append({"id": f"inv:{inv.id}", "kind": "investigation", "title": f"{inv.acronym}: {inv.name}",
                      "text": text, "keys": f"{inv.acronym} {inv.name} {inv.project} {' '.join(inv.areas)} {inv.fuel_type}",
                      "source_id": cite.source_id, "url": src.url if src else "", "location": cite.location})
    for r in ds.rows:
        bits = [f"{r.material}, {r.environment}", f"{r.measure.replace('_', ' ')}"]
        if r.o2_pct is not None:
            bits.append(f"{r.o2_pct:g}% O2")
        if r.pressure_psia is not None:
            bits.append(f"{r.pressure_psia:g} psia")
        bits += [f"outcome {r.outcome}", r.facility, r.flow_note, f"Quote: {r.short_quote}", r.caveat]
        items.append({"id": r.row_id, "kind": "ledger_row", "title": f"{r.material} ({r.environment})",
                      "text": ". ".join(bits), "keys": f"{r.material} {r.material_id} {r.environment} {r.measure}",
                      "o2_pct": r.o2_pct, "pressure_psia": r.pressure_psia, "gravity_g": r.gravity_g,
                      "source_id": r.source_id, "url": r.source_url, "location": r.location,
                      "aggregate": r.material_id == AGGREGATE})
    for m in ds.margins:
        items.append({"id": m.margin_id, "kind": "margin", "title": f"{m.material} published margin ({m.environment})",
                      "text": f"Published oxygen margin of {m.margin_pct_o2:g}% O2 in {m.environment}. {m.basis}. {m.caveat}",
                      "keys": f"{m.material} {m.material_id} {m.environment} margin", "margin_pct_o2": m.margin_pct_o2,
                      "gravity_g": m.gravity_g, "source_id": m.source_id, "url": m.source_url, "location": m.location})
    for it in items:
        it["_bag"] = " ".join([it["title"], it["keys"], it["text"]]).lower()
    return items


def retrieve(index: list[dict], question: str) -> list[dict]:
    toks = _tokens(question)
    if not toks:
        return []
    scored = []
    for it in index:
        bag = it["_bag"]
        score = 0.0
        for t in toks:
            if re.search(r"(?<![a-z0-9])" + re.escape(t), bag):
                score += 3 if t in it["keys"].lower() or t in it["title"].lower() else 1
        if score:
            scored.append((score, it))
    if not scored:
        return []
    scored.sort(key=lambda s: -s[0])
    floor = max(1.0, scored[0][0] * 0.25)  # drop weak, incidental matches
    kept = [it for s, it in scored if s >= floor]
    invs = [it for it in kept if it["kind"] == "investigation"][:MAX_INVESTIGATIONS]
    rows = [it for it in kept if it["kind"] != "investigation"][:MAX_ROWS]
    return invs + rows


def _public(it: dict) -> dict:
    return {k: it[k] for k in ("id", "kind", "title", "source_id", "url", "location")} | {"snippet": it["text"][:280]}


class Asker:
    def __init__(self, cat: Catalogue, ds: Dataset, explainer: Explainer):
        self.index = build_index(cat, ds)
        self.explainer = explainer
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    def ask(self, question: str) -> dict:
        question = re.sub(r"\s+", " ", question).strip()
        context = retrieve(self.index, question)
        base = {"question": question, "evidence": [_public(c) for c in context]}
        if not context:
            return {**base, "answer": None, "citations": [], "ai_status": "no_match",
                    "ai_note": "Nothing in the FlameLedger catalogue or ledger matches this question. Try naming a "
                               "material, an investigation (for example BASS, FLEX or SAME), an environment or a topic."}
        if not self.explainer.enabled:
            return {**base, "answer": None, "citations": [], "ai_status": NOT_CONFIGURED,
                    "ai_note": "AI answers are not configured on this server. The most relevant sourced evidence is listed."}
        try:
            return {**base, **self._answer(question, context)}
        except Exception:  # noqa: BLE001 - the page must never error because of the AI layer
            log.exception("Ask failed unexpectedly")
            return {**base, "answer": None, "citations": [], "ai_status": UNAVAILABLE,
                    "ai_note": "AI answer unavailable (service error). The most relevant sourced evidence is listed."}

    def _answer(self, question: str, context: list[dict]) -> dict:
        payload = {"question": question,
                   "context": [{k: c[k] for k in ("id", "kind", "title", "text")} for c in context]}
        key = canonical_hash({"p": payload, "m": self.explainer._settings.gemini_model})
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        prompt = "Answer the question from the context.\n" + json.dumps(payload, ensure_ascii=False)
        deadline = time.monotonic() + TOTAL_BUDGET_S
        raw = self.explainer._call(SYSTEM_INSTRUCTION, prompt, deadline)
        if raw is None:
            return {"answer": None, "citations": [], "ai_status": UNAVAILABLE,
                    "ai_note": "AI answer unavailable (the AI service did not respond). The most relevant sourced evidence is listed."}
        res = verify_answer(_loads(raw), context)
        if not res.ok:
            log.info("Ask answer failed verification (%d errors); retrying once", len(res.errors))
            retry = (prompt + "\n\nYour previous answer failed verification for these reasons:\n- "
                     + "\n- ".join(res.errors[:15]) + "\nReturn corrected JSON only.")
            raw = self.explainer._call(SYSTEM_INSTRUCTION, retry, deadline)
            res = verify_answer(_loads(raw), context) if raw is not None else res
        if res.ok and res.output is not None:
            by_id = {c["id"]: c for c in context}
            out = {"answer": res.output.answer,
                   "citations": [_public(by_id[c]) for c in dict.fromkeys(res.output.citations)],
                   "claims": [c.model_dump() for c in res.output.claims],
                   "ai_status": VERIFIED, "ai_note": "Every number and citation was checked against the evidence shown."}
        else:
            out = {"answer": None, "citations": [], "ai_status": FAILED_VERIFICATION,
                   "ai_note": "AI answer unavailable (failed verification). The most relevant sourced evidence is listed."}
        with self._lock:
            self._cache[key] = out
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return out
