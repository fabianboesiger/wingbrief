// wingbrief: Daten, Ampel-Logik, Karte und Detail-Panels.
import { renderCharts } from "./chart.js";

export const TZ = "Europe/Zurich";
export const PH = ["fronten", "gewitter", "regiowind", "wind", "foehn"];
export const SECS = ["morgen", "mittag", "nachmittag"];
export const PH_SHORT = { fronten: "Fronten", gewitter: "Gewitter", regiowind: "Regiowind", wind: "Wind", foehn: "Föhn" };
export const LEVEL = {
  alarm: { label: "Alarmzeichen", short: "Alarm", sym: "!" },
  achtung: { label: "Achtung", short: "Achtung", sym: "!" },
  unsicher: { label: "unsicher", short: "unsicher", sym: "?" },
  ok: { label: "keine Alarmzeichen", short: "ok", sym: "✓" },
  keine_daten: { label: "keine Daten", short: "–", sym: "–" },
};
export const RANK = { alarm: 5, achtung: 4, unsicher: 3, ok: 1, keine_daten: 0 };
export const STATUS = {
  alarm: { label: "Alarmzeichen", sym: "!" },
  achtung: { label: "Achtung", sym: "!" },
  unsicher: { label: "unsicher", sym: "?" },
  neutral: { label: "kein Alarmzeichen", sym: "·" },
  guenstig: { label: "günstig", sym: "✓" },
  keine_daten: { label: "keine Daten", sym: "–" },
  selbst_pruefen: { label: "selbst prüfen", sym: "↗" },
  trifft_zu: { label: "trifft zu", sym: "●" },
  trifft_nicht_zu: { label: "trifft nicht zu", sym: "○" },
};
export const KIND = { alarm: "Alarmzeichen", guenstig: "Günstiges Zeichen", faktor: "Rahmenbedingung" };
export const DATA = { A: "automatisch", T: "Näherung", L: "selbst prüfen" };

// Kleine Symbole je Phänomen (24×24, Strich)
export const ICON = {
  fronten: '<path d="M4 15a4 4 0 0 1 1-7.9A5.5 5.5 0 0 1 15.6 6 3.8 3.8 0 0 1 19 13.5H6"/><path d="M8 18l-1 2M12 18l-1 2M16 18l-1 2"/>',
  gewitter: '<path d="M5 13a4 4 0 0 1 .8-7.9A5.5 5.5 0 0 1 16.4 5 3.8 3.8 0 0 1 18 12.4"/><path d="M12 11l-3 5h4l-2 5"/>',
  regiowind: '<path d="M2 19l6-9 4 5 3-4 7 8"/><path d="M6 6c2-1.5 4 1.5 6 0s4 1.5 6 0"/>',
  wind: '<path d="M3 8h11a3 3 0 1 0-3-3"/><path d="M3 12h16a3 3 0 1 1-3 3"/><path d="M3 16h7"/>',
  foehn: '<path d="M2 20l7-12 4 6 2-3 7 9"/><path d="M14 4c2 0 3 1 5 1M15 7c2 0 3 1 5 1"/>',
};
export const icon = (ph, cls = "ic") =>
  `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[ph]}</svg>`;

export let IDX = null, META = null;
const detailCache = new Map();

export async function load(base = "data/") {
  [IDX, META] = await Promise.all([
    fetch(base + "index.json?t=" + Math.floor(Date.now() / 600000)).then((r) => r.json()),
    fetch(base + "meta.json?t=" + Math.floor(Date.now() / 600000)).then((r) => r.json()),
  ]);
  return { IDX, META };
}
export function loadDetail(uid, base = "data/") {
  if (!detailCache.has(uid)) detailCache.set(uid, fetch(`${base}detail/${uid}.json?v=${encodeURIComponent(IDX.generated)}`).then((r) => (r.ok ? r.json() : null)));
  return detailCache.get(uid);
}

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const isRegion = (id) => id in META.regions;
export const unitName = (id) => (META.regions[id] || META.valleys[id]).name;
export const phName = (ph) => META.catalog.phenomena[ph].name;
export const worst = (lv) => lv.reduce((a, b) => ((RANK[b] ?? 0) > (RANK[a] ?? 0) ? b : a), "keine_daten");

