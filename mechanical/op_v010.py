# SPDX-License-Identifier: LicenseRef-OpenPatch
"""OpenPatch v0.1.0 INTEGRATED pod (mechanical variant `v010`), additive to the bench pod.

TEST PROJECT: never worn, never filled with anything but water (CLAUDE.md, DISCLAIMER.md).

Idea: the v0.1.0 pod IS the bench pod (frozen CNC reservoir, drive, end cap, modular dock insert on the frozen interface)
plus an electronics tail.  The Insight Flex dome slides in from the +X end, so the tail cannot sit *behind* the dock; it lies in the
free strip BESIDE the dock tunnel (y > dock axis + dome radius + clearance) and the pod gets longer (docs/v010/ARCHITECTURE.md
assumed a tail behind the dock; see mechanical/V010.md section 2).

Everything is expressed in u = x - x_r1 (pod frame) and absolute y, derived from the computed bench layout (`op_layout.compute_layout`),
so it follows drive / reservoir changes of the bench pod.  Shared files only carry small hooks (`p["v010_active"]`).

Board frame (same convention as the bench pod board): bx = x_pod - X0, by = y_pod - V0, X0 = x_r1 + U0, V0 = board.y0;
board viewed from the TOP (lid side), F.Cu = lid side (+Z), B.Cu = floor side.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from op_cmds import Script
from op_layout import HERE, compute_layout

SCHEMA = "openpatch-v010-layout/1"
REMOVED_BENCH = ["pod_board", "ffc_conn", "ffc_cable"]          # bench-only bodies (pod_board is re-created as the integrated board)
NEW_BODIES = ["pod_board", "e73", "pico_conn", "pico_plug", "battery", "bat_foam", "bat_pad_p", "bat_pad_n", "spring_p", "spring_n",
              "piezo", "switch", "chg_pad_1", "chg_pad_2", "charge_gasket"]
V010_EXCLUDE_PAIRS: list[list[str]] = []                         # everything touches only; no intentional overlaps (checked)
ELEC_FILE = HERE.parent / "electronics" / "v010" / "board.layout.json"


# ----------------------------------------------------------------------------------------------------------------------
# parameters / strip plan
# ----------------------------------------------------------------------------------------------------------------------
def read_electronics(path: Path | None = None) -> dict | None:
    """electronics/v010/board.layout.json (written by the electronics agent) wins over the built-in proposal outline.

    Accepted keys (board frame as defined above): `outline_polygon_board_mm` (or `board.outline_polygon_board_mm`, or `outline`) = closed polygon;
    optional `components`: {name: {"center_board_mm": [bx, by]}} for e73 / pico_conn / piezo / switch / charge_pad_1 / charge_pad_2 (informational:
    the mechanical positions are reported against them by check.py, they do not move parts)."""
    f = path or ELEC_FILE
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    poly = d.get("outline_polygon_board_mm") or (d.get("board") or {}).get("outline_polygon_board_mm") or d.get("outline")
    return {"file": str(f.relative_to(HERE.parent)), "outline": poly, "components": d.get("components", {})}


def strip_plan(p: dict, L0: dict) -> dict:
    """u positions of the strip items (connector, cell, E73) from the computed bench layout; tail_len = distance x_r1 -> inner end wall."""
    v = p["v010"]
    xr, B = L0["x_r1"], L0["bench"]
    tm = next(s for s in B["sensors"] if s["id"] == "HALL_3D")
    tmag_end_u = tm["center_pod_mm"][0] + tm["body_xyz_mm"][0] / 2 - xr
    c, bt, e, st = v["connector"], v["battery"], v["e73"], v["strip"]
    conn_u = tmag_end_u + c["tmag_clear"] - c["plug_x"][0]          # connector origin: plug body clears the TMAG package
    conn_u1 = conn_u + c["housing_x"][1]
    cell_u0 = conn_u1 + st["gap"]
    cell_u1 = cell_u0 + bt["l"]
    e73_u0 = cell_u1 + st["gap"] + 0.2
    e73_u1 = e73_u0 + e["l"]
    tail_len = max(e73_u1 + st["e73_end_gap"], p["bench"]["tail_len"])
    cn = p["cannula"]
    return {"tmag_end_u": round(tmag_end_u, 3), "conn_u": round(conn_u, 3), "conn_u1": round(conn_u1, 3), "cell_u0": round(cell_u0, 3),
            "cell_u1": round(cell_u1, 3), "e73_u0": round(e73_u0, 3), "e73_u1": round(e73_u1, 3), "tail_len": round(tail_len, 3),
            "lead_end_u": round(conn_u + c["plug_x"][0] - v["lead"]["end_clear"], 3),
            "y_lo_arms": round(p["dock"]["y_c"] + p["dock"]["arm_t"] + L0["dock"]["arm_in"] + st["arm_clear"], 3),
            "y_lo_dome": round(p["dock"]["y_c"] + cn["A_dome_d"] / 2 + st["arm_clear"], 3),
            "arms_end_u": round(L0["dock"]["arm_x"][1] - xr, 3)}


def prepare(p: dict) -> dict:
    """Return a copy of the params with the v0.1.0 overrides applied (height, board, mount set, tail length, plan)."""
    p = copy.deepcopy(p)
    v = p["v010"]
    p["mode"] = "bench"
    p["v010_active"] = True
    p["shell"]["width"] = p["bench"]["width_by_layout"][p["bench"]["drive_layout"]]
    p["shell"]["height"] = v["height"]
    p["bench"]["board_t"] = v["board"]["t"]
    p["bench"]["mount"] = {**p["bench"]["mount"], **v["mount"]}
    p["v010_plan"] = {"lead_end_u": 0.0}
    L0 = compute_layout(p, next(iter(p["variants"])))
    plan = strip_plan(p, L0)
    p["bench"]["tail_len"] = plan["tail_len"]
    p["v010_plan"] = plan
    p["v010_electronics"] = read_electronics()
    return p


# ----------------------------------------------------------------------------------------------------------------------
# geometry (pod coordinates, mm)
# ----------------------------------------------------------------------------------------------------------------------
def _arc(cx: float, cy: float, r: float, a0: float, a1: float, n: int = 10) -> list[tuple[float, float]]:
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def geometry(p: dict, L: dict) -> dict:
    v, pl = p["v010"], p["v010_plan"]
    xr, B, D = L["x_r1"], L["bench"], L["dock"]
    bd, bt, e, c, pz, bn, ch, st = v["board"], v["battery"], v["e73"], v["connector"], v["piezo"], v["button"], v["charge"], v["strip"]
    z0, ztop, zi, zt, wall = B["z0"], B["ztop"], L["z_top_inner"], p["shell"]["height"], L["wall"]
    U0, V0 = B["U0"], bd["y0"]
    X0 = xr + U0

    def X(u: float) -> float:
        return xr + u

    # ---- board outline (pod coordinates) ---------------------------------------------------------------------------------
    u_r = pl["tail_len"] - bd["right_gap"]
    R = bd["corner_r"]
    um = bd["left_to_u"]
    pts_u = [(U0, bd["left_y0"]), (um, bd["left_y0"]), (um, bd["y0"]), (u_r - R, bd["y0"])]
    pts_u += _arc(u_r - R, bd["y0"] + R, R, -90, 0)[1:]
    pts_u += [(u_r, bd["y1"] - R)] + _arc(u_r - R, bd["y1"] - R, R, 0, 90)[1:]
    pts_u += [(U0 + 1.0, bd["y1"])] + _arc(U0 + 1.0, bd["y1"] - 1.0, 1.0, 90, 180)[1:]
    outline_pod = [(round(X(u), 4), round(y, 4)) for u, y in pts_u]
    outline_board = [[round(x - X0, 4), round(y - V0, 4)] for x, y in outline_pod]
    elec = p.get("v010_electronics")
    if elec and elec.get("outline"):                       # electronics agent's outline wins (board frame)
        outline_board = [[round(a, 4), round(b, 4)] for a, b in elec["outline"]]
        outline_pod = [(round(X0 + a, 4), round(V0 + b, 4)) for a, b in outline_board]

    # ---- strip items ------------------------------------------------------------------------------------------------------
    cell_yc = bt["y0"] + bt["w"] / 2
    cell_z0 = wall + bt["foam_t"]
    cell_top = cell_z0 + bt["t"]
    cell = {"u": [pl["cell_u0"], pl["cell_u1"]], "x": [X(pl["cell_u0"]), X(pl["cell_u1"])], "y": [bt["y0"], bt["y0"] + bt["w"]], "z": [round(cell_z0, 3), round(cell_top, 3)]}
    pads = []
    for sg in (-1, 1):
        px, py = X(pl["cell_u0"] + bt["pad_u"]), cell_yc + sg * bt["pad_dy"] / 2
        pads.append({"center_pod": [round(px, 3), round(py, 3)], "size": bt["pad"], "z": [round(cell_top, 3), round(cell_top + 0.05, 3)]})
    ribs = [{"id": "rib_ym", "x": [X(pl["cell_u0"] - 0.1), X(pl["cell_u1"] + 0.1)], "y": [bt["y0"] - 0.1 - bt["rib_t"], bt["y0"] - 0.1], "h": bt["rib_h"]},
            {"id": "rib_yp", "x": [X(pl["cell_u0"] - 0.1), X(pl["cell_u1"] + 0.1)], "y": [bt["y0"] + bt["w"] + 0.1, bt["y0"] + bt["w"] + 0.1 + bt["rib_t"]], "h": bt["rib_h"]},
            {"id": "rib_xm", "x": [X(pl["cell_u0"] - 0.1 - bt["rib_t"]), X(pl["cell_u0"] - 0.1)], "y": [bt["y0"] - 0.1, bt["y0"] + bt["w"] + 0.1], "h": bt["end_rib_h"]},
            {"id": "rib_xp", "x": [X(pl["cell_u1"] + 0.1), X(pl["cell_u1"] + 0.1 + bt["rib_t"])], "y": [bt["y0"] - 0.1, bt["y0"] + bt["w"] + 0.1], "h": bt["rib_h"]}]
    e73_y0 = max(pl["y_lo_dome"], bd["y0"] + 0.0)
    e73 = {"center_pod": [round(X(pl["e73_u0"] + e["l"] / 2), 4), round(e73_y0 + e["w"] / 2, 4)], "u": [pl["e73_u0"], pl["e73_u1"]],
           "y": [round(e73_y0, 3), round(e73_y0 + e["w"], 3)], "z": [round(z0 - e["h"] - 0.03, 3), z0], "antenna_end": "+X",
           "antenna_keepout_u": [round(pl["e73_u1"] - e["antenna_keepout_l"], 3), round(pl["e73_u1"] + p["v010"]["strip"]["e73_end_gap"], 3)]}
    conn = {"origin_pod": [round(X(pl["conn_u"]), 4), c["y"]], "plug_mouth_x": round(X(pl["conn_u"] + c["plug_x"][0]), 3),
            "housing_x": [round(X(pl["conn_u"] + c["housing_x"][0]), 3), round(X(pl["conn_u"] + c["housing_x"][1]), 3)],
            "tab_y": [c["y"] - c["tab_half_y"], c["y"] + c["tab_half_y"]], "z": [round(z0 - c["h"], 3), z0]}
    pz_u0 = pl["cell_u0"] + pz["u0_off"]
    piezo = {"x": [round(X(pz_u0), 3), round(X(pz_u0 + pz["l"]), 3)], "y": [pz["y"], pz["y"] + pz["w"]], "z": [ztop, ztop + pz["h"]],
             "port": [round(X(pz_u0 + pz["l"] / 2), 3), pz["y"] + pz["w"] / 2]}
    sw_u = pz_u0 + pz["l"] + bn["gap_u"]
    sw = {"center_pod": [round(X(sw_u), 3), bn["y"]], "size": bn["sw"], "z": [ztop, ztop + bn["sw"][2]]}
    cu = pl["e73_u0"] + ch["u_off"]
    cpads = [{"center_pod": [round(X(cu), 3), round(ch["y_c"] + sg * ch["pitch"] / 2, 3)], "size": ch["pad"], "z": [ztop, ztop + ch["pad_t"]]} for sg in (-1, 1)]
    wy = (ch["y_c"] - ch["pitch"] / 2 - ch["pad"] / 2 - ch["win_margin"], ch["y_c"] + ch["pitch"] / 2 + ch["pad"] / 2 + ch["win_margin"])
    window = {"x": [round(X(cu - ch["win_x"] / 2), 3), round(X(cu + ch["win_x"] / 2), 3)], "y": [round(wy[0], 3), round(wy[1], 3)]}
    gw = ch["gasket_w"]
    gasket = {"outer_x": [window["x"][0] - gw, window["x"][1] + gw], "outer_y": [window["y"][0] - gw, window["y"][1] + gw],
              "z": [round(ztop + ch["gasket_gap"], 3), round(zi - ch["gasket_gap"], 3)]}
    vt = v["vent"]
    vent = {"center_pod": [round(X(vt["u"]), 3), vt["y"]], "hole_d": vt["hole_d"], "recess_d": vt["recess_d"], "recess_depth": vt["recess_depth"]}
    # ---- spring contact stack ------------------------------------------------------------------------------------------------
    spring_gap = z0 - (cell_top + 0.05)
    # ---- lead -------------------------------------------------------------------------------------------------------------------
    n = L["nfp_term"]
    ld = p["bench"]["lead"]
    lead_len = (conn["plug_mouth_x"] - n["x_center"]) + (c["h"] / 2 + z0 - c["h"] - ld["groove_floor"]) + abs(c["y"] - ld["groove_y"]) + c["lead_rise_allow"]
    # ---- holes through the board -----------------------------------------------------------------------------------------------
    m = p["bench"]["mount"]
    holes = [{"what": "lid screw clearance", "center_pod": [s_["x"], s_["y"]], "d": bd["screw_hole_d"]} for s_ in L["screws"]
             if s_["x"] > X0 - 2 and s_["y"] > bd["y0"] - 2]
    holes += [{"what": "locating pin", "center_pod": [round(X(q[0]), 4), q[1]], "d": m["hole_d"]} for q in m["pins"]]
    holes += [{"what": "board screw M1.2", "center_pod": [round(X(m["screw"][0]), 4), m["screw"][1]], "d": m["screw_hole_d"]}]
    return {"U0": U0, "V0": V0, "X0": X0, "z0": z0, "ztop": ztop, "zi": zi, "zt": zt, "board_t": ztop - z0, "outline_pod": outline_pod,
            "outline_board": outline_board, "u_right": round(u_r, 3), "holes": holes, "cell": cell, "cell_pads": pads, "ribs": ribs,
            "cell_yc": cell_yc, "spring_gap": round(spring_gap, 3), "e73": e73, "conn": conn, "piezo": piezo, "switch": sw, "charge_pads": cpads, "window": window,
            "gasket": gasket, "vent": vent, "lead_len_est": round(lead_len, 2), "plan": pl, "electronics_file": (elec or {}).get("file")}


# ----------------------------------------------------------------------------------------------------------------------
# CAD
# ----------------------------------------------------------------------------------------------------------------------
def _catalog_bodies(key: str) -> list[str]:
    return list(json.loads((HERE / "components" / "catalog.json").read_text())[key]["bodies"])


def build(s: Script, p: dict, L: dict, G: dict) -> None:
    from op_dock import build_insert
    from op_models import _box, _cut, _ins, _mat
    v = p["v010"]
    xr, wall = L["x_r1"], L["wall"]
    z0, ztop, zi, zt = G["z0"], G["ztop"], G["zi"], G["zt"]
    bt, c, pz, bn, ch, e = v["battery"], v["connector"], v["piezo"], v["button"], v["charge"], v["e73"]
    m = p["bench"]["mount"]

    s.add("solid.remove", bodies=list(REMOVED_BENCH))
    # frozen insert keeps its bench length (the same printed part fits bench and v0.1.0 pods); the tunnel continues in the housing
    Lf = dict(L)
    Lf["length"] = xr + p["dock_interface_frozen"]["tail_u"]
    s.add("solid.remove", bodies=["dock_insert"])
    build_insert(s, p, Lf, "dock_insert")

    # ---- integrated board --------------------------------------------------------------------------------------------------------
    s.polyprism("pod_board", [tuple(q) for q in G["outline_pod"]], (z0, ztop))
    cuts = [s.cyl(f"t_bh{i}", "Z", (h["center_pod"][0], h["center_pod"][1], 0), h["d"], z0 - 0.1, ztop + 0.1) for i, h in enumerate(G["holes"])]
    s.cut("pod_board", cuts)
    for i, cp in enumerate(G["charge_pads"]):
        x, y = cp["center_pod"]
        hs = cp["size"] / 2
        s.box(f"chg_pad_{i + 1}", (x - hs, x + hs), (y - hs, y + hs), tuple(cp["z"]))
    # ---- E73 module (real STEP, hangs below the board, antenna toward +X) ------------------------------------------------------------
    ex, ey = G["e73"]["center_pod"]
    cmds = [_ins("ebyte_e73_2g4m08s1c", "e73", _mat((0, -1, 0), (-1, 0, 0), (0, 0, -1), (ex, ey, z0 - 0.03)))]   # castellation pads protrude 0.03: seat them on the board bottom
    names = _catalog_bodies("ebyte_e73_2g4m08s1c")
    cmds += [{"command": "solid.combine", "params": {"target": "pcb", "tools": [n for n in names if n != "pcb"], "operation": "join", "name": "join e73"}},
             {"command": "body.rename", "params": {"body": "pcb", "name": "e73"}}]
    # ---- PicoBlade connector + plug stub (lead is a flexible 4-wire lead: only a stub is modelled) ------------------------------------
    cx, cy = G["conn"]["origin_pod"]
    mat = _mat((0, 1, 0), (1, 0, 0), (0, 0, -1), (cx, cy, z0))
    cmds += [_ins("molex_picoblade_53261_0471", "pbc", mat), _ins("lead_picoblade_plug", "pbp", mat)]
    cn_names = _catalog_bodies("molex_picoblade_53261_0471")
    pl_names = _catalog_bodies("lead_picoblade_plug")
    stub_end = cx + c["plug_x"][0] - 1.5
    for nme in pl_names:
        if nme.startswith("strip"):
            cmds.append({"command": "solid.remove", "params": {"bodies": [nme]}})
        elif nme.startswith("wire"):
            cmds += [_box(f"t_wcut_{nme}", (cx - 80, stub_end), (cy - 10, cy + 10), (0, z0)), _cut(nme, f"t_wcut_{nme}")]
    pl_keep = [n_ for n_ in pl_names if not n_.startswith("strip")]
    cmds += [{"command": "solid.combine", "params": {"target": "housing", "tools": [n_ for n_ in cn_names if n_ != "housing"], "operation": "join", "name": "join conn"}},
             {"command": "body.rename", "params": {"body": "housing", "name": "pico_conn"}},
             {"command": "solid.combine", "params": {"target": "plug", "tools": [n_ for n_ in pl_keep if n_ != "plug"], "operation": "join", "name": "join plug"}},
             {"command": "body.rename", "params": {"body": "plug", "name": "pico_plug"}}]
    s.cmds.extend(cmds)
    # ---- Li-Po cell, foam, PCM pads, spring contacts -------------------------------------------------------------------------------------
    cl = G["cell"]
    s.box("bat_foam", tuple(cl["x"]), tuple(cl["y"]), (wall, cl["z"][0]))
    s.box("battery", tuple(cl["x"]), tuple(cl["y"]), tuple(cl["z"]))
    for nm, sp_, pd in (("p", "spring_p", G["cell_pads"][0]), ("n", "spring_n", G["cell_pads"][1])):
        px, py = pd["center_pod"]
        hw = pd["size"][0] / 2
        s.box(f"bat_pad_{nm}", (px - hw, px + hw), (py - pd["size"][1] / 2, py + pd["size"][1] / 2), tuple(pd["z"]))
        hs = bt["spring"][0] / 2
        s.box(sp_, (px - hs, px + hs), (py - hs, py + hs), (pd["z"][1], z0))
    # ---- top side: piezo, tact switch ----------------------------------------------------------------------------------------------------
    s.box("piezo", tuple(G["piezo"]["x"]), tuple(G["piezo"]["y"]), tuple(G["piezo"]["z"]))
    sx, sy = G["switch"]["center_pod"]
    sw_ = G["switch"]["size"]
    s.box("switch", (sx - sw_[0] / 2, sx + sw_[0] / 2), (sy - sw_[1] / 2, sy + sw_[1] / 2), tuple(G["switch"]["z"]))
    # ---- charge-window gasket (reference part, die-cut silicone) ------------------------------------------------------------------------------
    gk = G["gasket"]
    s.box("charge_gasket", tuple(gk["outer_x"]), tuple(gk["outer_y"]), tuple(gk["z"]))
    s.box("t_gk_in", tuple(G["window"]["x"]), tuple(G["window"]["y"]), (gk["z"][0] - 0.1, gk["z"][1] + 0.1))
    s.cut("charge_gasket", ["t_gk_in"])
    # ---- housing features -------------------------------------------------------------------------------------------------------------------------
    joins = [s.box(f"t_{r['id']}", tuple(r["x"]), tuple(r["y"]), (wall - 0.1, wall + r["h"])) for r in G["ribs"]]
    s.join("bottom", joins)
    pt = p["port"]
    px, py = G["piezo"]["port"]
    bx, by = G["switch"]["center_pod"]
    zpost = ztop + bn["sw"][2] + 0.1
    s.join("top", [s.cyl("t_btnpost", "Z", (bx, by, 0), p["button"]["post_d"], zpost, zi + 0.1)])
    lc = [s.cyl("t_port", "Z", (px, py, 0), pt["hole_d"], zi - 0.1, zt + 0.1),
          s.cyl("t_prec", "Z", (px, py, 0), pt["recess_d"], zi - 0.1, zi + pt["recess_depth"]),
          s.cyl("t_vent", "Z", (G["vent"]["center_pod"][0], G["vent"]["center_pod"][1], 0), G["vent"]["hole_d"], zi - 0.1, zt + 0.1),
          s.cyl("t_vrec", "Z", (G["vent"]["center_pod"][0], G["vent"]["center_pod"][1], 0), G["vent"]["recess_d"], zi - 0.1, zi + G["vent"]["recess_depth"]),
          s.cyl("t_memb", "Z", (bx, by, 0), p["button"]["d_memb"], zt - (wall - p["button"]["memb_t"]), zt + 0.1),
          s.box("t_chgwin", tuple(G["window"]["x"]), tuple(G["window"]["y"]), (zi - 0.1, zt + 0.1))]
    s.cut("top", lc)


def part_lists(base_mfg: dict, base_names: list) -> tuple[dict, list]:
    mfg = dict(base_mfg)
    mfg["charge_gasket"] = ["charge_gasket"]
    names = [b for b in base_names if b not in REMOVED_BENCH] + NEW_BODIES
    return mfg, names


# ----------------------------------------------------------------------------------------------------------------------
# layout.json for the electronics
# ----------------------------------------------------------------------------------------------------------------------
def layout_json(p: dict, L: dict, G: dict) -> dict:
    v = p["v010"]
    X0, V0 = G["X0"], G["V0"]

    def bf(x: float, y: float) -> list[float]:
        return [round(x - X0, 3), round(y - V0, 3)]

    def rect_b(x0, y0, x1, y1) -> list[float]:
        return [round(x0 - X0, 3), round(y0 - V0, 3), round(x1 - X0, 3), round(y1 - V0, 3)]

    xr, B, pl = L["x_r1"], L["bench"], G["plan"]
    e, cl, c = G["e73"], G["cell"], G["conn"]
    ztop, z0 = G["ztop"], G["z0"]
    top_free = G["zi"] - ztop
    y_lo, y_hi = G["V0"], v["board"]["y1"]
    zones = [
        {"id": "dock_tunnel", "rect_board": rect_b(xr + 4.4, p["dock"]["y_c"] - 6.2, L["x_end"], p["dock"]["y_c"] + 6.2),
         "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": 0.0,
         "note": "dock insert (top z 5.2) and the Insight Flex dome path under the board: NO bottom-side parts except HALL_DOCK pocket (0.4 mm, z 4.9..5.3 over the insert recess)"},
        {"id": "strip_tall", "rect_board": rect_b(xr + pl["tmag_end_u"] + 0.3, pl["y_lo_dome"], L["x_end"] - 0.6, y_hi),
         "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": round(z0 - L["wall"] - 0.2, 2),
         "note": "free air beside the dock tunnel: E73 (2.25), PicoBlade (3.4), cell bay (<=0.75 SMD spring contacts only over the cell)"},
        {"id": "battery_bay", "rect_board": rect_b(cl["x"][0], cl["y"][0], cl["x"][1], cl["y"][1]), "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": 0.75,
         "note": "cell top z %.2f; only the 2 SMD spring contacts (pads below) may hang under the board here" % cl["z"][1]},
        {"id": "wing_spindle", "rect_board": rect_b(X0, v["board"]["left_y0"], xr + v["board"]["left_to_u"], y_hi), "top_max_mm": round(top_free - 0.2, 2), "bottom_max_mm": 1.5,
         "note": "TMAG5273 hangs 1.45 mm (z 3.85..5.3) on the spindle axis; DRV5032 pair on top"},
    ]
    sens = []
    for sn in B["sensors"]:
        sens.append({"id": sn["id"], "part": sn["part"], "side": sn["side"], "center_board_mm": bf(*sn["center_pod_mm"]), "body_xyz_mm": sn["body_xyz_mm"],
                     "z_body_pod": sn["z_body_pod"], "note": "position relative to the spindle magnet / dock interface is UNCHANGED from the bench pod (u = %.2f)" % (sn["center_pod_mm"][0] - xr)})
    return {
        "schema": SCHEMA, "variant": L["variant"], "kind": "integrated_pod_board", "units": "mm", "status": "generated by mechanical/generate.py --variant v010; CAD-verified by check.py --variant v010",
        "warning": "TEST PROJECT - never worn, water only.",
        "frames": {"pod": "X length, Y width, Z up (Z=0 skin side)", "board": "bx,by = pod x,y minus transform.board_origin_in_pod_mm, viewed from the TOP (lid side), X right, Y up; KiCad: flip Y",
                   "layers": "F.Cu = top/lid side (+Z), B.Cu = bottom/floor side (-Z)"},
        "pod": {"length": round(L["length"], 3), "width": L["width"], "height": L["height"], "x_r1": round(xr, 4), "x_end_inner": round(L["x_end"], 3)},
        "transform": {"board_origin_in_pod_mm": [round(X0, 4), round(V0, 4)], "rotation_deg": 0, "mirror": False, "board_bottom_z_pod": z0, "board_top_z_pod": round(ztop, 3),
                      "u_origin_note": "u = x_pod - x_r1; the board file is identical for all sizes except this offset"},
        "board": {"thickness_mm": v["board"]["t"], "layers": v["board"]["layers"], "outline_polygon_board_mm": G["outline_board"], "outline_source": G["electronics_file"] or "mechanical generator (strip layout)",
                  "note": "closed CCW polygon; inside corners add R0.5 for routing. Holes below are NPTH."},
        "stack_z_pod": {"floor_top": L["wall"], "foam": [L["wall"], cl["z"][0]], "cell": cl["z"], "cell_pad_top": round(cl["z"][1] + 0.05, 3), "board_bottom": z0, "board_top": round(ztop, 3), "lid_inner": round(G["zi"], 3),
                        "top_free_mm": round(top_free, 2), "spring_contact_gap_mm": G["spring_gap"], "spring_free_height_max_mm": v["battery"]["spring_free_max"]},
        "zones": zones,
        "heights_mm": {"top_max": round(top_free - 0.2, 2), "bottom_over_dock_tunnel": 0.0, "bottom_over_dock_hall_only": 0.4, "bottom_strip_tall": round(z0 - L["wall"] - 0.2, 2), "bottom_over_battery": 0.75},
        "battery": {"class": v["battery"]["class"], "envelope_mm": [v["battery"]["l"], v["battery"]["w"], v["battery"]["t"]], "bay_rect_board": rect_b(cl["x"][0], cl["y"][0], cl["x"][1], cl["y"][1]),
                    "pcm_end": "-X", "cell_pads_board_mm": [dict(center_board_mm=bf(*q["center_pod"]), size_mm=q["size"], polarity=pol) for q, pol in zip(G["cell_pads"], ("B+/P+ (assign by cell label)", "B-/P- (assign by cell label)"))],
                    "spring_contacts": {"count": 2, "side": "bottom", "centers_board_mm": [bf(*q["center_pod"]) for q in G["cell_pads"]], "footprint_mm": v["battery"]["spring"], "free_height_max_mm": v["battery"]["spring_free_max"],
                                        "compressed_height_mm": G["spring_gap"], "note": "MPN not selected (VERIFY): 1.0-1.2 mm SMD spring finger class; fallback: M1.2 clamp pads"}},
        "e73": {"part": e73_part(p), "center_board_mm": bf(*e["center_pod"]), "side": "bottom", "size_mm": [v["e73"]["l"], v["e73"]["w"], v["e73"]["h"]], "long_axis": "X", "antenna_end": "+X",
                "rotation_note": "module as in the E73 library model rotated: antenna end (ceramic) toward +X, pad row end toward -X, module hangs BELOW the board (castellations on the board), z %.2f..%.2f" % tuple(e["z"]),
                "antenna_keepout_board_mm": rect_b(xr + e["antenna_keepout_u"][0], e["y"][0], xr + e["antenna_keepout_u"][1], e["y"][1]), "antenna_keepout_note": "all layers copper-free + no metal parts (cell, magnets, motor are >= 14 mm away)"},
        "motor_connector": {"part": v["connector"]["part"], "origin_board_mm": bf(*c["origin_pod"]), "side": "bottom", "row_axis": "Y", "cavity_faces": "-X (plug enters from the motor side)",
                            "footprint_board_mm": rect_b(c["housing_x"][0], c["tab_y"][0], c["housing_x"][1], c["tab_y"][1]), "height_mm": v["connector"]["h"],
                            "lead_length_estimate_mm": G["lead_len_est"], "lead_length_limit_mm": v["connector"]["lead_max_mm"],
                            "note": "footprint as molex_picoblade_53261_0471 in components/catalog.json; VERIFY against the Molex drawing"},
        "piezo": {"part": v["piezo"]["part"], "side": "top", "rect_board_mm": rect_b(G["piezo"]["x"][0], G["piezo"]["y"][0], G["piezo"]["x"][1], G["piezo"]["y"][1]), "height_mm": v["piezo"]["h"],
                  "sound_port_board_mm": bf(*G["piezo"]["port"]), "note": "MLT-8530 (3.0 mm) does NOT fit on the lid side (1.5 mm free) and sounds into the floor if hung below: see V010.md"},
        "button": {"side": "top", "center_board_mm": bf(*G["switch"]["center_pod"]), "size_mm": G["switch"]["size"], "membrane_d_mm": p["button"]["d_memb"]},
        "charge_pads": {"side": "top", "pads_board_mm": [dict(center_board_mm=bf(*q["center_pod"]), size_mm=[q["size"], q["size"]], net=n) for q, n in zip(G["charge_pads"], ("CHG_IN (+5 V, 20 mA)", "GND"))],
                        "finish": "ENIG (no HASL), no solder mask over the pad",
                        "lid_window_board_mm": rect_b(G["window"]["x"][0], G["window"]["y"][0], G["window"]["x"][1], G["window"]["y"][1]),
                        "gasket_outer_board_mm": rect_b(G["gasket"]["outer_x"][0], G["gasket"]["outer_y"][0], G["gasket"]["outer_x"][1], G["gasket"]["outer_y"][1]),
                        "keepout_note": "keep the gasket ring (1.2 mm wide around the window) free of components and vias; ESD/TVS next to the pads"},
        "vent": {"center_pod_mm": G["vent"]["center_pod"], "center_board_mm": bf(*G["vent"]["center_pod"]), "note": "lid vent d%.1f + d%.1f recess for an ePTFE membrane; keep the membrane disc area above the board free of tall parts (top free %.2f mm)" % (G["vent"]["hole_d"], G["vent"]["recess_d"], top_free)},
        "hall_sensors": sens,
        "holes_npth": [dict(what=h["what"], center_board_mm=bf(*h["center_pod"]), d_mm=h["d"]) for h in G["holes"]],
        "mounting": {"posts_under_board": [dict(center_board_mm=bf(L["x_r1"] + q[0], q[1]), d_mm=p["bench"]["mount"]["post_d"]) for q in p["bench"]["mount"]["posts"]]
                     + [dict(center_board_mm=bf(L["x_r1"] + q[0], q[1]), d_mm=p["bench"]["mount"]["pin_post_d"], note="locating pin post") for q in p["bench"]["mount"]["pins"]],
                     "lid_hold_down_pads_top": [dict(center_board_mm=bf(L["x_r1"] + q[0], q[1]), d_mm=p["bench"]["mount"]["hd_d"], top_keepout_d_mm=p["bench"]["mount"]["hd_d"] + 0.6) for q in p["bench"]["mount"]["hd"]]},
        "unrouted_notes": "no components under the board over the dock tunnel; top-side parts <= %.2f mm; the strip beside the tunnel is the only place for tall bottom parts" % (top_free - 0.2),
    }


def e73_part(p: dict) -> str:
    return p["v010"]["e73"]["part"]
