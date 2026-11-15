import { $, h, getJSON, ENV, fillBuildInfo } from "/static/common.js";

const EXAMPLE = ["PMMA rod", "cotton-fiberglass fabric", "silicone", "Synergy Pro Navy fabric"];
const EXAMPLE_PRESET = "lunar_habitat_nominal";
const DISCLAIMER = "Research decision support, not certification.";
const AI_TEXT = {
  failed_verification: "AI explanation unavailable (failed verification). The deterministic verdicts above are complete without it.",
  unavailable: "AI explanation unavailable right now. The deterministic verdicts above are complete without it.",
  not_configured: "AI explanation is not configured on this server. The deterministic verdicts above are complete without it.",
};

let presets = [];
let lastRequest = null;

const form = $("#review-form");
const fields = { preset: $("#preset"), o2: $("#o2"), pressure: $("#pressure"), gravity: $("#gravity"),
                 materials: $("#materials"), tol: $("#tol"), thin: $("#thin") };

function sourceA(id, url, location) {
  const label = id.replace("NTRS-", "NTRS ") + (location ? `, ${location}` : "");
  return url ? h("a", { class: "src", href: url, target: "_blank", rel: "noopener noreferrer", text: label }) : h("span", { class: "src", text: label });
}

function showFormError(text) {
  const el = $("#form-error");
  el.textContent = text;
  el.hidden = !text;
}

function applyPreset(id) {
  const p = presets.find((x) => x.preset_id === id);
  const note = $("#preset-note");
  if (!p) { note.replaceChildren(); return; }
  fields.o2.value = p.o2_pct; fields.pressure.value = p.pressure_psia; fields.gravity.value = p.gravity_g;
  note.replaceChildren(`${p.gravity_label}. Source: ${p.source_note}`,
    p.source_url ? h("span", {}, " · ", h("a", { href: p.source_url, target: "_blank", rel: "noopener noreferrer", text: "PDF" })) : "");
}

function syncPresetToInputs() {
  const p = presets.find((x) => x.preset_id === fields.preset.value);
  if (p && (Number(fields.o2.value) !== p.o2_pct || Number(fields.pressure.value) !== p.pressure_psia || Number(fields.gravity.value) !== p.gravity_g)) {
    fields.preset.value = "";
    applyPreset("");
  }
}

function readForm() {
  const num = (el) => (el.value.trim() === "" ? NaN : Number(el.value));
  const o2 = num(fields.o2), pressure = num(fields.pressure), gravity = num(fields.gravity);
  const tol = num(fields.tol), thin = num(fields.thin);
  const materials = [...new Set(fields.materials.value.split(/\r?\n/).map((x) => x.trim()).filter(Boolean))];
  if (!(o2 > 0 && o2 <= 100)) return { error: "Oxygen must be more than 0 and at most 100%." };
  if (!(pressure > 0 && pressure <= 30)) return { error: "Pressure must be more than 0 and at most 30 psia." };
  if (!(gravity >= 0 && gravity <= 1.5)) return { error: "Gravity must be between 0 and 1.5 g." };
  if (!(tol >= 0 && tol <= 5) || !(thin >= 0 && thin <= 5)) return { error: "Thresholds must be between 0 and 5% O2." };
  if (!materials.length) return { error: "Enter at least one material, one per line." };
  if (materials.length > 20) return { error: "Enter at most 20 materials." };
  const long = materials.find((m) => m.length > 80);
  if (long) return { error: `This line is longer than 80 characters: "${long.slice(0, 40)}…"` };
  const body = { o2_pct: o2, pressure_psia: pressure, gravity_g: gravity, materials,
                 thresholds: { red_o2_tolerance_pct: tol, thin_margin_pct_o2: thin } };
  if (fields.preset.value) body.preset_id = fields.preset.value;
  return { body };
}

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
                                 body: JSON.stringify(body) });
  if (res.status === 429) throw new Error("Too many reviews in a minute. Please wait a moment and try again.");
  if (res.status === 422) throw new Error("Some input was not accepted. Check the values and try again.");
  if (!res.ok) throw new Error("The review service had a problem. Please try again.");
  return res;
}

