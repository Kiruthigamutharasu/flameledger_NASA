# Space Apps project page: ready-to-paste fields

Every link must open without a login.

---

### Project Name
FlameLedger

### High-Level Project Summary
FlameLedger summarises and ranks 21 NASA combustion investigations (BASS, Saffire, FLEX, SAME, ACME, FM2 and more) for five habitat types: crew spacecraft, space station, lunar base, pressurized rover and Mars base. It also keeps a hand-verified evidence ledger of 15 materials. Materials are screened for flammability on Earth, but flames behave differently in microgravity and partial gravity. For example, a PMMA rod spread steadily at 13.6% O2 on the ISS (BASS-II wind-tunnel flow, not cabin ventilation) against a 16% O2 1g blowoff limit, a published margin of −2.4% O2. FlameLedger collects the published NASA results material by material, links every number to its NASA source page, and shows where the evidence runs out: of 15 materials, 14 have Earth-gravity results but only 5 have microgravity evidence, and 49 of 75 material-by-environment cells are empty. Its Habitat Review agent gives each material a deterministic verdict for one or several habitat atmospheres, and the Ask page answers plain-English questions. In both, Gemini writes the text and a verifier checks every AI number and citation against the NASA sources before anything is shown. The project supports NASA's FM2 lunar experiment with three hypotheses registered before it flies.

### Link to Project Demo
Demo video (30 seconds, English subtitles, YouTube unlisted): paste the YouTube link here after uploading.

### Link to Final Project
Live app: https://flameledger.onrender.com · Code: https://github.com/Kiruthigamutharasu/flameledger_NASA

### Detailed Project Description
**What it does.** FlameLedger has five pages and an open API.
1. *Evidence Ledger*: computed metrics, a coverage grid of materials × environments (1g, ISS microgravity, lunar, Mars, FM2) and all published oxygen margins, ranked. Each cell opens the underlying values with the NASA document, page or table, and a quote of under 15 words.
2. *Habitat Review* (AI agent): the user picks a habitat preset (e.g. lunar habitat 34% O2 / 8.2 psia, from NASA's FM2 presentation) or enters custom values, and lists materials. Deterministic rules assign 🔴 (burned in reduced gravity at or below this O2), 🟠 (thin or negative published margin), 🟢 (self-extinguished at this gravity level at or above this O2) or ⚪ (no comparable space data: test needed). Every applicable verdict is listed, with caveats on pressure, test-duct flow vs. cabin ventilation, and partial gravity. Gemini then explains the verdicts; a verifier checks that every cited source was in the evidence given, that every number matches it within ±0.1, and that no number appears in the prose without a claim. If verification fails twice, only the deterministic table is shown. Users can download the full report as a PDF.
3. *Investigations*: 21 NASA combustion investigations (BASS, Saffire, SoFIE, FLARE, FM2, LUCI, FLEX, FLEX-2, CFI, the six ACME experiments, SPICE, SLICE, SAME, SAME-R, DAFT, water mist), each summarised with objective, fuels and sample sizes, conditions, variables, measurements and hardware. They are ranked by relevance to a crew spacecraft, space station, lunar base, pressurized rover or Mars base, with the reason behind every score, and can be filtered by prevention, detection and suppression and compared side by side. Includes fire safety on Earth and a data guide for modellers.
4. *Ask*: plain-English questions answered by Gemini from the catalogue and ledger only; the answer is shown only after the verifier checks every number and citation, and the sourced evidence is always listed.
5. *Partial gravity & FM2*: NASA drop-tower data show the lunar-gravity limit below both the 0g and 1g limits for all three materials tested, so, for those materials and under drop-tower criteria, 0g and 1g did not bracket lunar gravity. The page shows FM2's four planned tests and three pre-registered qualitative hypotheses, each with a refutation criterion, fixed by one SHA-256 fingerprint and the git tag fm2-hypotheses-v1.

**Benefits.** Habitat and materials engineers, researchers and students can see in seconds which materials have reduced-gravity evidence for their atmosphere, and which tests are missing. The verified ledger is reusable through a JSON/CSV API.

**How we built it.** FastAPI and pydantic serve a static HTML/CSS/JS frontend with hand-built SVG charts (no CDN, strict Content-Security-Policy). The data lives in CSV files that are validated at startup; unverified rows never reach the API. There are 167 automated tests. It is deployed on Render.

**Limitations.** The ledger is small and hand-verified. Lunar and Mars values come from short drop-tower tests. Only published margins are shown, and there are no numeric lunar or Mars predictions. This is research decision support, not certification.

### Use of Artificial Intelligence
- **In the product:** Google Gemini writes plain-language explanations of verdicts on the Habitat Review page and answers questions on the Ask page (answers come only from the investigation catalogue and verified ledger). It does not decide verdicts; deterministic rules do. Its output is shown only after FlameLedger's verifier confirms that every number and source matches the NASA evidence rows it was given. Without AI the app still works fully.
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
We use no partner-agency datasets directly. The investigation catalogue includes FLARE (Flammability Limits At Reduced-g Experiment), which NASA Glenn describes as an international team including JAXA, NASA and ESA, flying on JAXA's Kibo module with JAXA's 'Solid Combustion' hardware. Habitat presets for the ISS cabin, spacesuit and Moon base come from the NASA Space Apps 2026 *Flame in Freefall* challenge brief. A Saffire preliminary-results paper was considered but is held back, because its only available copy requires a login.

### References
- All NASA documents listed under NASA Data.
- NASA Glenn Research Center, Combustion Science: https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/
- NASA, A Researcher's Guide to: Combustion Science (2015): https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/
- NASA Glenn fact sheets for BASS, Saffire, FLEX, SAME, DAFT, SPICE, SLICE and ACME (linked from the Combustion Science page)
- NASA Spinoff: Fireman's Air Tanks, Fire Detector, New Technology for the Fire Attire
- NASA Space Apps 2026 challenge brief, *Flame in Freefall*.
- We did not use any other repositories or datasets; every fact comes from the NASA documents listed above and the Space Apps 2026 challenge brief.

Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. Uses public NASA data.
