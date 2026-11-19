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
    from op_dock import build_dock_cuts, build_dock_joins, build_mouth_cut
    joins = build_dock_joins(s, p, L)
    if L["mode"] != "bench":
        joins.append(s.cyl("t_boss", "Y", (L["x_s"], 0, sp["z"]), sp["boss_d"], wall - 0.1, L["y_r0"]))

    # ---- Spindellager-Böcke (trocken: in der Stirnwand, nass: hinter dem Reservoir) ------
    bh = dr["bush_od"] + 2 * 0.675
    z_top_blk = zc + bh / 2
    yb = (ys - bh / 2, ys + bh / 2)
    if not L["coax"]:
        joins.append(s.box("t_dblk", (wall + 0.02, dr["gear_x0"] - 0.05), yb, (wall - 0.1, z_top_blk)))
    fb = L["far_block"]
    joins.append(s.box("t_fblk", (fb[0], fb[1]), yb, (wall - 0.1, z_top_blk)))
    # Führungsschiene für den Schlitten
    joins.append(s.box("t_rail", (L["x_r0"] + 0.4, fb[0] - 0.3), (ys - dr["rail_w"] / 2, ys + dr["rail_w"] / 2),
                       (wall - 0.1, dr["rail_top"])))
    # Motor-Sättel (Schalen) unter Getriebekopf/Motor
    ym, zr = L["y_m"], dr["motor_d"] / 2
    saddles = [L["gh_x"][0] + 3.0, L["mo_x"][0] + (0.6 if L["nfp"] else 2.0), L["mo_x"][1] - 2.0]
    if L["coax"]:                                # coaxial motor: cradles under the motor / gearbox on the lane axis
        C = L["coax"]
        ym = ys
        saddles = [C["x_m0"] + 1.2, C["x_m1"] + 1.5, C["x_g1"] - 1.8]
    for i, cx in enumerate(saddles):
        joins.append(s.box(f"t_sad{i}", (cx - dr["cradle_t"] / 2, cx + dr["cradle_t"] / 2), (ym - 2.2, ym + 2.2),
                           (wall - 0.1, wall + dr["cradle_up"] + 0.2)))
    # Kontakt-Regal für Motor-FPC
    bench = L["mode"] == "bench"
    if not bench:
        sf = L["contacts"]["motor_shelf"]
        joins.append(s.box("t_shelf", tuple(sf["x"]), tuple(sf["y"]), (wall - 0.1, sf["z_top"])))
    # Akku-Taschenrippen (Kabel-/Laschenkanal = Lücke bei y der Schraube C)
    rt = bt["rib_t"]
    rx = (L["bat_x0"] - 0.15 - rt, L["bat_x0"] - 0.15)
    for i, (y0, y1) in enumerate(() if bench else ((L["bat_y0"] + 0.1, sc["c_y"] - 1.5), (sc["c_y"] + 1.5, L["bat_y1"] - 0.1))):
        joins.append(s.box(f"t_rib{i}", rx, (y0, y1), (wall - 0.1, wall + bt["rib_h"])))
    # Schraubdome (Hartanschlag für Dichtung bei z = lap_high + gasket_c) und PCB-Stifte
    z_stop = sh["lap_high"] + sh["gasket_c"]
    for i, sp_ in enumerate(L["screws"]):
        joins.append(s.cyl(f"t_dome{i}", "Z", (sp_["x"], sp_["y"], 0), sc["boss_d"], wall - 0.1, z_stop - 0.01))
    if bench:
        bn, mt = p["bench"], p["bench"]["mount"]
        z_b = L["bench"]["z0"]
        for i, q in enumerate(mt["pins"]):
            joins.append(s.cyl(f"t_bpinpost{i}", "Z", (L["x_r1"] + q[0], q[1], 0), mt["pin_post_d"], wall - 0.1, z_b))
            joins.append(s.cyl(f"t_bpin{i}", "Z", (L["x_r1"] + q[0], q[1], 0), mt["pin_d"], z_b - 0.1, z_b + mt["pin_h"] - 0.1))
        for i, q in enumerate(mt["posts"] + [mt["screw"]]):
            d = mt["post_d"] if i < len(mt["posts"]) else mt["boss_d"]
            joins.append(s.cyl(f"t_bpost{i}", "Z", (L["x_r1"] + q[0], q[1], 0), d, wall - 0.1, z_b))
        if L["coax"]:
            from op_coax import build_coax_joins
            joins.extend(build_coax_joins(s, p, L))
    s.join("bottom", joins)

    cut = []
    if L["mode"] != "bench":
        cut.append(s.cyl("t_sb", "Y", (L["x_s"], 0, sp["z"]), sp["d"] + 2 * sp["bore_clr"], -0.1, sp["len"] + 0.3))
        cut.append(s.cyl("t_sc", "Y", (L["x_s"], 0, sp["z"]), sp["port_d"], sp["len"] + 0.2, L["y_r0"] + 0.01))
    else:       # fill-needle access hole in the -Y wall in front of the cap septum
        cut.append(s.cyl("t_fillacc", "Y", (L["x_r1"] + p["dock"]["cap"]["septum_x"], 0, L["dock"]["z_n"]), p["dock"]["cap"]["wall_hole_d"], -0.1, wall + 0.1))
    # Lager-Bohrungen
    bb = dr["bush_od"] + dr["bush_bore_clr"]
    if not L["coax"]:
        cut.append(s.cyl("t_dbore", "X", (0, ys, zc), bb, L["dry_bush"][0], dr["gear_x0"] + 0.05))
    cut.append(s.cyl("t_fbore", "X", (0, ys, zc), bb, fb[0] - 0.1, fb[1] + 0.1))
    # Sattel-Mulden (Motor Ø6.1)
    for i in range(len(saddles)):
        pass
    if not L["coax"]:
        cut.append(s.cyl("t_mcut", "X", (0, ym, zc), dr["motor_d"] + 0.1, L["gh_x"][0] - 0.2, L["mot_end"] + 0.5 - dr["motor_tail"]))
    else:
        cut.append(s.cyl("t_mcut", "X", (0, ys, zc), dr["motor_d"] + 0.1, L["coax"]["x_m0"] - 0.1, L["coax"]["x_fb0"] + 0.1))
    # Schrauben-Pilotlöcher M1.2 (Ø1.0)
    for i, sp_ in enumerate(L["screws"]):
        cut.append(s.cyl(f"t_pil{i}", "Z", (sp_["x"], sp_["y"], 0), sc["pilot"], z_stop - sc["len"] + 2.0, z_stop + 0.1))
    if bench:
        mt, bd = p["bench"]["mount"], L["bench"]
        q = mt["screw"]
        cut.append(s.cyl("t_bscrew", "Z", (L["x_r1"] + q[0], q[1], 0), sc["pilot"], bd["z0"] - 3.4, bd["z0"] + 0.1))
        if L["coax"]:
            from op_coax import build_coax_cuts
            cut.extend(build_coax_cuts(s, p, L))
    cut.append(s.rrect("t_vel", (L["x_r0"] + vc["margin_x"], L["x_r1"] - 1.5), (vc["y0"], vc["y1"]), vc["r"], (-0.1, vc["depth"])))
    n = L["nfp_term"]
    if bench and n and not L["coax"]:       # side-by-side motor: terminal block pocket (pins point down), lead channel to the +X wall slot
        ld = p["bench"]["lead"]
        m = ld["pocket_margin"]
        cut.append(s.box("t_tpocket", (n["block_x"][0] - m, n["block_x"][1] + m), (n["block_y"][0] - m, n["block_y"][1] + m), (ld["pocket_floor"], wall + 0.05)))
        cut.append(s.box("t_leadch", (n["x_center"], L["length"] - wall - 0.2), (ld["groove_y"] - ld["groove_w"] / 2, ld["groove_y"] + ld["groove_w"] / 2), (ld["groove_floor"], ld["groove_top"])))
        cut.append(s.box("t_leadslot", (L["length"] - wall - 0.3, L["length"] + 0.1), (ld["groove_y"] - ld["slot_w"] / 2, ld["groove_y"] + ld["slot_w"] / 2), (ld["groove_floor"], ld["slot_z_top"])))
    s.cut("bottom", cut)
    if bench and n and not L["coax"]:
        ld = p["bench"]["lead"]
        posts = [s.cyl(f"t_zz{k}", "Z", (L["mot_end"] + ld["post_x0"] + k * ld["post_pitch"], ld["groove_y"] + (-1) ** k * ld["post_dy"], 0), ld["post_d"], ld["groove_floor"] - 0.05, wall + ld["post_h"])
                 for k in range(ld["posts"])]
        s.join("bottom", posts)
    dock_cuts = build_dock_cuts(s, p, L) + build_mouth_cut(s, p, L, "t_kmouth")
    s.cut("bottom", dock_cuts)


