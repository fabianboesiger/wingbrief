// wingbrief – eigene Seiten: Start (Karte) → Gebiet → Phänomen → Check, dazu Info und Anreise & Vor Ort.
// Routen bestehen nur aus Buchstaben, Ziffern und Bindestrichen: #tessin, #tessin-foehn, #tessin-O4, #info, #vor-ort.
import * as W from "./shared.js";

const POSTER = "https://www.shv-fsvl.ch/fileadmin/files/redakteure/Allgemein/Sicherheit/Sicherheit/Entscheidungsstrategie_Meteo_V10.pdf";
const LOGO = `<svg aria-hidden="true" viewBox="0 0 32 32"><defs><linearGradient id="LG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a2f8f"/><stop offset=".55" stop-color="#a5479f"/><stop offset="1" stop-color="#f48a6c"/></linearGradient></defs><rect width="32" height="32" rx="8" fill="url(#LG)"/><path d="M0 28L9 20L13 23.5L20.5 16.5L32 26V32H0Z" fill="#2a1f5c"/><g transform="translate(15.8 12.4) rotate(-14) scale(1.2)"><path d="M-10 1.4Q0 -10 10 1.4Q0 -2.2 -10 1.4Z" fill="#fff"/><circle cx="0" cy="6.3" r="1.7" fill="#fff"/></g></svg>`;
const app = document.getElementById("app");
let day, sec = "tag";
const slug = (id) => id.replace(/_/g, "");
let BYSLUG = {};
const go = (h) => { location.hash = h; };
const esc = W.esc;

// ------------------------------------------------------------- Bausteine
function tabsHtml() {
  return `<div class="tabs" role="tablist">${W.dayKeys().map((d) =>
    `<button role="tab" aria-selected="${d === day}" data-d="${d}">${W.dayParts(d).rel}</button>`).join("")}</div>`;
}
function wireTabs(root, rerender) {
  root.querySelectorAll(".tabs [data-d]").forEach((b) => b.onclick = () => {
    day = b.dataset.d; W.store.set("day", day);
    if (sec !== "tag" && W.isPast(day, sec)) sec = "tag";
    rerender();
  });
}
function header(active = "") {
  return `<header class="site-head"><a class="brand" href="#" aria-label="wingbrief, zur Karte">${LOGO}<span class="wm">wing<b>brief</b></span></a>
    <a class="iconbtn${active === "info" ? " on" : ""}" href="#info" aria-label="Über wingbrief">i</a></header>`;
}
function topbar(backHref, backLabel, active = "") {
  return `${header(active)}<a class="back" href="${backHref}"><span>‹</span>${esc(backLabel)}</a>`;
}
function setPage(title, html) {
  document.title = title ? `${title} – wingbrief` : "wingbrief";
  app.innerHTML = html;
  window.scrollTo(0, 0);
  app.querySelector(".page-title")?.focus({ preventScroll: true });
}
const lvOf = (u, ph = null) => (sec === "tag" ? W.dayLevel(u, day, ph) : (ph ? W.fullLevel(u, day, sec, ph) : W.unitLevel(u, day, sec)));
const statusBig = (lv) => `<div class="status-big"><span class="lv ${lv}">${W.LEVEL[lv].sym}</span>${W.LEVEL[lv].label}</div>`;
const whenText = () => { const p = W.dayParts(day); return `${p.rel}${p.i > 1 ? ` ${p.date}` : ""} · ${W.secLabel(sec)}`; };
function row(href, lv, title, sub, st = null) {
  const mark = st ? `<span class="lv st-${st}">${W.STATUS[st]?.sym ?? ""}</span>` : `<span class="lv ${lv}">${W.LEVEL[lv].sym}</span>`;
  return `<li><button data-go="${href}">${mark}<span><b>${title}</b><small>${esc(sub)}</small></span><span class="chev">›</span></button></li>`;
}
function wireRows(root) {
  root.querySelectorAll("[data-go]").forEach((b) => b.onclick = () => go(b.dataset.go));
}

