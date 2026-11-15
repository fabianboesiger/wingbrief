// wingbrief – statische Seite. Liest data/index.json, data/meta.json, data/detail/<einheit>.json.
import { renderCharts } from "./chart.js";

const TZ = "Europe/Zurich";
const app = document.getElementById("app");
const PH_ORDER = ["fronten", "gewitter", "regiowind", "wind", "foehn"];
const SECS = ["morgen", "mittag", "nachmittag"];
const LEVEL = {
  alarm: { label: "Alarmzeichen", sym: "!" },
  achtung: { label: "Achtung", sym: "!" },
  unsicher: { label: "unsicher", sym: "?" },
  ok: { label: "keine Alarmzeichen", sym: "✓" },
  keine_daten: { label: "keine Daten", sym: "–" },
};
const LEVEL_RANK = { alarm: 5, achtung: 4, unsicher: 3, ok: 1, keine_daten: 0 };
const STATUS = {
  alarm: { label: "Alarmzeichen", sym: "!" },
  achtung: { label: "Achtung", sym: "!" },
  unsicher: { label: "unsicher (Ensemble)", sym: "?" },
  neutral: { label: "kein Alarmzeichen", sym: "·" },
  guenstig: { label: "günstig", sym: "✓" },
  keine_daten: { label: "keine Daten", sym: "–" },
  selbst_pruefen: { label: "selbst prüfen", sym: "◎" },
  trifft_zu: { label: "trifft zu", sym: "●" },
  trifft_nicht_zu: { label: "trifft nicht zu", sym: "○" },
};
const KIND = { alarm: "Alarmzeichen", guenstig: "günstiges Zeichen", faktor: "Rahmenbedingung" };
const DATA = { A: "automatisch", T: "Näherung", L: "selbst prüfen" };

