"""Dock fit-test coupon: a flat strip with 6 variants of the slide-on dock channel + snap arms, NO needle.

Each cell = the real dock geometry (end block, guard tube, floor opening, two snap arms with hooks) of one parameter set,
on a 0.9 mm base plate that is open at the +X end (the dome slides in from there).  Variants vary the dome diameter
cannula.A_dome_d and the hook height cannula.N_hook_h in 0.15 mm steps around the placeholders.  The ID digit (1..6) is
engraved with a 7-segment pattern.  Used with a real cannula head to check slide / latch / release before ordering pods.
"""
from __future__ import annotations

import copy

from op_cmds import Script
from op_dock import build_dock_cuts, build_dock_joins, dock_geometry

STEP = 0.15
CELL_Y = 17.5          # pitch of the cells along Y
CELL_X = 19.0
SEG = {  # 7-segment digits: a,b,c,d,e,f,g
    1: "bc", 2: "abdeg", 3: "abcdg", 4: "bcfg", 5: "acdfg", 6: "acdefg"}


def variants(p: dict) -> list[dict]:
    a0, h0 = p["cannula"]["A_dome_d"], p["cannula"]["N_hook_h"]
    out = []
    for i, (da, dh) in enumerate([(-1, -1), (0, -1), (1, -1), (-1, 1), (0, 1), (1, 1)]):
        out.append({"id": i + 1, "A_dome_d": round(a0 + da * STEP, 3), "N_hook_h": round(h0 + dh * STEP, 3)})
    return out


def _scope(cmds: list[dict], suffix: str) -> list[dict]:
    """Make every body name unique per cell (names are global in a script)."""
    names = set()
    for c in cmds:
        for k in ("body_name", "name"):
            if isinstance(c["params"].get(k), str) and c["command"].startswith("solid."):
                names.add(c["params"][k])
    out = []
    for c in copy.deepcopy(cmds):
        pr = c["params"]
        for k in ("body_name", "name", "target"):
            if isinstance(pr.get(k), str) and pr[k] in names:
                pr[k] = pr[k] + suffix
        for k in ("tools", "bodies"):
            if isinstance(pr.get(k), list):
                pr[k] = [x + suffix if x in names else x for x in pr[k]]
        out.append(c)
    return out


def build_coupon(p: dict) -> tuple[Script, list[dict]]:
    vs = variants(p)
    s = Script()
    wall = p["shell"]["wall"]
    plate_t = wall
    ny = len(vs)
    s.box("coupon", (0, CELL_X), (0, CELL_Y * ny), (0, plate_t))
    for i, v in enumerate(vs):
        q = copy.deepcopy(p)
        q["cannula"]["A_dome_d"], q["cannula"]["N_hook_h"] = v["A_dome_d"], v["N_hook_h"]
        xr = 0.4
        yc = CELL_Y * i + CELL_Y / 2
        q["dock"]["y_c"] = yc
        L = {"x_r1": xr, "wall": wall, "length": CELL_X}
        L["dock"] = dock_geometry(q, xr, wall)
        cell = Script()
        joins = build_dock_joins(cell, q, L)
        cuts = build_dock_cuts(cell, q, L)
        tool_name = "coupon"
        # needle-free: the guard tube bore stays (hub seat), the fluid channel is not needed -> keep as a through hole marker
        cell.join(tool_name, joins)
        cell.cut(tool_name, cuts)
        # engraved ID (7 segments) near the open end, between cells
        dx, dy = 16.6, yc - CELL_Y / 2 + 1.3          # digit centre, inside the margin between two floor openings
        segs = SEG[v["id"]]
        w, ln, t = 0.4, 1.0, 0.3
        pos = {"a": (0, 1.0, "h"), "g": (0, 0.0, "h"), "d": (0, -1.0, "h"), "f": (-0.5, 0.5, "v"),
               "b": (0.5, 0.5, "v"), "e": (-0.5, -0.5, "v"), "c": (0.5, -0.5, "v")}
        eng = []
        for sg in segs:
            ox, oy, o = pos[sg]
            cx, cy = dx + ox, dy + oy
            ex, ey = (ln + w, w) if o == "h" else (w, ln + w)
            eng.append(cell.box(f"t_e{sg}", (cx - ex / 2, cx + ex / 2), (cy - ey / 2, cy + ey / 2), (plate_t - t, plate_t + 0.1)))
        cell.cut(tool_name, eng)
        cmds = cell.dumps()
        # scope: rename every tool body of this cell; keep the shared 'coupon' target
        scoped = _scope([c for c in cmds], f"_c{i}")
        for c in scoped:   # undo suffix on the shared body
            pr = c["params"]
            for k in ("body_name", "name", "target"):
                if pr.get(k) == "coupon_c%d" % i:
                    pr[k] = "coupon"
            if isinstance(pr.get("tools"), list):
                pr["tools"] = [x for x in pr["tools"]]
        s.cmds.extend(scoped)
    return s, vs
