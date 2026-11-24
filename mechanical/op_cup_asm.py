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
    ("6 seal ring + USB-C frame + lid (button cap + O-ring pre-fitted in the lid) + 3 screws", ["lid_gasket", "usb_gasket", "top", "button_oring", "button_cap"]),
    ("7 dock parts from BELOW through the pocket (springs: tabs pushed up into the anchor slots)", ["hub_gasket", "needle_hub", "needle", "needle_guard", "dock_clip"]),
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
    # ---- (1) shell joint (owner 2026-11-24): lid bottom face sits on the bottom-shell rim at z = lap (plastic-to-plastic hard stop, flush outer seam); seal ring in a groove in the
    #          rim at constant distance from the outer wall, pressed by a tongue under the lid; 3 posts in the bottom corners (thread-forming M1.2 into d1.0 pilots, 4 mm deep),
    #          post tops `post_gap` below the lid roof so only the rim carries the lid; flush countersunk heads in the clear lid, sealed with a dab of silicone
    jt = c["joint"]
    rr = c["corner_r_outer"]
    for k, (px, py) in enumerate(posts):
        joins.append(s.cyl(f"t_post{k}", "Z", (px, py, 0), 2.0, w - 0.1, H - w - jt["post_gap"]))
        cuts.append(s.cyl(f"t_pilot{k}", "Z", (px, py, 0), 1.0, H - w - 4.0, H - w))
        tcuts += [s.cyl(f"t_tcl{k}", "Z", (px, py, 0), 2.4, lap + 0.001, H - w + 0.05), s.cyl(f"t_thole{k}", "Z", (px, py, 0), 1.4, H - w - 0.1, H + 0.1),
                  s.cyl(f"t_thead{k}", "Z", (px, py, 0), 2.4, H - 0.6, H + 0.1)]
    u = L["usb"]
    xu, zu = u["x_c"], u["z_c"]
    sk = jt["usb_skip_half"]
    rim = ((0, Lp), (0, W))

    def usb_skip(name: str) -> str:              # groove, tongue and seal end at the USB-C gasket frame (the frame carries the seal across the joint there)
        return s.box(name, (xu - sk, xu + sk), (W - 2.0, W + 0.1), (lap - 1.0, lap + 1.0))
    s.rrect_ring("t_groove", *rim, rr, tuple(jt["groove_off"]), (lap - jt["groove_depth"], lap + 0.01))
    s.cut("t_groove", [usb_skip("t_gr_usb")])
    cuts.append("t_groove")
    s.rrect_ring("t_tongue", *rim, rr, tuple(jt["tongue_off"]), (lap - jt["tongue_h"], lap + 0.01))
    s.cut("t_tongue", [usb_skip("t_to_usb")])
    tjoins.append("t_tongue")
    s.rrect_ring("lid_gasket", *rim, rr, tuple(jt["seal_off"]), (lap - jt["groove_depth"], lap - jt["groove_depth"] + jt["seal_h"]))
    s.cut("lid_gasket", [usb_skip("t_lg_usb")])
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
        tjoins.append(s.cyl(f"t_hold{k}", "Z", (x, y, 0), bs["rib_d"], zb1 + jt["rib_gap"], H - w + 0.05))
    for k, (x, y) in enumerate(L["board_screws"]):                                   # board screw bosses (top = board underside), thread-forming pilot from the top
        joins.append(s.cyl(f"t_sboss{k}", "Z", (x, y, 0), bs["boss_d"], w - 0.1, bs["z_top"]))
        cuts.append(s.cyl(f"t_spilot{k}", "Z", (x, y, 0), bs["pilot_d"], bs["z_top"] - bs["pilot_depth"], bs["z_top"] + 0.01))
    joins.append(s.box("t_shelf", tuple(bs["shelf_x"]), (bs["shelf_y0"], W - w + 0.05), (w - 0.1, lap)))           # above the rim the shelf stays inside the lid wall face
    joins.append(s.box("t_shelf_t", tuple(bs["shelf_x"]), (bs["shelf_y0"], W - w), (lap - 0.01, bs["z_top"])))
    tjoins.append(s.box("t_hold_w", tuple(bs["shelf_x"]), (bs["shelf_y0"], W - w + 0.05), (zb1 + jt["rib_gap"], H - w + 0.05)))
    # ---- (7b) side button (owner 2026-11-24): printed cap in a round hole through the +Y LID wall, inserted from inside (flange bar inside), O-ring rod seal in a counterbore
    build_button(s, c, L, tcuts)
    # ---- (8) USB-C seat: STADIUM opening through bottom AND lid wall with a 0.3 x 45 deg outer chamfer, stadium gasket recess in the wall inner face, stadium silicone frame
    build_usb(s, c, L, cuts, tcuts)
    s.join("bottom", joins)
    s.cut("bottom", cuts)
    s.join("top", tjoins)
    s.cut("top", tcuts)


