"""PDF version of the Habitat Review report.

Uses fpdf2's built-in Helvetica, so no font files are shipped. Helvetica covers Latin-1 only,
so text is normalised (emoji become coloured markers, the minus sign becomes '-').
"""
from __future__ import annotations

from contextlib import contextmanager

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from .data import Dataset
from .report import LIMITATIONS
from .rules import DISCLAIMER as VERDICT_DISCLAIMER

COLORS = {"red": (200, 49, 43), "orange": (217, 130, 43), "green": (46, 139, 87), "grey": (138, 141, 148)}
ENV = {"1g": "Normal gravity (1g)", "microgravity": "Microgravity", "lunar": "Lunar gravity",
       "mars": "Mars gravity", "fm2": "FM2 (planned, lunar)"}
WORD = {"red": "RED", "orange": "ORANGE", "green": "GREEN", "grey": "GREY"}
TEXT = (20, 22, 26)
MUTED = (102, 106, 115)
LINK = (28, 92, 171)
_MAP = str.maketrans({"−": "-", "–": "-", "—": "-", "‑": "-", "‘": "'", "’": "'",
                      "“": '"', "”": '"', "…": "...", "≤": "<=", "≥": ">=", "✔": "",
                      " ": " "})


def latin(text) -> str:
    s = ("" if text is None else str(text)).translate(_MAP)
    s = "".join(ch for ch in s if ord(ch) < 0x2000 or ch in "€")  # drop emoji and symbols Helvetica lacks
    return s.encode("latin-1", "replace").decode("latin-1")


def _num(v) -> str:
    return "n/a" if v is None else f"{v:g}"


class _PDF(FPDF):
    def __init__(self, footer_text: str):
        super().__init__(format="A4")
        self.footer_text = latin(footer_text)
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(True, margin=20)
        self.set_title("FlameLedger Habitat Review")
        self.set_author("FlameLedger")
        self.set_creator("FlameLedger")

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", size=7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 4, self.footer_text, align="L")
        self.set_y(-14)
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="R")


@contextmanager
def _indent(pdf: FPDF, mm: float):
    base = pdf.l_margin
    pdf.set_left_margin(base + mm)
    pdf.set_x(base + mm)
    try:
        yield
    finally:
        pdf.set_left_margin(base)
        pdf.set_x(base)


