import { $, h, s, getJSON, ENV, num, pct, sourceLink, tip, showError, fillBuildInfo, linear } from "/static/common.js";

const FINDING_TITLES = {
  E9: "Earth tests can overstate the oxygen a flame needs",
  E10: "Below Earth's gravity, some materials burn more readily",
  E11: "Partial gravity is expected to raise flammability for some materials",
};

function renderFindings(rows) {
  const cards = Object.keys(FINDING_TITLES).map((id) => rows.find((r) => r.row_id === id)).filter(Boolean).map((r) =>
    h("div", { class: "card stack" },
      h("h3", { text: FINDING_TITLES[r.row_id] }),
      h("p", {}, h("span", { class: "quote", text: r.short_quote })),
      h("p", { class: "small" }, sourceLink(r.source_id, r.source_url, r.location), `. ${r.caveat}`)));
  $("#findings").replaceChildren(...(cards.length ? cards : [h("p", { class: "small", text: "No findings are available in the current ledger." })]));
}

function renderProfile(profile) {
  const lede = $("#profile-lede");
  if (!profile.n_materials) { lede.textContent = "No material in the ledger has published limits at all four gravity levels."; return; }
  lede.textContent = `For ${profile.n_lunar_below_both} of ${profile.n_materials} materials with published limits at all four gravity levels, ` +
    "the lunar-gravity limit is lower than both the microgravity limit and the normal-gravity limit. A lower limit means the flame survives in thinner oxygen.";

  const all = profile.materials.flatMap((m) => m.points.map((p) => p.moc_pct_o2));
  const lo = Math.floor(Math.min(...all)) - 1, hi = Math.ceil(Math.max(...all)) + 1;
  const W = 280, H = 226, L = 40, R = 262, T = 26, B = 172;
  const x = linear(0, 1, L + 8, R - 8), y = linear(lo, hi, B, T);

  const panels = profile.materials.map((m) => {
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
      "aria-label": `${m.material}: ` + m.points.map((p) => `${p.label} ${pct(p.moc_pct_o2)}`).join(", ") });
    for (let t = Math.ceil(lo / 2) * 2; t <= hi; t += 2) {
      svg.append(s("line", { class: "gridline", x1: L, x2: R, y1: y(t), y2: y(t) }),
        s("text", { x: L - 6, y: y(t) + 4, "text-anchor": "end", text: String(t) }));
    }
    svg.append(s("text", { x: L - 30, y: 12, text: "Limit, % O2" }));
    const pts = [...m.points].sort((a, b) => a.gravity_g - b.gravity_g);
    svg.append(s("polyline", { class: "link", points: pts.map((p) => `${x(p.gravity_g)},${y(p.moc_pct_o2)}`).join(" ") }));
    for (const p of pts) {
      const cx = x(p.gravity_g), cy = y(p.moc_pct_o2), env = ENV[p.environment];
      svg.append(s("circle", { class: `f-${env.cls} ring`, cx, cy, r: 6 }),
        s("text", { class: "val", x: cx, y: cy - 11, "text-anchor": "middle", text: num(p.moc_pct_o2) }),
        s("text", { x: cx, y: B + 18, "text-anchor": "middle", text: env.short }),
        s("text", { x: cx, y: B + 32, "text-anchor": "middle", text: `${num(p.gravity_g)}g` }));
      const hit = s("circle", { class: "hit", cx, cy, r: 14 });
      tip(hit, `${m.material}, ${p.label}\nSelf-extinguished at ${pct(p.moc_pct_o2)}; burned at ${pct(p.uloi_pct_o2)}\n${m.source_id}, ${m.location}`);
      svg.append(hit);
    }
    svg.append(s("line", { class: "axis", x1: L, x2: R, y1: B, y2: B }),
      s("text", { x: (L + R) / 2, y: H - 4, "text-anchor": "middle", text: "Gravity level (Earth = 1g)" }));
    return h("div", { class: "card" },
      h("p", { class: "panel-title", text: m.material }),
      h("p", { class: "small", text: `Tested at ${num(m.pressure_psia)} psia` }),
      h("div", { class: "chart" }, svg),
      h("p", { class: "verdict-line", text: m.lunar_below_both
        ? "Lunar limit is below both the microgravity and the 1g limit."
        : "Lunar limit is not below both the microgravity and the 1g limit." }),
      h("p", { class: "small" }, sourceLink(m.source_id, m.source_url, m.location)));
  });
  $("#profile").replaceChildren(...panels);

  $("#profile-caption").textContent = `${profile.measure_note} ${profile.materials[0].points.find((p) => p.environment === "lunar").caveat} ` +
    "The grey lines only join the published points. They are not a model and must not be used to estimate limits at other gravity levels.";

  const order = ["microgravity", "lunar", "mars", "1g"];
  $("#profile-table").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "Material" }), h("th", { scope: "col", text: "Pressure" }),
      order.map((e) => h("th", { scope: "col", text: `${ENV[e].label}: self-extinguished / burned` })), h("th", { scope: "col", text: "Source" }))),
    h("tbody", {}, profile.materials.map((m) => h("tr", {},
      h("th", { scope: "row", text: m.material }), h("td", { class: "num-col", text: `${num(m.pressure_psia)} psia` }),
      order.map((e) => { const p = m.points.find((q) => q.environment === e);
        return h("td", { class: "num-col", text: `${num(p.moc_pct_o2)}% / ${num(p.uloi_pct_o2)}% O2` }); }),
      h("td", {}, sourceLink(m.source_id, m.source_url, m.location)))))));
}

