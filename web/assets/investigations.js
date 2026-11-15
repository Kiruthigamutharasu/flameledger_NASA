import { $, h, s, getJSON, showError, fillBuildInfo, tip, linear, setQuery, copyLinkButton } from "/static/common.js";

const REF_PRESETS = [
  ["iss_cabin", "ISS cabin"], ["moon_base_brief", "Moon base (brief)"], ["lunar_habitat_nominal", "Lunar habitat"], ["eva_suit_lunar", "Spacesuit"],
];

function renderO2(cat, presets, rows) {
  const ranged = cat.investigations.filter((i) => i.o2_range).sort((a, b) => a.o2_range.max - b.o2_range.max);
  // only measured flammability limits and observations count, never planning values such as habitat atmospheres
  const reduced = rows.filter((r) => ["microgravity", "lunar", "mars"].includes(r.environment) && r.o2_pct !== null
    && r.material_id !== "aggregate" && (r.value_kind === "limit" || r.value_kind === "observation"));
  const bars = ranged.map((i) => ({ label: i.acronym, min: i.o2_range.min, max: i.o2_range.max, note: i.o2_range.label,
    src: `${i.o2_range.source_id}, ${i.o2_range.location}`, href: `#inv-${i.id}`, cls: /planned/i.test(i.status + i.o2_range.label) ? "planned" : "inv" }));
  if (reduced.length) {
    const v = reduced.map((r) => r.o2_pct);
    bars.unshift({ label: "Ledger limits (0g, Moon, Mars)", min: Math.min(...v), max: Math.max(...v),
      note: `${reduced.length} verified reduced-gravity rows from NASA reports`, src: "Evidence Ledger", href: "/#h-grid", cls: "ledger" });
  }
  const refs = REF_PRESETS.map(([id, label]) => { const p = presets.find((x) => x.preset_id === id); return p && { label, v: p.o2_pct, note: `${p.label}: ${p.o2_pct}% O2, ${p.pressure_psia} psia` }; }).filter(Boolean);

  const W = 760, L = 220, R = 730, top = 66, rowH = 30, H = top + bars.length * rowH + 40;
  const x = linear(0, 100, L, R);
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Oxygen range reported by each investigation compared with habitat atmospheres" });
  const bottom = top + bars.length * rowH;
  for (let t = 0; t <= 100; t += 10) {
    svg.append(s("line", { class: "gridline", x1: x(t), x2: x(t), y1: top - 6, y2: bottom }),
      s("text", { x: x(t), y: bottom + 16, "text-anchor": "middle", text: `${t}%` }));
  }
  svg.append(s("text", { x: (L + R) / 2, y: bottom + 34, "text-anchor": "middle", text: "Oxygen concentration (% by volume)" }));
  refs.forEach((r, i) => {
    const row = [0, 1, 2, 0][i] ?? i % 3;
    const line = s("line", { class: "ref", x1: x(r.v), x2: x(r.v), y1: 14 + row * 16, y2: bottom });
    tip(line, r.note);
    svg.append(line, s("text", { class: "lab-strong", x: r.v > 90 ? x(r.v) : x(r.v) + 4, y: 10 + row * 16, "text-anchor": r.v > 90 ? "end" : "start", text: `${r.label} ${r.v}%` }));
  });
  bars.forEach((b, i) => {
    const y = top + i * rowH + 6;
    const a = b.min === null ? x(b.max) - 4 : x(b.min), w = Math.max(6, x(b.max) - a);
    const rect = s("rect", { class: `o2-bar ${b.cls}`, x: a, y, width: w, height: rowH - 12, rx: 4 });
    tip(rect, `${b.label}\n${b.note}\n${b.src}`);
    const link = s("a", { href: b.href }, s("text", { class: "lab-strong", x: L - 10, y: y + 13, "text-anchor": "end", text: b.label }));
    svg.append(link, rect, s("text", { class: "val", x: x(b.max) + 6, y: y + 13,
      text: b.min === null ? `up to ${b.max}%` : b.min === b.max ? `${b.max}%` : `${b.min}–${b.max}%` }));
  });
  $("#o2-chart").replaceChildren(svg);

  const habitat = refs.find((r) => r.label === "Lunar habitat");
  if (habitat) {
    const reach = ranged.filter((i) => i.o2_range.max >= habitat.v);
    const solids = ranged.filter((i) => i.fuel_type === "solid");
    const solidReach = solids.filter((i) => i.o2_range.max >= habitat.v);
    const tagPlanned = (i) => i.acronym + (/planned/i.test(i.status + i.o2_range.label) ? " (planned)" : "");
    const ledgerMax = reduced.length ? Math.max(...reduced.map((r) => r.o2_pct)) : null;
    $("#o2-insight").textContent =
      `${reach.length} of ${ranged.length} investigations with a reported oxygen range reach the ${habitat.v}% lunar habitat level ` +
      `(${reach.map(tagPlanned).join(", ")}). Of the solid-material investigations, ${solidReach.length} of ${solids.length} do` +
      `${solidReach.length ? ` (${solidReach.map(tagPlanned).join(", ")})` : ""}.` +
      (ledgerMax !== null ? ` The measured reduced-gravity limits in the ledger go up to ${ledgerMax}% O2.` : "");
  }
}

