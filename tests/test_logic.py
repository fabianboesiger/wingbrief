"""Tests für Profile, Geometrie, Aggregation und SHV-Ampellogik sowie synthetische Föhn-/Bise-Fälle."""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from wingbrief import engine, vertical
from wingbrief.checks import base, foehn, wind
from wingbrief.checks.base import ACHTUNG, ALARM, GUENSTIG, JA, KEINE, NEIN, NEUTRAL, UNSICHER, Entry
from wingbrief.extract import ML_LEVELS, Bundle, load_units

T0 = datetime(2026, 11, 15, 6, tzinfo=timezone.utc)


# ------------------------------------------------------------- vertical
def test_at_height_and_wind():
    z = np.array([3000.0, 2000.0, 1000.0])
    v = np.array([-10.0, 0.0, 10.0])
    assert vertical.at_height(z, v, 1500) == pytest.approx(5.0)
    assert np.isnan(vertical.at_height(z, v, 500))
    sp, d = vertical.wind(0.0, -10.0)  # Wind nach Süden = aus Norden
    assert sp == pytest.approx(36.0)
    assert d == pytest.approx(0.0)
    sp, d = vertical.wind(-10.0, 0.0)  # nach Westen = aus Osten
    assert d == pytest.approx(90.0)


def test_theta_e_reasonable():
    # warm-feuchte Sommerluft: 20 °C, 12 g/kg auf 850 hPa -> deutlich über 60 °C
    te = vertical.theta_e(293.15, 0.012, 85000) - 273.15
    assert 60 < te < 80
    # kalte, trockene Luft
    assert vertical.theta_e(268.15, 0.002, 85000) - 273.15 < 25


def test_inversions_and_lapse():
    z = np.array([3000.0, 2500.0, 2000.0, 1500.0, 1000.0, 500.0])
    t = np.array([-8.0, -5.0, -1.0, 2.0, 0.0, 3.0]) + 273.15  # Inversion 1000→1500 m
    inv = vertical.inversions(z, t, 400)
    assert inv and inv[0]["base"] == 1000.0 and inv[0]["strength"] == pytest.approx(2.0)
    assert vertical.lapse_rate(z, t, 2000, 3000) == pytest.approx(0.7)


def test_direction_helpers():
    assert base.in_dir(350, 315, 45)
    assert base.in_dir(10, 315, 45)
    assert not base.in_dir(100, 315, 45)
    assert vertical.angle_diff(350, 10) == pytest.approx(20)
    assert base.bearing((46.0, 8.0), (47.0, 8.0)) == pytest.approx(0, abs=0.5)


# --------------------------------------------------------- Aggregation
def _e(status, ens=None):
    return Entry(T0, status, "", ens)


def test_aggregate_alarm_wins():
    st, _, _ = engine.aggregate([_e(NEUTRAL), _e(ALARM), _e(ACHTUNG)], "alarm", False)
    assert st == ALARM


def test_aggregate_guenstig_needs_all():
    assert engine.aggregate([_e(GUENSTIG), _e(GUENSTIG)], "guenstig", False)[0] == GUENSTIG
    assert engine.aggregate([_e(GUENSTIG), _e(NEUTRAL)], "guenstig", False)[0] == NEUTRAL


def test_aggregate_ensemble_thresholds():
    assert engine.aggregate([_e(NEUTRAL, (0.35, 0.65))], "alarm", True)[0] == ALARM
    assert engine.aggregate([_e(NEUTRAL, (0.1, 0.9))], "alarm", True)[0] == NEUTRAL
    assert engine.aggregate([_e(NEUTRAL, (0.2, 0.6))], "alarm", True)[0] == UNSICHER


def test_aggregate_faktor():
    assert engine.aggregate([_e(NEIN), _e(JA)], "faktor", False)[0] == JA
    assert engine.aggregate([], "faktor", False)[0] == KEINE


def test_phenomenon_level_shv_logic():
    cat = engine.load_catalog()
    # Föhn: O4 Alarm -> Alarm
    assert engine.phenomenon_level({"O4": ALARM, "OG": NEUTRAL}, cat, "foehn") == ALARM
    # alle günstigen Zeichen erfüllt, keine Alarmzeichen -> ok
    sts = {c: NEUTRAL for c, v in cat["checks"].items() if v["phenomenon"] == "foehn" and v["kind"] == "alarm"}
    sts["OG"] = GUENSTIG
    assert engine.phenomenon_level(sts, cat, "foehn") == "ok"
    # keine Alarmzeichen, aber günstiges Zeichen fehlt -> Achtung
    sts["OG"] = NEUTRAL
    assert engine.phenomenon_level(sts, cat, "foehn") == ACHTUNG
    # Näherung (W4) hebt nur auf Achtung
    g = {c: NEUTRAL for c, v in cat["checks"].items() if v["phenomenon"] == "gewitter"}
    g["W4"] = ALARM
    g["WG"] = GUENSTIG
    assert engine.phenomenon_level(g, cat, "gewitter") == ACHTUNG


def test_catalog_complete():
    cat = engine.load_catalog()
    implemented = set()
    for m in engine.MODULES.values():
        implemented |= set(m.CHECKS)
    for cid, c in cat["checks"].items():
        assert c["data"] in "ATL"
        assert c["kind"] in ("alarm", "guenstig", "faktor")
        if c["data"] in "AT":
            assert cid in implemented, f"{cid} ist im Katalog, aber nicht implementiert"
        else:
            assert cid in engine.PROXY or c.get("links"), f"{cid}: L-Check ohne Link"
    assert implemented <= set(cat["checks"])


