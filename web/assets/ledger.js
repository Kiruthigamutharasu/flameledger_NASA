import { $, h, s, getJSON, ENV, MEASURE, num, pct, signed, sourceLink, tip, showError, fillBuildInfo, linear } from "/static/common.js";

const psia = (v) => (v === null || v === undefined ? "not in ledger" : `${num(v)} psia`);

function table(headers, rows) {
  return h("table", {},
    h("thead", {}, h("tr", {}, headers.map((t) => h("th", { scope: "col", text: t })))),
    h("tbody", {}, rows.map((cells) => h("tr", {}, cells.map((c) => (c instanceof Node && c.tagName === "TH" ? c : h("td", {}, c)))))));
}

function renderMetrics(m) {
  const tile = (value, of, label, gap) => h("div", { class: gap ? "tile gap" : "tile" },
    h("div", { class: "num" }, String(value), of !== null ? h("span", { class: "of", text: ` of ${of}` }) : null),
    h("div", { class: "lab", text: label }));
  $("#metrics").replaceChildren(
    tile(m.materials, null, "materials in the ledger"),
    tile(m.with_1g, m.materials, "have a normal-gravity (1g) result"),
    tile(m.with_microgravity, m.materials, "have microgravity evidence"),
    tile(m.with_partial_gravity, m.materials, "have any lunar or Mars gravity data"),
    tile(m.with_published_margin, m.materials, "have a published margin against 1g"),
    tile(m.with_long_duration_lunar, m.materials, "have long-duration lunar-gravity data. FM2 plans the first.", true),
    tile(m.cells_empty, m.cells_total, "material and environment pairs have no data", true),
    tile(m.evidence_rows, null, `verified evidence rows from ${m.sources} NASA documents`));
}

function renderGrid(cov, rowsById) {
  const detail = $("#cell-detail");
  let pressed = null;

  const open = (material, env, cell, btn) => {
    if (pressed) pressed.setAttribute("aria-pressed", "false");
    pressed = btn; btn.setAttribute("aria-pressed", "true");
    const rows = cell.row_ids.map((id) => rowsById.get(id)).filter(Boolean);
    detail.replaceChildren(h("div", { class: "card stack" },
      h("h3", { text: `${material.material}: ${env.label}` }),
      h("p", { class: "small", text: env.description }),
      h("div", { class: "scroll" }, table(
        ["Measure", "Value", "Pressure", "Sample and facility", "Flow", "Source", "Quote and caveat"],
        rows.map((r) => [
          MEASURE[r.measure] || r.measure,
          h("span", { class: "num-col", text: r.o2_pct === null ? `${r.outcome} (qualitative)` : pct(r.o2_pct) }),
          h("span", { class: "num-col", text: psia(r.pressure_psia) }),
          `${r.form}. ${r.facility}`,
          r.flow_note,
          sourceLink(r.source_id, r.source_url, r.location),
          h("span", {}, h("span", { class: "quote", text: r.short_quote }), ` ${r.caveat}`),
        ])))));
    detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const body = cov.materials.map((material) => h("tr", {},
    h("th", { scope: "row", text: material.material }),
    cov.environments.map((env) => {
      const cell = material.cells[env.id];
      const kids = [
        h("span", { class: "k", text: { data: "Measured", qualitative: "Qualitative", planned: "Planned", none: "Gap" }[cell.status] }),
        h("span", { class: "v", text: cell.summary }),
        cell.sources.length ? h("span", { class: "s", text: cell.sources.map((x) => x.source_id.replace("NTRS-", "NTRS ")).join(", ") }) : null,
      ];
      const cls = `cell ${cell.status} env-${ENV[env.id].cls}`;
      if (cell.status === "none") return h("td", {}, h("div", { class: cls }, kids));
      const btn = h("button", { class: cls, type: "button", "aria-pressed": "false",
        "aria-label": `${material.material}, ${env.label}: ${cell.summary}. Show evidence.` }, kids);
      btn.addEventListener("click", () => open(material, env, cell, btn));
      return h("td", {}, btn);
    })));

  $("#grid").replaceChildren(h("table", { class: "grid-table" },
    h("caption", { class: "skip", text: "Evidence coverage by material and test environment" }),
    h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "Material" }),
      cov.environments.map((e) => h("th", { scope: "col", text: e.label, title: e.description })))),
    h("tbody", {}, body)));

  const m = cov.metrics;
  $("#grid-caption").textContent =
    `${m.cells_empty} of ${m.cells_total} cells are empty, and the empty cells are the finding: for those pairs we found no published value we could verify. ` +
    `Lunar and Mars values are short-duration ground tests. ` +
    (m.rows_held_back ? `${m.rows_held_back} row is held back until its source can be checked publicly.` : "");
}

