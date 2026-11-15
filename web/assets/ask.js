import { $, h, fillBuildInfo } from "/static/common.js";

const EXAMPLES = [
  "Which NASA experiments studied smoke detection?",
  "What happens to a PMMA rod in microgravity?",
  "Which investigations tested high oxygen atmospheres?",
  "How was partial gravity studied?",
  "What suppressants did FLEX test?",
];
const STATUS_TEXT = {
  failed_verification: "AI answer unavailable (failed verification). The evidence below is complete and sourced.",
  unavailable: "AI answer unavailable right now. The evidence below is complete and sourced.",
  not_configured: "AI answers are not configured on this server. The evidence below is complete and sourced.",
  no_match: "",
};
const KIND = { investigation: "Investigation", ledger_row: "Ledger row", margin: "Published margin" };

const q = $("#question");
const err = $("#ask-error");

function srcLink(item) {
  const label = `${item.source_id.replace("NTRS-", "NTRS ")}${item.location ? `, ${item.location}` : ""}`;
  return item.url ? h("a", { class: "src", href: item.url, target: "_blank", rel: "noopener noreferrer", text: label }) : h("span", { class: "src", text: label });
}

function render(res) {
  const cited = new Set((res.citations || []).map((c) => c.id));
  const answer = $("#answer");
  if (res.answer) {
    answer.replaceChildren(h("div", { class: "card ai stack" },
      h("div", { class: "row" }, h("h3", { text: "Answer" }), h("span", { class: "badge ok", title: res.ai_note, text: "Verified ✔ every number and citation checked" })),
      h("p", { class: "answer-text", text: res.answer }),
      res.citations.length ? h("p", { class: "small" }, "Cited: ", ...res.citations.flatMap((c, i) => [i ? " · " : "", h("a", { href: `#ev-${c.id}`, text: c.title })])) : null,
      res.claims && res.claims.length ? h("details", {}, h("summary", { text: `Claims checked by the verifier (${res.claims.length})` }),
        h("div", { class: "inner" }, h("ul", { class: "claims" }, res.claims.map((c) => h("li", {}, c.text, " ", h("span", { class: "src", text: `(${c.source_id})` })))))) : null,
      h("p", { class: "small", text: "Written by an AI model from the evidence below and checked by FlameLedger's verifier. Research decision support, not certification." })));
  } else {
    answer.replaceChildren(h("div", { class: `card ${res.ai_status === "no_match" ? "" : "ai off"} stack` },
      h("p", { text: res.ai_status === "no_match" ? res.ai_note : STATUS_TEXT[res.ai_status] || res.ai_note })));
  }
  $("#evidence").replaceChildren(...(res.evidence.length ? res.evidence.map((e) => h("li", { class: `ev ${cited.has(e.id) ? "cited" : ""}`, id: `ev-${e.id}` },
    h("div", { class: "row tight" }, h("span", { class: "badge", text: KIND[e.kind] || e.kind }), h("strong", { text: e.title }),
      cited.has(e.id) ? h("span", { class: "badge ok", text: "cited" }) : null),
    h("p", { class: "small", text: e.snippet + (e.snippet.length >= 280 ? "…" : "") }),
    h("p", { class: "small" }, "Source: ", srcLink(e),
      e.kind === "investigation" ? h("span", {}, " · ", h("a", { href: `/investigations#inv-${e.id.replace("inv:", "")}`, text: "Open card" })) : null)))
    : [h("li", { class: "small", text: "No matching evidence." })]));
  $("#answer-section").hidden = false;
}

async function ask(event) {
  event.preventDefault();
  err.hidden = true;
  const question = q.value.trim();
  if (question.length < 3) { err.textContent = "Type a question of at least 3 characters."; err.hidden = false; return; }
  const btn = $("#ask-go");
  btn.disabled = true; btn.textContent = "Searching the evidence…";
  try {
    const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ question }) });
    if (res.status === 429) throw new Error("Too many questions in a minute. Please wait a moment and try again.");
    if (!res.ok) throw new Error("The question could not be answered. Please try again.");
    render(await res.json());
    $("#h-answer").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    err.textContent = e.message; err.hidden = false;
  } finally {
    btn.disabled = false; btn.textContent = "Ask";
  }
}

function main() {
  fillBuildInfo();
  $("#ask-form").addEventListener("submit", ask);
  q.addEventListener("input", () => { $("#chars").textContent = String(q.value.length); });
  $("#examples").replaceChildren(...EXAMPLES.map((text) => {
    const b = h("button", { type: "button", class: "chip", text });
    b.addEventListener("click", () => { q.value = text; $("#chars").textContent = String(text.length); $("#ask-form").requestSubmit(); });
    return b;
  }));
}
main();
