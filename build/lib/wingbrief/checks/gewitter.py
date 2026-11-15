"""Wärmegewitter / Luftschichtung (Einheit: Region). SHV-Plakat, Zeile Planung."""
from __future__ import annotations

import math

import numpy as np

from .. import vertical
from ..extract import TZ
from .base import ALARM, GUENSTIG, KEINE, NEUTRAL, Ctx, Result, fmt


def W2(ctx: Ctx) -> Result:
    r = Result("W2")
    tal = f"{ctx.id}.tal"
    p = ctx.pmsl_hpa(tal)
    st = {k: ctx.pmsl_hpa(ctx.station(k)) for k in ("west", "east", "south", "north")}
    qff, grad = ctx.th("W2", "qff_hpa"), ctx.th("W2", "grad_hpa")
    allp = np.stack(list(st.values()) + [p])
    spread = np.nanmax(allp, axis=0) - np.nanmin(allp, axis=0)
    wl = ctx.th("W2", "wind_kmh")
    for i, t in enumerate(ctx.t_ml):
        k = ctx.sfc_near(t)
        if k is None or math.isnan(p[k]):
            r.add(t, KEINE)
            continue
        w = ctx.wind_at(f"{ctx.id}.voralpen", i, 3000)[0]
        flat = p[k] < qff and spread[k] < grad and not math.isnan(w) and w < wl
        r.add(t, ALARM if flat else NEUTRAL, f"QFF {p[k]:.1f} hPa, Spannweite {spread[k]:.1f} hPa, Wind 3000 m {fmt(w, 'km/h', 0)}")
    r.line("Bodendruck (QFF) Region", "hPa", ctx.t_sfc, p)
    r.line("Druck-Spannweite über die Schweiz", "hPa", ctx.t_sfc, spread, axis="right")
    r.threshold("Tiefdruck unter", qff, "hPa")
    r.points.append(ctx.point_info(tal))
    r.note = ("Spannweite = grösster minus kleinster QFF von Genf, Kloten, Lugano, Zürich und der Region. "
              "Zusätzlich schwacher Wind auf 3000 m ü. M. (flache Lage = schwache Strömung).")
    return r


def W3(ctx: Ctx) -> Result:
    r = Result("W3")
    cov = ctx.b.area_cover[f"reg.{ctx.id}"]
    mx = ctx.b.area_max[f"reg.{ctx.id}"]
    lim_max, lim_cov = ctx.th("W3", "max_mm_h"), ctx.th("W3", "cover")
    for i, t in enumerate(ctx.t_sfc):
        if math.isnan(mx[i]):
            r.add(t, KEINE)
            continue
        st = ALARM if mx[i] >= lim_max and cov[i] < lim_cov else NEUTRAL
        r.add(t, st, f"max {mx[i]:.1f} mm/h, Fläche {cov[i]:.0%}")
    r.line("Maximale Niederschlagsrate", "mm/h", ctx.t_sfc, mx)
    r.line("Fläche mit Niederschlag", "%", ctx.t_sfc, cov * 100, axis="right")
    r.threshold("Intensität ab", lim_max, "mm/h")
    r.points.extend(ctx.point_info(p) for p in ctx.region_points())
    return r


def W4(ctx: Ctx) -> Result:
    r = Result("W4")
    pts = ctx.region_points()
    cape = np.nanmax(np.stack([ctx.sfc("CAPE_ML", p) for p in pts]), axis=0)
    lim = ctx.th("W4", "cape")
    for i, t in enumerate(ctx.t_sfc):
        if math.isnan(cape[i]):
            r.add(t, KEINE)
            continue
        afternoon = 12 <= t.astimezone(TZ).hour <= 18
        r.add(t, ALARM if cape[i] >= lim and afternoon else NEUTRAL, f"CAPE {cape[i]:.0f} J/kg")
    r.line("CAPE (mittlere Schicht), max. Regionspunkte", "J/kg", ctx.t_sfc, cape)
    r.threshold("Hinweis ab", lim, "J/kg")
    r.points.extend(ctx.point_info(p) for p in pts)
    return r


def _theta_e_850(ctx: Ctx, point: str, i: int) -> float:
    p = ctx.profile(point, i)
    if p["P"].max() < 85000:
        return float("nan")
    t = vertical.at_pressure(p["P"], p["T"], 85000)
    q = vertical.at_pressure(p["P"], p["QV"], 85000)
    if math.isnan(t) or math.isnan(q):
        return float("nan")
    return vertical.theta_e(t, q, 85000) - 273.15


def W5(ctx: Ctx) -> Result:
    r = Result("W5")
    pts = [f"{ctx.id}.tal", f"{ctx.id}.voralpen"]
    lim = ctx.th("W5", "theta_e_c")
    vals = []
    for i, t in enumerate(ctx.t_ml):
        v = np.nanmax([_theta_e_850(ctx, p, i) for p in pts]) if any(
            not math.isnan(_theta_e_850(ctx, p, i)) for p in pts) else float("nan")
        vals.append(v)
        r.add(t, KEINE if math.isnan(v) else (ALARM if v > lim else NEUTRAL), fmt(v, "°C"))
    r.line("Theta-E 850 hPa", "°C", ctx.t_ml, vals)
    r.threshold("SHV-Schwelle", lim, "°C")
    r.points.extend(ctx.point_info(p) for p in pts)
    r.note = "850 hPa liegt im Gebirge teils unter Grund; dann zählt nur der andere Punkt."
    return r


