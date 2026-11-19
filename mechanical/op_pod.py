# SPDX-License-Identifier: LicenseRef-OpenPatch
"""v0.1.0 INTEGRATED POD (`generate.py --variant v010`): ONE coherent model of all decisions up to 2026-11-19.  TEST PROJECT, water only, never on a person.

Axes: X = pod length (rear outer face x = 0, +X = dock mouth), Y = width (0..32), Z = up (0 = skin).  Every number is in params.json -> `pod`, `reservoir_frozen_v010`.

Architecture (spec 2a-2d, 3a-3e, 4b, 4c, 7a, 8a; owner requirement "exactly one rod"):
  * coaxial translating M1.6 screw on the bore axis = the ONLY rod; nut glued to the front face of the nut gear (gear_d); anti-rotation slot/tab; plunger pushed only (pressure fill);
  * motor in the REAR ZONE beside the screw tail, shaft pointing +X, gear_a (z16) meshes DIRECTLY with gear_d (z20): no idler, no side rod, no encoder lane;
  * angle magnet = diametric RING on the thrust sleeve behind the nut gear, TMAG5273 on the SENSOR board beside it (side-shaft, YZ angle);
  * closed CNC reservoir (wall 1.0, wide stadium bore, port offset to the dock axis), minimal fluid module (sandwich cap, no valve, underside septum, op_cap.py), dock insert on the frozen interface (op_dock.py);
  * boards: MAIN over the dock tunnel (+ wing over the cell), SENSOR board + USB board in the rear pocket, motor contact card, FPC spine under the reservoir; waterproof USB-C in the rear wall;
  * clear lid, engraved scale, piezo on the lid inner face, ePTFE vent, 0.5 mm main gasket.
"""
from __future__ import annotations

import copy
import math

from op_cmds import Script
from op_layout import stadium_area


# ----------------------------------------------------------------------------------------------------------------------------------- parameters
def prepare(p0: dict) -> dict:
    """Parameter set of the v010 build: the pod block overrides the bench-era numbers the reused builders (op_cap, op_dock, op_mould, op_shell) read."""
    p = copy.deepcopy(p0)
    P, fz = p["pod"], p["reservoir_frozen_v010"]
    p["mode"] = "bench"                       # selects the frozen dock interface / sandwich cap code paths of op_dock / op_cap
    p["v010_pod"] = True
    p["shell"]["height"] = P["height"]
    p["shell"]["width"] = 32.0
    rs = p["reservoir"]
    rs.update(w_in=fz["bore_w"], h_in=fz["bore_h"], wall=fz["wall"], dead=P["res"]["dead"], plunger_gap=P["res"]["plunger_gap"], plunger_len=P["res"]["plunger_len"])
    p["reservoir_frozen"] = {**p["reservoir_frozen"], **{k: fz[k] for k in ("bore_w", "bore_h", "wall", "end_wall", "port_d", "outer_w", "outer_h", "bore_corner_r")}}
    p["dock"]["y_c"] = P["dock"]["y_c"]
    p["dock"]["cap"]["spigot_len"] = P["dock"]["spigot_len"]
    p["velcro"]["y1"] = P["spine"]["y0"] - 0.5          # the Velcro recess stays clear of the spine channel (floor 0.55 + channel would leave 0.25 mm)
    # DFM (vendor hard floors, dfm_rules.json): fluid sandwich, plunger, inserts
    p["septum"]["d"] = P["fluid"]["septum_d"]            # d4 -> d3.2: the pocket d4.1 left 0.15 mm walls in the 4.4 mm block (SLA hard floor 0.4)
    cap = p["dock"]["cap"]
    cap["bore_d"] = P["fluid"]["needle_bore_d"]           # d1.0 x 2.9 (<= 3 x d, SLA hole rule); the d0.5 prime channel is only the short half groove
    cap["sandwich"]["spur_w"] = P["fluid"]["spur_w"]
    cap["sandwich"]["screws"]["pos"] = P["fluid"]["clamp_pos"]
    cap["sandwich"]["gasket"]["y_margin"] = P["fluid"]["gasket_y_margin"]      # -0.1: the recess runs out through the block side faces (no side wall: no thin step)
    cap["sandwich"]["gasket"]["y_max_rel"] = P["fluid"]["gasket_y_max_rel"]
    cap["sandwich"]["spur_depth"] = P["fluid"]["spur_depth"]
    p["seal"]["ring_b"] = P["plunger"]["ring_b"]                  # front groove 0.8 wide (slot hard floor 0.5, the 0.6 groove measured 0.4); front flange 0.41
    F = p["dock_interface_frozen"]                                 # v0.1.0 dock interface (decision recorded in V010.md): ledge 0.45 -> 0.50 (MJF hard floor), flange 0.43, floor pad 0.1 in the dock zone
    F["ledge_z"] = [0.0, P["dock"]["ledge_t"]]
    F["detent"] = {**F["detent"], "z": [P["dock"]["ledge_t"] - 0.05, P["dock"]["ledge_t"] + 0.35]}
    p["dock"]["cover"]["x_end_u"] = P["fluid"]["velcro_x_end_u"]   # the Velcro recess must stay >= 0.5 mm clear of the dock window (frozen datum 4.4)
    cap["sandwich"]["gasket"]["x"] = P["fluid"]["gasket_x"]          # recess 0.5 .. 3.9: >= 0.5 mm walls to both block faces (the bench 0.25 .. 4.3 left 0.1 mm)
    cap["sandwich"]["screws"]["head_depth"] = 0.0
    p["seal"]["purge"]["groove_w"] = P["plunger"]["purge_w"]
    p["dock"]["digit_w"] = P["insert"]["digit_w"]
    p["dock"]["digit_h"] = P["insert"]["digit_h"]
    p["variants"] = {k: {"stroke": 0.0} for k in P["sizes"]}
    p["spec"]["length_targets"] = dict(P["length_targets"])
    p["spec"]["max_height"] = 8.5
    return p


