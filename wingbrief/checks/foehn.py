"""Föhn (Einheit: Tal). SHV-Plakat, Zeile Planung.

Talseite «nord» liegt bei Südföhn im Lee (Luv = Süden), «sued» bei Nordföhn.
Inneralpine Täler werden für beide Richtungen geprüft (der schlechtere Wert zählt).
"""
from __future__ import annotations

import math

import numpy as np

from .. import vertical
from ..extract import TZ, section_of
from .base import ACHTUNG, ALARM, GUENSTIG, JA, KEINE, NEIN, NEUTRAL, Ctx, Result, bearing, fmt, in_dir


def _directions(ctx: Ctx) -> list[str]:
    """Föhnrichtungen, für die das Tal im Lee liegt: 'sued' = Südföhn, 'nord' = Nordföhn."""
    side = ctx.unit["side"]
    return {"nord": ["sued"], "sued": ["nord"]}.get(side, ["sued", "nord"])


def _pass(ctx: Ctx) -> tuple[str, dict]:
    pid = ctx.unit["pass"]
    return pid, ctx.units["passes"][pid]


def O2(ctx: Ctx) -> Result:
    r = Result("O2")
    lim = ctx.th("O2", "wind_kmh")
    axis = ctx.unit["axis"]
    downvalley_from = bearing(tuple(axis[0]), tuple(axis[-1]))  # Wind kommt vom Talende her
    pts = ctx.valley_points()
    s2000, s800 = [], []
    for i, t in enumerate(ctx.t_ml):
        best = None
        m2000 = m800 = float("nan")
        for p in pts:
            for h, agl in ((2000, False), (800, True)):
                sp, d = ctx.wind_at(p, i, h, agl=agl)
                if math.isnan(sp):
                    continue
                if agl:
                    m800 = sp if math.isnan(m800) else max(m800, sp)
                else:
                    m2000 = sp if math.isnan(m2000) else max(m2000, sp)
                along = in_dir(d, downvalley_from - 45, downvalley_from + 45)
                score = sp if along else 0
                if best is None or score > best[0]:
                    best = (score, sp, d, h, agl, along)
        s2000.append(m2000)
        s800.append(m800)
        if best is None:
            r.add(t, KEINE)
            continue
        _, sp, d, h, agl, along = best
        lvl = f"{h} m {'über Grund' if agl else 'ü. M.'}"
        r.add(t, ALARM if along and sp >= lim else NEUTRAL,
              f"{sp:.0f} km/h aus {d:.0f}° auf {lvl}" + (" (talauswärts)" if along else ""))
    r.line("Wind 2000 m ü. M. (max. Talpunkte)", "km/h", ctx.t_ml, s2000)
    r.line("Wind 800 m über Grund (max. Talpunkte)", "km/h", ctx.t_ml, s800)
    r.threshold("Alarm ab (talauswärts)", lim, "km/h")
    r.points.extend(ctx.point_info(p) for p in pts)
    r.note = f"Talauswärts = Wind aus {downvalley_from:.0f}° ±45°."
    return r


def O3(ctx: Ctx) -> Result:
    r = Result("O3")
    pid, ps = _pass(ctx)
    pt = f"pass.{pid}.crest"
    ang, lim = ctx.th("O3", "angle"), ctx.th("O3", "wind_kmh")
    dirs = _directions(ctx)
    s3, s4 = [], []
    for i, t in enumerate(ctx.t_ml):
        hits, vals = [], []
        sp3, d3 = ctx.wind_at(pt, i, 3000)
        sp4, d4 = ctx.wind_at(pt, i, 4000)
        s3.append(sp3)
        s4.append(sp4)
        for sp, d, h in ((sp3, d3, 3000), (sp4, d4, 4000)):
            if math.isnan(sp):
                continue
            vals.append(f"{h} m: {sp:.0f} km/h aus {d:.0f}°")
            for fd in dirs:
                normal = ps["normal_from_south"] + (0 if fd == "sued" else 180)
                if vertical.angle_diff(d, normal) <= ang and sp >= lim:
                    hits.append(fd)
        if not vals:
            r.add(t, KEINE)
            continue
        r.add(t, ALARM if hits else NEUTRAL, "; ".join(vals))
    r.line(f"Wind 3000 m ü. M. ({ps['name']})", "km/h", ctx.t_ml, s3)
    r.line(f"Wind 4000 m ü. M. ({ps['name']})", "km/h", ctx.t_ml, s4)
    r.threshold("ab", lim, "km/h")
    r.points.append(ctx.point_info(pt))
    r.note = f"Kammnormale {ps['name']}: Südföhn aus {ps['normal_from_south']}°, Nordföhn aus {(ps['normal_from_south'] + 180) % 360}°. Gilt nicht für seichten Föhn (siehe O7)."
    return r


