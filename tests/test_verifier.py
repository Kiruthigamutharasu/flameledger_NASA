"""The verifier must pass a faithful explanation and reject wrong numbers, unknown sources and bad wording."""
import json

import pytest

from flameledger.verifier import prose_numbers, verify

EVIDENCE = [
    {"id": "E2", "source_id": "NTRS-20160000593", "o2_pct": 13.6, "pressure_psia": None, "gravity_g": 0},
    {"id": "E3", "source_id": "NTRS-20160000593", "margin_pct_o2": -2.4, "gravity_g": 0},
    {"id": "E15.mylar_g.lunar.moc", "source_id": "NTRS-20130010991", "o2_pct": 14.1, "pressure_psia": 10.2,
     "gravity_g": 0.165},
]
HABITAT = {"o2_pct": 34, "pressure_psia": 8.2, "gravity_g": 0.165}
KEYS = ["pmma_rod", "mylar_g"]


def good(**overrides):
    out = {
        "summary": "PMMA rod burned in microgravity at 13.6% O2, below the habitat's 34% O2.",
        "per_material": [{"material_id": "pmma_rod", "explanation": "Published margin of -2.4% O2 (E3)."}],
        "claims": [
            {"text": "PMMA burned at 13.6% O2", "value": 13.6, "unit": "pct_O2", "source_id": "E2"},
            {"text": "Habitat O2", "value": 34, "unit": "pct_O2", "source_id": "habitat"},
            {"text": "Published margin", "value": -2.4, "unit": "pct_O2", "source_id": "E3"},
        ],
    }
    out.update(overrides)
    return out


def extra_claim(**claim):
    return good(claims=good()["claims"] + [{"text": "x", **claim}])


def test_pass():
    res = verify(good(), EVIDENCE, HABITAT, KEYS)
    assert res.ok, res.errors


def test_pass_from_json_string():
    assert verify(json.dumps(good()), EVIDENCE, HABITAT, KEYS).ok


def test_wrong_number_fails():
    res = verify(good(claims=[{"text": "x", "value": 13.0, "unit": "pct_O2", "source_id": "E2"}]), EVIDENCE, HABITAT, KEYS)
    assert not res.ok and any("does not match" in e for e in res.errors)


def test_number_within_tolerance_passes():
    assert verify(extra_claim(value=13.55, unit="pct_O2", source_id="E2"), EVIDENCE, HABITAT, KEYS).ok


def test_unknown_source_fails():
    res = verify(extra_claim(value=13.6, unit="pct_O2", source_id="NTRS-99999999999"), EVIDENCE, HABITAT, KEYS)
    assert not res.ok and any("not in the evidence given" in e for e in res.errors)


def test_percent_vs_fraction_is_normalised():
    claims = [{"text": "x", "value": 0.136, "unit": "pct_O2", "source_id": "E2"},
              {"text": "h", "value": 0.34, "unit": "pct_O2", "source_id": "habitat"},
              {"text": "m", "value": 2.4, "unit": "pct_O2", "source_id": "E3"}]
    assert verify(good(claims=claims), EVIDENCE, HABITAT, KEYS).ok


def test_percent_is_not_matched_to_a_gravity_value():
    assert not verify(extra_claim(value=16, unit="pct_O2", source_id="E15.mylar_g.lunar.moc"), EVIDENCE, HABITAT, KEYS).ok


def test_unit_mismatch_fails():
    assert not verify(extra_claim(value=13.6, unit="psia", source_id="E2"), EVIDENCE, HABITAT, KEYS).ok


def test_source_id_may_be_the_ntrs_id():
    assert verify(extra_claim(value=13.6, unit="pct_O2", source_id="NTRS-20160000593"), EVIDENCE, HABITAT, KEYS).ok


def test_prose_number_without_claim_fails():
    res = verify(good(summary="PMMA burned at 13.6% O2 and would burn at 11% on the Moon."), EVIDENCE, HABITAT, KEYS)
    assert not res.ok and any("11" in e and "not backed" in e for e in res.errors)


def test_identifiers_are_not_numbers():
    assert prose_numbers("See NTRS 20160000593, E15, Test 3, FM2, 1g and 0g, Table 2, p.5, late 2026.", []) == []
    assert prose_numbers("PMMA 1/4-in rod at 13.6% O2", ["PMMA 1/4-in rod"]) == [13.6]


@pytest.mark.parametrize("summary", [
    "This material is certified for flight.",
    "PMMA is safe at 13.6% O2.",
    "0g and 1g give bounds for lunar gravity.",
    "NASA's Test 1 is wrong.",
])
def test_banned_wording_fails(summary):
    assert not verify(good(summary=summary), EVIDENCE, HABITAT, KEYS).ok


def test_not_certification_is_allowed():
    assert verify(good(summary="Research decision support, not certification. 13.6% O2."), EVIDENCE, HABITAT, KEYS).ok


def test_unknown_material_key_fails():
    bad = good(per_material=[{"material_id": "kapton", "explanation": "No space data."}])
    assert not verify(bad, EVIDENCE, HABITAT, KEYS).ok


def test_word_limits():
    assert not verify(good(summary="word " * 121), EVIDENCE, HABITAT, KEYS).ok
    long = good(per_material=[{"material_id": "pmma_rod", "explanation": "word " * 61}])
    assert not verify(long, EVIDENCE, HABITAT, KEYS).ok


@pytest.mark.parametrize("raw", [None, "not json", {"summary": ""}, {"per_material": []}, []])
def test_malformed_output_fails_closed(raw):
    assert not verify(raw, EVIDENCE, HABITAT, KEYS).ok
