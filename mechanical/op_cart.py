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
import os
from pathlib import Path

from op_cmds import Script

MFG_PARTS = {"bottom": ["bottom"], "top": ["top"], "slider": ["slider"], "pusher": ["pusher"], "lock_flag": ["lock_flag"], "button": ["button"], "lid_gasket": ["lid_gasket"]}
PURCHASED = ["cartridge", "stopper", "cart_cap", "adapter", "adapter_lug_a", "adapter_lug_b", "adapter_seal", "tubing", "rod", "rod_nut", "gear_rod", "pinion", "washer_r", "washer_f",
             "motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "magnet", "hall_tmag", "lock_magnet", "hall_lock"]
KEEPOUT = ["ko_board", "ko_battery", "ko_usb", "ko_tmag_board"]
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED + KEEPOUT
ADAPTER_A = ["adapter", "adapter_lug_a", "adapter_lug_b", "adapter_seal", "tubing"]
ADAPTER_B = ["b_cap", "needle", "luer_hub", "luer_set"]


def part_names(p: dict) -> list[str]:
    """Bodies of this variant: A = original Insight adapter, B = printed needle cap + bought needle / Luer hub / tubing connector; yoke drive: yoke + stem."""
    names = PART_NAMES
    if p["cart"]["adapter"]["type"] == "needle_cap":
        names = [n for n in PART_NAMES if n not in ADAPTER_A] + ADAPTER_B
    if p["cart"]["adapter"]["type"] == "insight_flat":
        names = [n for n in PART_NAMES if n != "lock_flag"]
    if p["cart"].get("drive_type") == "yoke":
        names = [n for n in names if n != "slider"] + ["yoke", "stem"]
    if p["cart"].get("front_module"):
        names = [n for n in names if not n.startswith("adapter_") and n != "tubing"] + ["front_module", "needle"]
    return names


def mfg_parts(p: dict) -> dict:
    m = dict(MFG_PARTS)
    if p["cart"].get("drive_type") == "yoke":
        m.pop("slider")
        m["yoke"] = ["yoke"]
    if p["cart"]["adapter"]["type"] == "insight_flat":
        m.pop("lock_flag")
    if p["cart"]["adapter"]["type"] == "needle_cap":
        m["b_cap"] = ["b_cap"]
    return m
# pairs that touch or overlap by design (bonded, threaded, meshing, press fit, needle through the septum, stacked keep-outs)
EXCLUDE_PAIRS = [["pinion", "gear_rod"], ["rod", "rod_nut"], ["rod", "gear_rod"], ["rod_nut", "gear_rod"], ["rod", "slider"], ["rod", "pusher"], ["pusher", "stopper"],
                 ["stopper", "cartridge"], ["cart_cap", "cartridge"], ["adapter", "cart_cap"], ["adapter", "cartridge"], ["adapter", "adapter_lug_a"], ["adapter", "adapter_lug_b"], ["adapter", "adapter_seal"], ["adapter_seal", "adapter_lug_a"],
                 ["adapter", "tubing"], ["motor_shaft", "pinion"], ["motor_shaft", "motor_boss"], ["motor_boss", "gearhead"], ["gearhead", "motor"], ["motor", "motor_rear_boss"],
                 ["magnet", "pinion"], ["magnet", "motor_shaft"], ["lock_magnet", "lock_flag"], ["lock_magnet", "adapter"], ["lock_flag", "adapter"], ["lid_gasket", "top"], ["lid_gasket", "bottom"],
                 ["ko_battery", "ko_board"], ["ko_usb", "ko_board"], ["hall_tmag", "ko_tmag_board"], ["washer_r", "gear_rod"], ["washer_f", "gear_rod"], ["button", "bottom"], ["button", "top"],
                 ["stem", "yoke"], ["stem", "pusher"], ["rod_nut", "yoke"],
                 ["b_cap", "cart_cap"], ["needle", "cart_cap"], ["needle", "cartridge"], ["needle", "luer_hub"], ["luer_hub", "luer_set"], ["lock_flag", "b_cap"]]


def prepare(p0: dict, variant: str = "A") -> dict:
    """Resolve the cart block for one variant (cart.variants[variant] merged over the common block): motor preset, derived cartridge numbers."""
    from op_layout import merge
    p = copy.deepcopy(p0)
    var = p["cart"].get("variants", {}).get(variant, {})
    p["cart"] = merge(p["cart"], {k: v for k, v in var.items() if not k.startswith("_")})
    p["cart"]["_variant"] = variant
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
    if rc.get("type") == "cup_bayonet":                      # A since 2026-11-25: socket for the adapter cup, lip ring = bore_d
        r_groove = rc["bore_d"] / 2
    big = max(big, 2 * r_groove * math.sin(math.radians(rc["sector_deg"])))
    zc = w + c["floor_clr"] + big / 2
    H = round(zc + big / 2 + c["roof_clr"] + sh["gasket_t"] + w, 2)
    ad = c["adapter"]
    flat = ad["type"] == "insight_flat"
    y_c = w + c["side_clr"] + big / 2
    if flat:                                                  # the flat Insight adapter's connector-side end is flush with the -Y side
        y_c = max(y_c, ad["conn_from_end"])
        if ad.get("flush"):                                   # owner 2026-11-24: the adapter IS the end face -> the pump takes its cross-section (body_len x body_w)
            if H > ad["body_w"] + 1e-6:
                raise ValueError(f"adapter width {ad['body_w']} < required height {H}: cannot sit flush")
            H = ad["body_w"]
            zc = H / 2 + (c["front_module"].get("bore_offset", 0.0) if c.get("front_module") else 0.0)   # A: bore 0.4 towards the silver side (pump photo)
    a = g["m"] * (g["z_rod"] + g["z_pinion"]) / 2.0                     # centre distance screw axis -> motor axis (standard spur pair)
    yoke = c.get("drive_type") == "yoke"
    y_s = y_c                                                           # drive screw axis (on the cartridge axis for the rod drive)
    if yoke:
        # owner 2026-11-24: nothing behind the cartridge but the pusher: rotating M2 screw BESIDE the barrel (axially fixed, gear on its front end beside
        # the barrel), a printed yoke rides on it (brass nut) and pushes a stem + pusher disc into the cartridge; the yoke foot runs in a floor channel
        yk = c["yoke"]
        y_s = y_c + ca["od"] / 2 + gear_od / 2 + yk["gear_barrel_clr"]
        sl_len = yk["t"]
        x_sl0 = w + yk["rear_clr"]                                     # yoke rear face at FULL
        x_c0 = x_sl0 + sl_len + stroke + c["travel_margin"]            # yoke front face at EMPTY stays travel_margin behind the cartridge
        x_pu1 = x_c0 + ca["stopper_recess"]
        x_pu0 = x_pu1 - pu["t"]
        x_rib_r0 = x_c0
        x_rib_r1 = x_rib_r0 + rb["t"]
        x_g0 = x_rib_r1 + g["washer_t"]
    else:
        sl_len = sl["len"]
        x_sl0 = w + c["rear_clr"]                                       # slider rear face at FULL (rod fully back)
        # the slider runs THROUGH the square hole of the rear rib and stops travel_margin before the rear washer (annulus outside the slider)
        x_g0 = x_sl0 + sl["len"] + stroke + c["travel_margin"] + g["washer_t"]
        x_rib_r1 = x_g0 - g["washer_t"]
        x_rib_r0 = x_rib_r1 - rb["t"]
    x_g1 = x_g0 + g["face_rod"]
    x_rib_f0 = x_g1 + g["washer_t"]
    x_rib_f1 = x_rib_f0 + rb["t"]
    if not yoke:
        x_pu0 = x_rib_f1 + c["pusher_clr"]                              # pusher rear face at FULL
        x_pu1 = x_pu0 + pu["t"]
        x_c0 = x_pu1 - ca["stopper_recess"]                             # cartridge rear end (stopper rear face = pusher front face at FULL)
    y_m = y_s + a
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
    # lane 2 (owner 2026-11-24): new board outline (same chip set as the cup board) ON TOP over the whole lane: above the motor at the rear, above the
    # cell at the front; the cell lies on the floor in front of the TMAG strip; USB-C on the board north edge, button switch on the board underside
    bd, bat, usb, bt = c["board"], c["battery"], c["usb"], c["button"]
    lane2_y0 = y_c + big / 2 + c["lane_clr"]
    lane2_w = max(bat["w"], bd["w"])
    W = round(max(lane2_y0 + lane2_w + c["board_wall_clr"] + w, y_m + dr["motor_d"] / 2 + c["side_clr"] + w), 2)
    ad_y = None
    if flat:                                                  # the adapter lies flush along the front end face: the end face is as wide as the adapter is long
        ad_y = [y_c - ad["conn_from_end"], y_c - ad["conn_from_end"] + ad["body_len"]]
        W = round(max(W, ad_y[1]), 2)
    bed = ad["step_h"] if flat else 0.0                      # A: pocket for the adapter's key step (depth = step height)
    x_seat = x_n1 + ad["seat_to_cap"]                         # adapter seat plane = housing front face
    x_front = x_seat                                          # lane 1 alone sets the length
    length = round(x_front, 2)
    x_ad1 = x_seat + ad["body_h"] if flat else x_front + ad["out_len"]
    if ad["type"] == "needle_cap":
        nc = c["needle_cap"]
        x_ad1 = x_n1 - nc["tip_past_cap"] + nc["needle_len"] + nc["hub_len"] + 3.0     # cap + hub + coupled Luer collar
    collar = [x_front - rc["collar_len"], x_front]
    collar_y1 = y_c + r_groove + rc["collar_wall"]
    stroke_avail = (x_c1 - ca["shoulder_inset"]) - x_st1
    y_bd1 = W - w - c["board_wall_clr"]
    y_bd0 = y_bd1 - bd["w"]
    x_bd0 = bd["x0"]
    x_bd1 = collar[0] - c["board_front_clr"] if y_bd0 < collar_y1 else x_front - w - bed - 0.3
    sc = c["screws"]
    if y_bd1 > W - sc["inset"] - sc["boss_d"] / 2:          # front lid-screw boss sits in the board's +Y corner: end the board before it
        x_bd1 = min(x_bd1, x_front - max(sc["inset"], w + bed + sc["boss_d"] / 2 + 0.15) - sc["boss_d"] / 2 - 0.3)
    tm_top = zc + 2.6
    pz0 = round(max(zc + dr["motor_d"] / 2, tm_top) + 0.1 + bd["bottom_parts"], 3)
    pz = [pz0, pz0 + bd["t"]]
    L = {"length": length, "width": W, "height": H, "wall": w, "zc": zc, "y_c": y_c, "y_m": y_m, "a_gear": a, "big": round(big, 3), "gear_od": gear_od,
         "stroke": stroke, "stroke_avail": round(stroke_avail, 2), "bore_area": round(c["_bore_area"], 3), "x_front": x_front,
         "front_governed_by": "lane 1: cartridge + stroke + drive", "length_with_adapter": round(x_ad1, 2),
         "slider_full": [x_sl0, x_sl0 + sl_len], "y_s": y_s, "yoke": yoke, "rib_r": [x_rib_r0, x_rib_r1], "gear": [x_g0, x_g1], "rib_f": [x_rib_f0, x_rib_f1],
         "pusher_full": [x_pu0, x_pu1], "cart": [x_c0, x_c1], "neck": [x_c1, x_n1], "stopper_full": [x_st0, x_st1], "rod_full": [x_sl0, x_pu0],
         "rod_len": round(x_pu0 - x_sl0, 2) if not yoke else round(x_rib_f1 + c["yoke"]["screw_front"] - (w - c["yoke"]["screw_in_wall"]), 2), "adapter": [x_seat - ad["depth"], x_ad1], "x_seat": x_seat, "bed": bed, "adapter_y": ad_y, "collar": collar, "collar_y1": round(collar_y1, 3), "r_groove": r_groove,
         "pinion": [x_pin0, x_pin1], "boss": [x_boss0, x_boss1], "gearhead": [x_gh0, x_boss0], "motor": [x_mo0, x_gh0], "rear_boss": [x_tail0, x_mo0],
         "magnet": [x_mag0, x_mag1], "tmag": [x_tm0, x_tm1], "lane2_y0": lane2_y0}
    fm = c.get("front_module")
    if fm:                                                    # A: the tested FACE4 lock face is its own part over the front `depth` mm
        x_bd1 = min(x_bd1, x_front - fm["depth"] - 0.3)
    x_bd1_max = x_bd1
    if bd.get("l"):                                           # one common board for A and B (fixed outline), must fit the shorter lane
        x_bd1 = x_bd0 + bd["l"]
    L["board_x1_max"] = round(x_bd1_max, 3)
    L["board"] = {"x": [x_bd0, x_bd1], "y": [y_bd0, y_bd1], "z": [pz0 - bd["bottom_parts"], pz[1] + bd["top_parts"]], "pcb_z": pz,
                  "outline_mm": [round(x_bd1 - x_bd0, 2), bd["w"]], "area_mm2": round((x_bd1 - x_bd0) * bd["w"], 1)}
    xb0 = x_boss0 + c["board_gap_x"]                          # cell on the floor from the motor boss on: it passes under the pinion and the TMAG strip (both above z 4.75)
    L["battery"] = {"x": [xb0, xb0 + bat["l"]], "y": [y_bd0, y_bd0 + bat["w"]], "z": [w, w + bat["t"]]}            # cell under the board
    xu = x_bd1 - usb["x_from_board_east"]
    zu = (pz[0] + pz[1]) / 2
    L["usb"] = {"x": [xu - usb["w"] / 2, xu + usb["w"] / 2], "y": [W - w - usb["d"], W - w], "z": [zu - usb["h"] / 2, zu + usb["h"] / 2], "x_c": xu, "z_c": zu}
    L["button_x"] = round(x_bd1 - bt["x_from_board_east"], 2)
    L["button_z"] = round(pz0 - bt["below_pcb"], 3)
    bf = c.get("board_front")
    if bf:
        # owner 2026-11-24 (taper): board + cell in the FRONT zone beside the cartridge (full width only there), cell crosswise on the floor under the board
        x_bd0 = bf["x0"]
        x_bd1 = x_bd0 + bf["l"]
        y_bd1 = W - w - c["board_wall_clr"]
        y_bd0 = y_bd1 - bf["w"]
        pz0 = round(w + bat["t"] + 0.02 + bd["bottom_parts"], 3)
        pz = [pz0, pz0 + bd["t"]]
        L["board_x1_max"] = round(x_front - max(sc["inset"], w + bed + sc["boss_d"] / 2 + 0.15) - sc["boss_d"] / 2 - 0.3, 3)
        L["board"] = {"x": [x_bd0, x_bd1], "y": [y_bd0, y_bd1], "z": [pz0 - bd["bottom_parts"], pz[1] + bd["top_parts"]], "pcb_z": pz,
                      "outline_mm": [bf["l"], bf["w"]], "area_mm2": round(bf["l"] * bf["w"], 1)}
        yb1 = W - w - 0.3
        zb0 = w
        if bf.get("cell_floor") is not None:                  # A since 2026-11-26: the far edge is rounded (end-face section R5): cell moves
            yb1 = bf["cell_y1"]                               # inward under the cartridge lane, in a floor pocket (floor cell_floor)
            zb0 = bf["cell_floor"]
        L["battery"] = {"x": [x_bd0 + bf["cell_dx"], x_bd0 + bf["cell_dx"] + bat["w"]], "y": [yb1 - bat["l"], yb1], "z": [zb0, zb0 + bat["t"]],
                        "pocket": zb0 < w}
        xu = x_bd0 + bf["usb_x"]
        zu = (pz[0] + pz[1]) / 2
        L["usb"] = {"x": [xu - usb["w"] / 2, xu + usb["w"] / 2], "y": [W - w - usb["d"], W - w], "z": [max(zu - usb["h"] / 2, w + bat["t"] + 0.02), zu + usb["h"] / 2],
                    "x_c": xu, "z_c": zu}
        L["button_x"] = round(x_bd0 + bf["button_x"], 2)
        L["button_z"] = round(pz0 - bt["below_pcb"], 3)
        if bf.get("switch_on_top"):                            # A: the rounded far edge (R5) ends at z 5: SW1 on the board top face, button above it
            L["button_z"] = round(pz[1] + bf["switch_on_top"], 3)
    lk = c["lock"]
    yh = collar_y1 + 0.1 + lk["hall_pkg"][1] / 2
    if flat:                                                  # magnet bonded in the adapter underside near its tubing end, hall behind the front plate
        yh = ad_y[1] - lk["flat_mag_from_end"]
    x_hall1 = x_front - (c["front_module"]["depth"] + 0.2 if c.get("front_module") else w + bed + 0.1)     # behind the front module (A)
    L["lock"] = {"hall_x": [x_hall1 - lk["hall_pkg"][0], x_hall1], "hall_y": yh,
                 "magnet_r": round(yh - y_c, 3)}
    L["empty"] = {"slider": [x_sl0 + stroke, x_sl0 + sl_len + stroke], "pusher": [x_pu0 + stroke, x_pu1 + stroke],
                  "stopper": [x_st0 + stroke, x_st1 + stroke], "rod": [x_sl0 + stroke, x_pu0 + stroke]}
    L["rod_past_nut_empty"] = round(L["empty"]["rod"][0] - x_g0, 2)          # < 0: the rod rear end is still behind the nut at EMPTY (engaged)
    L["slider_to_rib_empty"] = round(x_rib_r1 - L["empty"]["slider"][1], 2)       # slider front face to the rear washer at EMPTY
    if yoke:
        yk = c["yoke"]
        L["screw"] = [w - yk["screw_in_wall"], x_rib_f1 + yk["screw_front"]]          # rotating screw, rear end in a pocket of the rear wall
        L["stem"] = [x_sl0 + sl_len, x_pu0]
        L["empty"]["stem"] = [L["stem"][0] + stroke, L["stem"][1] + stroke]
        L["empty"]["rod"] = L["empty"]["stem"]
        L["rod_past_nut_empty"] = round(-(L["screw"][1] - L["empty"]["slider"][1]), 2)   # < 0: nut still on the screw at EMPTY
        L["slider_to_rib_empty"] = round(x_rib_r0 - L["empty"]["slider"][1], 2)          # yoke front to the rear gear rib at EMPTY
    L["length_total"] = round(x_ad1, 2)
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
    # ISO 13926-1 glass cylinder (1.6 ml row, VERIFIED table): barrel d1/d2 up to x1, rounded shoulder (here a cone) down to the neck d5,
    # neck, collar d4 x h2 under the aluminium crimp cap (cap OD measured 7.5), septum under the cap's centre hole
    sh_len = ca.get("shoulder_len", ca["shoulder_inset"])
    cap0 = n1 - ca["cap_len"]
    s.tube("cartridge", "X", (0, yc, zc), ca["od"], ca["id"], x0, x1)
    s.cone("t_cart_sh", "X", (0, yc, zc), ca["od"] / 2, ca["neck_od"] / 2, x1 - 0.01, x1 + sh_len)
    s.cyl("t_cart_neck", "X", (0, yc, zc), ca["neck_od"], x1 + sh_len - 0.01, cap0 + 0.01)
    s.join("cartridge", ["t_cart_sh", "t_cart_neck"])
    s.cut("cartridge", [s.cone("t_cart_shi", "X", (0, yc, zc), ca["id"] / 2, ca["neck_id"] / 2, x1 - 0.01, x1 + sh_len - 0.8),
                        s.cyl("t_cart_nb", "X", (0, yc, zc), ca["neck_id"], x1 - 0.05, n1 + 0.1)])
    s.cyl("cart_cap", "X", (0, yc, zc), ca["cap_od"], cap0, n1)                                     # aluminium crimp cap over collar + septum
    s.cut("cart_cap", [s.cyl("t_cap_hole", "X", (0, yc, zc), ca.get("cap_hole_d", 3.0), n1 - 0.3, n1 + 0.1)])     # septum window in the cap top
    s.cyl("stopper", "X", (0, yc, zc), ca["id"], *L["stopper_full"])
    xa0, xa1 = L["adapter"]
    xf = L["x_front"]
    lk, lo = c["lock"], L["lock"]
    if ad["type"] == "insight_flat":
        build_insight_flat(s, p, L)
        s.cyl("lock_magnet", "X", (0, lo["hall_y"], zc), lk["mag_d"], L["x_seat"] + 0.05, L["x_seat"] + 0.05 + lk["mag_t"])    # bonded in a drilled pocket of the adapter underside (VERIFY)
        return
    if ad["type"] == "needle_cap":
        build_needle_cap(s, p, L)
    else:
        build_insight_adapter(s, p, L)
    # adapter-locked detection: a printed flag clipped on the adapter body carries a d1 x 0.5 magnet in front of the lock hall (VERIFY on the sample)
    s.box("lock_flag", (xf + 0.05, xf + 0.05 + lk["flag_t"]), (yc + ad["body_d"] / 2 - 0.6, lo["hall_y"] + 1.0), (zc - 1.0, zc + 1.0))
    s.cyl("lock_magnet", "X", (0, lo["hall_y"], zc), lk["mag_d"], xf + 0.05, xf + 0.05 + lk["mag_t"])


def build_insight_adapter(s: Script, p: dict, L: dict) -> None:
    """Variant A: the original Accu-Chek Insight adapter (bought, unmodified), envelope ESTIMATE."""
    c = p["cart"]
    ca, ad, rc = c["cartridge"], c["adapter"], c["receiver"]
    yc, zc = L["y_c"], L["zc"]
    n1 = L["neck"][1]
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


def build_insight_flat(s: Script, p: dict, L: dict) -> None:
    """Variant A: the original Accu-Chek Insight Adapter & Tubing as seen in the manual / product photos: a flat, elongated, domed body that lies flush on the
    end face (long axis along Y when locked), a short connector cylinder under its connector-side end goes into the receiver bore (needle on the septum,
    two lugs, about 90 deg clockwise turn), tubing leaves the other narrow end. Envelope ESTIMATE from the manual renders (pump 52 x 19 as the scale)."""
    c = p["cart"]
    if c.get("front_module"):                                 # A since 2026-11-26: adapter dummy derived from the tested face, built in build_front_module
        return
    ca, ad, rc = c["cartridge"], c["adapter"], c["receiver"]
    yc, zc, xs = L["y_c"], L["zc"], L["x_seat"]
    y0, y1 = L["adapter_y"]
    n1 = L["neck"][1]
    sh = c["shell"]
    Lt, W, H = L["length_total"], L["width"], L["height"]
    outline_prism(s, p, L, "adapter", 0.0, (0, H))                                # same outer block + edge radii as the housing: flush outline
    s.fillet_chain("adapter", (Lt / 2, 0.0, 0.0), sh["top_fillet"])
    s.fillet_chain("adapter", (Lt / 2, 0.0, H), sh["top_fillet"])
    s.add("solid.combine", target="adapter", tools=[s.box("t_ad_keep", (xs, Lt + 1), (-1, W + 1), (-1, H + 1))], operation="intersect", name="adapter end")
    if rc.get("type") == "cup_bayonet":
        _adapter_cup(s, p, L)
        s.cyl("tubing", "Y", (xs + ad["tube_x_above_base"], 0, zc), ad["tube_d"], y1 - 1.0, y1 + 8.0)
        return
    st = step_box(p, L, 0.0)
    s.box("t_ad_step", (xs - ad["step_h"], xs + 0.01), st[0], st[1])          # key step under the tubing half
    s.cyl("t_ad_conn", "X", (0, yc, zc), ad["nose_od"], xs - ad["depth"], xs + 0.01)
    s.join("adapter", ["t_ad_step", "t_ad_conn"])
    s.cut("adapter", [s.cyl("t_ad_cav", "X", (0, yc, zc), ca["cap_od"] + 0.1, xs - ad["depth"] - 0.1, n1 + ad["cap_gap"])])
    rl = ad["nose_od"] / 2 + ad["lug_h"] - ad["lug_w"] / 2
    for nm, ang in (("adapter_lug_a", rc["lock_deg"]), ("adapter_lug_b", rc["lock_deg"] + 180.0)):
        y, z = _pol(yc, zc, rl, ang)
        s.cyl(nm, "X", (0, y, z), ad["lug_w"], xs - ad["lug_from_seat"] - ad["lug_t"], xs - ad["lug_from_seat"])
    s.cyl("tubing", "Y", (xs + ad["tube_x_above_base"], 0, zc), ad["tube_d"], y1 - 1.0, y1 + 8.0)       # far end, ~2 above the underside (D720,449 Fig. 8)


def _adapter_cup(s: Script, p: dict, L: dict) -> None:
    """Dummy of the real adapter's underside (owner photos 2026-11-25, PHOTO-ESTIMATE): body sits seal_gap off the face on the white ring, cup + rim lips
    in the socket (lips under the tabs = locked), far half beyond the arc stands step_h proud into the face recess."""
    c = p["cart"]
    ad, rc, ca = c["adapter"], c["receiver"], c["cartridge"]
    cp = ad["cup"]
    yc, zc, xs, W, H = L["y_c"], L["zc"], L["x_seat"], L["width"], L["height"]
    Lt = L["length_total"]
    n1 = L["neck"][1]
    g = cp["seal_gap"]
    s.cut("adapter", [s.box("t_ad_gap", (xs - 1, xs + g), (-1, W + 1), (-1, H + 1))])
    s.box("t_ad_step", (xs + g - ad["step_h"], xs + g + 0.01), (yc, W + 1), (-1, H + 1))
    s.cut("t_ad_step", [s.cyl("t_ad_stc", "X", (0, yc, zc), 2 * cp["step_r"], xs - 5, xs + 5)])
    s.add("solid.combine", target="t_ad_step", tools=[outline_prism(s, p, L, "t_ad_stk", 0.0, (0, H))], operation="intersect", name="step in outline")
    s.cyl("t_ad_cup", "X", (0, yc, zc), cp["od"], xs - cp["proud"], xs + g + 0.01)
    s.join("adapter", ["t_ad_step", "t_ad_cup"])
    s.cut("adapter", [s.cyl("t_ad_cav", "X", (0, yc, zc), max(cp["id"], ca["cap_od"] + 0.1), xs - cp["proud"] - 0.1, n1 + ad["cap_gap"])])
    ws = lug_widths(cp)
    for k, nm in enumerate(("adapter_lug_a", "adapter_lug_b")):                                                     # the two hook lugs (locked position)
        deg = rc["lock_deg"] + 180.0 * k
        s.cyl(nm, "X", (0, yc, zc), cp["lip_od"], xs - cp["proud"], xs - cp["proud"] + cp["lip_h"])
        s.cut(nm, [s.cyl(f"t_ad_lipin{k}", "X", (0, yc, zc), cp["od"] + 0.01, xs - cp["proud"] - 1, xs)])
        s.add("solid.combine", target=nm, tools=[_half(s, f"t_ad_half{k}", L, (xs - 10, xs + 1), deg)], operation="intersect", name=f"lug {k} side")   # one piece per body
        s.add("solid.combine", target=nm, tools=[_band(s, f"t_ad_lipb{k}", L, (xs - 10, xs + 1), ws[k] / 2, deg)], operation="intersect", name=f"lug {k}")
    s.cyl("adapter_seal", "X", (0, yc, zc), cp["seal_od"], xs, xs + g)                                              # white ring (compressed)
    s.cut("adapter_seal", [s.cyl("t_ad_sealin", "X", (0, yc, zc), cp["od"] + 0.02, xs - 1, xs + 1)])


def needle_cap_geom(p: dict, L: dict) -> dict:
    nc = p["cart"]["needle_cap"]
    n1 = L["neck"][1]
    tip = n1 - nc["tip_past_cap"]                          # needle tip inside the cartridge neck, past the septum
    x_hn = tip + nc["needle_len"]                          # hub nose (needle end)
    return {"tip": tip, "x_hn": x_hn, "x_cap1": x_hn + nc["hub_seat"], "x_hub1": x_hn + nc["hub_len"]}       # hub nose sits in a shallow centring seat


def build_needle_cap(s: Script, p: dict, L: dict) -> None:
    """Variant B: printed bayonet cap (same nose + lugs as the Insight adapter estimate, so it locks in the same receiver), pressing the crimp cap
    with its inner face; it centres a standard Luer-lock hypodermic needle on the septum axis; the hub's female Luer takes the tubing set."""
    c = p["cart"]
    ca, ad, rc, nc = c["cartridge"], c["adapter"], c["receiver"], c["needle_cap"]
    yc, zc = L["y_c"], L["zc"]
    n1 = L["neck"][1]
    xa0 = L["adapter"][0]
    xf = L["x_front"]
    G = needle_cap_geom(p, L)
    s.cyl("b_cap", "X", (0, yc, zc), ad["nose_od"], xa0, xf)
    s.cyl("t_bc_body", "X", (0, yc, zc), ad["body_d"], xf, G["x_cap1"])
    rl = ad["nose_od"] / 2 + ad["lug_h"] - ad["lug_w"] / 2
    lugs = []
    for k, ang in enumerate((rc["lock_deg"], rc["lock_deg"] + 180.0)):
        y, z = _pol(yc, zc, rl, ang)
        lugs.append(s.cyl(f"t_bc_lug{k}", "X", (0, y, z), ad["lug_w"], xf - ad["lug_from_seat"] - ad["lug_t"], xf - ad["lug_from_seat"]))
    s.join("b_cap", ["t_bc_body"] + lugs)
    s.cut("b_cap", [s.cyl("t_bc_cav", "X", (0, yc, zc), ca["cap_od"] + 0.3, xa0 - 0.1, n1),
                    s.cyl("t_bc_ndl", "X", (0, yc, zc), nc["hole_d"], n1 - 0.1, G["x_hn"] + 0.01),
                    s.cyl("t_bc_hub", "X", (0, yc, zc), nc["hub_nose_d"] + 0.25, G["x_hn"], G["x_cap1"] + 0.1)])
    s.cyl("needle", "X", (0, yc, zc), nc["needle_d"], G["tip"], G["x_hn"] + 0.5)
    s.cyl("luer_hub", "X", (0, yc, zc), nc["hub_nose_d"], G["x_hn"], G["x_hn"] + nc["hub_nose_len"])
    s.cyl("t_lh_body", "X", (0, yc, zc), nc["hub_d"], G["x_hn"] + nc["hub_nose_len"] - 0.01, G["x_hub1"])
    s.join("luer_hub", ["t_lh_body"])
    s.cyl("luer_set", "X", (0, yc, zc), nc["coupler_clear_d"] - 0.6, G["x_hub1"] - 6.0, G["x_hub1"] + 3.0)     # male Luer-lock collar of the tubing set (ESTIMATE)
    s.cut("luer_set", [s.cyl("t_ls_in", "X", (0, yc, zc), nc["hub_d"] + 0.2, G["x_hub1"] - 6.1, G["x_hub1"] + 0.01)])


def build_yoke(s: Script, p: dict, L: dict, name: str = "yoke", dx: float = 0.0) -> list[str]:
    """Printed yoke at the screw (nut pocket), arm across to the cartridge axis (stem socket), foot down into the floor channel. Returns body names."""
    c = p["cart"]
    yk, nut = c["yoke"], c["nut"]
    yc, zc, ys = L["y_c"], L["zc"], L["y_s"]
    x0, x1 = L["slider_full"][0] + dx, L["slider_full"][1] + dx
    yf = (yc + ys) / 2
    s.box(name, (x0, x1), (ys - yk["block"] / 2, ys + yk["block"] / 2), (zc - yk["block"] / 2, zc + yk["block"] / 2))
    parts = [s.box(f"t_{name}_arm", (x0, x1), (yc - yk["boss_d"] / 2, ys), (zc - yk["arm_h"] / 2, zc + yk["arm_h"] / 2)),
             s.cyl(f"t_{name}_boss", "X", (0, yc, zc), yk["boss_d"], x0, x1),
             s.box(f"t_{name}_foot", (x0, x1), (yf - yk["foot_w"] / 2, yf + yk["foot_w"] / 2), (L["wall"] + yk["foot_gap"], zc - yk["arm_h"] / 2 + 0.01))]
    s.join(name, parts)
    s.cut(name, [s.cyl(f"t_{name}_scr", "X", (0, ys, zc), c["rod"]["d"] + 0.4, x0 - 0.1, x1 + 0.1),
                 s.hexprism(f"t_{name}_hex", (x1 - nut["h"], x1 + 0.1), ys, zc, nut["af"] / 2 + 0.05),
                 s.cyl(f"t_{name}_stem", "X", (0, yc, zc), yk["stem_d"], x0 + yk["stem_in"], x1 + 0.1)])
    return [name]


def build_drive_yoke(s: Script, p: dict, L: dict) -> None:
    c, dr = p["cart"], p["drive_nfp"]
    g, rd, pu, nut, yk = c["gears"], c["rod"], c["pusher"], c["nut"], c["yoke"]
    yc, zc, ys = L["y_c"], L["zc"], L["y_s"]
    s.cyl("rod", "X", (0, ys, zc), rd["d"], *L["screw"])                                         # rotating M2 screw beside the barrel
    build_yoke(s, p, L)
    x1 = L["slider_full"][1]
    s.hexprism("rod_nut", (x1 - nut["h"], x1), ys, zc, nut["af"] / 2)
    s.cut("rod_nut", [s.cyl("t_nut_bore", "X", (0, ys, zc), rd["d"], x1 - nut["h"] - 0.1, x1 + 0.1)])
    s.cyl("stem", "X", (0, yc, zc), yk["stem_d"], L["slider_full"][0] + yk["stem_in"], L["stem"][1] + pu["stem_in"])
    s.cyl("pusher", "X", (0, yc, zc), pu["d"], *L["pusher_full"])
    s.cut("pusher", [s.cyl("t_pu_bore", "X", (0, yc, zc), yk["stem_d"], L["pusher_full"][0] - 0.1, L["pusher_full"][0] + pu["stem_in"])])
    g0, g1 = L["gear"]
    s.tube("gear_rod", "X", (0, ys, zc), L["gear_od"], rd["d"], g0, g1)                          # z40 bonded (or tapped) on the screw
    s.tube("washer_r", "X", (0, ys, zc), g["washer_od"], rd["d"] + 0.2, L["rib_r"][1], g0)
    s.tube("washer_f", "X", (0, ys, zc), g["washer_od"], rd["d"] + 0.2, g1, L["rib_f"][0])
    _build_motor(s, p, L)


def _build_motor(s: Script, p: dict, L: dict) -> None:
    c, dr = p["cart"], p["drive_nfp"]
    g = c["gears"]
    zc, ym = L["zc"], L["y_m"]
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
    s.box("ko_tmag_board", (L["tmag"][1], L["tmag"][1] + tm["board_t"]), (ym - 2.6, ym + 2.6), (zc - 2.6, zc + 2.6))


def build_drive(s: Script, p: dict, L: dict) -> None:
    if L.get("yoke"):
        build_drive_yoke(s, p, L)
        return
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
    s.tube("washer_r", "X", (0, yc, zc), g["washer_r_od"], g["washer_r_id"], L["rib_r"][1], g0)       # bears on the gear outside the slider path
    s.tube("washer_f", "X", (0, yc, zc), g["washer_od"], rd["d"] + 0.2, g1, L["rib_f"][0])
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
    pads += [s.cyl(f"t_kb_padt{k}", "Z", (x, y, 0), d, pz[1], bz[1] + 0.1) for k, (x, y, d) in enumerate(board_ledges(p, L))]   # lid pins
    rx, ry = board_lid_rib(L)
    pads.append(s.box("t_kb_rib", (rx[0] - 0.3, rx[1] + 0.3), (ry[0] - 0.3, ry[1] + 0.3), (pz[1], bz[1] + 0.1)))
    s.cut("ko_board", pads)                                                                     # part-free pads on both board faces
    lk, lo = p["cart"]["lock"], L["lock"]
    hx, hy, hz = lk["hall_pkg"]
    s.box("hall_lock", tuple(lo["hall_x"]), (lo["hall_y"] - hy / 2, lo["hall_y"] + hy / 2), (L["zc"] - hz / 2, L["zc"] + hz / 2))


def board_ledges(p: dict, L: dict) -> list[tuple[float, float, float]]:
    """Posts from the floor to the board underside (x, y, part-free pad d): one at the rear (behind the motor), two at the front (in front of the cell)."""
    bx, by = L["board"]["x"], L["board"]["y"]
    d = p["cart"]["board_ledge_d"] + 0.6
    if p["cart"].get("board_front"):                          # posts east of the crosswise cell
        xe = L["battery"]["x"][1] + 1.0
        return [(xe, by[0] + 0.9, d), (bx[1] - 1.0, by[0] + 0.9, d), (bx[1] - 1.0, by[1] - 0.9, d)]
    return [(bx[0] + 1.2, by[0] + 1.0, d), (bx[1] - 1.0, by[0] + 0.9, d), (bx[1] - 1.0, by[1] - 0.9, d)]


def board_lid_rib(L: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    bx, by = L["board"]["x"], L["board"]["y"]
    return (bx[1] - 4.0, bx[1] - 3.0), (by[0] + 0.3, by[0] + 1.3)


def _receiver_cuts(s: Script, p: dict, L: dict, tag: str) -> list[str]:
    """Bore for the adapter nose, two axial entry channels at entry_deg / +180 and the lug groove (sector band +-sector_deg around +-Y only)."""
    c = p["cart"]
    ad, rc, ca = c["adapter"], c["receiver"], c["cartridge"]
    if rc.get("type") == "cup_bayonet":
        return _cup_socket_cuts(s, p, L, tag)
    yc, zc, xf, xs = L["y_c"], L["zc"], L["x_front"], L["x_seat"]
    xg0 = xs - ad["lug_from_seat"] - ad["lug_t"] - rc["lug_clr"]
    xg1 = xs - ad["lug_from_seat"] + rc["lug_clr"]
    tools = [s.cyl(f"t_rb_{tag}", "X", (0, yc, zc), rc["bore_d"], xs - ad["depth"] - 0.05, xf + 0.1),
             s.cyl(f"t_rn_{tag}", "X", (0, yc, zc), ca["od"] + 2 * c["cradle_clr"], L["collar"][0] - 0.1, xs - ad["depth"] + 0.01)]
    hz = L["r_groove"] * math.sin(math.radians(rc["sector_deg"]))
    s.cyl(f"t_rg_{tag}", "X", (0, yc, zc), 2 * L["r_groove"], xg0, xg1)
    s.add("solid.combine", target=f"t_rg_{tag}", tools=[s.box(f"t_rgb_{tag}", (xg0 - 1, xg1 + 1), (yc - 20, yc + 20), (zc - hz, zc + hz))], operation="intersect", name=f"sector {tag}")
    tools.append(f"t_rg_{tag}")
    ew = rc.get("entry_w") or [ad["lug_w"], ad["lug_w"]]                   # optional keyed lugs (patent: one wide, one narrow)
    for k, ang in enumerate((rc["entry_deg"], rc["entry_deg"] + 180.0)):
        rl = ad["nose_od"] / 2 + ad["lug_h"] - ew[k] / 2
        y, z = _pol(yc, zc, rl, ang)
        tools.append(s.cyl(f"t_re{k}_{tag}", "X", (0, y, z), ew[k] + 2 * rc["lug_clr"], xg0, xf + 0.1))
    if rc.get("cbore_d"):                                                   # optional counterbore for a flange at the nose base
        tools.append(s.cyl(f"t_rcb_{tag}", "X", (0, yc, zc), rc["cbore_d"], xs - rc["cbore_depth"], xf + 0.1))
    if L.get("adapter_y"):
        tools.append(bed_tool(s, p, L, tag))
    return tools


def lug_widths(cp: dict) -> list[float]:
    """Chord width of the two cup lugs: [lug at lock_deg (far half), opposite lug]; keyed when unequal."""
    w = cp.get("lug_w")
    if w is None:
        a = cp["lip_arc_deg"]
        return [2 * cp["lip_od"] / 2 * math.sin(math.radians(min(a, 179.0) / 2))] * 2
    return list(w) if isinstance(w, (list, tuple)) else [w, w]


def cup_geom(p: dict, L: dict) -> dict:
    """Derived cup-socket numbers (variant A, owner photos 2026-11-25): tab depth, window half-widths, recess radius / depth, hook and ball positions."""
    ad, rc = p["cart"]["adapter"], p["cart"]["receiver"]
    cp = ad["cup"]
    tab_depth = cp["proud"] - cp["lip_h"] - rc["tab_axial_clr"]
    band_h = [w / 2 + rc["lip_clr"] for w in lug_widths(cp)]
    r_rec = rc.get("recess_r", cp["step_r"] - rc["step_clr"])
    rec_d = ad["step_h"] - cp["seal_gap"] + rc["step_clr"]
    yh = L["y_c"] + math.sqrt(max(cp["hook_r"] ** 2 - cp["hook_off"] ** 2, 0.0))
    return {"tab_depth": tab_depth, "band_h": band_h, "r_rec": r_rec, "rec_d": rec_d, "y_hook": yh}

def _band(s: Script, name: str, L: dict, x: tuple[float, float], h: float, deg: float) -> str:
    """Slab through the socket axis, half-width h, containing the directions deg and deg + 180 (0 = +Y, 90 = +Z)."""
    yc, zc = L["y_c"], L["zc"]
    s.box(name, x, (yc - 30, yc + 30), (zc - h, zc + h))
    if abs(deg) > 1e-6:
        s.add("solid.move", bodies=[name], axis=[1, 0, 0], angle=f"{deg} deg", origin=[0, yc, zc])
    return name


def _half(s: Script, name: str, L: dict, x: tuple[float, float], deg: float) -> str:
    """Half space (as a big box) on the side of the direction deg (0 = +Y, 90 = +Z) of the socket axis."""
    yc, zc = L["y_c"], L["zc"]
    s.box(name, x, (yc, yc + 40), (zc - 40, zc + 40))
    if abs(deg) > 1e-6:
        s.add("solid.move", bodies=[name], axis=[1, 0, 0], angle=f"{deg} deg", origin=[0, yc, zc])
    return name


def _undercut_pockets(s: Script, p: dict, L: dict, tag: str, G: dict, x_bot: float, x_tab: float) -> list[str]:
    """Two bayonet pockets under the rim: each runs travel_deg clockwise (seen from the face: decreasing angle) from its window to a radial stop face;
    optional snap bump (radial snap_bump) just past the lug's final position."""
    rc, cp = p["cart"]["receiver"], p["cart"]["adapter"]["cup"]
    yc, zc = L["y_c"], L["zc"]
    R = rc["bore_d"] / 2
    out = []
    for k in range(2):
        a0 = rc["entry_deg"] + 180.0 * k
        a1 = a0 - rc["travel_deg"]
        dl = math.degrees(math.asin(min(G["band_h"][k] / R, 0.99)))
        lo, hi = a1 - dl, a0 + dl
        nm = f"t_ru{k}_{tag}"
        s.cyl(nm, "X", (0, yc, zc), rc["bore_d"], x_bot, x_tab + 0.01)
        for j, d in enumerate((lo + 90.0, hi - 90.0)):
            s.add("solid.combine", target=nm, tools=[_half(s, f"t_ruh{k}{j}_{tag}", L, (x_bot - 1, x_tab + 1), d)], operation="intersect",
                  name=f"pocket {k} side {j} {tag}")
        if rc.get("snap_bump"):
            wl = lug_widths(cp)[k] / 2
            ab = math.radians(a1 + math.degrees(math.asin(min((wl + 0.6) / R, 0.99))))
            rb = R + 0.5 - rc["snap_bump"]
            s.cut(nm, [s.cyl(f"t_rsb{k}_{tag}", "X", (0, yc + rb * math.cos(ab), zc + rb * math.sin(ab)), 1.0, x_bot - 0.1, x_tab + 0.1)])
        out.append(nm)
    return out


def _cup_socket_cuts(s: Script, p: dict, L: dict, tag: str) -> list[str]:
    """Socket for the Insight adapter cup: tab bore (retaining tabs), entry gaps, lip ring under the tabs, cartridge passage, step recess with catch notches."""
    c = p["cart"]
    ad, rc, ca = c["adapter"], c["receiver"], c["cartridge"]
    cp = ad["cup"]
    yc, zc, xf, xs, W, H = L["y_c"], L["zc"], L["x_front"], L["x_seat"], L["width"], L["height"]
    G = cup_geom(p, L)
    x_tab = xs - G["tab_depth"]
    x_bot = xs - cp["proud"] - rc["tab_axial_clr"]
    tools = [s.cyl(f"t_rt_{tag}", "X", (0, yc, zc), rc["tab_id"], x_bot - 0.01, xf + 0.1),                       # through the rim down to the pocket floor (cup body)
             s.cyl(f"t_rn_{tag}", "X", (0, yc, zc), ca["od"] + 2 * c["cradle_clr"], L["collar"][0] - 0.1, x_bot + 0.01)]
    tools += _undercut_pockets(s, p, L, tag, G, x_bot, x_tab)
    for k in range(2):                                                                                       # 2 windows (entry gaps), per-side width
        deg = rc["entry_deg"] + 180.0 * k
        nm = f"t_re{k}_{tag}"
        s.cyl(nm, "X", (0, yc, zc), rc["bore_d"], x_tab - 0.01, xf + 0.1)
        s.add("solid.combine", target=nm, tools=[_half(s, f"t_reh{k}_{tag}", L, (x_tab - 1, xf + 1), deg)], operation="intersect", name=f"window {k} side {tag}")
        s.add("solid.combine", target=nm, tools=[_band(s, f"t_reb{k}_{tag}", L, (x_tab - 1, xf + 1), G["band_h"][k], deg)], operation="intersect", name=f"window {k} {tag}")
        tools.append(nm)
    if rc.get("cbore_d"):                                                                                     # seal seat for the white ring
        tools.append(s.cyl(f"t_rcb_{tag}", "X", (0, yc, zc), rc["cbore_d"], xs - rc["cbore_depth"], xf + 0.1))
    if rc.get("ball_d"):                                                                                      # detent ball pockets (press-in steel ball)
        for k, sg in enumerate((1, -1)):
            tools.append(s.cyl(f"t_rball{k}_{tag}", "X", (0, yc + rc["ball_y"], zc + sg * rc["ball_off"]), rc["ball_d"] - 0.05,
                               xs - (rc["ball_d"] - rc["ball_protrude"]), xf + 0.1))
    s.box(f"t_rs_{tag}", (xs - G["rec_d"], xf + 0.1), (yc, W + 1), (-1, H + 1))                                  # recess outside r_rec (raised far half)
    s.cut(f"t_rs_{tag}", [s.cyl(f"t_rsc_{tag}", "X", (0, yc, zc), 2 * G["r_rec"], xs - G["rec_d"] - 1, xf + 1)])
    tools.append(f"t_rs_{tag}")
    for k, sg in enumerate((1, -1)):                                                                          # catch notch in the arc riser (both sides)
        zh = zc + sg * cp["hook_off"]
        tools.append(s.box(f"t_rk{k}_{tag}", (xs - G["rec_d"] - rc["catch_extra"], xf + 0.1), (G["y_hook"] - rc["catch_d"] - 0.6, G["y_hook"] + 0.5),
                           (zh - rc["catch_w"] / 2, zh + rc["catch_w"] / 2)))
    return tools


def step_box(p: dict, L: dict, clr: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """(y, z) ranges of the adapter's key step (raised underside of its tubing half, manual p.29 side view) grown by clr."""
    ad = p["cart"]["adapter"]
    y0, y1 = L["adapter_y"]
    return ((L["y_c"] + ad["step_from_conn"] - clr, y1 - ad["step_rim"] + clr), (ad["step_rim"] - clr, L["height"] - ad["step_rim"] + clr))


def bed_tool(s: Script, p: dict, L: dict, tag: str) -> str:
    """Variant A: pocket in the front face for the adapter's key step (+clr): it locates the adapter in the locked position (flush with the housing)."""
    ad = p["cart"]["adapter"]
    yr, zr = step_box(p, L, ad["bed_clr"])
    return s.box(f"t_bed_{tag}", (L["x_seat"] - ad["step_h"] - ad["bed_clr"], L["x_seat"] + 0.1), yr, zr)


def build_housing(s: Script, p: dict, L: dict) -> None:
    c = p["cart"]
    w, Lp, W, H = L["wall"], L["length"], L["width"], L["height"]
    yc, zc, ym = L["y_c"], L["zc"], L["y_m"]
    sh, rc, rb, sl, ca = c["shell"], c["receiver"], c["ribs"], c["slider"], c["cartridge"]
    r_o = sh["corner_r"]
    split = H - sh.get("lid_h", w) - sh["gasket_t"]                     # tub up to here; lid (flat plate, or a cap lid_h deep) on a 0.5 gasket above
    Lt = L.get("length_total", Lp) if L.get("adapter_y") else Lp          # A: the housing and the adapter share one outer block (flush outline)
    outline_prism(s, p, L, "bottom", 0.0, (0, split))
    if L.get("_section"):                                     # A: the end-face section runs the whole length (seamless with the front module)
        clip_to_section(s, L, "bottom", 0.0, "b")
    else:
        s.fillet_chain("bottom", (Lt / 2, 0.0, 0.0), sh["top_fillet"])
    if Lt > Lp:
        s.cut("bottom", [s.box("t_cut_ad_b", (Lp, Lt + 1), (-1, W + 1), (-1, H + 1))])
    outline_prism(s, p, L, "t_cav", w, (w, split + 0.1))
    clip_to_section(s, L, "t_cav", w, "cav")
    s.add("solid.combine", target="t_cav", tools=[s.box("t_cav_x", (-1, Lp - w), (-1, W + 1), (-1, H + 1))], operation="intersect", name="cavity front")
    s.cut("bottom", ["t_cav"])
    joins, cuts = [], []
    # receiver collar (lane 1 only) in front of the board east edge
    c0, c1 = L["collar"]
    joins.append(s.box("t_collar", (c0, Lp - w + 0.01), (w - 0.01, L["collar_y1"]), (w - 0.01, split)))
    if L["bed"] > 0:                                          # thicker front wall behind the adapter bed
        joins.append(s.box("t_fplate", (Lp - w - L["bed"] - 0.01, Lp - w + 0.01), (w - 0.01, W - w + 0.01), (w - 0.01, split)))
    # cartridge cradles, slider U channel, rear + front gear ribs with U slots (drop-in drive), motor saddles
    for k, xs in enumerate(c["cradle_x"]):
        x0 = L["cart"][0] + xs
        y_hi = yc + ca["od"] / 2 + 0.6
        if L.get("yoke") and L["gear"][0] - 0.3 < x0 + c["cradle_t"] and x0 < L["rib_f"][1] + 0.3:
            y_hi = min(y_hi, L["y_s"] - L["gear_od"] / 2 - 0.3)                  # cradle beside the screw gear
        bt = L.get("battery")
        if bt and x0 < bt["x"][1] and x0 + c["cradle_t"] > bt["x"][0]:
            y_hi = min(y_hi, bt["y"][0] - 0.3)                                    # cradle beside the crosswise cell (A, 49 wide since 2026-11-26)
        joins.append(s.box(f"t_cr{k}", (x0, x0 + c["cradle_t"]), (w - 0.01, y_hi), (w - 0.01, zc)))
        cuts.append(s.cyl(f"t_cr_b{k}", "X", (0, yc, zc), ca["od"] + 2 * c["cradle_clr"], x0 - 0.1, x0 + c["cradle_t"] + 0.1))
    ch_w = sl["w"] + 2 * sl["clr"]
    if L.get("yoke"):
        j2, c2 = _housing_yoke(s, p, L, split)
        joins += j2
        cuts += c2
    if not L.get("yoke"):                                     # rod drive on the cartridge axis: slider channel + ribs
        joins.append(s.box("t_ch", (w - 0.01, L["rib_r"][0] + 0.01), (yc - ch_w / 2 - sl["rail_t"], yc + ch_w / 2 + sl["rail_t"]), (w - 0.01, zc + sl["h"] / 2 - sl["rail_drop"])))
        cuts.append(s.box("t_ch_in", (w + c["rear_clr"] - 0.1, L["rib_r"][1] + 0.1), (yc - ch_w / 2, yc + ch_w / 2), (zc - sl["h"] / 2 - sl["clr"], zc + 4.0)))
        gr = L["gear_od"] / 2
        for nm, (x0, x1) in (("t_rib_r", L["rib_r"]), ("t_rib_f", L["rib_f"])):
            joins.append(s.box(nm, (x0, x1), (w - 0.01, min(yc + gr - 0.3, ym - p["drive_nfp"]["motor_d"] / 2 - 0.2)), (w - 0.01, split)))   # stops short of the motor boss
            sw = ch_w if nm == "t_rib_r" else rb["slot_w"]                       # rear rib: square slider passage, front rib: rod slot
            z0 = zc - sl["h"] / 2 - sl["clr"] if nm == "t_rib_r" else zc
            cuts.append(s.box(f"{nm}_slot", (x0 - 0.1, x1 + 0.1), (yc - sw / 2, yc + sw / 2), (z0, split + 0.1)))
            if nm == "t_rib_f":
                cuts.append(s.cyl(f"{nm}_hole", "X", (0, yc, zc), rb["slot_w"], x0 - 0.1, x1 + 0.1))
    for k, x0 in enumerate((L["motor"][0] + 1.0, L["gearhead"][0] + 2.0)):
        joins.append(s.box(f"t_ms{k}", (x0, x0 + c["motor_saddle_t"]), (ym - 3.6, ym + 3.6), (w - 0.01, zc)))
        cuts.append(s.cyl(f"t_ms_b{k}", "X", (0, ym, zc), p["drive_nfp"]["motor_d"] + 0.1, x0 - 0.1, x0 + c["motor_saddle_t"] + 0.1))
    pz0 = L["board"]["pcb_z"][0]
    bx, by = L["board"]["x"], L["board"]["y"]
    for k, (x, y, _d) in enumerate(board_ledges(p, L)):
        joins.append(s.cyl(f"t_led{k}", "Z", (x, y, 0), c["board_ledge_d"], w - 0.01, pz0))
    bt_ = L["battery"]                                                    # cell: frame walls on the floor (+ double-sided tape under the cell)
    if bt_.get("pocket"):
        cuts.append(s.box("t_cell_pocket", (bt_["x"][0] - 0.15, bt_["x"][1] + 0.15), (bt_["y"][0] - 0.15, bt_["y"][1] + 0.15), (bt_["z"][0], w + 0.3)))
    fc, ft = 0.15, 0.8
    xa, xb_ = bt_["x"][0] - fc, bt_["x"][1] + fc
    ya, yb = bt_["y"][0] - fc, bt_["y"][1] + fc
    zt_low, zt = w + 1.5, bt_["z"][1] - 0.4
    for nm, xr, yr, zt_ in (("t_cf_x0", (xa - ft, xa), (ya + 4.0, yb - 4.0), zt), ("t_cf_x1", (xb_, xb_ + ft), (ya + 4.0, yb - 4.0), zt),
                            ("t_cf_y0", (xa + 2.0, xb_ - 2.0), (ya - ft, ya), zt_low), ("t_cf_y1", (xa + 2.0, xb_ - 2.0), (yb, yb + ft), zt)):
        joins.append(s.box(nm, xr, yr, (w - 0.01, zt_)))
    s.join("bottom", joins)
    cuts += _receiver_cuts(s, p, L, "b")
    u = L["usb"]
    cuts.append(s.box("t_usb_open", (u["x_c"] - c["usb"]["open_w"] / 2, u["x_c"] + c["usb"]["open_w"] / 2), (W - w - 0.1, W + 0.1),
                      (u["z_c"] - c["usb"]["open_h"] / 2, u["z_c"] + c["usb"]["open_h"] / 2)))
    cuts += _screw_cuts_bottom(s, p, L) + _button_cuts(s, p, L, "b")
    s.cut("bottom", cuts)
    # flat lid with hold-down ribs (rod slots, board corner), the receiver bore continues through it where the bore reaches above the split
    lt = split + sh["gasket_t"]
    outline_prism(s, p, L, "top", 0.0, (lt, H))
    if L.get("_section"):
        clip_to_section(s, L, "top", 0.0, "t")
    else:
        s.fillet_chain("top", (Lt / 2, 0.0, H), sh["top_fillet"])
    if Lt > Lp:
        s.cut("top", [s.box("t_cut_ad_t", (Lp, Lt + 1), (-1, W + 1), (-1, H + 1))])
    tj = []
    if sh.get("lid_h"):                                      # cap lid: hollow it, keep collar + front plate material above the parting line
        outline_prism(s, p, L, "t_cavl", w, (lt - 0.1, H - w))
        clip_to_section(s, L, "t_cavl", w, "cavl")
        s.add("solid.combine", target="t_cavl", tools=[s.box("t_cavl_x", (-1, Lp - w), (-1, W + 1), (-1, H + 1))], operation="intersect", name="lid cavity front")
        s.cut("top", ["t_cavl"])
        tj.append(s.box("t_collar_l", (L["collar"][0], Lp - w + 0.01), (w - 0.01, L["collar_y1"]), (lt - 0.01, H - w + 0.01)))
        if L["bed"] > 0:
            tj.append(s.box("t_fplate_l", (Lp - w - L["bed"] - 0.01, Lp - w + 0.01), (w - 0.01, W - w + 0.01), (lt - 0.01, H - w + 0.01)))
    t_top = (H - w + 0.01) if sh.get("lid_h") else lt + 0.01             # lid tabs reach the lid roof (a cap lid is hollow down to lt)
    ch_w = sl["w"] + 2 * sl["clr"]
    for nm, (x0, x1) in (("t_lr_r", L["rib_r"]), ("t_lr_f", L["rib_f"])):
        if L.get("yoke"):                                     # caps over the screw slots
            sw, zb, ya = rb["slot_w"], zc + c["rod"]["d"] / 2 + 0.1, L["y_s"]
        else:
            sw, zb, ya = ((ch_w, zc + sl["h"] / 2 + sl["clr"]) if nm == "t_lr_r" else (rb["slot_w"], zc + c["rod"]["d"] / 2 + 0.1)) + (yc,)
        tj.append(s.box(nm, (x0, x1), (ya - sw / 2 + 0.01, ya + sw / 2 - 0.01), (zb, t_top)))
    rx, ry = board_lid_rib(L)
    tj.append(s.box("t_lr_bd", rx, ry, (L["board"]["pcb_z"][1], t_top)))
    # shake-proof (owner 2026-11-26): the lid holds every loose part down; with the bottom cradles / saddles / ledges nothing can move
    hd = c.get("hold_down_gap", 0.15)
    for k, xs in enumerate(c["cradle_x"]):                                # cartridge: a lid rib over each cradle
        x0 = L["cart"][0] + xs
        if zc + ca["od"] / 2 + hd < lt - 0.05:
            tj.append(s.box(f"t_lhd_c{k}", (x0, x0 + c["cradle_t"]), (yc - 2.5, yc + 2.5), (zc + ca["od"] / 2 + hd, t_top)))
    md = p["drive_nfp"]["motor_d"]
    for k, x0 in enumerate((L["motor"][0] + 1.0, L["gearhead"][0] + 2.0)):  # motor: a lid rib over each saddle
        tj.append(s.box(f"t_lhd_m{k}", (x0, x0 + c["motor_saddle_t"]), (ym - 2.0, ym + 2.0), (zc + md / 2 + hd, t_top)))
    for k, (x, y, _d) in enumerate(board_ledges(p, L)):                    # board: a lid pin over each floor post (part-free pads)
        tj.append(s.cyl(f"t_lhd_b{k}", "Z", (x, y, 0), c["board_ledge_d"], L["board"]["pcb_z"][1] + 0.02, t_top))
    tj += _screw_bosses_lid(s, p, L, t_top - 0.01)
    s.join("top", tj)
    s.cut("top", _receiver_cuts(s, p, L, "t") + _screw_pilots_lid(s, p, L, lt) + _button_cuts(s, p, L, "t"))
    outline_prism(s, p, L, "lid_gasket", 0.3, (split, lt))
    clip_to_section(s, L, "lid_gasket", 0.3, "lg")
    x_lg = Lp - 0.3 - (cup_geom(p, L)["rec_d"] if rc.get("type") == "cup_bayonet" else 0.0)     # A cup socket: gasket stops behind the face recess
    s.cut("lid_gasket", [outline_prism(s, p, L, "t_lg_in", w + 0.1, (split - 0.1, lt + 0.1)), s.box("t_lg_x", (x_lg, Lt + 1), (-1, W + 1), (-1, H + 1))])
    fm = c.get("front_module")
    if fm:                                                    # A since 2026-11-26: front `depth` mm = separate FACE4 part (print/A_lock/make_face.py)
        x_cut = Lp - fm["depth"]
        for b in ("bottom", "top", "lid_gasket"):
            s.cut(b, [s.box(f"t_fm_{b}", (x_cut, Lt + 1), (-1, W + 1), (-1, H + 1))])


def shell_len(L: dict) -> float:
    """Length of the outer block: incl. the flush adapter (A), else the housing alone."""
    return L["length_total"] if L.get("adapter_y") else L["length"]


def outline_segments(p: dict, L: dict, d: float) -> list[tuple]:
    """Closed plan outline (CCW) of the tapered shell offset inward by d, as exact lines and arcs (cheap B-rep, no spline):
    straight -Y side, front end with corner radius corner_r, +Y side = full width W from taper.x_full to the front,
    an S of two tangent arcs of equal radius down to taper.w_rear at taper.x_rear, straight to the rear, rear corners taper.r_rear.
    Items: ("line", p0, p1) or ("arc", centre, start, end, clockwise)."""
    sh = p["cart"]["shell"]
    tp = sh["taper"]
    W, Lt = L["width"], shell_len(L)
    rf, rr, wr = sh["corner_r"], tp["r_rear"], tp["w_rear"]
    xa, xb = tp["x_rear"], tp["x_full"]
    th = 2 * math.atan((W - wr) / (xb - xa))                                     # tan(th/2) = dy/dx for two equal tangent arcs
    R = (xb - xa) / (2 * math.sin(th))

    def pol(c: tuple[float, float], r: float, deg: float) -> tuple[float, float]:
        return (round(c[0] + r * math.cos(math.radians(deg)), 5), round(c[1] + r * math.sin(math.radians(deg)), 5))
    c_rl, c_fl, c_fr, c_rr = (rr, rr), (Lt - rf, rf), (Lt - rf, W - rf), (rr, wr - rr)
    c2, c1 = (xb, W - R), (xa, wr + R)                                           # convex arc at the front of the S, concave arc at its rear
    ad = math.degrees(th)
    s_mid = pol(c2, R - d, 90 + ad)
    return [
        ("arc", c_rl, pol(c_rl, rr - d, 180), pol(c_rl, rr - d, 270), False),
        ("line", pol(c_rl, rr - d, 270), pol(c_fl, rf - d, 270)),
        ("arc", c_fl, pol(c_fl, rf - d, 270), pol(c_fl, rf - d, 360), False),
        ("line", pol(c_fl, rf - d, 360), pol(c_fr, rf - d, 0)),
        ("arc", c_fr, pol(c_fr, rf - d, 0), pol(c_fr, rf - d, 90), False),
        ("line", pol(c_fr, rf - d, 90), pol(c2, R - d, 90)),
        ("arc", c2, pol(c2, R - d, 90), s_mid, False),
        ("arc", c1, s_mid, pol(c1, R + d, -90), True),
        ("line", pol(c1, R + d, -90), pol(c_rr, rr - d, 90)),
        ("arc", c_rr, pol(c_rr, rr - d, 90), pol(c_rr, rr - d, 180), False),
        ("line", pol(c_rr, rr - d, 180), pol(c_rl, rr - d, 180)),
    ]


def outline_points(p: dict, L: dict, d: float, step: float = 1.0) -> list[tuple[float, float]]:
    """The same outline sampled as points (figures, checks)."""
    out = []
    for sg in outline_segments(p, L, d):
        if sg[0] == "line":
            (x0, y0), (x1, y1) = sg[1], sg[2]
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
            out += [(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) for k in range(n)]
        else:
            c, s0, s1, cw = sg[1:]
            r = math.hypot(s0[0] - c[0], s0[1] - c[1])
            a0, a1 = math.atan2(s0[1] - c[1], s0[0] - c[0]), math.atan2(s1[1] - c[1], s1[0] - c[0])
            sw = a1 - a0
            sw = (sw - 2 * math.pi if sw > 0 else sw) if cw else (sw + 2 * math.pi if sw < 0 else sw)
            n = max(2, int(abs(sw) * r / step))
            out += [(c[0] + r * math.cos(a0 + sw * k / n), c[1] + r * math.sin(a0 + sw * k / n)) for k in range(n)]
    return [(round(x, 4), round(y, 4)) for x, y in out]


def outline_prism(s: Script, p: dict, L: dict, name: str, d: float, z: tuple[float, float]) -> str:
    """Tapered A shell: exact line / arc outline extruded from z0 to z1; falls back to a rounded rectangle when there is no taper."""
    if not p["cart"]["shell"].get("taper"):
        r = p["cart"]["shell"]["corner_r"]
        return s.rrect(name, (d, shell_len(L) - d), (d, L["width"] - d), r - d, z)
    s.add("sketch.create", plane="XY", offset=z[0])
    for sg in outline_segments(p, L, d):
        if sg[0] == "line":
            s.add("sketch.line", points=[list(sg[1]), list(sg[2])])
        else:
            c, s0, s1, cw = sg[1:]
            s.add("sketch.arc.center_point", center=list(c), start=list(s0), end=list(s1), clockwise=cw)
    s.add("sketch.finish")
    s.add("solid.extrude", distance=z[1] - z[0], body_name=name, name=name)
    return name


def screw_points(p: dict, L: dict) -> list[tuple[float, float]]:
    """Lid screws from the UNDERSIDE (clean top): two rear corners and the front +Y corner (the lane-1 front corner is the receiver collar)."""
    sc = p["cart"]["screws"]
    d = sc["inset"]
    tp = p["cart"]["shell"].get("taper")
    if tp:                                                    # tapered shell: rear-left corner, rear-right (narrow) corner, front +Y corner
        x_f = L["length"] - max(d, L["wall"] + L["bed"] + sc["boss_d"] / 2 + 0.15)
        y_f = L["width"] - d
        fm = p["cart"].get("front_module")
        if fm:                                                # A: in front of the board, inside the rounded far edge (section R5)
            x_f = L["board"]["x"][1] + 0.3 + sc["boss_d"] / 2
            y_f = L["width"] - d - 3.2                        # boss clear of where the floor curves up into the R5 edge
            rl = (tp["screw_rl"][0], tp["screw_rl"][1] + 1.0)  # rear-left boss clear of the small near-end edge round
            return [rl, (tp["screw_rr_x"], tp["w_rear"] - tp["screw_rr_in"]), (x_f, y_f)]
        return [tuple(tp["screw_rl"]), (tp["screw_rr_x"], tp["w_rear"] - tp["screw_rr_in"]), (x_f, y_f)]
    y_s = L["wall"] + sc["boss_d"] / 2 + 0.05                   # -Y screw: between the side wall and the slider-channel rail, in the tail zone
    x_f = L["length"] - max(d, L["wall"] + L["bed"] + sc["boss_d"] / 2 + 0.15)    # front boss clears the (thicker) front wall
    return [(d, L["width"] - d), (x_f, L["width"] - d), (sc["x_side"], y_s)]


def _screw_bosses_lid(s: Script, p: dict, L: dict, lt: float) -> list[str]:
    sc, w = p["cart"]["screws"], L["wall"]
    return [s.cyl(f"t_lboss{k}", "Z", (x, y, 0), sc["boss_d"], w + sc["boss_gap"], lt + 0.01) for k, (x, y) in enumerate(screw_points(p, L))]


def _screw_pilots_lid(s: Script, p: dict, L: dict, lt: float) -> list[str]:
    sc, w = p["cart"]["screws"], L["wall"]
    return [s.cyl(f"t_lpil{k}", "Z", (x, y, 0), sc["pilot_d"], w + sc["boss_gap"] - 0.1, w + sc["boss_gap"] + sc["pilot_depth"]) for k, (x, y) in enumerate(screw_points(p, L))]


def _screw_cuts_bottom(s: Script, p: dict, L: dict) -> list[str]:
    """Clearance hole through the floor + counterbore from the underside so the head sits flush (hidden under the pump)."""
    sc, w = p["cart"]["screws"], L["wall"]
    out = []
    for k, (x, y) in enumerate(screw_points(p, L)):
        out.append(s.cyl(f"t_sh{k}", "Z", (x, y, 0), sc["clear_d"], -0.1, w + 0.1))
        out.append(s.cyl(f"t_scb{k}", "Z", (x, y, 0), sc["head_d"] + 0.3, -0.1, sc["head_h"]))
    return out


def button_geom(p: dict, L: dict) -> dict:
    bt = p["cart"]["button"]
    return {"x": L["button_x"], "z": L["button_z"], "y_out": L["width"], "y_in": L["width"] - L["wall"]}


def _button_cuts(s: Script, p: dict, L: dict, tag: str) -> list[str]:
    """Sealed button in the +Y wall in front of the board's side switch: through hole for the stem, outside counterbore for the (silicone or TPU) cap."""
    bt, B = p["cart"]["button"], button_geom(p, L)
    return [s.cyl(f"t_bh_{tag}", "Y", (B["x"], 0, B["z"]), bt["hole_d"], B["y_in"] - 0.1, B["y_out"] + 0.1),
            s.cyl(f"t_bc_{tag}", "Y", (B["x"], 0, B["z"]), bt["cap_d"] + bt["clr"], B["y_out"] - bt["recess"], B["y_out"] + 0.1)]


def build_button(s: Script, p: dict, L: dict) -> None:
    """Button cap: flush head in the outside recess, stem through the wall, barb ring behind the wall (snaps in, seals by the head flange)."""
    bt, B = p["cart"]["button"], button_geom(p, L)
    x, z = B["x"], B["z"]
    s.cyl("button", "Y", (x, 0, z), bt["cap_d"], B["y_out"] - bt["recess"], B["y_out"] + bt["dome"])
    stem = s.cyl("t_btn_stem", "Y", (x, 0, z), bt["hole_d"] - 0.1, B["y_in"] - bt["stem_in"], B["y_out"] - bt["recess"] + 0.01)
    barb = s.cyl("t_btn_barb", "Y", (x, 0, z), bt["barb_d"], B["y_in"] - bt["barb_t"] - 0.05, B["y_in"] - 0.05)
    s.join("button", [stem, barb])


def _housing_yoke(s: Script, p: dict, L: dict, split: float) -> tuple[list[str], list[str]]:
    """Yoke drive: gear ribs on the screw axis (U slots, drop-in screw), screw pocket in the rear wall, floor channel for the yoke foot."""
    c = p["cart"]
    w, yc, zc, ys, ym = L["wall"], L["y_c"], L["zc"], L["y_s"], L["y_m"]
    rb, yk, ca = c["ribs"], c["yoke"], c["cartridge"]
    joins, cuts = [], []
    y_lo = yc + ca["od"] / 2 + c["cradle_clr"] + 0.2
    y_hi = ym - p["drive_nfp"]["motor_d"] / 2 - 0.2
    for nm, (x0, x1) in (("t_yrib_r", L["rib_r"]), ("t_yrib_f", L["rib_f"])):
        joins.append(s.box(nm, (x0, x1), (y_lo, y_hi), (w - 0.01, split)))
        cuts.append(s.box(f"{nm}_slot", (x0 - 0.1, x1 + 0.1), (ys - rb["slot_w"] / 2, ys + rb["slot_w"] / 2), (zc, split + 0.1)))
        cuts.append(s.cyl(f"{nm}_hole", "X", (0, ys, zc), rb["slot_w"], x0 - 0.1, x1 + 0.1))
    cuts.append(s.cyl("t_screw_pocket", "X", (0, ys, zc), c["rod"]["d"] + 0.2, w - yk["screw_in_wall"] - 0.05, w + 0.1))
    joins.append(s.cyl("t_screw_boss", "X", (0, ys, zc), 4.0, w - 0.01, w + yk["rear_clr"] - 0.2))                  # bearing boss on the rear wall
    cuts.append(s.cyl("t_screw_boss_hole", "X", (0, ys, zc), c["rod"]["d"] + 0.2, w - 0.2, w + yk["rear_clr"]))
    yf = (yc + ys) / 2
    fw = yk["foot_w"] / 2 + yk["foot_clr"]
    x0, x1 = w - 0.01, L["rib_r"][0] - 0.05
    for k, sgn in enumerate((-1, 1)):
        y_in = yf + sgn * fw
        joins.append(s.box(f"t_frail{k}", (x0, x1), tuple(sorted((y_in, y_in + sgn * yk["rail_t"]))), (w - 0.01, w + yk["rail_h"])))
    return joins, cuts


def _front_module_files(p: dict, L: dict) -> Path:
    """A: (re)generate the FACE4 front module, the adapter dummy, the needle and the end-face section in pump coordinates."""
    import subprocess
    here = Path(__file__).resolve().parent
    out = here / "out" / "v010-cart" / "A" / "print"
    py = here.parent / ".venv" / "bin" / "python"
    subprocess.run([str(py), "make_face.py", "--module", str(out), "--at", f"{L['length']},{L['y_c']},{L['zc']}"],
                   cwd=here / "print" / "A_lock", check=True, capture_output=True)
    return out


def section_points(L: dict, d: float = 0.0) -> list[tuple[float, float]]:
    """End-face section (y, z) shared by the housing and the front module (seamless), offset inward by d along the vertex normals."""
    pts = L["_section"]
    if d == 0:
        return [tuple(q) for q in pts]
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1.0 if area > 0 else -1.0                                   # CCW: inward normal = left of the direction of travel
    out = []
    for i in range(n):
        (y0, z0), (y1, z1), (y2, z2) = pts[i - 1], pts[i], pts[(i + 1) % n]
        ty, tz = y2 - y0, z2 - z0
        ln = math.hypot(ty, tz) or 1.0
        out.append((y1 - sgn * tz / ln * d, z1 + sgn * ty / ln * d))
    return out


def clip_to_section(s: Script, L: dict, body: str, d: float, tag: str) -> None:
    """Intersect a body with the end-face section prism (inset d) over the whole length."""
    if not L.get("_section"):
        return
    t = s.prism_yz(f"t_sec_{tag}", section_points(L, d), -1.0, L.get("length_total", L["length"]) + 1.0)
    s.add("solid.combine", target=body, tools=[t], operation="intersect", name=f"section {tag}")


def build(p: dict) -> tuple[Script, dict]:
    L = geometry(p)
    if p["cart"].get("front_module"):
        import json as _json
        L["_section"] = _json.loads((_front_module_files(p, L) / "cart_A_section.json").read_text())
    s = Script()
    build_housing(s, p, L)
    build_cartridge(s, p, L)
    build_drive(s, p, L)
    build_electronics(s, p, L)
    build_button(s, p, L)
    build_front_module(s, p, L)
    return s, L


def build_front_module(s: Script, p: dict, L: dict) -> None:
    """A: the tested FACE4 lock face (print/A_lock/make_face.py --module), placed on the housing front as a real body."""
    fm = p["cart"].get("front_module")
    if not fm:
        return
    here = Path(__file__).resolve().parent
    out = here / "out" / "v010-cart" / "A" / "print"
    for f, nm in (("cart_A_front_module_placed.step", "front_module"), ("cart_A_adapter_dummy_placed.step", "adapter"),
                  ("cart_A_needle_placed.step", "needle")):
        s.add("file.insert_step", path=os.path.relpath(out / f, here))
        s.add("body.rename", body="COMPOUND", name=nm)