def _para(pdf: FPDF, text: str, size=9.5, style="", color=TEXT, h=4.8, after=1.2):
    pdf.set_font("Helvetica", style=style, size=size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, h, latin(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if after:
        pdf.ln(after)


def _heading(pdf: FPDF, text: str, size=13, before=4):
    pdf.ln(before)
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()
    _para(pdf, text, size=size, style="B", h=6.5, after=1.5)


def _dot(pdf: FPDF, level: str, size=3.2):
    pdf.set_fill_color(*COLORS[level])
    pdf.ellipse(pdf.get_x(), pdf.get_y() + 0.9, size, size, style="F")


def _link_line(pdf: FPDF, prefix: str, label: str, url: str | None, suffix: str = "", size=8.5):
    pdf.set_font("Helvetica", size=size)
    pdf.set_text_color(*TEXT)
    if prefix:
        pdf.write(4.4, latin(prefix))
    if url:
        pdf.set_text_color(*LINK)
        pdf.set_font("Helvetica", style="U", size=size)
        pdf.write(4.4, latin(label), link=url)
        pdf.set_font("Helvetica", size=size)
        pdf.set_text_color(*TEXT)
    else:
        pdf.write(4.4, latin(label))
    if suffix:
        pdf.write(4.4, latin(suffix))
    pdf.ln(5)


def build_pdf(review: dict, ai: dict | None, ai_status: str, ai_note: str, dataset: Dataset,
              disclaimer: str, generated: str, commit: str) -> bytes:
    pdf = _PDF(disclaimer)
    pdf.add_page()
    h, th = review["habitat"], review["thresholds"]

    # ---- title block ----
    _para(pdf, "FlameLedger Habitat Review", size=20, style="B", h=9, after=1)
    _para(pdf, f"Generated {generated} UTC  |  commit {commit[:12]}", size=8.5, color=MUTED, after=3)
    pdf.set_fill_color(253, 243, 220)
    pdf.set_draw_color(226, 182, 74)
    pdf.set_font("Helvetica", style="B", size=9.5)
    pdf.set_text_color(*TEXT)
    pdf.multi_cell(0, 7, latin(VERDICT_DISCLAIMER + " Always consult the original NASA documents."),
                   border=1, fill=True, padding=(0, 3), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ---- habitat ----
    _heading(pdf, "Habitat")
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(*TEXT)
    pdf.set_draw_color(217, 215, 207)
    with pdf.table(col_widths=(30, 32, 28, 90), text_align="LEFT", line_height=5.5,
                   first_row_as_headings=True) as t:
        t.row([latin(x) for x in ("O2 (%)", "Pressure (psia)", "Gravity (g)", "Habitat")])
        t.row([_num(h["o2_pct"]), _num(h["pressure_psia"]), _num(h["gravity_g"]),
               latin(f"{h['label']} ({h['gravity_label']})")])
    pdf.ln(2)
    if h.get("source_note"):
        _link_line(pdf, "Preset source: ", h["source_note"].strip(), h.get("source_url"))
    _para(pdf, f"Thresholds ({th['label']}): a reduced-gravity burn at up to habitat O2 + "
               f"{_num(th['red_o2_tolerance_pct'])}% O2 is red; a published margin below "
               f"{_num(th['thin_margin_pct_o2'])}% O2 is thin.", size=8.5, color=MUTED)

    # ---- verdict summary ----
    _heading(pdf, "Verdicts")
    pdf.set_font("Helvetica", size=8.5)
    with pdf.table(col_widths=(46, 46, 88), text_align="LEFT", line_height=4.8, first_row_as_headings=True) as t:
        t.row(["Material (as entered)", "Ledger material", "Headline verdict"])
        for v in review["verdicts"]:
            lvl = v["headline"]["level"]
            row = t.row()
            row.cell(latin(v["input"]))
            row.cell(latin(v["material"] or "not in ledger"))
            row.cell(latin(f"{WORD[lvl]}: {v['headline']['label']}"),
                     style=FontFace(emphasis="BOLD", color=COLORS[lvl]))

    # ---- AI explanation ----
    _heading(pdf, "AI explanation")
    if ai:
        _para(pdf, "Verified: every number and source was checked against the evidence rows.",
              size=8.5, style="B", color=COLORS["green"])
        _para(pdf, ai["summary"])
    else:
        _para(pdf, f"{ai_note} The deterministic verdicts in this report are complete without it.", color=MUTED)
    explanations = {pm["material_id"]: pm["explanation"] for pm in (ai or {}).get("per_material", [])}

    # ---- per material ----
    cited: set[str] = set()
    for v in review["verdicts"]:
        _heading(pdf, v["input"] + (f"  ({v['material']})" if v["material"] and v["material"].lower() != v["input"].lower() else ""), size=11.5, before=5)
        for x in v["verdicts"]:
            _dot(pdf, x["level"])
            with _indent(pdf, 5.5):
                _para(pdf, f"{WORD[x['level']]}: {x['label']}", size=9.5, style="B", color=COLORS[x["level"]], after=0)
                _para(pdf, x["reason"], size=9)
        if v["key"] in explanations:
            _para(pdf, "AI explanation (verified): " + explanations[v["key"]], size=9, style="I")
        if v["missing"]:
            _para(pdf, "What is missing", size=8.5, style="B", color=MUTED, after=0)
            for m in v["missing"]:
                _para(pdf, "- " + m, size=8.5, after=0)
            pdf.ln(1.2)
        if v["evidence"]:
            _para(pdf, "Evidence used", size=8.5, style="B", color=MUTED, after=0)
            for e in v["evidence"]:
                cited.add(e["source_id"])
                value = (f"published margin {_num(e['margin_pct_o2'])}% O2" if e["kind"] == "margin"
                         else f"{_num(e.get('o2_pct'))}% O2 ({e.get('outcome')})" if e.get("o2_pct") is not None
                         else f"{e.get('outcome')} (qualitative)")
                pressure = f", {_num(e['pressure_psia'])} psia" if e.get("pressure_psia") else ""
                _link_line(pdf, f"- {e['id']}: {ENV.get(e['environment'], e['environment'])}, {value}{pressure}. Source: ",
                           f"{e['source_id']}, {e['location']}", e["source_url"], f'.  "{e["short_quote"]}"')
            pdf.ln(0.6)
        _para(pdf, "Caveats", size=8.5, style="B", color=MUTED, after=0)
        for c in v["caveats"]:
            src = c.get("source")
            if src:
                cited.add(src["source_id"])
                _link_line(pdf, f"- {c['text']} Source: ", f"{src['source_id']}, {src['location']}", src["source_url"])
            else:
                _para(pdf, "- " + c["text"], size=8.5, after=0)

    # ---- sources and limitations ----
    _heading(pdf, "Sources", before=6)
    for sid in sorted(cited):
        src = dataset.source(sid)
        if src:
            _link_line(pdf, f"- {src.short_cite}. {src.title}. {src.venue}. ", src.source_id.replace("NTRS-", "NTRS "),
                       src.landing_url or src.pdf_url)
    _heading(pdf, "Limitations")
    for item in LIMITATIONS:
        _para(pdf, "- " + item, size=8.5, after=0.4)
    pdf.ln(3)
    _para(pdf, disclaimer, size=8.5, style="B", color=MUTED)
    return bytes(pdf.output())