const AREA_LABEL = { prevention: "Prevention", detection: "Detection", suppression: "Suppression", fundamental: "Fundamental science" };
const FIELD_LABEL = { areas: "Fire safety area", platform: "Platform", hardware: "Hardware", fuel_type: "Fuel type", fuels: "Fuels and samples",
  conditions: "Test conditions", variables: "Variables", measurements: "Measurements", status: "Status" };
const NOT_YET = "Not yet summarised";
const lc = (s) => s.charAt(0).toLowerCase() + s.slice(1);
const state = { cat: null, area: "", fuel: "", q: "", selected: new Set() };

const srcLink = (cat, sid, location) => {
  const s = cat.sources.find((x) => x.source_id === sid);
  const label = (s ? s.title.replace(/\s*\(.*?\)\s*$/, "") : sid) + (location ? `, ${location}` : "");
  return s ? h("a", { class: "src", href: s.url, target: "_blank", rel: "noopener noreferrer", text: label }) : h("span", { class: "src", text: label });
};
const areaBadges = (areas) => h("span", { class: "row tight" }, areas.map((a) => h("span", { class: `badge area-${a}`, text: AREA_LABEL[a] || a })));
const psiLink = (inv) => h("a", { class: "src", href: `https://psi.nasa.gov/physci/repo/search?q=${encodeURIComponent(inv.acronym.split(/[\s/]/)[0])}`,
  target: "_blank", rel: "noopener noreferrer", text: "Search NASA PSI" });

function field(label, value) {
  return [h("dt", { text: label }), h("dd", { class: value === NOT_YET ? "muted" : "", text: value })];
}

function card(inv) {
  const cat = state.cat;
  const box = h("input", { type: "checkbox", id: `cmp-${inv.id}`, "aria-label": `Select ${inv.acronym} to compare` });
  box.checked = state.selected.has(inv.id);
  box.addEventListener("change", () => {
    if (box.checked && state.selected.size >= 3) { box.checked = false; return; }
    box.checked ? state.selected.add(inv.id) : state.selected.delete(inv.id);
    syncCompareBar();
  });
  const q = inv.quotes[0];
  return h("article", { class: "card stack inv-card", id: `inv-${inv.id}` },
    h("div", { class: "inv-head" },
      h("div", {}, h("h3", { text: inv.acronym }), h("p", { class: "small inv-name", text: inv.name + (inv.project ? ` · ${inv.project} project` : "") })),
      h("label", { class: "cmp", for: `cmp-${inv.id}` }, box, " Compare")),
    areaBadges(inv.areas),
    h("p", { text: inv.objective }),
    h("p", {}, h("span", { class: "quote", text: q.text }), " ", srcLink(cat, q.source_id, q.location)),
    Object.keys(inv.flags).length ? h("ul", { class: "tags", "aria-label": "Relevance tags" },
      Object.entries(inv.flags).map(([f, note]) => h("li", { class: "tag", title: note, text: cat.flags[f].split(" (")[0] }))) : null,
    h("details", {},
      h("summary", { text: "Fuels, conditions and measurements" }),
      h("div", { class: "inner" },
        h("dl", { class: "facts" },
          field("Platform", inv.platform), field("Hardware", inv.hardware), field("Fuel type", inv.fuel_type),
          field("Fuels and samples", inv.fuels), field("Test conditions", inv.conditions), field("Variables", inv.variables),
          field("Measurements", inv.measurements), field("Status", inv.status),
          inv.earth_application ? field("Earth application", inv.earth_application) : null),
        Object.keys(inv.flags).length ? h("div", {}, h("p", { class: "small strong", text: "Why it is tagged" }),
          h("ul", { class: "small" }, Object.entries(inv.flags).map(([f, note]) => h("li", {}, h("strong", { text: `${cat.flags[f].split(" (")[0]}: ` }), note)))) : null,
        inv.quotes.length > 1 ? h("ul", { class: "small" }, inv.quotes.slice(1).map((x) => h("li", {}, h("span", { class: "quote", text: x.text }), " ", srcLink(cat, x.source_id, x.location)))) : null,
        inv.ledger_rows.length ? h("p", { class: "small" }, "Ledger rows from this investigation: ",
          h("a", { href: "/#h-grid", text: inv.ledger_rows.join(", ") })) : null,
        h("p", { class: "small" }, "Sources: ", ...inv.sources.flatMap((s, i) => [i ? " · " : "", srcLink(cat, s.source_id, s.location)]), " · ", psiLink(inv)))));
}

