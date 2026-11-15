# FlameLedger

What do reduced-gravity fire experiments actually tell us about spacecraft materials, and where does the evidence run out? FlameLedger answers that one material at a time, and every number links back to the NASA report it came from.

Our entry for the NASA Space Apps Challenge 2026, *Flame in Freefall*.

- **Live app: https://flameledger.onrender.com**
- Try the Example review: https://flameledger.onrender.com/review?example=1
- API docs: https://flameledger.onrender.com/docs
- Code: https://github.com/Kiruthigamutharasu/flameledger_NASA

The app runs on Render's free tier, so the first visit after a quiet period can take about a minute to wake up.

> Research decision support, not certification. Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. Uses public NASA data.

## Why we built this

Spacecraft materials are screened for flammability on Earth. NASA's standard Test 1 is "an upward burning test at the worst-case atmospheric conditions" (NTRS 20260001966, p.27). But flames don't behave the same way when buoyancy is weak or missing, and the published data shows it:

- A ¼-inch PMMA rod has a 1g blowoff limit of 16% O2, yet it kept spreading at 13.6% O2 on the ISS during BASS-II. The NASA authors report this as a margin of −2.4% O2, measured against the 1g blowoff limit rather than Test 1 (NTRS 20160000593, p.18).
- In NASA's drop-tower tests on Mylar G, Ultem 1000 and Nomex HT90-40, the lunar-gravity limit came out lower than both the microgravity limit and the 1g limit (NTRS 20130010991, Table I). So you can't assume the Moon sits somewhere between orbit and Earth.
- NASA's FM2 experiment plans to burn four solid samples "in actual long duration Lunar gravity", with launch planned for late 2026 (NTRS 20260000646).

If you're choosing materials for a lunar habitat, the useful question is: for my atmosphere, is there any reduced-gravity evidence for this material, and if not, what's missing? We couldn't find a single place that answers that, so we built one.

## What's in it

**Evidence Ledger** (`/`): opens with the key finding (a PMMA rod kept burning on the ISS below its Earth-gravity blowoff limit) and four "start here" cards that take you straight into each tool. Then come headline counts, a grid of materials against test environments (1g, ISS microgravity, lunar, Mars, FM2) and every published oxygen margin, ranked. Click any cell to see the values behind it, with the NASA document, the page or table, and a short quote. The empty cells matter most: they show where nobody has published data yet. A glossary explains ULOI, MOC, margins of safety, Test 1 and the ISS hardware, each from its NASA source.

**Investigations** (`/investigations`): 21 NASA combustion investigations (BASS, Saffire, SoFIE, FLARE, FM2, LUCI, FLEX, FLEX-2, CFI, the six ACME experiments, SPICE, SLICE, SAME, SAME-R, DAFT and the water-mist experiment). Each card gives the objective, fuels and sample sizes, test conditions, variables, measurements and hardware, with its NASA sources. Pick a habitat (crew spacecraft, space station, lunar base, pressurized rover, Mars base) and the investigations are ranked by relevance, with the reason for every point of the score. Filter by prevention, detection or suppression, and compare two or three investigations side by side. An **oxygen coverage map** puts the oxygen range each investigation tested next to the atmospheres we plan to live in (ISS 21%, Moon base 30%, lunar habitat 34%, spacesuit 100%). Of the solid-material investigations with a reported oxygen range, only FM2 (planned) and SoFIE (planned chamber range) reach the lunar-habitat level. A **similarities grid** shows all 21 investigations at once (fuel, platform, oxygen tested and relevance tags), and a **timeline** runs from the 2003 water-mist experiment to FM2. The page also covers fire safety on Earth and a guide to the data for modellers, and the whole catalogue downloads as CSV.

**Shareable views:** every page keeps its state in the link, so you can send a colleague (or a judge) straight to a result: `/review?example=1` runs the Example review, `/ask?q=…` answers a question, and `/investigations?habitat=space_station&compare=flex,flex2` opens a ranking with a comparison.

**Ask** (`/ask`): ask a question in plain English, such as "Which experiments studied smoke detection?". FlameLedger finds the most relevant investigations and ledger rows, Gemini writes a short answer from that evidence only, and the answer is shown only if every number and citation checks out. The sourced evidence is always listed, even without AI.

