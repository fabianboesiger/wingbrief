// wingbrief – Startseite: Tages-Tabs, Ampelkarte, Details auf Abruf im Panel.
import * as W from "./shared.js";

const POSTER = "https://www.shv-fsvl.ch/fileadmin/files/redakteure/Allgemein/Sicherheit/Sicherheit/Entscheidungsstrategie_Meteo_V10.pdf";
let day;

function renderTabs() {
  document.getElementById("tabs").innerHTML = W.dayKeys().map((d) =>
    `<button role="tab" aria-selected="${d === day}" data-d="${d}">${W.dayParts(d).rel}</button>`).join("");
  document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => { day = b.dataset.d; render(); });
}

function render() {
  renderTabs();
  W.drawMap(document.getElementById("map"), {
    lv: (u) => W.dayLevel(u, day),
    onPick: (u) => W.openSheet(W.unitBriefView(u, day), { replace: true }),
  });
}

function infoView() {
  const cat = W.META.catalog;
  const n = (d) => Object.values(cat.checks).filter((c) => c.data === d).length;
  return {
    title: "Über wingbrief",
    render(el) {
      el.innerHTML = `<div class="cd">
        <p>wingbrief prüft die Zeile <b>Planung</b> der <a href="${POSTER}" target="_blank" rel="noopener">SHV-Meteo-Entscheidungsstrategie</a>
          mit Prognosedaten von MeteoSchweiz, für heute und die nächsten 4 Tage.</p>
        <p>Farbe auf der Karte = schlechtestes der fünf Phänomene am gewählten Tag (noch kommende Abschnitte).
          Flächen sind Regionen, Linien Täler. Gebiet antippen für Abschnitte, Phänomene und Checks.</p>
        <div class="levels">
          <div><i class="lv alarm">!</i><span><b>Alarmzeichen</b>: mindestens ein automatisch geprüftes SHV-Alarmzeichen trifft zu.</span></div>
          <div><i class="lv achtung">!</i><span><b>Achtung</b>: kein Alarmzeichen, aber nicht alle «allgemein günstigen Zeichen» erfüllt.</span></div>
          <div><i class="lv unsicher">?</i><span><b>unsicher</b>: Tag 3–5, die Ensemble-Members sind sich nicht einig.</span></div>
          <div><i class="lv ok">✓</i><span><b>keine Alarmzeichen</b>: alle günstigen Zeichen erfüllt. Keine Freigabe.</span></div>
        </div>
        <p>${n("A")} Checks automatisch, ${n("T")} als Näherung, ${n("L")} zum selbst Prüfen. Schwellen ohne SHV-Zahl sind als «DHV» oder «eigener Vorschlag» gekennzeichnet.</p>
        <div class="info-links"><button class="linkbtn" id="vorort">Checkliste Anreise &amp; Vor Ort ›</button>
          <a href="https://github.com/fabianboesiger/wingbrief" target="_blank" rel="noopener">Quellcode und Methode ↗</a></div>
        <p class="cd-note">Quelle: MeteoSchweiz (ICON-CH2-EPS, Lokalprognose, SwissMetNet-Klimatologie).
          Modelllauf ${W.fmtDateTime(W.IDX.model.run)}, berechnet ${W.fmtDateTime(W.IDX.generated)}.</p>
        <p class="cd-note">«${W.esc(W.META.poster.entscheid)}» (SHV)</p></div>`;
      el.querySelector("#vorort").onclick = () => W.openSheet(posterView());
    },
  };
}

function posterView() {
  const P = W.META.poster;
  const block = (title, rows) => `<h3 style="margin:14px 0 0;font-size:15px">${title}</h3>` + W.PH.map((ph) =>
    `<h4>${W.icon(ph, "ic ic-inline")} ${W.esc(W.phName(ph))}</h4><ul>${(rows[ph] || []).map((r) => r.guenstig
      ? `<li><b>Günstig:</b> ${W.esc(r.guenstig)}</li>`
      : `<li>${W.esc(r.check)} → <span class="al">${W.esc(r.alarm)}</span></li>`).join("")}</ul>`).join("");
  return {
    title: "Anreise &amp; Vor Ort",
    render(el) {
      el.innerHTML = `<div class="poster"><p class="cd-note">Diese Punkte des SHV-Plakats prüfst du mit aktuellen Messungen und eigenen Beobachtungen.</p>
        ${block("Anreise / Bergfahrt", P.anreise)}${block("Vor Ort / im Flug", P.vor_ort)}
        <h3 style="margin:14px 0 0;font-size:15px">Gelände und Mensch</h3>
        <ul style="margin-top:6px">${[...P.gelaende_mensch.planung, ...P.gelaende_mensch.vor_ort].map((x) => `<li>${W.esc(x)}</li>`).join("")}</ul></div>`;
    },
  };
}

async function init() {
  try {
    await W.load(`data/`);
  } catch {
    document.getElementById("map").innerHTML = "<p>Die Prognosedaten konnten nicht geladen werden.</p>";
    return;
  }
  day = W.defaultSelection()[0];
  document.getElementById("legend").innerHTML = W.legendHtml();
  document.getElementById("info").onclick = () => W.openSheet(infoView(), { replace: true });
  const age = (Date.now() - Date.parse(W.IDX.generated)) / 3600000;
  if (age > 6) {
    const s = document.getElementById("stale");
    s.hidden = false;
    s.textContent = `Achtung: Daten sind ${Math.round(age)} h alt.`;
  }
  render();
}
init();