function renderFm2(rows, coverage) {
  const mission = rows.find((r) => r.row_id === "E12");
  const target = rows.find((r) => r.row_id === "E18");
  const tests = rows.filter((r) => r.evidence_id === "E13").sort((a, b) => b.o2_pct - a.o2_pct);
  const about = $("#fm2-about");
  if (!mission || !tests.length) { about.replaceChildren(h("p", { class: "small", text: "FM2 details are not available in the current ledger." })); return; }

  about.replaceChildren(
    h("h3", { text: "What FM2 will do" }),
    h("p", {}, "NASA's Flammability of Materials on the Moon experiment plans to burn ",
      h("span", { class: "quote", text: mission.short_quote }), ". ", sourceLink(mission.source_id, mission.source_url, mission.location)),
    h("p", {}, `Fuel: ${tests[0].material} (${tests[0].form}). ${tests[0].flow_note}.`),
    h("table", {},
      h("thead", {}, h("tr", {}, ["Test", "Atmosphere", "NASA's stated expectation"].map((t) => h("th", { scope: "col", text: t })))),
      h("tbody", {}, tests.map((t) => h("tr", {},
        h("th", { scope: "row", text: t.row_id.replace("E13.t", "Test ") }),
        h("td", { class: "num-col", text: `${pct(t.o2_pct)} at ${num(t.pressure_psia)} psia` }),
        h("td", {}, h("span", { class: "quote", text: t.short_quote })))))),
    h("p", { class: "small" }, sourceLink(tests[0].source_id, tests[0].source_url, tests[0].location), ". No FM2 result exists yet."),
    target ? h("p", { class: "small" }, "NASA's design concept: ", h("span", { class: "quote", text: target.short_quote }), ". ",
      sourceLink(target.source_id, target.source_url, target.location), `. ${target.caveat}`) : null);

  // Number line of planned test atmospheres, with reference atmospheres from the ledger.
  const refs = [["E16", "Nominal lunar habitat"], ["E17", "Historical Test 1 atmosphere"]]
    .map(([id, label]) => [rows.find((r) => r.row_id === id), label]).filter(([r]) => r && r.o2_pct !== null);
  const values = [...tests.map((t) => t.o2_pct), ...refs.map(([r]) => r.o2_pct)];
  const lo = Math.floor((Math.min(...values) - 1) / 5) * 5, hi = Math.ceil((Math.max(...values) + 1) / 5) * 5;
  const W = 560, H = 190, L = 30, R = 530, axisY = 128;
  const x = linear(lo, hi, L, R);
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": "Planned FM2 test atmospheres: " + tests.map((t) => pct(t.o2_pct)).join(", ") + `, all at ${num(tests[0].pressure_psia)} psia.` });
  svg.append(s("line", { class: "axis", x1: L, x2: R, y1: axisY, y2: axisY }));
  for (let t = lo; t <= hi; t += 5) {
    svg.append(s("line", { class: "axis", x1: x(t), x2: x(t), y1: axisY, y2: axisY + 5 }),
      s("text", { x: x(t), y: axisY + 20, "text-anchor": "middle", text: String(t) }));
  }
  svg.append(s("text", { x: (L + R) / 2, y: H - 8, "text-anchor": "middle", text: "Oxygen concentration (% O2)" }));
  refs.forEach(([r, label], i) => {
    const yTop = 14 + i * 30;
    svg.append(s("line", { class: "ref", x1: x(r.o2_pct), x2: x(r.o2_pct), y1: yTop + 6, y2: axisY }),
      s("text", { x: x(r.o2_pct) + (x(r.o2_pct) > (L + R) / 2 ? -6 : 6), y: yTop + 10, "text-anchor": x(r.o2_pct) > (L + R) / 2 ? "end" : "start", text: `${label}: ${num(r.o2_pct)}% at ${num(r.pressure_psia)} psia` }));
  });
  for (const t of tests) {
    const cx = x(t.o2_pct), name = t.row_id.replace("E13.t", "Test ");
    const dot = s("circle", { class: "planned-dot", cx, cy: axisY - 22, r: 7 });
    tip(dot, `${name}: ${pct(t.o2_pct)} at ${num(t.pressure_psia)} psia\nNASA's expectation: ${t.short_quote}\n${t.source_id}, ${t.location}`);
    svg.append(dot, s("text", { class: "val", x: cx, y: axisY - 36, "text-anchor": "middle", text: `${name.replace("Test ", "T")} · ${num(t.o2_pct)}%` }));
  }
  $("#fm2-chart").replaceChildren(svg);
  $("#fm2-caption").replaceChildren(
    `Open circles are planned tests at ${num(tests[0].pressure_psia)} psia with no result yet. Dashed lines are reference atmospheres from NASA documents `,
    ...refs.flatMap(([r]) => ["(", sourceLink(r.source_id, r.source_url, r.location), ") "]),
    "and may be at a different pressure, as labelled. Oxygen percentage alone does not define flammability.");

  const fm2Cells = coverage.materials.map((m) => [m.material, m.cells.fm2.status]);
  const planned = fm2Cells.filter(([, st]) => st === "planned").map(([name]) => name);
  const empty = fm2Cells.filter(([, st]) => st === "none").length;
  $("#fm2-cells").replaceChildren(
    h("p", { text: planned.length
      ? `FM2 will turn the "Planned" cell for ${planned.join(", ")} into the first long-duration lunar-gravity result in this ledger.`
      : "No ledger cell is currently marked as planned for FM2." }),
    h("p", { class: "small", text: `${empty} of ${fm2Cells.length} materials in the ledger have no planned long-duration lunar-gravity test that we could verify. ` +
      `${coverage.metrics.with_partial_gravity} have short-duration lunar or Mars gravity data from ground facilities.` }));
}