const wd = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, weekday: "short" });
const dm = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, day: "numeric", month: "numeric" });
const dtf = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
export const fmtDateTime = (iso) => dtf.format(new Date(iso));
export function dayParts(d) {
  const i = Number(d.slice(1));
  const dt = new Date(IDX.days[i].date + "T12:00:00");
  return { rel: i === 0 ? "Heute" : i === 1 ? "Morgen" : wd.format(dt).replace(".", ""), wd: wd.format(dt).replace(".", ""), date: dm.format(dt), i };
}
export const dayKeys = () => IDX.days.map((d) => d.key);
export const secInfo = (s) => IDX.sections.find((x) => x.key === s);
export const secLabel = (s) => (s === "tag" ? "Ganzer Tag" : secInfo(s).label);
export const secRange = (s) => (s === "tag" ? "6–18 Uhr" : `${secInfo(s).from}–${secInfo(s).to} Uhr`);

const cell = (uid, d, s) => IDX.status[uid]?.[d]?.[s];
export function fullLevel(uid, d, s, ph) {
  if (s === "tag") return worst(SECS.map((x) => cell(uid, d, x)?.full?.[ph] ?? "keine_daten"));
  return cell(uid, d, s)?.full?.[ph] ?? "keine_daten";
}
export const unitLevel = (uid, d, s) => worst(PH.map((p) => fullLevel(uid, d, s, p)));
export const chainCount = (uid, d, s) => PH.filter((p) => fullLevel(uid, d, s, p) === "alarm").length;
export const isPast = (d, s) => s !== "tag" && !!cell(Object.keys(IDX.status)[0], d, s)?.past;

export function defaultSelection() {
  for (const d of dayKeys()) for (const s of SECS) if (!isPast(d, s)) return [d, s];
  return ["d0", "tag"];
}

export function checkStatus(uid, d, s, cid) {
  if (s !== "tag") return cell(uid, d, s)?.checks?.[cid] ?? ["keine_daten", ""];
  const order = { alarm: 6, achtung: 5, unsicher: 4, trifft_zu: 3, selbst_pruefen: 3, neutral: 2, trifft_nicht_zu: 2, guenstig: 1, keine_daten: 0 };
  const all = SECS.map((x) => cell(uid, d, x)?.checks?.[cid]).filter(Boolean);
  if (!all.length) return ["keine_daten", ""];
  if (META.catalog.checks[cid].kind === "guenstig" && all.every((c) => c[0] === "guenstig")) return all[1] || all[0];
  return all.reduce((a, b) => (order[b[0]] > order[a[0]] ? b : a));
}

/** Einheit, deren Checks ein Phänomen bestimmen (Täler erben Fronten/Gewitter/Wind von der Region). */
export function ownerOf(uid, ph) {
  const unit = META.catalog.phenomena[ph].unit;
  if (unit === "region" && !isRegion(uid)) return META.valleys[uid].region;
  return uid;
}
export const checksOf = (ph) => Object.keys(META.catalog.checks).filter((c) => META.catalog.checks[c].phenomenon === ph);

