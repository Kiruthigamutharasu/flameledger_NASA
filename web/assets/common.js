// Shared helpers. All text is inserted as text nodes, never parsed as HTML.
const SVG_NS = "http://www.w3.org/2000/svg";

function build(node, attrs, kids) {
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "text") node.textContent = value;
    else if (key === "on") for (const [evt, fn] of Object.entries(value)) node.addEventListener(evt, fn);
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}
export const h = (tag, attrs, ...kids) => build(document.createElement(tag), attrs, kids);
export const s = (tag, attrs, ...kids) => build(document.createElementNS(SVG_NS, tag), attrs, kids);
export const $ = (sel, root = document) => root.querySelector(sel);

export async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${url} returned ${res.status}`);
  return res.json();
}

export const ENV = {
  "1g": { label: "Normal gravity (1g)", short: "Earth", cls: "1g" },
  microgravity: { label: "Microgravity", short: "0g", cls: "micro" },
  lunar: { label: "Lunar gravity", short: "Moon", cls: "lunar" },
  mars: { label: "Mars gravity", short: "Mars", cls: "mars" },
  fm2: { label: "FM2 on the Moon", short: "FM2", cls: "planned" },
};

export const MEASURE = {
  uloi: "ULOI (1g)", moc: "MOC (1g)", uloi_star: "ULOI* (low-g)", moc_star: "MOC* (low-g)",
  blowoff_limit: "Blowoff limit", steady_spread: "Steady flame spread", flame_spread: "Flame spread",
  fm2_test_condition: "Planned test atmosphere", aggregate_finding: "Finding", mission_description: "Mission",
  habitat_atmosphere: "Planned habitat atmosphere", test_method: "Test method", design_expectation: "Design expectation",
};

export const num = (v) => (v === null || v === undefined ? "" : String(Number(v)));
export const pct = (v) => (v === null || v === undefined ? "not in ledger" : `${num(v)}% O2`);
export const signed = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)}`;

export function sourceLink(sourceId, url, location) {
  const label = sourceId.replace("NTRS-", "NTRS ") + (location ? `, ${location}` : "");
  return h("a", { class: "src", href: url, target: "_blank", rel: "noopener noreferrer", text: label,
                  title: "Opens the NASA source PDF in a new tab" });
}

// One shared tooltip for chart marks. Works with mouse and keyboard focus.
let tipEl;
export function tip(target, text) {
  if (!tipEl) { tipEl = h("div", { class: "tip", role: "tooltip" }); document.body.append(tipEl); }
  const place = (x, y) => {
    tipEl.style.display = "block";
    const w = tipEl.offsetWidth, hgt = tipEl.offsetHeight;
    tipEl.style.left = `${Math.max(8, Math.min(x + 14, window.innerWidth - w - 8))}px`;
    tipEl.style.top = `${y + hgt + 24 > window.innerHeight ? y - hgt - 12 : y + 16}px`;
  };
  target.addEventListener("mousemove", (e) => { tipEl.textContent = text; place(e.clientX, e.clientY); });
  target.addEventListener("mouseleave", () => { tipEl.style.display = "none"; });
  target.addEventListener("focus", () => {
    const box = target.getBoundingClientRect();
    tipEl.textContent = text; place(box.left + box.width / 2, box.top + box.height / 2);
  });
  target.addEventListener("blur", () => { tipEl.style.display = "none"; });
  target.setAttribute("tabindex", "0");
  target.setAttribute("aria-label", text.replace(/\n/g, ". "));
}

export function showError(container, error) {
  console.error(error);
  container.replaceChildren(h("p", { class: "error", role: "alert",
    text: "This section could not load its data. Please refresh the page. The evidence is also available at /api/ledger." }));
}

export async function fillBuildInfo() {
  const slot = $("#build-info");
  if (!slot) return;
  try {
    const meta = await getJSON("/api/meta");
    slot.textContent = `Version ${meta.version}, commit ${meta.commit === "n/a" ? "n/a" : meta.commit.slice(0, 10)}, viewed ${meta.date} (UTC).`;
  } catch { slot.textContent = ""; }
}

// Keep the page state in the URL so any view can be shared, and copy it on request.
export function setQuery(params) {
  const url = new URL(window.location.href);
  url.search = "";
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  window.history.replaceState(null, "", url);
}

export function copyLinkButton(label = "Copy link") {
  const btn = h("button", { class: "btn", type: "button", text: label });
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      btn.textContent = "Link copied ✔";
    } catch {
      btn.textContent = "Copy the address bar";
    }
    setTimeout(() => { btn.textContent = label; }, 2000);
  });
  return btn;
}

export const linear =(d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

// Light/dark theme toggle on every page; follows the system setting until the viewer chooses.
(function initTheme() {
  const root = document.documentElement;
  let saved = null;
  try { saved = localStorage.getItem("fl-theme"); } catch { /* storage may be blocked */ }
  if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
  const current = () => root.getAttribute("data-theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const place = () => {
    const nav = document.querySelector(".nav");
    if (!nav || nav.querySelector(".theme-btn")) return;
    const btn = h("button", { class: "theme-btn", type: "button" });
    const label = () => {
      const next = current() === "dark" ? "light" : "dark";
      btn.textContent = next === "dark" ? "☾ Dark" : "☀ Light";
      btn.setAttribute("aria-label", `Switch to ${next} theme`);
    };
    btn.addEventListener("click", () => {
      const next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("fl-theme", next); } catch { /* ignore */ }
      label();
    });
    label();
    nav.append(btn);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", place); else place();
})();
