"""Investigation catalogue, habitat ranking, comparison and Ask FlameLedger."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flameledger.config import ROOT, Settings
from flameledger.data import MAX_QUOTE_WORDS, DataError, load_dataset
from flameledger.investigations import load_catalogue, rank
from flameledger.main import create_app
from flameledger.verifier import verify_answer

DATA = Path(__file__).resolve().parent.parent / "data"
NO_KEY = Settings(data_dir=DATA, web_dir=ROOT / "web", gemini_api_key="", gemini_model="")


@pytest.fixture(scope="module")
def cat():
    ds = load_dataset(DATA)
    return load_catalogue(DATA, {r.row_id for r in ds.rows})


@pytest.fixture()
def client():
    return TestClient(create_app(NO_KEY))


def test_catalogue_covers_the_challenge_investigations(cat):
    acronyms = " ".join(i.acronym for i in cat.investigations)
    for name in ("BASS", "Saffire", "SAME", "SAME-R", "DAFT", "FLEX", "FLEX-2", "CFI", "CFI-G", "BRE",
                 "E-FIELD", "SPICE", "SLICE", "FM2", "LUCI", "SoFIE", "FLARE"):
        assert name in acronyms, name
    areas = {a for i in cat.investigations for a in i.areas}
    assert {"prevention", "detection", "suppression"} <= areas


def test_every_field_is_sourced_and_quotes_are_short(cat):
    known = {s.source_id for s in cat.sources}
    for inv in cat.investigations:
        assert inv.sources and inv.quotes
        for q in inv.quotes:
            assert q.source_id in known and len(q.text.split()) <= MAX_QUOTE_WORDS
        for flag, note in inv.flags.items():
            assert flag in cat.flags and note
    assert all(s.url.startswith("https://") for s in cat.sources)


def test_ranking_is_transparent(cat):
    res = rank(cat, "lunar_base")
    top = res["results"][0]
    assert top["id"] == "fm2"
    assert top["score"] == sum(r["weight"] for r in top["reasons"])
    assert res["label"] == "FlameLedger ranking weights, not NASA criteria"
    station = [r["id"] for r in rank(cat, "space_station")["results"][:3]]
    assert "saffire" in station and "bass" in station


@pytest.mark.parametrize("change,expected", [
    (lambda d: d["investigations"][0]["quotes"][0].update(text=" ".join(["w"] * 15)), "longer than"),
    (lambda d: d["investigations"][0]["quotes"][0].update(source_id="NOPE"), "unknown source_id"),
    (lambda d: d["investigations"][0].update(ledger_rows=["E999"]), "not a verified ledger row"),
    (lambda d: d["investigations"][0].update(areas=["cooking"]), "investigations.json"),
    (lambda d: d["sources"][0].update(url="http://insecure.example"), "investigations.json"),
])
def test_bad_catalogue_is_rejected(tmp_path, change, expected):
    target = tmp_path / "data"
    shutil.copytree(DATA, target)
    path = target / "investigations.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    change(d)
    path.write_text(json.dumps(d), encoding="utf-8")
    ds = load_dataset(target)
    with pytest.raises(DataError) as err:
        load_catalogue(target, {r.row_id for r in ds.rows})
    assert expected in str(err.value)


def test_investigation_endpoints(client):
    body = client.get("/api/investigations").json()
    assert len(body["investigations"]) >= 20 and body["earth_applications"]
    det = client.get("/api/investigations", params={"area": "detection"}).json()["investigations"]
    assert {i["id"] for i in det} >= {"same", "daft"}
    assert client.get("/api/investigations/bass").json()["acronym"].startswith("BASS")
    assert client.get("/api/investigations/nope").status_code == 404
    ranked = client.get("/api/investigations/rank", params={"habitat": "pressurized_rover"}).json()
    assert ranked["results"][0]["score"] >= ranked["results"][-1]["score"]
    assert client.get("/api/investigations/rank", params={"habitat": "venus"}).status_code == 422


def test_compare(client):
    res = client.get("/api/investigations/compare", params={"ids": "flex,flex2"}).json()
    hw = next(r for r in res["rows"] if r["field"] == "hardware")
    assert "mdca" in res["similarities"]["hardware_terms"] and hw["values"][1] == "MDCA in the CIR"
    for bad in ("flex", "flex,flex", "a,b,c,d", "flex,nope"):
        assert client.get("/api/investigations/compare", params={"ids": bad}).status_code in (404, 422)


def test_ask_without_ai_returns_sourced_evidence(client):
    res = client.post("/api/ask", json={"question": "Which experiments studied smoke detection?"}).json()
    assert res["ai_status"] == "not_configured" and res["answer"] is None
    ids = [e["id"] for e in res["evidence"]]
    assert "inv:same" in ids and "inv:daft" in ids
    assert all(e["url"].startswith("https://") for e in res["evidence"])


def test_ask_no_match_and_validation(client):
    assert client.post("/api/ask", json={"question": "pizza recipes please"}).json()["ai_status"] == "no_match"
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 301}).status_code == 422


def test_ask_rate_limit(client):
    codes = [client.post("/api/ask", json={"question": "FLEX suppressants"}).status_code for _ in range(11)]
    assert codes[-1] == 429 and codes[:10] == [200] * 10


def _app_with(answer_fn):
    app = create_app(NO_KEY)
    app.state.explainer._transport = answer_fn
    return TestClient(app)


def test_ask_verified_answer_with_fake_model():
    good = {"answer": "FLEX tested inert-gas suppressants with oxygen mole fractions from 0.10 to 0.50.",
            "citations": ["inv:flex"],
            "claims": [{"text": "low", "value": 0.10, "source_id": "inv:flex"},
                       {"text": "high", "value": 0.50, "source_id": "inv:flex"}]}
    res = _app_with(lambda *_: json.dumps(good)).post("/api/ask", json={"question": "What suppressants did FLEX test?"}).json()
    assert res["ai_status"] == "verified" and res["citations"][0]["id"] == "inv:flex"


def test_ask_rejects_invented_numbers():
    bad = {"answer": "FLEX showed flames die at 12% oxygen on the Moon.", "citations": ["inv:flex"], "claims": []}
    res = _app_with(lambda *_: json.dumps(bad)).post("/api/ask", json={"question": "What suppressants did FLEX test?"}).json()
    assert res["ai_status"] == "failed_verification" and res["answer"] is None and res["evidence"]


def test_verify_answer_rules():
    ctx = [{"id": "inv:x", "title": "X", "text": "Oxygen from 10% to 40% at 0.2 to 1.5 atm."}]
    ok = {"answer": "It ran from 10% to 40% oxygen.", "citations": ["inv:x"],
          "claims": [{"text": "a", "value": 10, "source_id": "inv:x"}, {"text": "b", "value": 0.4, "source_id": "inv:x"}]}
    assert verify_answer(ok, ctx).ok
    assert not verify_answer({**ok, "citations": ["inv:y"]}, ctx).ok
    assert not verify_answer({**ok, "claims": [{"text": "a", "value": 55, "source_id": "inv:x"}]}, ctx).ok
    assert not verify_answer({**ok, "answer": "This material is certified at 10%."}, ctx).ok
    assert not verify_answer("not json", ctx).ok


def test_catalogue_csv(client):
    import csv as _csv
    import io as _io
    res = client.get("/api/investigations.csv")
    assert res.status_code == 200 and "attachment" in res.headers["Content-Disposition"]
    rows = list(_csv.DictReader(_io.StringIO(res.text)))
    assert len(rows) == len(client.get("/api/investigations").json()["investigations"])
    flex = next(r for r in rows if r["id"] == "flex")
    assert (flex["o2_min_pct"], flex["o2_max_pct"]) == ("10", "50") and "nasa.gov" in flex["sources"]


def test_o2_ranges_are_sourced(cat):
    known = {s.source_id for s in cat.sources}
    ranged = {i.id: i.o2_range for i in cat.investigations if i.o2_range}
    assert {"bass", "sofie", "flex", "fm2", "cfi_g"} <= set(ranged)
    assert (ranged["fm2"].min, ranged["fm2"].max) == (25, 37)
    assert all(r.source_id in known for r in ranged.values())


def test_o2_range_order_is_validated(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(DATA, target)
    path = target / "investigations.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    next(i for i in d["investigations"] if i["id"] == "flex")["o2_range"]["min"] = 90
    path.write_text(json.dumps(d), encoding="utf-8")
    ds = load_dataset(target)
    with pytest.raises(DataError):
        load_catalogue(target, {r.row_id for r in ds.rows})


def test_spacecraft_and_station_rank_differently(cat):
    sc = [r["id"] for r in rank(cat, "spacecraft")["results"]]
    st = [r["id"] for r in rank(cat, "space_station")["results"]]
    assert sc != st


def test_atmosphere_matrix(client):
    body = {"materials": ["Ultem", "silicone"], "preset_ids": ["iss_cabin", "lunar_habitat_nominal"]}
    res = client.post("/api/review/matrix", json=body).json()
    assert [c["preset_id"] for c in res["columns"]] == ["iss_cabin", "lunar_habitat_nominal"]
    ultem = next(r for r in res["rows"] if r["material_id"] == "ultem_1000")
    assert [c["level"] for c in ultem["cells"]] == ["orange", "red"]
    assert res["disclaimer"] == "Research decision support, not certification."
    assert client.post("/api/review/matrix", json={**body, "preset_ids": ["iss_cabin"]}).status_code == 422
    assert client.post("/api/review/matrix", json={**body, "preset_ids": ["iss_cabin", "nope"]}).status_code == 422
