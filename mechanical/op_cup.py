# SPDX-License-Identifier: LicenseRef-OpenPatch
"""OpenPatch v0.1.0 "cup" pod (`generate.py --variant v010 --drive cup`): one rotating rod on the tank axis, plunger = long cup.

TEST PROJECT: never worn, never filled with anything but water (CLAUDE.md, DISCLAIMER.md).

Concept B (user decision), everything else of the earlier drives is removed (no second rod, carriage, tongue, idler, third gear):
  * ONE M1.6 x 0.35 rod on the tank axis, rotating and axially fixed (bush behind the gear pair; sleeve bears on the bush front face, the rod-end magnet
    bears on the bush rear face), driven by the NFP-608-26.45 through exactly two gears (GHW module 0.3, z16 on the motor -> z20 on the rod).
  * PLUNGER = long cup: stadium 15.8 x 4.8, two cast lip seals at the CLOSED front end, blind axial bore d2.0 with a brass nut in a hex pocket at the rear.
    The rod screws INTO the plunger from behind and never passes through it; the stadium shape stops the plunger from turning.
  * TANK = frozen CNC bore (16 x 5) with closed walls (no slot), open dry end, ONE outlet port (d2.0) in the front end wall.
  * Dock tunnel BESIDE the tank (y strip next to the tank) running the whole pod length, mouth in the rear end wall; end cap + needle at the front end.
    The frozen dock insert / interface is reused unchanged (same x0_u, flange pocket, arms) in the frame xa = wall.
  * Fill septum on the UNDERSIDE of the end cap (fill needle through a floor hole), inside the area covered by the Velcro patch (spec 3e); no check valve (spec 3c).
  * Battery, USB-C and boards are RESERVED keep-out boxes (ko_*), no PCB design.

Frame: x = 0 at the OUTLET (front) end, +X toward the dry end (rod stack, motor, USB-C); y = 0 at the -Y wall; z = 0 skin side.
The pod axes are the bench axes rotated by 180 degrees about Z (the dome still slides in from the mouth toward the needle: here the mouth is at +X).
"""
from __future__ import annotations

import copy
import math

from op_cmds import Script
import op_cup_dock as dock
from op_layout import stadium_area

HEX_APOTHEM_ANGLE = 0.0


def prepare(p0: dict) -> dict:
    """Cup-pod overrides: pod width W -> tank (lane 1) and lane 2 widths, un-frozen tank bore, strokes from the bore area, dock head estimate."""
    p = copy.deepcopy(p0)
    c, sh = p["cup"], p["shell"]
    w, W, rz = sh["wall"], c["width"], c["reservoir"]
    lane2 = c["battery"]["w"] + 0.4                                       # lane 2 = cell width + clearance
    c["lane2_inner"] = lane2
    outer = min(W - 2 * w - 0.1 - lane2, 2 * (W - w - 0.1 - c["motor_y_ext"] - w))
    outer = math.floor(outer * 10) / 10
    bore_w = round(outer - 2 * rz["wall"], 3)
    fz = p["reservoir_frozen"]
    fz.update({"bore_w": bore_w, "bore_h": rz["bore_h"], "wall": rz["wall"], "end_wall": rz["end_wall"], "port_d": rz["port_d"], "outer_w": outer, "outer_h": rz["bore_h"] + 2 * rz["wall"],
               "_comment": "CUP variant only (op_cup.prepare): un-frozen wide tank; bench keeps 16 x 5"})
    area = stadium_area(bore_w, rz["bore_h"])
    for v in c["sizes"]:
        p["variants"][v]["stroke"] = round(c["volume_ml"][v] * 1000.0 / area, 2)
    p["mode"], p["cup_active"] = "bench", True
    sh["width"], sh["height"] = W, c["height"]
    p["cup_bore_area"] = area
    p["reservoir"]["w_in"], p["reservoir"]["h_in"] = bore_w, rz["bore_h"]          # seal mould + CNC data follow the cup-pod bore
    dr = dict(p["drive"])
    dr.update(p["drive_presets"][dr.get("active_preset") or "nfp_608_26"])
    p["drive_nfp"] = dr
    return p


