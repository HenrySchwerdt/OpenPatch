# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Assembly features of the cup-pod housing (drop-in seats, closure, gaskets).  Adds housing geometry only; no component or keep-out box is moved."""
from __future__ import annotations

from op_cmds import Script

# assembly order (each group drops in from above unless noted); used by cup_check (drop test), ASSEMBLY-CUP.md and the exploded render
ORDER = [
    ("1 housing", ["bottom"]),
    ("2 tank + plunger + rod cartridge", ["reservoir", "plunger_core", "seal_a", "seal_b", "nut", "rod", "gear_b", "bush_rod", "thrust_collar", "magnet", "septum"]),
    ("3 motor + gear A", ["motor", "gearhead", "motor_boss", "motor_rear_boss", "motor_shaft", "gear_a", "motor_term"]),
    ("4 battery (301030)", ["ko_battery"]),
    ("5 board + USB-C + piezo/button (PCBA; motor 4 + cell 2 wires soldered to its west-end pads first)", ["ko_board", "ko_board_tab", "ko_usb", "ko_aux", "ko_io", "ko_side_a", "ko_side_b", "ko_tmag_board", "hall_tmag", "ko_dock_board", "hall_dock"]),
    ("6 gaskets + lid + 3 screws", ["lid_gasket", "usb_gasket", "top"]),
    ("7 dock parts from BELOW through the pocket window", ["hub_gasket", "needle_hub", "needle", "needle_guard", "dock_clip"]),
]
FROM_BELOW = {"hub_gasket", "needle_hub", "needle", "needle_guard", "dock_clip", "cannula_adapter", "dock_magnet"}


def corner_posts(L: dict) -> list[tuple[float, float]]:
    w, Lp, W = L["wall"], L["length"], L["width"]
    return [(w + 1.65, w + 1.65), (Lp - w - 1.65, w + 1.65), (Lp - w - 1.65, W - w - 1.65)]


