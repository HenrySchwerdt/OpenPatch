# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Checks of the v0.1.0 zero-tail (stack) layout: board over the tunnel, cell strip, radio/piezo on the lid side, motor shelf contacts, USB-C. TEST PROJECT."""
from __future__ import annotations

import check as C

TOP_PARTS = ["radio", "piezo", "switch", "hall_drv0", "hall_drv1"]
TARGETS = {"OP-100": 45.0, "OP-200": 52.0}


def check_stack(p: dict, L: dict, by: dict) -> tuple[list, list]:
    problems, warns = [], []
    G, S = L["v010"], p["v010"]["stack"]
    need = ("pod_board", "radio", "battery", "bat_foam", "bat_pad_p", "bat_pad_n", "spring_p", "spring_n", "mspring_1", "mspring_2", "mspring_3", "mspring_4", "motor_fpc", "piezo", "switch",
            "usb_conn", "usb_board", "usb_gasket", "usb_link_1", "usb_link_2", "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock", "dock_magnet", "dock_insert", "cannula_adapter", "end_cap", "motor", "gearhead")
    for n in need:
        if n not in by:
            problems.append(f"v010 body missing: {n}")
    for gone in ("ffc_conn", "ffc_cable", "qi_coil", "rf_module", "pcb", "e73", "pico_conn", "chg_pad_1", "charge_gasket"):
        if gone in by:
            problems.append(f"body from an older layout/the dropped charge pads present: {gone}")
    if problems:
        return problems, warns
    bb = {k: x["bbox"] for k, x in by.items()}
    z0, ztop, zi, xr = G["z0"], G["ztop"], G["zi"], L["x_r1"]
    b = bb["pod_board"]
    if b["min"][0] < L["xi0"] + 0.3 or b["max"][0] > L["x_end"] - 0.3 or b["min"][1] < L["yi0"] + 0.3 or b["max"][1] > L["yi1"] - 0.3:
        problems.append(f"pod_board bbox x {b['min'][0]:.2f}..{b['max'][0]:.2f} y {b['min'][1]:.2f}..{b['max'][1]:.2f} closer than 0.3 mm to the housing walls")
    # ---- no tall bottom-side part over the tunnel ----------------------------------------------------------------------
    yc = L["dock"]["y_c"]
    for n in ("battery", "bat_foam", "spring_p", "spring_n", "usb_conn", "usb_board", "usb_gasket", "motor_fpc", "mspring_1"):
        x = bb[n]
        if x["min"][2] < z0 - 0.01 and x["min"][0] < xr + G["plan"]["arms_end_u"] + 0.5 and x["min"][1] < G["plan"]["y_lo_arms"] - 1e-3 and x["max"][1] > yc - 6.2 and x["min"][0] > xr:
            problems.append(f"{n} (y_min {x['min'][1]:.2f}) under the board in the dock tunnel / snap-arm zone (limit {G['plan']['y_lo_arms']:.2f})")
    # dome path: nothing below the board with y in the tunnel band beyond the insert
    for n in ("usb_conn", "usb_board", "usb_gasket", "battery", "radio"):
        x = bb[n]
        if n != "radio" and x["min"][1] < yc + 5.5 and x["max"][1] > yc - 5.5 and x["max"][0] > xr + G["plan"]["arms_end_u"] and x["min"][2] < 5.0:
            problems.append(f"{n} intrudes into the dome path y {yc - 5.5:.1f}..{yc + 5.5:.1f}")
    # ---- cell stack ---------------------------------------------------------------------------------------------------------------
    bt = bb["battery"]
    gap = z0 - (bt["max"][2] + 0.05)
    fr = S["cell"]["spring_free_max"]
    if not (0.2 <= gap <= fr - 0.2):
        problems.append(f"cell spring contact gap {gap:.2f} mm outside 0.2..{fr - 0.2:.1f}")
    warns.append(f"cell {S['cell']['class']} class {S['cell']['l']} x {S['cell']['w']} x {S['cell']['t']} mm (+0.6 foam): top z {bt['max'][2]:.2f}, spring gap {gap:.2f} mm, compression {fr - gap - 0.3:.2f}..{fr - gap:.2f} mm over the thickness range")
    # ---- motor contacts --------------------------------------------------------------------------------------------------------------
    mg = z0 - G["motor_pads"][0]["z_top"]
    if not (0.2 <= mg <= fr - 0.2):
        problems.append(f"motor spring contact gap {mg:.2f} mm outside 0.2..{fr - 0.2:.1f}")
    if bb["pod_board"]["min"][0] < bb["motor"]["max"][0] + 0.1:
        problems.append("board tongue reaches over the motor end")
    warns.append(f"motor contacts: FPC tail on the shelf (pads z {G['motor_pads'][0]['z_top']:.2f}), 4 SMD springs, compression {fr - mg:.2f} mm; custom NFP FPC tail (spec 1c) or a 4-trace flex jumper clamped on the pins: OPEN")
    # ---- top side -------------------------------------------------------------------------------------------------------------------------
    for n in TOP_PARTS:
        if bb[n]["max"][2] > zi - 0.05:
            problems.append(f"{n} top z {bb[n]['max'][2]:.2f} touches the lid inner z {zi:.2f}")
    if S["radio"]["h"] > 1.3:
        problems.append("radio taller than 1.3 mm")
    warns.append(f"lid side: radio {bb['radio']['max'][2] - ztop:.2f} mm, piezo {bb['piezo']['max'][2] - ztop:.2f}, tact {bb['switch']['max'][2] - ztop:.2f}; free under the lid {zi - ztop:.2f} mm (board 0.8 + parts <= 1.3 over the tunnel)")
    # ---- USB-C --------------------------------------------------------------------------------------------------------------------------------
    u = G["usb"]
    uc, ug, ub = bb["usb_conn"], bb["usb_gasket"], bb["usb_board"]
    if u["web_above_mm"] < C.MIN_FEATURE - 1e-9:
        problems.append(f"web above the USB-C opening {u['web_above_mm']:.2f} mm < {C.MIN_FEATURE} (lap step at z 5.0)")
    if u["open_z"][0] - L["wall"] < -1e-9:
        problems.append("USB opening below the floor top")
    nose_in_open = (uc["max"][1] - uc["min"][1]) <= (u["open_y"][1] - u["open_y"][0]) - 0.1 and (uc["max"][2] - uc["min"][2]) <= (u["open_z"][1] - u["open_z"][0]) - 0.05
    if not nose_in_open:
        problems.append("USB-C nose does not fit the wall opening with clearance")
    if abs(ug["min"][0] - uc["max"][0]) > 0.6 and ug["max"][0] > L["x_end"] + 1e-3:
        problems.append("USB gasket not between receptacle flange and end wall")
    if uc["max"][0] < L["length"] - 0.3:
        problems.append("USB-C nose does not reach the end-wall outer face")
    if uc["max"][2] > z0 - 0.4:
        problems.append(f"USB-C top z {uc['max'][2]:.2f} closer than 0.4 mm to the main board bottom {z0}")
    for k in (1, 2):
        lk = bb[f"usb_link_{k}"]
        if abs(lk["min"][2] - ub["max"][2]) > 0.02 or abs(lk["max"][2] - z0) > 0.02:
            problems.append(f"usb_link_{k} does not span USB board -> main board")
    warns.append(f"USB-C {S['usb']['w']} x {S['usb']['d']} x {S['usb']['h']} mm mid-mount at z {u['z'][0]:.2f}..{u['z'][1]:.2f}, opening {S['usb']['open_w']} x {S['usb']['open_h']} mm in the +X wall, web above {u['web_above_mm']:.2f} mm, "
                 f"gasket {S['usb']['gasket_t']} mm; USB board z {u['board']['z'][0]:.2f}..{u['board']['z'][1]:.2f} linked to the main board by {S['usb']['link_h']} mm elastomer/pogo links (VERIFY)")
    # ---- dock / hall (unchanged vs the bench pod) ---------------------------------------------------------------------------------------------
    dm, dh = bb["dock_magnet"], bb["hall_dock"]
    dgap = dh["min"][2] - dm["max"][2]
    if not (0.4 <= dgap <= 1.5):
        problems.append(f"dock hall air gap {dgap:.2f} mm outside 0.4..1.5")
    mag = bb["magnet"]
    for n in ("hall_tmag", "hall_drv0", "hall_drv1"):
        if bb[n]["min"][0] - mag["max"][0] < 0.4:
            problems.append(f"{n} closer than 0.4 mm to the spindle magnet")
    pr_i, wr_i = C.check_insert(p, L, by)
    problems += pr_i
    warns += wr_i
    # ---- size targets (spec 2b): reported, never silent -----------------------------------------------------------------------------------
    import op_v010s
    pj = op_v010s.project(p, L)
    tgt = TARGETS.get(L["variant"])
    if tgt:
        miss = L["length"] - tgt
        warns.append(f"TARGET spec 2b: {L['variant']} <= {tgt:.0f} mm: current drive {L['length']:.2f} mm ({'MET' if miss <= 0 else f'NOT MET, gap {miss:.2f} mm'}); "
                     f"projected coaxial drive (stroke {pj['stroke_proj']}, rear stack {S['projection']['rear_stack']}): {pj['length_proj']:.2f} mm ({'MET' if pj['length_proj'] <= tgt else 'NOT MET, gap %.2f mm' % (pj['length_proj'] - tgt)})")
    return problems, warns