def motor_opt(p: dict) -> dict:
    P = p["pod"]["motor"]
    return P["options"][P["option"]]


# ----------------------------------------------------------------------------------------------------------------------------------- layout
def layout(p: dict, size: str) -> dict:
    P, sh, fz = p["pod"], p["shell"], p["reservoir_frozen_v010"]
    wall, H, W = sh["wall"], P["height"], sh["width"]
    R, dr, g, rg, tm = P["res"], P["drive"], P["motor"]["gear"], P["ring"], P["ring"]["tmag"]
    mo = motor_opt(p)
    w_in, h_in = fz["bore_w"], fz["bore_h"]
    A = stadium_area(w_in, h_in)
    stroke = P["volume_ul"][size] / A
    zc = wall + fz["outer_h"] / 2.0
    y_r = (R["y0"] + R["y1"]) / 2.0
    centre = g["module"] * (g["z_motor"] + g["z_screw"]) / 2.0 + g["centre_add"]
    y_m = y_r + P["motor"]["y_side"] * centre
    # --- rear zone: the motor stack decides the gear plane, unless a long stroke needs the screw tail room (nut front >= rear_min + stroke + engagement)
    nut_t = dr["nut_len"]
    gear_x1_motor = wall + 0.1 + mo["stack"] + g["clr"] + g["gear_t"]
    gear_x1_screw = dr["screw_rear_min_x"] + stroke + dr["engage_margin"] + 0.5 - dr["nut_glue"]
    gear_x1 = max(gear_x1_motor, gear_x1_screw)
    gear_x0 = gear_x1 - g["gear_t"]
    x_mrear = gear_x0 - g["clr"] - mo["stack"]                       # rear boss tip
    x_gh1 = x_mrear + mo["stack"] - mo["boss_front"]                 # gearbox front face
    nut = (gear_x1 + dr["nut_glue"], gear_x1 + dr["nut_glue"] + nut_t)
    x_r0 = gear_x1 + dr["nut_to_res"]
    xrear_full = x_r0 + R["dry_strip"]
    xrear_empty = xrear_full + stroke
    x_in0 = x_r0 + R["dry_strip"]
    x_in1 = xrear_full + stroke + R["plunger_len"] + R["dead"]
    x_r1 = x_in1 + fz["end_wall"]
    tail_u = p["dock_interface_frozen"]["tail_u"]
    length = x_r1 + tail_u
    dsock = dr["socket_depth"]
    x_tip = xrear_full + dsock - 0.05
    screw_rear_full = nut[1] - (nut_t + dr["engage_margin"]) - stroke - 0.5
    # --- stack behind the nut gear: bush | ring magnet | gear_d
    ring_x1 = gear_x0 - rg["gap_to_gear"]
    ring_x0 = ring_x1 - rg["t"]
    bush_x1 = ring_x0 - rg["gap_to_bush"]
    bush_x0 = bush_x1 - dr["bush_len"]
    from op_dock import dock_geometry
    D = dock_geometry(p, x_r1, wall)
    zi = H - wall
    L = {
        "mode": "bench", "variant": size, "v010_pod": True, "length": length, "width": W, "height": H, "wall": wall, "stroke": stroke, "area": A,
        "z_axis": zc, "y_r": y_r, "y_m": y_m, "gear_centre": centre, "x_r0": x_r0, "x_r1": x_r1, "x_in0": x_in0, "x_in1": x_in1, "x_end": length - wall, "z_top_inner": zi,
        "res_w_out": fz["outer_w"], "res_h_out": fz["outer_h"], "res_y": [R["y0"], R["y1"]], "port_y": D["y_c"],
        "xrear_full": xrear_full, "xrear_empty": xrear_empty, "gear_x0": gear_x0, "gear_x1": gear_x1, "x_mrear": x_mrear, "x_gh1": x_gh1,
        "nut": list(nut), "x_tip": x_tip, "screw_rear_full": screw_rear_full, "screw_rear_empty": screw_rear_full + stroke,
        "ring": [ring_x0, ring_x1], "bush": [bush_x0, bush_x1], "dock": D, "tail_u": tail_u, "rear_zone": x_r0,
        "gear_limit": "motor stack" if gear_x1_motor >= gear_x1_screw else "screw tail",
    }
    # --- lid screws: -Y lane every <= pitch_max, plus two on the +Y side (rear, front)
    sc = P["screws"]
    xs0, xs1 = 5.2, length - 5.3                      # the rounded corners (R4) end at x = 4 / L - 4: the -Y lane screws stay on the straight wall
    n = int(math.ceil((xs1 - xs0) / sc["pitch_max"]))
    xs = [xs0 + k * (xs1 - xs0) / n for k in range(n + 1)]
    L["screws"] = [{"x": round(x, 3), "y": sc["lane_y"]} for x in xs] + [{"x": q[0], "y": q[1]} for q in sc["plus_y"]]
    return L


