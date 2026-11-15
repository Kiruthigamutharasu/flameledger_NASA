# FlameLedger — Developer Guide

Single source of truth for architecture, rules, API contract and workflow.
The list of allowed facts is `docs/EVIDENCE_AUDIT.md` together with `data/*.csv`.

> Code ships straight to production (Render). Only local testing happens first. Everything merged must be prod-ready.

---

## 1. Why not Streamlit

| Concern | Streamlit | FastAPI + static HTML/JS (chosen) |
|---|---|---|
| Presentation (judging criterion) | Generic look, limited layout control | Full design control, custom SVG charts |
| Influence / Best Use of Data | Data trapped in the UI | Public JSON API + OpenAPI docs (`/docs`) others can reuse |
| Reliability on Render free tier | Websocket session, full-script rerun per click | Plain HTTP, stateless, fast first paint |
| Testability | UI logic hard to test | Every endpoint tested with `TestClient` |
| Security | Little control | Strict CSP, input limits, rate limit on the AI endpoint |

No Node or build step: one fewer thing that can break before the deadline.

---

## 2. Architecture

```
Browser (vanilla HTML/CSS/JS, no CDN)
   │  fetch JSON
   ▼
FastAPI  (flameledger/main.py)
   ├── /api/*            JSON API (pydantic-validated)
   ├── /                 web/index.html   Evidence Ledger
   ├── /review           web/review.html  Habitat Review (AI agent)
   ├── /fm2              web/fm2.html     Partial gravity & FM2
   └── /static/*         web/assets/      css, js, svg
        │
        ├── data.py      load + validate data/ledger.csv, data/presets.csv (once, at startup)
        ├── rules.py     deterministic verdicts (source of truth)
        ├── llm.py       Gemini explanation (optional)
        ├── verifier.py  checks every AI number/source against evidence rows
        └── report.py    Markdown report
```

### Repo layout
```
flameledger/   __init__.py main.py api.py data.py rules.py llm.py verifier.py report.py config.py
web/           index.html review.html fm2.html assets/{styles.css,common.js,ledger.js,review.js,fm2.js}
data/          ledger.csv presets.csv
tests/         test_data.py test_rules.py test_verifier.py test_api.py
docs/          EVIDENCE_AUDIT.md SLIDES.md SUBMISSION.md
requirements.txt  render.yaml  .python-version  .env.example
```

### AI agent pipeline (Habitat Review)
1. `rules.py` decides verdicts. **The LLM never decides a verdict.**
2. `llm.py` sends Gemini only the habitat, the verdict table and the evidence rows used. It returns JSON only (temperature 0.2, 30 s timeout, 1 retry).
3. `verifier.py` checks that every `source_id` is in the evidence given, that every number matches an evidence value within ±0.1 (percent vs fraction normalised), and that every number in the prose appears in `claims`.
4. If verification fails, the verifier's errors go back to Gemini for one retry. If it fails again, the page shows the deterministic table plus "AI explanation unavailable (failed verification)".
5. If there's no key, a timeout or any exception, the deterministic result is still returned. **The page never errors.**
6. Responses are cached in memory by a hash of the input, so the demo is instant and costs are bounded.

---

## 3. Non-negotiable content rules
1. Never invent data, numbers, material names, quotes, or PSI/NTRS IDs. The only allowed facts are the audited rows in `docs/EVIDENCE_AUDIT.md`. If something is unknown, say "unknown".
2. Every displayed number shows its source: NTRS ID, link and page/table.
3. Rows with `verified=needs_check` are **filtered out in `data.py`** and never reach the API.
4. No "bounds" wording. No numeric predictions for lunar or Mars gravity.
5. Duct/burner flow ≠ cabin ventilation. Always caveat this.
6. We support NASA's FM2 work. Never say NASA's test is wrong. Every verdict carries "Research decision support, not certification." Thresholds are labelled "FlameLedger research thresholds, not NASA criteria."
7. Quotes are under 15 words and link to the full text.
8. **Only published margins are shown** (E3: −2.4% O2). Never compute a margin by subtracting rows, for example E4's MOC minus E2. A test enforces this.
9. Footer on every page: "Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. Uses public NASA data." No NASA logos.

