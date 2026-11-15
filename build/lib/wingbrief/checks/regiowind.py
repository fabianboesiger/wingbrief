"""Regiowind (Einheit: Tal). SHV-Plakat, Zeile Planung."""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np

from .. import vertical
from ..extract import TZ, section_of
from .base import ALARM, GUENSTIG, JA, KEINE, NEIN, NEUTRAL, Ctx, Result, bearing, fmt, in_dir

SUMMER = range(4, 11)


def _precip_48h(ctx: Ctx, i: int) -> tuple[float, float]:
    """Niederschlag der letzten (bis zu) 48 h an den Talpunkten, Mittel in mm; zweiter Wert: Stunden."""
    t = ctx.t_sfc[i]
    j = ctx.sfc_back(t, 48)
    hours = 48.0
    if j is None:
        j, hours = 0, (t - ctx.t_sfc[0]).total_seconds() / 3600
    pts = ctx.valley_points()
    vals = [ctx.sfc("TOT_PREC", p)[i] - ctx.sfc("TOT_PREC", p)[j] for p in pts]
    return float(np.nanmean(vals)), hours


def _snow(ctx: Ctx, i: int) -> float:
    return float(np.nanmean([ctx.sfc("SNOWC", p)[i] for p in ctx.valley_points()]))


def R2(ctx: Ctx) -> Result:
    r = Result("R2")
    for t in ctx.rep_times():
        lt = t.astimezone(TZ)
        yes = lt.month in SUMMER and section_of(t) == "nachmittag"
        r.add(t, JA if yes else NEIN, f"{lt:%B}, {'Nachmittag' if section_of(t) == 'nachmittag' else 'nicht Nachmittag'}")
    return r


def R3(ctx: Ctx) -> Result:
    r = Result("R3")
    v = ctx.unit
    feats = [x for x, on in (("langes, grosses Tal", v.get("long_valley")), ("Talverengung", v.get("narrows"))) if on]
    for t in ctx.rep_times():
        r.add(t, JA if feats else NEIN, ", ".join(feats) or "kein langes Tal, keine Talverengung")
    r.points.extend(ctx.point_info(p) for p in ctx.valley_points())
    return r


def R4(ctx: Ctx) -> Result:
    r = Result("R4")
    text = ctx.unit.get("pumping")
    ns = ctx.pmsl_hpa(ctx.station("south")) - ctx.pmsl_hpa(ctx.station("north"))
    for i, t in enumerate(ctx.t_sfc):
        if not text:
            r.add(t, NEIN, "keine besonderen Hinweise auf der Karte für dieses Tal")
            continue
        extra = f" Südüberdruck {ns[i]:.1f} hPa: Pässe werden möglicherweise nicht mehr überspült." if ns[i] > 1 else ""
        r.add(t, JA, text + extra)
    r.line("Lugano − Zürich", "hPa", ctx.t_sfc, ns)
    r.note = text or ""
    return r


def R5(ctx: Ctx) -> Result:
    r = Result("R5")
    s_lim, p_lim = ctx.th("R5", "snow"), ctx.th("R5", "precip_mm")
    snow, prec = [], []
    for i, t in enumerate(ctx.t_sfc):
        s = _snow(ctx, i)
        p, hours = _precip_48h(ctx, i)
        snow.append(s)
        prec.append(p)
        if math.isnan(s):
            r.add(t, KEINE)
            continue
        yes = s < s_lim and p < p_lim
        r.add(t, JA if yes else NEIN, f"Schnee {s:.0f} %, Niederschlag {p:.1f} mm/{hours:.0f} h")
    r.line("Schneebedeckung Talpunkte", "%", ctx.t_sfc, snow)
    r.line("Niederschlag letzte 48 h", "mm", ctx.t_sfc, prec, axis="right")
    r.note = "In den ersten 48 h des Laufs zählt nur der Niederschlag seit Laufbeginn."
    return r


def upvalley_from(ctx: Ctx) -> float:
    """Richtung (woher), aus der ein talaufwärts wehender Wind kommt."""
    axis = ctx.unit["axis"]
    return bearing(tuple(axis[-1]), tuple(axis[0]))