// ------------------------------------------------------------- Seiten
function pageHome() {
  setPage("", `${header()}
    ${tabsHtml()}<p class="stale" id="stale" hidden></p>
    <div class="map" id="map"></div><div class="legend1">${W.legendHtml()}</div>
    <p class="foot">Planung, keine Freigabe · Quelle: MeteoSchweiz</p>`);
  wireTabs(app, pageHome);
  const age = (Date.now() - Date.parse(W.IDX.generated)) / 3600000;
  if (age > 6) { const s = app.querySelector("#stale"); s.hidden = false; s.textContent = `Achtung: Daten sind ${Math.round(age)} h alt.`; }
  W.drawMap(app.querySelector("#map"), { lv: (u) => W.dayLevel(u, day), onPick: (u) => go(slug(u)) });
}

function pageUnit(uid) {
  const region = W.isRegion(uid);
  const v = region ? null : W.META.valleys[uid];
  const sub = region ? `Region · ${W.META.regions[uid].valleys.length} Täler`
    : `Tal in <a href="#${slug(v.region)}">${esc(W.unitName(v.region))}</a> · Pass ${esc(W.META.passes[v.pass].name)}`;
  const noValleys = region && !W.META.regions[uid].valleys.length;
  const phs = W.PH.filter((ph) => !(noValleys && W.META.catalog.phenomena[ph].unit === "valley"));
  const secBtn = (x) => {
    const l = x === "tag" ? W.dayLevel(uid, day) : W.unitLevel(uid, day, x);
    return `<button class="ub-sec${x === sec ? " on" : ""}${x !== "tag" && W.isPast(day, x) ? " past" : ""}" data-s="${x}" aria-pressed="${x === sec}">
      <i class="st-${l}">${W.LEVEL[l].sym}</i><span>${x === "tag" ? "Ganzer Tag" : W.secLabel(x)}</span><small>${W.secRange(x)}</small></button>`;
  };
  setPage(W.unitName(uid), `${topbar("#", "Karte")}
    <div class="hero"><div><h1 class="page-title" tabindex="-1">${esc(W.unitName(uid))}</h1><p class="page-sub">${sub}</p></div><div class="loc" id="loc"></div></div>
    ${tabsHtml()}
    <section class="card"><h2>${whenText()}</h2>${statusBig(lvOf(uid))}
      <div class="ub-secs" style="margin-top:10px">${[...W.SECS, "tag"].map(secBtn).join("")}</div></section>
    <section class="card"><h2>Phänomene</h2><ul class="sv-list">${phs.map((ph) => {
      const l = lvOf(uid, ph);
      return row(`${slug(uid)}-${ph}`, l, `${W.icon(ph, "ic ic-inline")} ${esc(W.phName(ph))}`, W.LEVEL[l].label);
    }).join("")}</ul>${noValleys ? '<p class="sv-note">Regiowind und Föhn werden pro Tal geprüft; für diese Region sind keine Täler hinterlegt.</p>' : ""}</section>
    ${region && !noValleys ? `<section class="card"><h2>Täler</h2><ul class="sv-list">${W.META.regions[uid].valleys.map((t) =>
      row(slug(t), lvOf(t), esc(W.unitName(t)), W.LEVEL[lvOf(t)].label)).join("")}</ul></section>` : ""}`);
  wireTabs(app, () => pageUnit(uid));
  app.querySelectorAll(".ub-sec").forEach((b) => b.onclick = () => { sec = b.dataset.s; pageUnit(uid); });
  wireRows(app);
  const related = new Set([uid, ...(region ? W.META.regions[uid].valleys : [])]);
  W.drawMap(app.querySelector("#loc"), { lv: (u) => (related.has(u) ? lvOf(u) : "keine_daten"), onPick: (u) => go(slug(u)) });
}

