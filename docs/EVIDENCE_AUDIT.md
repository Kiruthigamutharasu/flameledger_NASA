# Evidence audit: every source read from the NASA PDF (15 Nov 2026)

Method: each PDF was downloaded from ntrs.nasa.gov and its text extracted with pypdf. Every value below was matched to the extracted text. "PDF p." is the page number in the file; "printed p." is the number printed on the page, where one exists.
Nothing below is inferred. Wherever the paper's own caveats apply, they are quoted or paraphrased.

## A. Seed rows E1–E14

| Row | Status | Where found | Notes / corrections |
|---|---|---|---|
| E1 | ✅ verified | NTRS 20160000593, PDF p.18 | Exact text: "The 1g blowoff for the ¼" rod is at 16% oxygen". **Citation fix:** the document is a poster, *Combustion of Solids in Microgravity: Results from the BASS-II Experiment* (Ferkul, Bhattacharjee, Fernandez-Pello, Miller, Olson, Takahashi, T'ien; ASGSR 2014). The p.18 panel is by Sandra Olson. |
| E2 | ✅ verified | same, PDF p.18 | "we obtained steady spreading at 13.6% oxygen in BASS-II". The flow is concurrent (stagnation-point) flow in a wind tunnel, not cabin ventilation. |
| E3 | ✅ verified | same, PDF p.18 | "negative Oxygen Margin of Safety of 2.4% O2"; "should be de-rated by at least that much". |
| E4 | ✅ verified | NTRS 20110008636, Table 2, printed p.5 | Extruded PMMA ¼-in rod, chemical igniter: ULOI 19.5, MOC 19. Tested at 14.7 psia, upward, quiescent, Test 1 burn-length criterion. |
| E5 | ✅ verified | same, Table 2, p.5 | Same rod, hot-wire igniter: ULOI 18.9, MOC 18. |
| E6 | ✅ verified | same, Table 7, printed p.7 | Cast PMMA ¼-in rod, hot-wire: ULOI 15.7, MOC 14. Cast with chemical igniter: "Testing in progress" (no value). |
| E7 | ✅ verified | same, Table 2, p.5 | Silicone MQ 0.040 in: chemical 23.4 / 22, hot-wire 22.5 / 21. |
| E8 | ✅ verified | NTRS 20130012832, PDF p.25 and p.33 | SIBAL = 75% cotton / 25% fiberglass. Steady opposed-flow spread in microgravity. "in normal gravity air, a flame self-extinguishes in the opposed flow geometry". No O2 limit value is quoted. |
| E9 | ✅ verified | NTRS 20080034883, PDF p.5 | "greater than those in 0g, by up to 4% oxygen mole fraction" (Olson, Ruff, Miller). |
| E10 | ✅ verified | NTRS 20130010991, PDF p.1 | "a gravity level below Earth's at which materials burn more readily". **The same paper contains numbers, see N1.** |
| E11 | ✅ verified | NTRS 20260000646, PDF p.1 | "certain partial-g environments are expected to increase the flammability limits for some materials". |
| E12 | ✅ verified | same, PDF p.1 | "four solid fuel samples in quiescent habitable atmospheres in actual long duration Lunar gravity"; "planned launch date of late 2026". |
| E13 | ✅ verified (extended) | NTRS 20260001966, PDF p.10 (and p.5) | **All four FM2 tests** at 8.2 psia ±0.3: Test 1 = 37%, Test 2 = 33%, Test 3 = 29%, Test 4 = 25% O2. Fabric "Synergy Pro Navy", 2 × 20 cm, hot-wire, upward. p.5: Tests 1–3 "should burn to threshold"; Test 4 "not expected to ignite". |
| E14 | ❌ **link fails** | istina.msu.ru | The URL opens a **login page**, which breaks the "public, no login" rule. The claim must not be shown until it's re-sourced to a public paper, preferably on NTRS. |

## B. New evidence in the same NASA documents (proposed E15+)

| ID | Fact | Source | Caveats that must be shown with it |
|---|---|---|---|
| N1 | **Measured partial-gravity limits.** Table I, "Limiting Oxygen Molar Concentrations and Oxygen Margin of Safety for Different Gravity Levels": see table below | NTRS 20130010991, Table I, printed p.6 | Drop-tower centrifuge tests. "low g extinction limit criteria are not the same as 1g due to time constraints in drop testing" (p.1). Concurrent (upward) flow. The paper says its lunar and 0g values come from its ref. 8. |
| N2 | Lunar-surface habitat (HLS), lunar habitat and pressurized rover "will nominally use 8.2 psia / 34% O2", with control bands "up to 37% O2" | NTRS 20260001966, PDF p.25 | These are planning values from NASA slides, not a requirement document. |
| N3 | EVA suit: 100% O2, 4.3 psia | NTRS 20260001966, PDF p.25 | Confirms the challenge-brief spacesuit preset. |
| N4 | Test 1 is "an upward burning test at the worst-case atmospheric conditions", historically 30% O2 / 10.2 psia. A sample that burns more than 15 cm fails | NTRS 20260001966, PDF p.27 | Context only. |
| N5 | FM2 design target: material "with an expected Lunar LOC of 24-26%" | NTRS 20260001966, PDF p.5 | This is NASA's own design expectation, shown as a quote with its source. It is **not** a FlameLedger prediction. |

### N1: Table I values (% O2, molar)

