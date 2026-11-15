import { $, h, getJSON, showError } from "/static/common.js";

// Tiers run from least to most lunar-relevant evidence. Status "data" or "qualitative" counts as evidence.
const TIERS = [
  { id: "none", title: "No reduced-gravity evidence at all", why: "Only normal-gravity (1g) results. Any microgravity or lunar test would be new." },
  { id: "micro", title: "Microgravity evidence, but nothing at lunar or Mars gravity", why: "Partial gravity can differ from both 0g and 1g, so a lunar-gravity test is the next step." },
  { id: "drop", title: "Short drop-tower lunar data, no long-duration lunar test", why: "Drop-tower limit criteria differ from 1g because test time is short; a long-duration test would confirm them." },
  { id: "planned", title: "Planned in FM2 (no result yet)", why: "FM2 is planned to give the first long-duration lunar data for this material." },
];
const has = (c) => c && (c.status === "data" || c.status === "qualitative");

async function main() {
  const box = $("#next-tests");
  try {
    const cov = await getJSON("/api/coverage");
    const groups = Object.fromEntries(TIERS.map((t) => [t.id, []]));
    for (const m of cov.materials) {
      const c = m.cells;
      const tier = c.fm2 && c.fm2.status === "planned" ? "planned"
        : has(c.lunar) ? "drop" : has(c.microgravity) || has(c.mars) ? "micro" : "none";
      groups[tier].push(m.material);
    }
    box.replaceChildren(...TIERS.filter((t) => groups[t.id].length).map((t, i) => h("div", { class: `card next-tier tier-${t.id}` },
      h("div", { class: "row" }, h("span", { class: "tier-n", text: String(i + 1) }), h("h3", { text: `${t.title} (${groups[t.id].length})` })),
      h("p", { class: "small", text: t.why }),
      h("ul", { class: "tags" }, groups[t.id].map((name) => h("li", { class: "tag", text: name }))))));
  } catch (err) { showError(box, err); }
}
main();