def u2x(L: dict, u: float) -> float:
    return L["x_r1"] + u


# ----------------------------------------------------------------------------------------------------------------------------------- electronics geometry
def geometry(p: dict, L: dict) -> dict:
    """Positions of boards / cell / USB-C / sensor / spine in pod coordinates (also the electronics interface, see layout_json)."""
    P = p["pod"]
    wall, zc, xr = L["wall"], L["z_axis"], L["x_r1"]
    bd, cl, us, tm, ring, mc, sp = P["board"], P["cell"], P["usb"], P["ring"]["tmag"], P["ring"], P["mcard"], P["spine"]
    mo = motor_opt(p)
    z0 = bd["z0"]
    ztop = z0 + bd["t"]
    G: dict = {"z0": z0, "ztop": ztop}
    # ---- MAIN board: tunnel part + wing over the cell + tongue over the spine shelf
    ur = L["tail_u"] - 1.0 - bd["right_gap"]            # inner face of the end wall is tail_u - 0.9
    ul = bd["u_left"]
    ty0, ty1 = bd["tunnel_y"]
    wy0, wy1 = bd["wing_y"]
    shelf_u = [2.4, 4.9]
    tong_u0 = shelf_u[0] - 0.4
    tong_u1 = ul + 3.6
    y_hi = 31.0
    pts = [(ul, ty0), (ur, ty0), (ur, wy1), (tong_u1, wy1), (tong_u1, y_hi), (tong_u0, y_hi), (tong_u0, wy1), (ul, wy1)]
    G["board_outline_u"] = [[round(a, 3), round(b, 3)] for a, b in pts]
    G["board_outline_pod"] = [[round(xr + a, 3), round(b, 3)] for a, b in pts]
    area = 0.0
    for i in range(len(pts)):
        x1_, y1_ = pts[i]
        x2_, y2_ = pts[(i + 1) % len(pts)]
        area += x1_ * y2_ - x2_ * y1_
    G["board_area_mm2"] = round(abs(area) / 2.0, 1)
    G["board_holes_u"] = [[ur - 0.8, 21.0], [ur - 0.8, 24.2]]       # locating pins on the floor posts (right end, beside the cell)
    # ---- cell bay (strip beside the tunnel, full height; the board lies over it)
    cell_z0 = wall + cl["foam_t"]
    cell_top = cell_z0 + cl["t"]
    cx0, cx1 = xr + cl["u0"], xr + cl["u0"] + cl["l"]
    cy0, cy1 = cl["y0"], cl["y0"] + cl["w"]
    yc_cell = (cy0 + cy1) / 2
    G["cell"] = {"x": [round(cx0, 3), round(cx1, 3)], "y": [cy0, cy1], "z": [round(cell_z0, 3), round(cell_top, 3)]}
    G["cell_pads"] = [{"c": [round(cx0 + cl["pad_u"], 3), round(yc_cell + sg * cl["pad_dy"] / 2, 3)], "size": cl["pad"], "z": [round(cell_top, 3), round(cell_top + 0.05, 3)]} for sg in (-1, 1)]
    G["cell_ribs"] = [{"x": [cx0 - 0.1, cx1 + 0.1], "y": [cy0 - 0.1 - cl["rib_t"], cy0 - 0.1], "h": cl["rib_h"]},
                      {"x": [cx0 - 0.1, cx1 + 0.1], "y": [cy1 + 0.1, cy1 + 0.1 + cl["rib_t"]], "h": cl["rib_h"]}]
    G["spring_gap"] = round(z0 - (cell_top + 0.05), 3)
    # ---- spine: floor channel from the motor card to the shelf at the MAIN tongue
    spy = [sp["y0"], sp["y0"] + sp["w"]]
    pin_x = L["x_gh1"] - 11.0                               # NFP terminal pins 11 mm behind the gearbox front face
    card_x = [round(pin_x - 2.0, 3), round(pin_x + 2.0, 3)]
    zm = zc
    y_blk1 = L["y_m"] + mo["d"] / 2 + 0.65
    y_pin_tip = y_blk1 + 1.05
    spring_free = mc["spring"][2]
    comp = 0.4
    y_face = y_pin_tip + (spring_free - comp)           # card face: the spring (free height 0.8) is compressed by 0.4 against the pin tips
    G["motor_card"] = {"x": card_x, "y": [round(y_face, 3), round(y_face + mc["t"], 3)], "z": mc["z"], "pin_tip_y": round(y_pin_tip, 3), "compression_mm": comp,
                       "spring": {"x_pitch": 1.2, "z_centres": [round(zm + k * 1.2, 3) for k in (-1.5, -0.5, 0.5, 1.5)], "free_mm": spring_free},
                       "slot_ribs_y": [round(y_face - 0.2, 3), round(y_face + mc["t"] + 0.2, 3)]}
    G["motor_pin_x"] = round(pin_x, 3)
    G["spine"] = {"y": spy, "x": [round(card_x[1] + 0.8, 3), round(xr + shelf_u[0] - 0.1, 3)], "z": [wall - sp["channel_depth"] + 0.02, wall - sp["channel_depth"] + 0.02 + sp["t"]],
                  "channel_x": [round(card_x[1] + 0.7, 3), round(xr + shelf_u[0] + 0.05, 3)], "channel_z0": round(wall - sp["channel_depth"], 3),
                  "shelf": {"x": [round(xr + shelf_u[0], 3), round(xr + shelf_u[1], 3)], "y": [spy[0] - 0.2, 31.0], "z_top": 4.4},
                  "springs": {"x": [round(xr + 3.0, 3), round(xr + 4.5, 3)], "y": [spy[0] + 0.6, spy[1] - 0.6], "z": [4.5, z0]}}
    # ---- rear pocket: USB-C in the rear wall, USB board, SENSOR board + TMAG + ring magnet
    zu = us["z_c"]
    ux0 = 0.75
    ux1 = ux0 + us["d"]
    G["usb"] = {"x": [ux0, round(ux1, 3)], "y": [round(us["y_c"] - us["w"] / 2, 3), round(us["y_c"] + us["w"] / 2, 3)], "z": [round(zu - us["h"] / 2, 3), round(zu + us["h"] / 2, 3)],
                "open_x": [-0.1, round(wall + 0.1, 3)], "open_y": [round(us["y_c"] - us["open_w"] / 2, 3), round(us["y_c"] + us["open_w"] / 2, 3)],
                "open_z": [round(zu - us["open_h"] / 2, 3), round(zu + us["open_h"] / 2, 3)],
                "flange": {"x": [round(wall + us["gasket_t"], 3), round(wall + us["gasket_t"] + 0.5, 3)],
                           "y": [round(us["y_c"] - us["open_w"] / 2 - us["gasket_w"], 3), round(us["y_c"] + us["open_w"] / 2 + us["gasket_w"], 3)], "z": [wall + 0.05, 4.9]},
                "gasket": {"x": [wall, round(wall + us["gasket_t"], 3)], "y": [round(us["y_c"] - us["open_w"] / 2 - us["gasket_w"], 3), round(us["y_c"] + us["open_w"] / 2 + us["gasket_w"], 3)], "z": [wall + 0.05, 4.9]},
                "board": {"x": [round(ux1, 3), round(ux1 + us["board_len"], 3)], "y": [round(us["y_c"] - us["w"] / 2 - 0.3, 3), round(us["y_c"] + us["w"] / 2 + 0.3, 3)],
                          "z": [round(zu - us["board_t"] / 2, 3), round(zu + us["board_t"] / 2, 3)]}}
    rx0, rx1 = L["ring"]
    bz0 = tm["board_z0"]
    t_cx = (rx0 + rx1) / 2 - 0.65
    t_cy = L["y_r"] - ring["od"] / 2 - tm["gap"] - tm["pkg"][1] / 2
    bx1 = rx1 + 0.0
    G["sensor"] = {"board": {"x": [round(bx1 - tm["board_len"], 3), round(bx1, 3)], "y": [round(t_cy - tm["pkg"][1] / 2 - (tm["board_w"] - tm["pkg"][1]) + 0.0, 3), round(t_cy + tm["pkg"][1] / 2 + 0.15, 3)],
                             "z": [bz0, round(bz0 + tm["board_t"], 3)]},
                   "tmag": {"c": [round(t_cx, 3), round(t_cy, 3)], "x": [round(t_cx - tm["pkg"][0] / 2, 3), round(t_cx + tm["pkg"][0] / 2, 3)],
                            "y": [round(t_cy - tm["pkg"][1] / 2, 3), round(t_cy + tm["pkg"][1] / 2, 3)], "z": [round(bz0 + tm["board_t"], 3), round(bz0 + tm["board_t"] + tm["pkg"][2], 3)],
                            "angle_plane": "YZ (ANGLE_EN = 10b), side-shaft: sensor beside the ring, the ring axis is parallel to X",
                            "distance_axis_to_sensor_mm": round(L["y_r"] - t_cy, 3)}}
    G["sensor"]["posts"] = [[round(G["sensor"]["board"]["x"][0] + 0.8, 3), round(G["sensor"]["board"]["y"][0] + 0.8, 3)],
                            [round(G["sensor"]["board"]["x"][0] + 0.8, 3), round(G["sensor"]["board"]["y"][1] - 0.8, 3)],
                            [round(G["sensor"]["board"]["x"][1] - 0.8, 3), round(G["sensor"]["board"]["y"][0] + 0.8, 3)]]
    # ---- top side parts on MAIN
    r = bd["radio"]
    G["radio"] = {"x": [round(xr + r["u"][0], 3), round(xr + r["u"][1], 3)], "y": r["y"], "z": [ztop, ztop + r["h"]]}
    sw = bd["switch"]
    G["switch"] = {"c": [round(xr + sw["u"], 3), sw["y"]], "size": sw["size"], "z": [ztop, ztop + sw["size"][2]]}
    pz = P["piezo"]
    G["piezo"] = {"x": [pz["x0"], pz["x0"] + pz["l"]], "y": [pz["y0"], pz["y0"] + pz["w"]], "z": [L["z_top_inner"] - pz["h"], L["z_top_inner"]],
                  "port": [round(pz["x0"] + pz["l"] / 2, 3), round(pz["y0"] + pz["w"] / 2, 3)]}
    G["vent"] = {"c": [P["vent"]["x"], P["vent"]["y"]], **{k: P["vent"][k] for k in ("hole_d", "recess_d", "recess_depth")}}
    return G


