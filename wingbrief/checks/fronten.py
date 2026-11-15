"""Fronten (Einheit: Region). SHV-Plakat, Zeile Planung."""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np

from .base import ALARM, GUENSTIG, KEINE, NEUTRAL, Ctx, Result, fmt


def _rid(ctx: Ctx) -> str:
    return ctx.id


def F2(ctx: Ctx) -> Result:
    r = Result("F2")
    rid = _rid(ctx)
    west = ctx.b.area_cover[f"west.{rid}"]
    reg = ctx.b.area_cover[f"reg.{rid}"]
    rate = ctx.th("F2", "west_cover")
    for i, t in enumerate(ctx.t_sfc):
        if math.isnan(west[i]) or math.isnan(reg[i]):
            r.add(t, KEINE)
            continue
        j = ctx.sfc_index(t + timedelta(hours=3))
        approaching = reg[i] >= rate or (j is not None and not math.isnan(reg[j]) and reg[j] > reg[i] + 0.02)
        st = ALARM if west[i] >= rate and approaching else NEUTRAL
        r.add(t, st, f"West {west[i]:.0%}, Region {reg[i]:.0%}")
    r.line("Fläche mit Niederschlag westlich", "%", ctx.t_sfc, west * 100)
    r.line("Fläche mit Niederschlag in der Region", "%", ctx.t_sfc, reg * 100)
    r.threshold("Schwelle Westsektor", rate * 100, "%")
    # Ensemble Tag 3–5
    ens_w = ctx.b.ens_cover.get(f"west.{rid}")
    ens_r = ctx.b.ens_cover.get(f"reg.{rid}")
    if ens_w is not None and len(ctx.t_ens):
        frac = []
        for k, t in enumerate(ctx.t_ens):
            alarm = (ens_w[:, k] >= rate) & ((ens_r[:, k] >= rate) | (ens_w[:, k] >= rate))
            fa = float(np.mean(alarm))
            frac.append(fa * 100)
            r.add(t, ALARM if fa >= 0.3 else NEUTRAL, f"{fa:.0%} der Members mit Niederschlag im Westen", ens=(fa, 1 - fa))
        r.line("Members mit organisiertem Niederschlag", "%", ctx.t_ens, frac, role="ensemble")
    la, lo = ctx.units["regions"][rid]["points"]["tal"]
    r.points.append({"name": "Region (30 km um die Regionspunkte)", "lat": la, "lon": lo, "value": ""})
    r.note = "Sektor 225–315°, 0–200 km ab Regionsmitte; Niederschlag ≥ 0.5 mm/h."
    return r


def F3(ctx: Ctx) -> Result:
    r = Result("F3")
    pt = f"{ctx.id}.voralpen"
    tal = f"{ctx.id}.tal"
    p = ctx.pmsl_hpa(tal)
    west = ctx.b.area_cover[f"west.{ctx.id}"]
    lim = ctx.th("F3", "wind_kmh")
    sp_s, dir_s = [], []
    for i, t in enumerate(ctx.t_ml):
        sp, d = ctx.wind_at(pt, i, 3000)
        sp_s.append(sp)
        dir_s.append(d)
        k = ctx.sfc_near(t)
        if math.isnan(sp) or k is None:
            r.add(t, KEINE)
            continue
        lo, hi = max(0, k - 12), min(len(p), k + 13)
        win = p[lo:hi]
        kmin = lo + int(np.nanargmin(win))
        trough = 0 < kmin - lo < len(win) - 1 and np.nanmax(p[kmin:hi]) - p[kmin] >= 1.0
        westerly = 225 <= d <= 315 and sp >= lim
        st = ALARM if westerly and (trough or west[k] >= 0.2) else NEUTRAL
        r.add(t, st, f"3000 m: {fmt(sp, 'km/h', 0)} aus {d:.0f}°" + (", Trog" if trough else ""))
    r.line("Wind 3000 m ü. M.", "km/h", ctx.t_ml, sp_s)
    r.line("Windrichtung 3000 m ü. M.", "°", ctx.t_ml, dir_s, axis="dir")
    r.line("Bodendruck (QFF)", "hPa", ctx.t_sfc, p, axis="right")
    r.threshold("Westwind ab", lim, "km/h")
    r.points.append(ctx.point_info(pt))
    return r


