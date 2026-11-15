"""Daten für einen Lauf zusammenstellen: Punkte, Flächen, Zeitschritte, Downloads."""
from __future__ import annotations

import concurrent.futures as cf
import csv
import io
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import yaml

from . import CONFIG, icon, net, stac

log = logging.getLogger(__name__)
TZ = ZoneInfo("Europe/Zurich")

ML_LEVELS = (36, 80)          # Hauptflächen ca. 0–6000 m ü. M. über der Schweiz
ML_VARS = ["U", "V", "T", "QV", "P"]
SFC_VARS = ["PMSL", "U_10M", "V_10M", "VMAX_10M", "TOT_PREC", "LPI_MAX", "CAPE_ML", "SNOWC"]
ENS_VARS = ["PMSL", "TOT_PREC"]
SECTIONS = [("morgen", "Morgen", 6, 10), ("mittag", "Mittag", 10, 14), ("nachmittag", "Nachmittag", 14, 19)]
ENS_HOURS = (8, 12, 16)
N_DAYS = 5


def load_units() -> dict:
    return yaml.safe_load((CONFIG / "units.yaml").read_text())


def section_of(t: datetime) -> str | None:
    h = t.astimezone(TZ).hour
    for key, _, lo, hi in SECTIONS:
        if lo <= h < hi:
            return key
    return None


def day_index(t: datetime, today: date) -> int:
    return (t.astimezone(TZ).date() - today).days


# ------------------------------------------------------------------ Punkte
def station_coords() -> dict[str, tuple[float, float, float]]:
    """SwissMetNet-Stationen aus den Metadaten der Lokalprognose: abbr -> (lat, lon, Höhe)."""
    txt = net.get(f"https://data.geo.admin.ch/{stac.LOCAL}/ogd-local-forecasting_meta_point.csv").content.decode("latin1")
    out = {}
    for row in csv.DictReader(io.StringIO(txt), delimiter=";"):
        if row["point_type_id"] == "1" and row["station_abbr"]:
            out[row["station_abbr"]] = (float(row["point_coordinates_wgs84_lat"]),
                                        float(row["point_coordinates_wgs84_lon"]),
                                        float(row["point_height_masl"] or "nan"))
    return out


def station_point_ids() -> dict[str, str]:
    txt = net.get(f"https://data.geo.admin.ch/{stac.LOCAL}/ogd-local-forecasting_meta_point.csv").content.decode("latin1")
    return {row["station_abbr"]: row["point_id"]
            for row in csv.DictReader(io.StringIO(txt), delimiter=";")
            if row["point_type_id"] == "1" and row["station_abbr"]}


def build_points(units: dict, stations: dict) -> dict[str, tuple[float, float]]:
    pts: dict[str, tuple[float, float]] = {}
    for rid, r in units["regions"].items():
        for k, (la, lo) in r["points"].items():
            pts[f"{rid}.{k}"] = (la, lo)
    for vid, v in units["valleys"].items():
        for i, (la, lo) in enumerate(v["axis"]):
            pts[f"{vid}.{i}"] = (la, lo)
    for pid, p in units["passes"].items():
        for k in ("crest", "north", "south"):
            pts[f"pass.{pid}.{k}"] = tuple(p[k])
    for abbr in units["pressure_stations"].values():
        la, lo, _ = stations[abbr]
        pts[f"st.{abbr}"] = (la, lo)
    return pts


def region_center(r: dict) -> tuple[float, float]:
    arr = np.array(list(r["points"].values()))
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def build_areas(units: dict, grid: icon.Grid) -> dict[str, np.ndarray]:
    areas = {}
    for rid, r in units["regions"].items():
        cells = [grid.within(la, lo, 30.0) for la, lo in r["points"].values()]
        areas[f"reg.{rid}"] = np.unique(np.concatenate(cells))
        la, lo = region_center(r)
        areas[f"west.{rid}"] = grid.within(la, lo, 200.0, (225.0, 315.0))
    return areas


# ------------------------------------------------------------- Zeitschritte
def select_steps(run: datetime, quick: bool = False) -> dict[str, list[int]]:
    sfc = list(range(0, 49)) + list(range(51, 121, 3))
    ml, ens = [], []
    for h in range(0, 121):
        t = (run + timedelta(hours=h)).astimezone(TZ)
        if h <= 48 and 6 <= t.hour <= 18:
            ml.append(h)
        elif h > 48 and t.hour in ENS_HOURS:
            ml.append(h)
            ens.append(h)
    if quick:
        ml = [h for h in ml if (run + timedelta(hours=h)).astimezone(TZ).hour in ENS_HOURS]
        ens = ens[::3]
    ens_all = sorted(set(ens) | {h - 3 for h in ens})
    return {"sfc": sfc, "ml": ml, "ens": ens_all, "ens_valid": ens}


