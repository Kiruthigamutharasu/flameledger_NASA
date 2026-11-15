"""The ledger must load cleanly, and bad data must stop the app from starting."""
import csv
import shutil
from pathlib import Path

import pytest

from flameledger.data import MAX_QUOTE_WORDS, DataError, load_dataset

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def ds():
    return load_dataset(DATA)


def _edit(tmp_path: Path, filename: str, row_key: str, row_id: str, changes: dict) -> Path:
    """Copy data/ to a temp folder and change one row."""
    target = tmp_path / "data"
    shutil.copytree(DATA, target)
    path = target / filename
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    hit = [r for r in rows if r[row_key] == row_id]
    assert hit, f"{row_id} not found in {filename}"
    hit[0].update(changes)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return target


def test_loads_and_hides_unverified(ds):
    assert len(ds.rows) >= 40
    assert all(r.verified == "yes" for r in ds.rows)
    assert ds.hidden_rows == 1
    assert "E14" not in {r.row_id for r in ds.rows}
    assert "SAFFIRE-PRELIM" not in {s.source_id for s in ds.sources}


def test_every_row_is_sourced(ds):
    known = {s.source_id for s in ds.sources}
    for item in (*ds.rows, *ds.margins):
        assert item.source_id in known
        assert item.source_url.startswith("https://ntrs.nasa.gov/")
        assert item.location and item.short_quote
        assert len(item.short_quote.split()) <= MAX_QUOTE_WORDS


def test_value_ranges(ds):
    for r in ds.rows:
        assert r.o2_pct is None or 0 < r.o2_pct <= 100
        assert r.pressure_psia is None or r.pressure_psia > 0
        if r.value_kind in ("limit", "observation"):
            assert r.o2_pct is not None


def test_seed_values_match_the_audit(ds):
    by_id = {r.row_id: r for r in ds.rows}
    assert by_id["E1"].o2_pct == 16 and by_id["E2"].o2_pct == 13.6
    assert (by_id["E4.uloi"].o2_pct, by_id["E4.moc"].o2_pct) == (19.5, 19.0)
    assert (by_id["E5.uloi"].o2_pct, by_id["E5.moc"].o2_pct) == (18.9, 18.0)
    assert (by_id["E6.uloi"].o2_pct, by_id["E6.moc"].o2_pct) == (15.7, 14.0)
    assert (by_id["E7.chem.uloi"].o2_pct, by_id["E7.chem.moc"].o2_pct) == (23.4, 22.0)
    assert (by_id["E7.wire.uloi"].o2_pct, by_id["E7.wire.moc"].o2_pct) == (22.5, 21.0)
    assert by_id["E15.mylar_g.lunar.moc"].o2_pct == 14.1
    e19 = {r.row_id: r.o2_pct for r in ds.rows if r.evidence_id == "E19"}
    assert e19 == {  # NTRS 20110008636, Tables 2, 5, 8, 9 (checked against the PDF text)
        "E19.pi.chem.uloi": 27.2, "E19.pi.chem.moc": 26.0, "E19.pi.wire.uloi": 28.7, "E19.pi.wire.moc": 27.0,
        "E19.peek.chem.uloi": 20.8, "E19.peek.chem.moc": 20.1, "E19.peek.wire.uloi": 22.0, "E19.peek.wire.moc": 21.1,
        "E19.nbr.uloi": 16.6, "E19.nbr.moc": 16.1, "E19.pvc.uloi": 40.1, "E19.pvc.moc": 35.0,
        "E19.pom.uloi": 12.9, "E19.pom.moc": 12.0, "E19.pp.uloi": 17.6, "E19.pp.moc": 16.0,
        "E19.pa.uloi": 21.9, "E19.pa.moc": 20.0, "E19.epoxy.uloi": 23.6, "E19.epoxy.moc": 23.0}
    assert sorted(r.o2_pct for r in ds.rows if r.evidence_id == "E13") == [25, 29, 33, 37]
    margins = {m.margin_id: m.margin_pct_o2 for m in ds.margins}
    assert margins["E3"] == -2.4
    assert margins["E15.mylar_g.lunar"] == -5.75
    assert len(margins) == 10


def test_presets(ds):
    presets = {p.preset_id: p for p in ds.presets}
    assert (presets["lunar_habitat_nominal"].o2_pct, presets["lunar_habitat_nominal"].pressure_psia) == (34, 8.2)
    assert presets["iss_cabin"].o2_pct == 21
    assert {"eva_suit_0g", "eva_suit_lunar"} <= set(presets)


@pytest.mark.parametrize("filename,key,row_id,changes,expected", [
    ("ledger.csv", "row_id", "E2", {"o2_pct": "0"}, "o2_pct"),
    ("ledger.csv", "row_id", "E2", {"o2_pct": "120"}, "o2_pct"),
    ("ledger.csv", "row_id", "E2", {"o2_pct": ""}, "needs an o2_pct"),
    ("ledger.csv", "row_id", "E4.moc", {"pressure_psia": "-1"}, "pressure_psia"),
    ("ledger.csv", "row_id", "E2", {"source_id": ""}, "source_id"),
    ("ledger.csv", "row_id", "E2", {"source_url": "ftp://example.org/x.pdf"}, "source_url"),
    ("ledger.csv", "row_id", "E2", {"source_id": "NTRS-00000000000"}, "unknown source_id"),
    ("ledger.csv", "row_id", "E2", {"short_quote": " ".join(["word"] * 15)}, "longer than"),
    ("ledger.csv", "row_id", "E2", {"location": ""}, "location"),
    ("ledger.csv", "row_id", "E2", {"environment": "venus"}, "environment"),
    ("ledger.csv", "row_id", "E2", {"row_id": "E1"}, "duplicate"),
    ("margins.csv", "margin_id", "E3", {"margin_pct_o2": "abc"}, "margin_pct_o2"),
    ("presets.csv", "preset_id", "iss_cabin", {"o2_pct": "0"}, "o2_pct"),
])
def test_bad_data_is_rejected(tmp_path, filename, key, row_id, changes, expected):
    target = _edit(tmp_path, filename, key, row_id, changes)
    with pytest.raises(DataError) as err:
        load_dataset(target)
    assert expected in str(err.value)


def test_needs_check_row_is_held_back_not_rejected(tmp_path):
    target = _edit(tmp_path, "ledger.csv", "row_id", "E9", {"verified": "needs_check"})
    ds = load_dataset(target)
    assert "E9" not in {r.row_id for r in ds.rows}
    assert ds.hidden_rows == 2


def test_hypotheses_must_cite_verified_evidence(tmp_path):
    target = _edit(tmp_path, "ledger.csv", "row_id", "E11", {"verified": "needs_check"})
    with pytest.raises(DataError) as err:
        load_dataset(target)
    assert "not verified evidence" in str(err.value)


def test_missing_file_is_reported(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(DATA, target)
    (target / "presets.csv").unlink()
    with pytest.raises(DataError) as err:
        load_dataset(target)
    assert "presets.csv" in str(err.value)