| | Mylar G (10.2 psia) | Ultem 1000 (10.2 psia) | Nomex HT90-40 (14.7 psia) |
|---|---|---|---|
| 1g ULOI | 21.2 | 23.5 | 23.5 |
| 1g MOC | 20.0 | 23.0 | 22.1 |
| Martian ULOI* | 18.0 | 22.0 | 19.9 |
| Martian MOC* | 17.0 | 21.1 | 19.0 |
| Lunar ULOI* | 15.6 | 21.0 | 21.0 |
| Lunar MOC* | 14.1 | 19.9 | 19.9 |
| 0g* ULOI* | 17.0 | 24.0 | 23.0 |
| 0g* MOC* | 16.0 | 23.0 | 22.0 |
| Martian ΔO2 % | −3.1 | −1.7 | −3.35 |
| Lunar ΔO2 % | −5.75 | −2.8 | −2.35 |
| 0g ΔO2 % | −4.1 | 0.25 | −0.3 |

The ΔO2 margins are **published** values: (mean low-g limit) − (mean 1g limit), Eq. (1) on p.6. A negative value means the material burns at lower O2 in low gravity than in the 1g test.

## C. What this changes in the product
1. **The lunar and Mars columns of the coverage grid are no longer empty** for Mylar, Ultem and Nomex: there is short-duration drop-tower data. FM2 will be the first **long-duration** lunar-gravity test, which is the wording E12 itself uses. The claim "no partial-g data exists" must not appear anywhere.
2. **Evidence on the bracketing question.** For all three materials in N1, the lunar MOC* is below both the 0g* and the 1g MOC (Mylar 14.1 vs 16.0 / 20.0; Ultem 19.9 vs 23.0 / 23.0; Nomex 19.9 vs 22.0 / 22.1). This is direct published data showing that 0g and 1g did not bracket lunar g for these materials, under drop-tower criteria.
3. **More published margins:** PMMA rod −2.4 (ISS), plus Mylar, Ultem and Nomex at lunar, Martian and 0g* gravity (9 values). The largest is Mylar at lunar g, −5.75%.
4. **A NASA-sourced habitat preset:** "Artemis lunar habitat / rover (nominal), 34% O2 / 8.2 psia" (N2), plus "control-band max, 37% O2 / 8.2 psia".
5. **FM2 panel:** show all 4 tests. Hypothesis H3 should cite NASA's own stated expectation for Test 4 (N5 and p.5) rather than present it as original.
6. **Re-source E14** or leave it out.

## D. Not read (references only)
- Olson et al., "Partial gravity flammability of cast PMMA rods in concurrent axial stagnation flow", *Fire Safety Journal* 150 (2024) 104267. Cited on NTRS 20260001966 p.20. Not open access to us, so no values are used.

## E. Additions, 15 Nov 2026, 14:50 IST

| Row | Status | Where found | Notes |
|---|---|---|---|
| E19 | ✅ verified | NTRS 20110008636, Tables 2 and 5 (printed p.5–6), Tables 8 and 9 (printed p.7) | 1g ULOI / MOC (% O2) at 14.7 psia ("Except as noted, the tests were conducted at 14.7 psia", p.3). PI: chemical 27.2 / 26, hot-wire 28.7 / 27 (Table 2). PEEK: chemical 20.8 / 20.1, hot-wire 22 / 21.1 (Table 2). NBR: 16.6 / 16.1, standard mounting (Table 5). PVC sheet: 40.1 / 35, standard mounting (Table 5). POM (Acetron GP) 1/8-in rod: 12.9 / 12 (Table 8). PP 1/8-in rod: 17.6 / 16.0 (Table 8). PA (Nylon 101) 1/8-in rod: 21.9 / 20 (Table 8). Epoxy/glass, 2.5-in standard mounting: 23.6 / 23 (Table 9). |

Not added: PET and PEI from Table 2 (tested at 10.2 psia with the GRC hot-wire protocol). Their hot-wire values (21.3 / 20 and 23.5 / 23) almost match E15 Mylar G (a PET film) and Ultem 1000 (a PEI), so they are probably the same samples; adding them would double-count materials. The values with non-standard sample widths, thicknesses, durometers or pass/fail lengths (Tables 3, 4, 6, and the ½-in widths in Tables 8–9) are left out to keep one standard configuration per material.
No reduced-gravity value exists in the ledger for any E19 material. They appear as 1g-only rows, which widens the evidence gap shown by the coverage grid.

## F. Investigation catalogue (data/investigations.json), 15 Nov 2026, 16:00 IST

Method: the NASA PDFs (the 2015 ISS combustion Researcher's Guide and eight NASA Glenn fact sheets) were downloaded from nasa.gov and their text extracted with pypdf. Every quote taken from a PDF was matched word for word against the extracted text, after normalising ligatures and line-break hyphens. All 18 PDF quotes matched. The 7 quotes from web pages (the challenge statement and NASA Glenn's Combustion Science page) were checked by hand against the page text in a browser.

Rules applied:
- Status says "Conducted" only where a source says so (the challenge page describes the ACME, FLEX, FLEX-2 and CFI tests in the past tense); otherwise the source's own wording is used.
- Fields with no information in the sources say "Not yet summarised". Nothing was inferred, including what the "-R" in SAME-R stands for.
- Relevance tags (solid materials, air flow, habitat atmosphere, partial gravity, large scale, detection, suppression) each carry a sentence of evidence from the investigation's sources.
- Ranking weights are FlameLedger research settings, not NASA criteria, and are shown on the page.
