"""ICON-CH1/CH2-EPS: Gitter, Teil-Downloads und Extraktion an Punkten.

Die GRIB2-Dateien von MeteoSchweiz enthalten pro Datei eine Variable für einen
Zeitschritt. Mehrflächen-Variablen haben 80 Meldungen (Fläche 1 = oben,
80 = unten), perturbierte Dateien 20 Members × 80 Flächen. Alle Meldungen
einer Datei sind gleich lang (einfache Packung). Darum lässt sich ein
zusammenhängender Block von Flächen mit einem einzigen HTTP-Range-Request
laden.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import eccodes
import numpy as np

from . import net, stac

N_LEVELS = 80


@dataclass
class Grid:
    lat: np.ndarray
    lon: np.ndarray
    hhl: np.ndarray  # (81, ncell) Höhe der Flächengrenzen ü. M., 1 = oben
    hsurf: np.ndarray

    @property
    def hfl(self) -> np.ndarray:
        """Höhe der Hauptflächen (Mitte zwischen zwei HHL-Grenzen), (80, ncell)."""
        return 0.5 * (self.hhl[:-1] + self.hhl[1:])

    def nearest(self, lat: float, lon: float) -> int:
        dy = (self.lat - lat) * 111.2
        dx = (self.lon - lon) * 111.2 * np.cos(np.radians(lat))
        return int(np.argmin(dx * dx + dy * dy))

    def within(self, lat: float, lon: float, radius_km: float,
               bearing_range: tuple[float, float] | None = None) -> np.ndarray:
        """Zellindizes im Radius, optional nur in einem Richtungssektor (woher, °)."""
        dy = (self.lat - lat) * 111.2
        dx = (self.lon - lon) * 111.2 * np.cos(np.radians(lat))
        dist = np.hypot(dx, dy)
        mask = dist <= radius_km
        if bearing_range:
            brg = (np.degrees(np.arctan2(dx, dy)) + 360) % 360
            lo, hi = bearing_range
            mask &= (brg >= lo) & (brg <= hi)
        return np.nonzero(mask)[0]


def _read_messages(data: bytes) -> list[tuple[dict, np.ndarray]]:
    out = []
    pos = 0
    while pos < len(data):
        if data[pos:pos + 4] != b"GRIB":
            raise ValueError("keine GRIB-Meldung an Position %d" % pos)
        length = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
        gid = eccodes.codes_new_from_message(data[pos:pos + length])
        try:
            meta = {
                "level": eccodes.codes_get(gid, "level"),
                "number": eccodes.codes_get(gid, "number") if eccodes.codes_is_defined(gid, "number") else 0,
                "shortName": eccodes.codes_get(gid, "shortName"),
            }
            out.append((meta, eccodes.codes_get_values(gid)))
        finally:
            eccodes.codes_release(gid)
        pos += length
    return out


def load_grid(collection: str, cache_dir: Path) -> Grid:
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = "ch2" if collection == stac.ICON_CH2 else "ch1"
    npz = cache_dir / f"grid_{tag}.npz"
    if npz.exists():
        d = np.load(npz)
        return Grid(d["lat"], d["lon"], d["hhl"], d["hsurf"])
    model = "icon-ch2-eps" if tag == "ch2" else "icon-ch1-eps"
    hz = net.get(stac.collection_asset(collection, f"horizontal_constants_{model}.grib2")).content
    vt = net.get(stac.collection_asset(collection, f"vertical_constants_{model}.grib2")).content
    fields = {m["shortName"]: v for m, v in _read_messages(hz)}
    levels = sorted(((m["level"], v) for m, v in _read_messages(vt)), key=lambda x: x[0])
    hhl = np.stack([v for _, v in levels]).astype(np.float32)
    grid = Grid(fields["tlat"].astype(np.float64), fields["tlon"].astype(np.float64), hhl, hhl[-1])
    np.savez_compressed(npz, lat=grid.lat, lon=grid.lon, hhl=grid.hhl, hsurf=grid.hsurf)
    return grid


def message_length(href: str) -> tuple[int, int]:
    """(Länge einer Meldung, Dateigrösse)."""
    r = net.get(href, byte_range=(0, 15))
    total = int(r.headers["Content-Range"].split("/")[1])
    return struct.unpack(">Q", r.content[8:16])[0], total


def fetch_points(href: str, idx: np.ndarray, *, levels: tuple[int, int] | None = None,
                 msg_len: int | None = None) -> dict[int, np.ndarray]:
    """Werte an den Zellen idx.

    Rückgabe: {member: array}. Für Einflächen-Variablen hat array die Form
    (npoints,), für Mehrflächen (nlevels, npoints) mit den Flächen
    levels[0]..levels[1] (1-basiert, von oben nach unten).
    """
    if levels is None:
        data = net.get(href).content
    else:
        if msg_len is None:
            msg_len, _ = message_length(href)
        lo, hi = levels
        data = net.get(href, byte_range=((lo - 1) * msg_len, hi * msg_len - 1)).content
    by_member: dict[int, list[tuple[int, np.ndarray]]] = {}
    for meta, values in _read_messages(data):
        by_member.setdefault(meta["number"], []).append((meta["level"], values[idx]))
    out = {}
    for member, items in by_member.items():
        items.sort(key=lambda x: x[0])
        arr = np.stack([v for _, v in items]).astype(np.float32)
        out[member] = arr[0] if levels is None and len(items) == 1 else arr
    return out
