"""Checks ausführen, nach Tag × Tagesabschnitt zusammenfassen, Ampeln und Verkettung bilden.

Ampel je Phänomen (SHV-Logik):
  alarm        mindestens ein automatischer (A) Alarm-Check trifft zu
  unsicher     Ensemble uneinig (Tag 3–5) und kein Alarm
  achtung      sonst, wenn nicht alle günstigen Zeichen erfüllt sind
  ok           alle automatischen günstigen Zeichen erfüllt («keine Alarmzeichen»)
Näherungen (T) heben höchstens auf «achtung». Faktoren lösen allein nichts aus.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import yaml

from . import CONFIG, climatology
from .checks import base, fronten, gewitter, regiowind, wind, foehn
from .checks.base import (ACHTUNG, ALARM, GUENSTIG, JA, KEINE, NEIN, NEUTRAL, RANK, UNSICHER, Ctx, Result)
from .extract import N_DAYS, SECTIONS, TZ, Bundle, day_index, load_units, section_of

log = logging.getLogger(__name__)

PHENOMENA = ["fronten", "gewitter", "regiowind", "wind", "foehn"]
MODULES = {"fronten": fronten, "gewitter": gewitter, "regiowind": regiowind, "wind": wind, "foehn": foehn}
SELF_CHECK = "selbst_pruefen"
PROXY = {"F1": ["F2", "F6"], "W1": ["F5", "W3"], "R1": ["R9"], "U1": ["U2"], "O1": ["O4"]}
ENS_FROM_DAY = 2   # Tag 3–5 (Index 2–4)


def load_catalog() -> dict:
    return yaml.safe_load((CONFIG / "checks.yaml").read_text())


def aggregate(entries: list[base.Entry], kind: str, use_ens: bool) -> tuple[str, str, list | None]:
    """Status eines Checks in einem Tagesabschnitt."""
    if kind == "faktor":
        known = [e for e in entries if e.status in (JA, NEIN)]
        if not known:
            return KEINE, "", None
        hit = next((e for e in known if e.status == JA), None)
        return (JA, hit.value, None) if hit else (NEIN, known[0].value, None)
    ens = [e for e in entries if e.ens is not None]
    ctrl = [e for e in entries if e.ens is None and e.status != KEINE]
    if use_ens and ens:
        fa = max(e.ens[0] for e in ens)
        fo = min(e.ens[1] for e in ens)
        worst = max(ens, key=lambda e: e.ens[0])
        if kind == "guenstig":
            st = GUENSTIG if fo >= 0.8 else (NEUTRAL if fo <= 0.2 else UNSICHER)
            return st, min(ens, key=lambda e: e.ens[1]).value, [round(fa, 2), round(fo, 2)]
        if fa >= 0.3:
            return ALARM, worst.value, [round(fa, 2), round(fo, 2)]
        if fo >= 0.8:
            return NEUTRAL, worst.value, [round(fa, 2), round(fo, 2)]
        return UNSICHER, worst.value, [round(fa, 2), round(fo, 2)]
    if not ctrl:
        return KEINE, "", None
    if kind == "guenstig":
        if all(e.status == GUENSTIG for e in ctrl):
            return GUENSTIG, ctrl[len(ctrl) // 2].value, None
        bad = next(e for e in ctrl if e.status != GUENSTIG)
        return NEUTRAL, bad.value, None
    worst = max(ctrl, key=lambda e: RANK[e.status])
    return worst.status, worst.value, None


def phenomenon_level(statuses: dict[str, str], catalog: dict, phenomenon: str) -> str:
    checks = {cid: c for cid, c in catalog["checks"].items() if c["phenomenon"] == phenomenon}
    auto_alarm = [cid for cid, c in checks.items() if c["kind"] == "alarm" and c["data"] == "A"]
    proxy = [cid for cid, c in checks.items() if c["kind"] == "alarm" and c["data"] == "T"]
    good = [cid for cid, c in checks.items() if c["kind"] == "guenstig" and c["data"] == "A"]
    known = [statuses.get(c) for c in auto_alarm + good if statuses.get(c) not in (None, KEINE)]
    if not known:
        return KEINE
    if any(statuses.get(c) == ALARM for c in auto_alarm):
        return ALARM
    if any(statuses.get(c) == UNSICHER for c in auto_alarm + good):
        return UNSICHER
    if any(statuses.get(c) in (ACHTUNG, ALARM) for c in auto_alarm + proxy):
        return ACHTUNG
    if good and all(statuses.get(c) == GUENSTIG for c in good):
        return "ok"
    return ACHTUNG


LEVEL_RANK = {ALARM: 5, ACHTUNG: 4, UNSICHER: 3, "ok": 1, KEINE: 0}


def worst_level(levels: list[str]) -> str:
    return max(levels, key=lambda x: LEVEL_RANK[x]) if levels else KEINE


def run_unit(b: Bundle, units: dict, catalog: dict, clim: dict, unit_id: str, kind: str) -> dict[str, Result]:
    ctx = Ctx(b, units, catalog, clim, unit_id, kind)
    out = {}
    for ph in PHENOMENA:
        if catalog["phenomena"][ph]["unit"] != kind:
            continue
        for cid, fn in MODULES[ph].CHECKS.items():
            try:
                out[cid] = fn(ctx)
            except Exception as e:  # noqa: BLE001 - ein Check darf den Lauf nicht abbrechen
                log.exception("Check %s für %s fehlgeschlagen", cid, unit_id)
                res = Result(cid)
                res.note = f"Fehler bei der Berechnung: {e}"
                out[cid] = res
    return out


def summarize(b: Bundle, units: dict, catalog: dict, results: dict[str, dict[str, Result]]) -> dict:
    """status[unit][day][section] = {checks: {cid: [status, value, ens]}, level: {ph: level}}."""
    now = datetime.now(timezone.utc)
    status: dict = {}
    for uid, res in results.items():
        u = {}
        for d in range(N_DAYS):
            day = {}
            for skey, _, _, _ in SECTIONS:
                checks = {}
                for cid, r in res.items():
                    c = catalog["checks"][cid]
                    entries = [e for e in r.entries
                               if day_index(e.t, b.today) == d and section_of(e.t) == skey]
                    use_ens = d >= ENS_FROM_DAY and c.get("ensemble", False)
                    st, val, ens = aggregate(entries, c["kind"], use_ens)
                    checks[cid] = [st, val] + ([ens] if ens else [])
                day[skey] = {"checks": checks}
            u[f"d{d}"] = day
        status[uid] = u
    # L-Checks (selbst prüfen) mit Modell-Hinweis ergänzen
    for uid, u in status.items():
        for day in u.values():
            for sec in day.values():
                for cid, c in catalog["checks"].items():
                    if c["data"] != "L":
                        continue
                    ph_unit = catalog["phenomena"][c["phenomenon"]]["unit"]
                    if (ph_unit == "region") != (uid in units["regions"]):
                        continue
                    hints = [p for p in PROXY.get(cid, []) if sec["checks"].get(p, [None])[0] in (ALARM, ACHTUNG)]
                    sec["checks"][cid] = [SELF_CHECK, ("Modell-Hinweis: " + ", ".join(hints)) if hints else ""]
    # Ampeln je Einheit
    for uid, u in status.items():
        for day in u.values():
            for sec in day.values():
                sts = {cid: v[0] for cid, v in sec["checks"].items()}
                sec["level"] = {ph: phenomenon_level(sts, catalog, ph) for ph in PHENOMENA
                                if (catalog["phenomena"][ph]["unit"] == "region") == (uid in units["regions"])}
    # Zusammensetzen: Regionen erhalten Regiowind/Föhn als schlechtestes Tal,
    # Täler erhalten Fronten/Gewitter/Wind von ihrer Region.
    for uid, u in status.items():
        is_region = uid in units["regions"]
        for dkey, day in u.items():
            for skey, sec in day.items():
                full = dict(sec["level"])
                if is_region:
                    vids = [v for v, vv in units["valleys"].items() if vv["region"] == uid]
                    for ph in ("regiowind", "foehn"):
                        full[ph] = worst_level([status[v][dkey][skey]["level"][ph] for v in vids]) if vids else KEINE
                else:
                    rid = units["valleys"][uid]["region"]
                    for ph in ("fronten", "gewitter", "wind"):
                        full[ph] = status[rid][dkey][skey]["level"][ph]
                sec["full"] = {ph: full[ph] for ph in PHENOMENA}
                sec["chain"] = sum(1 for ph in PHENOMENA if full[ph] == ALARM)
                sec["past"] = _section_end(b, int(dkey[1:]), skey) < now
    return status


def _section_end(b: Bundle, d: int, skey: str) -> datetime:
    day = b.today + timedelta(days=d)
    hi = next(h for k, _, _, h in SECTIONS if k == skey)
    return datetime(day.year, day.month, day.day, min(hi, 23), tzinfo=TZ)


def run_all(b: Bundle) -> tuple[dict, dict, dict]:
    units = load_units()
    catalog = load_catalog()
    clim = climatology.load()
    results: dict[str, dict[str, Result]] = {}
    for rid in units["regions"]:
        results[rid] = run_unit(b, units, catalog, clim, rid, "region")
    for vid in units["valleys"]:
        results[vid] = run_unit(b, units, catalog, clim, vid, "valley")
    status = summarize(b, units, catalog, results)
    return status, results, catalog