def _lowest_inversion(p: dict, min_k: float = 0.5) -> dict | None:
    inv = vertical.inversions(p["z"], p["T"], p["zs"] + 100, top=5000, min_strength=min_k)
    return inv[0] if inv else None


def W6(ctx: Ctx) -> Result:
    r = Result("W6")
    pt = f"{ctx.id}.voralpen"
    lim, sink = ctx.th("W6", "lapse"), ctx.th("W6", "sink_m")
    rates, bases = [], []
    for i, t in enumerate(ctx.t_ml):
        p = ctx.profile(pt, i)
        lo = max(1500.0, p["zs"] + 300.0)
        rate, zb = vertical.max_lapse(p["z"], p["T"], lo, 3000.0)
        stable_above = False
        if not math.isnan(rate):
            above = vertical.lapse_rate(p["z"], p["T"], zb + 500, zb + 1500)
            inv = [x for x in vertical.inversions(p["z"], p["T"], zb + 500, top=zb + 2000)]
            stable_above = (not math.isnan(above) and above < 0.3) or bool(inv)
        invl = _lowest_inversion(p)
        base = invl["base"] if invl else float("nan")
        rates.append(rate)
        bases.append(base)
        j = ctx.ml_back(t, 24)
        sinking = False
        if j is not None and j < len(bases) and not math.isnan(base) and not math.isnan(bases[j]):
            sinking = bases[j] - base >= sink
        if math.isnan(rate) and math.isnan(base):
            r.add(t, KEINE)
            continue
        labile = not math.isnan(rate) and rate >= lim and stable_above
        val = f"{fmt(rate, '°C/100 m', 2)} ab {fmt(zb, 'm', 0)}"
        if not math.isnan(base):
            val += f"; Inversion ab {base:.0f} m"
        if sinking:
            val += " (sinkt)"
        r.add(t, ALARM if labile or sinking else NEUTRAL, val)
    r.line("Grösste Temperaturabnahme 1500–3000 m", "°C/100 m", ctx.t_ml, rates)
    r.line("Basis der untersten Inversion", "m ü. M.", ctx.t_ml, bases, axis="right")
    r.threshold("SHV: zu hohe Labilität ab", lim, "°C/100 m")
    r.points.append(ctx.point_info(pt))
    return r


def W8(ctx: Ctx) -> Result:
    r = Result("W8")
    tal = f"{ctx.id}.tal"
    p = ctx.pmsl_hpa(tal)
    lim = ctx.th("W8", "rise_hpa")
    rise = []
    for i, t in enumerate(ctx.t_sfc):
        j = ctx.sfc_back(t, 24)
        if j is None or math.isnan(p[i]):
            rise.append(float("nan"))
            r.add(t, KEINE, "kein Wert 24 h vorher")
            continue
        d = p[i] - p[j]
        rise.append(d)
        r.add(t, ALARM if d >= lim else NEUTRAL, f"{d:+.1f} hPa in 24 h")
    r.line("Druckänderung 24 h", "hPa", ctx.t_sfc, rise)
    r.threshold("Subsidenz ab", lim, "hPa")
    r.points.append(ctx.point_info(tal))
    return r


def WG(ctx: Ctx) -> Result:
    r = Result("WG")
    pt = f"{ctx.id}.voralpen"
    cov = ctx.b.area_cover[f"reg.{ctx.id}"]
    inv_k, rh_lim = ctx.th("WG", "inversion_k"), ctx.th("WG", "rh")
    strengths, rhs = [], []
    for i, t in enumerate(ctx.t_ml):
        p = ctx.profile(pt, i)
        inv = vertical.inversions(p["z"], p["T"], p["zs"], top=4000, min_strength=0.5)
        s = max((x["strength"] for x in inv), default=0.0)
        tt = vertical.at_height(p["z"], p["T"], 3000)
        qq = vertical.at_height(p["z"], p["QV"], 3000)
        pp = vertical.at_height(p["z"], p["P"], 3000)
        rh = vertical.rel_humidity(tt, qq, pp) if not math.isnan(tt) else float("nan")
        strengths.append(s)
        rhs.append(rh)
        k = ctx.sfc_near(t)
        dry = k is not None and not math.isnan(cov[k]) and cov[k] < 0.05
        ok = dry and (s >= inv_k or (not math.isnan(rh) and rh < rh_lim))
        r.add(t, GUENSTIG if ok else NEUTRAL,
              f"Inversion {s:.1f} K, RF 3000 m {fmt(rh, '%', 0)}" + ("" if dry else ", Niederschlag"))
    r.line("Stärkste Inversion bis 4000 m", "K", ctx.t_ml, strengths)
    r.line("Relative Feuchte 3000 m ü. M.", "%", ctx.t_ml, rhs, axis="right")
    r.threshold("starke Inversion ab", inv_k, "K")
    r.points.append(ctx.point_info(pt))
    return r


CHECKS = {"W2": W2, "W3": W3, "W4": W4, "W5": W5, "W6": W6, "W8": W8, "WG": WG}