**Habitat Review** (`/review`): enter an atmosphere (O2 %, pressure, gravity) and a list of materials. Each material gets a verdict from fixed rules, then Gemini writes a plain-English explanation that is only shown if it passes a fact check. A matrix then shows the same materials across several atmospheres side by side: Ultem and Nomex have a thin margin in ISS air but burn at Moon-base oxygen levels. For common materials that aren't in the ledger, such as Kapton or Teflon, the agent explains what NASA did test (smoke studies in SAME) instead of guessing. You can download the whole review as a PDF.

On the Evidence Ledger you can also **compare any two materials** across all five environments. A light/dark theme switch and print-friendly pages are on every page.

**Partial gravity & FM2** (`/fm2`): why 0g and 1g did not bracket lunar gravity for the three materials in NASA's drop-tower data, the published limits at four gravity levels, FM2's four planned tests, an **oxygen what-if heatmap** (every material at every oxygen level from 15% to 40%, in orbit, on the Moon or on Mars, showing where the evidence turns red: at lunar gravity it turns red at a lower oxygen level than in orbit for Mylar G, Nomex and Ultem), a **"what to test next"** plan that groups every material by the strongest reduced-gravity evidence it has, and three hypotheses we wrote down before FM2 flies.

**Open API** (`/docs`): the same data as JSON or CSV (`/api/ledger`, `/api/ledger.csv`, `/api/margins`, `/api/coverage`, `/api/gravity-profile`, `/api/hypotheses`, `/api/sources`, `/api/presets`), so anyone can reuse the checked ledger.

### Architecture

One FastAPI service serves both the pages and the JSON API. The verified data files are loaded and checked once, at startup.

![FlameLedger architecture](docs/images/architecture.png)

### The ledger in numbers

These counts are computed by the app from the data files, not typed in:

- 15 materials and 69 verified evidence rows, from 7 NASA documents
- 14 of the 15 materials have a 1g result, but only 5 have microgravity evidence and 3 have lunar or Mars data
- 10 published margins, covering 4 materials
- 49 of the 75 material/environment cells are empty
- No material has long-duration lunar-gravity data yet; FM2 plans to be the first
- 1 row is held back because its only source needs a login

## Screenshots

**Home:** the key finding and where to start.

![Home page: key finding and start-here cards](docs/images/00_home_start.png)

**Evidence Ledger:** live counts and the coverage grid. Every striped cell is a material/environment pair with no published data.

![Evidence Ledger: metrics and coverage grid](docs/images/01_evidence_ledger.png)

**Investigations:** NASA's combustion investigations ranked for the selected habitat, with a side-by-side comparison.

![Investigations ranked for a habitat](docs/images/10_investigations_rank.png)
![Comparing two investigations](docs/images/11_investigations_compare.png)

**Oxygen what-if:** where each material's evidence turns red as habitat oxygen rises, here at lunar gravity.

![Oxygen what-if heatmap](docs/images/17_oxygen_whatif.png)

**Similarities and timeline:** all 21 investigations in one grid, and when they flew.

![Similarities grid and timeline](docs/images/15_similarities_timeline.png)

**What to test next:** the evidence gaps as a test plan for a lunar habitat.

![What to test next](docs/images/16_test_next.png)

**Oxygen coverage:** how far NASA's tests reach toward the oxygen levels planned for lunar habitats and suits.

![Oxygen tested versus habitat atmospheres](docs/images/13_oxygen_coverage.png)

**Ask:** a plain-English question answered from the evidence, with a verified badge and the sources.

![Ask FlameLedger with a verified answer](docs/images/12_ask.png)

**Habitat Review:** the Example case (lunar habitat, 34% O2, 8.2 psia). The rules decide the verdicts, and Gemini's explanation is shown only after it passes the fact check.

![Habitat Review input](docs/images/03_habitat_review_input.png)
![Habitat Review verdicts with a verified AI explanation](docs/images/04_habitat_review_verdicts.png)

The same materials across habitat atmospheres, from ISS air to a spacesuit:

