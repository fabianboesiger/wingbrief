// Zeitreihen-Diagramme (Inline-SVG, ohne Bibliothek).
// Eine y-Achse pro Diagramm: Reihen mit unterschiedlicher Einheit werden auf
// mehrere kleine Diagramme verteilt. Schwellen als gestrichelte Linien,
// Klimawerte gestrichelt grau, Fadenkreuz-Tooltip über alle Reihen.

const NS = "http://www.w3.org/2000/svg";
let W = 640;
const H = 190, M = { l: 42, r: 12, t: 10, b: 24 };
const TZ = "Europe/Zurich";

const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const fmtNum = (v, unit) => v == null ? "–" : `${unit === "°" || unit === "%" ? Math.round(v) : (Math.abs(v) >= 100 ? Math.round(v) : v.toFixed(1))}${unit === "°" || unit === "%" ? "" : " "}${unit}`;
const hourFmt = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, weekday: "short", day: "numeric", month: "numeric" });
const localHour = (d) => Number(new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", hourCycle: "h23" }).format(d));

function niceTicks(lo, hi, n = 4) {
  if (!isFinite(lo) || !isFinite(hi)) return [];
  if (lo === hi) { lo -= 1; hi += 1; }
  const span = hi - lo, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

export function groupSeries(series) {
  const groups = new Map();
  const thresholds = series.filter((s) => s.role === "schwelle");
  for (const s of series) {
    if (s.role === "schwelle" || !s.t || !s.t.length) continue;
    const key = s.unit + (s.role === "ensemble" ? "|ens" : "");
    if (!groups.has(key)) groups.set(key, { unit: s.unit, ens: s.role === "ensemble", series: [], thresholds: [] });
    groups.get(key).series.push(s);
  }
  for (const g of groups.values()) {
    if (!g.ens) g.thresholds = thresholds.filter((t) => t.unit === g.unit);
  }
  return [...groups.values()];
}

export function renderCharts(container, series, opts) {
  container.innerHTML = "";
  const groups = groupSeries(series);
  if (!groups.length) {
    container.innerHTML = '<p class="muted">Für diesen Check gibt es keine Zeitreihe.</p>';
    return;
  }
  W = Math.max(300, Math.round((container.clientWidth || 640) - 22));
  const colorKeys = [];
  for (const g of groups) for (const s of g.series) {
    const k = s.colorKey || s.label;
    if (s.role !== "klima" && !colorKeys.includes(k)) colorKeys.push(k);
  }
  for (const g of groups) container.appendChild(chart(g, colorKeys, opts));
}

function chart(g, colorKeys, opts) {
  const wrap = document.createElement("figure");
  wrap.className = "chart";
  wrap.style.margin = "0";
  const title = g.ens ? "Ensemble: Anteil der Members (Tag 3–5)" : (g.series.length === 1 ? g.series[0].label : unitTitle(g.unit));
  const h = document.createElement("h4");
  h.textContent = `${title}${g.unit && !g.ens ? ` (${g.unit})` : ""}`;
  wrap.appendChild(h);
  const color = (s) => s.role === "klima" ? "var(--text-muted)" : `var(--series-${(colorKeys.indexOf(s.colorKey || s.label) % 8) + 1})`;
  if (g.series.length > 1) {
    const lg = document.createElement("div");
    lg.className = "lg";
    for (const s of g.series) {
      const it = document.createElement("span");
      it.innerHTML = `<i class="${s.dashed || s.role === "klima" ? "dash" : ""}" style="border-color:${color(s)}"></i>`;
      it.append(s.label);
      lg.appendChild(it);
    }
    wrap.appendChild(lg);
  }
  const x0 = opts.x0.getTime(), x1 = opts.x1.getTime();
  const pts = g.series.map((s) => s.t.map((t, i) => [Date.parse(t), s.v[i]]).filter(([t, v]) => v != null && t >= x0 && t <= x1));
  let lo = Infinity, hi = -Infinity;
  for (const p of pts) for (const [, v] of p) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  for (const t of g.thresholds) { lo = Math.min(lo, t.value); hi = Math.max(hi, t.value); }
  if (g.unit === "%") { lo = Math.min(lo, 0); hi = Math.max(hi, g.ens ? 100 : hi); }
  if (g.unit === "°") { lo = 0; hi = 360; }
  if (["km/h", "mm/h", "J/kg", "K"].includes(g.unit)) lo = Math.min(lo, 0);
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  const pad = (hi - lo) * 0.08 || 1;
  if (g.unit !== "°") { hi += pad; if (lo !== 0) lo -= pad; }
  const ticks = g.unit === "°" ? [0, 90, 180, 270, 360] : niceTicks(lo, hi);
  if (ticks.length && g.unit !== "°") { lo = Math.min(lo, ticks[0]); hi = Math.max(hi, ticks[ticks.length - 1]); }
  const X = (t) => M.l + (t - x0) / (x1 - x0) * (W - M.l - M.r);
  const Y = (v) => H - M.b - (v - lo) / (hi - lo) * (H - M.t - M.b);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title });
  // Nacht und gewählter Abschnitt
  for (let t = x0 - (x0 % 3600000); t < x1; t += 3600000) {
    const hr = localHour(new Date(t));
    if (hr < 6 || hr >= 19) el("rect", { class: "night", x: X(t), y: M.t, width: X(t + 3600000) - X(t), height: H - M.t - M.b }, svg);
  }
  if (opts.band) {
    const [a, b] = opts.band.map((d) => Math.max(x0, Math.min(x1, d.getTime())));
    if (b > a) el("rect", { class: "band", x: X(a), y: M.t, width: X(b) - X(a), height: H - M.t - M.b }, svg);
  }
  const grid = el("g", { class: "grid" }, svg), axis = el("g", { class: "axis" }, svg);
  for (const v of ticks) {
    el("line", { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v) }, grid);
    const tx = el("text", { x: M.l - 6, y: Y(v) + 3, "text-anchor": "end" }, axis);
    tx.textContent = g.unit === "°" ? `${v}°` : v;
  }
  // Tagesgrenzen
  for (let t = x0; t <= x1; t += 3600000) {
    const d = new Date(t);
    if (localHour(d) === 0 && d.getUTCMinutes() === 0) {
      el("line", { x1: X(t), x2: X(t), y1: M.t, y2: H - M.b }, grid);
    }
    if (localHour(d) === 12 && d.getUTCMinutes() === 0) {
      const tx = el("text", { x: X(t), y: H - 6, "text-anchor": "middle" }, axis);
      tx.textContent = dayFmt.format(d);
    }
  }
  // Schwellen
  for (const t of g.thresholds) {
    if (t.value < lo || t.value > hi) continue;
    el("line", { class: "thrline", x1: M.l, x2: W - M.r, y1: Y(t.value), y2: Y(t.value) }, svg);
    const tx = el("text", { class: "thrlbl", x: W - M.r - 2, y: Y(t.value) - 3, "text-anchor": "end" }, svg);
    tx.textContent = `${t.label} ${fmtNum(t.value, t.unit)}`;
  }
  // Jetzt
  const now = Date.now();
  if (now > x0 && now < x1) {
    el("line", { class: "now", x1: X(now), x2: X(now), y1: M.t, y2: H - M.b }, svg);
    const tx = el("text", { class: "nowlbl", x: X(now) + 3, y: M.t + 9 }, svg);
    tx.textContent = "jetzt";
  }
  // Reihen
  g.series.forEach((s, i) => {
    const p = pts[i];
    const c = color(s);
    if (g.unit === "°") {
      for (const [t, v] of p) el("circle", { cx: X(t), cy: Y(v), r: 2.6, fill: c }, svg);
      return;
    }
    let d = "", prev = null;
    for (const [t, v] of p) {
      const gap = prev && t - prev > 4 * 3600000;
      d += `${d && !gap ? "L" : "M"}${X(t).toFixed(1)},${Y(v).toFixed(1)}`;
      prev = t;
    }
    const path = el("path", { d, class: `series${s.role === "klima" ? " klima" : ""}`, stroke: c }, svg);
    if (s.dashed) path.setAttribute("stroke-dasharray", "5 3");
    if (p.length < 40) for (const [t, v] of p) el("circle", { cx: X(t), cy: Y(v), r: 2.5, fill: c }, svg);
  });
  // Fadenkreuz
  const hair = el("line", { class: "hair", y1: M.t, y2: H - M.b, visibility: "hidden" }, svg);
  const hit = el("rect", { x: M.l, y: 0, width: W - M.l - M.r, height: H, fill: "transparent", tabindex: 0 }, svg);
  const tip = document.getElementById("tip");
  const allT = [...new Set(pts.flat().map(([t]) => t))].sort((a, b) => a - b);
  const show = (clientX, clientY) => {
    if (!allT.length) return;
    const r = svg.getBoundingClientRect();
    const xv = M.l + (clientX - r.left) / r.width * W;
    const tv = x0 + (xv - M.l) / (W - M.l - M.r) * (x1 - x0);
    const t = allT.reduce((a, b) => Math.abs(b - tv) < Math.abs(a - tv) ? b : a);
    hair.setAttribute("x1", X(t)); hair.setAttribute("x2", X(t)); hair.setAttribute("visibility", "visible");
    const rows = g.series.map((s, i) => {
      const hitp = pts[i].find(([tt]) => tt === t);
      return `<div class="row"><i style="border-color:${color(s)}"></i>${s.label}: <b>${hitp ? fmtNum(hitp[1], g.unit) : "–"}</b></div>`;
    }).join("");
    tip.innerHTML = `<div><b>${dayFmt.format(new Date(t))} ${hourFmt.format(new Date(t))}</b></div>${rows}`;
    tip.hidden = false;
    const tw = tip.offsetWidth;
    tip.style.left = `${Math.min(window.innerWidth - tw - 8, clientX + 12)}px`;
    tip.style.top = `${clientY + 14}px`;
  };
  hit.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
  hit.addEventListener("pointerdown", (e) => show(e.clientX, e.clientY));
  hit.addEventListener("pointerleave", () => { tip.hidden = true; hair.setAttribute("visibility", "hidden"); });
  hit.addEventListener("focus", () => { const r = svg.getBoundingClientRect(); show(r.left + r.width / 2, r.top + 20); });
  hit.addEventListener("blur", () => { tip.hidden = true; hair.setAttribute("visibility", "hidden"); });
  wrap.appendChild(svg);
  return wrap;
}

function unitTitle(unit) {
  return {
    "km/h": "Wind", "hPa": "Druck", "°C": "Temperatur", "%": "Anteil", "°": "Windrichtung", "mm/h": "Niederschlag",
    "mm": "Niederschlag", "J/kg": "Energie", "K": "Temperaturdifferenz", "m ü. M.": "Höhe", "°C/100 m": "Temperaturgradient",
  }[unit] || unit;
}
