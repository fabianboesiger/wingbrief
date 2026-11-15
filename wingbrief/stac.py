"""Zugriff auf die STAC-API von data.geo.admin.ch (Open Data MeteoSchweiz)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import net

API = "https://data.geo.admin.ch/api/stac/v1"
ICON_CH2 = "ch.meteoschweiz.ogd-forecasting-icon-ch2"
ICON_CH1 = "ch.meteoschweiz.ogd-forecasting-icon-ch1"
LOCAL = "ch.meteoschweiz.ogd-local-forecasting"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def horizon(hours: int) -> str:
    d, h = divmod(hours, 24)
    return f"P{d}DT{h:02d}H00M00S"


def search(collection: str, limit: int = 100, **props) -> list[dict]:
    payload = {"collections": [collection], "limit": limit}
    payload.update(props)
    feats: list[dict] = []
    url = f"{API}/search"
    while True:
        d = net.post_json(url, payload)
        feats.extend(d.get("features", []))
        nxt = next((l for l in d.get("links", []) if l.get("rel") == "next"), None)
        if not nxt or len(feats) >= limit:
            return feats
        body = nxt.get("body", {})
        payload = {**payload, **body} if nxt.get("merge") else body
        url = nxt["href"]


def asset_href(feature: dict) -> str:
    return next(iter(feature["assets"].values()))["href"]


def collection_asset(collection: str, asset_id: str) -> str:
    return net.get(f"{API}/collections/{collection}/assets/{asset_id}").json()["href"]


def icon_href(collection: str, run: datetime, variable: str, step: int,
              perturbed: bool = False) -> str | None:
    feats = search(collection, limit=1, **{
        "forecast:reference_datetime": iso(run),
        "forecast:variable": variable,
        "forecast:horizon": horizon(step),
        "forecast:perturbed": perturbed,
    })
    return asset_href(feats[0]) if feats else None


def icon_assets(collection: str, run: datetime, variable: str) -> dict[tuple[int, bool], str]:
    """Alle Assets einer Variable eines Laufs: {(step, perturbed): href}."""
    out = {}
    for f in search(collection, limit=10_000, **{
            "forecast:reference_datetime": iso(run), "forecast:variable": variable}):
        p = f["properties"]
        hz = p["forecast:horizon"]  # PnDTnnHnnMnnS
        days = int(hz[1:hz.index("D")])
        hours = int(hz[hz.index("T") + 1:hz.index("H")])
        out[(days * 24 + hours, bool(p["forecast:perturbed"]))] = asset_href(f)
    return out


def latest_complete_run(collection: str = ICON_CH2, max_step: int = 120,
                        probe_variable: str = "PMSL") -> datetime | None:
    """Neuester Lauf, für den der letzte Zeitschritt bereits publiziert ist."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    every = 6 if collection == ICON_CH2 else 3
    run = now.replace(hour=now.hour - now.hour % every)
    for _ in range(6):
        if icon_href(collection, run, probe_variable, max_step):
            return run
        run -= timedelta(hours=every)
    return None