# ------------------------------------------------------------------- Bündel
@dataclass
class Bundle:
    run: datetime
    today: date
    points: dict[str, tuple[float, float]]
    pindex: dict[str, int]                         # Punkt -> Spalte
    steps: dict[str, list[int]]
    sfc: dict[str, np.ndarray] = field(default_factory=dict)     # var -> (nsfc, npts)
    ml: dict[str, np.ndarray] = field(default_factory=dict)      # var -> (nml, nlev, npts)
    hfl: np.ndarray | None = None                                # (nlev, npts)
    hsurf: np.ndarray | None = None                              # (npts,)
    area_cover: dict[str, np.ndarray] = field(default_factory=dict)  # area -> (nsfc,)
    area_max: dict[str, np.ndarray] = field(default_factory=dict)
    ens_pmsl: dict[int, np.ndarray] = field(default_factory=dict)    # member -> (nens, npts)
    ens_cover: dict[str, np.ndarray] = field(default_factory=dict)   # area -> (members, nens_valid)
    lf: dict[str, dict[str, tuple[list[datetime], np.ndarray]]] = field(default_factory=dict)
    lf_run: datetime | None = None
    stations: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    def t(self, kind: str) -> list[datetime]:
        return [self.run + timedelta(hours=h) for h in self.steps[kind]]

    def col(self, point: str) -> int:
        return self.pindex[point]


RATE = 0.5  # mm/h für «Niederschlagsfläche»


def _rates(acc: np.ndarray, steps: list[int]) -> np.ndarray:
    """Akkumulierten Niederschlag (Zeit, ...) in mm/h des vorangehenden Intervalls umrechnen."""
    out = np.full_like(acc, np.nan)
    for i in range(1, len(steps)):
        out[i] = (acc[i] - acc[i - 1]) / (steps[i] - steps[i - 1])
    return np.clip(out, 0, None)


def build_bundle(run: datetime, cache: Path, *, quick: bool = False, workers: int = 8,
                 with_ensemble: bool = True, with_local: bool = True) -> Bundle:
    t0 = time.time()
    units = load_units()
    stations = station_coords()
    grid = icon.load_grid(stac.ICON_CH2, cache)
    points = build_points(units, stations)
    names = list(points)
    idx = np.array([grid.nearest(*points[n]) for n in names])
    areas = build_areas(units, grid)
    area_union = np.unique(np.concatenate(list(areas.values())))
    pos_in_union = {a: np.searchsorted(area_union, cells) for a, cells in areas.items()}
    steps = select_steps(run, quick)
    today = datetime.now(timezone.utc).astimezone(TZ).date()
    b = Bundle(run=run, today=today, points=points, pindex={n: i for i, n in enumerate(names)},
               steps=steps, stations=stations)
    b.hfl = grid.hfl[ML_LEVELS[0] - 1:ML_LEVELS[1], idx]
    b.hsurf = grid.hsurf[idx]

    log.info("Assets suchen …")
    assets = {v: stac.icon_assets(stac.ICON_CH2, run, v) for v in set(SFC_VARS + ML_VARS + ENS_VARS)}

    jobs = []
    for v in SFC_VARS:
        for i, h in enumerate(steps["sfc"]):
            jobs.append(("sfc", v, i, h))
    for v in ML_VARS:
        for i, h in enumerate(steps["ml"]):
            jobs.append(("ml", v, i, h))
    if with_ensemble:
        for v in ENS_VARS:
            for i, h in enumerate(steps["ens"]):
                jobs.append(("ens", v, i, h))

    nsfc, nml, nens = len(steps["sfc"]), len(steps["ml"]), len(steps["ens"])
    npts = len(names)
    nlev = ML_LEVELS[1] - ML_LEVELS[0] + 1
    for v in SFC_VARS:
        b.sfc[v] = np.full((nsfc, npts), np.nan, np.float32)
    for v in ML_VARS:
        b.ml[v] = np.full((nml, nlev, npts), np.nan, np.float32)
    prec_area = np.full((nsfc, len(area_union)), np.nan, np.float32)
    ens_prec: dict[int, np.ndarray] = {}
    ens_pmsl: dict[int, np.ndarray] = {}
    msg_len_ml: dict[str, int] = {}

    def run_job(job):
        kind, v, i, h = job
        href = assets[v].get((h, kind == "ens"))
        if href is None:
            return job, None
        if kind == "ml":
            if v not in msg_len_ml:
                msg_len_ml[v] = icon.message_length(href)[0]
            return job, icon.fetch_points(href, idx, levels=ML_LEVELS, msg_len=msg_len_ml[v])
        if v == "TOT_PREC":
            return job, icon.fetch_points(href, np.concatenate([idx, area_union]))
        return job, icon.fetch_points(href, idx)

    log.info("%d Downloads (%s) …", len(jobs), "quick" if quick else "voll")
    with cf.ThreadPoolExecutor(workers) as ex:
        for job, res in ex.map(run_job, jobs):
            if res is None:
                continue
            kind, v, i, h = job
            if kind == "sfc":
                vals = res[0]
                if v == "TOT_PREC":
                    b.sfc[v][i] = vals[:npts]
                    prec_area[i] = vals[npts:]
                else:
                    b.sfc[v][i] = vals
            elif kind == "ml":
                b.ml[v][i] = res[0]
            else:
                for m, vals in res.items():
                    if v == "PMSL":
                        ens_pmsl.setdefault(m, np.full((nens, npts), np.nan, np.float32))[i] = vals
                    else:
                        ens_prec.setdefault(m, np.full((nens, npts + len(area_union)), np.nan, np.float32))[i] = vals

    # Niederschlagsflächen
    rates = _rates(prec_area, steps["sfc"])
    for a, pos in pos_in_union.items():
        sub = rates[:, pos]
        b.area_cover[a] = np.where(np.isnan(sub).all(axis=1), np.nan, np.nanmean(sub >= RATE, axis=1))
        b.area_max[a] = np.nanmax(np.where(np.isnan(sub), -1, sub), axis=1)
        b.area_max[a][b.area_max[a] < 0] = np.nan

    if ens_pmsl:
        b.ens_pmsl = ens_pmsl
        valid = steps["ens_valid"]
        vi = [steps["ens"].index(h) for h in valid]
        prev = [steps["ens"].index(h - 3) for h in valid]
        members = sorted(ens_prec)
        for a, pos in pos_in_union.items():
            cov = np.full((len(members), len(valid)), np.nan, np.float32)
            for mi, m in enumerate(members):
                arr = ens_prec[m][:, npts:][:, pos]
                r = np.clip((arr[vi] - arr[prev]) / 3.0, 0, None)
                cov[mi] = np.nanmean(r >= RATE, axis=1)
            b.ens_cover[a] = cov

    if with_local:
        abbrs = set()
        for r in units["regions"].values():
            abbrs |= set(r["stations"])
        for v in units["valleys"].values():
            abbrs.add(v["station"])
        b.lf, b.lf_run = load_local_forecast(sorted(abbrs))
    log.info("Bündel fertig in %.0f s", time.time() - t0)
    return b


