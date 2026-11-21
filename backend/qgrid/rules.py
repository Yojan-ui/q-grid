"""Natural-language operator rules -> validated JSON constraints -> QUBO penalty terms / hard constraints.

Faculty / estate staff write rules in plain English (rules/*.txt or the UI rule box). A parser turns each rule
into JSON; a pydantic schema plus a bounds guard (zones, jobs, times, levels exist and make sense) accept or
reject it with a reason. Accepted rules compile to:
  tank_min_by  -> soft QUBO term on the pump bit (rule:tank_target) + safety forcing so the target is met
  dg_forbid    -> QUBO penalty on the DG bit (rule:<id>) + safety ban (unless outage, if the rule says so)
  job_window   -> narrower start window for a flexible job (hard)
  fixed_run    -> fixed (critical) load on a weekday window (hard)
The LLM never produces schedules: it only proposes the JSON for a rule. Default parser = offline templates;
the Claude API path runs only when QGRID_USE_LLM=1 (it costs money) and its output passes the same guard.
"""
from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Literal, Union

import numpy as np
from pydantic import BaseModel, Field, ValidationError

from .model import T, Campus, DayData, hhmm_to_slot

ROOT = Path(__file__).resolve().parents[2]
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$|^24:00$"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class TankMinBy(BaseModel):
    type: Literal["tank_min_by"]
    zone: str
    level_frac: float = Field(ge=0.05, le=0.98)
    by_time: str = Field(pattern=HHMM)


class DGForbid(BaseModel):
    type: Literal["dg_forbid"]
    zone: str = "*"
    day_types: list[Literal["teaching", "exam", "vacation", "holiday", "fest"]] = Field(default_factory=list)
    unless_outage: bool = True


class JobWindow(BaseModel):
    type: Literal["job_window"]
    zone: str
    job: str
    earliest: str = Field(pattern=HHMM)
    latest: str = Field(pattern=HHMM)