let IDX, META;
const detailCache = new Map();
const store = {
  get(k, d) { try { return localStorage.getItem("wb." + k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("wb." + k, v); } catch { /* egal */ } },
};
const state = { day: null, sec: null, ph: store.get("ph", "alle") };

// ------------------------------------------------------------ Hilfen
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dateFmt = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, weekday: "short", day: "numeric", month: "numeric" });
const dtFmt = new Intl.DateTimeFormat("de-CH", { timeZone: TZ, weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
const isRegion = (id) => id in META.regions;
const unitName = (id) => (META.regions[id] || META.valleys[id]).name;
const phName = (ph) => META.catalog.phenomena[ph].name;
const secLabel = (s) => s === "tag" ? "Ganzer Tag" : IDX.sections.find((x) => x.key === s).label;
const secRange = (s) => { const x = IDX.sections.find((y) => y.key === s); return `${x.from}–${x.to} Uhr`; };

function dayLabel(d) {
  const i = Number(d.slice(1));
  const dt = new Date(IDX.days[i].date + "T12:00:00");
  const base = dateFmt.format(dt);
  return i === 0 ? `Heute, ${base}` : (i === 1 ? `Morgen, ${base}` : base);
}

function worst(levels) {
  return levels.reduce((a, b) => (LEVEL_RANK[b] ?? 0) > (LEVEL_RANK[a] ?? 0) ? b : a, "keine_daten");
}

function cell(uid, d, s) { return IDX.status[uid]?.[d]?.[s]; }

function fullLevel(uid, d, s, ph) {
  if (s === "tag") return worst(SECS.map((x) => cell(uid, d, x)?.full?.[ph] ?? "keine_daten"));
  return cell(uid, d, s)?.full?.[ph] ?? "keine_daten";
}
function chainCount(uid, d, s) {
  if (s === "tag") return PH_ORDER.filter((ph) => fullLevel(uid, d, "tag", ph) === "alarm").length;
  return cell(uid, d, s)?.chain ?? 0;
}
function unitLevel(uid, d, s, ph = "alle") {
  if (ph !== "alle") return fullLevel(uid, d, s, ph);
  return worst(PH_ORDER.map((p) => fullLevel(uid, d, s, p)));
}
function checkStatus(uid, d, s, cid) {
  if (s !== "tag") return cell(uid, d, s)?.checks?.[cid] ?? ["keine_daten", ""];
  const order = { alarm: 6, achtung: 5, unsicher: 4, trifft_zu: 3, selbst_pruefen: 3, neutral: 2, trifft_nicht_zu: 2, guenstig: 1, keine_daten: 0 };
  const all = SECS.map((x) => cell(uid, d, x)?.checks?.[cid]).filter(Boolean);
  if (!all.length) return ["keine_daten", ""];
  const kind = META.catalog.checks[cid].kind;
  if (kind === "guenstig" && all.every((c) => c[0] === "guenstig")) return all[1] || all[0];
  return all.reduce((a, b) => (order[b[0]] > order[a[0]] ? b : a));
}

const levelDot = (lv) => `<span class="dot ${lv}" aria-hidden="true">${LEVEL[lv]?.sym ?? ""}</span>`;
const levelBadge = (lv) => `<span class="st">${levelDot(lv)}${LEVEL[lv]?.label ?? lv}</span>`;
const statusDot = (st) => `<span class="dot ${st}" aria-hidden="true">${STATUS[st]?.sym ?? ""}</span>`;

function sectionPast(d, s) {
  if (s === "tag") return SECS.every((x) => cell(Object.keys(IDX.status)[0], d, x)?.past);
  return !!cell(Object.keys(IDX.status)[0], d, s)?.past;
}

function defaultSelection() {
  const first = Object.keys(IDX.status)[0];
  for (const d of IDX.days.map((x) => x.key)) {
    for (const s of SECS) if (!cell(first, d, s)?.past) return [d, s];
  }
  return ["d0", "tag"];
}

// ---------------------------------------------------------- Wähler
function controls(onChange) {
  const box = document.createElement("div");
  box.className = "controls";
  const days = document.createElement("div");
  days.className = "seg"; days.setAttribute("role", "group"); days.setAttribute("aria-label", "Tag");
  for (const { key } of IDX.days) {
    const b = document.createElement("button");
    b.textContent = dayLabel(key);
    b.setAttribute("aria-pressed", String(state.day === key));
    b.onclick = () => { state.day = key; if (sectionPast(key, state.sec) && state.sec !== "tag") state.sec = "tag"; onChange(); };
    days.appendChild(b);
  }
  const secs = document.createElement("div");
  secs.className = "seg"; secs.setAttribute("role", "group"); secs.setAttribute("aria-label", "Tagesabschnitt");
  for (const s of [...SECS, "tag"]) {
    const b = document.createElement("button");
    b.textContent = s === "tag" ? "Ganzer Tag" : `${secLabel(s)} ${secRange(s)}`;
    b.setAttribute("aria-pressed", String(state.sec === s));
    if (s !== "tag" && sectionPast(state.day, s)) { b.classList.add("past"); b.title = "bereits vorbei"; }
    b.onclick = () => { state.sec = s; onChange(); };
    secs.appendChild(b);
  }
  box.append(days, secs);
  return box;
}

// -------------------------------------------------------------- Karte
const BOUNDS = { lon0: 5.85, lon1: 10.6, lat0: 45.75, lat1: 47.9 };
const KX = Math.cos(46.8 * Math.PI / 180);
const MAPW = 640, MAPH = Math.round(MAPW * (BOUNDS.lat1 - BOUNDS.lat0) / ((BOUNDS.lon1 - BOUNDS.lon0) * KX));
const proj = ([lat, lon]) => [
  (lon - BOUNDS.lon0) / (BOUNDS.lon1 - BOUNDS.lon0) * MAPW,
  (BOUNDS.lat1 - lat) / (BOUNDS.lat1 - BOUNDS.lat0) * MAPH,
];
let CH_PATH = null, Delaunay = null;

async function loadMapDeps() {
  if (!CH_PATH) {
    const gj = await (await fetch("geo/ch.json")).json();
    CH_PATH = gj.geometry.coordinates.map((poly) => poly.map((ring) =>
      "M" + ring.map(([lon, lat]) => proj([lat, lon]).map((v) => v.toFixed(1)).join(",")).join("L") + "Z").join("")).join("");
  }
  if (!Delaunay) {
    try { ({ Delaunay } = await import("https://cdn.jsdelivr.net/npm/d3-delaunay@6.0.4/+esm")); } catch { Delaunay = false; }
  }
}

const levelColor = (lv) => ({ alarm: "var(--s-alarm)", achtung: "var(--s-achtung)", unsicher: "url(#hatch)", ok: "var(--s-ok)" }[lv] || "var(--s-keine)");

function mapSvg({ onlyUnit = null, points = null } = {}) {
  const ids = Object.keys(META.regions);
  const centers = ids.map((id) => proj(META.regions[id].center));
  let cells = "";
  if (!points) {
    if (Delaunay) {
      const vor = Delaunay.from(centers).voronoi([-40, -40, MAPW + 40, MAPH + 40]);
      ids.forEach((id, i) => {
        const lv = unitLevel(id, state.day, state.sec, state.ph);
        const op = onlyUnit && onlyUnit !== id ? ' opacity="0.35"' : "";
        cells += `<path class="cell" d="${vor.renderCell(i)}" fill="${levelColor(lv)}"${op} clip-path="url(#chclip)" tabindex="0" role="link"
          data-href="#/r/${id}" aria-label="${esc(META.regions[id].name)}: ${LEVEL[lv].label}"><title>${esc(META.regions[id].name)}: ${LEVEL[lv].label}</title></path>`;
      });
    } else {
      ids.forEach((id, i) => {
        const lv = unitLevel(id, state.day, state.sec, state.ph);
        cells += `<circle class="cell" cx="${centers[i][0]}" cy="${centers[i][1]}" r="26" fill="${levelColor(lv)}" tabindex="0" role="link" data-href="#/r/${id}"><title>${esc(META.regions[id].name)}</title></circle>`;
      });
    }
  }
  let valleys = "";
  const showValleys = !points && (state.ph === "alle" || state.ph === "regiowind" || state.ph === "foehn");
  if (showValleys) {
    for (const [vid, v] of Object.entries(META.valleys)) {
      const lv = state.ph === "alle" ? worst(["regiowind", "foehn"].map((p) => fullLevel(vid, state.day, state.sec, p))) : fullLevel(vid, state.day, state.sec, state.ph);
      const d = "M" + v.axis.map((p) => proj(p).map((x) => x.toFixed(1)).join(",")).join("L");
      const op = onlyUnit && onlyUnit !== vid && onlyUnit !== v.region ? ' opacity="0.35"' : "";
      valleys += `<path class="valley-ring" d="${d}"${op}/><path class="valley" d="${d}" stroke="${levelColor(lv)}"${op} tabindex="0" role="link"
        data-href="#/v/${vid}" aria-label="${esc(v.name)}: ${LEVEL[lv].label}"><title>${esc(v.name)}: ${LEVEL[lv].label}</title></path>`;
    }
  }
  let badges = "";
  if (!points) ids.forEach((id, i) => {
    const n = chainCount(id, state.day, state.sec);
    if (n > 0) badges += `<circle cx="${centers[i][0]}" cy="${centers[i][1]}" r="10" fill="var(--surface-1)" stroke="var(--text-primary)" stroke-width="1.5"/><text class="chain" x="${centers[i][0]}" y="${centers[i][1] + 4}" text-anchor="middle">${n}</text>`;
  });
  let dots = "";
  if (points) points.forEach((p, i) => {
    const [x, y] = proj([p.lat, p.lon]);
    dots += `<circle cx="${x}" cy="${y}" r="5" fill="var(--series-${(i % 8) + 1})" stroke="var(--surface-1)" stroke-width="2"/><text class="lbl" x="${x + 7}" y="${y + 4}">${i + 1}</text>`;
  });
  return `<svg class="map" viewBox="0 0 ${MAPW} ${MAPH}" role="img" aria-label="Karte der Schweiz">
    <defs><clipPath id="chclip"><path d="${CH_PATH}"/></clipPath>
      <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="6" height="6" fill="var(--surface-2)"/><rect width="3" height="6" fill="var(--s-unsicher)"/></pattern></defs>
    <path class="land" d="${CH_PATH}"/>${cells}<path d="${CH_PATH}" fill="none" stroke="var(--map-line)" stroke-width="1.2"/>${valleys}${badges}${dots}</svg>`;
}

function wireMap(root) {
  root.querySelectorAll("[data-href]").forEach((n) => {
    n.addEventListener("click", () => { location.hash = n.dataset.href; });
    n.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); location.hash = n.dataset.href; } });
  });
}

