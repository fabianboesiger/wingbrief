"""Vertikale Profile: Interpolation auf Höhen, Theta-E, Inversionen, Gradienten.

Profile sind von oben nach unten geordnet (ICON-Konvention). Die Funktionen
arbeiten mit einem einzelnen Profil (z: Höhen ü. M., Werte gleicher Länge).
"""
from __future__ import annotations

import math

import numpy as np


def at_height(z: np.ndarray, values: np.ndarray, target: float) -> float:
    """Linear auf die Höhe target (m ü. M.) interpolieren; NaN unter Grund."""
    order = np.argsort(z)
    zs, vs = z[order], values[order]
    if target < zs[0] or target > zs[-1]:
        return float("nan")
    return float(np.interp(target, zs, vs))


def at_pressure(p: np.ndarray, values: np.ndarray, target_pa: float) -> float:
    """Logarithmisch im Druck interpolieren; NaN falls ausserhalb."""
    lp = np.log(p)
    order = np.argsort(lp)
    xs, vs = lp[order], values[order]
    t = math.log(target_pa)
    if t < xs[0] or t > xs[-1]:
        return float("nan")
    return float(np.interp(t, xs, vs))


def wind(u: float, v: float) -> tuple[float, float]:
    """(Geschwindigkeit km/h, Richtung woher °)."""
    speed = math.hypot(u, v) * 3.6
    direction = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    return speed, direction


def angle_diff(a: float, b: float) -> float:
    d = abs((a - b + 180) % 360 - 180)
    return d


def theta_e(t_k: float, qv: float, p_pa: float) -> float:
    """Pseudopotentielle (äquivalentpotentielle) Temperatur nach Bolton (1980), in K."""
    p_hpa = p_pa / 100.0
    r = qv / (1 - qv)  # Mischungsverhältnis kg/kg
    e = p_hpa * r / (0.622 + r)
    e = max(e, 1e-6)
    t_l = 2840.0 / (3.5 * math.log(t_k) - math.log(e) - 4.805) + 55.0
    return t_k * (1000.0 / p_hpa) ** (0.2854 * (1 - 0.28 * r)) * math.exp(
        (3.376 / t_l - 0.00254) * r * 1000 * (1 + 0.81 * r))


def rel_humidity(t_k: float, qv: float, p_pa: float) -> float:
    r = qv / (1 - qv)
    e = p_pa / 100.0 * r / (0.622 + r)
    es = 6.112 * math.exp(17.67 * (t_k - 273.15) / (t_k - 29.65))
    return 100.0 * e / es


def inversions(z: np.ndarray, t: np.ndarray, zsurf: float, top: float = 5000.0,
               min_strength: float = 0.5) -> list[dict]:
    """Schichten, in denen die Temperatur mit der Höhe zunimmt.

    Rückgabe: Liste von {base, top, strength} (m ü. M., K), von unten nach oben.
    """
    order = np.argsort(z)
    zs, ts = z[order], t[order]
    keep = (zs >= zsurf) & (zs <= top)
    zs, ts = zs[keep], ts[keep]
    out = []
    i = 0
    while i < len(zs) - 1:
        if ts[i + 1] > ts[i]:
            j = i
            while j < len(zs) - 1 and ts[j + 1] > ts[j]:
                j += 1
            strength = float(ts[j] - ts[i])
            if strength >= min_strength:
                out.append({"base": float(zs[i]), "top": float(zs[j]), "strength": strength})
            i = j
        else:
            i += 1
    return out


def lapse_rate(z: np.ndarray, t: np.ndarray, z0: float, z1: float) -> float:
    """Temperaturabnahme in °C/100 m zwischen z0 und z1 (positiv = Abnahme)."""
    t0, t1 = at_height(z, t, z0), at_height(z, t, z1)
    if math.isnan(t0) or math.isnan(t1):
        return float("nan")
    return (t0 - t1) / (z1 - z0) * 100.0


def max_lapse(z: np.ndarray, t: np.ndarray, lo: float, hi: float, depth: float = 500.0,
              stepm: float = 100.0) -> tuple[float, float]:
    """Grösste Temperaturabnahme (°C/100 m) einer Schicht der Dicke depth in [lo, hi].

    Rückgabe: (Rate, Basis der Schicht).
    """
    best, base = float("nan"), float("nan")
    zb = lo
    while zb + depth <= hi + 1e-6:
        r = lapse_rate(z, t, zb, zb + depth)
        if not math.isnan(r) and (math.isnan(best) or r > best):
            best, base = r, zb
        zb += stepm
    return best, base