class FixedRun(BaseModel):
    type: Literal["fixed_run"]
    zone: str
    day: Literal["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    start: str = Field(pattern=HHMM)
    end: str = Field(pattern=HHMM)
    kw: float = Field(gt=0, le=500)
    critical: bool = True
    name: str = ""


RuleSpec = Union[TankMinBy, DGForbid, JobWindow, FixedRun]


class ParsedRules(BaseModel):
    """Schema the LLM must fill (one or more constraints for one sentence)."""
    rules: list[RuleSpec]


class RuleResult(BaseModel):
    text: str
    ok: bool
    reason: str = ""
    rule: dict | None = None
    parser: str = "template"


# ----------------------------------------------------------------------------- parsing
def _time(h: str, m: str | None, ampm: str | None) -> str:
    hh = int(h) % 12 if ampm else int(h)
    if ampm and ampm.lower().startswith("p"):
        hh += 12
    return f"{hh:02d}:{int(m or 0):02d}"


def _zone_from_words(text: str, campus: Campus) -> str | None:
    t = text.lower()
    aliases = {"hostel": "hostels", "lab": "heavy_labs", "library": "library", "canteen": "canteen", "food": "canteen",
               "admin": "admin", "server": "server_room", "health": "health_centre", "medical": "health_centre",
               "academic": "academic", "classroom": "academic", "pump": "pumping_station"}
    for z in campus.names:
        if z.replace("_", " ") in t or z in t:
            return z
    for k, z in aliases.items():
        if k in t and z in campus.names:
            return z
    return None


def template_parse(text: str, campus: Campus) -> dict | None:
    """Offline parser for the supported rule patterns. Returns raw JSON (validated later) or None."""
    t = text.strip().lower()
    tm = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
    m = re.search(r"tanks?.*?(?:above|over|at least|>=?)\s*(\d{1,3})\s*%.*?by\s*" + tm, t)
    if m:
        tank_zone = next((b.name for b in campus.buildings if b.tank), None)
        return {"type": "tank_min_by", "zone": tank_zone or "", "level_frac": int(m.group(1)) / 100,
                "by_time": _time(m.group(2), m.group(3), m.group(4))}
    if re.search(r"\b(no|never|don'?t|forbid|ban)\b.*\b(dg|diesel|generator)", t):
        dts = [d for k, d in (("exam", "exam"), ("vacation", "vacation"), ("fest", "fest"), ("teaching", "teaching"),
                              ("class", "teaching"), ("holiday", "holiday"), ("weekend", "holiday")) if k in t]
        z = _zone_from_words(t.split("dg")[-1] if "dg" in t else t, campus)
        return {"type": "dg_forbid", "zone": z or "*", "day_types": sorted(set(dts)), "unless_outage": "outage" in t}
    m = re.search(r"(.+?)\s+only\s+(after|before|between)\s+" + tm + r"(?:\s*(?:and|-|to)\s*" + tm + ")?", t)
    if m:
        what = m.group(1)
        job = None
        for b in campus.buildings:
            for j in b.flex:
                words = j.name.replace("_", " ").split()
                if all(w in what for w in words[:1]) or j.name.replace("_", " ") in what:
                    job = (b.name, j.name)
        if job is None:
            return {"type": "job_window", "zone": "", "job": what.strip(), "earliest": "00:00", "latest": "23:45"}
        a = _time(m.group(3), m.group(4), m.group(5))
        if m.group(2) == "after":
            e, l = a, "23:45"
        elif m.group(2) == "before":
            e, l = "00:00", a
        else:
            e, l = a, _time(m.group(6), m.group(7), m.group(8)) if m.group(6) else "23:45"
        return {"type": "job_window", "zone": job[0], "job": job[1], "earliest": e, "latest": l}
    m = re.search(r"(.+?)\s+must\s+run\s+(mon|tue|wed|thu|fri|sat|sun)\w*\s+" + tm + r"\s*(?:-|to)\s*" + tm, t)
    if m:
        name = m.group(1).strip()
        start = _time(m.group(3), m.group(4), m.group(5) or m.group(8))
        end = _time(m.group(6), m.group(7), m.group(8))
        kw, zone = None, _zone_from_words(name, campus)
        f = ROOT / "data" / "raw" / "lab_schedule.csv"
        if f.exists():
            import pandas as pd
            sch = pd.read_csv(f, comment="#")
            hit = sch[sch["name"].str.lower().str.contains(name.split(" lab")[0].split()[0], regex=False, na=False)]
            if len(hit):
                kw, zone = float(hit.iloc[0]["kw"]), str(hit.iloc[0]["zone"])
        return {"type": "fixed_run", "zone": zone or "", "day": m.group(2).capitalize(), "start": start, "end": end,
                "kw": kw or 0.0, "critical": True, "name": name}
    return None


def llm_parse(text: str, campus: Campus) -> list[dict]:
    """Claude API structured-output parse (opt-in: QGRID_USE_LLM=1). Returns raw rule dicts; the guard still runs."""
    import anthropic
    zones = {b.name: [j.name for j in b.flex] + (["dg"] if b.dg else []) + (["tank"] if b.tank else [])
             for b in campus.buildings}
    client = anthropic.Anthropic()
    resp = client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=2000,
        system=("Convert one campus-energy operating rule into constraints. Use only these zones and devices: "
                f"{zones}. Times are 24h HH:MM. Never invent zones or devices; never produce a schedule."),
        messages=[{"role": "user", "content": text}],
        output_format=ParsedRules,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        return []
    return [r.model_dump() for r in resp.parsed_output.rules]


# ----------------------------------------------------------------------------- guard
def guard(raw: dict, campus: Campus) -> tuple[bool, str, dict | None]:
    """Schema validation + bounds checks against the actual campus."""
    if not raw:
        return False, "could not understand the rule (no supported pattern matched)", None
    try:
        model = {"tank_min_by": TankMinBy, "dg_forbid": DGForbid, "job_window": JobWindow, "fixed_run": FixedRun}[raw.get("type")]
        r = model(**raw)
    except (KeyError, ValidationError) as e:
        return False, f"schema validation failed: {str(e).splitlines()[0]}", None
    zones = {b.name: b for b in campus.buildings}
    if r.type != "dg_forbid" or r.zone != "*":
        if r.zone not in zones:
            return False, f"unknown zone '{r.zone}' (known: {', '.join(zones)})", None
    if r.type == "tank_min_by":
        b = zones[r.zone]
        if b.tank is None:
            return False, f"zone '{r.zone}' has no water tank", None
        if r.level_frac * b.tank.capacity > b.tank.l_max:
            return False, f"target {r.level_frac:.0%} exceeds the tank's maximum fill", None
    if r.type == "dg_forbid" and r.zone != "*" and zones[r.zone].dg is None:
        return False, f"zone '{r.zone}' has no diesel generator", None
    if r.type == "job_window":
        job = next((j for j in zones[r.zone].flex if j.name == r.job), None)
        if job is None:
            return False, f"zone '{r.zone}' has no flexible load '{r.job}'", None
        e, l = hhmm_to_slot(r.earliest), min(hhmm_to_slot(r.latest), T) - job.slots
        if l < e:
            return False, (f"window {r.earliest}-{r.latest} is shorter than the job's duration "
                           f"({job.slots * 15} min) within one day; widen the window"), None
    if r.type == "fixed_run":
        if hhmm_to_slot(r.end) <= hhmm_to_slot(r.start):
            return False, "end time must be after start time", None
    return True, "", r.model_dump()


def parse_rule(text: str, campus: Campus) -> list[RuleResult]:
    use_llm = os.environ.get("QGRID_USE_LLM") == "1"
    raws, parser = [], "template"
    if use_llm:
        try:
            raws, parser = llm_parse(text, campus), "llm"
        except Exception as e:  # network / auth / refusal -> offline fallback
            raws, parser = [], f"template (LLM failed: {type(e).__name__})"
    if not raws:
        raws = [template_parse(text, campus)]
    out = []
    for raw in raws:
        ok, reason, rule = guard(raw or {}, campus)
        if rule is not None:
            rule["id"] = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]
        out.append(RuleResult(text=text, ok=ok, reason=reason, rule=rule, parser=parser))
    return out