def _dp(ctx: Ctx, fd: str) -> np.ndarray:
    """Druckdifferenz Luv minus Lee in hPa für Südföhn ('sued') bzw. Nordföhn ('nord')."""
    ns = ctx.pmsl_hpa(ctx.station("south")) - ctx.pmsl_hpa(ctx.station("north"))
    return ns if fd == "sued" else -ns


def O4(ctx: Ctx) -> Result:
    r = Result("O4")
    warn, alarm, rise = ctx.th("O4", "warn_hpa"), ctx.th("O4", "alarm_hpa"), ctx.th("O4", "rise_hpa")
    dirs = _directions(ctx)
    dps = {fd: _dp(ctx, fd) for fd in dirs}
    for i, t in enumerate(ctx.t_sfc):
        j = ctx.sfc_back(t, 6)
        worst = None
        for fd, dp in dps.items():
            if math.isnan(dp[i]):
                continue
            inc = j is not None and dp[i] - dp[j] >= rise
            st = ALARM if dp[i] >= alarm else (ACHTUNG if dp[i] >= warn or (dp[i] >= 2 and inc) else NEUTRAL)
            name = "Südföhn" if fd == "sued" else "Nordföhn"
            cand = (st, f"{name}: Luv−Lee {dp[i]:+.1f} hPa" + (", zunehmend" if inc else ""))
            if worst is None or _rank(cand[0]) > _rank(worst[0]):
                worst = cand
        if worst is None:
            r.add(t, KEINE)
        else:
            r.add(t, *worst)
    ns = ctx.pmsl_hpa(ctx.station("south")) - ctx.pmsl_hpa(ctx.station("north"))
    r.line("Lugano − Zürich (QFF)", "hPa", ctx.t_sfc, ns)
    for fd in dirs:
        sign = 1 if fd == "sued" else -1
        r.threshold(f"Alarm {'Südföhn' if fd == 'sued' else 'Nordföhn'}", sign * alarm, "hPa")
        r.threshold(f"Achtung {'Südföhn' if fd == 'sued' else 'Nordföhn'}", sign * warn, "hPa")
    if ctx.b.ens_pmsl:
        cs, cn = ctx.b.col(ctx.station("south")), ctx.b.col(ctx.station("north"))
        steps = ctx.b.steps["ens"]
        frac = []
        for k, h in enumerate(ctx.b.steps["ens_valid"]):
            i = steps.index(h)
            fa_list, fo_list = [], []
            for arr in ctx.b.ens_pmsl.values():
                ns_m = (arr[i, cs] - arr[i, cn]) / 100
                vals = [ns_m if fd == "sued" else -ns_m for fd in dirs]
                fa_list.append(max(vals) >= alarm)
                fo_list.append(max(vals) < warn)
            fa, fo = float(np.mean(fa_list)), float(np.mean(fo_list))
            frac.append(fa * 100)
            r.add(ctx.t_ens[k], ALARM if fa >= 0.3 else NEUTRAL, f"{fa:.0%} der Members ab {alarm:.0f} hPa", ens=(fa, fo))
        r.line("Members mit Alarm", "%", ctx.t_ens, frac, role="ensemble")
    for k in ("south", "north"):
        r.points.append(ctx.point_info(ctx.station(k)))
    r.note = "Schwellen 3/4 hPa: DHV; SHV nennt nur «ausgeprägt oder zunehmend»."
    return r


def _rank(st: str) -> int:
    from .base import RANK
    return RANK[st]


def O5(ctx: Ctx) -> Result:
    r = Result("O5")
    lim = ctx.th("O5", "lapse")
    n = len(ctx.unit["axis"])
    pt = f"{ctx.id}.{n // 2}"
    rates = []
    for i, t in enumerate(ctx.t_ml):
        p = ctx.profile(pt, i)
        rate = vertical.lapse_rate(p["z"], p["T"], p["zs"] + 50, p["zs"] + 1500)
        rates.append(rate)
        lt = t.astimezone(TZ)
        yes = lt.month in range(3, 9) and section_of(t) in ("mittag", "nachmittag") and not math.isnan(rate) and rate >= lim
        r.add(t, JA if yes else NEIN, f"{lt:%B}, {fmt(rate, '°C/100 m', 2)} in den unteren 1500 m")
    r.line("Temperaturabnahme untere 1500 m", "°C/100 m", ctx.t_ml, rates)
    r.threshold("ab", lim, "°C/100 m")
    r.points.append(ctx.point_info(pt))
    return r