function verdictChip(v) {
  return h("span", { class: `verdict v-${v.level}` }, h("span", { "aria-hidden": "true", text: v.emoji }), " ", v.label);
}

function renderSummary(result) {
  const rows = result.verdicts.map((v) => h("tr", {},
    h("th", { scope: "row" }, v.input, v.material && v.material.toLowerCase() !== v.input.toLowerCase()
      ? h("span", { class: "small block", text: `Ledger: ${v.material}` }) : null,
      !v.material ? h("span", { class: "small block", text: "Not in ledger" }) : null),
    h("td", {}, verdictChip(v.headline)),
    h("td", {}, v.verdicts.length > 1 ? `${v.verdicts.length} verdicts apply` : "1 verdict applies"),
    h("td", {}, h("a", { href: `#card-${v.key}`, text: "Details" }))));
  $("#summary-table").replaceChildren(h("table", {},
    h("caption", { class: "skip", text: "Headline verdict per material" }),
    h("thead", {}, h("tr", {}, ["Material", "Headline verdict", "Verdicts", ""].map((t) => h("th", { scope: "col", text: t })))),
    h("tbody", {}, rows)));
}

function renderAI(result) {
  const panel = $("#ai-panel");
  if (!result.ai) {
    panel.replaceChildren(h("div", { class: "card ai off" },
      h("h3", { text: "AI explanation" }), h("p", { text: AI_TEXT[result.ai_status] || AI_TEXT.unavailable })));
    return;
  }
  const claims = result.ai.claims.map((c) => {
    const ev = result.verdicts.flatMap((v) => v.evidence).find((e) => e.id === c.source_id || e.source_id === c.source_id);
    return h("li", {}, c.text, " ", c.source_id === "habitat" ? h("span", { class: "src", text: "(habitat input)" })
      : ev ? sourceA(c.source_id, ev.source_url, ev.id === c.source_id ? ev.location : "") : h("span", { class: "src", text: c.source_id }));
  });
  panel.replaceChildren(h("div", { class: "card ai stack" },
    h("div", { class: "row" }, h("h3", { text: "AI explanation" }),
      h("span", { class: "badge ok", title: result.ai_note, text: "Verified ✔ every number and source checked" })),
    h("p", { text: result.ai.summary }),
    claims.length ? h("details", {}, h("summary", { text: `Claims checked by the verifier (${claims.length})` }),
      h("div", { class: "inner" }, h("ul", { class: "claims" }, claims))) : null,
    h("p", { class: "small", text: `Explanation by an AI model, checked by FlameLedger's verifier. ${DISCLAIMER}` })));
}

function evidenceTable(list) {
  return h("table", {},
    h("thead", {}, h("tr", {}, ["Row", "Environment", "Value", "Pressure", "Source", "Quote and caveat"].map((t) => h("th", { scope: "col", text: t })))),
    h("tbody", {}, list.map((e) => h("tr", {},
      h("td", { class: "mono", text: e.id }),
      h("td", { text: (ENV[e.environment] || {}).label || e.environment }),
      h("td", { class: "num-col", text: e.kind === "margin" ? `${e.margin_pct_o2 > 0 ? "+" : ""}${e.margin_pct_o2}% O2 margin`
        : e.o2_pct !== null && e.o2_pct !== undefined ? `${e.o2_pct}% O2 (${e.outcome})` : `${e.outcome} (qualitative)` }),
      h("td", { class: "num-col", text: e.pressure_psia ? `${e.pressure_psia} psia` : "not in ledger" }),
      h("td", {}, sourceA(e.source_id, e.source_url, e.location)),
      h("td", {}, h("span", { class: "quote", text: e.short_quote }), ` ${e.caveat}`)))));
}

