#!/usr/bin/env python3
"""Resolve every Cura setting (defaults + formulas) for one machine and print CuraEngine '-s key=value' args.

CuraEngine on the command line only reads `default_value`; the `value` formulas are normally evaluated by the Cura
frontend. This script evaluates them the same way (single extruder) so CuraEngine gets a complete, consistent set.

usage: cura_resolve.py <resources dir> <machine def id> <extruder def id> <overrides.json>
writes one argument per line (NUL-free) to stdout: key=value
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def load_chain(res: Path, def_id: str) -> list[dict]:
    """Definition and all its parents, child first."""
    chain = []
    while def_id:
        p = res / "definitions" / f"{def_id}.def.json"
        if not p.exists():
            p = res / "extruders" / f"{def_id}.def.json"
        d = json.loads(p.read_text())
        chain.append(d)
        def_id = d.get("inherits")
    return chain


def flatten(settings: dict, out: dict) -> None:
    for key, s in settings.items():
        out[key] = s
        if "children" in s:
            flatten(s["children"], out)


def collect(res: Path, machine: str, extruder: str) -> tuple[dict, dict]:
    """Return (setting specs, layered raw values: default_value or '=formula')."""
    specs: dict = {}
    chain = load_chain(res, machine)
    flatten(chain[-1]["settings"], specs)  # fdmprinter holds every setting
    raw: dict = {}
    for key, s in specs.items():
        if "value" in s:
            raw[key] = "=" + str(s["value"])
        elif "default_value" in s:
            raw[key] = s["default_value"]
    for d in reversed(load_chain(res, extruder)[:-1]) if extruder else []:
        apply_overrides(raw, d.get("overrides", {}))
    for d in reversed(chain[:-1]):  # parents first, machine last
        apply_overrides(raw, d.get("overrides", {}))
    return specs, raw


def apply_overrides(raw: dict, overrides: dict) -> None:
    for key, o in overrides.items():
        if "value" in o:
            raw[key] = "=" + str(o["value"])
        elif "default_value" in o:
            raw[key] = o["default_value"]


def evaluate(specs: dict, raw: dict) -> dict:
    vals: dict = {}

    def get(k):
        if k in vals:
            return vals[k]
        v = raw.get(k)
        if isinstance(v, str) and v.startswith("="):
            vals[k] = None  # cycle guard
            vals[k] = ev(v[1:])
            return vals[k]
        vals[k] = coerce(specs.get(k, {}), v)
        return vals[k]

    class Env(dict):
        def __missing__(self, k):
            if k in raw or k in specs:
                return get(k)
            raise KeyError(k)

    helpers = {
        "math": math, "max": max, "min": min, "round": round, "int": int, "float": float, "abs": abs, "sum": sum,
        "len": len, "any": any, "all": all, "map": map, "list": list, "str": str, "bool": bool, "sorted": sorted,
        "True": True, "False": False, "None": None,
        "extruderValue": lambda e, k: get(k), "extruderValues": lambda k: [get(k)], "resolveOrValue": lambda k: get(k),
        "defaultExtruderPosition": lambda: "0", "anyExtruderWithMaterial": lambda k: "0",
        "anyExtruderNrWithOrDefault": lambda k: "0", "valueFromContainer": lambda i: None,
        "extruderValueFromContainer": lambda e, k, i: get(k), "variantValueFromContainer": lambda k: get(k),
    }

    def ev(expr: str):
        env = Env(helpers)
        try:
            return eval(expr, {"__builtins__": {}}, env)  # noqa: S307 - Cura's own definition formulas
        except Exception:  # noqa: BLE001 - unresolvable frontend-only formulas fall back to the default
            return None

    for k in specs:
        get(k)
    for k, s in specs.items():  # fall back to default_value where a formula could not be evaluated
        if vals.get(k) is None and "default_value" in s:
            vals[k] = s["default_value"]
    return vals


def coerce(spec: dict, v):
    t = spec.get("type")
    try:
        if t == "float":
            return float(v)
        if t == "int":
            return int(float(v))
        if t == "bool":
            return v if isinstance(v, bool) else str(v).lower() == "true"
    except (TypeError, ValueError):
        return v
    return v


def fmt(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return str(v)


def main() -> int:
    res, machine, extruder, ov_path = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
    specs, raw = collect(res, machine, extruder)
    raw.update(json.loads(ov_path.read_text()))
    vals = evaluate(specs, raw)
    missing = [k for k, s in specs.items() if s.get("type") not in ("category", None) and vals.get(k) is None]
    for k, v in vals.items():
        if v is None or specs.get(k, {}).get("type") == "category":
            continue
        sys.stdout.write(f"{k}={fmt(v)}\0")
    print(f"resolved {len(vals)} settings, unresolved {len(missing)}: {missing[:12]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