/** Ein Satz Begründung für ein Phänomen: auslösender Check und sein Wert. */
export function reason(uid, d, s, ph) {
  const lv = fullLevel(uid, d, s, ph);
  if (META.catalog.phenomena[ph].unit === "valley" && isRegion(uid)) {
    const vs = META.regions[uid].valleys;
    if (!vs.length) return { lv, text: "keine Täler hinterlegt", cid: null, owner: uid };
    const wv = vs.reduce((a, b) => ((RANK[fullLevel(b, d, s, ph)] ?? 0) > (RANK[fullLevel(a, d, s, ph)] ?? 0) ? b : a));
    const r = reason(wv, d, s, ph);
    const n = vs.filter((v) => fullLevel(v, d, s, ph) === "alarm").length;
    return { ...r, lv, text: n ? `${n} von ${vs.length} Tälern, z. B. ${unitName(wv)}: ${r.text}` : r.text, owner: wv };
  }
  const owner = ownerOf(uid, ph);
  const cat = META.catalog.checks;
  const ids = checksOf(ph);
  const pick = (pred) => ids.find((c) => pred(cat[c], checkStatus(owner, d, s, c)));
  const order = [
    (c, st) => c.kind === "alarm" && c.data === "A" && st[0] === "alarm",
    (c, st) => c.kind === "alarm" && st[0] === "unsicher",
    (c, st) => c.kind === "guenstig" && st[0] === "unsicher",
    (c, st) => c.kind === "alarm" && (st[0] === "achtung" || (c.data === "T" && st[0] === "alarm")),
  ];
  for (const p of order) {
    const cid = pick(p);
    if (cid) return { lv, cid, owner, text: checkStatus(owner, d, s, cid)[1] || cat[cid].shv.split("→")[0].trim() };
  }
  const good = ids.find((c) => cat[c].kind === "guenstig");
  if (good) {
    const st = checkStatus(owner, d, s, good);
    if (lv === "ok") return { lv, cid: good, owner, text: st[1] || "günstige Zeichen erfüllt" };
    return { lv, cid: good, owner, text: `kein Alarmzeichen; günstiges Zeichen nicht erfüllt (${st[1] || "–"})` };
  }
  return { lv, cid: null, owner, text: "" };
}