# --------------------------------------------------- Lokalprognose (Punkte)
LF_PARAMS = ["fu3010h0", "fu3010h1", "dkl010h0", "tre200h0"]


def _lf_files(day: date) -> dict[str, dict[str, str]]:
    item = net.get(f"{stac.API}/collections/{stac.LOCAL}/items/{day:%Y%m%d}-ch")
    files: dict[str, dict[str, str]] = {}
    for key, a in item.json().get("assets", {}).items():
        parts = key.split(".")
        files.setdefault(parts[2], {})[parts[3]] = a["href"]
    return files


def load_local_forecast(abbrs: list[str]) -> tuple[dict, datetime | None]:
    """Neueste Lokalprognose plus Vortageslauf (für R6) an den Stationen abbrs."""
    ids = station_point_ids()
    want = {ids[a]: a for a in abbrs if a in ids}
    today = datetime.now(timezone.utc).date()
    out: dict[str, dict[str, tuple[list[datetime], np.ndarray]]] = {a: {} for a in want.values()}
    latest_run = None
    runs = []
    for day in (today - timedelta(days=1), today):
        try:
            files = _lf_files(day)
        except Exception as e:  # noqa: BLE001
            log.warning("Lokalprognose %s nicht verfügbar: %s", day, e)
            continue
        complete = [r for r, f in files.items() if all(p in f for p in LF_PARAMS)]
        if complete:
            runs.append(files[max(complete)])
            latest_run = datetime.strptime(max(complete), "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    series: dict[tuple[str, str], dict[datetime, float]] = {}
    for files in runs:  # älterer Lauf zuerst, neuerer überschreibt
        for p in LF_PARAMS:
            txt = net.get(files[p]).content.decode("latin1")
            for row in csv.reader(io.StringIO(txt), delimiter=";"):
                if row and row[0] in want:
                    try:
                        t = datetime.strptime(row[2], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                        series.setdefault((want[row[0]], p), {})[t] = float(row[3])
                    except (ValueError, IndexError):
                        continue
    for (a, p), d in series.items():
        ts = sorted(d)
        out[a][p] = (ts, np.array([d[t] for t in ts], np.float32))
    return out, latest_run
