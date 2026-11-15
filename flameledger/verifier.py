"""Check an AI explanation against the evidence it was given. Fail closed.

Rules:
1. The output matches the schema (summary <= 120 words, explanations <= 60 words).
2. Every claim cites an id that was in the evidence given: a row/margin id, its NTRS source id, or "habitat".
3. Every numeric claim matches a value of that evidence within +/-0.1 (percent and fraction are normalised).
4. Every number written in the prose appears among the claim values.
5. No certification language, no "bounds" wording, no statement that NASA's test is wrong.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

TOL = 0.1
HABITAT_ID = "habitat"
SUMMARY_WORDS = 120
EXPLANATION_WORDS = 60


class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(min_length=1, max_length=400)
    value: float | None = None
    unit: Literal["pct_O2", "psia"] | None = None
    source_id: str = Field(min_length=1, max_length=80)


class PerMaterial(BaseModel):
    model_config = ConfigDict(extra="ignore")
    material_id: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=800)


class AIOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str = Field(min_length=1, max_length=1500)
    per_material: list[PerMaterial] = Field(default_factory=list, max_length=20)
    claims: list[Claim] = Field(default_factory=list, max_length=80)


@dataclass
class Verification:
    ok: bool
    errors: list[str] = field(default_factory=list)
    output: AIOutput | None = None


BANNED = [
    (re.compile(r"\bbounds?\b", re.I), "uses 'bounds' wording"),
    (re.compile(r"(?<!not )(?<!no )\bcertif(?:ied|ies|y)\b", re.I), "claims certification"),
    (re.compile(r"\bcertification\b(?<!not certification)", re.I), "mentions certification"),
    (re.compile(r"\b(?:is|are)\s+(?:guaranteed\s+)?safe\b", re.I), "declares a material safe"),
    (re.compile(r"\bguarantee[sd]?\b", re.I), "gives a guarantee"),
    (re.compile(r"\b(?:NASA\S*|tests?|methods?|standards?|screening)\s+(?:[\w-]+\s+){0,4}(?:is|are|was|were)\s+"
                r"(?:\w+\s+)?(?:wrong|flawed|invalid|incorrect|unreliable)\b", re.I), "says a NASA test is wrong"),
]

_NUM = re.compile(r"(?<![A-Za-z0-9./])(?<![A-Za-z0-9]-)[-−]?\d+(?:\.\d+)?(?![A-Za-z0-9/])"
                  r"(?!\.\d)(?!\s?-?\s?(?:cm|mm|in|inch|inches|s|sec|seconds|cm/s)\b)")
_STRIP = [
    re.compile(r"NTRS[-\s]?\d+", re.I),
    re.compile(r"\b(?:19|20)\d{2}\b"),                # years, e.g. "late 2026"
    re.compile(r"\bTest\s*\d\b", re.I),               # FM2 test numbers
    re.compile(r"\b(?:Table|p\.|PDF p\.|page|Eq\.)\s*\(?\d+\)?", re.I),
    re.compile(r"\b\d+\s*(?:of|out of)\s+\d+\b", re.I),  # counts like "3 of 4" are not measurements
]


def _words(text: str) -> int:
    return len(text.split())


def evidence_values(evidence: list[dict], habitat: dict) -> dict[str, dict[str, list[float]]]:
    """{id: {"pct": [...], "psia": [...], "other": [...]}} for every evidence item, its source and the habitat."""
    out: dict[str, dict[str, list[float]]] = {}

    def add(key: str, kind: str, value):
        if value is None:
            return
        slot = out.setdefault(key, {"pct": [], "psia": [], "other": []})
        slot[kind].append(float(value))

    for item in evidence:
        for key in (item["id"], item["source_id"]):
            add(key, "pct", item.get("o2_pct"))
            add(key, "psia", item.get("pressure_psia"))
            add(key, "other", item.get("gravity_g"))
            if item.get("margin_pct_o2") is not None:
                add(key, "pct", item["margin_pct_o2"])
                add(key, "pct", abs(item["margin_pct_o2"]))
            out.setdefault(key, {"pct": [], "psia": [], "other": []})
    add(HABITAT_ID, "pct", habitat.get("o2_pct"))
    add(HABITAT_ID, "psia", habitat.get("pressure_psia"))
    add(HABITAT_ID, "other", habitat.get("gravity_g"))
    return out


def _forms(value: float) -> list[float]:
    """The value itself plus, for a fraction (|v| <= 1), its percent form. Evidence is stored in percent."""
    return [value, value * 100] if 0 < abs(value) <= 1 else [value]


def _matches(value: float, candidates: list[float]) -> bool:
    return any(abs(f - c) <= TOL + 1e-9 for f in _forms(value) for c in candidates)


def prose_numbers(text: str, strip_terms: list[str]) -> list[float]:
    clean = text.replace("−", "-").replace("–", "-").replace("‑", "-")
    for term in sorted({t for t in strip_terms if t}, key=len, reverse=True):
        clean = re.sub(re.escape(term), " ", clean, flags=re.I)
    for pattern in _STRIP:
        clean = pattern.sub(" ", clean)
    return [abs(float(m.group().replace("−", "-"))) for m in _NUM.finditer(clean)]


def verify(raw: dict | str | None, evidence: list[dict], habitat: dict, material_keys: list[str],
           strip_terms: list[str] | None = None) -> Verification:
    errors: list[str] = []
    if raw is None:
        return Verification(False, ["empty response"])
    try:
        out = AIOutput.model_validate_json(raw) if isinstance(raw, str) else AIOutput.model_validate(raw)
    except (ValidationError, ValueError) as exc:
        return Verification(False, [f"output does not match the JSON schema: {str(exc)[:300]}"])

    if _words(out.summary) > SUMMARY_WORDS:
        errors.append(f"summary has {_words(out.summary)} words; the limit is {SUMMARY_WORDS}")
    keys = set(material_keys)
    for pm in out.per_material:
        if pm.material_id not in keys:
            errors.append(f"per_material uses unknown material_id '{pm.material_id}'")
        if _words(pm.explanation) > EXPLANATION_WORDS:
            errors.append(f"explanation for {pm.material_id} has {_words(pm.explanation)} words; the limit is {EXPLANATION_WORDS}")

    values = evidence_values(evidence, habitat)
    claim_values: list[float] = []
    for i, claim in enumerate(out.claims, start=1):
        slot = values.get(claim.source_id)
        if slot is None:
            errors.append(f"claim {i} cites '{claim.source_id}', which is not in the evidence given")
            continue
        if claim.value is None:
            continue
        pool = {"pct_O2": slot["pct"], "psia": slot["psia"], None: slot["pct"] + slot["psia"] + slot["other"]}[claim.unit]
        if not _matches(claim.value, pool):
            errors.append(f"claim {i} value {claim.value:g} ({claim.unit or 'no unit'}) does not match "
                          f"any value of {claim.source_id}")
            continue
        claim_values.extend(abs(f) for f in _forms(claim.value))

    texts = [("summary", out.summary)] + [(f"explanation for {pm.material_id}", pm.explanation) for pm in out.per_material]
    terms = list(strip_terms or [])
    for where, text in texts:
        for n in prose_numbers(text, terms):
            if not _matches(n, claim_values):
                errors.append(f"the number {n:g} in the {where} is not backed by a claim")
        for pattern, why in BANNED:
            if pattern.search(text):
                errors.append(f"the {where} {why}")
    for claim in out.claims:
        for pattern, why in BANNED:
            if pattern.search(claim.text):
                errors.append(f"a claim {why}")

    return Verification(not errors, errors, out)


# ---------- Ask FlameLedger answers ----------
ANSWER_WORDS = 150
_ANY_NUM = re.compile(r"\d+(?:\.\d+)?")


class AnswerClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(min_length=1, max_length=400)
    value: float | None = None
    source_id: str = Field(min_length=1, max_length=80)


class AnswerOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    answer: str = Field(min_length=1, max_length=2000)
    citations: list[str] = Field(default_factory=list, max_length=30)
    claims: list[AnswerClaim] = Field(default_factory=list, max_length=60)


@dataclass
class AnswerVerification:
    ok: bool
    errors: list[str] = field(default_factory=list)
    output: AnswerOutput | None = None


def item_numbers(item: dict) -> list[float]:
    """Every number in a context item's text and numeric fields, plus percent forms of fractions."""
    nums = [float(n) for n in _ANY_NUM.findall(item.get("text", ""))]
    nums += [float(item[k]) for k in ("o2_pct", "pressure_psia", "gravity_g", "margin_pct_o2") if item.get(k) is not None]
    nums += [abs(n) for n in nums]
    return nums + [n * 100 for n in nums if 0 < abs(n) <= 1]