function legendHtml() {
  return `<div class="legend">${["alarm", "achtung", "unsicher", "ok", "keine_daten"].map((l) => levelBadge(l)).join("")}
    <span class="st"><span class="dot neutral" aria-hidden="true">2</span>Phänomene mit Alarmzeichen (Verkettung)</span></div>`;
}

// ------------------------------------------------------------ Ansichten
async function viewHome() {
  await loadMapDeps();
  const render = () => {
    app.innerHTML = "";
    const h = document.createElement("h1");
    h.textContent = "Planung: Alarmzeichen nach Region und Tal";
    app.appendChild(h);
    app.appendChild(controls(render));
    const phSeg = document.createElement("div");
    phSeg.className = "seg"; phSeg.setAttribute("role", "group"); phSeg.setAttribute("aria-label", "Phänomen");
    for (const p of ["alle", ...PH_ORDER]) {
      const b = document.createElement("button");
      b.textContent = p === "alle" ? "Alle Phänomene" : phName(p);
      b.setAttribute("aria-pressed", String(state.ph === p));
      b.onclick = () => { state.ph = p; store.set("ph", p); render(); };
      phSeg.appendChild(b);
    }
    app.querySelector(".controls").appendChild(phSeg);
    const grid = document.createElement("div");
    grid.className = "grid2";
    const left = document.createElement("div");
    left.innerHTML = `<div class="mapwrap">${mapSvg()}${legendHtml()}</div>
      <p class="muted" style="font-size:.85rem">Flächen: Regionen (Fronten, Gewitter, überregionaler Wind). Linien: Täler (Regiowind, Föhn).
      ${dayLabel(state.day)}, ${secLabel(state.sec)}${state.ph === "alle" ? "" : `, nur ${phName(state.ph)}`}. Antippen für Details.</p>`;
    wireMap(left);
    const right = document.createElement("div");
    right.className = "card";
    right.innerHTML = `<h2>Regionen</h2>${unitList(Object.keys(META.regions))}<h2 style="margin-top:14px">Täler</h2>${unitList(Object.keys(META.valleys))}`;
    grid.append(left, right);
    app.appendChild(grid);
  };
  render();
}