function renderGrid() {
  const { cat, area, fuel, q } = state;
  const needle = q.trim().toLowerCase();
  const items = cat.investigations.filter((i) => (!area || i.areas.includes(area)) && (!fuel || i.fuel_type.startsWith(fuel))
    && (!needle || JSON.stringify(i).toLowerCase().includes(needle)));
  $("#inv-grid").replaceChildren(...(items.length ? items.map(card) : [h("p", { class: "small", text: "No investigation matches these filters." })]));
}

function syncCompareBar() {
  const n = state.selected.size;
  $("#compare-bar").hidden = n === 0;
  $("#compare-count").textContent = n < 2 ? `${n} selected: pick ${2 - n} more` : `${n} selected`;
  $("#compare-go").disabled = n < 2;
}

async function runCompare() {
  const ids = [...state.selected];
  const out = $("#compare-out");
  try {
    const res = await getJSON(`/api/investigations/compare?ids=${encodeURIComponent(ids.join(","))}`);
    if (state.syncUrl) state.syncUrl();
    const sim = res.similarities;
    const shared = [
      sim.areas.length ? `Same fire-safety area: ${sim.areas.map((a) => AREA_LABEL[a]).join(", ")}.` : "They cover different fire-safety areas.",
      sim.flags.length ? `Shared relevance: ${sim.flags.map((f) => lc(f.split(" (")[0])).join("; ")}.` : "",
      sim.hardware_terms.length ? `Shared hardware: ${sim.hardware_terms.map((x) => x.toUpperCase()).join(", ")}.` : "",
    ].filter(Boolean).join(" ");
    out.replaceChildren(h("div", { class: "card stack" },
      h("h3", { text: `Comparing ${res.acronyms.join(", ")}` }),
      h("p", { text: shared }),
      h("div", { class: "scroll" }, h("table", { class: "cmp-table" },
        h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "" }), res.acronyms.map((a) => h("th", { scope: "col", text: a })))),
        h("tbody", {}, res.rows.map((r) => h("tr", { class: r.same ? "same" : "" },
          h("th", { scope: "row" }, FIELD_LABEL[r.field] || r.field, r.same ? h("span", { class: "small block", text: "same" }) : null),
          r.values.map((v) => h("td", { class: v === NOT_YET ? "muted" : "", text: r.field === "areas" ? v.split(", ").map((a) => AREA_LABEL[a] || a).join(", ") : v }))))))),
      h("p", { class: "small", text: res.note })));
    out.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (err) { showError(out, err); }
}

async function renderRank(profileId) {
  const list = $("#rank-list");
  try {
    const res = await getJSON(`/api/investigations/rank?habitat=${encodeURIComponent(profileId)}`);
    $("#rank-label").textContent = `${res.label}.`;
    const top = res.results.filter((r) => r.score > 0).slice(0, 8);
    list.replaceChildren(...top.map((r) => h("li", { class: "rank-item" },
      h("div", { class: "rank-top" },
        h("a", { class: "rank-name", href: `#inv-${r.id}`, text: `${r.acronym}` }),
        h("span", { class: "small", text: r.name }),
        h("span", { class: "score", text: `${r.score} / ${res.max_score}` })),
      h("div", { class: "meter", role: "img", "aria-label": `Score ${r.score} of ${res.max_score}` },
        h("span", { class: "meter-fill", "data-w": String(Math.round((r.score / res.max_score) * 20)) })),
      h("p", { class: "small" }, "Why: ", r.reasons.map((x) => `${lc(x.label.split(" (")[0])} (+${x.weight})`).join(", "), "."))));
  } catch (err) { showError(list, err); }
}