function renderHypotheses(data) {
  const short = data.commit === "n/a" ? "n/a" : data.commit.slice(0, 10);
  $("#hyp-meta").replaceChildren(h("div", { class: "stack" },
    h("p", {}, h("strong", { text: "Registered: " }), data.registered_on, " · ", h("strong", { text: "Git tag: " }), data.tag, " · ",
      h("strong", { text: "Commit serving this page: " }), h("span", { class: "mono", text: short })),
    h("p", { class: "small" }, "SHA-256 fingerprint of the hypothesis text: ", h("span", { class: "mono", text: data.sha256 })),
    h("p", { class: "small", text: "Anyone can recompute this fingerprint from /api/hypotheses. If a single word changes, the fingerprint changes." })));
  $("#hyp-list").replaceChildren(...data.hypotheses.map((hyp) => h("div", { class: "card hyp" },
    h("h3", { text: `${hyp.id}. ${hyp.text}` }),
    h("dl", {},
      h("dt", { text: "Basis" }), h("dd", { text: hyp.basis }),
      h("dt", { text: "Refuted if" }), h("dd", { text: hyp.refuted_if }),
      h("dt", { text: "Evidence" }), h("dd", { text: hyp.evidence_ids.join(", ") + " (see the Evidence Ledger)" })))));
}

async function section(target, loader) {
  try { await loader(); } catch (err) { showError($(target), err); }
}

async function main() {
  fillBuildInfo();
  const rowsP = getJSON("/api/ledger");
  section("#findings", async () => renderFindings(await rowsP));
  section("#profile-lede", async () => renderProfile(await getJSON("/api/gravity-profile")));
  section("#fm2-about", async () => renderFm2(await rowsP, await getJSON("/api/coverage")));
  section("#hyp-meta", async () => renderHypotheses(await getJSON("/api/hypotheses")));
}
main();