# ----------------------------------------------------------------------------------------------------------------------------------- builders
def build_reservoir(s: Script, p: dict, L: dict) -> None:
    fz = p["reservoir_frozen_v010"]
    zc, y_r = L["z_axis"], L["y_r"]
    s.stadium("reservoir", (L["x_r0"], L["x_r1"]), y_r, zc, fz["outer_w"], fz["outer_h"])
    s.stadium("t_chamber", (L["x_r0"] - 0.1, L["x_in1"]), y_r, zc, fz["bore_w"], fz["bore_h"])
    port = s.cyl("t_rport", "X", (0, L["port_y"], zc), fz["port_d"], L["x_in1"] - 0.1, L["x_r1"] + 0.1)
    s.cut("reservoir", ["t_chamber", port])


def build_plunger(s: Script, p: dict, L: dict) -> None:
    from op_seal import bead_bodies, ring_range, variant
    rs, sl, dr = p["reservoir"], p["seal"], p["pod"]["drive"]
    zc, y_r, xr = L["z_axis"], L["y_r"], L["xrear_full"]
    c = rs["plunger_clr"]
    wc, hc = rs["w_in"] - 2 * c, rs["h_in"] - 2 * c
    gd = sl["groove_depth"]
    xf = xr + rs["plunger_len"]
    s.stadium("plunger_core", (xr, xf), y_r, zc, wc, hc)
    tools = []
    v0 = variant(p)
    for k, which in enumerate(v0["rings"]):           # only the grooves of the active seal variant (S2: the front groove): no empty rear groove, flanges stay solid
        a, b = ring_range(p, which)
        s.stadium_ring(f"t_gr{k}", (xr + a, xr + b), y_r, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
        tools.append(f"t_gr{k}")
    tools.append(s.cyl("t_psock", "X", (0, y_r, zc), 2.5, xr - 0.1, xr + dr["socket_depth"]))
    pg = sl["purge"]
    x0g = xf - pg["groove_d"]
    tools.append(s.box("t_pg_y", (x0g, xf + 0.1), (y_r - wc / 2 - 0.1, y_r + wc / 2 + 0.1), (zc - pg["groove_w"] / 2, zc + pg["groove_w"] / 2)))
    tools.append(s.box("t_pg_z", (x0g, xf + 0.1), (y_r - pg["groove_w"] / 2, y_r + pg["groove_w"] / 2), (zc - hc / 2 - 0.1, zc + hc / 2 + 0.1)))
    tools.append(s.cyl("t_pg_c", "X", (0, y_r, zc), pg["centre_d"], x0g, xf + 0.1))
    s.cut("plunger_core", tools)
    s.box("t_ptab", (xr + dr["socket_depth"] - dr["tab_len"], xr + dr["socket_depth"] + 0.05), (y_r - dr["tab_t"] / 2, y_r + dr["tab_t"] / 2), (zc - 1.5, zc + 1.5))      # chord tab fused into the socket wall (no slots < 0.5)
    s.join("plunger_core", ["t_ptab"])
    v = variant(p)
    ao = sl["assembly_gap"]
    for which in v["rings"]:
        nm = "seal_" + which
        a, b = ring_range(p, which)
        parts = bead_bodies(s, nm, xr + a, xr + b, y_r, zc, wc, hc, rs["w_in"] - ao, rs["h_in"] - ao, v["land"])
        s.join(nm, parts[1:])
        s.stadium(f"t_{nm}_floor", (xr + a - 0.1, xr + b + 0.1), y_r, zc, wc - 2 * gd, hc - 2 * gd)
        s.cut(nm, [f"t_{nm}_floor"])


def build_drive(s: Script, p: dict, L: dict) -> None:
    """Coaxial drive + motor beside it.  Bodies: drive_screw (the ONLY rod), nut, gear_d, thrust_sleeve2, bush_dry2, ring_magnet, motor parts, gear_a."""
    P = p["pod"]
    dr, g, rg = P["drive"], P["motor"]["gear"], P["ring"]
    mo = motor_opt(p)
    zc, y_r, y_m = L["z_axis"], L["y_r"], L["y_m"]
    gx0, gx1 = L["gear_x0"], L["gear_x1"]
    mod = g["module"]
    # screw with the hacksaw slot for the plunger tab
    s.cyl("drive_screw", "X", (0, y_r, zc), dr["screw_d"], L["screw_rear_full"], L["x_tip"])
    s.cut("drive_screw", [s.box("t_sslot", (L["x_tip"] - dr["tab_len"], L["x_tip"] + 0.1), (y_r - dr["slot_t"] / 2, y_r + dr["slot_t"] / 2), (zc - 1.0, zc + 1.0))])
    nx0, nx1 = L["nut"]
    s.hexprism("nut", (nx0, nx1), y_r, zc, dr["nut_af"] / 2, angle=0.0)
    s.cyl("t_nbore", "X", (0, y_r, zc), dr["screw_d"] + 0.05, nx0 - 0.1, nx1 + 0.1)
    s.cut("nut", ["t_nbore"])
    bx0, bx1 = L["bush"]
    s.tube("bush_dry2", "X", (0, y_r, zc), dr["bush_od"], dr["bush_id"], bx0, bx1)
    s.tube("thrust_sleeve2", "X", (0, y_r, zc), dr["sleeve_od"], dr["screw_d"] + 0.1, bx1 + dr["sleeve_gap"], gx1)
    s.cyl("gear_d", "X", (0, y_r, zc), mod * (g["z_screw"] + 2), gx0, gx1)
    s.cyl("t_gdb", "X", (0, y_r, zc), dr["sleeve_od"] + 0.04, gx0 - 0.1, gx1 + 0.1)
    s.cut("gear_d", ["t_gdb"])
    rpd = P["drive"]["rear_plug_d"]
    s.cyl("rear_plug", "X", (0, y_r, zc), rpd, 0.0, L["wall"])
    s.box("t_plug_up", (0.0, L["wall"]), (y_r - rpd / 2, y_r + rpd / 2), (zc, p["shell"]["lap_high"]))
    s.join("rear_plug", ["t_plug_up"])          # silicone stopper in the screw insertion hole of the rear wall (dry zone, splash seal only)
    rx0, rx1 = L["ring"]
    s.tube("ring_magnet", "X", (0, y_r, zc), P["ring"]["od"], P["ring"]["id"], rx0, rx1)
    # motor (envelope; the real NFP model replaces it in the *_real.sc pass): rear boss, motor, gearhead, front boss, shaft, terminal block + pins (block facing +Y)
    x_rb0 = L["x_mrear"]
    x_m0 = x_rb0 + mo["tail"]
    x_m1 = x_m0 + mo["motor_len"]
    x_g1 = L["x_gh1"]
    x_fb1 = x_g1 + mo["boss_front"]
    s.cyl("motor_rear_boss", "X", (0, y_m, zc), mo["rear_boss_d"], x_rb0, x_m0)
    s.cyl("motor", "X", (0, y_m, zc), mo["d"], x_m0, x_m1)
    s.cyl("gearhead", "X", (0, y_m, zc), mo["d"], x_m1, x_g1)
    s.cyl("motor_boss", "X", (0, y_m, zc), mo["boss_d"], x_g1, x_fb1)
    s.cyl("motor_shaft", "X", (0, y_m, zc), mo["shaft_d"], x_fb1, gx1 + 0.2)
    pin_x = L["x_gh1"] - 11.0
    yb0 = y_m + mo["d"] / 2
    s.box("motor_term", (pin_x - 1.7, pin_x + 1.7), (yb0, yb0 + 0.65), (zc - 2.3, zc + 2.3))
    pins = [s.box("motor_pins" if k == 0 else f"t_pin{k}", (pin_x - 0.15, pin_x + 0.15), (yb0 + 0.65 - 0.01, yb0 + 0.65 + 1.05), (zc + dz - 0.15, zc + dz + 0.15))
            for k, dz in enumerate((-1.8, -0.6, 0.6, 1.8))]
    s.join(pins[0], pins[1:])
    s.cyl("gear_a", "X", (0, y_m, zc), mod * (g["z_motor"] + 2), gx0, gx1)
    s.cyl("t_gab", "X", (0, y_m, zc), mo["shaft_d"] + 0.02, gx0 - 0.1, gx1 + 0.1)
    s.cut("gear_a", ["t_gab"])


def build_fluid(s: Script, p: dict, L: dict) -> None:
    from op_cap import build_cap, build_oring, build_septum
    from op_dock import build_needle
    build_cap(s, p, L)
    build_septum(s, p, L)
    build_oring(s, p, L)
    build_needle(s, p, L)


def build_dock_parts(s: Script, p: dict, L: dict) -> None:
    """Dock insert (frozen interface) + the dummy cannula head with its magnet (fit-test fixture) + the dock hall."""
    from op_dock import build_adapter, build_insert
    L2 = dict(L, wall=L["wall"] + p["pod"]["dock"]["floor_pad"])         # the dock zone floor is 1.0 mm thick (pad), the insert interface is defined from it
    build_insert(s, p, L2, "dock_insert")
    ad = p["bench"]["adapter"]
    D = L["dock"]
    s.cyl("dock_magnet", "Z", (D["x_d"] + ad["magnet_dx"], D["y_c"], 0), ad["magnet_d"], ad["lug_top"] - ad["magnet_t"], ad["lug_top"])
    build_adapter(s, p, L, name="cannula_adapter", lug=True)
    hx = D["x_d"] + ad["magnet_dx"]
    hp = p["bench"]["dock"]["pkg"]
    G = L["geo"]
    s.box("hall_dock", (hx - hp[0] / 2, hx + hp[0] / 2), (D["y_c"] - hp[1] / 2, D["y_c"] + hp[1] / 2), (G["z0"] - hp[2], G["z0"]))


def build_electronics(s: Script, p: dict, L: dict) -> None:
    G = L["geo"]
    P = p["pod"]
    wall = L["wall"]
    z0, ztop = G["z0"], G["ztop"]
    from op_shell import build_gasket  # noqa: F401  (gasket built by the caller)
    pts = [tuple(q) for q in G["board_outline_pod"]]
    s.polyprism("pod_board", pts, (z0, ztop))
    xr = L["x_r1"]
    holes = [s.cyl(f"t_bh{i}", "Z", (xr + h[0], h[1], 0), P["pins"]["hole_d"], z0 - 0.1, ztop + 0.1) for i, h in enumerate(G["board_holes_u"])]
    s.cut("pod_board", holes)
    r = G["radio"]
    s.box("radio", tuple(r["x"]), tuple(r["y"]), tuple(r["z"]))
    sw = G["switch"]
    s.box("switch", (sw["c"][0] - sw["size"][0] / 2, sw["c"][0] + sw["size"][0] / 2), (sw["c"][1] - sw["size"][1] / 2, sw["c"][1] + sw["size"][1] / 2), tuple(sw["z"]))
    pz = G["piezo"]
    s.box("piezo", tuple(pz["x"]), tuple(pz["y"]), tuple(pz["z"]))
    # cell, foam, pads, springs
    c = G["cell"]
    s.box("bat_foam", tuple(c["x"]), tuple(c["y"]), (wall, c["z"][0]))
    s.box("battery", tuple(c["x"]), tuple(c["y"]), tuple(c["z"]))
    cl = P["cell"]
    for nm, pd in (("p", G["cell_pads"][0]), ("n", G["cell_pads"][1])):
        px, py = pd["c"]
        s.box(f"bat_pad_{nm}", (px - pd["size"][0] / 2, px + pd["size"][0] / 2), (py - pd["size"][1] / 2, py + pd["size"][1] / 2), tuple(pd["z"]))
        hs = cl["spring"][0] / 2
        s.box(f"spring_{nm}", (px - hs, px + hs), (py - hs, py + hs), (pd["z"][1], z0))
    # USB-C
    u = G["usb"]
    s.box("usb_conn", tuple(u["x"]), tuple(u["y"]), tuple(u["z"]))
    f = u["flange"]
    s.box("t_usb_fl", tuple(f["x"]), tuple(f["y"]), tuple(f["z"]))
    s.join("usb_conn", ["t_usb_fl"])
    gk = u["gasket"]
    s.box("usb_gasket", tuple(gk["x"]), tuple(gk["y"]), tuple(gk["z"]))
    s.box("t_ug_in", (gk["x"][0] - 0.1, gk["x"][1] + 0.1), tuple(u["open_y"]), tuple(u["open_z"]))
    s.cut("usb_gasket", ["t_ug_in"])
    s.box("usb_board", tuple(u["board"]["x"]), tuple(u["board"]["y"]), tuple(u["board"]["z"]))
    # SENSOR board, TMAG, motor contact card + 4 springs, spine
    sn = G["sensor"]
    s.box("sensor_board", tuple(sn["board"]["x"]), tuple(sn["board"]["y"]), tuple(sn["board"]["z"]))
    s.cut("sensor_board", [s.cyl(f"t_sbh{i}", "Z", (q[0], q[1], 0), P["pins"]["hole_d"], sn["board"]["z"][0] - 0.1, sn["board"]["z"][1] + 0.1) for i, q in enumerate(sn["posts"])])
    tm = sn["tmag"]
    s.box("hall_tmag", tuple(tm["x"]), tuple(tm["y"]), tuple(tm["z"]))
    mc = G["motor_card"]
    s.box("motor_card", tuple(mc["x"]), tuple(mc["y"]), tuple(mc["z"]))
    msp = P["mcard"]["spring"]
    for k, zz in enumerate(mc["spring"]["z_centres"]):
        xx = L["x_gh1"] - 11.0
        s.box(f"mspring_{k + 1}", (xx - msp[0] / 2, xx + msp[0] / 2), (mc["pin_tip_y"], mc["y"][0]), (zz - msp[1] / 2, zz + msp[1] / 2))      # compressed state
    sp = G["spine"]
    s.box("spine_fpc", tuple(sp["x"]), tuple(sp["y"]), tuple(sp["z"]))
    sh = sp["shelf"]
    s.box("t_sp_riser", (sh["x"][0] - P["spine"]["t"] - 0.05, sh["x"][0] - 0.05), tuple(sp["y"]), (sp["z"][0], sh["z_top"] + P["spine"]["t"]))
    s.box("t_sp_top", (sh["x"][0] - 0.15, sp["springs"]["x"][1] + 0.5), tuple(sp["y"]), (sh["z_top"], sh["z_top"] + P["spine"]["t"]))
    s.join("spine_fpc", ["t_sp_riser", "t_sp_top"])
    ss = sp["springs"]
    s.box("spine_springs", tuple(ss["x"]), tuple(ss["y"]), (sh["z_top"] + P["spine"]["t"], z0))
