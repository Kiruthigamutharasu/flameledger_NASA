# Space Apps project page: ready-to-paste fields

Replace `<LIVE_URL>`, `<GITHUB_URL>` and `<SLIDES_URL>` before pasting. Every link must open without a login.

---

### Project Name
FlameLedger

### High-Level Project Summary
FlameLedger is an evidence ledger for spacecraft fire safety across gravity levels. Materials are screened for flammability on Earth, but flames behave differently in microgravity and partial gravity. For example, a PMMA rod spread steadily at 13.6% O2 on the ISS against a 16% O2 limit in normal gravity, a published margin of −2.4% O2. FlameLedger collects the published NASA results material by material, links every number to its NASA source page, and shows where the evidence runs out: of 15 materials, 14 have Earth-gravity results but only 5 have microgravity evidence, and 49 of 75 material-by-environment cells are empty. Its Habitat Review agent gives each material a deterministic verdict for a given habitat atmosphere. Gemini explains the verdicts, and a verifier checks every AI number against the sources before anything is shown. The project supports NASA's FM2 lunar experiment with three hypotheses registered before it flies.

### Link to Project Demo
`<SLIDES_URL>` (7 slides, public, no login)

### Link to Final Project
Live app: `<LIVE_URL>` · Code: `<GITHUB_URL>`

### Detailed Project Description
**What it does.** FlameLedger has three pages and an open API.
1. *Evidence Ledger*: computed metrics, a coverage grid of materials × environments (1g, ISS microgravity, lunar, Mars, FM2) and all published oxygen margins, ranked. Each cell opens the underlying values with the NASA document, page or table, and a quote of under 15 words.
2. *Habitat Review* (AI agent): the user picks a habitat preset (e.g. lunar habitat 34% O2 / 8.2 psia, from NASA's FM2 presentation) or enters custom values, and lists materials. Deterministic rules assign 🔴 (burned in reduced gravity at or below this O2), 🟠 (thin or negative published margin), 🟢 (self-extinguished at this gravity level at or above this O2) or ⚪ (no comparable space data: test needed). Every applicable verdict is listed, with caveats on pressure, test-duct flow vs. cabin ventilation, and partial gravity. Gemini then explains the verdicts; a verifier checks that every cited source was in the evidence given, that every number matches it within ±0.1, and that no number appears in the prose without a claim. If verification fails twice, only the deterministic table is shown. Users can download the full report as a PDF.
3. *Partial gravity & FM2*: NASA drop-tower data show the lunar-gravity limit below both the 0g and 1g limits for all three materials tested, so 0g and 1g do not bracket the Moon. The page shows FM2's four planned tests and three pre-registered qualitative hypotheses, each with a refutation criterion and a SHA-256 fingerprint.

**Benefits.** Habitat and materials engineers, researchers and students can see in seconds which materials have reduced-gravity evidence for their atmosphere, and which tests are missing. The verified ledger is reusable through a JSON/CSV API.

**How we built it.** FastAPI and pydantic serve a static HTML/CSS/JS frontend with hand-built SVG charts (no CDN, strict Content-Security-Policy). The data lives in CSV files that are validated at startup; unverified rows never reach the API. There are 122 automated tests. It is deployed on Render.

**Limitations.** The ledger is small and hand-verified. Lunar and Mars values come from short drop-tower tests. Only published margins are shown, and there are no numeric lunar or Mars predictions. This is research decision support, not certification.

### Use of Artificial Intelligence
- **In the product:** Google Gemini writes plain-language explanations of verdicts on the Habitat Review page. It does not decide verdicts; deterministic rules do. Its output is shown only after FlameLedger's verifier confirms that every number and source matches the NASA evidence rows it was given. Without AI the app still works fully.
- **In development:** an AI coding assistant helped write code and documentation; the team reviewed all of it.
- **Data:** no AI-generated facts. Every ledger value was checked by a human against the NASA PDF and recorded with its page in docs/EVIDENCE_AUDIT.md.

### NASA Data
- NTRS 20160000593: Ferkul et al., Combustion of Solids in Microgravity: Results from the BASS-II Experiment. https://ntrs.nasa.gov/citations/20160000593
- NTRS 20110008636: Hirsch et al. 2011, Selected Parametric Effects on Materials Flammability Limits. https://ntrs.nasa.gov/citations/20110008636
- NTRS 20130012832: Ferkul et al., Flammability Aspects of a Cotton-Fiberglass Fabric in Opposed and Concurrent Airflow in Microgravity. https://ntrs.nasa.gov/citations/20130012832
- NTRS 20080034883: Olson, Ruff & Miller 2008, Microgravity Flame Spread in Exploration Atmospheres. https://ntrs.nasa.gov/citations/20080034883
- NTRS 20130010991: Olson & Ferkul 2012, Evaluating Material Flammability in Microgravity and Martian Gravity Compared to the NASA Standard Normal Gravity Test. https://ntrs.nasa.gov/citations/20130010991
- NTRS 20260000646: Ferkul et al., Flammability of Materials on the Moon (FM2), LPSC 2026 abstract. https://ntrs.nasa.gov/citations/20260000646
- NTRS 20260001966: Ferkul et al., Flammability of Materials on the Moon (FM2), LPSC 2026 presentation. https://ntrs.nasa.gov/citations/20260001966

### Space Agency Partner & Other Data
No partner-agency data is used. Habitat presets for the ISS cabin, spacesuit and Moon base come from the NASA Space Apps 2026 *Flame in Freefall* challenge brief. A Saffire preliminary-results paper was considered but is held back, because its only available copy requires a login.

### References
- All NASA documents listed under NASA Data.
- NASA Space Apps 2026 challenge brief, *Flame in Freefall*.
- `<TEAM: list any other public repos or READMEs consulted, or write "None">`

Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. Uses public NASA data.
