"""Stationsklimatologie aus SwissMetNet-Stundenwerten (für «gewohnt», «stärker als gewohnt»).

Ergebnis (config/climatology.json):
  wind[abbr][monat][stunde_lokal] = [P10, P25, P50, P75, P90] Mittelwind km/h
  tamp[abbr][monat] = [P25, P50, P75] Tagesamplitude der Temperatur in K
"""
from __future__ import annotations

import concurrent.futures as cf
import csv
import io
import json
import logging
from datetime import datetime, timezone

import numpy as np
import yaml

from . import CONFIG, net, stac

log = logging.getLogger(__name__)
SMN = "ch.meteoschweiz.ogd-smn"
PCTS = [10, 25, 50, 75, 90]


def stations_needed() -> list[str]:
    units = yaml.safe_load((CONFIG / "units.yaml").read_text())
    s = set()
    for r in units["regions"].values():
        s |= set(r["stations"])
    for v in units["valleys"].values():
        s.add(v["station"])
    return sorted(s)


def station_climatology(abbr: str) -> dict | None:
    from .extract import TZ
    item = net.get(f"{stac.API}/collections/{SMN}/items/{abbr.lower()}").json()
    hrefs = [a["href"] for k, a in item["assets"].items()
             if "_h_historical_" in k and k.split("_")[-1][:4] >= "2010"]
    if not hrefs:
        return None
    wind = {m: {h: [] for h in range(24)} for m in range(1, 13)}
    temps: dict = {}
    for href in hrefs:
        txt = net.get(href).content.decode("latin1")
        for row in csv.DictReader(io.StringIO(txt), delimiter=";"):
            try:
                t = datetime.strptime(row["reference_timestamp"], "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
            except (KeyError, ValueError):
                continue
            lt = t.astimezone(TZ)
            fu = row.get("fu3010h0", "")
            if fu not in ("", None):
                wind[lt.month][lt.hour].append(float(fu))
            ta = row.get("tre200h0", "")
            if ta not in ("", None):
                temps.setdefault(lt.date(), []).append(float(ta))
    out_w = {}
    for m, hours in wind.items():
        out_w[m] = {h: [round(float(x), 1) for x in np.percentile(v, PCTS)] if len(v) > 50 else None
                    for h, v in hours.items()}
    amps: dict = {m: [] for m in range(1, 13)}
    for d, vals in temps.items():
        if len(vals) >= 20:
            amps[d.month].append(max(vals) - min(vals))
    out_t = {m: [round(float(x), 1) for x in np.percentile(v, [25, 50, 75])] if len(v) > 20 else None
             for m, v in amps.items()}
    return {"wind": out_w, "tamp": out_t}


def build(workers: int = 6) -> dict:
    abbrs = stations_needed()
    res = {"wind": {}, "tamp": {}, "pcts": PCTS,
           "source": "SwissMetNet Stundenwerte ab 2010, MeteoSchweiz",
           "generated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with cf.ThreadPoolExecutor(workers) as ex:
        for abbr, c in zip(abbrs, ex.map(station_climatology, abbrs)):
            if c is None:
                log.warning("keine Klimadaten für %s", abbr)
                continue
            res["wind"][abbr] = c["wind"]
            res["tamp"][abbr] = c["tamp"]
            log.info("Klima %s ok", abbr)
    return res


def write(path=CONFIG / "climatology.json") -> None:
    data = build()
    path.write_text(json.dumps(data, separators=(",", ":")))


def load(path=CONFIG / "climatology.json") -> dict:
    if not path.exists():
        return {"wind": {}, "tamp": {}}
    return json.loads(path.read_text())
