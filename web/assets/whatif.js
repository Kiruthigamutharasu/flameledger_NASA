import { $, h, s, getJSON, showError, tip, setQuery } from "/static/common.js";

const GRAVITY = [["0", "Microgravity (orbit)"], ["0.165", "Moon (0.165 g)"], ["0.38", "Mars (0.38 g)"]];
const REFS = ["iss_cabin", "moon_base_brief", "lunar_habitat_nominal", "lunar_habitat_max"];
const REF_LABEL = { iss_cabin: "ISS", moon_base_brief: "Moon base (brief)", lunar_habitat_nominal: "Lunar habitat", lunar_habitat_max: "Control-band max" };
const LEVEL_TEXT = { red: "evidence of burning at or below this O2", orange: "thin or negative published margin",
  green: "evidence of no burning at this O2", grey: "no comparable space data" };
const cache = {};
const sweep = (g) => (cache[g] ??= getJSON(`/api/review/sweep?gravity_g=${g}&pressure_psia=8.2&o2_min=15&o2_max=40`));
const shortName = (n) => n.replace(/\s*\(.*?\)/g, "").replace(/, 1\/8-in rod/, " rod").replace(/ 1\/4-in rod/, " rod");

function draw(res, gLabel) {
  const lv = res.o2_levels, L = 190, cw = 21, ch = 22, top = 58, W = L + lv.length * cw + 20, H = top + res.rows.length * ch + 40;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Verdict per material and oxygen level, ${gLabel}` });
  const x = (o2) => L + (o2 - lv[0]) * cw;
  res.rows.forEach((r, i) => {
    const y = top + i * ch;
    svg.append(s("text", { class: "lab-strong", x: L - 8, y: y + 15, "text-anchor": "end", text: shortName(r.material) }));
    r.levels.forEach((lvl, j) => {
      const cell = s("rect", { class: `hm hm-${lvl}`, x: x(lv[j]) + 1, y: y + 1, width: cw - 2, height: ch - 2, rx: 2 });
      tip(cell, `${r.material} at ${lv[j]}% O2 (${gLabel}): ${LEVEL_TEXT[lvl]}`);
      svg.append(cell);
    });
  });
  const bottom = top + res.rows.length * ch;
  for (let o2 = lv[0]; o2 <= lv[lv.length - 1]; o2 += 5) svg.append(s("text", { x: x(o2) + cw / 2, y: bottom + 16, "text-anchor": "middle", text: `${o2}%` }));
  svg.append(s("text", { x: L + (lv.length * cw) / 2, y: bottom + 34, "text-anchor": "middle", text: "Habitat oxygen (% O2)" }));
  res.references.filter((r) => REFS.includes(r.preset_id)).forEach((r, i) => {
    const xx = x(r.o2_pct) + cw / 2;
    const ty = 12 + (i % 3) * 15, right = xx > W - 170;
    const line = s("line", { class: "ref", x1: xx, x2: xx, y1: ty + 3, y2: bottom });
    tip(line, `${r.label}: ${r.o2_pct}% O2`);
    svg.append(line, s("text", { class: "lab-strong", x: right ? xx - 3 : xx + 3, y: ty, "text-anchor": right ? "end" : "start",
      text: `${REF_LABEL[r.preset_id] || r.label} ${r.o2_pct}%` }));
  });
  $("#whatif").replaceChildren(svg);
}

function insight(cur, micro, gLabel, g) {
  const ref = cur.references.find((r) => r.preset_id === "lunar_habitat_nominal");
  const red = cur.rows.filter((r) => r.first_red_o2 !== null);
  const at = ref ? red.filter((r) => r.first_red_o2 <= ref.o2_pct) : [];
  const parts = [];
  if (ref) parts.push(`At ${gLabel}, ${at.length} of ${cur.rows.length} materials have evidence of burning at or below the ${ref.o2_pct}% lunar habitat level.`);
  parts.push(`${cur.rows.length - red.length} have no comparable space evidence at any level shown.`);
  if (g !== "0" && micro) {
    const lower = cur.rows.filter((r) => {
      const m = micro.rows.find((x) => x.material === r.material);
      return r.first_red_o2 !== null && m && m.first_red_o2 !== null && r.first_red_o2 < m.first_red_o2;
    }).map((r) => `${shortName(r.material)} (${r.first_red_o2}% vs ${micro.rows.find((x) => x.material === r.material).first_red_o2}% in microgravity)`);
    if (lower.length) parts.push(`Compared with microgravity, the evidence turns red at a lower oxygen level for ${lower.join(", ")}.`);
  }
  const floor = cur.o2_levels[0];
  if (red.some((r) => r.first_red_o2 === floor)) parts.push(`Materials red at ${floor}% may already be red below it.`);
  $("#whatif-insight").textContent = parts.join(" ");
}

async function show(g) {
  const label = GRAVITY.find(([v]) => v === g)[1];
  document.querySelectorAll("#whatif-g .chip").forEach((c) => c.setAttribute("aria-pressed", c.dataset.g === g ? "true" : "false"));
  try {
    const [cur, micro] = await Promise.all([sweep(g), sweep("0")]);
    draw(cur, label);
    insight(cur, micro, label, g);
  } catch (err) { showError($("#whatif"), err); }
}

function main() {
  const wanted = new URLSearchParams(window.location.search).get("g");
  const start = GRAVITY.some(([v]) => v === wanted) ? wanted : "0.165";
  $("#whatif-g").replaceChildren(...GRAVITY.map(([v, label]) => {
    const b = h("button", { type: "button", class: "chip", "data-g": v, text: label });
    b.addEventListener("click", () => { show(v); setQuery({ g: v }); });
    return b;
  }));
  show(start);
}
main();