def build_button(s: Script, c: dict, L: dict, tcuts: list) -> None:
    """Button cap (MFG part `button_cap`) + O-ring (`button_oring`) + their lid cuts.  y: wall inner face W - w, outer face W; the cap is drawn at rest."""
    bt = c["button"]
    W, w = L["width"], L["wall"]
    xb, zb = bt["x_c"], bt["z_c"]
    yi, yo = W - w, W
    yc = yi + bt["cbore_depth"]
    tcuts += [s.cyl("t_btn_cb", "Y", (xb, 0, zb), bt["cbore_d"], yi - 0.05, yc),
              s.cyl("t_btn_bore", "Y", (xb, 0, zb), bt["bore_d"], yc - 0.01, yo + 0.1),
              s.cone("t_btn_ch", "Y", (xb, 0, zb), bt["bore_d"] / 2, bt["bore_d"] / 2 + bt["bore_chamfer"] + 0.1, yo - bt["bore_chamfer"], yo + 0.1)]
    yf = yo - bt["face_recess"]
    fc = bt["face_chamfer"]
    s.cyl("button_cap", "Y", (xb, 0, zb), bt["stem_d"], yi - 0.1, yf - fc)
    parts = [s.cone("t_bc_ch", "Y", (xb, 0, zb), bt["stem_d"] / 2, bt["stem_d"] / 2 - fc, yf - fc, yf),
             s.box("t_bc_fl", tuple(bt["flange"]["x"]), (yi - bt["flange"]["t"], yi), tuple(bt["flange"]["z"])),
             s.box("t_bc_pad", tuple(bt["pad"]["x"]), (bt["pad"]["face_y"], yi - bt["flange"]["t"] + 0.01), tuple(bt["pad"]["z"]))]
    s.join("button_cap", parts)
    s.tube("button_oring", "Y", (xb, 0, zb), bt["cbore_d"] - 0.01, bt["stem_d"] + 0.01, yi, yc - 0.005)          # drawn installed: 0.5 CS squeezed radially into the 0.4 gland (d2.4 / d1.6)


def build_usb(s: Script, c: dict, L: dict, cuts: list, tcuts: list) -> None:
    usb = c["usb"]
    W, w = L["width"], L["wall"]
    u = L["usb"]
    xu, zu = u["x_c"], u["z_c"]
    ow, oh, m, ch, g = usb["open_w"], usb["open_h"], usb["recess_margin"], usb["chamfer_out"], usb["gasket"]
    for sfx, lst in (("b", cuts), ("t", tcuts)):
        lst.append(s.stadium_y(f"t_usb_open_{sfx}", (W - w - 0.1, W + 0.1), xu, zu, ow, oh))
        lst.append(s.stadium_y(f"t_usb_ch_{sfx}", (W - ch, W + 0.01), xu, zu, ow, oh, taper_deg=45.0))
        rec = s.stadium_y(f"t_usb_rec_{sfx}", (W - w - 0.05, W - w + usb["recess_depth"]), xu, zu, ow + 2 * m, oh + 2 * m)
        s.cut(rec, [s.box(f"t_usb_rec_clip_{sfx}", (xu - ow, xu + ow), (W - w - 0.2, W), (usb["recess_z_max"], zu + oh))])
        lst.append(rec)
    s.stadium_y("usb_gasket", (W - w, W - w + g["t"]), xu, zu, ow + 2 * g["margin"], oh + 2 * g["margin"])
    s.cut("usb_gasket", [s.stadium_y("t_ug_in", (W - w - 0.1, W - w + g["t"] + 0.1), xu, zu, g["in_w"], g["in_h"]),
                         s.box("t_ug_clip", (xu - ow, xu + ow), (W - w - 0.2, W), (g["z_max"], zu + oh))])