def _is_upvalley(ctx: Ctx, direction: float) -> bool:
    b = upvalley_from(ctx)
    return in_dir(direction, b - 60, b + 60)


def _lf_dir(ctx: Ctx) -> dict:
    ts, vs = ctx.lf(ctx.unit["station"], "dkl010h0")
    return dict(zip(ts, vs))


def _lf_day(ctx: Ctx, param: str, day) -> list[tuple]:
    ts, vs = ctx.lf(ctx.unit["station"], param)
    return [(t, v) for t, v in zip(ts, vs) if t.astimezone(TZ).date() == day]


def R6(ctx: Ctx) -> Result:
    r = Result("R6")
    abbr = ctx.unit["station"]
    for t in ctx.rep_times():
        prev = t.astimezone(TZ).date() - timedelta(days=1)
        rows = [(tt, v) for tt, v in _lf_day(ctx, "fu3010h0", prev) if 12 <= tt.astimezone(TZ).hour <= 18]
        if not rows:
            r.add(t, KEINE, "keine Lokalprognose für den Vortag")
            continue
        dirs = _lf_dir(ctx)
        exceed = []
        for tt, v in rows:
            c = ctx.clim_wind(abbr, tt)
            if c and _is_upvalley(ctx, float(dirs.get(tt, float("nan")))):
                exceed.append((v - c[3], v, c[3]))
        if not exceed and rows:
            r.add(t, NEUTRAL, "Vortag kein talaufwärts wehender Wind über P75")
            continue
        if not exceed:
            r.add(t, KEINE, "keine Klimatologie")
            continue
        mn = ctx.th("R6", "min_kmh")
        d, v, p75 = max(exceed, key=lambda x: x[1])
        hit = any(dd >= 0 and vv >= mn for dd, vv, _ in exceed)
        r.add(t, ALARM if hit else NEUTRAL, f"Vortag max. {v:.0f} km/h talaufwärts (P75 {p75:.0f})")
    ts, vs = ctx.lf(abbr, "fu3010h0")
    r.line(f"Lokalprognose Mittelwind {abbr}", "km/h", ts, vs)
    r.line("Klima P75", "km/h", ts, [(ctx.clim_wind(abbr, t) or [None] * 5)[3] for t in ts], role="klima")
    r.note = f"Referenzstation {abbr}. Vortag = Prognose für den Tag davor (für heute: Lauf von gestern)."
    return r


def R7(ctx: Ctx) -> Result:
    r = Result("R7")
    pt = f"{ctx.id}.0"
    side = ctx.unit["side"]
    lim = ctx.th("R7", "wind_kmh")
    sp_s = []
    for i, t in enumerate(ctx.t_ml):
        sp, d = ctx.wind_at(pt, i, 800, agl=True)
        sp_s.append(sp)
        if side == "inneralpin":
            r.add(t, NEUTRAL, "inneralpines Tal: nicht anwendbar")
            continue
        if math.isnan(sp):
            r.add(t, KEINE)
            continue
        if t.astimezone(TZ).month not in SUMMER:
            r.add(t, NEUTRAL, f"{sp:.0f} km/h aus {d:.0f}° (Winterhalbjahr: kein thermischer Talwind)")
            continue
        sector = (315, 45) if side == "nord" else (90, 180)
        yes = in_dir(d, *sector) and sp >= lim
        r.add(t, ALARM if yes else NEUTRAL, f"{sp:.0f} km/h aus {d:.0f}°")
    r.line("Wind 800 m über Grund (Talmündung)", "km/h", ctx.t_ml, sp_s)
    r.threshold("ab", lim, "km/h")
    r.points.append(ctx.point_info(pt))
    return r