def build(s: Script, p: dict, L: dict) -> None:
    c, K = p["cup"], L["dock"]
    w, Lp, W, H, lap = L["wall"], L["length"], L["width"], L["height"], p["shell"]["lap_low"]
    zc, yr, xc = L["zc"], L["y_r"], L["xc"]
    dr = p["drive_nfp"]
    bu, usb, bat = c["bush"], c["usb"], c["battery"]
    posts = corner_posts(L)
    joins, cuts, tcuts, tjoins = [], [], [], []
    # ---- (1) lid closure from the TOP: 3 posts in the bottom corners (thread-forming M1.2 into d1.0 pilots, 4 mm deep); flush countersunk heads in the clear lid, sealed under the head by a
    #          0.3 mm silicone washer; the lid roof rests on the post tops; flat silicone gasket on the rim
    rr = c["corner_r_outer"]
    for k, (px, py) in enumerate(posts):
        joins.append(s.cyl(f"t_post{k}", "Z", (px, py, 0), 2.0, w - 0.1, H - w - 0.05))
        cuts.append(s.cyl(f"t_pilot{k}", "Z", (px, py, 0), 1.0, H - w - 4.0, H - w))
        tcuts += [s.cyl(f"t_tcl{k}", "Z", (px, py, 0), 2.4, lap + 0.3, H - w + 0.05), s.cyl(f"t_thole{k}", "Z", (px, py, 0), 1.4, H - w - 0.1, H + 0.1),
                  s.cyl(f"t_thead{k}", "Z", (px, py, 0), 2.4, H - 0.6, H + 0.1)]
    s.rrect("lid_gasket", (0.15, Lp - 0.15), (0.15, W - 0.15), rr - 0.15, (lap, lap + 0.5))
    s.rrect("t_gk_in", (0.55, Lp - 0.55), (0.55, W - 0.55), rr - 0.55, (lap - 0.1, lap + 0.6))
    s.cut("lid_gasket", ["t_gk_in"])
    # ---- (2) motor cradle: U saddles with snap lips (built in op_cup.py) hold the can; nothing hangs from the lid; FPC groove from the pin pocket toward lane 2
    yt = L["gearhead_y"][0] + dr["term_x"]
    cuts.append(s.box("t_fpc_groove", (xc, L["battery"]["x"][0] - 0.1), (yt - 1.1, yt + 1.1), (0.35, w + 0.01)))
    # ---- (3) tank seat: rear stop blocks (datum at the dry rim), front datum = dock pocket face; O-ring face groove around the needle-hub seat
    for k, (y0, y1) in enumerate(((7.4, 9.4), (yr + 5.0, yr + 7.0))):
        joins.append(s.box(f"t_stop{k}", (L["x_dry"] - 0.7, L["x_dry"] - 0.05), (y0, y1), (w - 0.1, 2.0)))
    zn = K["z_n"]
    hs = c["dock"]["hub_seal"]                      # flat ring cut from the 0.5 mm silicone sheet (no standard 3.2 x 2.4 x 0.4 O-ring is orderable): seated in the groove, protrudes t - depth
    s.tube("t_hog", "X", (0, yr, zn), hs["groove_od"], hs["groove_id"], L["x_t0"] - hs["groove_depth"], L["x_t0"] + 0.01)
    s.cut("reservoir", ["t_hog"])
    s.tube("hub_gasket", "X", (0, yr, zn), hs["od"], hs["id"], L["x_t0"] - hs["groove_depth"], L["x_t0"] - hs["groove_depth"] + hs["t"])
    # ---- (4) bearing rib is a U cradle (slot open to the top); relief pockets for gear A / B already cut
    cuts.append(s.box("t_rib_slot", (L["bush"][0] - 0.05, L["bush"][1] + 0.05), (yr - (bu["od"] + bu["bore_clr"]) / 2, yr + (bu["od"] + bu["bore_clr"]) / 2), (zc, zc + 3.0)))
    # ---- (6) battery tray: 0.4 mm floor recess (swell / wire reserve, lateral retention)
    b = L["battery"]
    cuts.append(s.box("t_bat_tray", (b["x"][0] - 0.1, b["x"][1] + 0.1), (b["y"][0] + 0.2, b["y"][1] + 0.05), (w - 0.4, w + 0.01)))
    # ---- (7) board 3-point support (board review 2026-11-20 fix 5): two d1.0 floor ledges east of the cell + one shelf on the +Y wall at the west end, all with top z 5.3
    #          (= board underside); three lid hold-down ribs press the board top (z 6.1) at the same x/y (rib 1.5 = lid inner 7.6 - 6.1, nominal zero gap, VERIFY on the print)
    bs = c["board_support"]
    zb1 = c["board"]["pcb_z"][1]
    for k, (x, y) in enumerate(bs["ledges"]):
        joins.append(s.cyl(f"t_ledge{k}", "Z", (x, y, 0), bs["ledge_d"], w - 0.1, bs["z_top"]))
        tjoins.append(s.cyl(f"t_hold{k}", "Z", (x, y, 0), bs["rib_d"], zb1, H - w + 0.05))
    for k, (x, y) in enumerate(L["board_screws"]):                                   # board screw bosses (top = board underside), thread-forming pilot from the top
        joins.append(s.cyl(f"t_sboss{k}", "Z", (x, y, 0), bs["boss_d"], w - 0.1, bs["z_top"]))
        cuts.append(s.cyl(f"t_spilot{k}", "Z", (x, y, 0), bs["pilot_d"], bs["z_top"] - bs["pilot_depth"], bs["z_top"] + 0.01))
    joins.append(s.box("t_shelf", tuple(bs["shelf_x"]), (bs["shelf_y0"], W - w + 0.05), (w - 0.1, bs["z_top"])))
    tjoins.append(s.box("t_hold_w", tuple(bs["shelf_x"]), (bs["shelf_y0"], W - w + 0.05), (zb1, H - w + 0.05)))
    # ---- (7b) side button (fix 6): flex window in the +Y LID wall, recessed from outside to a 0.45 mm membrane (below the R1.8 top fillet), 0.3 mm inner nub on the SW1 actuator
    bt = c["button"]
    tcuts.append(s.box("t_btn_win", tuple(bt["win_x"]), (W - w + bt["wall_left"], W + 0.1), tuple(bt["win_z"])))
    tjoins.append(s.box("t_btn_nub", (bt["x_c"] - bt["nub_w"] / 2, bt["x_c"] + bt["nub_w"] / 2), (W - w - bt["nub_t"], W - w + 0.05), tuple(bt["nub_z"])))
    # ---- (8) USB-C seat: opening through bottom wall AND lid wall, gasket recess 0.4 deep in the wall inner face, silicone frame (centre x 23.5, board mid-plane z 5.7)
    u = L["usb"]
    xu, zu = u["x_c"], u["z_c"]
    cuts.append(s.box("t_usb_rec", (xu - usb["open_w"] / 2 - 0.9, xu + usb["open_w"] / 2 + 0.9), (W - w - 0.05, W - w + 0.4), (zu - usb["open_h"] / 2 - 0.9, min(lap, zu + usb["open_h"] / 2 + 0.9))))
    tcuts += [s.box("t_usb_open_t", (xu - usb["open_w"] / 2, xu + usb["open_w"] / 2), (W - w - 0.1, W + 0.1), (lap, zu + usb["open_h"] / 2)),
              s.box("t_usb_rec_t", (xu - usb["open_w"] / 2 - 0.9, xu + usb["open_w"] / 2 + 0.9), (W - w - 0.05, W - w + 0.4), (lap + 0.4, zu + usb["open_h"] / 2 + 0.9))]
    s.box("usb_gasket", (xu - usb["open_w"] / 2 - 0.8, xu + usb["open_w"] / 2 + 0.8), (W - w, W - w + 0.4), (max(zu - usb["open_h"] / 2 - 0.8, w + 0.1), min(lap, zu + usb["open_h"] / 2 + 0.8)))
    s.cut("usb_gasket", [s.box("t_ug_in", (xu - usb["open_w"] / 2, xu + usb["open_w"] / 2), (W - w - 0.1, W - w + 0.5), (zu - usb["open_h"] / 2, zu + usb["open_h"] / 2))])
    s.cut("lid_gasket", [s.box("t_lg_usb", (xu - usb["open_w"] / 2 - 0.9, xu + usb["open_w"] / 2 + 0.9), (W - w - 0.2, W + 0.1), (lap - 0.1, lap + 0.6))])
    # ---- (9) U-clip bridge slot in the pocket end wall (clip is pressed in from below), pocket mouth lead-in chamfer on the window edge
    z0 = K["clip"]["z0"]
    cuts.append(s.box("t_clip_slot", (K["x_far"] - 0.2, K["x_far"] + 0.3), (yr - K["R"] - 0.6, yr + K["R"] + 0.6), (z0 - 0.1, z0 + K["clip"]["b"] + 0.1)))
    s.join("bottom", joins)
    s.cut("bottom", cuts)
    s.join("top", tjoins)
    s.cut("top", tcuts)
