"""Gemeinsame Typen und Hilfen für die Checks."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from .. import vertical
from ..extract import TZ, Bundle

ALARM, ACHTUNG, UNSICHER, NEUTRAL, GUENSTIG, KEINE = (
    "alarm", "achtung", "unsicher", "neutral", "guenstig", "keine_daten")
RANK = {ALARM: 5, ACHTUNG: 4, UNSICHER: 3, NEUTRAL: 2, GUENSTIG: 1, KEINE: 0}
# Faktoren
JA, NEIN = "trifft_zu", "trifft_nicht_zu"


@dataclass
class Entry:
    t: datetime
    status: str
    value: str = ""
    ens: tuple[float, float] | None = None   # (Anteil Alarm, Anteil ok) der Members


@dataclass
class Result:
    id: str
    entries: list[Entry] = field(default_factory=list)
    series: list[dict] = field(default_factory=list)
    points: list[dict] = field(default_factory=list)
    note: str = ""

    def add(self, t, status, value="", ens=None):
        self.entries.append(Entry(t, status, value, ens))

    def line(self, label: str, unit: str, times, values, role: str = "prognose", **kw):
        self.series.append({
            "label": label, "unit": unit, "role": role,
            "t": [t.isoformat() for t in times],
            "v": [None if (v is None or (isinstance(v, float) and math.isnan(v))) else round(float(v), 2)
                  for v in values], **kw})

    def threshold(self, label: str, value: float, unit: str):
        self.series.append({"label": label, "unit": unit, "role": "schwelle", "value": value})


def fmt(v: float, unit: str = "", nd: int = 1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sep = "" if unit in ("°", "%") else " "
    return f"{v:.{nd}f}{(sep + unit) if unit else ''}"


class Ctx:
    """Zugriff auf die Daten für eine Einheit (Region oder Tal)."""

    def __init__(self, b: Bundle, units: dict, catalog: dict, clim: dict, unit_id: str, kind: str):
        self.b, self.units, self.catalog, self.clim = b, units, catalog, clim
        self.id, self.kind = unit_id, kind
        self.unit = units["regions" if kind == "region" else "valleys"][unit_id]
        self.t_sfc = b.t("sfc")
        self.t_ml = b.t("ml")
        self.t_ens = [b.run + timedelta(hours=h) for h in b.steps.get("ens_valid", [])]

    # ---------------------------------------------------------- Schwellen
    def th(self, check: str, key: str) -> float:
        return float(self.catalog["checks"][check]["thresholds"][key]["value"])

    # -------------------------------------------------------- Bodenfelder
    def sfc(self, var: str, point: str) -> np.ndarray:
        return self.b.sfc[var][:, self.b.col(point)].astype(float)

    def pmsl_hpa(self, point: str) -> np.ndarray:
        return self.sfc("PMSL", point) / 100.0

    def station(self, role: str) -> str:
        return "st." + self.units["pressure_stations"][role]

    def sfc_index(self, t: datetime) -> int | None:
        try:
            return self.t_sfc.index(t)
        except ValueError:
            return None

    def sfc_near(self, t: datetime, tol_h: float = 1.5) -> int | None:
        best, bi = None, None
        for i, ts in enumerate(self.t_sfc):
            d = abs((ts - t).total_seconds())
            if d <= tol_h * 3600 and (best is None or d < best):
                best, bi = d, i
        return bi

    def rep_times(self) -> list[datetime]:
        """Repräsentative Zeiten (08, 12, 16 Uhr lokal) für Tag 0–4."""
        from ..extract import N_DAYS
        out = []
        for d in range(N_DAYS):
            day = self.b.today + timedelta(days=d)
            for h in (8, 12, 16):
                out.append(datetime(day.year, day.month, day.day, h, tzinfo=TZ))
        return out

    def sfc_back(self, t: datetime, hours: int) -> int | None:
        return self.sfc_index(t - timedelta(hours=hours))

    # -------------------------------------------------------- Profile
    def profile(self, point: str, i: int) -> dict:
        c = self.b.col(point)
        return {
            "z": self.b.hfl[:, c].astype(float),
            "zs": float(self.b.hsurf[c]),
            **{v: self.b.ml[v][i, :, c].astype(float) for v in ("U", "V", "T", "QV", "P")},
        }

    def wind_at(self, point: str, i: int, height: float, agl: bool = False) -> tuple[float, float]:
        p = self.profile(point, i)
        h = height + (p["zs"] if agl else 0.0)
        u = vertical.at_height(p["z"], p["U"], h)
        v = vertical.at_height(p["z"], p["V"], h)
        if math.isnan(u) or math.isnan(v):
            return float("nan"), float("nan")
        return vertical.wind(u, v)

    def t_at(self, point: str, i: int, height: float) -> float:
        p = self.profile(point, i)
        return vertical.at_height(p["z"], p["T"], height) - 273.15

    def ml_back(self, t: datetime, hours: int) -> int | None:
        try:
            return self.t_ml.index(t - timedelta(hours=hours))
        except ValueError:
            return None

    # -------------------------------------------------------- Lokalprognose
    def lf(self, abbr: str, param: str) -> tuple[list[datetime], np.ndarray]:
        return self.b.lf.get(abbr, {}).get(param, ([], np.array([])))

    def clim_wind(self, abbr: str, t: datetime) -> list[float] | None:
        lt = t.astimezone(TZ)
        try:
            return self.clim["wind"][abbr][str(lt.month)][str(lt.hour)]
        except (KeyError, TypeError):
            return None

    def clim_tamp(self, abbr: str, month: int) -> list[float] | None:
        try:
            return self.clim["tamp"][abbr][str(month)]
        except (KeyError, TypeError):
            return None

    # -------------------------------------------------------- Geometrie
    def region_points(self) -> list[str]:
        rid = self.id if self.kind == "region" else self.unit["region"]
        return [f"{rid}.{k}" for k in self.units["regions"][rid]["points"]]

    def valley_points(self) -> list[str]:
        return [f"{self.id}.{i}" for i in range(len(self.unit["axis"]))]

    def point_info(self, point: str, value: str = "") -> dict:
        la, lo = self.b.points[point]
        return {"name": point_label(point, self.units), "lat": la, "lon": lo, "value": value}


def point_label(point: str, units: dict) -> str:
    parts = point.split(".")
    if parts[0] == "st":
        return f"Station {parts[1]}"
    if parts[0] == "pass":
        p = units["passes"][parts[1]]["name"]
        return {"crest": p, "north": f"{p} Nord", "south": f"{p} Süd"}[parts[2]]
    if parts[0] in units["regions"]:
        return f"{units['regions'][parts[0]]['name']} ({ {'tal': 'Tal', 'voralpen': 'Voralpen/Mittelland', 'kamm': 'Kamm'}[parts[1]] })"
    if parts[0] in units["valleys"]:
        v = units["valleys"][parts[0]]
        n = len(v["axis"])
        i = int(parts[1])
        pos = "Mündung" if i == 0 else ("Talende" if i == n - 1 else f"Talpunkt {i}")
        return f"{v['name']} ({pos})"
    return point


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Richtung von a nach b in Grad (0 = Nord)."""
    dy = (b[0] - a[0]) * 111.2
    dx = (b[1] - a[1]) * 111.2 * math.cos(math.radians(a[0]))
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def in_dir(d: float, lo: float, hi: float) -> bool:
    """Liegt Richtung d im Sektor [lo, hi] (im Uhrzeigersinn, über 360 möglich)?"""
    if math.isnan(d):
        return False
    lo %= 360
    hi %= 360
    return lo <= d <= hi if lo <= hi else (d >= lo or d <= hi)
