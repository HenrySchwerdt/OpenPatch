# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Assembly features of the cup-pod housing (drop-in seats, closure, gaskets).  Adds housing geometry only; no component or keep-out box is moved."""
from __future__ import annotations

from op_cmds import Script

# assembly order (each group drops in from above unless noted); used by cup_check (drop test), ASSEMBLY-CUP.md and the exploded render
ORDER = [
    ("1 housing", ["bottom"]),
    ("2 tank + plunger + rod cartridge", ["reservoir", "plunger_core", "seal_a", "seal_b", "nut", "rod", "thrust_sleeve", "gear_b", "bush_rod", "thrust_collar", "magnet", "septum"]),
    ("3 motor + gear A", ["motor", "gearhead", "motor_boss", "motor_rear_boss", "motor_shaft", "gear_a", "motor_term"]),
    ("4 battery (301030)", ["ko_battery"]),
    ("5 board + USB-C + piezo/button (PCBA)", ["ko_board", "ko_usb", "ko_aux", "ko_io", "ko_side_a", "ko_side_b", "ko_tmag_board", "hall_tmag", "ko_dock_board", "hall_dock"]),
    ("6 gaskets + lid + 3 screws", ["lid_gasket", "usb_gasket", "top"]),
    ("7 dock parts from BELOW through the pocket window", ["hub_oring", "needle_hub", "needle", "needle_guard", "dock_clip"]),
]
FROM_BELOW = {"hub_oring", "needle_hub", "needle", "needle_guard", "dock_clip", "cannula_adapter", "dock_magnet"}


def corner_posts(L: dict) -> list[tuple[float, float]]:
    w, Lp, W = L["wall"], L["length"], L["width"]
    return [(w + 1.5, w + 1.5), (Lp - w - 1.5, w + 1.5), (Lp - w - 1.5, W - w - 1.5)]