function renderPmma(rowsById, margins) {
  const box = $("#pmma-chart");
  const one = rowsById.get("E1"), zero = rowsById.get("E2"), margin = margins.find((x) => x.margin_id === "E3");
  if (!one || !zero || !margin) { box.replaceChildren(h("p", { class: "small", text: "This comparison is not available in the current ledger." })); return; }

  const W = 560, H = 176, L = 190, R = 520;
  const top = Math.ceil(Math.max(one.o2_pct, zero.o2_pct) / 5) * 5;
  const x = linear(0, top, L, R);
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `PMMA quarter-inch rod. 1g blowoff limit ${pct(one.o2_pct)}. Steady flame spread on the ISS at ${pct(zero.o2_pct)}. Published margin ${signed(margin.margin_pct_o2)}% O2.` });
  for (let t = 0; t <= top; t += 5) {
    svg.append(s("line", { class: "gridline", x1: x(t), x2: x(t), y1: 14, y2: 128 }),
      s("text", { x: x(t), y: 144, "text-anchor": "middle", text: String(t) }));
  }
  svg.append(s("text", { x: (L + R) / 2, y: 166, "text-anchor": "middle", text: "Oxygen concentration (% O2)" }));
  const bars = [[one, "1g blowoff limit", "Normal gravity", "f-1g", 24], [zero, "Steady flame spread", "Space Station (BASS-II)", "f-micro", 70]];
  for (const [row, title, subtitle, cls, y] of bars) {
    const rect = s("rect", { class: cls, x: L, y, width: x(row.o2_pct) - L, height: 26, rx: 4 });
    tip(rect, `${title}: ${pct(row.o2_pct)}\n${row.flow_note}\n${row.source_id}, ${row.location}`);
    svg.append(rect,
      s("text", { class: "lab-strong", x: L - 10, y: y + 12, "text-anchor": "end", text: title }),
      s("text", { x: L - 10, y: y + 26, "text-anchor": "end", text: subtitle }),
      s("text", { class: "val", x: x(row.o2_pct) + 8, y: y + 18, text: `${num(row.o2_pct)}%` }));
  }
  const y = 116, a = x(zero.o2_pct), b = x(one.o2_pct);
  svg.append(s("line", { class: "zero", x1: a, x2: b, y1: y, y2: y }),
    s("line", { class: "zero", x1: a, x2: a, y1: y - 5, y2: y + 5 }), s("line", { class: "zero", x1: b, x2: b, y1: y - 5, y2: y + 5 }),
    s("text", { class: "val", x: a - 8, y: y + 4, "text-anchor": "end", text: `published margin ${signed(margin.margin_pct_o2)}% O2` }),
    s("line", { class: "axis", x1: L, x2: L, y1: 14, y2: 128 }));
  box.replaceChildren(svg);

  $("#pmma-caption").replaceChildren(
    h("span", { class: "quote", text: margin.short_quote }), " ",
    sourceLink(margin.source_id, margin.source_url, margin.location), ". ",
    `Published by NASA authors. ${margin.caveat}`);
}

function renderPunchline(rowsById, margins) {
  const one = rowsById.get("E1"), zero = rowsById.get("E2"), m = margins.find((x) => x.margin_id === "E3");
  if (!one || !zero || !m) return;
  $("#punchline").replaceChildren(
    h("span", { class: "punch-big", text: `${num(zero.o2_pct)}% O2` }),
    h("span", {}, ` A PMMA rod kept burning on the Space Station at ${num(zero.o2_pct)}% oxygen, below its ${num(one.o2_pct)}% Earth-gravity blowoff limit: a published margin of ${signed(m.margin_pct_o2)}% O2. `,
      sourceLink(m.source_id, m.source_url, m.location)));
}