def load_rules(campus: Campus, rules_dir: str | Path | None = None) -> list[RuleResult]:
    d = ROOT / (rules_dir or campus.cfg.get("rules_dir", "rules"))
    res = []
    for f in sorted(Path(d).glob("*.txt")) if Path(d).exists() else []:
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                res += parse_rule(line, campus)
    return res


# ----------------------------------------------------------------------------- compile
def apply_rules(campus: Campus, day: DayData, rules: list[dict]) -> tuple[Campus, DayData, list[dict]]:
    """Return (campus', day', agent_rules) with job windows / fixed runs applied and DG / tank rules compiled."""
    c2, d2 = copy.deepcopy(campus), copy.deepcopy(day)
    agent_rules = []
    dow = DAYS[int(np.datetime64(day.day, "D").astype(object).weekday())] if day.day[:4].isdigit() else None
    for r in rules:
        if r["type"] == "job_window":
            b = c2.buildings[c2.names.index(r["zone"])]
            for j in b.flex:
                if j.name == r["job"]:
                    j.earliest = hhmm_to_slot(r["earliest"])
                    j.latest = min(hhmm_to_slot(r["latest"]), T) - j.slots
                    if not (j.earliest <= j.default <= j.latest):
                        j.default = j.earliest
        elif r["type"] == "fixed_run" and r["day"] == dow:
            i = c2.names.index(r["zone"])
            a, b_ = hhmm_to_slot(r["start"]), hhmm_to_slot(r["end"])
            d2.load[i, a:b_] += r["kw"]
            if r.get("critical", True):
                d2.crit[i, a:b_] += r["kw"]
        elif r["type"] == "dg_forbid":
            if not r["day_types"] or day.day_type in r["day_types"]:
                agent_rules.append({"type": "dg_forbid", "zone": r["zone"], "unless_outage": r["unless_outage"], "id": r["id"]})
        elif r["type"] == "tank_min_by":
            agent_rules.append({"type": "tank_min_by", "zone": r["zone"], "level_frac": r["level_frac"],
                                "by_slot": hhmm_to_slot(r["by_time"]), "id": r["id"]})
    return c2, d2, agent_rules