def F5(ctx: Ctx) -> Result:
    r = Result("F5")
    pts = ctx.region_points()
    lpi = np.nanmax(np.stack([ctx.sfc("LPI_MAX", p) for p in pts]), axis=0)
    cov = ctx.b.area_cover[f"reg.{ctx.id}"]
    mx = ctx.b.area_max[f"reg.{ctx.id}"]
    for i, t in enumerate(ctx.t_sfc):
        if math.isnan(lpi[i]):
            r.add(t, KEINE)
            continue
        spotty = mx[i] >= 5 and cov[i] < 0.3
        st = ALARM if lpi[i] > 0 or spotty else NEUTRAL
        r.add(t, st, f"LPI {fmt(lpi[i], '', 1)}" + (", fleckig" if spotty else ""))
    r.line("Blitzpotential LPI (max. Regionspunkte)", "J/kg", ctx.t_sfc, lpi)
    r.threshold("Alarm ab", 0, "J/kg")
    r.points.extend(ctx.point_info(p) for p in pts)
    return r


def F6(ctx: Ctx) -> Result:
    r = Result("F6")
    pt = f"{ctx.id}.tal"
    lim = ctx.th("F6", "drop_k")
    temps = [ctx.t_at(pt, i, 1500) for i in range(len(ctx.t_ml))]
    for i, t in enumerate(ctx.t_ml):
        j = ctx.ml_back(t, 24)
        if j is None or math.isnan(temps[i]) or math.isnan(temps[j]):
            r.add(t, KEINE, "kein Wert 24 h vorher")
            continue
        d = temps[i] - temps[j]
        r.add(t, ALARM if d <= -lim else NEUTRAL, f"{d:+.1f} K in 24 h ({temps[i]:.1f} °C)")
    r.line("Temperatur 1500 m ü. M.", "°C", ctx.t_ml, temps)
    r.points.append(ctx.point_info(pt))
    r.note = "Vergleich mit dem Wert 24 h früher im selben Lauf (ab Tag 2)."
    return r


def FG(ctx: Ctx) -> Result:
    r = Result("FG")
    tal = f"{ctx.id}.tal"
    p = ctx.pmsl_hpa(tal)
    we = ctx.pmsl_hpa(ctx.station("west")) - ctx.pmsl_hpa(ctx.station("east"))
    ns = ctx.pmsl_hpa(ctx.station("south")) - ctx.pmsl_hpa(ctx.station("north"))
    qff, wl = ctx.th("FG", "qff_hpa"), ctx.th("FG", "wind_kmh")
    pts = ctx.region_points()
    for i, t in enumerate(ctx.t_ml):
        k = ctx.sfc_near(t)
        if k is None:
            r.add(t, KEINE)
            continue
        w10 = max(np.hypot(ctx.sfc("U_10M", q)[k], ctx.sfc("V_10M", q)[k]) * 3.6 for q in pts)
        w2k = np.nanmax([ctx.wind_at(q, i, 2000)[0] for q in pts])
        ok = p[k] >= qff and abs(we[k]) < 2 and abs(ns[k]) < 2 and w10 < wl and w2k < wl
        r.add(t, GUENSTIG if ok else NEUTRAL,
              f"QFF {p[k]:.0f} hPa, ΔP W-O {we[k]:+.1f}, N-S {ns[k]:+.1f}, Wind {w2k:.0f} km/h")
    r.line("Bodendruck (QFF)", "hPa", ctx.t_sfc, p)
    r.line("Genf − Kloten", "hPa", ctx.t_sfc, we, axis="right")
    r.line("Lugano − Zürich", "hPa", ctx.t_sfc, ns, axis="right")
    r.threshold("Hochdruck ab", qff, "hPa")
    if ctx.b.ens_pmsl:
        c = {k: ctx.b.col(ctx.station(k)) for k in ("west", "east", "south", "north")}
        ct = ctx.b.col(tal)
        idx = [ctx.b.steps["ens"].index(h) for h in ctx.b.steps["ens_valid"]]
        for k, t in enumerate(ctx.t_ens):
            oks = []
            for m, arr in ctx.b.ens_pmsl.items():
                a = arr[idx[k]] / 100
                oks.append(a[ct] >= qff and abs(a[c["west"]] - a[c["east"]]) < 2 and abs(a[c["south"]] - a[c["north"]]) < 2)
            fo = float(np.mean(oks))
            r.add(t, GUENSTIG if fo >= 0.8 else NEUTRAL, f"{fo:.0%} der Members Hochdrucklage", ens=(0.0, fo))
    r.points.append(ctx.point_info(tal))
    return r


CHECKS = {"F2": F2, "F3": F3, "F5": F5, "F6": F6, "FG": FG}