function pagePhenomenon(uid, ph) {
  const p = W.META.catalog.phenomena[ph];
  const r = W.reason(uid, day, sec, ph);
  let body = "";
  if (p.unit === "valley" && W.isRegion(uid)) {
    body = `<section class="card"><h2>Pro Tal geprüft</h2><ul class="sv-list">${W.META.regions[uid].valleys.map((t) => {
      const l = lvOf(t, ph);
      return row(`${slug(t)}-${ph}`, l, esc(W.unitName(t)), W.reason(t, day, sec, ph).text || W.LEVEL[l].label);
    }).join("")}</ul></section>`;
  } else {
    const owner = W.ownerOf(uid, ph);
    const groups = { alarm: "Alarmzeichen", guenstig: "Allgemein günstige Zeichen", faktor: "Rahmenbedingungen" };
    body = (owner !== uid ? `<p class="sv-note">Gilt für die ganze Region <a href="#${slug(owner)}">${esc(W.unitName(owner))}</a>.</p>` : "") +
      Object.entries(groups).map(([kind, title]) => {
        const ids = W.checksOf(ph).filter((c) => W.META.catalog.checks[c].kind === kind);
        if (!ids.length) return "";
        return `<section class="card"><h2>${title}</h2><ul class="sv-list">${ids.map((cid) => {
          const c = W.META.catalog.checks[cid];
          const [st, val] = W.checkStatus(owner, day, sec, cid);
          return row(`${slug(uid)}-${cid}`, null, esc(c.shv.split("→")[0].trim()), val || W.STATUS[st]?.label, st);
        }).join("")}</ul></section>`;
      }).join("");
  }
  setPage(`${W.phName(ph)} · ${W.unitName(uid)}`, `${topbar(`#${slug(uid)}`, W.unitName(uid))}
    <div><h1 class="page-title" tabindex="-1">${W.icon(ph, "ic")} ${esc(W.phName(ph))}</h1><p class="page-sub">${esc(W.unitName(uid))} · ${whenText()}</p></div>
    ${tabsHtml()}
    <section class="card">${statusBig(r.lv)}<p class="reason">${esc(r.text)}</p>
      <details class="sv-about" style="margin-top:10px"><summary>Worum es geht (SHV)</summary><p>${esc(p.inhalt)} <b>Hauptgefahr:</b> ${esc(p.gefahr)}</p></details></section>
    ${body}`);
  wireTabs(app, () => pagePhenomenon(uid, ph));
  wireRows(app);
}

function pageCheck(uid, cid) {
  const c = W.META.catalog.checks[cid];
  setPage(c.shv.split("→")[0].trim(), `${topbar(`#${slug(uid)}-${c.phenomenon}`, W.phName(c.phenomenon))}
    <div><h1 class="page-title" tabindex="-1">${esc(c.shv.split("→")[0].trim())}</h1><p class="page-sub">${esc(W.unitName(uid))} · ${whenText()}</p></div>
    ${tabsHtml()}
    <section class="card" id="cd">${W.checkDetailHtml(uid, cid, day, sec)}</section>`);
  wireTabs(app, () => pageCheck(uid, cid));
  W.fillCheckDetail(app.querySelector("#cd"), uid, cid, day, sec);
}

function pageInfo() {
  const cat = W.META.catalog;
  const n = (d) => Object.values(cat.checks).filter((c) => c.data === d).length;
  setPage("Über wingbrief", `${topbar("#", "Karte", "info")}<h1 class="page-title" tabindex="-1">Über wingbrief</h1>
    <section class="card prose"><p>wingbrief prüft die Zeile <b>Planung</b> der <a href="${POSTER}" target="_blank" rel="noopener">SHV-Meteo-Entscheidungsstrategie</a>
      mit Prognosedaten von MeteoSchweiz, für heute und die nächsten 4 Tage.</p>
      <p>Farbe auf der Karte = schlechtestes der fünf Phänomene am gewählten Tag. Flächen sind Regionen, Linien Täler.</p></section>
    <section class="card"><h2>Ampel</h2><div class="levels">
      <div><i class="lv alarm">!</i><span><b>Alarmzeichen</b>: mindestens ein automatisch geprüftes SHV-Alarmzeichen trifft zu.</span></div>
      <div><i class="lv achtung">!</i><span><b>Achtung</b>: kein Alarmzeichen, aber nicht alle «allgemein günstigen Zeichen» erfüllt.</span></div>
      <div><i class="lv unsicher">?</i><span><b>unsicher</b>: Tag 3–5, die Ensemble-Members sind sich nicht einig.</span></div>
      <div><i class="lv ok">✓</i><span><b>keine Alarmzeichen</b>: alle günstigen Zeichen erfüllt. Keine Freigabe.</span></div></div></section>
    <section class="card prose"><p>${n("A")} Checks automatisch, ${n("T")} als Näherung, ${n("L")} zum selbst Prüfen.</p>
      <p><a href="#vor-ort">Checkliste Anreise &amp; Vor Ort ›</a></p>
      <p class="cd-note">Quelle: MeteoSchweiz. Modelllauf ${W.fmtDateTime(W.IDX.model.run)}, berechnet ${W.fmtDateTime(W.IDX.generated)}.</p>
      <p class="cd-note">«${esc(W.META.poster.entscheid)}» (SHV)</p></section>`);
}

function pageVorOrt() {
  const P = W.META.poster;
  const block = (title, rows) => `<section class="card poster"><h2>${title}</h2>${W.PH.map((ph) =>
    `<h4>${W.icon(ph, "ic ic-inline")} ${esc(W.phName(ph))}</h4><ul>${(rows[ph] || []).map((r) => r.guenstig
      ? `<li><b>Günstig:</b> ${esc(r.guenstig)}</li>` : `<li>${esc(r.check)} → <span class="al">${esc(r.alarm)}</span></li>`).join("")}</ul>`).join("")}</section>`;
  setPage("Anreise & Vor Ort", `${topbar("#info", "Über wingbrief", "info")}<h1 class="page-title" tabindex="-1">Anreise &amp; Vor Ort</h1>
    <p class="page-sub">Diese Punkte des SHV-Plakats prüfst du mit aktuellen Messungen und eigenen Beobachtungen.</p>
    ${block("Anreise / Bergfahrt", P.anreise)}${block("Vor Ort / im Flug", P.vor_ort)}
    <section class="card poster"><h2>Gelände und Mensch</h2><ul>${[...P.gelaende_mensch.planung, ...P.gelaende_mensch.vor_ort].map((x) => `<li>${esc(x)}</li>`).join("")}</ul></section>`);
}

// ------------------------------------------------------------- Router
function route() {
  document.getElementById("tip").hidden = true;
  const h = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (!h) return pageHome();
  if (h === "info") return pageInfo();
  if (h === "vor-ort") return pageVorOrt();
  const [s, x] = h.split("-");
  const uid = BYSLUG[s];
  if (!uid) return pageHome();
  if (!x) return pageUnit(uid);
  if (W.PH.includes(x)) return pagePhenomenon(uid, x);
  if (W.META.catalog.checks[x]) return pageCheck(uid, x);
  return pageUnit(uid);
}

async function init() {
  try { await W.load("data/"); } catch { app.innerHTML = "<p>Die Prognosedaten konnten nicht geladen werden.</p>"; return; }
  BYSLUG = Object.fromEntries([...Object.keys(W.META.regions), ...Object.keys(W.META.valleys)].map((id) => [slug(id), id]));
  const saved = W.store.get("day", null);
  day = W.dayKeys().includes(saved) ? saved : W.defaultSelection()[0];
  window.addEventListener("hashchange", route);
  route();
}
init();
