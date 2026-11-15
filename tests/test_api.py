"""Every page and endpoint must respond, and the API must expose only verified, published values."""
import csv
import io
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flameledger.data import canonical_hash
from flameledger.main import DISCLAIMER, app, create_app

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app)


@pytest.mark.parametrize("path", ["/", "/fm2", "/review", "/investigations", "/ask"])
def test_pages_load_with_disclaimer(path):
    res = client.get(path)
    assert res.status_code == 200
    assert DISCLAIMER in res.text
    assert "Research decision support, not certification" in res.text
    assert "Content-Security-Policy" in res.headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("path", ["/static/styles.css", "/static/common.js", "/static/ledger.js", "/static/fm2.js", "/static/review.js", "/static/investigations.js", "/static/ask.js", "/static/gaps.js", "/static/compare.js",
                                  "/static/favicon.svg", "/favicon.ico", "/docs", "/openapi.json"])
def test_assets_and_docs_load(path):
    assert client.get(path).status_code == 200


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["rows"] > 0
    assert isinstance(body["ai_enabled"], bool)


def test_ledger_only_returns_verified_rows():
    rows = client.get("/api/ledger").json()
    assert rows and all(r["verified"] == "yes" for r in rows)
    assert "E14" not in {r["row_id"] for r in rows}
    assert all(r["source_url"].startswith("https://ntrs.nasa.gov/") and r["location"] for r in rows)
    pmma = client.get("/api/ledger", params={"material_id": "pmma_rod", "environment": "microgravity"}).json()
    assert [r["row_id"] for r in pmma] == ["E2"]


def test_ledger_csv_download():
    res = client.get("/api/ledger.csv")
    assert res.status_code == 200 and "attachment" in res.headers["Content-Disposition"]
    rows = list(csv.DictReader(io.StringIO(res.text)))
    assert len(rows) == len(client.get("/api/ledger").json())


def test_margins_are_exactly_the_published_ones():
    with (ROOT / "data" / "margins.csv").open(newline="", encoding="utf-8") as fh:
        published = {r["margin_id"]: float(r["margin_pct_o2"]) for r in csv.DictReader(fh)}
    served = {m["margin_id"]: m["margin_pct_o2"] for m in client.get("/api/margins").json()}
    assert served == published


def test_no_computed_margin_is_served():
    """E6 (cast rod MOC 14.0) minus E2 (13.6) would be an unpublished margin. It must not appear anywhere."""
    for path in ("/api/coverage", "/api/gravity-profile", "/api/ledger", "/api/margins"):
        text = client.get(path).text
        assert not re.search(r"-?0\.4(0+)?\b(?!\d)", text.replace("0.40-in", "").replace("0.040-in", "")), path
    assert "margin" not in json.dumps(client.get("/api/gravity-profile").json()).lower()


def test_coverage_metrics_match_the_ledger():
    cov = client.get("/api/coverage").json()
    rows = [r for r in client.get("/api/ledger").json() if r["material_id"] != "aggregate"]
    materials = {r["material_id"] for r in rows}
    real = [r for r in rows if r["outcome"] != "planned"]
    m = cov["metrics"]
    assert m["materials"] == len(materials) == len(cov["materials"])
    assert m["with_1g"] == len({r["material_id"] for r in real if r["environment"] == "1g"})
    assert m["with_microgravity"] == len({r["material_id"] for r in real if r["environment"] == "microgravity"})
    assert m["with_partial_gravity"] == len({r["material_id"] for r in real if r["environment"] in ("lunar", "mars")})
    assert m["with_published_margin"] == len({x["material_id"] for x in client.get("/api/margins").json()})
    assert m["with_long_duration_lunar"] == 0
    assert m["cells_total"] == len(materials) * len(cov["environments"])
    empty = sum(1 for mat in cov["materials"] for c in mat["cells"].values() if c["status"] == "none")
    assert m["cells_empty"] == empty
    fm2 = {mat["material_id"]: mat["cells"]["fm2"]["status"] for mat in cov["materials"]}
    assert fm2["synergy_pro_navy"] == "planned"


def test_gravity_profile_uses_published_values():
    prof = client.get("/api/gravity-profile").json()
    assert prof["n_materials"] == 3
    mylar = next(m for m in prof["materials"] if m["material_id"] == "mylar_g")
    assert {p["environment"]: p["moc_pct_o2"] for p in mylar["points"]} == {
        "microgravity": 16.0, "lunar": 14.1, "mars": 17.0, "1g": 20.0}
    assert mylar["lunar_below_both"] is True


def test_hypotheses_fingerprint_is_reproducible():
    body = client.get("/api/hypotheses").json()
    assert len(body["hypotheses"]) == 3 and body["registered_on"] == "2026-11-15"
    assert body["sha256"] == canonical_hash(body["hypotheses"])
    assert "commit" in body


def test_presets_and_sources():
    presets = client.get("/api/presets").json()
    assert len(presets) == 10 and all(0 < p["o2_pct"] <= 100 for p in presets)
    sources = client.get("/api/sources").json()
    assert sources and all(s["pdf_url"].startswith("https://ntrs.nasa.gov/") for s in sources)


def test_not_found():
    page = client.get("/nope")
    assert page.status_code == 404 and DISCLAIMER in page.text
    api = client.get("/api/nope")
    assert api.status_code == 404 and "detail" in api.json()


