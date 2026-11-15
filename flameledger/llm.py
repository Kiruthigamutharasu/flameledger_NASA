"""Optional Gemini explanation of the deterministic verdicts.

The LLM never decides a verdict. It only explains the verdict table, using the evidence
rows it is given, and its output must pass verifier.verify before it is shown.
Any failure (no key, timeout, bad JSON, failed verification) returns ai=None and the
page shows the deterministic result. Nothing here raises to the caller.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from .config import Settings
from .data import canonical_hash
from .verifier import EXPLANATION_WORDS, HABITAT_ID, SUMMARY_WORDS, verify

log = logging.getLogger(__name__)

CALL_TIMEOUT_S = 30
TOTAL_BUDGET_S = 55
TEMPERATURE = 0.2
CACHE_SIZE = 256

# status values returned to the client
VERIFIED = "verified"
FAILED_VERIFICATION = "failed_verification"
UNAVAILABLE = "unavailable"
NOT_CONFIGURED = "not_configured"

SYSTEM_INSTRUCTION = f"""You explain fire-safety verdicts for spacecraft materials to engineers and students.
Rules you must follow:
- Use ONLY the habitat, the verdict table and the evidence items provided. Do not use outside knowledge.
- Every number you write must come from the provided evidence or the habitat. Add each one to "claims" with
  its exact value, its unit ("pct_O2", "psia" or null) and the "source_id" of the evidence item it came from
  (use the item's "id", or "{HABITAT_ID}" for a habitat value).
- Do not change, re-rank or second-guess any verdict. The verdicts are decided by deterministic rules.
- Never compute a new margin, difference or prediction. Never give a numeric prediction for lunar or Mars gravity.
- If a material has no space data, say "No space data" and what test is missing.
- Never claim certification or that a material is safe. Never say NASA's tests are wrong. Never use the word "bounds".
- Summary: at most {SUMMARY_WORDS} words. Each per-material explanation: at most {EXPLANATION_WORDS} words.
Writing style:
- Plain English for an engineer. Complete sentences; never end mid-word.
- Write oxygen as "13.6% O2" and pressure as "8.2 psia". Never write field names such as pct_O2 or o2_pct in prose.
- For each material, start with its "headline" verdict (the first, highest-ranked one) and the evidence behind
  it (the key number and the environment it was measured in). Mention lower-ranked verdicts after it, then the
  most important gap. Do not just list every missing environment.
- Say once, in the summary only, that test-duct flow is not cabin ventilation.
- The summary first names only the materials whose headline is "red" or "orange" as concerns, with the key
  number for each. Grey materials are evidence gaps, not hazards: say they lack comparable space data and
  what testing would close the gap. If no headline is red or orange, say so plainly.
Return JSON only, with exactly this shape:
{{"summary": str, "per_material": [{{"material_id": str, "explanation": str}}],
  "claims": [{{"text": str, "value": number|null, "unit": "pct_O2"|"psia"|null, "source_id": str}}]}}
Use the verdict table's "material_id" values for per_material."""


@dataclass(frozen=True)
class AIResult:
    ai: dict | None
    status: str
    note: str


Transport = Callable[[str, str, float], str]  # (system, prompt, timeout_s) -> raw JSON text


def _verdict_table(review: dict) -> list[dict]:
    return [{"material_id": v["key"], "input": v["input"], "ledger_material": v["material"],
             "headline": v["headline"]["level"],
             "verdicts": [{"level": x["level"], "label": x["label"], "reason": x["reason"]} for x in v["verdicts"]],
             "missing": v["missing"]} for v in review["verdicts"]]


def _evidence(review: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for v in review["verdicts"]:
        for e in v["evidence"]:
            seen.setdefault(e["id"], e)
    return list(seen.values())


def _strip_terms(review: dict, evidence: list[dict]) -> list[str]:
    terms = []
    for v in review["verdicts"]:
        terms += [v["input"], v["material"] or ""]
    for e in evidence:
        terms += [e["id"], e.get("material", ""), e.get("evidence_id", ""), e.get("location", "")]
    return terms


class Explainer:
    def __init__(self, settings: Settings, transport: Transport | None = None):
        self._settings = settings
        self._transport = transport
        self._client = None
        self._client_lock = threading.Lock()
        self._cache: OrderedDict[str, AIResult] = OrderedDict()
        self._cache_lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._transport is not None or self._settings.ai_enabled

    # ---------- Gemini transport ----------
    def _gemini(self, system: str, prompt: str, timeout_s: float) -> str:
        from google import genai  # imported lazily so the app starts even if the SDK is broken
        from google.genai import types

        with self._client_lock:
            if self._client is None:
                self._client = genai.Client(api_key=self._settings.gemini_api_key)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=TEMPERATURE,
            response_mime_type="application/json",
            max_output_tokens=2048,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )
        resp = self._client.models.generate_content(model=self._settings.gemini_model, contents=prompt, config=config)
        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("empty response from the model")
        return text

    def _call(self, system: str, prompt: str, deadline: float) -> str | None:
        """One call plus one retry on a transport error, within the overall time budget."""
        transport = self._transport or self._gemini
        for attempt in (1, 2):
            remaining = deadline - time.monotonic()
            if remaining < 3:
                return None
            try:
                return transport(system, prompt, min(CALL_TIMEOUT_S, remaining))
            except Exception as exc:  # noqa: BLE001 - any SDK/network failure is non-fatal by design
                log.warning("AI call attempt %d failed: %s", attempt, type(exc).__name__)
        return None

    # ---------- public ----------
    def explain(self, review: dict, cache_only: bool = False) -> AIResult:
        if not self.enabled:
            return AIResult(None, NOT_CONFIGURED, "AI explanation is not configured on this server.")
        try:
            return self._explain(review, cache_only)
        except Exception:  # noqa: BLE001 - the page must never error because of the AI layer
            log.exception("AI explanation failed unexpectedly")
            return AIResult(None, UNAVAILABLE, "AI explanation unavailable (service error).")

    def _explain(self, review: dict, cache_only: bool) -> AIResult:
        evidence = _evidence(review)
        habitat = review["habitat"]
        payload = {"habitat": {"id": HABITAT_ID, **{k: habitat[k] for k in ("o2_pct", "pressure_psia", "gravity_g", "gravity_label")}},
                   "verdict_table": _verdict_table(review),
                   "evidence": [{k: v for k, v in e.items() if k not in ("source_url", "short_quote")} for e in evidence]}
        key = canonical_hash({"payload": payload, "model": self._settings.gemini_model})
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        if cache_only:
            return AIResult(None, UNAVAILABLE, "AI explanation not generated for this exact input yet.")

        keys = [v["key"] for v in review["verdicts"]]
        terms = _strip_terms(review, evidence)
        prompt = "Explain these verdicts.\n" + json.dumps(payload, ensure_ascii=False)
        deadline = time.monotonic() + TOTAL_BUDGET_S

        raw = self._call(SYSTEM_INSTRUCTION, prompt, deadline)
        if raw is None:
            return AIResult(None, UNAVAILABLE, "AI explanation unavailable (the AI service did not respond).")
        result = verify(_loads(raw), evidence, habitat, keys, terms)
        if not result.ok:
            log.info("AI output failed verification (%d errors); retrying once", len(result.errors))
            retry_prompt = (prompt + "\n\nYour previous answer failed verification for these reasons:\n- "
                            + "\n- ".join(result.errors[:15]) + "\nReturn corrected JSON only.")
            raw = self._call(SYSTEM_INSTRUCTION, retry_prompt, deadline)
            result = verify(_loads(raw), evidence, habitat, keys, terms) if raw is not None else result

        if result.ok and result.output is not None:
            out = AIResult(result.output.model_dump(), VERIFIED, "AI explanation verified against the evidence rows.")
        else:
            log.info("AI output failed verification after retry: %s", "; ".join(result.errors[:5]))
            out = AIResult(None, FAILED_VERIFICATION, "AI explanation unavailable (failed verification).")
        with self._cache_lock:
            self._cache[key] = out
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return out


def _loads(raw: str | None):
    if raw is None:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text  # verify() reports the schema error
