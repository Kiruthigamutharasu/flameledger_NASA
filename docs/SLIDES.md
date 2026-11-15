# FlameLedger: 7 slides (including the title)

Every number below is from `data/*.csv` or `/api/coverage`, with its source shown on the slide. No NASA logos.
Footer on every slide: *Built for the 2026 NASA Space Apps Challenge. Not affiliated with or endorsed by NASA. Uses public NASA data.*

Submission-guide requirements: at most 7 slides including the title, in English, hosted on a public link. The deck must show the team name, team member names, the chosen challenge, and how space agency open data made the project possible (slides 1, 3, 4 and 7 cover these). If you submit a video instead: at most 30 seconds, with English subtitles.

---

## 1. FlameLedger
**Material by material: what reduced-gravity fire experiments already tell us, and where the evidence runs out.**
- Team: cool-flame-crew · Members: Kiruthiga Mutharasu
- NASA Space Apps 2026 · Challenge: *Flame in Freefall*
- Live: https://flameledger.onrender.com · Code: https://github.com/Kiruthigamutharasu/flameledger_NASA
- Research decision support, not certification.

## 2. The stakes: the first fire tests on the Moon
- NASA's **FM2** experiment plans to burn four solid fuel samples "in actual long duration Lunar gravity". Launch is planned for late 2026. *(NTRS 20260000646, p.1)*
- Planned lunar habitats and rovers: **34% O2 at 8.2 psia** nominal, with control bands up to 37% O2. *(NTRS 20260001966, p.25)*
- Materials are screened on Earth. Will that screening hold on the Moon?

## 3. The gap: Earth screening vs. reduced gravity
- PMMA ¼-in rod: **1g blowoff limit 16% O2**; **steady flame spread at 13.6% O2 on the ISS** (BASS-II).
- NASA authors' published margin: **−2.4% O2**, measured against the 1g *blowoff* limit, not Test 1. *(NTRS 20160000593, p.18)*
- Drop-tower data: lunar-gravity limits fall **below both** the 0g and the 1g limits for all 3 materials tested. *(NTRS 20130010991, Table I)*
- Visual: the PMMA bar chart from the Evidence Ledger page.

## 4. Evidence Ledger and Investigations: the gaps are the finding
*[Screenshot: metrics tiles and coverage grid]*
- 15 materials · 69 verified rows · 7 NASA documents
- **49 of 75** material × environment cells have no data; 14 materials have Earth (1g) results, only 5 have any microgravity evidence
- **0** materials have long-duration lunar-gravity data; FM2 plans the first
- 21 NASA investigations (BASS, Saffire, FLEX, SAME, ACME, FM2…) summarised and **ranked for your habitat**: spacecraft, station, lunar base, rover, Mars base
- Every value links to its NASA PDF page; the same data is available as an open JSON/CSV API.

## 5. AI agents with a fact-checker: Habitat Review and Ask
*[Screenshot: docs/images/14_atmosphere_matrix.png, plus the verdicts with the Verified badge]*
- Rules decide: 🔴 PMMA rod, Ultem and Nomex at a lunar habitat (34% O2) · ⚪ two fabrics with no comparable space data
- **Same materials, different atmospheres:** Ultem and Nomex have a 🟠 thin margin in ISS air but are 🔴 at Moon-base oxygen
- Gemini explains; the **verifier checks every number and source** and shows the explanation only if it passes ("Verified ✔")
- Works without AI too, and the full report downloads as a PDF.
- **Ask:** plain-English questions answered only from NASA evidence, with every number and citation checked

## 6. Partial gravity and FM2 hypotheses
- Why 0g and 1g did not bracket lunar gravity in NASA's drop-tower data: for Mylar G, Ultem 1000 and Nomex HT90-40 the lunar limit was below both. *(NTRS 20130010991, Table I)*
- FM2 Tests 1–4: 37 / 33 / 29 / 25% O2 at 8.2 psia, Synergy Pro Navy fabric. *(NTRS 20260001966, p.10)*
- Pre-registered, qualitative, each with a refutation test (git tag `fm2-hypotheses-v1`):
  - H1: the fabric sustains upward spread at 29% O2.
  - H2: its lunar limit will be lower than both its 0g and 1g limits.
  - H3: 25% O2 is closer to threshold than 29% (matching NASA's own expectation for Test 4).

## 7. Validity: why you can trust it
- Every source PDF was read and audited page by page (`docs/EVIDENCE_AUDIT.md`); a row with an unverifiable source is held back.
- Only published margins are shown; FlameLedger never computes one. There are no numeric lunar or Mars predictions.
- 165 automated tests, a strict CSP and a rate-limited AI endpoint; the page never errors without AI.
- Limitations: a small, hand-verified ledger; short drop-tower tests; test-duct flow is not cabin ventilation; not certification.
- Links: live app · GitHub · `/docs` API