def geometry(p: dict, variant: str) -> dict:
    """Layout A (user sketch): motor column at the rear (x min) spanning both lanes; lane 1 (-Y side): gear B + rod -> cup plunger -> tank -> front wall -> dock at the right end;
    lane 2 (+Y side): battery, boards, USB-C, length-matched.  x = 0 rear outer face, y = 0 lane-1 outer wall, z = 0 skin side."""
    c, g, pl, bu, mg, tm, co = p["cup"], p["cup"]["gears"], p["cup"]["plunger"], p["cup"]["bush"], p["cup"]["magnet"], p["cup"]["tmag"], p["cup"]["collar"]
    sh, fz, dr = p["shell"], p["reservoir_frozen"], p["drive_nfp"]
    w, W, H = sh["wall"], sh["width"], sh["height"]
    s = p["variants"][variant]["stroke"]
    res_w, res_h = fz["outer_w"], fz["outer_h"]
    zc, y_r = w + res_h / 2, w + res_w / 2
    dk, fl = c["dock"], c["fill"]
    r_in = sh["corner_r"] - w

    def corner_clear(y_edge: float) -> float:
        dy = y_edge - (W - w - r_in)
        return 0.0 if dy <= 0 else r_in - math.sqrt(max((r_in - 0.05) ** 2 - dy ** 2, 0.0))
    y_g0, y_g1 = y_r + 1.2, y_r + g["bevel_back"]
    y_boss0 = y_g1 + g["clr_boss"]
    y_body0 = y_boss0 + dr["boss_front"]
    y_gh1 = y_body0 + dr["gearhead_len"]
    y_mo1 = y_gh1 + dr["motor_len"]
    y_tail1 = y_mo1 + dr["motor_tail"]
    xc = w + dr["motor_d"] / 2 + 0.1 + corner_clear(y_mo1)                 # motor column centre (axis Y); nothing behind it
    x_gb0, x_gb1 = xc + 1.2, xc + g["bevel_back"]                          # rod miter gear (rod ends at its rear face)
    x_m0, x_m1 = xc + 1.2 - mg["t"], xc + 1.2                               # magnet on gear B's rear face
    x_h0, x_h1 = xc - 1.8, xc - 1.8 + tm["pkg"][0]                          # TMAG beside the magnet (-Y), tiny sensor tab
    ty = y_r - mg["d"] / 2 - tm["gap"] - tm["pkg"][1] / 2
    x_b0 = x_gb1 + bu["sleeve_gap"]
    x_b1 = x_b0 + bu["len"]
    x_col0 = x_b1 + co["gap"]
    x_col1 = x_col0 + co["len"]
    x_dry = x_col1 + g["clr_tank"]
    nut_zone = p["drive"]["nut_len"] + pl["nut_recess"]
    L_pl = pl["front_wall"] + pl["tip_clear_full"] + pl["tip_in_nut_empty"] + s + nut_zone
    x_pr = x_dry + pl["dry_in"]                  # plunger rear face at FULL
    x_pf_full = x_pr + L_pl                      # plunger front face at FULL
    x_pf_empty = x_pf_full + s
    x_in = x_pf_empty + pl["dead"]               # bore front face
    x_t0 = x_in + fz["end_wall"]                 # tank front face (outlet side)
    x_tip = x_pr + nut_zone + s + pl["tip_in_nut_empty"]
    x_s = x_t0 - 1.6
    y_s = y_r + fl["septum_dy"]
    K = dock.layout(p, x_t0, y_r)
    bat, u, bd = c["battery"], c["usb"], c["board"]
    xl2 = xc + 3.4
    length = max(K["x_far"] + w, xl2 + bat["l"] + 3.1 + w)    # lane 2 (cell + USB-C on the +Y wall + corner) must fit; lane 1 sets the minimum
    lane2_y = [w + res_w + 0.2, W - w - 0.1]
    bat, u, bd = c["battery"], c["usb"], c["board"]
    x_l2 = xl2
    L = {"variant": variant, "stroke": s, "length": length, "width": W, "height": H, "wall": w, "zc": zc, "y_r": y_r, "res_w_out": res_w, "res_h_out": res_h,
         "xc": xc, "x_dry": x_dry, "x_pr": x_pr, "x_pf_full": x_pf_full, "x_pf_empty": x_pf_empty, "x_in": x_in, "x_t0": x_t0, "x_tip": x_tip, "x_s": x_s, "y_s": y_s, "L_pl": L_pl, "nut_zone": nut_zone,
         "tank_len": x_t0 - x_dry, "collar": [x_col0, x_col1], "gear_b": [x_gb0, x_gb1], "gear_a_y": [y_g0, y_g1], "bush": [x_b0, x_b1], "magnet": [x_m0, x_m1], "tmag": [x_h0, x_h1], "tmag_y": ty,
         "boss_y": [y_boss0, y_body0], "gearhead_y": [y_body0, y_gh1], "motor_y": [y_gh1, y_mo1], "rear_boss_y": [y_mo1, y_tail1], "y_motor_end": y_tail1,
         "rod_len": x_tip - x_gb0, "dock": K, "lane2_y": lane2_y, "bore_w": fz["bore_w"], "bore_h": fz["bore_h"], "bore_area": p["cup_bore_area"], "aspect": fz["bore_w"] / fz["bore_h"],
         "ratio": g["z_motor"] / g["z_rod"],
         "u_per_step": dr["screw_pitch"] * (g["z_motor"] / g["z_rod"]) / (dr["steps_per_rev"] * dr["gh_ratio"]) * p["cup_bore_area"] / 10.0}
    xb1 = x_l2 + bat["l"]
    tb = bat["z0"] + bat["t"]                                                    # cell top incl. 0.2 swell allowance (3.0 + 0.2)
    L["battery"] = {"x": [x_l2, xb1], "y": [lane2_y[0], lane2_y[0] + bat["w"]], "z": [bat["z0"], tb]}
    L["usb"] = {"x": [x_l2, x_l2 + u["w"]], "y": [W - w - u["d"], W - w], "z": [tb + 0.1, tb + 0.1 + u["h"]]}      # USB-C stacked ABOVE the front end of the cell
    L["board"] = {"x": [x_l2 + u["w"] + 0.3, xb1], "y": list(lane2_y), "z": [tb + 0.1, tb + 0.1 + 0.8 + 1.3]}      # main board above the rest of the cell
    xa0 = xb1 + 0.3
    L["aux"] = {"x": [xa0, max(xa0 + 0.5, length - 3.6)], "y": list(lane2_y), "z": [4.9, bd["z1"]]}
    L["io"] = {"x": [w + 3.1, x_dry - 0.2], "y": [w + 0.1, ty - tm["pkg"][1] / 2 - 0.2], "z": [w + 0.1, bd["z1"]]}
    hy = K["half"] + p["cup"]["dock"]["pocket_wall"] + 0.1
    L["side_a"] = {"x": [K["x_bf"], length - 3.8], "y": [w + 0.1, y_r - hy], "z": [w + 0.1, bd["z1"]]}
    L["side_b"] = {"x": [K["x_bf"], length - w - 0.3], "y": [y_r + hy, w + res_w - 0.1], "z": [w + 0.1, bd["z1"]]}
    L["dock_board"] = {"x": [K["x_d"] - 3.0, K["x_d"] + 3.0], "y": [y_r - 3.0, y_r + 3.0], "z": [5.3, 5.9]}
    L["lane2_fit"] = {"need_x": bat["l"] + 3.1, "have_x": length - w - x_l2}
    L["envelope"] = {"bbox_mm": [round(length, 2), W, H], "bbox_volume_ml": round(length * W * H / 1000.0, 2)}
    return L


