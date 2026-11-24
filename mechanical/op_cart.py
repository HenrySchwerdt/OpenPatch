# SPDX-License-Identifier: LicenseRef-OpenPatch
"""v0.1.0 "cart" pump: an Accu-Chek Insight-type 1.6 ml cartridge + the original Insight adapter & tubing in a small tubed bench pump.

TEST PROJECT, NOT A MEDICAL DEVICE: bench only, filled with WATER only (never insulin or any drug), never worn (DISCLAIMER.md).

Frame: x = 0 rear outer face, +X toward the adapter (front); y = 0 outer wall on the cartridge side; z = 0 underside.
Lane 1 (-Y): anti-rotation slider + translating M2 piston rod (tail zone, length = stroke) -> gear nut (m0.5 z20 spur gear with a bonded
M2 brass nut, held axially between two ribs) -> pusher disc -> cartridge stopper -> cartridge -> Insight adapter in the bayonet receiver.
Lane 2 (+Y): NFP-608-26.45 motor parallel to the rod in the tail zone (pinion m0.5 z10, angle magnet on its front face, TMAG strip in front
of it), then the UNCHANGED cup-pod main board with the Ampul 301030 cell under it and the USB-C receptacle in the +Y wall.
No custom tank, no plunger casting, no dock, no needle, no septum: cartridge and adapter are bought parts.
"""
from __future__ import annotations

import copy
import math

from op_cmds import Script