function unitList(ids) {
  const phs = state.ph === "alle" ? PH_ORDER : [state.ph];
  return `<ul class="unitlist">${ids.map((id) => {
    const lv = unitLevel(id, state.day, state.sec, state.ph);
    const n = chainCount(id, state.day, state.sec);
    const chips = phs.map((p) => { const l = fullLevel(id, state.day, state.sec, p); return `<span class="chip">${levelDot(l)}${phName(p)}</span>`; }).join("");
    return `<li><a href="#/${isRegion(id) ? "r" : "v"}/${id}"><span class="uname">${levelDot(lv)} ${esc(unitName(id))}</span>
      <span class="chainbadge">${n ? `${n} von 5 mit Alarmzeichen` : ""}</span><span class="usub">${chips}</span></a></li>`;
  }).join("")}</ul>`;
}

function matrixHtml(uid) {
  let head = "<tr><th></th>" + IDX.days.map((d) => `<th class="day" colspan="3">${esc(dayLabel(d.key).replace(/^(Heute|Morgen), /, "$1 "))}</th>`).join("") + "</tr>";
  head += "<tr><th></th>" + IDX.days.map(() => SECS.map((s) => `<th class="day" title="${secLabel(s)}">${secLabel(s)[0]}</th>`).join("")).join("") + "</tr>";
  const rows = PH_ORDER.map((ph) => `<tr><th>${phName(ph)}</th>${IDX.days.map((d) => SECS.map((s) => {
    const lv = fullLevel(uid, d.key, s, ph);
    const sel = state.day === d.key && (state.sec === s || state.sec === "tag") ? " sel" : "";
    return `<td><button class="cell-${lv}${sel}" data-d="${d.key}" data-s="${s}" aria-label="${phName(ph)}, ${dayLabel(d.key)}, ${secLabel(s)}: ${LEVEL[lv].label}" title="${LEVEL[lv].label}">${LEVEL[lv].sym}</button></td>`;
  }).join("")).join("")}</tr>`).join("");
  const chain = `<tr><th>Verkettung</th>${IDX.days.map((d) => SECS.map((s) => `<td style="text-align:center;font-size:11px">${chainCount(uid, d.key, s) || ""}</td>`).join("")).join("")}</tr>`;
  return `<div class="matrix-wrap"><table class="matrix">${head}${rows}${chain}</table></div>`;
}

function checkRows(uid, ph, routeUnit) {
  const cat = META.catalog;
  const ids = Object.keys(cat.checks).filter((c) => cat.checks[c].phenomenon === ph);
  const stages = { basis: "Basis", fortgeschritten: "Fortgeschritten" };
  let html = "";
  for (const [stage, label] of Object.entries(stages)) {
    const list = ids.filter((c) => cat.checks[c].stage === stage || (stage === "basis" && !cat.checks[c].stage));
    if (!list.length) continue;
    html += `<div class="stage">${label}</div><ul class="checks">`;
    for (const cid of list) {
      const c = cat.checks[cid];
      const [st, val, ens] = checkStatus(uid, state.day, state.sec, cid);
      const ensTxt = ens ? ` · Ensemble: ${Math.round(ens[0] * 100)} % Alarm` : "";
      html += `<li><a href="#/${isRegion(uid) ? "r" : "v"}/${uid}/${cid}">${statusDot(st)}
        <span class="ctext"><span class="cid">${cid}</span>${esc(c.shv)}<span class="kindtag">${KIND[c.kind]}</span>${c.data !== "A" ? `<span class="kindtag">${DATA[c.data]}</span>` : ""}</span>
        <span class="cval">${STATUS[st]?.label ?? st}${val ? `: ${esc(val)}` : ""}${ensTxt}</span></a></li>`;
    }
    html += "</ul>";
  }
  return html;
}