def R8(ctx: Ctx) -> Result:
    r = Result("R8")
    abbr = ctx.unit["station"]
    for t in ctx.rep_times():
        day = t.astimezone(TZ).date()
        rows = _lf_day(ctx, "tre200h0", day)
        c = ctx.clim_tamp(abbr, day.month)
        if len(rows) < 20 or not c:
            r.add(t, KEINE, "Tag nicht vollständig in der Lokalprognose")
            continue
        vals = [v for _, v in rows]
        amp = max(vals) - min(vals)
        if day.month not in SUMMER:
            r.add(t, NEUTRAL, f"Amplitude {amp:.1f} K (Winterhalbjahr)")
            continue
        r.add(t, ALARM if amp < c[0] else NEUTRAL, f"Amplitude {amp:.1f} K (P25 {c[0]:.1f})")
    ts, vs = ctx.lf(abbr, "tre200h0")
    r.line(f"Lokalprognose Temperatur {abbr}", "°C", ts, vs)
    r.note = f"Referenzstation {abbr}; Klimatologie der Tagesamplitude im selben Monat."
    return r


def R9(ctx: Ctx) -> Result:
    r = Result("R9")
    abbr = ctx.unit["station"]
    mn = ctx.th("R9", "min_kmh")
    ts, vs = ctx.lf(abbr, "fu3010h0")
    dirs = _lf_dir(ctx)
    p75 = []
    for t, v in zip(ts, vs):
        c = ctx.clim_wind(abbr, t)
        p75.append(c[3] if c else None)
        d = float(dirs.get(t, float("nan")))
        if c is None:
            r.add(t, KEINE)
            continue
        up = _is_upvalley(ctx, d)
        txt = f"{v:.0f} km/h aus {d:.0f}° (P75 {c[3]:.0f})" + ("" if up else ", nicht talaufwärts")
        r.add(t, ALARM if up and v >= c[3] and v >= mn else NEUTRAL, txt)
    r.line(f"Lokalprognose Mittelwind {abbr}", "km/h", ts, vs)
    r.line("Klima P75", "km/h", ts, p75, role="klima")
    r.threshold("mindestens", mn, "km/h")
    r.note = (f"Referenzstation {abbr} (statistisch verbesserte Lokalprognose MeteoSchweiz). "
              f"Talwind = talaufwärts, aus {upvalley_from(ctx):.0f}° ±60°.")
    return r


def R10(ctx: Ctx) -> Result:
    r = Result("R10")
    n = len(ctx.unit["axis"])
    pt = f"{ctx.id}.{n // 2}"
    crest = float(ctx.unit["crest_m"])
    lim = ctx.th("R10", "inversion_k")
    bases = []
    for i, t in enumerate(ctx.t_ml):
        p = ctx.profile(pt, i)
        inv = [x for x in vertical.inversions(p["z"], p["T"], p["zs"] + 200, top=crest, min_strength=lim)
               if x["base"] < crest]
        bases.append(inv[0]["base"] if inv else float("nan"))
        r.add(t, ALARM if inv else NEUTRAL,
              f"Inversion {inv[0]['strength']:.1f} K ab {inv[0]['base']:.0f} m" if inv else "keine Inversion unter Kretenhöhe")
    r.line("Inversionsbasis unter Kretenhöhe", "m ü. M.", ctx.t_ml, bases)
    r.threshold("Kretenhöhe", crest, "m ü. M.")
    r.points.append(ctx.point_info(pt))
    return r


def RG(ctx: Ctx) -> Result:
    r = Result("RG")
    s_lim, p_lim = ctx.th("RG", "snow"), ctx.th("RG", "precip_mm")
    for i, t in enumerate(ctx.t_sfc):
        lt = t.astimezone(TZ)
        s = _snow(ctx, i)
        p, hours = _precip_48h(ctx, i)
        winter = lt.month in (11, 12, 1, 2, 3)
        ok = winter or (not math.isnan(s) and s >= s_lim) or p >= p_lim
        why = "Nov.–März" if winter else (f"Schnee {s:.0f} %" if s >= s_lim else f"Niederschlag {p:.0f} mm")
        r.add(t, GUENSTIG if ok else NEUTRAL, why if ok else f"Schnee {fmt(s, '%', 0)}, Niederschlag {p:.1f} mm")
    return r


CHECKS = {"R2": R2, "R3": R3, "R4": R4, "R5": R5, "R6": R6, "R7": R7, "R8": R8, "R9": R9, "R10": R10, "RG": RG}
