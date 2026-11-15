"""Überregionaler Wind (Einheit: Region). SHV-Plakat, Zeile Planung."""
from __future__ import annotations

import math

import numpy as np

from .base import ACHTUNG, ALARM, GUENSTIG, JA, KEINE, NEIN, NEUTRAL, Ctx, Result, fmt, in_dir

HEIGHTS_AGL = (1500, 2000, 3000, 4000)
CHANNEL_DIRS = {"bise": (30, 90), "west": (225, 300)}


def _channel(ctx: Ctx, i: int) -> tuple[bool, str]:
    rid = ctx.id
    channels = ctx.units["regions"][rid].get("channels", [])
    sp, d = ctx.wind_at(f"{rid}.tal", i, 2000, agl=True)
    for c in channels:
        if in_dir(d, *CHANNEL_DIRS[c]) and sp >= 10:
            return True, f"{'Bise' if c == 'bise' else 'Westwind'} {sp:.0f} km/h aus {d:.0f}°"
    return False, f"{fmt(sp, 'km/h', 0)} aus {d:.0f}°"


def U2(ctx: Ctx) -> Result:
    r = Result("U2")
    warn, alarm = ctx.th("U2", "warn_kmh"), ctx.th("U2", "alarm_kmh")
    pts = ctx.region_points()
    per_h = {h: [] for h in HEIGHTS_AGL}
    for i, t in enumerate(ctx.t_ml):
        best, where = float("nan"), ""
        for h in HEIGHTS_AGL:
            sp = np.nanmax([ctx.wind_at(p, i, h, agl=True)[0] for p in pts])
            per_h[h].append(sp)
            if not math.isnan(sp) and (math.isnan(best) or sp > best):
                best, where = sp, f"{h} m ü. G."
        if math.isnan(best):
            r.add(t, KEINE)
            continue
        st = ALARM if best >= alarm else (ACHTUNG if best >= warn else NEUTRAL)
        chan, why = _channel(ctx, i)
        if st == ACHTUNG and chan:
            st = ALARM
            where += f"; kanalisiert ({why})"
        r.add(t, st, f"{best:.0f} km/h auf {where}")
    for h in HEIGHTS_AGL:
        r.line(f"Wind {h} m über Grund", "km/h", ctx.t_ml, per_h[h])
    r.threshold("Achtung", warn, "km/h")
    r.threshold("Alarm", alarm, "km/h")
    r.points.extend(ctx.point_info(p) for p in pts)
    r.note = "Stärkster Wert der drei Regionspunkte. SHV nennt keine Zahl für «zu stark»."
    return r


def U3(ctx: Ctx) -> Result:
    r = Result("U3")
    mean_l, gust_l = ctx.th("U3", "mean_kmh"), ctx.th("U3", "gust_kmh")
    stations = ctx.units["regions"][ctx.id]["stations"]
    series = {}
    for a in stations:
        series[a] = (ctx.lf(a, "fu3010h0"), ctx.lf(a, "fu3010h1"))
    times = sorted({t for (ts, _), _ in series.values() for t in ts})
    lookup = {a: (dict(zip(m[0], m[1])), dict(zip(g[0], g[1]))) for a, (m, g) in series.items()}
    for t in times:
        worst = None
        for a, (m, g) in lookup.items():
            if t in m:
                score = max(m[t] / mean_l, g.get(t, 0) / gust_l)
                if worst is None or score > worst[0]:
                    worst = (score, a, m[t], g.get(t, float("nan")))
        if worst is None:
            r.add(t, KEINE)
            continue
        _, a, mv, gv = worst
        r.add(t, ALARM if mv >= mean_l or gv >= gust_l else NEUTRAL, f"{a}: Mittel {mv:.0f}, Böe {gv:.0f} km/h")
    for a, ((ts, vs), (tg, vg)) in series.items():
        r.line(f"{a} Mittelwind", "km/h", ts, vs, colorKey=a)
        r.line(f"{a} Böen", "km/h", tg, vg, dashed=True, colorKey=a)
    r.threshold("Mittelwind", mean_l, "km/h")
    r.threshold("Böen", gust_l, "km/h")
    for a in stations:
        if a in ctx.b.stations:
            la, lo, _ = ctx.b.stations[a]
            r.points.append({"name": f"Station {a}", "lat": la, "lon": lo, "value": ""})
    return r