function renderCards(result) {
  const explanations = new Map(((result.ai && result.ai.per_material) || []).map((p) => [p.material_id, p.explanation]));
  $("#detail-cards").replaceChildren(...result.verdicts.map((v) => h("article", { class: `card stack vcard v-${v.headline.level}`, id: `card-${v.key}` },
    h("div", { class: "row" }, h("h3", { text: v.input }), v.material ? h("span", { class: "badge", text: v.material }) : h("span", { class: "badge", text: "Not in ledger" })),
    h("ul", { class: "vlist" }, v.verdicts.map((x) => h("li", {}, verdictChip(x), h("p", { text: x.reason })))),
    explanations.has(v.key) ? h("p", { class: "ai-line" }, h("strong", { text: "AI explanation (verified): " }), explanations.get(v.key)) : null,
    v.missing.length ? h("div", {}, h("p", { class: "small strong", text: "What is missing" }), h("ul", { class: "small" }, v.missing.map((m) => h("li", { text: m })))) : null,
    v.evidence.length ? h("details", {}, h("summary", { text: `Evidence used (${v.evidence.length})` }), h("div", { class: "scroll" }, evidenceTable(v.evidence))) : null,
    h("div", {}, h("p", { class: "small strong", text: "Caveats" }), h("ul", { class: "small" }, v.caveats.map((c) => h("li", {}, c.text,
      c.source ? h("span", {}, " ", sourceA(c.source.source_id, c.source.source_url, c.source.location)) : null)))),
    h("p", {}, h("span", { class: "badge strong", text: DISCLAIMER })))));
}

function render(result) {
  const hab = result.habitat;
  $("#results-lede").textContent = `${hab.label}: ${hab.o2_pct}% O2, ${hab.pressure_psia} psia, ${hab.gravity_g} g (${hab.gravity_label}). ` +
    `Where several verdicts apply, all are listed and the highest is the headline. ${result.thresholds.label}.`;
  renderSummary(result);
  renderAI(result);
  renderCards(result);
  $("#results-section").hidden = false;
}

async function run(event) {
  event.preventDefault();
  showFormError("");
  const { body, error } = readForm();
  if (error) { showFormError(error); return; }
  const btn = $("#run");
  btn.disabled = true; btn.textContent = "Reviewing… (the AI check can take up to a minute)";
  try {
    const result = await (await post("/api/review", body)).json();
    lastRequest = body;
    $("#download").disabled = false;
    $("#download-md").disabled = false;
    render(result);
    $("#h-results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showFormError(err.message || "The review could not run. Please try again.");
  } finally {
    btn.disabled = false; btn.textContent = "Review materials";
  }
}

async function download(kind) {
  if (!lastRequest) return;
  const pdf = kind === "pdf";
  const btn = $(pdf ? "#download" : "#download-md");
  btn.disabled = true;
  try {
    const blob = await (await post(pdf ? "/api/report.pdf" : "/api/report", lastRequest)).blob();
    const url = URL.createObjectURL(blob);
    const a = h("a", { href: url, download: pdf ? "flameledger_habitat_review.pdf" : "flameledger_habitat_review.md" });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    showFormError(pdf ? "The PDF could not be created. Try the Markdown report instead." : (err.message || "The report could not be created."));
  } finally {
    btn.disabled = false;
  }
}

async function main() {
  fillBuildInfo();
  form.addEventListener("submit", run);
  $("#download").addEventListener("click", () => download("pdf"));
  $("#download-md").addEventListener("click", () => download("md"));
  $("#example").addEventListener("click", () => {
    fields.materials.value = EXAMPLE.join("\n");
    if (presets.some((p) => p.preset_id === EXAMPLE_PRESET)) { fields.preset.value = EXAMPLE_PRESET; applyPreset(EXAMPLE_PRESET); }
    showFormError("");
  });
  fields.preset.addEventListener("change", () => applyPreset(fields.preset.value));
  for (const el of [fields.o2, fields.pressure, fields.gravity]) el.addEventListener("input", syncPresetToInputs);
  try {
    presets = await getJSON("/api/presets");
    fields.preset.append(...presets.map((p) => h("option", { value: p.preset_id, text: `${p.label} (${p.o2_pct}% O2, ${p.pressure_psia} psia)` })));
    const start = presets.find((p) => p.preset_id === EXAMPLE_PRESET) || presets[0];
    if (start) { fields.preset.value = start.preset_id; applyPreset(start.preset_id); }
  } catch {
    showFormError("Presets could not load. You can still enter a custom habitat.");
  }
}
main();