def test_frontend_wording_rules():
    """No secrets, no forbidden wording, no external scripts, and the footer on every page."""
    for path in (ROOT / "web").rglob("*"):
        if path.suffix not in {".html", ".js", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bbounds?\b", text, re.I), f"'bounds' wording in {path.name}"
        assert "innerHTML" not in text, f"innerHTML in {path.name}"
        assert not re.search(r"AIza[0-9A-Za-z_\-]{20,}", text), f"API key in {path.name}"
        assert not re.search(r"<(script|link)[^>]+(src|href)=[\"']https?://", text), f"external asset in {path.name}"
        assert " style=" not in text, f"inline style (blocked by CSP) in {path.name}"
        if path.suffix == ".html":
            assert DISCLAIMER in text, f"footer missing in {path.name}"


EXAMPLE = {"o2_pct": 34, "pressure_psia": 8.2, "gravity_g": 0.165, "preset_id": "lunar_habitat_nominal",
           "materials": ["PMMA rod", "cotton-fiberglass fabric", "silicone", "Synergy Pro Navy fabric"]}


def test_review_example_without_ai():
    c = TestClient(create_app())
    res = c.post("/api/review", json=EXAMPLE)
    assert res.status_code == 200
    body = res.json()
    assert body["ai"] is None and body["ai_status"] == "not_configured"
    assert body["habitat"]["label"] == "Lunar habitat / pressurized rover, nominal"
    heads = {v["material_id"]: v["headline"]["level"] for v in body["verdicts"]}
    assert heads == {"pmma_rod": "red", "sibal_fabric": "grey", "silicone_mq": "grey", "synergy_pro_navy": "grey"}
    assert body["disclaimer"] == "Research decision support, not certification."
    assert body["thresholds"]["label"] == "FlameLedger research thresholds, not NASA criteria"
    shown = {e["id"] for v in body["verdicts"] for e in v["evidence"]}
    assert "E14" not in shown


def test_review_custom_habitat_label():
    c = TestClient(create_app())
    body = c.post("/api/review", json={**EXAMPLE, "o2_pct": 30}).json()
    assert body["habitat"]["label"] == "Custom habitat"


@pytest.mark.parametrize("change", [
    {"o2_pct": 0}, {"o2_pct": 100.5}, {"pressure_psia": 0}, {"pressure_psia": 31}, {"gravity_g": -0.1},
    {"gravity_g": 1.6}, {"materials": []}, {"materials": ["x"] * 21}, {"materials": ["x" * 81]},
    {"materials": ["   "]}, {"preset_id": "../etc"}, {"extra": 1}, {"thresholds": {"thin_margin_pct_o2": 9}},
])
def test_review_rejects_bad_input(change):
    c = TestClient(create_app())
    res = c.post("/api/review", json={**EXAMPLE, **change})
    assert res.status_code == 422
    assert "Traceback" not in res.text


def test_review_rate_limit():
    c = TestClient(create_app())
    codes = [c.post("/api/review", json=EXAMPLE).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429
    other = c.post("/api/review", json=EXAMPLE, headers={"X-Forwarded-For": "203.0.113.9"})
    assert other.status_code == 200


def test_report_markdown():
    c = TestClient(create_app())
    res = c.post("/api/report", json=EXAMPLE)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/markdown")
    assert "attachment" in res.headers["Content-Disposition"]
    text = res.text
    for needle in ("# FlameLedger Habitat Review", "Research decision support, not certification.",
                   "## Limitations", "## Sources", DISCLAIMER, "NTRS-20160000593", "13.6"):
        assert needle in text


def test_report_escapes_user_text():
    c = TestClient(create_app())
    text = c.post("/api/report", json={**EXAMPLE, "materials": ["[click](https://evil.example) | <script>"]}).text
    assert "[click](https://evil.example)" not in text and "<script>" not in text


def test_review_survives_ai_crash():
    application = create_app()

    def boom(*_):
        raise RuntimeError("model exploded")
    application.state.explainer._transport = boom
    body = TestClient(application).post("/api/review", json=EXAMPLE).json()
    assert body["ai"] is None and body["ai_status"] == "unavailable" and body["verdicts"]


def test_report_pdf():
    c = TestClient(create_app())
    res = c.post("/api/report.pdf", json=EXAMPLE)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="flameledger_habitat_review.pdf"' in res.headers["Content-Disposition"]
    assert res.content.startswith(b"%PDF") and len(res.content) > 3000


def test_report_pdf_survives_unicode_and_hostile_text():
    c = TestClient(create_app())
    weird = ["PMMA \U0001F525 rod", "\u5927\u7406\u77f3 marble", "\u2212 minus \u2014 dash \u201cquoted\u201d",
             "<script>alert(1)</script>", "**bold** [x](y)", "Nomex\u00a0HT90\u201140"]
    res = c.post("/api/report.pdf", json={**EXAMPLE, "materials": weird})
    assert res.status_code == 200 and res.content.startswith(b"%PDF")


def test_report_pdf_includes_verified_ai_when_cached():
    import json as _json
    application = create_app()
    good = {"summary": "PMMA rod burned in microgravity at 13.6% O2. Test-duct flow is not cabin ventilation.",
            "per_material": [{"material_id": "pmma_rod", "explanation": "Burned at 13.6% O2 in microgravity."}],
            "claims": [{"text": "burn", "value": 13.6, "unit": "pct_O2", "source_id": "E2"}]}
    application.state.explainer._transport = lambda *_: _json.dumps(good)
    c = TestClient(application)
    body = {**EXAMPLE, "materials": ["PMMA rod"]}
    assert c.post("/api/review", json=body).json()["ai_status"] == "verified"
    res = c.post("/api/report.pdf", json=body)
    assert res.status_code == 200 and res.content.startswith(b"%PDF")