def U4(ctx: Ctx) -> Result:
    r = Result("U4")
    channels = ctx.units["regions"][ctx.id].get("channels", [])
    for i, t in enumerate(ctx.t_ml):
        if not channels:
            r.add(t, NEIN, "keine kanalisierenden Geländeformen hinterlegt")
            continue
        chan, why = _channel(ctx, i)
        r.add(t, JA if chan else NEIN, why)
    r.note = "Hinterlegt: " + (", ".join({"bise": "Bise", "west": "Westwind"}[c] for c in channels) or "keine")
    return r


def U5(ctx: Ctx) -> Result:
    r = Result("U5")
    lim = ctx.th("U5", "dp_hpa")
    we = ctx.pmsl_hpa(ctx.station("west")) - ctx.pmsl_hpa(ctx.station("east"))
    for i, t in enumerate(ctx.t_sfc):
        j = ctx.sfc_back(t, 3)
        if j is None or math.isnan(we[i]):
            r.add(t, KEINE)
            continue
        rising = abs(we[i]) > abs(we[j])
        kind = "Bise" if we[i] < 0 else "West"
        st = ALARM if abs(we[i]) > lim and rising else NEUTRAL
        r.add(t, st, f"Genf−Kloten {we[i]:+.1f} hPa ({kind}){', zunehmend' if rising else ''}")
    r.line("Genf − Kloten (QFF)", "hPa", ctx.t_sfc, we)
    r.threshold("SHV: über", lim, "hPa")
    r.threshold("Bise: unter", -lim, "hPa")
    if ctx.b.ens_pmsl:
        cw, ce = ctx.b.col(ctx.station("west")), ctx.b.col(ctx.station("east"))
        steps = ctx.b.steps["ens"]
        frac = []
        for k, h in enumerate(ctx.b.steps["ens_valid"]):
            i, j = steps.index(h), steps.index(h - 3)
            alarms = []
            for arr in ctx.b.ens_pmsl.values():
                d, d0 = (arr[i, cw] - arr[i, ce]) / 100, (arr[j, cw] - arr[j, ce]) / 100
                alarms.append(abs(d) > lim and abs(d) > abs(d0))
            fa = float(np.mean(alarms))
            frac.append(fa * 100)
            r.add(ctx.t_ens[k], ALARM if fa >= 0.3 else NEUTRAL, f"{fa:.0%} der Members über {lim:.0f} hPa und zunehmend",
                  ens=(fa, 1 - fa))
        r.line("Members mit Alarm", "%", ctx.t_ens, frac, role="ensemble")
    for k in ("west", "east"):
        r.points.append(ctx.point_info(ctx.station(k)))
    return r


def UG(ctx: Ctx) -> Result:
    r = Result("UG")
    qff, wl = ctx.th("UG", "qff_hpa"), ctx.th("UG", "wind_kmh")
    tal = f"{ctx.id}.tal"
    p = ctx.pmsl_hpa(tal)
    pts = ctx.region_points()
    for i, t in enumerate(ctx.t_ml):
        k = ctx.sfc_near(t)
        if k is None:
            r.add(t, KEINE)
            continue
        winds = [ctx.wind_at(q, i, h, agl=True)[0] for q in pts for h in HEIGHTS_AGL]
        winds += [float(np.hypot(ctx.sfc("U_10M", q)[k], ctx.sfc("V_10M", q)[k]) * 3.6) for q in pts]
        mx = float(np.nanmax(winds))
        ok = p[k] >= qff and mx < wl
        r.add(t, GUENSTIG if ok else NEUTRAL, f"QFF {p[k]:.0f} hPa, max. Wind {mx:.0f} km/h")
    r.line("Bodendruck (QFF)", "hPa", ctx.t_sfc, p)
    r.threshold("Hochdruck ab", qff, "hPa")
    r.points.append(ctx.point_info(tal))
    return r


CHECKS = {"U2": U2, "U3": U3, "U4": U4, "U5": U5, "UG": UG}