# ----------------------------------------------- synthetische Bündel
def _bundle(pmsl_south=1015.0, pmsl_north=1010.0, t_north=2.0, t_south=-1.0,
            u=0.0, v=0.0, n_ml=3) -> Bundle:
    units = load_units()
    names = []
    for rid, r in units["regions"].items():
        names += [f"{rid}.{k}" for k in r["points"]]
    for vid, vv in units["valleys"].items():
        names += [f"{vid}.{i}" for i in range(len(vv["axis"]))]
    for pid in units["passes"]:
        names += [f"pass.{pid}.{k}" for k in ("crest", "north", "south")]
    names += [f"st.{a}" for a in units["pressure_stations"].values()]
    points = {n: (46.5, 8.5) for n in names}
    npts = len(names)
    steps = {"sfc": list(range(0, 13)), "ml": list(range(0, n_ml)), "ens": [], "ens_valid": []}
    b = Bundle(run=T0, today=date(2026, 11, 15), points=points,
               pindex={n: i for i, n in enumerate(names)}, steps=steps)
    nlev = ML_LEVELS[1] - ML_LEVELS[0] + 1
    z = np.linspace(6000, 300, nlev)
    b.hfl = np.repeat(z[:, None], npts, axis=1)
    b.hsurf = np.full(npts, 250.0)
    pm = np.full((13, npts), 101300.0, np.float32)
    pm[:, b.pindex["st.LUG"]] = pmsl_south * 100
    pm[:, b.pindex["st.SMA"]] = pmsl_north * 100
    b.sfc = {"PMSL": pm}
    temp = np.repeat((15 - 0.0065 * z + 273.15)[:, None], npts, axis=1)
    for pid in units["passes"]:
        temp[:, b.pindex[f"pass.{pid}.north"]] += t_north - (15 - 0.0065 * 2000)
        temp[:, b.pindex[f"pass.{pid}.south"]] += t_south - (15 - 0.0065 * 2000)
    b.ml = {
        "T": np.repeat(temp[None], n_ml, axis=0).astype(np.float32),
        "U": np.full((n_ml, nlev, npts), u, np.float32),
        "V": np.full((n_ml, nlev, npts), v, np.float32),
        "QV": np.full((n_ml, nlev, npts), 0.004, np.float32),
        "P": np.repeat(np.linspace(47000, 98000, nlev)[None, :, None], n_ml, axis=0).repeat(npts, axis=2).astype(np.float32),
    }
    return b


def _ctx(b, unit, kind="valley"):
    return base.Ctx(b, load_units(), engine.load_catalog(), {"wind": {}, "tamp": {}}, unit, kind)


def test_foehn_day_reusstal():
    """Föhntag (wie 15.11.2026): Südüberdruck 6 hPa, Luv 3 °C kühler -> Alarm im Reusstal."""
    b = _bundle(pmsl_south=1016, pmsl_north=1010, t_north=2.0, t_south=-1.0)
    ctx = _ctx(b, "reusstal")
    o4 = foehn.O4(ctx)
    assert {e.status for e in o4.entries} == {ALARM}
    o7 = foehn.O7(ctx)
    assert {e.status for e in o7.entries} == {ALARM}
    # Leventina liegt im Luv -> keine Alarmzeichen, günstig
    ctx_s = _ctx(b, "leventina")
    assert {e.status for e in foehn.O4(ctx_s).entries} == {NEUTRAL}
    assert {e.status for e in foehn.OG(ctx_s).entries} == {GUENSTIG}


def test_foehn_warn_threshold():
    b = _bundle(pmsl_south=1013.3, pmsl_north=1010.0, t_north=1.4, t_south=0.0)
    ctx = _ctx(b, "reusstal")
    assert {e.status for e in foehn.O4(ctx).entries} == {ACHTUNG}
    assert {e.status for e in foehn.O7(ctx).entries} == {ACHTUNG}


def test_bise_day_wind():
    """Hochdrucktag mit schwacher Bise (wie 14.11.2026): 10 km/h aus NE -> kein Alarm, kein Föhn."""
    # 10 km/h aus 45° (u, v positiv nach Osten/Norden; Wind aus NE weht nach SW)
    spd = 10 / 3.6
    u = v = -spd / np.sqrt(2)
    b = _bundle(pmsl_south=1024, pmsl_north=1025, t_north=1.0, t_south=1.0, u=u, v=v)
    ctx = _ctx(b, "westmittelland", kind="region")
    u2 = wind.U2(ctx)
    assert {e.status for e in u2.entries} == {NEUTRAL}
    assert "km/h" in u2.entries[0].value
    ctx_v = _ctx(b, "reusstal")
    assert {e.status for e in foehn.O4(ctx_v).entries} == {NEUTRAL}
    assert {e.status for e in foehn.OG(ctx_v).entries} == {GUENSTIG}


def test_strong_wind_alarm():
    b = _bundle(u=10.0, v=0.0)  # 36 km/h aus Westen
    ctx = _ctx(b, "jura", kind="region")
    assert {e.status for e in wind.U2(ctx).entries} == {ALARM}
