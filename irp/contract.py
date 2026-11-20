"""Strict inert JSON contract for CODED-generated iRp™ fictional worlds.

The model is untrusted. This module does not interpret scripts, URLs or arbitrary actions.
"""
import json
import math
import re

SCHEMA = "innovulis.irp.blueprint.v1"
SECTORS = {"habitat", "energy", "health", "agriculture", "transport", "civic"}
THEMES = {"ocean", "forest", "desert", "night"}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
MAX_BYTES = 16384


class BlueprintRejected(ValueError):
    pass


def _check(ok, reason):
    if not ok:
        raise BlueprintRejected("IRP_BLUEPRINT_INVALID:" + reason)


def _keys(obj, names, reason):
    _check(type(obj) is dict and set(obj) == set(names), reason + "_KEYS")


def _string(value, lo, hi, reason):
    _check(type(value) is str and lo <= len(value) <= hi and
           value == value.strip() and
           all(ord(c) >= 32 and ord(c) != 127 for c in value), reason + "_TEXT")
    return value


def _number(value, lo, hi, reason):
    _check(type(value) in (float, int) and math.isfinite(value) and lo <= value <= hi, reason + "_RANGE")
    return value


def validate_blueprint(value):
    _keys(value, ("schema", "title", "summary", "theme", "districts", "plan"), "ROOT")
    _check(value["schema"] == SCHEMA, "SCHEMA")
    title = _string(value["title"], 3, 80, "TITLE")
    summary = _string(value["summary"], 3, 240, "SUMMARY")
    theme = value["theme"]
    _check(type(theme) is str and theme in THEMES, "THEME")
    raw_districts = value["districts"]
    _check(type(raw_districts) is list and 3 <= len(raw_districts) <= 12, "DISTRICTS")
    districts = []
    seen = set()
    for raw in raw_districts:
        _keys(raw, ("id", "name", "sector", "x", "y", "height"), "DISTRICT")
        name = _string(raw["name"], 2, 48, "DISTRICT_NAME")
        ident = raw["id"]
        _check(type(ident) is str and IDENTIFIER.fullmatch(ident) is not None, "DISTRICT_ID")
        _check(ident not in seen, "DISTRICT_DUPLICATE")
        seen.add(ident)
        sector = raw["sector"]
        _check(type(sector) is str and sector in SECTORS, "SECTOR")
        x = _number(raw["x"], 8, 92, "X")
        y = _number(raw["y"], 8, 92, "Y")
        height = raw["height"]
        _check(type(height) is int and 1 <= height <= 5, "HEIGHT")
        districts.append(dict(id=ident, name=name, sector=sector, x=x, y=y, height=height))
    plan = value["plan"]
    _keys(plan, ("aid_units", "diplomacy", "communications_disrupted"), "PLAN")
    aid = plan["aid_units"]
    _check(type(aid) is int and 0 <= aid <= 100, "AID")
    diplomacy = _number(plan["diplomacy"], 0, 1, "DIPLOMACY")
    disruption = plan["communications_disrupted"]
    _check(type(disruption) is bool, "DISRUPTION")
    clean = dict(schema=SCHEMA, title=title, summary=summary, theme=theme, districts=districts,
                 plan=dict(aid_units=aid, diplomacy=diplomacy, communications_disrupted=disruption))
    _check(len(json.dumps(clean, ensure_ascii=False, allow_nan=False).encode("utf-8")) <= MAX_BYTES, "SIZE")
    return clean


def safe_json_loads(text):
    """Reject NaN and Infinity, which json.loads otherwise accepts by default."""
    return json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(BlueprintRejected("NONFINITE_VALUE")))