def build(s: Script, p: dict, L: dict) -> None:
    c, K = p["cup"], L["dock"]
    w, Lp, W, H, lap = L["wall"], L["length"], L["width"], L["height"], p["shell"]["lap_low"]
    zc, yr, xc = L["zc"], L["y_r"], L["xc"]
    dr = p["drive_nfp"]
    bu, usb, bat = c["bush"], c["usb"], c["battery"]
    posts = corner_posts(L)
    joins, cuts, tcuts = [], [], []
    # ---- (1) lid closure: 3 tall posts (thread-forming M1.2 into d1.0 pilots, 4 mm deep), lid roof rests on them, flat 0.5 mm gasket on the rim, lid clearance cut at the corner
    for k, (px, py) in enumerate(posts):
        joins.append(s.cyl(f"t_post{k}", "Z", (px, py, 0), 2.0, w - 0.1, H - w - 0.05))
        cuts.append(s.cyl(f"t_pilot{k}", "Z", (px, py, 0), 1.0, H - w - 4.0, H - w))
        tcuts += [s.cyl(f"t_tcl{k}", "Z", (px, py, 0), 2.4, lap + 0.3, H - w + 0.05), s.cyl(f"t_thole{k}", "Z", (px, py, 0), 1.4, H - w - 0.1, H + 0.1),
                  s.cyl(f"t_thead{k}", "Z", (px, py, 0), 2.4, H - 0.5, H + 0.1)]
    s.rrect("lid_gasket", (0.15, Lp - 0.15), (0.15, W - 0.15), p["shell"]["corner_r"] - 0.15, (lap, lap + 0.5))
    s.rrect("t_gk_in", (0.65, Lp - 0.65), (0.65, W - 0.65), p["shell"]["corner_r"] - 0.65, (lap - 0.1, lap + 0.6))
    s.cut("lid_gasket", ["t_gk_in"])
    # ---- (2) motor cradle: saddles exist (U, open top); lid posts hold the can; FPC groove from the pin pocket toward lane 2
    ys = [L["gearhead_y"][0] + 0.5, L["motor_y"][1] - 2.2]
    sl = c["motor"]["saddle_len"]
    for k, y0 in enumerate(ys):
        tcjoin = s.cyl(f"t_mpost{k}", "Z", (xc, y0 + sl / 2, 0), 1.6, H - w - 0.35, H - w + 0.05)
        joins_top = tcjoin
        s.join("top", [joins_top])
    yt = L["gearhead_y"][0] + dr["term_x"]
    cuts.append(s.box("t_fpc_groove", (xc, L["battery"]["x"][0] - 0.1), (yt - 1.1, yt + 1.1), (0.35, w + 0.01)))
    # ---- (3) tank seat: rear stop blocks (datum at the dry rim), front datum = dock pocket face; O-ring face groove around the needle-hub seat
    for k, (y0, y1) in enumerate(((7.4, 9.4), (yr + 5.0, yr + 7.0))):
        joins.append(s.box(f"t_stop{k}", (L["x_dry"] - 0.7, L["x_dry"] - 0.05), (y0, y1), (w - 0.1, 2.0)))
    zn = K["z_n"]
    s.tube("t_hog", "X", (0, yr, zn), 3.4, 2.4, L["x_t0"] - 0.3, L["x_t0"] + 0.01)
    s.cut("reservoir", ["t_hog"])
    s.tube("hub_oring", "X", (0, yr, zn), 3.2, 2.4, L["x_t0"] - 0.25, L["x_t0"] + 0.2)
    # ---- (4) bearing rib is a U cradle (slot open to the top); relief pockets for gear A / B already cut
    cuts.append(s.box("t_rib_slot", (L["bush"][0] - 0.05, L["bush"][1] + 0.05), (yr - (bu["od"] + bu["bore_clr"]) / 2, yr + (bu["od"] + bu["bore_clr"]) / 2), (zc, zc + 3.0)))
    # ---- (6) battery tray: 0.4 mm floor recess (swell / wire reserve, lateral retention)
    b = L["battery"]
    cuts.append(s.box("t_bat_tray", (b["x"][0] - 0.1, b["x"][1] + 0.1), (b["y"][0] + 0.2, b["y"][1] + 0.05), (w - 0.4, w + 0.01)))
    # ---- (7) board ledges (z up to 4.15, under the aux zone; the board outline itself is not touched)
    xb = b["x"][1]
    for k, y in enumerate((L["lane2_y"][0] + 1.5, L["lane2_y"][1] - 1.5)):
        joins.append(s.cyl(f"t_ledge{k}", "Z", (xb + 1.2, y, 0), 1.8, w - 0.1, 4.15))
    # ---- (8) USB-C seat: opening through bottom wall AND lid wall, gasket recess 0.4 deep in the wall inner face, silicone frame
    u = L["usb"]
    xu, zu = (u["x"][0] + u["x"][1]) / 2, (u["z"][0] + u["z"][1]) / 2
    cuts.append(s.box("t_usb_rec", (xu - usb["open_w"] / 2 - 0.9, xu + usb["open_w"] / 2 + 0.9), (W - w - 0.05, W - w + 0.4), (zu - usb["open_h"] / 2 - 0.9, min(lap, zu + usb["open_h"] / 2 + 0.9))))
    tcuts += [s.box("t_usb_open_t", (xu - usb["open_w"] / 2, xu + usb["open_w"] / 2), (W - w - 0.1, W + 0.1), (lap, zu + usb["open_h"] / 2)),
              s.box("t_usb_rec_t", (xu - usb["open_w"] / 2 - 0.9, xu + usb["open_w"] / 2 + 0.9), (W - w - 0.05, W - w + 0.4), (lap + 0.4, zu + usb["open_h"] / 2 + 0.9))]
    s.box("usb_gasket", (xu - usb["open_w"] / 2 - 0.8, xu + usb["open_w"] / 2 + 0.8), (W - w, W - w + 0.4), (max(zu - usb["open_h"] / 2 - 0.8, w + 0.1), min(lap, zu + usb["open_h"] / 2 + 0.8)))
    s.cut("usb_gasket", [s.box("t_ug_in", (xu - usb["open_w"] / 2, xu + usb["open_w"] / 2), (W - w - 0.1, W - w + 0.5), (zu - usb["open_h"] / 2, zu + usb["open_h"] / 2))])
    s.cut("lid_gasket", [s.box("t_lg_usb", (xu - usb["open_w"] / 2 - 0.9, xu + usb["open_w"] / 2 + 0.9), (W - w - 0.2, W + 0.1), (lap - 0.1, lap + 0.6))])
    # ---- (9) U-clip bridge slot in the pocket end wall (clip is pressed in from below), pocket mouth lead-in chamfer on the window edge
    z0 = K["clip"]["z0"]
    cuts.append(s.box("t_clip_slot", (K["x_far"] - 0.2, K["x_far"] + 0.3), (yr - K["R"] - 0.6, yr + K["R"] + 0.6), (z0 - 0.1, z0 + K["clip"]["b"] + 0.1)))
    # ---- (10) piezo port + membrane recess and button membrane in the lid roof (over the aux zone)
    ax = L["aux"]["x"]
    xm = (ax[0] + ax[1]) / 2
    pz, bn, pt = (xm - 1.0, L["lane2_y"][1] - 2.8), (xm + 1.0, L["lane2_y"][0] + 3.0), p["port"]
    tcuts += [s.cyl("t_pz", "Z", (pz[0], pz[1], 0), pt["hole_d"], H - w - 0.1, H + 0.1), s.cyl("t_pzr", "Z", (pz[0], pz[1], 0), pt["recess_d"], H - w - 0.1, H - w + pt["recess_depth"]),
              s.cyl("t_bm", "Z", (bn[0], bn[1], 0), p["button"]["d_memb"], H - (w - p["button"]["memb_t"]), H + 0.1)]
    s.join("bottom", joins)
    s.cut("bottom", cuts)
    s.cut("top", tcuts)