def build_tank_and_plunger(s: Script, p: dict, L: dict) -> None:
    fz, sl, pl, dr, fl, hb = p["reservoir_frozen"], p["seal"], p["cup"]["plunger"], p["drive_nfp"], p["cup"]["fill"], p["cup"]["dock"]["hub"]
    zc, yr, K = L["zc"], L["y_r"], L["dock"]
    zn = K["z_n"]
    s.stadium("reservoir", (L["x_dry"], L["x_t0"]), yr, zc, L["res_w_out"], L["res_h_out"])
    s.stadium("t_chamber", (L["x_dry"] - 0.1, L["x_in"]), yr, zc, fz["bore_w"], fz["bore_h"])
    tools = ["t_chamber",
             s.cyl("t_oA", "X", (0, yr, zn), fl["out_d"], L["x_in"] - 0.1, L["x_t0"] + 0.1),                               # outlet straight through the front wall (+X)
             s.cyl("t_hseat", "X", (0, yr, zn), hb["d"] - hb["press"], K["x_hub"][0], L["x_t0"] + 0.1),                  # press-fit seat of the needle hub
             s.cyl("t_spk", "Z", (L["x_s"], L["y_s"], 0), fl["pocket_d"], 0.85, fl["pocket_top"]),                       # fill septum pocket on the underside
             s.cyl("t_fC", "X", (0, L["y_s"], fl["chan_z"]), fl["chan_d"], L["x_s"], L["x_in"] + 0.1)]                   # fill channel into the bore front lower corner
    s.cut("reservoir", tools)
    s.cyl("septum", "Z", (L["x_s"], L["y_s"], 0), fl["septum_d"], 0.9, 0.9 + fl["septum_h"])
    # plunger cup (FULL state): front face = x_pf_full (right), open rear = x_pr (left)
    c = pl["clr"]
    wc, hc = fz["bore_w"] - 2 * c, fz["bore_h"] - 2 * c
    gd = sl["groove_depth"]
    xr, xf, nz = L["x_pr"], L["x_pf_full"], L["nut_zone"]
    s.stadium("plunger_core", (xr, xf), yr, zc, wc, hc)
    tools = []
    for k, (a, b) in enumerate((pl["ring_front_a"], pl["ring_front_b"])):
        s.stadium_ring(f"t_gr{k}", (xf - b, xf - a), yr, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
        tools.append(f"t_gr{k}")
    tools.append(s.cyl("t_pbore", "X", (0, yr, zc), pl["bore_d"], xr - 0.1, xf - pl["front_wall"]))
    tools.append(s.hexprism("t_phex", (xr - 0.1, xr + nz), yr, zc, (dr["nut_af"] + pl["nut_clr"]) / 2, angle=HEX_APOTHEM_ANGLE))
    s.cut("plunger_core", tools)
    ao = sl["assembly_gap"]
    for k, nm in enumerate(("seal_a", "seal_b")):
        a, b = (pl["ring_front_a"], pl["ring_front_b"])[k]
        s.stadium_ring(nm, (xf - b, xf - a), yr, zc, fz["bore_w"] - ao, fz["bore_h"] - ao, wc - 2 * gd, hc - 2 * gd)
    s.hexprism("nut", (xr + pl["nut_recess"], xr + nz), yr, zc, dr["nut_af"] / 2, angle=HEX_APOTHEM_ANGLE)
    s.cyl("t_nbore", "X", (0, yr, zc), p["cup"]["rod"]["d"] + 0.05, xr - 0.1, xr + nz + 0.1)
    s.cut("nut", ["t_nbore"])


def build_drive(s: Script, p: dict, L: dict) -> None:
    g, bu, mg, tm, dr, rd, co = p["cup"]["gears"], p["cup"]["bush"], p["cup"]["magnet"], p["cup"]["tmag"], p["drive_nfp"], p["cup"]["rod"], p["cup"]["collar"]
    zc, yr, xc = L["zc"], L["y_r"], L["xc"]
    gb0, gb1 = L["gear_b"]
    ga0, ga1 = L["gear_a_y"]
    tip = g["tip_od"]
    s.cyl("rod", "X", (0, yr, zc), rd["d"], gb0, L["x_tip"])                       # rod ENDS at gear B
    s.tube("thrust_sleeve", "X", (0, yr, zc), g["sleeve_od"], g["sleeve_id"], gb0, gb1)
    s.cyl("gear_b", "X", (0, yr, zc), tip, gb0, gb1)
    s.cyl("t_gbb", "X", (0, yr, zc), g["sleeve_od"] + g["bore_clr"], gb0 - 0.1, gb1 + 0.1)
    s.cut("gear_b", ["t_gbb"])
    s.tube("bush_rod", "X", (0, yr, zc), bu["od"], bu["id"], *L["bush"])
    s.tube("thrust_collar", "X", (0, yr, zc), co["od"], rd["d"] + 0.04, *L["collar"])
    s.cyl("magnet", "X", (0, yr, zc), mg["d"], *L["magnet"])
    px, py, pz = tm["pkg"]
    s.box("hall_tmag", (L["tmag"][0], L["tmag"][1]), (L["tmag_y"] - py / 2, L["tmag_y"] + py / 2), (zc - pz / 2, zc + pz / 2))
    s.cyl("motor_boss", "Y", (xc, 0, zc), dr["boss_d"], *L["boss_y"])
    s.cyl("gearhead", "Y", (xc, 0, zc), dr["motor_d"], *L["gearhead_y"])
    s.cyl("motor", "Y", (xc, 0, zc), dr["motor_d"], *L["motor_y"])
    s.cyl("motor_rear_boss", "Y", (xc, 0, zc), dr["rear_boss_d"], *L["rear_boss_y"])
    s.cyl("motor_shaft", "Y", (xc, 0, zc), dr["shaft_d"], ga0 + 0.15, L["boss_y"][0])
    s.cyl("gear_a", "Y", (xc, 0, zc), tip, ga0, ga1)
    s.cyl("t_gab", "Y", (xc, 0, zc), dr["shaft_d"] + g["bore_clr"], ga0 - 0.1, ga1 + 0.1)
    s.cut("gear_a", ["t_gab"])
    bx, by, bh = dr["term_block"]
    yt = L["gearhead_y"][0] + dr["term_x"]
    zb = zc - dr["motor_d"] / 2 - bh
    s.box("motor_term", (xc - by / 2, xc + by / 2), (yt - bx / 2, yt + bx / 2), (zb, zb + bh))
    tabs = [s.box(f"t_tab{k}", (xc + dr["term_pitch"] * kk - 0.15, xc + dr["term_pitch"] * kk + 0.15), (yt, yt + dr["pin_tab_len"]), (zb - dr["pin_tab_t"], zb + 0.01))
            for k, kk in enumerate((-1.5, -0.5, 0.5, 1.5))]
    s.join("motor_term", tabs)


def build_electronics_boxes(s: Script, p: dict, L: dict) -> None:
    tm, K = p["cup"]["tmag"], L["dock"]
    zc = L["zc"]
    for nm, k in (("ko_board", "board"), ("ko_aux", "aux"), ("ko_io", "io"), ("ko_side_a", "side_a"), ("ko_side_b", "side_b"), ("ko_battery", "battery"), ("ko_usb", "usb"), ("ko_dock_board", "dock_board")):
        b = L[k]
        s.box(nm, tuple(b["x"]), tuple(b["y"]), tuple(b["z"]))
    s.box("ko_tmag_board", tuple(L["tmag"]), (L["tmag_y"] - tm["pkg"][1] / 2 - 0.2, L["tmag_y"] + tm["pkg"][1] / 2 + 0.2), (zc + tm["pkg"][2] / 2, zc + tm["pkg"][2] / 2 + tm["board_t"]))
    dock.build_head(s, p, K)
    dock.build_clip(s, p, K)
    dock.build_needle(s, p, K)
    s.box("hall_dock", (K["x_d"] - 0.55, K["x_d"] + 0.55), (K["y_c"] - 0.7, K["y_c"] + 0.7), (L["dock_board"]["z"][0] - 0.4, L["dock_board"]["z"][0]))


def build_housing(s: Script, p: dict, L: dict) -> None:
    sh, g, c = p["shell"], p["cup"]["gears"], p["cup"]
    w, Lp, W, H, lap, r = L["wall"], L["length"], L["width"], L["height"], sh["lap_low"], sh["corner_r"]
    zc, yr, xc, K = L["zc"], L["y_r"], L["xc"], L["dock"]
    dr = p["drive_nfp"]
    half, dk = K["half"], c["dock"]
    rr = c["corner_r_outer"]                                                    # outer vertical corner radius (pebble); inner cavity keeps R3.1
    s.rrect("bottom", (0, Lp), (0, W), rr, (0, lap))
    s.fillet_chain("bottom", (Lp / 2, 0.0, 0.0), c["bottom_break"])             # flat bottom, 0.3 mm edge break only
    s.rrect("t_cav", (w, Lp - w), (w, W - w), r - w, (w, lap + 0.1))
    s.cut("bottom", ["t_cav"])
    z_roof0 = dk["head"]["B_dome_h"] + dk["clr"]
    joins = [s.box("t_pk", (K["x_bf"], Lp - w + 0.01), (yr - half - dk["pocket_wall"], yr + half + dk["pocket_wall"]), (w - 0.1, z_roof0 + dk["roof"]))]
    cuts = [s.box("t_pk_in", (K["x_bf"] - 0.02, K["x_far"]), (yr - half, yr + half), (-0.1, z_roof0)),
            s.box("t_pk_win", (K["plate_x"][0], K["plate_x"][1]), (yr - half, yr + half), (-0.1, w + 0.05)),
            s.cyl("t_floor_fill", "Z", (L["x_s"], L["y_s"], 0), c["fill"]["hole_d"], -0.1, w + 0.05)]
    gb0, gb1 = L["gear_b"]
    cuts.append(s.box("t_grelief", (gb0 - 0.3, gb1 + 0.3), (yr - 3.0, yr + 3.0), (w - g["floor_relief"], w + 0.01)))
    cuts.append(s.box("t_grelief2", (xc - 3.2, xc + 3.2), (L["gear_a_y"][0] - 0.3, L["gear_a_y"][1] + 0.3), (w - g["floor_relief"], w + 0.01)))
    u, usb = L["usb"], c["usb"]
    xu = (u["x"][0] + u["x"][1]) / 2
    cuts.append(s.box("t_usb_open", (xu - usb["open_w"] / 2, xu + usb["open_w"] / 2), (W - w - 0.1, W + 0.1), ((u["z"][0] + u["z"][1]) / 2 - usb["open_h"] / 2, (u["z"][0] + u["z"][1]) / 2 + usb["open_h"] / 2)))
    bx, by, bh = dr["term_block"]
    yt = L["gearhead_y"][0] + dr["term_x"]
    cuts.append(s.box("t_pin_pocket", (xc - by / 2 - 0.4, xc + by / 2 + 0.4), (yt - bx / 2 - 0.4, yt + dr["pin_tab_len"] + 0.4), (0.35, w + 0.01)))
    bu = c["bush"]
    bh_ = bu["od"] + 2 * bu["rib_wall"]
    joins.append(s.box("t_rib", tuple(L["bush"]), (yr - bh_ / 2, yr + bh_ / 2), (w - 0.1, zc + bh_ / 2)))
    ys = [L["gearhead_y"][0] + 0.5, L["motor_y"][1] - 2.2]
    sl = c["motor"]["saddle_len"]
    for k, y0 in enumerate(ys):
        joins.append(s.box(f"t_sad{k}", (xc - 3.4, xc + 3.4), (y0, y0 + sl), (w - 0.1, zc)))
    s.join("bottom", joins)
    cuts.append(s.cyl("t_bush_bore", "X", (0, yr, zc), bu["od"] + bu["bore_clr"], L["bush"][0] - 0.05, L["bush"][1] + 0.05))
    for k, y0 in enumerate(ys):
        cuts.append(s.cyl(f"t_sad_bore{k}", "Y", (xc, 0, zc), 6.0 + 2 * c["motor"]["saddle_clr"], y0 - 0.05, y0 + sl + 0.05))
    s.cut("bottom", cuts)
    lap_t = lap + 0.4                                                           # lid starts 0.4 above the rim: flat gasket between
    s.rrect("top", (0, Lp), (0, W), rr, (lap_t, H))
    s.fillet_chain("top", (Lp / 2, 0.0, H), c["top_fillet"])                    # smooth pebble top: largest fillet the unchanged inner cavity allows (min wall 0.5)
    s.rrect("t_cavt", (w, Lp - w), (w, W - w), r - w, (lap_t - 0.1, H - w))
    s.cut("top", ["t_cavt"])


def build(p: dict, variant: str) -> tuple[Script, dict]:
    L = geometry(p, variant)
    s = Script()
    build_housing(s, p, L)
    build_tank_and_plunger(s, p, L)
    build_drive(s, p, L)
    build_electronics_boxes(s, p, L)
    import op_cup_asm
    op_cup_asm.build(s, p, L)
    return s, L


MFG_PARTS = {"bottom": ["bottom"], "top": ["top"], "reservoir": ["reservoir"], "plunger_core": ["plunger_core"], "plunger_seal": ["seal_a", "seal_b"],
             "thrust_sleeve": ["thrust_sleeve"], "thrust_collar": ["thrust_collar"], "lid_gasket": ["lid_gasket"], "usb_gasket": ["usb_gasket"]}
PURCHASED = ["nut", "rod", "bush_rod", "gear_a", "gear_b", "motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "magnet", "hall_tmag", "septum",
             "hub_oring", "needle", "needle_hub", "needle_guard", "cannula_adapter", "dock_magnet", "dock_clip", "hall_dock"]
KEEPOUT = ["ko_board", "ko_aux", "ko_io", "ko_side_a", "ko_side_b", "ko_battery", "ko_usb", "ko_tmag_board", "ko_dock_board"]
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED + KEEPOUT
EXCLUDE_PAIRS = [["gear_a", "gear_b"], ["needle_guard", "needle_hub"], ["needle_hub", "reservoir"], ["lid_gasket", "top"], ["hub_oring", "reservoir"]]