def build_top(s: Script, p: dict, L: dict) -> None:
    from op_dock import build_mouth_cut
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
    bench = L["mode"] == "bench"
    if bench:
        bd, mt = L["bench"], p["bench"]["mount"]
        for i, q in enumerate(mt["hd"]):
            joins.append(s.cyl(f"t_hd{i}", "Z", (L["x_r1"] + q[0], q[1], 0), mt["hd_d"], bd["ztop"] + 0.05, zi + 0.1))
        s.join("top", joins)
        fl = p["bench"]["ffc"]
        cuts = []
        for i, sp_ in enumerate(L["screws"]):
            cuts.append(s.cyl(f"t_lh{i}", "Z", (sp_["x"], sp_["y"], 0), sc["clear"], z_stop - 0.1, zt + 0.1))
            cuts.append(s.cyl(f"t_lc{i}", "Z", (sp_["x"], sp_["y"], 0), sc["head_d"], zt - sc["head_depth"], zt + 0.1))
        cuts.append(s.box("t_ffcslot", (w - wall - 0.2, w + 0.1), (fl["v"] - fl["slot_w"] / 2, fl["v"] + fl["slot_w"] / 2),
                          tuple(fl["slot_z"])))
        cuts.extend(build_mouth_cut(s, p, L, "t_kmouth_top", top_part=True))
        # fill window over the carriage lane + scale (tick every 10 U delivered, long every 50 U; 1 U = 10 mm3)
        ys_, mm10 = L["y_s"], 100.0 / 74.63
        cuts.append(s.box("t_fillwin", (L["xrear_full"] + 0.5, L["xrear_empty"] + 3.5), (ys_ - 1.0, ys_ + 1.0), (zt - wall - 0.1, zt + 0.1)))
        k = 0
        while k * mm10 <= L["stroke"] + 1e-6:
            x = L["xrear_full"] + k * mm10
            ln = 1.0 if k % 5 == 0 else 0.5
            cuts.append(s.box(f"t_tick{k}", (x - 0.12, x + 0.12), (ys_ + 1.3, ys_ + 1.3 + ln), (zt - 0.3, zt + 0.1)))
            k += 1
        s.cut("top", cuts)
        return
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
    cuts.extend(build_mouth_cut(s, p, L, "t_kmouth_top", top_part=True))
    s.cut("top", cuts)


def build_gasket(s: Script, p: dict, L: dict) -> None:
    sh = p["shell"]
    w, wd, r, wall = L["length"], L["width"], sh["corner_r"], sh["wall"]
    z0 = sh["lap_high"]
    ri = sh["rim_inset"]
    s.rrect("gasket", (ri, w - ri), (ri, wd - ri), r - ri, (z0 + 0.005, z0 + sh["gasket_c"] - 0.005))
    s.rrect("t_gin", (wall, w - wall), (wall, wd - wall), r - wall, (z0 - 0.1, z0 + sh["gasket_c"] + 0.1))
    s.cut("gasket", ["t_gin"])
    from op_dock import build_mouth_cut
    s.cut("gasket", build_mouth_cut(s, p, L, "t_gmouth", top_part=True))