function renderMargins(margins) {
  const data = [...margins].sort((p, q) => p.margin_pct_o2 - q.margin_pct_o2);
  const W = 560, L = 176, R = 500, rowH = 28, top = 8;
  const H = top + data.length * rowH + 44;
  const lo = Math.floor(Math.min(...data.map((d) => d.margin_pct_o2), 0));
  const hi = Math.ceil(Math.max(...data.map((d) => d.margin_pct_o2), 1));
  const x = linear(lo, hi, L, R);
  const bottom = top + data.length * rowH;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `Ranked published oxygen margins. Most negative: ${data[0].material}, ${ENV[data[0].environment].label}, ${signed(data[0].margin_pct_o2)}% O2.` });
  for (let t = lo; t <= hi; t += 1) {
    svg.append(s("line", { class: t === 0 ? "zero" : "gridline", x1: x(t), x2: x(t), y1: top, y2: bottom }),
      s("text", { x: x(t), y: bottom + 16, "text-anchor": "middle", text: signed(t) }));
  }
  svg.append(s("text", { x: (L + R) / 2, y: bottom + 36, "text-anchor": "middle", text: "Published margin against the 1g limit (% O2)" }));
  data.forEach((d, i) => {
    const y = top + i * rowH + 4, v = d.margin_pct_o2;
    const x0 = Math.min(x(0), x(v)), w = Math.max(2, Math.abs(x(v) - x(0)));
    const rect = s("rect", { class: `f-${ENV[d.environment].cls}`, x: x0, y, width: w, height: rowH - 8, rx: 4 });
    tip(rect, `${d.material}, ${ENV[d.environment].label}\nPublished margin ${signed(v)}% O2\n${d.source_id}, ${d.location}`);
    svg.append(rect,
      s("text", { class: "lab-strong", x: L - 82, y: y + 14, "text-anchor": "end", text: d.material }),
      s("text", { x: L - 8, y: y + 14, "text-anchor": "end", text: ENV[d.environment].short }),
      s("text", { class: "val", x: Math.max(x(0), x(v)) + 6, y: y + 14, text: signed(v) }));
  });
  $("#margin-chart").replaceChildren(svg);

  $("#margin-table").replaceChildren(table(
    ["Material", "Environment", "Margin", "How the authors defined it", "Source", "Caveat"],
    data.map((d) => [d.material, ENV[d.environment].label,
      h("span", { class: "num-col", text: `${signed(d.margin_pct_o2)}% O2` }), d.basis,
      sourceLink(d.source_id, d.source_url, d.location), d.caveat])));
}

function renderSources(sources, rows) {
  $("#source-table").replaceChildren(table(["Document", "Authors", "Year", "Venue", "Links"],
    sources.map((x) => [x.title, x.authors, x.year, x.venue,
      h("span", {}, x.landing_url ? h("a", { href: x.landing_url, target: "_blank", rel: "noopener noreferrer", text: x.source_id.replace("NTRS-", "NTRS ") }) : x.source_id,
        " · ", h("a", { href: x.pdf_url, target: "_blank", rel: "noopener noreferrer", text: "PDF" }))])));
  $("#row-table").replaceChildren(table(["Row", "Subject", "Environment", "Measure", "Value", "Pressure", "Source", "Quote"],
    rows.map((r) => [r.row_id, r.material, ENV[r.environment].label, MEASURE[r.measure] || r.measure,
      h("span", { class: "num-col", text: r.o2_pct === null ? "qualitative" : pct(r.o2_pct) }),
      h("span", { class: "num-col", text: psia(r.pressure_psia) }),
      sourceLink(r.source_id, r.source_url, r.location), h("span", { class: "quote", text: r.short_quote })])));
}

async function main() {
  fillBuildInfo();
  try {
    const [cov, rows, margins, sources] = await Promise.all([
      getJSON("/api/coverage"), getJSON("/api/ledger"), getJSON("/api/margins"), getJSON("/api/sources")]);
    const rowsById = new Map(rows.map((r) => [r.row_id, r]));
    renderMetrics(cov.metrics);
    renderGrid(cov, rowsById);
    renderPmma(rowsById, margins);
    renderPunchline(rowsById, margins);
    renderMargins(margins);
    renderSources(sources, rows);
  } catch (err) {
    showError($("#metrics"), err);
    $("#grid").replaceChildren();
  }
}
main();