### Data-modelling decisions
- Qualitative or aggregate rows (E8–E12, E14) may have an empty `o2_pct`. Rows that aren't material-specific use `material_id=aggregate`.
- E13 has two atmospheres, so it becomes two rows. Synergy Pro Navy rows use `outcome=planned`.
- The spacesuit preset is split into two (0 g and lunar g); we don't pick one.
- Verdict precedence: 🔴 > 🟠 > 🟢 > ⚪. Every verdict that applies is listed, and the highest one is the headline.
- A material that burned in microgravity but has no O2 value (SIBAL) gets ⚪ with the note "Burned in microgravity (qualitative); O2 not in ledger, cannot compare to this habitat."
- E14 isn't on a NASA host, so it is listed under "Other data" and shown as a paraphrase only.

---

## 4. API contract

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","rows":N,"ai_enabled":bool}` |
| GET | `/api/ledger` | verified rows only |
| GET | `/api/coverage` | metrics + grid (materials × 1g / ISS µg / lunar / Mars / FM2), computed from the data |
| GET | `/api/margins` | published margins only |
| GET | `/api/presets` | habitat presets |
| GET | `/api/meta` | `{"date", "commit"}`: commit comes from `RENDER_GIT_COMMIT`, then `git rev-parse`, otherwise `"n/a"` |
| POST | `/api/review` | `{habitat, verdicts[], ai: {...}|null, ai_status}` |
| POST | `/api/report` | `text/markdown` download |

`/api/review` input: `o2_pct` must be in (0, 100], `pressure_psia` in (0, 30], `gravity_g` in [0, 1.5], and `materials` is a list of 1–20 strings of up to 80 characters each.

---

## 5. Production standards
- Secrets come only from env vars (`GEMINI_API_KEY`, `GEMINI_MODEL`). They never appear in code, logs or the frontend.
- Ledger validation runs once at startup and fails fast with a clear message. A bad row is a deploy blocker, not a runtime surprise.
- Security headers: `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.
- `/api/review` is rate-limited in memory per IP (10 requests/minute) to protect the Gemini key.
- Use `logging` and never `print`. Error messages shown to users never include stack traces.
- The frontend uses no external CDNs (the CSP blocks them). Charts are hand-built SVG. Text goes in with `textContent`; never use `innerHTML` with data.
- The frontend is accessible: semantic HTML, labelled inputs, emoji verdicts always paired with text, and AA contrast.
- Dependencies are pinned to tested ranges in `requirements.txt`. Python is 3.12 (`.python-version`).

---

## 6. Run · test · deploy

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env              # fill GEMINI_API_KEY, GEMINI_MODEL
.venv/Scripts/python -m uvicorn flameledger.main:app --reload --port 8000
.venv/Scripts/python -m pytest -q
```

**Before every commit:** pytest passes, and every page plus `/api/health` returns 200 locally, both with and without `GEMINI_API_KEY`.

**Render** (`render.yaml`): one Python web service. Build command: `pip install -r requirements.txt`. Start command: `uvicorn flameledger.main:app --host 0.0.0.0 --port $PORT`. Health check: `/api/health`. Set `GEMINI_API_KEY` and `GEMINI_MODEL` in the Render dashboard.

---

## 7. Workflow
- Work in small steps: plan, build, pytest, local check, commit.
- Before any number or quote is shown, check it against its NASA PDF page and record it in `docs/EVIDENCE_AUDIT.md`.
- Commits are authored as `cool-flame-crew`.

---

## 8. Changes after the evidence audit (15 Nov, 13:00 IST)
Every source PDF was read and the result is recorded in `docs/EVIDENCE_AUDIT.md`. That audit, with `data/*.csv`, replaces "E1–E14 only" as the list of allowed facts.
- **E15** adds measured 1g, microgravity, lunar and Mars limits for Mylar G, Ultem 1000 and Nomex HT90-40 (NTRS 20130010991, Table I). Never write that no partial-gravity data exists. FM2 gives the first *long-duration* lunar data.
- **E16–E18** add NASA's planned lunar habitat atmosphere, the Test 1 description and the FM2 design target.
- **E13** now holds all four FM2 tests. **E14** stays `needs_check` because its only link needs a login.
- Data files: `ledger.csv`, `margins.csv` (published margins only), `presets.csv`, `sources.csv`, `hypotheses.json`.
- Extra endpoints: `/api/sources`, `/api/gravity-profile`, `/api/hypotheses`, `/api/ledger.csv`.
- Install with `requirements-dev.txt` locally (adds pytest and httpx). Render installs `requirements.txt`.
- Every page carries the same nav: Evidence Ledger, Habitat Review, Partial gravity & FM2, Open API.
