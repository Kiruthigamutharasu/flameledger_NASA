"""Load and validate the hand-verified evidence ledger.

The dataset is loaded once at startup. Any invalid row raises DataError, so a bad
ledger stops the deploy instead of reaching a user. Rows that are not marked
verified=yes are counted but never exposed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

log = logging.getLogger(__name__)

MAX_QUOTE_WORDS = 14  # project rule: quotes stay under 15 words
AGGREGATE = "aggregate"

Environment = Literal["1g", "microgravity", "lunar", "mars", "fm2"]


class DataError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Invalid FlameLedger data:\n- " + "\n- ".join(problems))


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, value, info):
        if isinstance(value, str) and value.strip() == "":
            field = cls.model_fields[info.field_name]
            return None if type(None) in getattr(field.annotation, "__args__", ()) else ""
        return value


class Source(_Row):
    source_id: str = Field(min_length=1)
    short_cite: str = Field(min_length=1)
    title: str
    authors: str
    year: str
    venue: str
    landing_url: str
    pdf_url: str = Field(pattern=r"^https://")


class LedgerRow(_Row):
    row_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    material: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    form: str
    environment: Environment
    facility: str
    gravity_g: float = Field(ge=0, le=1.5)
    o2_pct: float | None = Field(default=None, gt=0, le=100)
    pressure_psia: float | None = Field(default=None, gt=0, le=30)
    flow_regime: str
    flow_note: str
    measure: str = Field(min_length=1)
    value_kind: Literal["limit", "observation", "qualitative", "condition"]
    outcome: Literal["burned", "extinguished", "limit", "planned", "n/a"]
    source_id: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    location: str
    short_quote: str
    verified: Literal["yes", "needs_check"]
    comparability: int | None = Field(default=None, ge=0, le=5)
    caveat: str

    @model_validator(mode="after")
    def _check(self):
        if self.value_kind in ("limit", "observation") and self.o2_pct is None:
            raise ValueError(f"value_kind={self.value_kind} needs an o2_pct value")
        if self.verified == "yes":
            if not self.location or self.location.lower() == "unknown":
                raise ValueError("a verified row needs a page/table location")
            if not self.short_quote:
                raise ValueError("a verified row needs a short quote")
        if len(self.short_quote.split()) > MAX_QUOTE_WORDS:
            raise ValueError(f"short_quote is longer than {MAX_QUOTE_WORDS} words")
        return self


class Margin(_Row):
    margin_id: str = Field(min_length=1)
    evidence_id: str
    material: str
    material_id: str
    environment: Environment
    gravity_g: float = Field(ge=0, le=1.5)
    margin_pct_o2: float = Field(ge=-100, le=100)
    basis: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    location: str = Field(min_length=1)
    short_quote: str = Field(min_length=1)
    verified: Literal["yes", "needs_check"]
    caveat: str

    @model_validator(mode="after")
    def _check(self):
        if len(self.short_quote.split()) > MAX_QUOTE_WORDS:
            raise ValueError(f"short_quote is longer than {MAX_QUOTE_WORDS} words")
        return self


class Preset(_Row):
    preset_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    o2_pct: float = Field(gt=0, le=100)
    pressure_psia: float = Field(gt=0, le=30)
    gravity_g: float = Field(ge=0, le=1.5)
    gravity_label: str
    source_id: str
    source_url: str
    source_note: str = Field(min_length=1)


@dataclass(frozen=True)
class Dataset:
    rows: tuple[LedgerRow, ...]          # verified rows only
    margins: tuple[Margin, ...]          # verified, published margins only
    presets: tuple[Preset, ...]
    sources: tuple[Source, ...]          # only sources cited by a verified row or margin
    hypotheses: dict
    hypotheses_sha256: str
    hidden_rows: int                     # rows held back because they are not verified

    def source(self, source_id: str) -> Source | None:
        return next((s for s in self.sources if s.source_id == source_id), None)

    @property
    def material_rows(self) -> tuple[LedgerRow, ...]:
        return tuple(r for r in self.rows if r.material_id != AGGREGATE)


def _read(path: Path, model: type[_Row], problems: list[str]) -> list:
    if not path.is_file():
        problems.append(f"{path.name}: file is missing")
        return []
    out = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for line_no, raw in enumerate(csv.DictReader(fh), start=2):
            try:
                out.append(model(**raw))
            except (ValidationError, TypeError) as exc:
                detail = "; ".join(
                    f"{'.'.join(str(p) for p in e['loc']) or 'row'}: {e['msg']}" for e in exc.errors()
                ) if isinstance(exc, ValidationError) else str(exc)
                problems.append(f"{path.name} line {line_no}: {detail}")
    return out


def _unique(items: list, attr: str, name: str, problems: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        key = getattr(item, attr)
        if key in seen:
            problems.append(f"{name}: duplicate {attr} '{key}'")
        seen.add(key)


def canonical_hash(payload) -> str:
    """SHA-256 of canonical JSON, so the hash does not depend on line endings or key order."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_dataset(data_dir: Path) -> Dataset:
    data_dir = Path(data_dir)
    problems: list[str] = []
    sources = _read(data_dir / "sources.csv", Source, problems)
    rows = _read(data_dir / "ledger.csv", LedgerRow, problems)
    margins = _read(data_dir / "margins.csv", Margin, problems)
    presets = _read(data_dir / "presets.csv", Preset, problems)

    _unique(sources, "source_id", "sources.csv", problems)
    _unique(rows, "row_id", "ledger.csv", problems)
    _unique(margins, "margin_id", "margins.csv", problems)
    _unique(presets, "preset_id", "presets.csv", problems)

    by_id = {s.source_id: s for s in sources}
    for item, name, key in [(r, "ledger.csv", r.row_id) for r in rows] + [(m, "margins.csv", m.margin_id) for m in margins]:
        src = by_id.get(item.source_id)
        if src is None:
            problems.append(f"{name} {key}: unknown source_id '{item.source_id}'")
        elif item.source_url != src.pdf_url:
            problems.append(f"{name} {key}: source_url does not match sources.csv for {item.source_id}")

    hypotheses: dict = {}
    hyp_path = data_dir / "hypotheses.json"
    try:
        hypotheses = json.loads(hyp_path.read_text(encoding="utf-8"))
        if not hypotheses.get("hypotheses") or not hypotheses.get("registered_on"):
            problems.append("hypotheses.json: needs 'registered_on' and a non-empty 'hypotheses' list")
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"hypotheses.json: {exc}")

    verified_rows = tuple(r for r in rows if r.verified == "yes")
    verified_margins = tuple(m for m in margins if m.verified == "yes")
    known_evidence = {r.evidence_id for r in verified_rows} | {m.evidence_id for m in verified_margins}
    for hyp in hypotheses.get("hypotheses", []):
        for ev in hyp.get("evidence_ids", []):
            if ev not in known_evidence:
                problems.append(f"hypotheses.json {hyp.get('id')}: cites {ev}, which is not verified evidence")
    if not verified_rows:
        problems.append("ledger.csv: no verified rows")

    if problems:
        raise DataError(problems)

    cited = {r.source_id for r in verified_rows} | {m.source_id for m in verified_margins}
    hidden = len(rows) - len(verified_rows)
    log.info("Ledger loaded: %d verified rows, %d hidden, %d margins, %d presets",
             len(verified_rows), hidden, len(verified_margins), len(presets))
    return Dataset(
        rows=verified_rows,
        margins=verified_margins,
        presets=tuple(presets),
        sources=tuple(s for s in sources if s.source_id in cited),
        hypotheses=hypotheses,
        hypotheses_sha256=canonical_hash(hypotheses.get("hypotheses", [])),
        hidden_rows=hidden,
    )