def verify_answer(raw, context: list[dict], strip_terms: list[str] | None = None) -> AnswerVerification:
    """Ask answers: citations and claims must point at the context given; every number must come from it."""
    if raw is None:
        return AnswerVerification(False, ["empty response"])
    try:
        out = AnswerOutput.model_validate_json(raw) if isinstance(raw, str) else AnswerOutput.model_validate(raw)
    except (ValidationError, ValueError) as exc:
        return AnswerVerification(False, [f"output does not match the JSON schema: {str(exc)[:300]}"])
    errors: list[str] = []
    by_id = {c["id"]: c for c in context}
    if _words(out.answer) > ANSWER_WORDS:
        errors.append(f"answer has {_words(out.answer)} words; the limit is {ANSWER_WORDS}")
    for cid in out.citations:
        if cid not in by_id:
            errors.append(f"citation '{cid}' is not one of the context items given")
    claim_values: list[float] = []
    for i, claim in enumerate(out.claims, start=1):
        item = by_id.get(claim.source_id)
        if item is None:
            errors.append(f"claim {i} cites '{claim.source_id}', which is not one of the context items given")
            continue
        if claim.value is None:
            continue
        if not _matches(claim.value, item_numbers(item)):
            errors.append(f"claim {i} value {claim.value:g} does not appear in {claim.source_id}")
            continue
        claim_values.extend(abs(f) for f in _forms(claim.value))
    terms = list(strip_terms or []) + [c.get("title", "") for c in context] + list(by_id)
    for n in prose_numbers(out.answer, terms):
        if not _matches(n, claim_values):
            errors.append(f"the number {n:g} in the answer is not backed by a claim")
    for pattern, why in BANNED:
        if pattern.search(out.answer):
            errors.append(f"the answer {why}")
    if out.claims and not out.citations:
        errors.append("the answer makes claims but cites no context item")
    return AnswerVerification(not errors, errors, out)