![Same materials, different atmospheres](docs/images/14_atmosphere_matrix.png)

Each material gets its own card with the evidence, what's missing and the caveats:

![Material detail card](docs/images/05_material_detail.png)

**Published margins:** only the margins NASA authors published, ranked.

![Published oxygen margins](docs/images/02_published_margins.png)

**Partial gravity:** for all three materials with data at four gravity levels, the lunar limit is lower than both the microgravity and the 1g limit.

![Measured limits at four gravity levels](docs/images/06_partial_gravity.png)

**FM2:** NASA's four planned lunar tests, and our three hypotheses registered before the mission flies.

![FM2 planned tests](docs/images/07_fm2_mission.png)
![Pre-registered FM2 hypotheses](docs/images/09_fm2_hypotheses.png)

It works on a phone too:

<img src="docs/images/08_mobile_review.png" alt="Habitat Review on a phone" width="300">

## How the Habitat Review works

![Habitat Review agent workflow](docs/images/agent_workflow.png)

The verdicts come from fixed rules, not from the AI. For each material:

- 🔴 It burned in reduced gravity at or below the habitat's O2.
- 🟠 A published margin is negative or thin.
- 🟢 It self-extinguished at the habitat's own gravity level, at or above its O2.
- ⚪ There's no comparable space data, so a test is needed. The app shows the nearest evidence and what's missing.

When several apply, all of them are listed and the most serious one becomes the headline. The thresholds (count a burn up to +0% O2 above the habitat; a margin under 0.5% O2 is thin) are our own research settings, not NASA criteria, and you can change them on the page.

Gemini only gets the habitat, the verdict table and the evidence rows that were used. It has to answer in JSON, and every number it uses has to be listed as a claim with its source. Our verifier then checks three things:

1. every source it cites was in the evidence we gave it;
2. every number matches that evidence within ±0.1 (it handles 0.136 vs 13.6%);
3. no number appears in the text without a matching claim, and there's no wording like "certified", "safe" or "NASA's test is wrong".

If the check fails, Gemini gets one more try with the list of errors. If that also fails, the page says "AI explanation unavailable (failed verification)" and still shows the full rule-based result. With no API key, a timeout or any error, you still get the verdicts. The page never breaks because of the AI.

## How this fits the judging criteria

- **Influence:** a public, checked, citable ledger and investigation catalogue with an open API, habitat-specific rankings, and reviews you can download as a PDF.
- **Creativity:** we treat the gaps as the finding, and we registered FM2 hypotheses before the mission flies (SHA-256 fingerprint plus the git tag `fm2-hypotheses-v1`).
- **Validity:** every number links to its NASA page, only published margins are shown, the AI is fact-checked, and there are 167 automated tests and a written evidence audit (`docs/EVIDENCE_AUDIT.md`).
- **Relevance:** it summarises, ranks and interprets NASA combustion investigations for spacecraft, stations, lunar and Mars bases and rovers, which is what *Flame in Freefall* asks for. See [`docs/CHALLENGE_COVERAGE.md`](docs/CHALLENGE_COVERAGE.md) for a point-by-point map.
- **Presentation:** five focused pages with one-click shareable views, hand-drawn SVG charts, no external scripts, and it works on a phone.

## NASA data we used

