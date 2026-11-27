"""RVCE campus rescale: turn the OSM layout (qgrid/campus.py build_layout) into the campus the team brief describes.

Pure functions on plain dicts (no I/O), so qgrid/campus.py, qgrid/datasets.py and the tests can all call them.

  rescale_layout(cfg, layout)  -> new layout dict
      1. drops the OSM buildings listed in campus.osm_exclude (not RVCE's own buildings, e.g. RV University blocks)
         and recomputes each zone's footprint, floor area and centroid;
      2. floor areas: the hostels zone gets campus.facts.boys_hostels_m2; every other OSM-mapped zone is scaled by one
         common factor so that their floor areas sum to campus.facts.built_up_m2 (minus the hostels when
         built_up_includes_hostels is true); virtual zones (not in OSM) keep their config floor area;
      3. PV: campus.pv_existing.total_kwp (21 roofs, 1,564 x 320 Wp) is spread over the zones in proportion to
         footprint x pv_roof (ASSUMPTION: which 21 roofs carry the modules is not known);
      records what it did under layout["rescale"]; calling it again on its own output returns it unchanged.
  apply_dg_sets(cfg)           -> cfg copy whose zone `dg` entries come from campus.dg_sets (kW = kVA x rated_pf)
  asset_status(cfg)            -> {asset type: EXISTING | PROPOSED}
Figures come from the team brief ("team brief, RVCE estate data pending"); see docs/data_verification.md.
"""
from __future__ import annotations

import copy


def enabled(cfg: dict) -> bool:
    return bool(cfg.get("campus", {}).get("rescale", {}).get("enabled", False))


def pv_total_kwp(cfg: dict) -> float:
    pe = cfg["campus"]["pv_existing"]
    return float(pe["total_kwp"])


def asset_status(cfg: dict) -> dict:
    return dict(cfg["campus"]["asset_status"])


def excluded_ids(cfg: dict) -> set[str]:
    return {str(e["osm_id"]) for e in cfg["campus"].get("osm_exclude", [])}


def _recompute_zone(zz: dict, keep: list[dict]) -> dict:
    out = dict(zz)
    out["buildings"] = keep
    if zz.get("source") != "osm":
        return out
    fp = sum(b["area_m2"] for b in keep)
    out["footprint_m2"] = fp
    out["floor_m2"] = sum(b["area_m2"] * b["levels"] for b in keep)
    if fp > 0:
        cx = cy = 0.0
        for b in keep:
            poly = b["polygon"]
            cx += b["area_m2"] * sum(p[0] for p in poly) / len(poly)
            cy += b["area_m2"] * sum(p[1] for p in poly) / len(poly)
        out["cx"], out["cy"] = cx / fp, cy / fp
    return out


def rescale_layout(cfg: dict, layout: dict) -> dict:
    if "rescale" in layout:
        return layout
    cc = cfg["campus"]
    facts, pe = cc["facts"], cc["pv_existing"]
    hostel_zone = facts.get("hostel_zone", "hostels")
    excl = excluded_ids(cfg)
    out = copy.deepcopy(layout)
    removed = []
    zones = {}
    for z, zz in out["zones"].items():
        keep = [b for b in zz.get("buildings", []) if b["osm_id"] not in excl]
        removed += [{"zone": z, "osm_id": b["osm_id"], "name": b.get("name"), "area_m2": b["area_m2"]}
                    for b in zz.get("buildings", []) if b["osm_id"] in excl]
        zones[z] = _recompute_zone(zz, keep)

    hostels_m2 = float(facts["boys_hostels_m2"])
    built_up = float(facts["built_up_m2"])
    target_other = built_up - hostels_m2 if facts.get("built_up_includes_hostels", False) else built_up
    others = [z for z, zz in zones.items() if z != hostel_zone and zz.get("source") == "osm"]
    osm_other = sum(zones[z]["floor_m2"] for z in others)
    k = target_other / osm_other if osm_other > 0 else 1.0
    floor_before = {z: round(zz["floor_m2"], 1) for z, zz in zones.items()}
    for z in others:
        zones[z]["floor_m2"] *= k
    if hostel_zone in zones:
        zones[hostel_zone]["floor_m2"] = hostels_m2

    total_kwp = float(pe["total_kwp"])
    w = {z: zz["footprint_m2"] * float(cc["zones"][z].get("pv_roof", 1.0)) for z, zz in zones.items()}
    wsum = sum(w.values())
    for z, zz in zones.items():
        zz["pv_kwp_osm_roof"] = zz.get("pv_kwp")
        zz["pv_kwp"] = total_kwp * w[z] / wsum if wsum > 0 else 0.0

    out["zones"] = zones
    out["rescale"] = {
        "source": facts.get("source", "team brief, RVCE estate data pending"),
        "removed_buildings": removed,
        "floor_scale_non_hostel": k,
        "floor_m2_after_exclusion": floor_before,
        "built_up_m2": built_up, "built_up_includes_hostels": bool(facts.get("built_up_includes_hostels", False)),
        "boys_hostels_m2": hostels_m2, "boys_hostel_beds": int(facts["boys_hostel_beds"]),
        "pv_total_kwp": total_kwp, "pv_modules": int(pe["modules"]), "pv_module_wp": float(pe["module_wp"]),
        "pv_roofs": int(pe["roofs"]), "pv_allocation": pe.get("allocation", "footprint_x_pv_roof (ASSUMPTION)"),
        "dg_sets": cc.get("dg_sets", {}), "asset_status": dict(cc.get("asset_status", {})),
    }
    return out


def dg_kw(cfg: dict) -> dict[str, float]:
    """Host zone -> DG kW from campus.dg_sets (kVA x rated_pf; sets with the same host add up)."""
    ds = cfg["campus"]["dg_sets"]
    pf = float(ds["rated_pf"])
    out: dict[str, float] = {}
    for s in ds["sets"]:
        out[s["host"]] = out.get(s["host"], 0.0) + float(s["kva"]) * pf
    return out


def apply_dg_sets(cfg: dict) -> dict:
    """cfg copy where the zone `dg` entries are exactly the campus.dg_sets hosts (other zones lose their DG).
    Operating parameters (min_load_frac, min_on_slots) come from dg_sets.operating."""
    c = copy.deepcopy(cfg)
    ds = c["campus"]["dg_sets"]
    op = ds.get("operating", {"min_load_frac": 0.3, "min_on_slots": 4})
    kw = dg_kw(c)
    for z, spec in c["campus"]["zones"].items():
        if z in kw:
            spec["dg"] = {"kw": kw[z], **op}
        else:
            spec.pop("dg", None)
    return c
