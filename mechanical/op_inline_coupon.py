"""Cheap printable bench test coupon of the cup drive (`generate.py --variant bench --drive inline --coupon`) -> studies/drive/coupon/.

No pod needed.  Parts: bore block (stadium 16 x 5, open at both ends), rear block with the screw bush seat, front pad (flat: kitchen-scale thrust test)
or front plug with the d2.0 port (leak / pressure test), plus the REAL plunger parts (piston + 2 cast lip rings, tube, plate, nut) and the M1.6 screw.
Axis along X, bore axis y = 14, z = 4.2 (same z as the pod).  Test procedure: studies/drive/SEALED-DRIVE-STUDY.md section 8.
"""
from __future__ import annotations

from op_inline import (PLATE_CBORE, PLATE_CBORE_D, PLATE_POCKET, PLATE_T, SCREW_HOLE_D, SOCKET_D, SOCKET_DEPTH, TUBE_ID, TUBE_OD, cup_geometry, cup_len, pl_core)


def build_coupon(s, p: dict, stroke: float = 13.4) -> dict:
    rs, dr, sl = p["reservoir"], p["drive"], p["seal"]
    zc, yr = 4.2, 14.0
    wo, ho = rs["w_in"] + 2 * rs["wall"], rs["h_in"] + 2 * rs["wall"]
    xr0 = 8.0                                            # bore block starts behind the rear block
    L_bore = 1.0 + stroke + cup_len(stroke) + 0.2 + 1.0
    xr1 = xr0 + L_bore
    s.stadium("coupon_bore", (xr0, xr1), yr, zc, wo + 3.0, ho + 3.0)
    s.cut("coupon_bore", [s.stadium("t_cchamber", (xr0 - 0.1, xr1 + 0.1), yr, zc, rs["w_in"], rs["h_in"])])
    s.box("coupon_rear", (0.0, xr0 - 0.2), (yr - 9.0, yr + 9.0), (zc - 4.0, zc + 4.0))
    s.cut("coupon_rear", [s.cyl("t_cbush", "X", (0, yr, zc), dr["bush_od"] + dr["bush_bore_clr"], 2.0, 3.2),
                          s.cyl("t_chole", "X", (0, yr, zc), 2.0, -0.1, 2.1), s.cyl("t_cpass", "X", (0, yr, zc), 8.0, 3.1, xr0 + 0.1)])
    s.stadium("coupon_front_pad", (xr1 + 0.3, xr1 + 2.3), yr, zc, wo + 3.0, ho + 3.0)
    s.stadium("coupon_front_plug", (xr1 + 3.0, xr1 + 6.0), yr, zc, wo + 3.0, ho + 3.0)
    s.cut("coupon_front_plug", [s.cyl("t_cport", "X", (0, yr, zc), 2.0, xr1 + 2.9, xr1 + 6.1)])
    L = {"stroke": stroke, "xrear": xr0 + 1.0, "z_axis": zc, "y_r": yr}
    old = rs["plunger_len"]
    rs["plunger_len"] = cup_len(stroke)
    C = cup_geometry(p, L)
    c = rs["plunger_clr"]
    wc, hc = rs["w_in"] - 2 * c, rs["h_in"] - 2 * c
    gd = sl["groove_depth"]
    xpr = C["xpr"]
    s.stadium("plunger_core", (xpr, xpr + pl_core(p)), yr, zc, wc, hc)
    tools = []
    for k, (a, b) in enumerate((sl["ring_a"], sl["ring_b"])):
        s.stadium_ring(f"t_gr{k}", (xpr + a, xpr + b), yr, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
        tools.append(f"t_gr{k}")
    tools.append(s.cyl("t_psock", "X", (0, yr, zc), SOCKET_D, xpr - 0.1, xpr + SOCKET_DEPTH))
    s.cut("plunger_core", tools)
    s.stadium("plunger_nose", (C["nose"][0], C["nose"][1]), yr, zc, wc, hc)
    for k, nm in enumerate(("seal_a", "seal_b")):
        a, b = (sl["ring_a"], sl["ring_b"])[k]
        s.stadium_ring(nm, (xpr + a, xpr + b), yr, zc, rs["w_in"] - sl["assembly_gap"], rs["h_in"] - sl["assembly_gap"], wc - 2 * gd, hc - 2 * gd)
    s.tube("plunger_tube", "X", (0, yr, zc), TUBE_OD, TUBE_ID, C["tube"][0], C["tube"][1])
    x0 = C["plate"][0]
    s.stadium("plunger_plate", (x0, x0 + PLATE_T), yr, zc, wc, hc)
    s.cut("plunger_plate", [s.hexprism("t_phex", (x0 - 0.1, x0 + PLATE_POCKET), yr, zc, (dr["nut_af"] + 0.1) / 2, angle=0.0),
                            s.cyl("t_phole", "X", (0, yr, zc), SCREW_HOLE_D, x0 - 0.1, x0 + PLATE_T + 0.1),
                            s.cyl("t_pcb", "X", (0, yr, zc), PLATE_CBORE_D, x0 + PLATE_T - PLATE_CBORE, x0 + PLATE_T + 0.1)])
    s.hexprism("nut", (C["nut"][0], C["nut"][1]), yr, zc, dr["nut_af"] / 2, angle=0.0)
    s.cyl("t_nbore", "X", (0, yr, zc), dr["screw_d"] + 0.05, C["nut"][0] - 0.1, C["nut"][1] + 0.1)
    s.cut("nut", ["t_nbore"])
    s.cyl("drive_screw", "X", (0, yr, zc), dr["screw_d"], 1.0, C["x_tip"])
    rs["plunger_len"] = old
    return {"printed": ["coupon_bore", "coupon_rear", "coupon_front_pad", "coupon_front_plug", "plunger_core", "plunger_nose", "plunger_plate"],
            "bore_len": round(L_bore, 2), "x_tip": round(C["x_tip"], 2), "stroke": stroke}