| ID | Document | What we took from it |
|---|---|---|
| [NTRS 20160000593](https://ntrs.nasa.gov/citations/20160000593) | Ferkul et al., *Combustion of Solids in Microgravity: Results from the BASS-II Experiment* (ASGSR 2014 poster) | PMMA rod: 1g blowoff 16% O2, ISS spread at 13.6% O2, published margin −2.4% O2 |
| [NTRS 20110008636](https://ntrs.nasa.gov/citations/20110008636) | Hirsch et al. 2011, *Selected Parametric Effects on Materials Flammability Limits* | 1g ULOI/MOC for PMMA rods, silicone, polyimide, PEEK, nitrile rubber, PVC, POM, polypropylene, nylon and epoxy/glass (Tables 2, 5, 7, 8, 9) |
| [NTRS 20130012832](https://ntrs.nasa.gov/citations/20130012832) | Ferkul et al., *Flammability Aspects of a Cotton-Fiberglass Fabric … in Microgravity* | SIBAL fabric, qualitative microgravity and 1g results |
| [NTRS 20080034883](https://ntrs.nasa.gov/citations/20080034883) | Olson, Ruff & Miller 2008, *Microgravity Flame Spread in Exploration Atmospheres* | Overall finding: 1g ULOI and MOC "greater than those in 0g, by up to 4% oxygen mole fraction" (fuels tested) |
| [NTRS 20130010991](https://ntrs.nasa.gov/citations/20130010991) | Olson & Ferkul 2012, *Evaluating Material Flammability in Microgravity and Martian Gravity …* | Table I: limits and published margins at 1g, Mars, lunar and 0g for Mylar G, Ultem 1000 and Nomex HT90-40 |
| [NTRS 20260000646](https://ntrs.nasa.gov/citations/20260000646) | Ferkul et al., FM2 abstract, LPSC 2026 | The FM2 mission; partial gravity may raise flammability limits |
| [NTRS 20260001966](https://ntrs.nasa.gov/citations/20260001966) | Ferkul et al., FM2 presentation, LPSC 2026 | FM2 Tests 1–4 (37/33/29/25% O2 at 8.2 psia), the lunar habitat atmosphere (34% O2, 8.2 psia), the EVA suit (100% O2, 4.3 psia), the Test 1 description, and the FM2 design target |

The investigation catalogue also draws on NASA Glenn's [Combustion Science](https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/) page and fact sheets (BASS, Saffire, FLEX, SAME, DAFT, SPICE, SLICE, ACME), NASA's [Researcher's Guide to ISS Combustion Science](https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/) and NASA Spinoff pages. The full list is on the Investigations page and in `data/investigations.json`.

Some habitat presets also come from the Space Apps 2026 challenge brief. Values from NASA PDFs are logged with their page in [`docs/EVIDENCE_AUDIT.md`](docs/EVIDENCE_AUDIT.md). The ISS-cabin and Moon-base presets come from the challenge brief web page.

## Limitations

- 15 materials isn't everything. We added only what we could check against a public NASA PDF. If a material isn't here, we have no verified evidence for it, which doesn't mean it's safe.
- We only show margins the original authors published. We never calculate a margin ourselves, and we don't predict numbers for lunar or Mars gravity.
- The lunar and Mars values come from short drop-tower tests, whose limit criteria differ from the 1g test. FM2 will give the first long-duration lunar data.
- Flow in a test duct or burner isn't the same as cabin ventilation.
- This is research decision support, not certification. Always go back to the original NASA documents and your programme's materials and processes authority.

## Running it yourself

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
cp .env.example .env          # optional: GEMINI_API_KEY and GEMINI_MODEL
.venv/Scripts/python -m uvicorn flameledger.main:app --reload --port 8000
.venv/Scripts/python -m pytest -q
```

It works fine without a Gemini key; you just get the rule-based verdicts. We deploy it as a single Render web service (`render.yaml`, health check at `/api/health`).

Built with FastAPI, pydantic and plain HTML/CSS/JS: no build step, no CDN, and a strict Content-Security-Policy. Gemini is called through `google-genai`, and the PDF reports are made with `fpdf2`.

## Timeline

We planned before the event and built all the code and data on 14–15 November 2026.

## Use of AI

- **In the app:** Google Gemini writes the plain-English explanation on the Habitat Review page and the answers on the Ask page. It never decides a verdict or invents data: its text is only shown once our verifier has checked every number and citation against the NASA evidence it was given. Retrieval for Ask is keyword-based, so the AI only ever sees the most relevant sourced items.
- **During development:** we used an AI coding assistant to help write code and documentation. We reviewed all of it ourselves.
- **Data:** none of the data is AI-generated. We checked every value in the ledger by hand against the NASA PDF, page by page (`docs/EVIDENCE_AUDIT.md`).

## References

All the NASA documents we used are listed in the table above, along with the Space Apps 2026 *Flame in Freefall* challenge brief. We did not use any other repositories or datasets.

## Licence

MIT. See [LICENSE](LICENSE).

Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. Uses public NASA data. No NASA logos are used.
