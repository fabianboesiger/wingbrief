"""JSON-Ausgabe für die statische Seite."""
from __future__ import annotations

import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import CONFIG, ROOT
from .checks.base import point_label
from .extract import N_DAYS, SECTIONS, Bundle, load_units, region_center
from .engine import PHENOMENA


def _dump(path: Path, data) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False, default=str)
    path.write_text(txt, encoding="utf-8")
    return len(txt.encode())


def _clean(o):
    """NaN/Inf entfernen (JSON-konform)."""
    if isinstance(o, float):
        return None if o != o or o in (float("inf"), float("-inf")) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def write(b: Bundle, status: dict, results: dict, catalog: dict, out: Path) -> dict:
    units = load_units()
    data = out / "data"
    days = []
    for d in range(N_DAYS):
        day = b.today.fromordinal(b.today.toordinal() + d)
        days.append({"key": f"d{d}", "date": day.isoformat()})
    index = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": {"name": "ICON-CH2-EPS", "run": b.run.isoformat(),
                  "local_forecast_run": b.lf_run.isoformat() if b.lf_run else None},
        "days": days,
        "sections": [{"key": k, "label": l, "from": lo, "to": min(hi, 18)} for k, l, lo, hi in SECTIONS],
        "phenomena": PHENOMENA,
        "status": status,
    }
    sizes = {"index.json": _dump(data / "index.json", _clean(index))}
    for uid, res in results.items():
        det = {"unit": uid, "run": b.run.isoformat(), "checks": {}}
        for cid, r in res.items():
            det["checks"][cid] = {
                "series": r.series, "points": r.points, "note": r.note,
                "entries": [[e.t.isoformat(), e.status, e.value] + ([list(e.ens)] if e.ens else []) for e in r.entries],
            }
        sizes[f"detail/{uid}.json"] = _dump(data / "detail" / f"{uid}.json", _clean(det))
    static = yaml.safe_load((CONFIG / "poster_static.yaml").read_text())
    regions = {rid: {"name": r["name"], "center": list(region_center(r)), "points": r["points"],
                     "stations": r["stations"], "channels": r.get("channels", []),
                     "valleys": [v for v, vv in units["valleys"].items() if vv["region"] == rid]}
               for rid, r in units["regions"].items()}
    valleys = {vid: {k: v[k] for k in ("name", "region", "axis", "side", "pass", "pass_valley", "crest_m", "station")}
               | {"pumping": v.get("pumping")} for vid, v in units["valleys"].items()}
    passes = {pid: {"name": p["name"], "crest": p["crest"], "north": p["north"], "south": p["south"]}
              for pid, p in units["passes"].items()}
    meta = {"catalog": catalog, "poster": static, "regions": regions, "valleys": valleys, "passes": passes}
    sizes["meta.json"] = _dump(data / "meta.json", _clean(meta))
    return sizes


def copy_site(out: Path) -> None:
    site = ROOT / "site"
    for p in site.rglob("*"):
        if p.is_file():
            dest = out / p.relative_to(site)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)


def archive(out_dir: Path, b: Bundle, index_path: Path) -> Path:
    """Komprimierte Kopie der Ausgabe je Lauf (für Kalibrierung und Vortageswerte)."""
    dest = out_dir / f"{b.run:%Y/%m}" / f"{b.run:%Y%m%d%H}.json.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest, "wb") as f:
        f.write(index_path.read_bytes())
    return dest
