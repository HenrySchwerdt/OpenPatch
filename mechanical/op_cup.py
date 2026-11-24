# SPDX-License-Identifier: LicenseRef-OpenPatch
"""OpenPatch v0.1.0 "cup" pod (`generate.py --variant v010 --drive cup`): one rotating rod on the tank axis, plunger = long cup.

TEST PROJECT: never worn, never filled with anything but water (CLAUDE.md, DISCLAIMER.md).

Concept B (user decision), everything else of the earlier drives is removed (no second rod, carriage, tongue, idler, third gear):
  * ONE M1.6 x 0.35 rod on the tank axis, rotating and axially fixed in a bush behind the gear pair: forward thrust (plunger pushed out) goes collar -> bush rear
    face, reverse thrust (plunger pulled back) goes gear B hub back face -> bush front face; gear B is tapped onto the rod (no sleeve).  Driven by the
    NFP-608-26.45 through exactly two bought miter gears (module 0.3, z12 : z12, 1:1, BUY-LIST A1/A2).
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
    lane2 = c["battery"]["w"] + 0.4 + c.get("lane2_extra", 0.0)            # lane 2 = cell width + clearance + board routing room (owner 2026-11-22)
    c["lane2_inner"] = lane2
    outer = min(W - 2 * w - 0.1 - lane2, 2 * (W - w - 0.1 - c["motor_y_ext"] - w))
    outer = math.floor(round(outer * 10, 6)) / 10
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
    dr["nut_af"], dr["nut_len"] = c["nut"]["af"], c["nut"]["len"]                   # real brass DIN 934 M1.6 (AF 3.5, h 1.3); the bench keeps drive.nut_af 3.2
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

    W_x = W - c.get("lane2_extra", 0.0)        # x layout (motor column, tank, dock, length) stays referenced to the pre-2026-11-22 corner: lane-2 widening moves y only

    def corner_clear(y_edge: float) -> float:
        dy = y_edge - (W_x - w - r_in)
        return 0.0 if dy <= 0 else r_in - math.sqrt(max((r_in - 0.05) ** 2 - dy ** 2, 0.0))
    y_g0, y_g1 = y_r + g["front_a"], y_r + g["back_a"]                      # gear A (motor): faced front / back, measured from the rod axis
    y_boss0 = y_g1 + g["clr_boss"]
    y_body0 = y_boss0 + dr["boss_front"]
    y_gh1 = y_body0 + dr["gearhead_len"]
    y_mo1 = y_gh1 + dr["motor_len"]
    y_tail1 = y_mo1 + dr["motor_tail"]
    xc = w + dr["motor_d"] / 2 + 0.1 + corner_clear(y_mo1)                 # motor column centre (axis Y); nothing behind it
    x_gb0, x_gb1 = xc + g["front_b"], xc + g["back_b"]                     # gear B (rod, tapped onto the rod, rod ends flush with its front face)
    x_m0, x_m1 = x_gb0 - mg["t"], x_gb0                                     # magnet on gear B's front (motor-side) face
    x_h0, x_h1 = xc - 1.8, xc - 1.8 + tm["pkg"][0]                          # TMAG beside the magnet (-Y), tiny sensor tab
    ty = y_r - mg["d"] / 2 - tm["gap"] - tm["pkg"][1] / 2
    x_b0 = x_gb1 + bu["gear_gap"]                                           # bush front face: reverse-thrust stop of the gear B hub
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
    xl2 = xc + c["battery"]["x_off"]                                      # cell envelope west end: leaves the wire channel x 7.5..xl2 (motor / cell / TMAG wires)
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
    # USB-C mid-mount receptacle in a notch of the board north edge, centred on the board mid-plane; keep-out bottom clipped to the cell envelope top (+0.02)
    L["usb"] = {"x": [u["x_c"] - u["w"] / 2, u["x_c"] + u["w"] / 2], "y": [W - w - u["d"], W - w], "z": [max(u["z_c"] - u["h"] / 2, tb + 0.02), u["z_c"] + u["h"] / 2],
                "z_c": u["z_c"], "x_c": u["x_c"]}
    # main board (lane-2 body) incl. top parts (<= top_max) and bottom parts over the cell (>= cell top + 0.02); the notches (USB-C, wire channel, support pads, button) are cut in CAD
    L["board"] = {"x": list(bd["pcb_x"]), "y": list(bd["pcb_y"]), "z": [tb + 0.02, bd["top_max"]], "pcb_z": list(bd["pcb_z"])}
    xa0 = bd["pcb_x"][1] + 0.1                                                    # east of the board: antenna clearance (kept free of parts)
    L["aux"] = {"x": [xa0, max(xa0 + 0.5, length - 3.6)], "y": list(lane2_y), "z": [4.9, bd["z1"]]}
    L["io"] = {"x": [w + 3.1, x_dry - 0.2], "y": [w + 0.1, ty - tm["pkg"][1] / 2 - 0.2], "z": [w + 0.1, bd["z1"]]}
    hy = K["half"] + p["cup"]["dock"]["pocket_wall"] + 0.1
    L["side_a"] = {"x": [K["x_bf"], length - 3.8], "y": [w + 0.1, y_r - hy], "z": [w + 0.1, bd["z1"]]}
    L["side_b"] = {"x": [K["x_bf"], length - w - 0.3], "y": [y_r + hy, w + res_w - 0.1], "z": [w + 0.1, bd["z1"]]}
    L["dock_board"] = {"x": [K["x_d"] - 3.0, K["x_d"] + 3.0], "y": [y_r - 3.0, y_r + 3.0], "z": [5.3, 5.9]}
    bsp = c["board_support"]
    L["board_screws"] = [list(bsp["screw_w"]), [round(K["x_bf"] + bsp["screw_e"]["dx_dock"], 3), bsp["screw_e"]["y"]]]       # W (board tab), E (side_b leg)
    L["lane2_fit"] = {"need_x": bat["l"] + 3.1, "have_x": length - w - x_l2}
    bs, bt = c["board_support"], c["button"]
    r2 = 3.0 + c["motor"]["saddle_clr"]
    L["elec_interface"] = {
        "_comment": "pod frame (x = 0 motor/rear end, y = 0 tank-side wall, z = 0 skin side), mm; agreed with the electronics agent (board review 2026-11-20)",
        "board_west_edge_min_x": bd["pcb_x"][0], "board_z": list(bd["pcb_z"]), "lid_inner_z": H - w, "top_parts_max_z": bd["top_max"],
        "usb_opening": {"shape": "stadium (full semicircular ends R%.2f), 0.3 x 45 deg outer chamfer" % (u["open_h"] / 2), "x": [u["x_c"] - u["open_w"] / 2, u["x_c"] + u["open_w"] / 2],
                        "z": [u["z_c"] - u["open_h"] / 2, u["z_c"] + u["open_h"] / 2], "x_c": u["x_c"], "z_c": u["z_c"], "wall_inner_y": W - w,
                        "gasket_recess": {"shape": "stadium, clipped at z %.2f" % u["recess_z_max"], "x": [u["x_c"] - u["open_w"] / 2 - u["recess_margin"], u["x_c"] + u["open_w"] / 2 + u["recess_margin"]],
                                          "z": [u["z_c"] - u["open_h"] / 2 - u["recess_margin"], u["recess_z_max"]], "depth_y": u["recess_depth"]},
                        "gasket_frame_inner": [u["gasket"]["in_w"], u["gasket"]["in_h"]]},
        "usb_receptacle_keepout": L["usb"],
        "wire_channel": {"x": [round(xc + 3.0 + 0.03, 2), round(x_l2, 2)], "y": list(lane2_y), "z": [w, bd["pcb_z"][0]], "note": "motor 4 + cell 2 + TMAG strip; no bottom-side parts over it"},
        "cell": {"x": L["battery"]["x"], "y": L["battery"]["y"], "z": L["battery"]["z"], "lead_end": "WEST (VERIFY-ON-SAMPLE)"},
        "support_pads": [{"x": x, "y": y, "kind": "floor ledge below (d%.1f, top z %.1f) + lid rib above (d%.1f, bottom z %.1f)" % (bs["ledge_d"], bs["z_top"], bs["rib_d"], bd["pcb_z"][1]),
                          "part_free_d_both_faces": bs["pad_d"]} for x, y in bs["ledges"]]
                        + [{"x": round(sum(bs["shelf_x"]) / 2, 2), "y": round((bs["shelf_y0"] + bd["pcb_y"][1]) / 2, 2), "kind": "wall shelf below + wall rib above, contact x %.1f-%.1f, y %.1f-board edge" % (bs["shelf_x"][0], bs["shelf_x"][1], bs["shelf_y0"]),
                            "part_free_rect_both_faces": {"x": [bs["shelf_x"][0] - 0.3, bs["shelf_x"][1] + 0.3], "y": [bs["shelf_y0"] - 0.3, bd["pcb_y"][1]]}}],
        "button": {"actuator_x": bt["x_c"], "actuator_z": bt["actuator_z"], "actuator_tip_y_max": bt["actuator_tip_y_max"], "part": "lid",
                   "cap": {"axis_z": bt["z_c"], "stem_d": bt["stem_d"], "pad": {"x": bt["pad"]["x"], "z": bt["pad"]["z"], "contact_face_y": bt["pad"]["face_y"]},
                           "flange": {"x": bt["flange"]["x"], "z": bt["flange"]["z"], "y": [round(W - w - bt["flange"]["t"], 3), W - w]},
                           "stroke_to_actuate": round(bt["pad"]["face_y"] - bt["actuator_tip_y_max"] + bt["switch_travel"], 3),
                           "pressed_flange_y_min": round(W - w - bt["flange"]["t"] - (bt["pad"]["face_y"] - bt["actuator_tip_y_max"] + bt["switch_travel"]), 3),
                           "note": "board keeps x %.1f-%.1f, y >= %.2f, z >= %.2f free except the SW1 actuator; the flange bar (x %.1f-%.1f, z %.2f-%.2f) travels to y %.2f when pressed: SW1 body front face must be at y < that (VERIFY)" % (
                               bt["kb_notch_x"][0], bt["kb_notch_x"][1], bt["actuator_tip_y_max"], bd["pcb_z"][1], bt["flange"]["x"][0], bt["flange"]["x"][1], bt["flange"]["z"][0], bt["flange"]["z"][1],
                               W - w - bt["flange"]["t"] - (bt["pad"]["face_y"] - bt["actuator_tip_y_max"] + bt["switch_travel"]))}},
        "board_screws": [{"x": x, "y": y, "hole_d_npth": bs["hole_d"], "keepout_ring_d_both_faces": bs["ring_d"], "boss_d": bs["boss_d"], "boss_top_z": bs["z_top"],
                          "pilot": "d%.2f x %.1f deep" % (bs["pilot_d"], bs["pilot_depth"]), "screw": bs["screw"]} for x, y in L["board_screws"]],
        "west_tab": bs["west_tab"],
        "lane2_saddle": {"y": [L["motor_y"][1] - 2.2, L["motor_y"][1] - 2.2 + c["motor"]["saddle_len"]], "x_max": round(xc + c["motor"]["lane2_r_out"], 3), "lip_top_z": c["motor"]["lane2_lip_z"],
                         "x_at_lip_top": round(xc + math.sqrt(c["motor"]["lane2_r_out"] ** 2 - (c["motor"]["lane2_lip_z"] - zc) ** 2), 3), "bore_r": r2},
    }
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


def gear_profile(g: dict, front: float, back: float, hub_d: float) -> list[tuple[float, float, float, float]]:
    """Envelope of a module-m miter gear as (a0, a1, r0, r1) frustums, a = distance from the pitch-cone apex along the gear axis.

    Tip cone 45 degrees (r = a + m cos 45) from the front face to the pitch circle (a = m z / 2, r = tip radius), back cone down to the hub radius, hub cylinder to `back`."""
    rp = g["module"] * g["z_motor"] / 2.0
    dk = g["module"] * math.cos(math.radians(45.0))
    ro = rp + dk
    hr = hub_d / 2.0
    a_h = rp + ro - hr
    segs = [(front, rp, front + dk, ro), (rp, a_h, ro, hr)]
    if back > a_h + 1e-6:
        segs.append((a_h, back, hr, hr))
    return segs


def build_gear(s: Script, name: str, axis: str, c: tuple[float, float, float], apex: float, segs: list, bore_d: float) -> None:
    """Gear envelope (join of frustums / hub cylinder) with its bore; `apex` = coordinate of the axes crossing along `axis`."""
    names = []
    for k, (a0, a1, r0, r1) in enumerate(segs):
        nm = name if k == 0 else f"t_{name}_s{k}"
        if abs(r0 - r1) < 1e-9:
            s.cyl(nm, axis, c, 2 * r0, apex + a0, apex + a1)
        else:
            s.cone(nm, axis, c, r0, r1, apex + a0, apex + a1)
        names.append(nm)
    if len(names) > 1:
        s.join(name, names[1:])
    s.cyl(f"t_{name}_bore", axis, c, bore_d, apex + segs[0][0] - 0.1, apex + segs[-1][1] + 0.1)
    s.cut(name, [f"t_{name}_bore"])


def build_drive(s: Script, p: dict, L: dict) -> None:
    g, bu, mg, tm, dr, rd, co = p["cup"]["gears"], p["cup"]["bush"], p["cup"]["magnet"], p["cup"]["tmag"], p["drive_nfp"], p["cup"]["rod"], p["cup"]["collar"]
    zc, yr, xc = L["zc"], L["y_r"], L["xc"]
    gb0, gb1 = L["gear_b"]
    ga0, ga1 = L["gear_a_y"]
    s.cyl("rod", "X", (0, yr, zc), rd["d"], gb0, L["x_tip"])                       # rod ENDS flush with gear B's front face; gear B is tapped onto the rod (no sleeve)
    build_gear(s, "gear_b", "X", (0, yr, zc), xc, gear_profile(g, g["front_b"], g["back_b"], g["hub_b_d"]), rd["d"] + g["bore_clr"])      # M1.6 tapped bore modelled at the rod size + clearance
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
    build_gear(s, "gear_a", "Y", (xc, 0, zc), yr, gear_profile(g, g["front_a"], g["back_a"], g["hub_a_d"]), dr["shaft_d"] + g["bore_clr"])   # D-shaft press fit (round bore + compound)
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
    cut_board_keepout(s, p, L)
    bs = p["cup"]["board_support"]
    tb_ = bs["west_tab"]
    s.box("ko_board_tab", tuple(tb_["x"]), tuple(tb_["y"]), tuple(p["cup"]["board"]["pcb_z"]))       # west board tab carrying the west screw (PCB only, no parts)
    sw = L["board_screws"][0]
    s.cut("ko_board_tab", [s.cyl("t_kbt_hole", "Z", (sw[0], sw[1], 0), bs["hole_d"], 5.0, 6.5)])
    se = L["board_screws"][1]
    s.cut("ko_side_b", [s.cyl("t_ksb_screw", "Z", (se[0], se[1], 0), bs["ring_d"], 0.5, 8.0)])          # screw column + part-free ring through the side_b keep-out
    s.box("ko_tmag_board", tuple(L["tmag"]), (L["tmag_y"] - tm["pkg"][1] / 2 - 0.2, L["tmag_y"] + tm["pkg"][1] / 2 + 0.2), (zc + tm["pkg"][2] / 2, zc + tm["pkg"][2] / 2 + tm["board_t"]))
    dock.build_head(s, p, K)
    dock.build_clip(s, p, K)
    dock.build_needle(s, p, K)
    s.box("hall_dock", (K["x_d"] - 0.55, K["x_d"] + 0.55), (K["y_c"] - 0.7, K["y_c"] + 0.7), (L["dock_board"]["z"][0] - 0.4, L["dock_board"]["z"][0]))


def cut_board_keepout(s: Script, p: dict, L: dict) -> None:
    """Notches in the main-board keep-out (= the agreed board body): USB-C notch, no bottom parts over the wire channel, part-free support pads, button nub space."""
    c, b, u = p["cup"], L["board"], L["usb"]
    bs, bt = c["board_support"], c["button"]
    z0, z1 = b["pcb_z"]
    lo, hi = b["z"][0] - 0.1, b["z"][1] + 0.1
    tools = [s.box("t_kb_usb", (u["x"][0] - 0.1, u["x"][1] + 0.1), (u["y"][0] - 0.1, b["y"][1] + 0.1), (lo, hi)),
             s.box("t_kb_wire", (b["x"][0] - 0.1, L["battery"]["x"][0] + 0.03), (b["y"][0] - 0.1, b["y"][1] + 0.1), (lo, z0)),
             s.box("t_kb_btn", tuple(bt["kb_notch_x"]), (bt["actuator_tip_y_max"], b["y"][1] + 0.1), (z1, hi))]
    for k, (x, y) in enumerate(bs["ledges"]):
        tools += [s.cyl(f"t_kb_pl{k}", "Z", (x, y, 0), bs["pad_d"], lo, z0), s.cyl(f"t_kb_pu{k}", "Z", (x, y, 0), bs["pad_d"], z1, hi)]
    m = (bs["pad_d"] - bs["ledge_d"]) / 2
    tools += [s.box("t_kb_sl", (bs["shelf_x"][0] - m, bs["shelf_x"][1] + m), (bs["shelf_y0"] - m, b["y"][1] + 0.1), (lo, z0)),
              s.box("t_kb_su", (bs["shelf_x"][0] - m, bs["shelf_x"][1] + m), (bs["shelf_y0"] - m, b["y"][1] + 0.1), (z1, hi))]
    s.cut("ko_board", tools)


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
    jt = c["joint"]
    # rim band (z 4.45-5.0): constant 0.9 mm wall also in the four corners so the seal groove keeps its inner wall (outer R4.8 vs cavity R3.1 leaves 0.57 on the diagonal)
    s.join("bottom", [s.rrect_ring("t_rim_band", (0, Lp), (0, W), rr, (0.0, jt["band_wall"]), (lap - jt["band_h"], lap))])
    z_roof0 = dk["head"]["B_dome_h"] + dk["clr"]
    joins = [s.box("t_pk", (K["x_bf"], Lp - w + 0.01), (yr - half - dk["pocket_wall"], yr + half + dk["pocket_wall"]), (w - 0.1, z_roof0 + dk["roof"]))]
    # pocket open to the underside AND to the +X end face (owner 2026-11-24): the head slides in from the end; the end wall stays above the opening as a lintel (z_roof0..rim)
    x_open = Lp + 0.1 if dk.get("open_end") else K["x_far"]
    cuts = [s.box("t_pk_in", (K["x_bf"] - 0.02, x_open), (yr - half, yr + half), (-0.1, z_roof0)),
            s.box("t_pk_win", (K["plate_x"][0], K["plate_x"][1]), (yr - half, yr + half), (-0.1, w + 0.05)),
            s.cyl("t_floor_fill", "Z", (L["x_s"], L["y_s"], 0), c["fill"]["hole_d"], -0.1, w + 0.05)]
    if dk.get("open_end"):
        open_join, open_cut = dock.open_end_tools(s, p, K, Lp, z_roof0)
    else:
        open_join, open_cut = [], []
    # no floor relief under the gears any more: the z12 envelopes (tip radius 2.01) keep 1.34 mm to the floor (the z16 tips had 0.65)
    # USB-C opening (stadium, both shells) is cut in op_cup_asm (8)
    bx, by, bh = dr["term_block"]
    yt = L["gearhead_y"][0] + dr["term_x"]
    cuts.append(s.box("t_pin_pocket", (xc - by / 2 - 0.4, xc + by / 2 + 0.4), (yt - bx / 2 - 0.4, yt + dr["pin_tab_len"] + 0.4), (0.35, w + 0.01)))
    bu = c["bush"]
    bh_ = bu["od"] + 2 * bu["rib_wall"]
    joins.append(s.box("t_rib", tuple(L["bush"]), (yr - bh_ / 2, yr + bh_ / 2), (w - 0.1, zc + bh_ / 2)))
    ys = [L["gearhead_y"][0] + 0.5, L["motor_y"][1] - 2.2]
    sl = c["motor"]["saddle_len"]
    for k, y0 in enumerate(ys):
        # snap saddle = C-ring: shell of radius r_bore + snap_t around the can axis, rooted in the floor at its bottom only (relief to both sides), cut flat at zc + snap_h
        # (tip above the can centre line: mouth 2*sqrt(r_bore^2 - snap_h^2) < can d6.0 -> snap-in from above, the ring arc opens ~0.4 mm per side); the lane-2 saddle is
        # thinned on the -X side by the lid wall (w); the lane-2 saddle (under the board west edge) is limited to r 3.37 (x <= 7.84) and its +X lip is cut at
        # z 5.2 so it stays below the board underside (z 5.3): wrap 180 + 31.6 (-X lip) + 18.1 (+X lip) = 230 deg at the bore, mouth 5.53 < can d6.0 (snap kept)
        lane2 = y0 > L["lane2_y"][0]
        rb = 3.0 + c["motor"]["saddle_clr"]
        r_out = min(rb + c["motor"]["snap_t"], xc - w, c["motor"]["lane2_r_out"] if lane2 else 9.0)
        joins.append(s.cyl(f"t_sad{k}", "Y", (xc, 0, zc), 2 * r_out, y0, y0 + sl))
        cuts.append(s.box(f"t_sad_top{k}", (xc - 4.0, xc + 4.0), (y0 - 0.1, y0 + sl + 0.1), (zc + c["motor"]["snap_h"], zc + 4.0)))
        if lane2:
            cuts.append(s.box(f"t_sad_lip{k}", (xc, xc + 4.0), (y0 - 0.1, y0 + sl + 0.1), (c["motor"]["lane2_lip_z"], zc + 4.0)))
    s.join("bottom", joins)
    cuts.append(s.cyl("t_bush_bore", "X", (0, yr, zc), bu["od"] + bu["bore_clr"], L["bush"][0] - 0.05, L["bush"][1] + 0.05))
    for k, y0 in enumerate(ys):
        cuts.append(s.cyl(f"t_sad_bore{k}", "Y", (xc, 0, zc), 6.0 + 2 * c["motor"]["saddle_clr"], y0 - 0.05, y0 + sl + 0.05))
    s.cut("bottom", cuts)
    if open_join:                                                               # anchor blocks after the pocket cut, then their slots and the lead-in chamfers
        s.join("bottom", open_join)
    if open_cut:
        s.cut("bottom", open_cut)
    lap_t = lap                                                                 # lid bottom face sits on the rim (hard stop, owner 2026-11-24); the seal is in the rim groove
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
             "thrust_collar": ["thrust_collar"], "lid_gasket": ["lid_gasket"], "usb_gasket": ["usb_gasket"], "button_cap": ["button_cap"]}
PURCHASED = ["nut", "rod", "bush_rod", "gear_a", "gear_b", "motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "magnet", "hall_tmag", "septum",
             "hub_gasket", "needle", "needle_hub", "needle_guard", "cannula_adapter", "dock_magnet", "dock_clip", "hall_dock", "button_oring"]
KEEPOUT = ["ko_board", "ko_board_tab", "ko_aux", "ko_io", "ko_side_a", "ko_side_b", "ko_battery", "ko_usb", "ko_tmag_board", "ko_dock_board"]
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED + KEEPOUT
EXCLUDE_PAIRS = [["gear_a", "gear_b"], ["needle_guard", "needle_hub"], ["needle_hub", "reservoir"], ["lid_gasket", "top"], ["hub_gasket", "reservoir"]]
