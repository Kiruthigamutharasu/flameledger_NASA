# How FlameLedger covers the *Flame in Freefall* challenge

Challenge: [Flame in Freefall: SI-Powered Fire Safety Insights from Microgravity Combustion Data](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/) (NASA Space Apps 2026).

The challenge asks for an SI-powered web dashboard that *"summarizes, ranks, and interprets combustion science investigations"* for fire safety. This file maps each part of the challenge to what we built and where to find it. It also lists what we found missing in our first version and what we added to close each gap.

## 1. Objectives

| Challenge asks | What FlameLedger does | Where |
|---|---|---|
| A web-based dashboard | Five pages plus an open API | `/`, `/investigations`, `/review`, `/ask`, `/fm2`, `/docs` |
| **Summarise** combustion science investigations | 21 NASA investigations, each with objective, fuels and samples, test conditions, variables, measurements, hardware, status and sources | `/investigations`, `GET /api/investigations` |
| **Rank** them | Ranked by relevance to five habitat types, with the reason behind every point of the score | `/investigations` ("Most relevant to your habitat"), `GET /api/investigations/rank` |
| **Interpret** them for fire safety | Material-by-material verdicts for a habitat atmosphere (Habitat Review); a gap analysis of what has and hasn't been tested (Evidence Ledger); partial-gravity findings and FM2 hypotheses | `/review`, `/`, `/fm2` |
| **SI (AI)-powered** | Gemini explains Habitat Review verdicts and answers free-text questions on the Ask page. Both are shown only after a verifier checks every number and citation against the NASA evidence | `/review`, `/ask` |
| Identify investigations relevant to spacecraft, space stations, lunar and Martian bases, and pressurized rovers | The habitat selector covers exactly these five | `/investigations` |
| Extract data that supports predictive modelling | Every dataset as JSON or CSV, with sources kept on every record; a "Data for modellers" guide | `/investigations#h-data`, `/api/ledger.csv`, `/api/gravity-profile` |
| Highlight research for next-generation fire safety equipment | Detection (SAME, SAME-R, DAFT) and suppression (FLEX, BASS, water mist) are tagged and filterable, alongside prevention | `/investigations` area filter |
| Fire safety on Earth (optional) | Seven sourced Earth applications: water-mist extinguishers, smoke detectors, firefighter air tanks and clothing, fuel models | `/investigations#h-earth` |

## 2. Potential considerations

| Consideration | Covered by |
|---|---|
| Audience: professors, students, researchers, engineers | Plain-English summaries with full technical detail on demand; open API for researchers |
| Experimental objectives | "Objective" on every investigation card |
| Fuels, including sample shape and size | "Fuels and samples" field (for example BASS's 41 samples: flat samples, spheres and candles; Saffire-I's 0.4 m by 1 m fabric) |
| Test conditions such as oxygen and air flow | "Test conditions" field, plus O2, pressure and flow regime on every ledger row |
| Variables: how tests within an investigation differ | "Variables" field |
| Sensors and measurements | "Measurements" field |
| Similarities and differences between investigations | Compare two or three investigations side by side; identical fields are highlighted, and shared areas, relevance tags and hardware are listed |
| Other PSI investigations (DAFT, BRE, ACME) | All included; ACME's six experiments are listed individually |
| Hardware (MSG, CIR, MDCA, SPICE duct) | "Hardware" field; compare shows shared hardware |
| Oxygen tested versus planned atmospheres | Oxygen coverage map on `/investigations`: each investigation's sourced oxygen range against the ISS, Moon base, lunar habitat and spacesuit atmospheres; the caption is computed from the data |
| Spacesuits and oxygen concentration (100% O2 at 4.3 psi; Moon base ≥30% O2 at ≤10.2 psi) | Habitat Review presets for EVA suits, the Moon base from the challenge brief, NASA's lunar habitat (34% O2, 8.2 psia) and the four FM2 test atmospheres |
| Highest-oxygen microgravity tests (CFI-G, up to 85% O2) | CFI-G card, tagged "habitat atmosphere" |
| Partial-gravity data (LUCI, FM2, E-FIELD) | LUCI, FM2 and E-FIELD cards tagged "partial gravity"; the FM2 page; drop-tower lunar and Mars limits in the ledger |
| The challenge brief suggests (paraphrased) that microgravity and normal-gravity results may span intermediate gravity levels | We show what NASA's own drop-tower data adds: for all three materials tested at four gravity levels, the lunar limit was below both the 0g and the 1g limit (NTRS 20130010991, Table I). This is a short-duration ground-test result, and FM2 will give the first long-duration lunar data. |

## 3. Gaps we found in our first version, and how we closed them

| Gap | Fix |
|---|---|
| The app was built around **materials**, while the challenge centres on **investigations** | New Investigations Explorer with 21 investigations |
| No ranking of investigations | Habitat relevance ranking with visible weights and reasons |
| Prevention only; no detection or suppression | Detection and suppression investigations added and filterable |
| No way to compare investigations | Side-by-side compare with similarities |
| AI only explained verdicts | New Ask page: free-text questions answered from the evidence and fact-checked |
| No Earth applications | "Fire safety on Earth" section |
| Data exports not presented for modellers | "Data for modellers" section |
| No overview of oxygen levels tested | Oxygen coverage map |
| Results could not be shared | Every view keeps its state in the URL, with a "Copy link" button |
| Catalogue not downloadable | `GET /api/investigations.csv` |
| 7 materials | 15 materials, all checked against NASA PDFs |

## 4. Sources for the investigation catalogue

All in `data/investigations.json`, each field with its source and page:

- the challenge statement and its Resources tab (spaceappschallenge.org);
- NASA Glenn Research Center, *Combustion Science* page;
- NASA, *A Researcher's Guide to: Combustion Science* (ISS Researcher's Guide Series, 2015);
- NASA Glenn fact sheets: BASS, Saffire, FLEX, SAME, DAFT, SPICE, SLICE, ACME;
- NASA Spinoff pages: firefighter air tanks, fire detector, firefighter clothing.

Every quote was checked word for word against the source text (see `docs/EVIDENCE_AUDIT.md`, section F).

## 5. Still open (honest limits)

- **PSI data files are not parsed.** We link each investigation to a NASA PSI search, but summaries come from NASA's fact sheets and guide, not from the raw PSI datasets.
- **Some fields say "Not yet summarised"** (for example LUCI, SAME-R and FLARE details) where our sources didn't give the information. We don't guess.
- **Ranking weights are our own research settings**, shown openly and labelled "not NASA criteria".
- **Ask** answers only from the catalogue and ledger. Questions outside them get a plain "not covered" plus the closest evidence.
