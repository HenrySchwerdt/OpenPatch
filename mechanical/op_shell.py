"""Gehäuse: Boden (bottom), Deckel (top), Dichtung (gasket)."""
from __future__ import annotations

import math

from op_cmds import Script


def build_bottom(s: Script, p: dict, L: dict) -> None:
    sh, sp, nd, cn, vc, dr = p["shell"], p["septum"], p["needle"], p["cannula"], p["velcro"], p["drive"]
    bt, sc, ct, co = p["battery"], p["screws"], p["contacts"], p["coil"]
    w, wd, r, wall = L["length"], L["width"], sh["corner_r"], sh["wall"]
    zc, ys = L["z_axis"], L["y_s"]
    s.rrect("bottom", (0, w), (0, wd), r, (0, sh["lap_low"]))
    s.rrect("t_rim", (sh["rim_inset"], w - sh["rim_inset"]), (sh["rim_inset"], wd - sh["rim_inset"]),
            r - sh["rim_inset"], (sh["lap_low"] - 0.01, sh["lap_high"]))
    s.join("bottom", ["t_rim"])
    s.rrect("t_cav", (wall, w - wall), (wall, wd - wall), r - wall, (wall, sh["lap_high"] + 0.5))
    s.cut("bottom", ["t_cav"])

    # ---- Kanülenturm, Septum-Boss ---------------------------------------------------
    tx0 = L["x_r1"]
    ty1 = L["y_p"] + cn["B_plate_width"] / 2 + cn["N_clearance"] + 0.9
    joins = [s.box("t_tower", (tx0, tx0 + L["tower_x"]), (wall - 0.1, ty1), (wall - 0.1, nd["tower_top"]))]
    joins.append(s.cyl("t_boss", "Y", (L["x_s"], 0, sp["z"]), sp["boss_d"], wall - 0.1, L["y_r0"]))

    # ---- Spindellager-Böcke (trocken: in der Stirnwand, nass: hinter dem Reservoir) ------
    bh = dr["bush_od"] + 2 * 0.675
    z_top_blk = zc + bh / 2
    yb = (ys - bh / 2, ys + bh / 2)
    joins.append(s.box("t_dblk", (wall + 0.02, dr["gear_x0"] - 0.05), yb, (wall - 0.1, z_top_blk)))
    fb = L["far_block"]
    joins.append(s.box("t_fblk", (fb[0], fb[1]), yb, (wall - 0.1, z_top_blk)))
    # Führungsschiene für den Schlitten
    joins.append(s.box("t_rail", (L["x_r0"] + 0.4, fb[0] - 0.3), (ys - dr["rail_w"] / 2, ys + dr["rail_w"] / 2),
                       (wall - 0.1, dr["rail_top"])))
    # Motor-Sättel (Schalen) unter Getriebekopf/Motor
    ym, zr = L["y_m"], dr["motor_d"] / 2
    saddles = [L["gh_x"][0] + 3.0, L["mo_x"][0] + 2.0, L["mo_x"][1] - 2.0]
    for i, cx in enumerate(saddles):
        joins.append(s.box(f"t_sad{i}", (cx - dr["cradle_t"] / 2, cx + dr["cradle_t"] / 2), (ym - 2.2, ym + 2.2),
                           (wall - 0.1, wall + dr["cradle_up"] + 0.2)))
    # Kontakt-Regal für Motor-FPC
    sf = L["contacts"]["motor_shelf"]
    joins.append(s.box("t_shelf", tuple(sf["x"]), tuple(sf["y"]), (wall - 0.1, sf["z_top"])))
    # Akku-Taschenrippen (Kabel-/Laschenkanal = Lücke bei y der Schraube C)
    rt = bt["rib_t"]
    rx = (L["bat_x0"] - 0.15 - rt, L["bat_x0"] - 0.15)
    for i, (y0, y1) in enumerate(((L["bat_y0"] + 0.1, sc["c_y"] - 1.5), (sc["c_y"] + 1.5, L["bat_y1"] - 0.1))):
        joins.append(s.box(f"t_rib{i}", rx, (y0, y1), (wall - 0.1, wall + bt["rib_h"])))
    # Schraubdome (Hartanschlag für Dichtung bei z = lap_high + gasket_c) und PCB-Stifte
    z_stop = sh["lap_high"] + sh["gasket_c"]
    for i, sp_ in enumerate(L["screws"]):
        joins.append(s.cyl(f"t_dome{i}", "Z", (sp_["x"], sp_["y"], 0), sc["boss_d"], wall - 0.1, z_stop - 0.01))
    for i, (dx, dy) in enumerate(((0.8, 4.5), (L["tower_x"] - 1.1, 11.0))):
        joins.append(s.cyl(f"t_pin{i}", "Z", (L["x_r1"] + dx, dy, 0), 1.0, nd["tower_top"] - 0.1, nd["tower_top"] + 0.7))
    s.join("bottom", joins)

    cut = []
    ph = L["pocket_h"]
    px = cn["A_plate_length"] / 2 + cn["N_clearance"]
    py = cn["B_plate_width"] / 2 + cn["N_clearance"]
    cut.append(s.box("t_pocket", (L["x_p"] - px, L["x_p"] + px), (L["y_p"] - py, L["y_p"] + py), (-0.1, ph)))
    gy = cn["E_wing_len"] / 2
    gz = (cn["G_wing_z"], cn["G_wing_z"] + cn["F_wing_height"])
    D = cn["D_wing_groove_depth"]
    cut.append(s.box("t_gr1", (L["x_p"] + px - 0.01, L["x_p"] + px + D), (L["y_p"] - gy, L["y_p"] + gy), gz))
    cut.append(s.box("t_gr2", (L["x_p"] - px - D, L["x_p"] - px + 0.01), (L["y_p"] - gy, L["y_p"] + gy), gz))
    # Schnapp-Rast (TODO-MEASURE: Federweg/Steifigkeit): Schlitze links/rechts der Flügelzone
    for k, sgn in enumerate((1, -1)):
        xw = L["x_p"] + sgn * px
        xa, xb = sorted((xw, xw + sgn * 1.4))
        for j, sy in enumerate((-1, 1)):
            yc = L["y_p"] + sy * (gy + 0.5)
            cut.append(s.box(f"t_slit{k}{j}", (xa, xb), (yc - 0.2, yc + 0.2), (gz[0] - 0.6, nd["tower_top"] + 0.1)))
    # Nadel-Bohrung, Kanal, Naben-Sitz
    cut.append(s.cyl("t_nb", "Z", (L["x_n"], L["y_n"], 0), nd["bore_d"], ph - 0.1, nd["channel_z"] + 0.1))
    cut.append(s.cyl("t_nh", "Z", (L["x_n"], L["y_n"], 0), nd["hub_d"], nd["hub_z0"] - 0.0, nd["hub_z0"] + nd["hub_t"]))
    cut.append(s.cyl("t_nc", "X", (0, L["y_n"], nd["channel_z"]), nd["channel_d"], L["x_r1"] - 0.5, L["x_n"]))
    cut.append(s.cyl("t_sb", "Y", (L["x_s"], 0, sp["z"]), sp["d"] + 2 * sp["bore_clr"], -0.1, sp["len"] + 0.3))
    cut.append(s.cyl("t_sc", "Y", (L["x_s"], 0, sp["z"]), sp["port_d"], sp["len"] + 0.2, L["y_r0"] + 0.01))
    # Lager-Bohrungen
    bb = dr["bush_od"] + dr["bush_bore_clr"]
    cut.append(s.cyl("t_dbore", "X", (0, ys, zc), bb, L["dry_bush"][0], dr["gear_x0"] + 0.05))
    cut.append(s.cyl("t_fbore", "X", (0, ys, zc), bb, fb[0] - 0.1, fb[1] + 0.1))
    # Sattel-Mulden (Motor Ø6.1)
    for i in range(len(saddles)):
        pass
    cut.append(s.cyl("t_mcut", "X", (0, ym, zc), dr["motor_d"] + 0.1, L["gh_x"][0] - 0.2, L["mot_end"] + 0.5 - dr["motor_tail"]))
    # Schrauben-Pilotlöcher M1.2 (Ø1.0)
    for i, sp_ in enumerate(L["screws"]):
        cut.append(s.cyl(f"t_pil{i}", "Z", (sp_["x"], sp_["y"], 0), sc["pilot"], z_stop - sc["len"] + 2.0, z_stop + 0.1))
    cut.append(s.rrect("t_vel", (L["x_r0"] + vc["margin_x"], L["x_r1"] - 1.5), (vc["y0"], vc["y1"]), vc["r"], (-0.1, vc["depth"])))
    s.cut("bottom", cut)