function phenomenonCard(uid, ph) {
  const p = META.catalog.phenomena[ph];
  const lv = fullLevel(uid, state.day, state.sec, ph);
  let body = "";
  const region = isRegion(uid);
  if (p.unit === "valley" && region) {
    const vids = META.regions[uid].valleys;
    body = vids.length ? `<p class="inherit">${phName(ph)} wird pro Tal geprüft:</p><ul class="unitlist">${vids.map((v) => {
      const l = fullLevel(v, state.day, state.sec, ph);
      return `<li><a href="#/v/${v}"><span class="uname">${levelDot(l)} ${esc(unitName(v))}</span><span class="chainbadge">${LEVEL[l].label}</span></a></li>`;
    }).join("")}</ul>` : `<p class="inherit">Für diese Region sind keine Täler hinterlegt.</p>`;
  } else if (p.unit === "region" && !region) {
    const rid = META.valleys[uid].region;
    body = `<p class="inherit">Geprüft für die Region <a href="#/r/${rid}">${esc(unitName(rid))}</a>.</p>${checkRows(rid, ph)}`;
  } else {
    body = checkRows(uid, ph);
  }
  return `<section class="card ph lv-${lv}" id="ph-${ph}">
    <div class="phhead"><h2>${phName(ph)}</h2>${levelBadge(lv)}</div>
    <details class="about"><summary>Worum es geht (SHV)</summary><p><b>Inhalt:</b> ${esc(p.inhalt)}</p>
      <p><b>Hauptgefahr:</b> ${esc(p.gefahr)}</p><p><b>Besonderheiten:</b> ${esc(p.besonderheiten)}</p></details>
    ${body}</section>`;
}

async function viewUnit(uid) {
  if (!(uid in META.regions) && !(uid in META.valleys)) return notFound();
  await loadMapDeps();
  const render = () => {
    const region = isRegion(uid);
    const sub = region
      ? `Region · ${META.regions[uid].valleys.length} Täler`
      : (() => { const v = META.valleys[uid]; return `Tal in <a href="#/r/${v.region}">${esc(unitName(v.region))}</a> · Talseite ${v.side === "nord" ? "Alpennordseite" : v.side === "sued" ? "Alpensüdseite" : "inneralpin"} · Pass ${esc(META.passes[v.pass].name)}${v.pass_valley ? " (Tal beginnt am Alpenhauptkamm)" : ""}`; })();
    const n = chainCount(uid, state.day, state.sec);
    app.innerHTML = `<div class="crumbs"><a href="#/">Übersicht</a></div><h1>${esc(unitName(uid))}</h1><p class="phmeta">${sub}</p>`;
    app.appendChild(controls(render));
    const top = document.createElement("div");
    top.className = "grid2";
    top.innerHTML = `<div class="card"><h2>Tage × Phänomene</h2>${matrixHtml(uid)}
      <p class="phmeta" style="margin-top:8px">${dayLabel(state.day)}, ${secLabel(state.sec)}: <b>${n} von 5 Phänomenen mit Alarmzeichen</b>.
      ${n >= 2 ? "Mehrere kritische Faktoren: eine gefährliche Verkettung wird wahrscheinlicher (SHV)." : ""}</p></div>
      <div class="mapwrap">${mapSvg({ onlyUnit: uid })}</div>`;
    app.appendChild(top);
    top.querySelectorAll(".matrix button").forEach((b) => b.addEventListener("click", () => { state.day = b.dataset.d; state.sec = b.dataset.s; render(); }));
    wireMap(top);
    const cards = document.createElement("div");
    cards.style.marginTop = "14px";
    cards.innerHTML = PH_ORDER.map((ph) => phenomenonCard(uid, ph)).join("");
    app.appendChild(cards);
  };
  render();
}

async function loadDetail(uid) {
  if (!detailCache.has(uid)) {
    detailCache.set(uid, fetch(`data/detail/${uid}.json?v=${encodeURIComponent(IDX.generated)}`).then((r) => r.ok ? r.json() : null));
  }
  return detailCache.get(uid);
}

