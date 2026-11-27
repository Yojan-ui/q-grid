"""RVCE campus rescale (qgrid/v2/campus_scale.py, config.yaml campus.*): 500.48 kWp over 21 roofs, built-up and hostel
floor areas, RVCE-only OSM buildings, 980 kVA of DG in two sets, PROPOSED labels for batteries / EV / cables.
Figures are from the team brief (RVCE estate data pending)."""
import json

import pytest

from qgrid import data as qd
from qgrid.model import load_campus
from qgrid.v2 import campus_scale as cs


@pytest.fixture(scope="module")
def cfg():
    return qd.load_config()


@pytest.fixture(scope="module")
def layout0():
    return json.loads((qd.PROC / "campus.json").read_text())


def test_pv_existing(cfg):
    pe = cfg["campus"]["pv_existing"]
    assert pe["modules"] == 1564 and pe["module_wp"] == 320 and pe["roofs"] == 21
    assert pe["modules"] * pe["module_wp"] / 1000 == pytest.approx(500.48)
    assert cs.pv_total_kwp(cfg) == pytest.approx(500.48)


def test_hostels_and_built_up(cfg):
    f = cfg["campus"]["facts"]
    assert f["boys_hostels_m2"] == 38659 and f["boys_hostel_beds"] == 1450
    assert f["built_up_m2"] == 67721


def test_dg_sets(cfg):
    ds = cfg["campus"]["dg_sets"]
    assert len(ds["sets"]) == 2
    assert sum(s["kva"] for s in ds["sets"]) == ds["total_kva"] == 980
    zones = cfg["campus"]["zones"]
    for s in ds["sets"]:
        assert s["host"] in zones and set(s["backs"]) <= set(zones) and s["host"] in s["backs"]
    # the zone dg entries load_campus() reads agree with the sets (kW = kVA x rated pf)
    kw = cs.dg_kw(cfg)
    assert {z for z, s in zones.items() if "dg" in s} == set(kw)
    for z, v in kw.items():
        assert zones[z]["dg"]["kw"] == pytest.approx(v)
    assert sum(kw.values()) == pytest.approx(980 * ds["rated_pf"])
    # moving a set to another zone moves the modelled DG
    c2 = json.loads(json.dumps(cfg))
    c2["campus"]["dg_sets"]["sets"][1]["host"] = "server_room"
    z2 = cs.apply_dg_sets(c2)["campus"]["zones"]
    assert "dg" not in z2["admin"] and z2["server_room"]["dg"]["kw"] == pytest.approx(490 * ds["rated_pf"])


def test_asset_status_proposed(cfg):
    st = cs.asset_status(cfg)
    assert st["battery"] == "PROPOSED" and st["ev"] == "PROPOSED" and st["cables"] == "PROPOSED"
    assert st["pv"] == "EXISTING" and st["dg"] == "EXISTING"


def test_rescale_layout(cfg, layout0):
    lay = cs.rescale_layout(cfg, layout0)
    z = lay["zones"]
    assert sum(v["pv_kwp"] for v in z.values()) == pytest.approx(500.48)
    assert z["pumping_station"]["pv_kwp"] == 0.0                     # pv_roof 0
    assert z["hostels"]["floor_m2"] == pytest.approx(38659)
    other = sum(v["floor_m2"] for k, v in z.items() if k != "hostels" and v.get("source") == "osm")
    assert other == pytest.approx(67721)                              # built_up_includes_hostels: false
    excl = cs.excluded_ids(cfg)
    assert excl and not any(b["osm_id"] in excl for v in z.values() for b in v["buildings"])
    assert {r["osm_id"] for r in lay["rescale"]["removed_buildings"]} == excl
    assert all("RVU" not in (b.get("name") or "") for v in z.values() for b in v["buildings"])
    assert cs.rescale_layout(cfg, lay) is lay                         # idempotent
    assert layout0.get("rescale") is None                             # input untouched
    c = load_campus(cs.apply_dg_sets(cfg), lay)
    assert sum(b.pv_kwp for b in c.buildings) == pytest.approx(500.48)
    assert sum(b.dg.kw for b in c.buildings if b.dg) == pytest.approx(980 * cfg["campus"]["dg_sets"]["rated_pf"])


def test_rescale_hostels_included_option(cfg, layout0):
    c2 = json.loads(json.dumps(cfg))
    c2["campus"]["facts"]["built_up_includes_hostels"] = True
    z = cs.rescale_layout(c2, layout0)["zones"]
    total = sum(v["floor_m2"] for v in z.values() if v.get("source") == "osm")
    assert total == pytest.approx(67721)


def test_dataset_rvce_rescaled(cfg):
    if not (qd.PROC / "pv.parquet").exists():
        pytest.skip("processed data not built (python scripts/fetch_data.py && make data); raw data is not in git")
    from qgrid import bdg2, datasets
    if cfg.get("loads", {}).get("source") == "bdg2" and not bdg2.available():
        pytest.skip("BDG2 raw files not present")
    campus, proc = datasets.build("rvce")
    assert sum(b.pv_kwp for b in campus.buildings) == pytest.approx(500.48)
    assert proc["meta"]["campus_rescale"]["boys_hostel_beds"] == 1450
    # PV series follow the new kWp exactly: annual yield per kWp is the same in every zone with PV
    y = {b.name: proc["pv"][b.name].sum() / b.pv_kwp for b in campus.buildings if b.pv_kwp > 0}
    assert max(y.values()) == pytest.approx(min(y.values()), rel=1e-9)
    floors = {z: v["floor_m2"] for z, v in proc["campus"]["zones"].items()}
    assert floors["hostels"] == pytest.approx(38659)