// ------------------------------------------------------------ Check-Detail (gemeinsam)
export function checkDetailHtml(uid, cid, d, s) {
  const c = META.catalog.checks[cid];
  const owner = ownerOf(uid, c.phenomenon);
  const [st, val, ens] = checkStatus(owner, d, s, cid);
  const thr = Object.entries(c.thresholds || {}).map(([k, t]) =>
    `<tr><td>${esc(thrLabel(k))}</td><td class="num">${t.value}</td><td>${esc(t.source)}</td></tr>`).join("");
  const links = (c.links || []).map((l) => META.catalog.links[l]).filter(Boolean)
    .map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)} ↗</a>`).join(" ");
  const strip = dayKeys().map((dd) => `<div class="cd-day"><span>${dayParts(dd).rel}</span><div>${SECS.map((x) => {
    const sx = checkStatus(owner, dd, x, cid)[0];
    return `<i class="st-${sx}${dd === d && (x === s || s === "tag") ? " sel" : ""}" title="${secLabel(x)}: ${STATUS[sx]?.label}">${STATUS[sx]?.sym ?? ""}</i>`;
  }).join("")}</div></div>`).join("");
  return `<div class="cd">
    <div class="cd-head"><span class="cd-id">${cid}</span><span class="pill st-${st}">${STATUS[st]?.sym} ${STATUS[st]?.label}</span></div>
    <p class="cd-value">${esc(val) || "kein Wert"}${ens ? `<br><small>Ensemble: ${Math.round(ens[0] * 100)} % der Members mit Alarm</small>` : ""}</p>
    <div class="cd-strip">${strip}</div>
    <blockquote class="cd-shv"><small>SHV-Plakat · Planung · ${c.stage === "fortgeschritten" ? "Fortgeschritten" : "Basis"} · ${KIND[c.kind]}</small>${esc(c.shv)}</blockquote>
    <h4>So prüft wingbrief <small>(${DATA[c.data]})</small></h4><p>${esc(c.rule)}</p>
    ${thr ? `<table class="cd-thr"><tr><th>Schwelle</th><th>Wert</th><th>Quelle</th></tr>${thr}</table>` : ""}
    ${links ? `<p class="cd-links">${links}</p>` : ""}
    ${owner !== uid ? `<p class="cd-note">Gilt für die Region ${esc(unitName(owner))}.</p>` : ""}
    <div class="cd-charts"></div>
    <details class="cd-raw"><summary>Alle Werte als Tabelle</summary><div class="cd-rawwrap"></div></details>
  </div>`;
}

const THR = {
  rate_mm_h: "Niederschlagsrate", west_cover: "Fläche im Westen", wind_kmh: "Wind", drop_k: "Abkühlung", qff_hpa: "Bodendruck",
  grad_hpa: "Druckspannweite", max_mm_h: "Max. Intensität", cover: "Fläche", cape: "CAPE", theta_e_c: "Theta-E", lapse: "Gradient",
  sink_m: "Absinken Inversion", rise_hpa: "Druckanstieg", inversion_k: "Inversion", rh: "Rel. Feuchte", snow: "Schnee",
  precip_mm: "Niederschlag", pct: "Klima-Perzentil", min_kmh: "Mindestwind", warn_kmh: "Achtung ab", alarm_kmh: "Alarm ab",
  mean_kmh: "Mittelwind", gust_kmh: "Böen", dp_hpa: "Druckdifferenz", warn_hpa: "Achtung ab", alarm_hpa: "Alarm ab",
  angle: "Winkel", warn_k: "Achtung ab", alarm_k: "Alarm ab", dt_k: "Temperaturdifferenz",
};
const thrLabel = (k) => THR[k] || k;

export async function fillCheckDetail(root, uid, cid, d, s) {
  const c = META.catalog.checks[cid];
  const owner = ownerOf(uid, c.phenomenon);
  const ch = root.querySelector(".cd-charts");
  const raw = root.querySelector(".cd-rawwrap");
  if (c.data === "L") {
    ch.innerHTML = `<p class="cd-note">Nicht als offene Daten verfügbar. Bitte selbst prüfen.</p>`;
    root.querySelector(".cd-raw").hidden = true;
    return;
  }
  const det = await loadDetail(owner);
  const x = det?.checks?.[cid];
  if (!x) { ch.innerHTML = '<p class="cd-note">Keine Detaildaten.</p>'; return; }
  const run = new Date(IDX.model.run);
  const today0 = new Date(IDX.days[0].date + "T00:00:00");
  const x0 = new Date(Math.min(run.getTime(), today0.getTime()) - (cid === "R6" ? 86400000 : 0));
  renderCharts(ch, x.series, { x0, x1: new Date(run.getTime() + 120 * 3600000), band: band(d, s) });
  raw.innerHTML = `<table><tr><th>Zeit</th><th>Status</th><th>Wert</th></tr>${x.entries.map((e) =>
    `<tr><td>${fmtDateTime(e[0])}</td><td>${STATUS[e[1]]?.label ?? e[1]}${e[3] ? " (Ens.)" : ""}</td><td>${esc(e[2])}</td></tr>`).join("")}</table>`;
}

function band(d, s) {
  const date = IDX.days[Number(d.slice(1))].date;
  const lo = s === "tag" ? 6 : secInfo(s).from, hi = s === "tag" ? 18 : secInfo(s).to;
  return [zurich(date, lo), zurich(date, hi)];
}
function zurich(date, hour) {
  const g = new Date(`${date}T${String(hour).padStart(2, "0")}:00:00Z`);
  const h = Number(new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", hourCycle: "h23" }).format(g));
  return new Date(g.getTime() - (h - hour) * 3600000);
}

// ------------------------------------------------------------ Karte
export const BOUNDS = { lon0: 5.85, lon1: 10.6, lat0: 45.75, lat1: 47.9 };
const KX = Math.cos(46.8 * Math.PI / 180);
export const MAPW = 640;
export const MAPH = Math.round(MAPW * (BOUNDS.lat1 - BOUNDS.lat0) / ((BOUNDS.lon1 - BOUNDS.lon0) * KX));
export const proj = ([lat, lon]) => [(lon - BOUNDS.lon0) / (BOUNDS.lon1 - BOUNDS.lon0) * MAPW, (BOUNDS.lat1 - lat) / (BOUNDS.lat1 - BOUNDS.lat0) * MAPH];
let CH = null, CELLS = null;
export async function mapGeometry() {
  if (!CH) {
    const gj = await (await fetch("geo/ch.json")).json();
    CH = gj.geometry.coordinates.map((poly) => poly.map((ring) => "M" + ring.map(([lo, la]) => proj([la, lo]).map((v) => v.toFixed(1)).join(",")).join("L") + "Z").join("")).join("");
  }
  if (!CELLS) {
    const ids = Object.keys(META.regions);
    const pts = ids.map((id) => proj(META.regions[id].center));
    try {
      const { Delaunay } = await import("https://cdn.jsdelivr.net/npm/d3-delaunay@6.0.4/+esm");
      const v = Delaunay.from(pts).voronoi([-40, -40, MAPW + 40, MAPH + 40]);
      CELLS = Object.fromEntries(ids.map((id, i) => [id, v.renderCell(i)]));
    } catch {
      CELLS = Object.fromEntries(ids.map((id, i) => [id, `M${pts[i][0] - 30},${pts[i][1]}a30,30 0 1,0 60,0a30,30 0 1,0 -60,0`]));
    }
  }
  return { ch: CH, cells: CELLS, valleys: Object.fromEntries(Object.entries(META.valleys).map(([k, v]) => [k, "M" + v.axis.map((p) => proj(p).map((x) => x.toFixed(1)).join(",")).join("L")])) };
}

export const store = {
  get(k, d) { try { return localStorage.getItem("wbd." + k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("wbd." + k, v); } catch { /* egal */ } },
};

// ------------------------------------------------------------ Sheet mit Zurück-Stapel
const stack = [];
let sheetEl = null, backdrop = null;
export function openSheet(view, { replace = false } = {}) {
  if (replace) stack.length = 0;
  stack.push(view);
  renderSheet();
}
export function closeSheet() {
  stack.length = 0;
  sheetEl?.remove(); backdrop?.remove(); sheetEl = backdrop = null;
  document.getElementById("tip").hidden = true;
}
function renderSheet() {
  const v = stack[stack.length - 1];
  if (!sheetEl) {
    backdrop = document.createElement("div");
    backdrop.className = "sheet-backdrop";
    backdrop.onclick = closeSheet;
    sheetEl = document.createElement("aside");
    sheetEl.className = "sheet";
    sheetEl.setAttribute("role", "dialog");
    sheetEl.setAttribute("aria-modal", "true");
    document.body.append(backdrop, sheetEl);
    document.addEventListener("keydown", escClose);
  }
  sheetEl.innerHTML = `<div class="grab"></div><div class="sheet-top">${stack.length > 1 ? '<button class="iconbtn" data-back aria-label="Zurück">‹</button>' : ""}
    <h3>${v.title}</h3><button class="iconbtn" data-close aria-label="Schliessen">×</button></div><div class="sheet-body"></div>`;
  sheetEl.querySelector("[data-close]").onclick = closeSheet;
  const back = sheetEl.querySelector("[data-back]");
  if (back) back.onclick = () => { stack.pop(); renderSheet(); };
  sheetEl.scrollTop = 0;
  v.render(sheetEl.querySelector(".sheet-body"));
  (back || sheetEl.querySelector("[data-close]")).focus({ preventScroll: true });
}
function escClose(e) {
  if (e.key === "Escape" && sheetEl) { closeSheet(); document.removeEventListener("keydown", escClose); }
}

/** Standard-Ansichten für die Sheets: Phänomen → Checks, Check → Detail. */
export function phenomenonView(uid, ph, d, s, onUnit) {
  return {
    title: `${icon(ph)} ${esc(phName(ph))} · ${esc(unitName(uid))}`,
    render(el) {
      const r = reason(uid, d, s, ph);
      const p = META.catalog.phenomena[ph];
      let list = "";
      if (p.unit === "valley" && isRegion(uid)) {
        list = `<p class="sv-note">Wird pro Tal geprüft.</p><ul class="sv-list">${META.regions[uid].valleys.map((v) => {
          const lv = fullLevel(v, d, s, ph);
          return `<li><button data-unit="${v}"><span class="lv ${lv}">${LEVEL[lv].sym}</span><span><b>${esc(unitName(v))}</b><small>${esc(reason(v, d, s, ph).text)}</small></span><span class="chev">›</span></button></li>`;
        }).join("")}</ul>`;
      } else {
        const owner = ownerOf(uid, ph);
        const groups = { alarm: "Alarmzeichen", guenstig: "Allgemein günstige Zeichen", faktor: "Rahmenbedingungen" };
        list = (owner !== uid ? `<p class="sv-note">Gilt für die ganze Region ${esc(unitName(owner))}.</p>` : "") +
          Object.entries(groups).map(([kind, title]) => {
            const ids = checksOf(ph).filter((c) => META.catalog.checks[c].kind === kind);
            if (!ids.length) return "";
            return `<h4 class="sv-h">${title}</h4><ul class="sv-list">${ids.map((cid) => {
              const c = META.catalog.checks[cid];
              const [st, val] = checkStatus(owner, d, s, cid);
              return `<li><button data-check="${cid}"><span class="lv st-${st}">${STATUS[st]?.sym}</span><span><b>${esc(c.shv.split("→")[0].trim())}</b><small>${esc(val || STATUS[st]?.label)}</small></span><span class="chev">›</span></button></li>`;
            }).join("")}</ul>`;
          }).join("");
      }
      el.innerHTML = `<div class="sv-sum"><span class="pill st-${r.lv}">${LEVEL[r.lv].sym} ${LEVEL[r.lv].label}</span><p>${esc(r.text)}</p></div>
        <details class="sv-about"><summary>Worum es geht</summary><p>${esc(p.inhalt)} <b>Hauptgefahr:</b> ${esc(p.gefahr)}</p></details>${list}`;
      el.querySelectorAll("[data-check]").forEach((b) => b.onclick = () => openSheet(checkView(uid, b.dataset.check, d, s)));
      el.querySelectorAll("[data-unit]").forEach((b) => b.onclick = () => (onUnit ? onUnit(b.dataset.unit) : openSheet(phenomenonView(b.dataset.unit, ph, d, s, onUnit))));
    },
  };
}
export function checkView(uid, cid, d, s) {
  const c = META.catalog.checks[cid];
  return {
    title: esc(c.shv.split("→")[0].trim()),
    render(el) { el.innerHTML = checkDetailHtml(uid, cid, d, s); fillCheckDetail(el, uid, cid, d, s); },
  };
}

/** Tagesbewertung: schlechtester noch kommender Abschnitt (alle, wenn der Tag vorbei ist). */
export function dayLevel(uid, d, ph = null) {
  const live = SECS.filter((s) => !isPast(d, s));
  const secs = live.length ? live : SECS;
  return worst(secs.map((s) => (ph ? fullLevel(uid, d, s, ph) : unitLevel(uid, d, s))));
}

/** Schlankes Gebiets-Panel: Status, drei Tagesabschnitte, fünf Phänomene nur mit Status. */
export function unitBriefView(uid, d, { focus = null } = {}) {
  let s = "tag";
  const view = {
    title: esc(unitName(uid)),
    render(el) {
      const lv = s === "tag" ? dayLevel(uid, d) : unitLevel(uid, d, s);
      const p = dayParts(d);
      const secBtn = (x) => {
        const l = x === "tag" ? dayLevel(uid, d) : unitLevel(uid, d, x);
        const past = x !== "tag" && isPast(d, x);
        return `<button class="ub-sec${x === s ? " on" : ""}${past ? " past" : ""}" data-s="${x}" aria-pressed="${x === s}">
          <i class="st-${l}">${LEVEL[l].sym}</i><span>${x === "tag" ? "Ganzer Tag" : secLabel(x)}</span><small>${secRange(x)}</small></button>`;
      };
      const noValleys = isRegion(uid) && !META.regions[uid].valleys.length;
      const shown = PH.filter((ph) => !(noValleys && META.catalog.phenomena[ph].unit === "valley"));
      const phs = (focus ? [focus, ...shown.filter((x) => x !== focus)] : shown).map((ph) => {
        const l = s === "tag" ? dayLevel(uid, d, ph) : fullLevel(uid, d, s, ph);
        return `<li><button data-ph="${ph}"><span class="lv ${l}">${LEVEL[l].sym}</span><span><b>${icon(ph, "ic ic-inline")} ${esc(phName(ph))}</b><small>${LEVEL[l].label}</small></span><span class="chev">›</span></button></li>`;
      }).join("");
      el.innerHTML = `<div class="sv-sum"><span class="pill st-${lv}">${LEVEL[lv].sym} ${LEVEL[lv].label}</span>
          <p class="ub-when">${p.rel}${p.i > 1 ? ` ${p.date}` : ""}</p></div>
        <div class="ub-secs">${[...SECS, "tag"].map(secBtn).join("")}</div>
        <ul class="sv-list">${phs}</ul>${noValleys ? '<p class="sv-note">Regiowind und Föhn werden pro Tal geprüft; für diese Region sind keine Täler hinterlegt.</p>' : ""}
        ${isRegion(uid) && META.regions[uid].valleys.length ? `<details class="ub-valleys"><summary>Täler (${META.regions[uid].valleys.length})</summary><ul class="sv-list">${META.regions[uid].valleys.map((v) => {
          const l = s === "tag" ? dayLevel(v, d) : unitLevel(v, d, s);
          return `<li><button data-valley="${v}"><span class="lv ${l}">${LEVEL[l].sym}</span><span><b>${esc(unitName(v))}</b><small>${LEVEL[l].label}</small></span><span class="chev">›</span></button></li>`;
        }).join("")}</ul></details>` : ""}`;
      el.querySelectorAll(".ub-sec").forEach((b) => b.onclick = () => { s = b.dataset.s; view.render(el); });
      el.querySelectorAll("[data-ph]").forEach((b) => b.onclick = () => openSheet(phenomenonView(uid, b.dataset.ph, d, s, (v) => openSheet(unitBriefView(v, d)))));
      el.querySelectorAll("[data-valley]").forEach((b) => b.onclick = () => openSheet(unitBriefView(b.dataset.valley, d)));
    },
  };
  return view;
}

/** Karte zeichnen. lv(uid) liefert die Stufe; fill = Regionen eingefärbt, sonst nur Punkte. */
export async function drawMap(el, { lv, fill = true, onPick, label = (u) => unitName(u) }) {
  const geo = await mapGeometry();
  const regions = Object.keys(META.regions), valleys = Object.keys(META.valleys);
  const col = (l) => ({ alarm: "var(--s-alarm)", achtung: "var(--s-achtung)", unsicher: "var(--s-unsicher)", ok: "var(--s-ok)" }[l] || "var(--s-keine)");
  const cells = regions.map((r) => { const l = lv(r);
    return `<path class="m-cell ${fill ? `m-f-${l}` : "m-plain"}" d="${geo.cells[r]}" clip-path="url(#m-clip)" tabindex="0" role="button" data-u="${r}" aria-label="${esc(label(r))}: ${LEVEL[l].label}"><title>${esc(label(r))}: ${LEVEL[l].label}</title></path>`; }).join("");
  const vals = valleys.map((v) => { const l = lv(v);
    return `<path class="m-vring" d="${geo.valleys[v]}"/><path class="m-valley" stroke="${col(l)}" d="${geo.valleys[v]}" tabindex="0" role="button" data-u="${v}" aria-label="${esc(label(v))}: ${LEVEL[l].label}"><title>${esc(label(v))}: ${LEVEL[l].label}</title></path>`; }).join("");
  const marks = regions.map((r) => { const l = lv(r); const [x, y] = proj(META.regions[r].center); const R = fill ? 9 : 12;
    return `<g class="m-mark"><circle cx="${x}" cy="${y}" r="${R}" fill="${col(l)}"/><text x="${x}" y="${y + (fill ? 4 : 4.5)}" fill="${l === "achtung" ? "var(--on-warn)" : "#fff"}" font-size="${fill ? 11 : 13}">${LEVEL[l].sym}</text></g>`; }).join("");
  el.innerHTML = `<svg class="m-map" viewBox="0 0 ${MAPW} ${MAPH}" role="img" aria-label="Karte der Schweiz mit Regionen und Tälern">
    <defs><clipPath id="m-clip"><path d="${geo.ch}"/></clipPath><pattern id="m-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--land)"/><rect width="3" height="6" fill="var(--s-unsicher)"/></pattern></defs>
    <path class="m-land" d="${geo.ch}"/>${cells}<path class="m-outline" d="${geo.ch}"/>${vals}${marks}</svg>`;
  el.querySelectorAll("[data-u]").forEach((n) => {
    n.addEventListener("click", () => onPick(n.dataset.u));
    n.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(n.dataset.u); } });
  });
}
export const legendHtml = () => ["alarm", "achtung", "unsicher", "ok"].map((l) => `<span><i class="lv ${l}">${LEVEL[l].sym}</i>${LEVEL[l].label}</span>`).join("");