MFG_PARTS = {"bottom": ["bottom"], "top": ["top"], "slider": ["slider"], "pusher": ["pusher"], "lock_flag": ["lock_flag"], "lid_gasket": ["lid_gasket"]}
PURCHASED = ["cartridge", "stopper", "cart_cap", "adapter", "adapter_lug_a", "adapter_lug_b", "tubing", "rod", "rod_nut", "gear_rod", "pinion", "washer_r", "washer_f",
             "motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "magnet", "hall_tmag", "lock_magnet", "hall_lock"]
KEEPOUT = ["ko_board", "ko_battery", "ko_usb", "ko_tmag_board"]
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED + KEEPOUT
# pairs that touch or overlap by design (bonded, threaded, meshing, press fit, needle through the septum, stacked keep-outs)
EXCLUDE_PAIRS = [["pinion", "gear_rod"], ["rod", "rod_nut"], ["rod", "gear_rod"], ["rod_nut", "gear_rod"], ["rod", "slider"], ["rod", "pusher"], ["pusher", "stopper"],
                 ["stopper", "cartridge"], ["cart_cap", "cartridge"], ["adapter", "cart_cap"], ["adapter", "cartridge"], ["adapter", "adapter_lug_a"], ["adapter", "adapter_lug_b"],
                 ["adapter", "tubing"], ["motor_shaft", "pinion"], ["motor_shaft", "motor_boss"], ["motor_boss", "gearhead"], ["gearhead", "motor"], ["motor", "motor_rear_boss"],
                 ["magnet", "pinion"], ["magnet", "motor_shaft"], ["lock_magnet", "lock_flag"], ["lock_flag", "adapter"], ["lid_gasket", "top"], ["lid_gasket", "bottom"],
                 ["ko_battery", "ko_board"], ["ko_usb", "ko_board"], ["hall_tmag", "ko_tmag_board"], ["washer_r", "gear_rod"], ["washer_f", "gear_rod"]]


def prepare(p0: dict) -> dict:
    """Resolve the cart block: motor preset and the derived cartridge numbers (bore area, stroke for the nominal volume)."""
    p = copy.deepcopy(p0)
    c = p["cart"]
    dr = dict(p["drive"])
    dr.update(p["drive_presets"]["nfp_608_26"])
    p["drive_nfp"] = dr
    ca = c["cartridge"]
    c["_bore_area"] = math.pi * (ca["id"] / 2) ** 2
    c["_stroke"] = round(c["volume_ml"] * 1000.0 / c["_bore_area"], 2)
    return p


def _pol(yc: float, zc: float, r: float, deg: float) -> tuple[float, float]:
    """Point at radius r, angle deg (0 = +Y, 90 = +Z) around the axis (yc, zc)."""
    return yc + r * math.cos(math.radians(deg)), zc + r * math.sin(math.radians(deg))


def geometry(p: dict) -> dict:
    c, dr = p["cart"], p["drive_nfp"]
    ca, ad, rc, g, rd, sl, pu, rb, sh = c["cartridge"], c["adapter"], c["receiver"], c["gears"], c["rod"], c["slider"], c["pusher"], c["ribs"], c["shell"]
    w = c["wall"]
    stroke = c["_stroke"]
    gear_od = g["m"] * (g["z_rod"] + 2)
    # height: cartridge barrel, gear tip circle and receiver bore share the axis; the bayonet groove lies in the +-Y flank sectors only (|angle| <= sector)
    big = max(ca["od"] + 2 * c["cradle_clr"], gear_od, rc["bore_d"])
    r_groove = rc["bore_d"] / 2 + ad["lug_h"] + rc["lug_clr"]
    big = max(big, 2 * r_groove * math.sin(math.radians(rc["sector_deg"])))
    zc = w + c["floor_clr"] + big / 2
    H = round(zc + big / 2 + c["roof_clr"] + sh["gasket_t"] + w, 2)
    y_c = w + c["side_clr"] + big / 2
    a = g["m"] * (g["z_rod"] + g["z_pinion"]) / 2.0                     # centre distance rod axis -> motor axis (standard spur pair)
    y_m = y_c + a
    # x stack along lane 1
    x_sl0 = w + c["rear_clr"]                                           # slider rear face at FULL (rod fully back)
    x_rib_r0 = x_sl0 + sl["len"] + stroke + c["travel_margin"]
    x_rib_r1 = x_rib_r0 + rb["t"]
    x_g0 = x_rib_r1 + g["washer_t"]
    x_g1 = x_g0 + g["face_rod"]
    x_rib_f0 = x_g1 + g["washer_t"]
    x_rib_f1 = x_rib_f0 + rb["t"]
    x_pu0 = x_rib_f1 + c["pusher_clr"]                                  # pusher rear face at FULL
    x_pu1 = x_pu0 + pu["t"]
    x_c0 = x_pu1 - ca["stopper_recess"]                                 # cartridge rear end (stopper rear face = pusher front face at FULL)
    x_c1 = x_c0 + ca["barrel_len"]                                      # shoulder (outer)
    x_n1 = x_c1 + ca["neck_len"]                                        # cap front face
    x_st0, x_st1 = x_pu1, x_pu1 + ca["stopper_len"]
    # motor column (lane 2, axis X, pinion flush with the gear)
    x_pin0, x_pin1 = x_g0, x_g1
    x_boss1 = x_pin0 - g["pinion_boss_clr"]
    x_boss0 = x_boss1 - dr["boss_front"]
    x_gh0 = x_boss0 - dr["gearhead_len"]
    x_mo0 = x_gh0 - dr["motor_len"]
    x_tail0 = x_mo0 - dr["motor_tail"]
    mg, tm = c["magnet"], c["tmag"]
    x_mag0, x_mag1 = x_pin1, x_pin1 + mg["t"]
    x_tm0 = x_mag1 + tm["gap"]
    x_tm1 = x_tm0 + tm["pkg"][2]
    # lane 2: the cup-pod main board unchanged (35.6 x 12.6 x 0.8), cell under it, USB-C on its north edge
    bd, bat, usb = c["board"], c["battery"], c["usb"]
    lane2_y0 = y_c + big / 2 + c["lane_clr"]
    W = round(max(lane2_y0 + bd["w"] + c["board_wall_clr"] + w, y_m + dr["motor_d"] / 2 + c["side_clr"] + w), 2)
    x_bd0 = x_tm1 + tm["board_t"] + c["board_gap_x"]
    x_bd1 = x_bd0 + bd["l"]
    y_bd1 = W - w - c["board_wall_clr"]
    y_bd0 = y_bd1 - bd["w"]
    # front: the receiver collar (lane 1 only) holds the adapter; its rear face must clear the board east edge
    x_front_neck = x_n1 + ad["seat_to_cap"]
    x_front_board = x_bd1 + c["board_front_clr"] + rc["collar_len"]
    x_front = max(x_front_neck, x_front_board)
    length = round(x_front, 2)
    x_ad1 = x_front + ad["out_len"]
    collar = [x_front - rc["collar_len"], x_front]
    collar_y1 = y_c + r_groove + rc["collar_wall"]
    stroke_avail = (x_c1 - ca["shoulder_inset"]) - x_st1
    L = {"length": length, "width": W, "height": H, "wall": w, "zc": zc, "y_c": y_c, "y_m": y_m, "a_gear": a, "big": round(big, 3), "gear_od": gear_od,
         "stroke": stroke, "stroke_avail": round(stroke_avail, 2), "bore_area": round(c["_bore_area"], 3), "x_front": x_front,
         "front_governed_by": "cartridge neck + adapter seat" if x_front_neck >= x_front_board else "board east edge + collar",
         "x_front_neck": round(x_front_neck, 2), "x_front_board": round(x_front_board, 2), "length_with_adapter": round(x_ad1, 2),
         "slider_full": [x_sl0, x_sl0 + sl["len"]], "rib_r": [x_rib_r0, x_rib_r1], "gear": [x_g0, x_g1], "rib_f": [x_rib_f0, x_rib_f1],
         "pusher_full": [x_pu0, x_pu1], "cart": [x_c0, x_c1], "neck": [x_c1, x_n1], "stopper_full": [x_st0, x_st1], "rod_full": [x_sl0, x_pu0],
         "rod_len": round(x_pu0 - x_sl0, 2), "adapter": [x_front - ad["depth"], x_ad1], "collar": collar, "collar_y1": round(collar_y1, 3), "r_groove": r_groove,
         "pinion": [x_pin0, x_pin1], "boss": [x_boss0, x_boss1], "gearhead": [x_gh0, x_boss0], "motor": [x_mo0, x_gh0], "rear_boss": [x_tail0, x_mo0],
         "magnet": [x_mag0, x_mag1], "tmag": [x_tm0, x_tm1], "lane2_y0": lane2_y0}
    pz = bd["pcb_z"]
    L["board"] = {"x": [x_bd0, x_bd1], "y": [y_bd0, y_bd1], "z": [bat["z0"] + bat["t"] + 0.02, bd["top_max"]], "pcb_z": list(pz)}
    xb0 = x_bd0 + bat["x_off_board"]
    L["battery"] = {"x": [xb0, xb0 + bat["l"]], "y": [y_bd0, y_bd0 + bat["w"]], "z": [bat["z0"], bat["z0"] + bat["t"]]}
    xu = x_bd0 + usb["x_from_board_west"]
    L["usb"] = {"x": [xu - usb["w"] / 2, xu + usb["w"] / 2], "y": [W - w - usb["d"], W - w], "z": [max(usb["z_c"] - usb["h"] / 2, bat["z0"] + bat["t"] + 0.02), usb["z_c"] + usb["h"] / 2],
                "x_c": xu, "z_c": usb["z_c"]}
    L["button_x"] = round(x_bd0 + c["button"]["x_from_board_west"], 2)
    lk = c["lock"]
    yh = collar_y1 + 0.1 + lk["hall_pkg"][1] / 2
    L["lock"] = {"hall_x": [x_front - w - 0.1 - lk["hall_pkg"][0], x_front - w - 0.1], "hall_y": yh,
                 "magnet_r": round(yh - y_c, 3)}
    L["empty"] = {"slider": [x_sl0 + stroke, x_sl0 + sl["len"] + stroke], "pusher": [x_pu0 + stroke, x_pu1 + stroke],
                  "stopper": [x_st0 + stroke, x_st1 + stroke], "rod": [x_sl0 + stroke, x_pu0 + stroke]}
    L["rod_past_nut_empty"] = round(L["empty"]["rod"][0] - x_g0, 2)          # < 0: the rod rear end is still behind the nut at EMPTY (engaged)
    L["slider_to_rib_empty"] = round(x_rib_r0 - L["empty"]["slider"][1], 2)
    L["u_per_step"] = rd["pitch"] * (g["z_pinion"] / g["z_rod"]) / (dr["steps_per_rev"] * dr["gh_ratio"]) * c["_bore_area"] / 10.0
    L["envelope"] = {"bbox_mm": [length, W, H], "bbox_volume_ml": round(length * W * H / 1000.0, 2),
                     "with_adapter_mm": [round(x_ad1, 2), W, H], "with_adapter_volume_ml": round(x_ad1 * W * H / 1000.0, 2)}
    return L


# ---------------------------------------------------------------------------------------------------------------------------------------------
def build_cartridge(s: Script, p: dict, L: dict) -> None:
    c = p["cart"]
    ca, ad, rc = c["cartridge"], c["adapter"], c["receiver"]
    yc, zc = L["y_c"], L["zc"]
    x0, x1 = L["cart"]
    n1 = L["neck"][1]
    s.tube("cartridge", "X", (0, yc, zc), ca["od"], ca["id"], x0, x1 - ca["shoulder_inset"])
    s.cyl("t_cart_sh", "X", (0, yc, zc), ca["od"], x1 - ca["shoulder_inset"] - 0.01, x1)
    s.cyl("t_cart_neck", "X", (0, yc, zc), ca["neck_od"], x1 - 0.01, n1 - ca["cap_len"] + 0.01)
    s.join("cartridge", ["t_cart_sh", "t_cart_neck"])
    s.cut("cartridge", [s.cyl("t_cart_nb", "X", (0, yc, zc), ca["neck_id"], x1 - ca["shoulder_inset"] - 0.05, n1 + 0.1)])
    s.cyl("cart_cap", "X", (0, yc, zc), ca["cap_od"], n1 - ca["cap_len"], n1)                     # aluminium crimp cap + rubber septum (one envelope)
    s.cyl("stopper", "X", (0, yc, zc), ca["id"], *L["stopper_full"])
    xa0, xa1 = L["adapter"]
    xf = L["x_front"]
    s.cyl("adapter", "X", (0, yc, zc), ad["nose_od"], xa0, xf)                                    # nose in the receiver bore
    s.cyl("t_ad_body", "X", (0, yc, zc), ad["body_d"], xf, xa1)
    s.join("adapter", ["t_ad_body"])
    s.cut("adapter", [s.cyl("t_ad_cav", "X", (0, yc, zc), ca["cap_od"] + 0.1, xa0 - 0.1, n1 + ad["cap_gap"])])
    rl = ad["nose_od"] / 2 + ad["lug_h"] - ad["lug_w"] / 2              # lug = pin d lug_w whose outer edge stands lug_h proud of the nose
    for nm, ang in (("adapter_lug_a", rc["lock_deg"]), ("adapter_lug_b", rc["lock_deg"] + 180.0)):     # lugs in the LOCKED position
        y, z = _pol(yc, zc, rl, ang)
        s.cyl(nm, "X", (0, y, z), ad["lug_w"], xf - ad["lug_from_seat"] - ad["lug_t"], xf - ad["lug_from_seat"])
    s.cyl("tubing", "X", (0, yc, zc), ad["tube_d"], xa1 - 0.5, xa1 + 8.0)
    # adapter-locked detection: a printed flag clipped on the adapter body carries a d1 x 0.5 magnet in front of the lock hall (VERIFY on the sample)
    lk, lo = c["lock"], L["lock"]
    s.box("lock_flag", (xf + 0.05, xf + 0.05 + lk["flag_t"]), (yc + ad["body_d"] / 2 - 0.6, lo["hall_y"] + 1.0), (zc - 1.0, zc + 1.0))
    s.cyl("lock_magnet", "X", (0, lo["hall_y"], zc), lk["mag_d"], xf + 0.05, xf + 0.05 + lk["mag_t"])


def build_drive(s: Script, p: dict, L: dict) -> None:
    c, dr = p["cart"], p["drive_nfp"]
    g, rd, sl, pu, nut = c["gears"], c["rod"], c["slider"], c["pusher"], c["nut"]
    yc, zc, ym = L["y_c"], L["zc"], L["y_m"]
    s.cyl("rod", "X", (0, yc, zc), rd["d"], *L["rod_full"])
    s.box("slider", tuple(L["slider_full"]), (yc - sl["w"] / 2, yc + sl["w"] / 2), (zc - sl["h"] / 2, zc + sl["h"] / 2))
    s.cut("slider", [s.cyl("t_sl_bore", "X", (0, yc, zc), rd["d"], L["slider_full"][0] - 0.1, L["slider_full"][1] + 0.1)])
    s.cyl("pusher", "X", (0, yc, zc), pu["d"], *L["pusher_full"])
    s.cut("pusher", [s.cyl("t_pu_bore", "X", (0, yc, zc), rd["d"], L["pusher_full"][0] - 0.1, L["pusher_full"][0] + pu["bore_depth"])])
    g0, g1 = L["gear"]
    s.tube("gear_rod", "X", (0, yc, zc), L["gear_od"], rd["d"] + 0.2, g0, g1)                       # spur envelope (tip circle); hex pocket for the nut
    s.cut("gear_rod", [s.hexprism("t_gear_hex", (g0 - 0.1, g0 + nut["h"]), yc, zc, nut["af"] / 2 + 0.03)])
    s.hexprism("rod_nut", (g0, g0 + nut["h"]), yc, zc, nut["af"] / 2)
    s.cut("rod_nut", [s.cyl("t_nut_bore", "X", (0, yc, zc), rd["d"], g0 - 0.1, g0 + nut["h"] + 0.1)])
    for nm, x in (("washer_r", (L["rib_r"][1], g0)), ("washer_f", (g1, L["rib_f"][0]))):
        s.tube(nm, "X", (0, yc, zc), g["washer_od"], rd["d"] + 0.2, *x)
    s.tube("pinion", "X", (0, ym, zc), g["m"] * (g["z_pinion"] + 2), dr["shaft_d"], *L["pinion"])
    s.cyl("motor_shaft", "X", (0, ym, zc), dr["shaft_d"], L["boss"][0], L["pinion"][1])
    s.cyl("motor_boss", "X", (0, ym, zc), dr["boss_d"], *L["boss"])
    s.cyl("gearhead", "X", (0, ym, zc), dr["motor_d"], *L["gearhead"])
    s.cyl("motor", "X", (0, ym, zc), dr["motor_d"], *L["motor"])
    s.cyl("motor_rear_boss", "X", (0, ym, zc), dr["rear_boss_d"], *L["rear_boss"])
    mg, tm = c["magnet"], c["tmag"]
    s.cyl("magnet", "X", (0, ym, zc), mg["d"], *L["magnet"])
    px, py, pz = tm["pkg"]
    s.box("hall_tmag", tuple(L["tmag"]), (ym - px / 2, ym + px / 2), (zc - py / 2, zc + py / 2))
    y0 = max(ym - 2.6, yc + c["cartridge"]["od"] / 2 + 0.2)                                       # strip stays clear of the cartridge barrel
    s.box("ko_tmag_board", (L["tmag"][1], L["tmag"][1] + tm["board_t"]), (y0, ym + 2.6), (zc - 2.6, zc + 2.6))


def build_electronics(s: Script, p: dict, L: dict) -> None:
    for nm, k in (("ko_board", "board"), ("ko_battery", "battery"), ("ko_usb", "usb")):
        b = L[k]
        s.box(nm, tuple(b["x"]), tuple(b["y"]), tuple(b["z"]))
    bz, pz = L["board"]["z"], L["board"]["pcb_z"]
    pads = [s.cyl(f"t_kb_pad{k}", "Z", (x, y, 0), d, bz[0] - 0.1, pz[0]) for k, (x, y, d) in enumerate(board_ledges(p, L))]
    rx, ry = board_lid_rib(L)
    pads.append(s.box("t_kb_rib", (rx[0] - 0.3, rx[1] + 0.3), (ry[0] - 0.3, ry[1] + 0.3), (pz[1], bz[1] + 0.1)))
    s.cut("ko_board", pads)                                                                     # part-free pads on both board faces
    lk, lo = p["cart"]["lock"], L["lock"]
    hx, hy, hz = lk["hall_pkg"]
    s.box("hall_lock", tuple(lo["hall_x"]), (lo["hall_y"] - hy / 2, lo["hall_y"] + hy / 2), (L["zc"] - hz / 2, L["zc"] + hz / 2))


def board_ledges(p: dict, L: dict) -> list[tuple[float, float, float]]:
    """Floor ledges under the board (x, y, part-free pad d): two at the south edge, one at the north-east corner."""
    bx, by = L["board"]["x"], L["board"]["y"]
    d = p["cart"]["board_ledge_d"] + 0.6
    return [(bx[0] + 1.0, by[0] + 0.8, d), (bx[1] - 1.0, by[0] + 0.8, d), (bx[1] - 1.0, by[1] - 0.8, d)]


def board_lid_rib(L: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    bx, by = L["board"]["x"], L["board"]["y"]
    return (bx[0] + 0.6, bx[0] + 1.6), (by[0] + 0.3, by[0] + 1.3)


def _receiver_cuts(s: Script, p: dict, L: dict, tag: str) -> list[str]:
    """Bore for the adapter nose, two axial entry channels at entry_deg / +180 and the lug groove (sector band +-sector_deg around +-Y only)."""
    c = p["cart"]
    ad, rc, ca = c["adapter"], c["receiver"], c["cartridge"]
    yc, zc, xf = L["y_c"], L["zc"], L["x_front"]
    xg0 = xf - ad["lug_from_seat"] - ad["lug_t"] - rc["lug_clr"]
    xg1 = xf - ad["lug_from_seat"] + rc["lug_clr"]
    tools = [s.cyl(f"t_rb_{tag}", "X", (0, yc, zc), rc["bore_d"], xf - ad["depth"] - 0.05, xf + 0.1),
             s.cyl(f"t_rn_{tag}", "X", (0, yc, zc), ca["od"] + 2 * c["cradle_clr"], L["collar"][0] - 0.1, xf - ad["depth"] + 0.01)]
    hz = L["r_groove"] * math.sin(math.radians(rc["sector_deg"]))
    s.cyl(f"t_rg_{tag}", "X", (0, yc, zc), 2 * L["r_groove"], xg0, xg1)
    s.add("solid.combine", target=f"t_rg_{tag}", tools=[s.box(f"t_rgb_{tag}", (xg0 - 1, xg1 + 1), (yc - 20, yc + 20), (zc - hz, zc + hz))], operation="intersect", name=f"sector {tag}")
    tools.append(f"t_rg_{tag}")
    rl = ad["nose_od"] / 2 + ad["lug_h"] - ad["lug_w"] / 2
    for k, ang in enumerate((rc["entry_deg"], rc["entry_deg"] + 180.0)):
        y, z = _pol(yc, zc, rl, ang)
        tools.append(s.cyl(f"t_re{k}_{tag}", "X", (0, y, z), ad["lug_w"] + 2 * rc["lug_clr"], xg0, xf + 0.1))
    return tools


def build_housing(s: Script, p: dict, L: dict) -> None:
    c = p["cart"]
    w, Lp, W, H = L["wall"], L["length"], L["width"], L["height"]
    yc, zc, ym = L["y_c"], L["zc"], L["y_m"]
    sh, rc, rb, sl, ca = c["shell"], c["receiver"], c["ribs"], c["slider"], c["cartridge"]
    r_o = sh["corner_r"]
    split = H - w - sh["gasket_t"]                                       # tub up to here, flat lid on a 0.5 gasket above
    s.rrect("bottom", (0, Lp), (0, W), r_o, (0, split))
    s.fillet_chain("bottom", (Lp / 2, 0.0, 0.0), sh["edge_break"])
    s.rrect("t_cav", (w, Lp - w), (w, W - w), r_o - w, (w, split + 0.1))
    s.cut("bottom", ["t_cav"])
    joins, cuts = [], []
    # receiver collar (lane 1 only) in front of the board east edge
    c0, c1 = L["collar"]
    joins.append(s.box("t_collar", (c0, Lp - w + 0.01), (w - 0.01, L["collar_y1"]), (w - 0.01, split)))
    # cartridge cradles, slider U channel, rear + front gear ribs with U slots (drop-in drive), motor saddles
    for k, xs in enumerate(c["cradle_x"]):
        x0 = L["cart"][0] + xs
        joins.append(s.box(f"t_cr{k}", (x0, x0 + c["cradle_t"]), (w - 0.01, yc + ca["od"] / 2 + 0.6), (w - 0.01, zc)))
        cuts.append(s.cyl(f"t_cr_b{k}", "X", (0, yc, zc), ca["od"] + 2 * c["cradle_clr"], x0 - 0.1, x0 + c["cradle_t"] + 0.1))
    ch_w = sl["w"] + 2 * sl["clr"]
    joins.append(s.box("t_ch", (w - 0.01, L["rib_r"][0] + 0.01), (yc - ch_w / 2 - sl["rail_t"], yc + ch_w / 2 + sl["rail_t"]), (w - 0.01, zc + sl["h"] / 2 - sl["rail_drop"])))
    cuts.append(s.box("t_ch_in", (w + c["rear_clr"] - 0.1, L["rib_r"][0] + 0.1), (yc - ch_w / 2, yc + ch_w / 2), (zc - sl["h"] / 2 - sl["clr"], zc + 4.0)))
    gr = L["gear_od"] / 2
    for nm, (x0, x1) in (("t_rib_r", L["rib_r"]), ("t_rib_f", L["rib_f"])):
        joins.append(s.box(nm, (x0, x1), (w - 0.01, min(yc + gr - 0.3, ym - p["drive_nfp"]["motor_d"] / 2 - 0.2)), (w - 0.01, split)))   # stops short of the motor boss
        cuts.append(s.box(f"{nm}_slot", (x0 - 0.1, x1 + 0.1), (yc - rb["slot_w"] / 2, yc + rb["slot_w"] / 2), (zc, split + 0.1)))
        cuts.append(s.cyl(f"{nm}_hole", "X", (0, yc, zc), rb["slot_w"], x0 - 0.1, x1 + 0.1))
    for k, x0 in enumerate((L["motor"][0] + 1.0, L["gearhead"][0] + 2.0)):
        joins.append(s.box(f"t_ms{k}", (x0, x0 + c["motor_saddle_t"]), (ym - 3.6, ym + 3.6), (w - 0.01, zc)))
        cuts.append(s.cyl(f"t_ms_b{k}", "X", (0, ym, zc), p["drive_nfp"]["motor_d"] + 0.1, x0 - 0.1, x0 + c["motor_saddle_t"] + 0.1))
    pz0 = L["board"]["pcb_z"][0]
    bx, by = L["board"]["x"], L["board"]["y"]
    for k, (x, y, _d) in enumerate(board_ledges(p, L)):
        joins.append(s.cyl(f"t_led{k}", "Z", (x, y, 0), c["board_ledge_d"], w - 0.01, pz0))
    s.join("bottom", joins)
    cuts += _receiver_cuts(s, p, L, "b")
    u = L["usb"]
    cuts.append(s.box("t_usb_open", (u["x_c"] - c["usb"]["open_w"] / 2, u["x_c"] + c["usb"]["open_w"] / 2), (W - w - 0.1, W + 0.1),
                      (u["z_c"] - c["usb"]["open_h"] / 2, u["z_c"] + c["usb"]["open_h"] / 2)))
    s.cut("bottom", cuts)
    # flat lid with hold-down ribs (rod slots, board corner), the receiver bore continues through it where the bore reaches above the split
    lt = split + sh["gasket_t"]
    s.rrect("top", (0, Lp), (0, W), r_o, (lt, H))
    s.fillet_chain("top", (Lp / 2, 0.0, H), sh["top_fillet"])
    tj = []
    for nm, (x0, x1) in (("t_lr_r", L["rib_r"]), ("t_lr_f", L["rib_f"])):
        tj.append(s.box(nm, (x0, x1), (yc - rb["slot_w"] / 2 + 0.01, yc + rb["slot_w"] / 2 - 0.01), (zc + c["rod"]["d"] / 2 + 0.1, lt + 0.01)))
    rx, ry = board_lid_rib(L)
    tj.append(s.box("t_lr_bd", rx, ry, (L["board"]["pcb_z"][1], lt + 0.01)))
    s.join("top", tj)
    s.cut("top", _receiver_cuts(s, p, L, "t"))
    s.rrect("lid_gasket", (0.3, Lp - 0.3), (0.3, W - 0.3), r_o - 0.3, (split, lt))
    s.cut("lid_gasket", [s.rrect("t_lg_in", (w + 0.1, Lp - w - 0.1), (w + 0.1, W - w - 0.1), r_o - w - 0.1, (split - 0.1, lt + 0.1))])


def build(p: dict) -> tuple[Script, dict]:
    L = geometry(p)
    s = Script()
    build_housing(s, p, L)
    build_cartridge(s, p, L)
    build_drive(s, p, L)
    build_electronics(s, p, L)
    return s, L
