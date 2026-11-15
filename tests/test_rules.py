"""Deterministic verdicts: each colour, aliases, caveats, and no computed margins."""
from pathlib import Path

import pytest

from flameledger.data import load_dataset
from flameledger.rules import DISCLAIMER, THRESHOLD_LABEL, Habitat, RulesEngine, Thresholds, match_material

DATA = Path(__file__).resolve().parent.parent / "data"
LUNAR = Habitat(34, 8.2, 0.165)
ISS = Habitat(21, 14.7, 0)


@pytest.fixture(scope="module")
def engine():
    return RulesEngine(load_dataset(DATA))


def one(engine, text, habitat, th=None):
    return engine.review(habitat, [text], th)["verdicts"][0]


def levels(item):
    return [v["level"] for v in item["verdicts"]]


@pytest.mark.parametrize("text,expected", [
    ("PMMA rod", "pmma_rod"), ("acrylic sheet", "pmma_rod"), ("Plexiglas window", "pmma_rod"),
    ("cotton-fiberglass fabric", "sibal_fabric"), ("SIBAL", "sibal_fabric"),
    ("silicone", "silicone_mq"), ("MQ rubber", "silicone_mq"), ("Synergy Pro Navy fabric", "synergy_pro_navy"),
    ("Mylar G", "mylar_g"), ("ultem 1000", "ultem_1000"), ("Nomex HT90-40", "nomex_ht90_40"),
    ("Kapton", None), ("", None), ("cotton", None), ("mqx", None),
    ("polyimide film", "polyimide_pi"), ("PEEK bracket", "peek"), ("nitrile seal", "nbr"), ("PVC hose", "pvc_sheet"),
    ("Delrin knob", "pom_rod"), ("polypropylene bag", "pp_rod"), ("Nylon strap", "nylon_rod"),
    ("epoxy/glass board", "epoxy_glass"), ("Nomex HT90-40 fabric", "nomex_ht90_40"), ("pipe", None),
])
def test_match_material(text, expected):
    assert match_material(text) == expected


def test_new_1g_only_materials_are_grey_with_nearest_evidence(engine):
    item = one(engine, "Delrin", LUNAR)
    assert item["material_id"] == "pom_rod" and levels(item) == ["grey"]
    assert "12.9% O2" in item["headline"]["reason"] and "E19.pom.uloi" in item["headline"]["reason"]


def test_red_and_orange_for_pmma(engine):
    item = one(engine, "PMMA rod", LUNAR)
    assert levels(item) == ["red", "orange"] and item["headline"]["level"] == "red"
    assert "E2" in item["verdicts"][0]["evidence_ids"] and "13.6% O2" in item["verdicts"][0]["reason"]
    assert item["verdicts"][1]["evidence_ids"] == ["E3"] and "-2.4% O2" in item["verdicts"][1]["reason"]


def test_red_needs_burn_at_or_below_habitat_o2(engine):
    item = one(engine, "PMMA rod", Habitat(13, 14.7, 0))  # below the 13.6% microgravity burn
    assert "red" not in levels(item)


def test_green_at_matching_gravity(engine):
    item = one(engine, "Ultem", ISS, Thresholds(thin_margin_pct_o2=0.0))
    assert item["headline"]["level"] == "green"
    assert item["verdicts"][0]["evidence_ids"] == ["E15.ultem_1000.0g.moc"]


def test_green_listed_below_orange_with_default_thin_threshold(engine):
    assert levels(one(engine, "Ultem", ISS)) == ["orange", "green"]


def test_grey_for_sibal_has_the_qualitative_note(engine):
    item = one(engine, "cotton-fiberglass fabric", LUNAR)
    assert levels(item) == ["grey"]
    assert ("Burned in microgravity (qualitative); O2 not in ledger, cannot compare to this habitat."
            in item["headline"]["reason"])


def test_grey_for_silicone_shows_nearest_evidence_and_gaps(engine):
    item = one(engine, "silicone", LUNAR)
    assert levels(item) == ["grey"] and "Nearest evidence" in item["headline"]["reason"]
    assert any("lunar gravity" in m for m in item["missing"])


def test_grey_for_fm2_fabric_mentions_planned_tests(engine):
    item = one(engine, "Synergy Pro Navy fabric", LUNAR)
    assert levels(item) == ["grey"] and "No result exists yet" in item["headline"]["reason"]
    assert any("FM2 plans the first long-duration" in m for m in item["missing"])


def test_unknown_material_is_grey_and_unknown(engine):
    item = one(engine, "Kapton", LUNAR)
    assert item["material_id"] is None and levels(item) == ["grey"] and item["evidence"] == []
    assert "unknown" in item["headline"]["reason"]


def test_every_verdict_has_disclaimer_and_caveats(engine):
    review = engine.review(LUNAR, ["PMMA rod", "silicone", "Kapton", "Mylar"])
    assert review["disclaimer"] == DISCLAIMER and review["thresholds"]["label"] == THRESHOLD_LABEL
    for item in review["verdicts"]:
        assert all(v["disclaimer"] == DISCLAIMER for v in item["verdicts"])
        texts = " ".join(c["text"] for c in item["caveats"])
        assert "not cabin ventilation" in texts and "partial-gravity" in texts


def test_pressure_caveat(engine):
    item = one(engine, "Mylar", LUNAR)  # the Mylar tests were at 10.2 psia
    assert any("differs from the test pressure" in c["text"] for c in item["caveats"])


def test_duplicates_are_merged_and_keys_unique(engine):
    review = engine.review(LUNAR, ["PMMA rod", "pmma rod", "acrylic", "Kapton", "Teflon"])
    keys = [v["key"] for v in review["verdicts"]]
    assert len(review["verdicts"]) == 4 and len(set(keys)) == 4


def test_only_published_margins_appear(engine):
    """Reasons may cite margins only from margins.csv, never a difference of two rows (e.g. 14.0 - 13.6)."""
    published = {m.margin_id for m in load_dataset(DATA).margins}
    review = engine.review(ISS, ["PMMA rod", "Mylar", "Ultem", "Nomex", "silicone", "SIBAL"])
    for item in review["verdicts"]:
        for e in item["evidence"]:
            if e["kind"] == "margin":
                assert e["id"] in published
        assert "0.4%" not in " ".join(v["reason"] for v in item["verdicts"])
