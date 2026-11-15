import { $, h, getJSON, showError, fillBuildInfo } from "/static/common.js";

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
    sel.value = "lunar_base";
    sel.addEventListener("change", () => renderRank(sel.value));
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
    $("#compare-clear").addEventListener("click", () => { state.selected.clear(); $("#compare-out").replaceChildren(); syncCompareBar(); renderGrid(); });
    renderGrid();

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
