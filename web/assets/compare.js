import { $, h, getJSON, showError, setQuery } from "/static/common.js";

async function main() {
  const out = $("#mat-compare");
  try {
    const cov = await getJSON("/api/coverage");
    const a = $("#mat-a"), b = $("#mat-b");
    for (const sel of [a, b]) sel.append(...cov.materials.map((m) => h("option", { value: m.material_id, text: m.material })));
    const params = new URLSearchParams(window.location.search);
    const ids = cov.materials.map((m) => m.material_id);
    a.value = ids.includes(params.get("a")) ? params.get("a") : (ids.includes("pmma_rod") ? "pmma_rod" : ids[0]);
    b.value = ids.includes(params.get("b")) ? params.get("b") : (ids.includes("mylar_g") ? "mylar_g" : ids[1]);
    const cell = (c) => h("td", { class: `cmpcell ${c.status}` },
      h("strong", { text: c.summary }),
      c.sources.length ? h("span", { class: "small block" }, ...c.sources.flatMap((s, i) => [i ? " · " : "",
        s.url ? h("a", { class: "src", href: s.url, target: "_blank", rel: "noopener noreferrer", text: s.source_id.replace("NTRS-", "NTRS ") }) : s.source_id])) : null);
    const render = (sync) => {
      const ma = cov.materials.find((m) => m.material_id === a.value), mb = cov.materials.find((m) => m.material_id === b.value);
      out.replaceChildren(h("table", {},
        h("thead", {}, h("tr", {}, h("th", { scope: "col", text: "Environment" }), h("th", { scope: "col", text: ma.material }), h("th", { scope: "col", text: mb.material }))),
        h("tbody", {}, cov.environments.map((e) => h("tr", {}, h("th", { scope: "row", text: e.label }), cell(ma.cells[e.id]), cell(mb.cells[e.id]))))));
      if (sync) setQuery({ a: a.value, b: b.value });
    };
    a.addEventListener("change", () => render(true));
    b.addEventListener("change", () => render(true));
    render(false);
  } catch (err) { showError(out, err); }
}
main();