def build_top(s: Script, p: dict, L: dict) -> None:
    sh, sc, bn, pt, co, ct = p["shell"], p["screws"], p["button"], p["port"], p["coil"], p["contacts"]
    w, wd, r, wall = L["length"], L["width"], sh["corner_r"], sh["wall"]
    z_stop = sh["lap_high"] + sh["gasket_c"]
    zt = sh["height"]
    s.rrect("top", (0, w), (0, wd), r, (sh["lap_low"] + 0.01, zt))
    if sh["top_fillet"] > 0:
        s.fillet_chain("top", (w / 2, 0.0, zt), sh["top_fillet"])
    ri = sh["lid_ring_inset"]
    s.rrect("t_lca", (ri, w - ri), (ri, wd - ri), r - ri, (sh["lap_low"] - 0.1, z_stop))
    s.rrect("t_lcb", (wall, w - wall), (wall, wd - wall), r - wall, (z_stop - 0.01, zt - wall))
    s.cut("top", ["t_lca", "t_lcb"])
    zi = zt - wall
    joins = []
    for i, sp_ in enumerate(L["screws"]):
        joins.append(s.cyl(f"t_lb{i}", "Z", (sp_["x"], sp_["y"], 0), sc["boss_d"] + 0.2, z_stop, zi + 0.1))
    # Spulensitz: 4 Pratzen außerhalb der Spule
    cx, cy = L["coil"]["cx"], L["coil"]["cy"]
    rr = L["coil"]["d"] / 2 + 0.7
    for i, ang in enumerate((45, 135, -45, -135)):
        a = math.radians(ang)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        joins.append(s.box(f"t_tab{i}", (x - 0.4, x + 0.4), (y - 0.4, y + 0.4), (co["z0"] - 0.1, zi + 0.1)))
    # Taster-Stößel und Halte-Pads
    bx, by = L["button"]["x"], L["button"]["y"]
    z_post = 5.5 + bn["sw_z"] + bn["post_gap"]
    joins.append(s.cyl("t_post", "Z", (bx, by, 0), bn["post_d"], z_post, zi + 0.1))
    for i, hp in enumerate(L["contacts"]["hold_down_pads"]):
        joins.append(s.cyl(f"t_hd{i}", "Z", (hp["x"], hp["y"], 0), hp["d"], hp["z0"], zi + 0.1))
    s.join("top", joins)
    cuts = []
    for i, sp_ in enumerate(L["screws"]):
        cuts.append(s.cyl(f"t_lh{i}", "Z", (sp_["x"], sp_["y"], 0), sc["clear"], z_stop - 0.1, zt + 0.1))
        cuts.append(s.cyl(f"t_lc{i}", "Z", (sp_["x"], sp_["y"], 0), sc["head_d"], zt - sc["head_depth"], zt + 0.1))
    cuts.append(s.cyl("t_memb", "Z", (bx, by, 0), bn["d_memb"], zt - (wall - bn["memb_t"]), zt + 0.1))
    bz = L["buzzer"]
    px, py = (bz["x0"] + bz["x1"]) / 2, (bz["y0"] + bz["y1"]) / 2
    cuts.append(s.cyl("t_port", "Z", (px, py, 0), pt["hole_d"], zi - 0.1, zt + 0.1))
    cuts.append(s.cyl("t_prec", "Z", (px, py, 0), pt["recess_d"], zi - 0.1, zi + pt["recess_depth"]))
    s.cut("top", cuts)


def build_gasket(s: Script, p: dict, L: dict) -> None:
    sh = p["shell"]
    w, wd, r, wall = L["length"], L["width"], sh["corner_r"], sh["wall"]
    z0 = sh["lap_high"]
    ri = sh["rim_inset"]
    s.rrect("gasket", (ri, w - ri), (ri, wd - ri), r - ri, (z0 + 0.005, z0 + sh["gasket_c"] - 0.005))
    s.rrect("t_gin", (wall, w - wall), (wall, wd - wall), r - wall, (z0 - 0.1, z0 + sh["gasket_c"] + 0.1))
    s.cut("gasket", ["t_gin"])