async function viewCheck(uid, cid) {
  const c = META.catalog.checks[cid];
  if (!c || (!(uid in META.regions) && !(uid in META.valleys))) return notFound();
  await loadMapDeps();
  const det = c.data === "L" ? null : await loadDetail(uid);
  const d = det?.checks?.[cid];
  const render = () => {
    const [st, val, ens] = checkStatus(uid, state.day, state.sec, cid);
    const thr = Object.entries(c.thresholds || {}).map(([k, t]) => `<tr><td>${esc(k)}</td><td>${t.value}</td><td>${esc(t.source)}</td></tr>`).join("");
    const links = (c.links || []).map((l) => META.catalog.links[l]).filter(Boolean).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join("");
    app.innerHTML = `<div class="crumbs"><a href="#/">Übersicht</a> › <a href="#/${isRegion(uid) ? "r" : "v"}/${uid}">${esc(unitName(uid))}</a> › ${phName(c.phenomenon)}</div>
      <h1><span class="cid">${cid}</span> ${phName(c.phenomenon)}: ${esc(c.shv.split("→")[0].trim())}</h1>`;
    app.appendChild(controls(render));
    const strip = IDX.days.map((dd) => `<div><div class="d">${esc(dayLabel(dd.key).replace(/^(Heute|Morgen), .*/, "$1"))}</div><div class="cells">${SECS.map((s) => {
      const x = checkStatus(uid, dd.key, s, cid)[0];
      const lv = { guenstig: "ok", neutral: "keine_daten", trifft_zu: "achtung", trifft_nicht_zu: "keine_daten", selbst_pruefen: "keine_daten" }[x] || x;
      const sel = state.day === dd.key && (state.sec === s || state.sec === "tag") ? " sel" : "";
      return `<span class="cell-${lv}${sel}" title="${secLabel(s)}: ${STATUS[x]?.label ?? x}">${STATUS[x]?.sym ?? ""}</span>`;
    }).join("")}</div></div>`).join("");
    const box = document.createElement("div");
    box.className = "grid2";
    box.innerHTML = `<div>
      <div class="card"><div class="phhead"><h2>${dayLabel(state.day)}, ${secLabel(state.sec)}</h2><span class="st">${statusDot(st)}${STATUS[st]?.label ?? st}</span></div>
        <p style="margin:.3em 0 0">${esc(val) || '<span class="muted">kein Wert</span>'}${ens ? `<br><span class="phmeta">Ensemble (21 Members): ${Math.round(ens[0] * 100)} % mit Alarm, ${Math.round(ens[1] * 100)} % ohne</span>` : ""}</p>
        <div class="strip" aria-label="Status je Tag und Abschnitt">${strip}</div></div>
      <div class="card"><div class="shv"><div class="lab">SHV-Plakat, Planung · ${c.stage === "fortgeschritten" ? "Fortgeschritten" : "Basis"} · ${KIND[c.kind]}</div>${esc(c.shv)}</div>
        <div class="lab muted" style="font-size:.72rem;text-transform:uppercase;letter-spacing:.05em">So prüft wingbrief (${DATA[c.data]})</div>
        <p style="margin:.3em 0">${esc(c.rule)}</p>${d?.note ? `<p class="phmeta">${esc(d.note)}</p>` : ""}
        ${thr ? `<table class="thr"><tr><th>Schwelle</th><th>Wert</th><th>Quelle</th></tr>${thr}</table>` : ""}
        ${links ? `<p class="links">${links}</p>` : ""}
        ${c.kind === "faktor" ? `<p class="phmeta">Rahmenbedingung: verschärft die Lage, löst allein kein Alarmzeichen aus.</p>` : ""}
        ${c.data === "T" ? `<p class="phmeta">Näherung: hebt die Ampel höchstens auf «Achtung».</p>` : ""}
      </div></div>
      <div><div class="charts" id="charts"></div>
        ${d?.points?.length ? `<div class="card" style="margin-top:14px"><h3>Verwendete Punkte</h3><div class="minimap">${mapSvg({ points: d.points })}</div>
          <ol style="font-size:.85rem;padding-left:1.3em">${d.points.map((p) => `<li>${esc(p.name)} <span class="muted">(${p.lat.toFixed(2)}, ${p.lon.toFixed(2)})</span></li>`).join("")}</ol></div>` : ""}
        ${d?.entries?.length ? `<details class="card" style="margin-top:14px"><summary>Alle Werte als Tabelle (${d.entries.length})</summary><div class="tablewrap"><table class="raw">
          <tr><th>Zeit</th><th>Status</th><th>Wert</th></tr>${d.entries.map((e) => `<tr><td>${dtFmt.format(new Date(e[0]))}</td><td>${STATUS[e[1]]?.label ?? e[1]}${e[3] ? " (Ensemble)" : ""}</td><td>${esc(e[2])}</td></tr>`).join("")}</table></div></details>` : ""}
      </div>`;
    app.appendChild(box);
    const ch = box.querySelector("#charts");
    if (c.data === "L") {
      ch.innerHTML = `<div class="card"><p>Diese Quelle ist nicht als offene Daten verfügbar. Bitte selbst prüfen.</p>${val ? `<p>${esc(val)}: Das Modell zeigt Hinweise bei den genannten Checks.</p>` : ""}</div>`;
    } else if (d) {
      const run = new Date(IDX.model.run);
      const today0 = new Date(IDX.days[0].date + "T00:00:00");
      const x0 = new Date(Math.min(run.getTime(), today0.getTime()) - (cid === "R6" ? 86400000 : 0));
      const x1 = new Date(run.getTime() + 120 * 3600000);
      renderCharts(ch, d.series, { x0, x1, band: bandFor(state.day, state.sec) });
    } else {
      ch.innerHTML = '<p class="muted">Keine Detaildaten.</p>';
    }
  };
  render();
}

