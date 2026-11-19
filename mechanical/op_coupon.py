# SPDX-License-Identifier: CERN-OHL-P-2.0
"""Dock insert variant set + pod-less fit-test fixture (spec 8a).

The cannula-specific geometry lives in the swappable DOCK INSERT (op_dock.build_insert).  This module builds
  * the variant set of inserts (parameter sweep over cannula.A_dome_d x cannula.N_hook_h, 12 variants, embossed ID 1..12),
  * the dock FIXTURE: a small plate carrying exactly the frozen pod-side interface (window, ledge, detent bumps), so the
    inserts can be fitted against a real cannula head without a pod.
All parts are generated in the pod frame with x_r1 = 0 (identical for OP-70/100/200: the insert only depends on u = x - x_r1).
"""
from __future__ import annotations

import copy

from op_cmds import Script
from op_dock import build_insert, build_pod_dock_interface, dock_geometry

A_STEPS = (-0.3, -0.1, 0.1, 0.3)       # dome diameter offsets (mm) around the placeholder
N_STEPS = (-0.3, 0.0, 0.3)             # hook height offsets (mm)


def variants(p: dict) -> list[dict]:
    a0, h0 = p["cannula"]["A_dome_d"], p["cannula"]["N_hook_h"]
    out, i = [], 0
    for dn in N_STEPS:
        for da in A_STEPS:
            i += 1
            out.append({"id": i, "A_dome_d": round(a0 + da, 3), "N_hook_h": round(h0 + dn, 3)})
    return out


def variant_params(p: dict, v: dict) -> dict:
    q = copy.deepcopy(p)
    q["cannula"]["A_dome_d"], q["cannula"]["N_hook_h"] = v["A_dome_d"], v["N_hook_h"]
    return q


def pod_frame(p: dict, x_r1: float = 0.0, length: float | None = None) -> dict:
    """Minimal layout dict for build_insert / build_pod_dock_interface in the pod frame."""
    F = p["dock_interface_frozen"]
    return {"x_r1": x_r1, "wall": p["shell"]["wall"] + (p["pod"]["dock"]["floor_pad"] if p.get("v010_pod") else 0.0), "length": x_r1 + F["tail_u"] if length is None else length, "mode": "bench"}


def add_variant_inserts(s: Script, p: dict, vs: list[dict], x_r1: float = 0.0, length: float | None = None,
                        prefix: str = "dock_insert_v") -> dict[int, dict]:
    """Append one insert body per variant (named prefix + 2-digit id); returns the dock geometry per variant."""
    geo = {}
    for v in vs:
        q = variant_params(p, v)
        L = pod_frame(p, x_r1, length)
        L["dock"] = dock_geometry(q, x_r1, L["wall"])
        build_insert(s, q, L, f"{prefix}{v['id']:02d}", vid=v["id"])
        geo[v["id"]] = L["dock"]
    return geo


def build_fixture(s: Script, p: dict) -> None:
    """Plate with the frozen window/ledge/detent interface; the pod's rear dock face is the plate's -X edge."""
    F = p["dock_interface_frozen"]
    L = pod_frame(p)
    L["dock"] = dock_geometry(p, 0.0, L["wall"])
    yc = L["dock"]["y_c"]
    wall, x0 = L["wall"], F["x0_u"]
    ym = F["pocket_half"] + 3.0
    s.box("dock_fixture", (x0 - 2.0, L["length"]), (yc - ym, yc + ym), (0, wall))
    bumps, cuts = build_pod_dock_interface(s, p, L)
    s.cut("dock_fixture", cuts)
    s.join("dock_fixture", bumps)
    # rear stop wall (the pod's end-cap block face) so the insert's front face has the same datum as in the pod
    s.join("dock_fixture", [s.box("t_fx_wall", (x0 - 2.0, x0 - 0.0), (yc - ym, yc + ym), (wall - 0.1, wall + 2.0))])