function renderWeights(cat) {
  const flags = Object.keys(cat.flags);
  $("#weights-table").replaceChildren(h("table", {},
    h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "Tag" }), cat.habitat_profiles.map((p) => h("th", { scope: "col", text: p.label })))),
    h("tbody", {}, flags.map((f) => h("tr", {}, h("th", { scope: "row", text: cat.flags[f] }),
      cat.habitat_profiles.map((p) => h("td", { class: "num-col", text: String(p.weights[f] ?? 0) })))))));
}

async function main() {
  fillBuildInfo();
  try {
    const cat = await getJSON("/api/investigations");
    state.cat = cat;
    $("#inv-count").textContent = `${cat.investigations.length} investigations · ${cat.sources.length} NASA sources`;
    $("#inv-statement").textContent = cat.statement;

    const sel = $("#habitat");
    sel.append(...cat.habitat_profiles.map((p) => h("option", { value: p.id, text: p.label })));
    const params = new URLSearchParams(window.location.search);
    const wanted = params.get("habitat");
    sel.value = cat.habitat_profiles.some((p) => p.id === wanted) ? wanted : "lunar_base";
    const syncUrl = () => setQuery({ habitat: sel.value, compare: state.selected.size >= 2 ? [...state.selected].join(",") : "" });
    state.syncUrl = syncUrl;
    sel.addEventListener("change", () => { renderRank(sel.value); syncUrl(); });
    $("#share-slot").replaceChildren(copyLinkButton("Copy link to this view"));
    Promise.all([getJSON("/api/presets"), getJSON("/api/ledger")])
      .then(([presets, rows]) => renderO2(cat, presets, rows))
      .catch((err) => showError($("#o2-chart"), err));
    renderRank(sel.value);
    renderWeights(cat);

    const chips = $("#area-chips");
    const areas = ["", "prevention", "detection", "suppression", "fundamental"];
    const chipEls = areas.map((a) => {
      const b = h("button", { type: "button", class: "chip", "aria-pressed": a === "" ? "true" : "false", text: a ? AREA_LABEL[a] : "All areas" });
      b.addEventListener("click", () => { state.area = a; chipEls.forEach((c) => c.setAttribute("aria-pressed", c === b ? "true" : "false")); renderGrid(); });
      return b;
    });
    chips.replaceChildren(...chipEls);
    const fuels = [...new Set(cat.investigations.map((i) => i.fuel_type.split(" ")[0]))].sort();
    $("#fuel").append(...fuels.map((f) => h("option", { value: f, text: f })));
    $("#fuel").addEventListener("change", (e) => { state.fuel = e.target.value; renderGrid(); });
    $("#q").addEventListener("input", (e) => { state.q = e.target.value; renderGrid(); });
    $("#compare-go").addEventListener("click", runCompare);
    $("#compare-clear").addEventListener("click", () => { state.selected.clear(); $("#compare-out").replaceChildren(); syncCompareBar(); renderGrid(); syncUrl(); });
    const preselect = (params.get("compare") || "").split(",").filter((id) => cat.investigations.some((i) => i.id === id)).slice(0, 3);
    preselect.forEach((id) => state.selected.add(id));
    renderGrid();
    syncCompareBar();
    if (state.selected.size >= 2) runCompare();

    $("#earth").replaceChildren(...cat.earth_applications.map((a) => h("div", { class: "card stack" },
      h("h3", { text: a.title }), h("p", { text: a.text }),
      h("p", { class: "small" }, srcLink(cat, a.source_id, a.location),
        a.investigation_ids.length ? h("span", {}, " · Related: ", ...a.investigation_ids.flatMap((id, i) => [i ? ", " : "",
          h("a", { href: `#inv-${id}`, text: (cat.investigations.find((x) => x.id === id) || {}).acronym || id })])) : null))));
    $("#inv-sources").replaceChildren(...cat.sources.map((s) => h("li", {},
      h("a", { href: s.url, target: "_blank", rel: "noopener noreferrer", text: s.title }), ` (${s.publisher})`)));
  } catch (err) {
    showError($("#inv-grid"), err);
  }
}
main();