function bandFor(d, s) {
  const date = IDX.days[Number(d.slice(1))].date;
  const lo = s === "tag" ? 6 : IDX.sections.find((x) => x.key === s).from;
  const hi = s === "tag" ? 18 : IDX.sections.find((x) => x.key === s).to;
  return [zurichDate(date, lo), zurichDate(date, hi)];
}
function zurichDate(date, hour) {
  // Lokale Zeit Zürich -> Date (Offset per Intl bestimmen)
  const guess = new Date(`${date}T${String(hour).padStart(2, "0")}:00:00Z`);
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", hourCycle: "h23" }).format(guess);
  const off = Number(parts) - hour;
  return new Date(guess.getTime() - off * 3600000);
}

function viewPoster() {
  const P = META.poster;
  const sec = (title, rows) => `<div class="card poster"><h2>${title}</h2>${PH_ORDER.map((ph) => `<h3>${phName(ph)}</h3><ul>${(rows[ph] || []).map((r) =>
    r.guenstig ? `<li><b>Allgemein günstig:</b> ${esc(r.guenstig)}</li>` : `<li>${esc(r.check)} → <span class="al">Alarmzeichen: ${esc(r.alarm)}</span></li>`).join("")}</ul>`).join("")}</div>`;
  const gm = P.gelaende_mensch;
  app.innerHTML = `<h1>Anreise &amp; Vor Ort</h1>
    <p>wingbrief prüft nur die Planung mit Prognosedaten. Die folgenden Punkte aus dem SHV-Plakat prüfst du mit aktuellen Messungen und eigenen Beobachtungen.</p>
    <div class="grid2">${sec("► Anreise / Bergfahrt", P.anreise)}${sec("► Vor Ort / im Flug", P.vor_ort)}</div>
    <div class="card poster" style="margin-top:14px"><h2>Gelände und Mensch</h2>
      ${Object.entries({ planung: "Planung", anreise: "Anreise", vor_ort: "Vor Ort", reflexion: "Reflexion" }).map(([k, l]) => `<h3>${l}</h3><ul>${gm[k].map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`).join("")}
      <p><b>Verkettung:</b> ${esc(P.verkettung)}</p><p><b>Entscheid:</b> ${esc(P.entscheid)}</p></div>`;
}

function viewInfo() {
  const cat = META.catalog;
  const count = (d) => Object.values(cat.checks).filter((c) => c.data === d).length;
  app.innerHTML = `<h1>So funktioniert's</h1>
  <div class="grid2"><div>
    <div class="card"><h2>Grundlage</h2>
      <p>wingbrief setzt die Zeile <b>Planung</b> des SHV-Plakats <a href="${cat.sources.poster}" target="_blank" rel="noopener">«Meteo-Entscheidungsstrategie» V10</a> mit offenen Prognosedaten von MeteoSchweiz um, für heute und die nächsten 4 Tage, je Morgen, Mittag und Nachmittag.</p>
      <p>Jeder Eintrag des Plakats ist ein Check: ${count("A")} automatisch, ${count("T")} als Näherung, ${count("L")} zum selbst Prüfen (Textprognose, Prévitemps, Bodenwetterkarte, Segelflugprognose sind nicht als offene Daten verfügbar). Ein Klick auf einen Check zeigt die SHV-Anforderung, die Regel, die Schwellen mit Quelle und die verglichenen Daten.</p></div>
    <div class="card"><h2>Ampel</h2><div class="levels-legend">
      <div>${levelBadge("alarm")}: mindestens ein automatisch geprüftes SHV-Alarmzeichen trifft zu.</div>
      <div>${levelBadge("achtung")}: kein Alarmzeichen, aber nicht alle «allgemein günstigen Zeichen» erfüllt, oder eine Näherung zeigt etwas.</div>
      <div>${levelBadge("unsicher")}: Tag 3–5, die Ensemble-Members sind sich nicht einig (Alarm ab 30 %, ok erst ab 80 %).</div>
      <div>${levelBadge("ok")}: alle günstigen Zeichen erfüllt, keine Alarmzeichen. Keine Freigabe: Anreise und Vor Ort bleiben nötig.</div>
      </div><p><b>Verkettung:</b> Zahl der Phänomene mit Alarmzeichen. SHV: «Wenn mehrere Faktoren kritisch sind, wird eine gefährliche Verkettung wahrscheinlicher.»</p>
      <p><b>Rahmenbedingungen</b> (Jahreszeit, Gelände, Tal am Pass) verschärfen, lösen aber allein keinen Alarm aus.</p></div>
    <div class="card"><h2>Regionen und Täler</h2>
      <p>SHV definiert keine Regionen. Fronten, Wärmegewitter und überregionaler Wind werden pro Region geprüft, Regiowind und Föhn pro Tal, wie auf dem Plakat («Tal beginnt an einem Pass am Alpenhauptkamm») und der SHV-Karte <a href="${cat.sources.pumping_map}" target="_blank" rel="noopener">«Alpines Pumpen»</a>.</p></div>
  </div><div>
    <div class="card"><h2>Daten</h2><ul>
      <li><b>ICON-CH2-EPS</b> (2.1 km, 120 h, 21 Members): Höhenwind und -temperatur aus dem Kontrolllauf; Druck und Niederschlag zusätzlich als Ensemble für Tag 3–5.</li>
      <li><b>Lokalprognose MeteoSchweiz</b> (statistisch verbessert) an SwissMetNet-Stationen: bodennaher Wind und Temperatur.</li>
      <li><b>SwissMetNet-Klimatologie</b> ab 2010: was an einer Station «gewohnt» ist (Perzentile pro Monat und Stunde).</li>
      <li>Aktualisierung stündlich geprüft, neuer Lauf alle 6 h. Quelle: MeteoSchweiz.</li></ul></div>
    <div class="card"><h2>Grenzen</h2><ul>
      <li>Schwellen ohne SHV-Zahl sind eigene Vorschläge oder vom DHV und werden mit dem Archiv kalibriert.</li>
      <li>Ein Gitterpunkt von 2.1 km bildet enge Täler nur grob ab.</li>
      <li>Startplatz, Landeplatz, Gelände und Mensch sind nicht Teil der Bewertung.</li>
      <li>Phasen Anreise und Vor Ort: siehe <a href="#/vor-ort">Checkliste</a>.</li></ul></div>
  </div></div>`;
}

function notFound() { app.innerHTML = `<p>Seite nicht gefunden. <a href="#/">Zur Übersicht</a></p>`; }

// --------------------------------------------------------------- Router
async function route() {
  document.getElementById("tip").hidden = true;
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const nav = parts[0] === "vor-ort" ? "vor-ort" : parts[0] === "info" ? "info" : "home";
  document.querySelectorAll("[data-nav]").forEach((a) => { if (a.dataset.nav === nav) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  if (!parts.length) await viewHome();
  else if (parts[0] === "vor-ort") viewPoster();
  else if (parts[0] === "info") viewInfo();
  else if ((parts[0] === "r" || parts[0] === "v") && parts.length === 2) await viewUnit(parts[1]);
  else if ((parts[0] === "r" || parts[0] === "v") && parts.length === 3) await viewCheck(parts[1], parts[2]);
  else notFound();
  window.scrollTo(0, 0);
}

async function init() {
  try {
    const bust = `?t=${Math.floor(Date.now() / 600000)}`;
    [IDX, META] = await Promise.all([
      fetch(`data/index.json${bust}`).then((r) => r.json()),
      fetch(`data/meta.json${bust}`).then((r) => r.json()),
    ]);
  } catch (e) {
    app.innerHTML = `<p>Die Prognosedaten konnten nicht geladen werden.</p>`;
    return;
  }
  [state.day, state.sec] = defaultSelection();
  document.getElementById("run").textContent = dtFmt.format(new Date(IDX.model.run)) + " (ICON-CH2-EPS)";
  document.getElementById("generated").textContent = dtFmt.format(new Date(IDX.generated));
  document.getElementById("entscheid").textContent = "«" + META.poster.entscheid + "» (SHV)";
  const age = (Date.now() - Date.parse(IDX.generated)) / 3600000;
  const runAge = (Date.now() - Date.parse(IDX.model.run)) / 3600000;
  if (age > 6 || runAge > 14) {
    const s = document.getElementById("stale");
    s.hidden = false;
    s.textContent = `Achtung: Die Daten sind veraltet (berechnet vor ${Math.round(age)} h, Modelllauf vor ${Math.round(runAge)} h).`;
  }
  window.addEventListener("hashchange", route);
  route();
}

init();