def O6(ctx: Ctx) -> Result:
    r = Result("O6")
    pid, ps = _pass(ctx)
    yes = bool(ctx.unit.get("pass_valley"))
    for t in ctx.rep_times():
        r.add(t, JA if yes else NEIN, f"Tal beginnt am {ps['name']}" if yes else "Tal beginnt nicht an einem Pass am Alpenhauptkamm")
    return r


def pass_height(ctx: Ctx) -> float:
    """Vergleichshöhe: ca. 2000 m ü. M. (SHV «Passhöhe und darüber»), mindestens 100 m über Modellgelände."""
    pid, _ = _pass(ctx)
    zs = max(float(ctx.b.hsurf[ctx.b.col(f"pass.{pid}.{k}")]) for k in ("north", "south"))
    return max(2000.0, round(zs + 100.0, -1))


def _pass_temps(ctx: Ctx, i: int) -> tuple[float, float]:
    pid, _ = _pass(ctx)
    h = pass_height(ctx)
    return ctx.t_at(f"pass.{pid}.north", i, h), ctx.t_at(f"pass.{pid}.south", i, h)


def O7(ctx: Ctx) -> Result:
    r = Result("O7")
    warn, alarm = ctx.th("O7", "warn_k"), ctx.th("O7", "alarm_k")
    pid, ps = _pass(ctx)
    dirs = _directions(ctx)
    tn_s, ts_s = [], []
    for i, t in enumerate(ctx.t_ml):
        tn, ts = _pass_temps(ctx, i)
        tn_s.append(tn)
        ts_s.append(ts)
        if math.isnan(tn) or math.isnan(ts):
            r.add(t, KEINE)
            continue
        worst = None
        for fd in dirs:
            cooler = (tn - ts) if fd == "sued" else (ts - tn)  # Luv kühler um …
            st = ALARM if cooler >= alarm else (ACHTUNG if cooler >= warn else NEUTRAL)
            name = "Südföhn" if fd == "sued" else "Nordföhn"
            cand = (st, f"{name}: Luv {cooler:+.1f} °C kühler (N {tn:.1f}, S {ts:.1f} °C)")
            if worst is None or _rank(cand[0]) > _rank(worst[0]):
                worst = cand
        r.add(t, *worst)
    h = pass_height(ctx)
    r.line(f"{ps['name']} Nord, {h:.0f} m ü. M.", "°C", ctx.t_ml, tn_s)
    r.line(f"{ps['name']} Süd, {h:.0f} m ü. M.", "°C", ctx.t_ml, ts_s)
    r.points.extend(ctx.point_info(f"pass.{pid}.{k}") for k in ("north", "south"))
    r.note = (f"Vergleich auf {h:.0f} m ü. M. (Passhöhe ca. 2000 m, mindestens 100 m über dem Modellgelände). "
              "Luv kühler als Lee ab 1–2 °C (SHV). Funktioniert auch bei seichtem Föhn.")
    return r


def OG(ctx: Ctx) -> Result:
    r = Result("OG")
    dt_lim, dp_lim = ctx.th("OG", "dt_k"), ctx.th("OG", "dp_hpa")
    dirs = _directions(ctx)
    dps = {fd: _dp(ctx, fd) for fd in dirs}
    for i, t in enumerate(ctx.t_ml):
        tn, ts = _pass_temps(ctx, i)
        k = ctx.sfc_near(t)
        if math.isnan(tn) or k is None:
            r.add(t, KEINE)
            continue
        ok = True
        txt = []
        for fd in dirs:
            lee_warmer = (tn - ts) if fd == "sued" else (ts - tn)
            ok &= lee_warmer <= dt_lim and dps[fd][k] < dp_lim
            txt.append(f"{'Südföhn' if fd == 'sued' else 'Nordföhn'}: Lee {lee_warmer:+.1f} °C, Luv−Lee {dps[fd][k]:+.1f} hPa")
        r.add(t, GUENSTIG if ok else NEUTRAL, "; ".join(txt))
    r.note = f"Temperaturvergleich auf {pass_height(ctx):.0f} m ü. M."
    return r


CHECKS = {"O2": O2, "O3": O3, "O4": O4, "O5": O5, "O6": O6, "O7": O7, "OG": OG}
