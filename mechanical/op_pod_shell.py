# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Housing of the v0.1.0 integrated pod: bottom shell (MJF PA12), clear lid (SLA), main gasket.  See op_pod.py.  TEST PROJECT, water only."""
from __future__ import annotations

from op_cmds import Script


def build_bottom(s: Script, p: dict, L: dict) -> None:
    from op_dock import build_mouth_cut, build_pod_dock_interface
    sh, sc, vc, P = p["shell"], p["screws"], p["velcro"], p["pod"]
    G = L["geo"]
    wall, length, W, r = L["wall"], L["length"], L["width"], sh["corner_r"]
    zc, xr = L["z_axis"], L["x_r1"]
    dr, mo = P["drive"], p["pod"]["motor"]["options"][p["pod"]["motor"]["option"]]
    D = L["dock"]
    ym0, ym1 = D["y_c"] - D["mouth_half"], D["y_c"] + D["mouth_half"]
    s.rrect("bottom", (0, length), (0, W), r, (0, sh["lap_high"]))
    s.rrect("t_cav", (wall, length - wall), (wall, W - wall), r - wall, (wall, sh["lap_high"] + 0.5))
    s.cut("bottom", ["t_cav"])
    L2 = dict(L, wall=wall + P["dock"]["floor_pad"])
    bumps, dcuts = build_pod_dock_interface(s, p, L2)
    joins, cuts = [], []
    Fz = p["dock_interface_frozen"]
    joins.append(s.box("t_dockpad", (xr + Fz["x0_u"], length - wall), (D["y_c"] - Fz["pocket_half"] - 0.6, D["y_c"] + Fz["pocket_half"] + 0.6), (wall - 0.1, wall + P["dock"]["floor_pad"])))
    z_stop = sh["lap_high"] + sh["gasket_c"]
    hb = sc["boss_d"] / 2
    for i, q in enumerate(L["screws"]):
        x0b, x1b = q["x"] - hb, q["x"] + hb
        if q["y"] < 10:
            yb = (wall, q["y"] + hb)
        elif q["x"] < 4.0:                                 # rear +Y screw: block merged into the rear wall
            x0b, yb = wall, (q["y"] - hb, q["y"] + hb)
        else:
            yb = (q["y"] - hb, W - wall)
        joins.append(s.box(f"t_dome{i}", (x0b, x1b), yb, (wall - 0.1, sh["lap_high"])))
        ins = 0.03                                         # above the wall top the block stands 0.03 mm clear of the gasket ring (no coincident faces)
        xu0, xu1, yu0, yu1 = x0b + (ins if x0b == wall else 0.0), x1b, yb[0] + (ins if yb[0] == wall else 0.0), yb[1] - (ins if yb[1] == W - wall else 0.0)
        joins.append(s.box(f"t_domeu{i}", (xu0, xu1), (yu0, yu1), (sh["lap_high"] - 0.1, z_stop - 0.01)))
        cuts.append(s.cyl(f"t_pil{i}", "Z", (q["x"], q["y"], 0), sc["pilot"], z_stop - 2.9, z_stop + 0.1))
    # --- bearing block of the nut-gear bush (the bush carries the screw reaction through the sleeve)
    bx0, bx1 = L["bush"]
    bh = dr["bush_od"] + 2 * dr["block_wall"]
    joins.append(s.box("t_bblk", (bx0 - 0.05, bx1), (L["y_r"] - bh / 2, L["y_r"] + bh / 2), (wall - 0.1, zc + bh / 2)))
    cuts.append(s.cyl("t_bbore", "X", (0, L["y_r"], zc), dr["bush_od"] + dr["bush_bore_clr"], bx0 - 0.1, bx1 + 0.1))
    # --- motor saddles + trough
    ym = L["y_m"]
    x_m0 = L["x_mrear"] + mo["tail"]
    for i, cx in enumerate((L["x_gh1"] - 6.4, L["x_gh1"] - 3.9, L["x_gh1"] - 1.4)):
        joins.append(s.box(f"t_sad{i}", (cx - 0.6, cx + 0.6), (ym - mo["d"] / 2 - 0.5, ym + mo["d"] / 2 + 0.5), (wall - 0.1, zc)))
    cuts.append(s.cyl("t_mcut", "X", (0, ym, zc), mo["d"] + 0.1, x_m0 - 0.1, L["x_gh1"] + 0.1))
    # --- motor contact card: seat block with a slot (the block sits above the spine channel)
    mc = G["motor_card"]
    z_blk = P["mcard"]["z"][0] + 0.6                    # block top below the spring row (springs start at z_c - 1.8 - 0.4 = 2.05)
    joins.append(s.box("t_cardblk", (mc["x"][0] - 0.55, mc["x"][1] + 0.55), (mc["y"][0] - 1.0, mc["y"][1] + 0.8), (wall - 0.1, z_blk)))
    cuts.append(s.box("t_cardslot", tuple(mc["x"]), (mc["y"][0] - 0.15, mc["y"][1] + 0.15), (mc["z"][0] - 0.0, z_blk + 0.1)))
    # --- crush ribs behind the reservoir rear face (axial preload of the fluid module, see params pod.res.rib_stop)
    rb = P["res"]["rib_stop"]
    for i, yy in enumerate((7.0, 12.4)):
        joins.append(s.box(f"t_crush{i}", (L["x_r0"] - rb["w"], L["x_r0"]), (yy - 0.8, yy + 0.8), (wall - 0.1, wall + rb["h"])))
    # --- cell bay ribs, board posts and pins, sensor board posts, spine shelf
    for i, rbk in enumerate(G["cell_ribs"]):
        yy = (rbk["y"][0], W - wall) if rbk["y"][0] > 25 else tuple(rbk["y"])
        joins.append(s.box(f"t_cribs{i}", tuple(rbk["x"]), yy, (wall - 0.1, wall + rbk["h"])))
    z0 = G["z0"]
    pn = P["pins"]
    for i, h in enumerate(G["board_holes_u"]):
        joins.append(s.cyl(f"t_bpost{i}", "Z", (xr + h[0], h[1], 0), pn["post_d"], wall - 0.1, z0))
        joins.append(s.cyl(f"t_bpin{i}", "Z", (xr + h[0], h[1], 0), pn["d"], z0 - 0.1, z0 + pn["h"] - 0.1))
    sn = G["sensor"]
    bz0 = sn["board"]["z"][0]
    for i, q in enumerate(sn["posts"]):
        joins.append(s.cyl(f"t_spost{i}", "Z", (q[0], q[1], 0), pn["post_d"], wall - 0.1, bz0))
        joins.append(s.cyl(f"t_spin{i}", "Z", (q[0], q[1], 0), pn["d"], bz0 - 0.1, bz0 + pn["h"] - 0.1))
    shf = G["spine"]["shelf"]
    joins.append(s.box("t_shelf", tuple(shf["x"]), tuple(shf["y"]), (wall - 0.1, shf["z_top"])))
    s.join("bottom", joins)
    # --- cuts: spine channel, USB opening, Velcro recess, fill-needle access hole, dock interface, mouth
    spn = G["spine"]
    cuts.append(s.box("t_chan", (spn["channel_x"][0], spn["channel_x"][1]), (spn["y"][0] - 0.2, spn["y"][1] + 0.2), (spn["channel_z0"], wall + 0.1)))
    u = G["usb"]
    cuts.append(s.box("t_usbopen", tuple(u["open_x"]), tuple(u["open_y"]), tuple(u["open_z"])))
    rh = P["drive"]["rear_plug_d"]
    cuts.append(s.cyl("t_screwhole", "X", (0, L["y_r"], zc), rh + 0.1, -0.1, wall + 0.1))      # the drive screw is inserted from the rear through this hole (assembly), then plugged
    cuts.append(s.box("t_screwslot", (-0.1, wall + 0.1), (L["y_r"] - rh / 2 - 0.05, L["y_r"] + rh / 2 + 0.05), (zc, sh["lap_high"] + 0.1)))    # open to the wall top (the gasket closes it)
    cuts.append(s.rrect("t_vel", (L["x_r0"] + vc["margin_x"], xr + p["dock"]["cover"]["x_end_u"]), (vc["y0"], vc["y1"]), vc["r"], (-0.1, vc["depth"])))
    cp = p["dock"]["cap"]
    cuts.append(s.cyl("t_fillacc", "Z", (xr + cp["septum_x"], L["dock"]["y_c"] - cp["septum_dy"], 0), cp["fill_hole_d"], -0.1, wall + 0.1))
    s.cut("bottom", cuts)
    s.cut("bottom", dcuts)
    s.join("bottom", bumps)                                  # detent bumps on the ledge (after the pocket cut), before the mouth cut
    s.cut("bottom", [s.box("t_kmoutha", (length - wall - 0.3, length + 0.1), (ym0, ym1), (-0.1, sh["lap_high"] + 0.1))])     # dock mouth through the end wall (the lid starts above the dome)


def build_gasket(s: Script, p: dict, L: dict) -> None:
    """Main gasket: 0.5 mm silicone ring on the wall top (flat joint), 0.75 mm wide; it runs unbroken over the dock mouth (the dome top is 0.5 mm lower)."""
    sh = p["shell"]
    length, W, r, wall = L["length"], L["width"], sh["corner_r"], L["wall"]
    z0 = sh["lap_high"]
    ri = 0.15
    s.rrect("gasket", (ri, length - ri), (ri, W - ri), r - ri, (z0 + 0.005, z0 + sh["gasket_c"] - 0.005))
    s.rrect("t_gin", (wall, length - wall), (wall, W - wall), r - wall, (z0 - 0.1, z0 + sh["gasket_c"] + 0.1))
    s.cut("gasket", ["t_gin"])


def build_top(s: Script, p: dict, L: dict) -> None:
    from op_dock import build_mouth_cut
    sh, sc, bn, pt, P = p["shell"], p["screws"], p["button"], p["port"], p["pod"]
    G = L["geo"]
    wall, length, W, r = L["wall"], L["length"], L["width"], sh["corner_r"]
    xr, zc = L["x_r1"], L["z_axis"]
    z_stop = sh["lap_high"] + sh["gasket_c"]
    zt = sh["height"]
    zi = zt - wall
    s.rrect("top", (0, length), (0, W), r, (z_stop, zt))
    if sh["top_fillet"] > 0:
        s.fillet_chain("top", (length / 2, 0.0, zt), sh["top_fillet"])
    s.rrect("t_lcb", (wall, length - wall), (wall, W - wall), r - wall, (z_stop - 0.1, zi))
    s.cut("top", ["t_lcb"])
    joins = []
    hl = sc["boss_d"] / 2 + 0.1
    for i, q in enumerate(L["screws"]):
        x0b, x1b = q["x"] - hl, q["x"] + hl
        if q["y"] < 10:
            yb = (0.5, q["y"] + hl)
        elif q["x"] < 4.0:
            x0b, yb = 0.5, (q["y"] - hl, q["y"] + hl)
        else:
            yb = (q["y"] - hl, W - 0.5)
        joins.append(s.box(f"t_lb{i}", (x0b, x1b), yb, (z_stop, zi + 0.1)))
    z_bt = G["ztop"]
    for i, (u, y) in enumerate(((6.0, 8.0), (18.6, 8.5), (13.0, 23.5))):          # board hold-down pads on bare board areas
        joins.append(s.cyl(f"t_hd{i}", "Z", (xr + u, y, 0), 1.2, z_bt + 0.05, zi + 0.1))
    mo = p["pod"]["motor"]["options"][p["pod"]["motor"]["option"]]
    joins.append(s.cyl("t_mpad", "Z", (L["x_gh1"] - 4.0, L["y_m"], 0), 1.6, zc + mo["d"] / 2 + 0.02, zi + 0.1))
    mc = G["motor_card"]
    joins.append(s.cyl("t_cpad", "Z", ((mc["x"][0] + mc["x"][1]) / 2, (mc["y"][0] + mc["y"][1]) / 2, 0), 1.0, mc["z"][1] + 0.05, zi + 0.1))
    sw = G["switch"]
    joins.append(s.cyl("t_btnpost", "Z", (sw["c"][0], sw["c"][1], 0), bn["post_d"], sw["z"][1] + bn["post_gap"], zi + 0.1))
    s.join("top", joins)
    cuts = []
    for i, q in enumerate(L["screws"]):
        cuts.append(s.cyl(f"t_lh{i}", "Z", (q["x"], q["y"], 0), sc["clear"], z_stop - 0.1, zt + 0.1))
        cuts.append(s.cyl(f"t_lc{i}", "Z", (q["x"], q["y"], 0), sc["head_d"], zt - sc["head_depth"], zt + 0.1))
    R = P["res"]
    rec = s.box("t_lrecess", (L["x_r0"] - 0.2, L["x_r1"] + 0.2), (L["res_y"][0] + 2.2, L["res_y"][1] - 2.2), (zi - 0.2, zc + L["res_h_out"] / 2 + R["lid_recess"]))
    cuts.append(rec)
    cuts.append(s.cyl("t_memb", "Z", (sw["c"][0], sw["c"][1], 0), bn["d_memb"], zt - (wall - bn["memb_t"]), zt + 0.1))
    px, py = G["piezo"]["port"]
    cuts.append(s.cyl("t_port", "Z", (px, py, 0), pt["hole_d"], zi - 0.1, zt + 0.1))
    cuts.append(s.cyl("t_prec", "Z", (px, py, 0), pt["recess_d"], zi - 0.1, zi + pt["recess_depth"]))
    vn = G["vent"]
    cuts.append(s.cyl("t_vent", "Z", (vn["c"][0], vn["c"][1], 0), vn["hole_d"], zi - 0.1, zt + 0.1))
    cuts.append(s.cyl("t_vrec", "Z", (vn["c"][0], vn["c"][1], 0), vn["recess_d"], zi - 0.1, zi + vn["recess_depth"]))
    # fill scale (clear lid, spec 2a): engraving 0.15 mm deep on the lid inner face above the plunger travel, tick every 10 U, long every 50 U (1 U = 10 mm3)
    mm10 = 100.0 / L["area"]
    ys_ = L["y_r"] + 9.0
    zr = zc + L["res_h_out"] / 2 + R["lid_recess"]
    eg = 0.15
    k = 0
    while k * mm10 <= L["stroke"] + 1e-6:
        x = L["xrear_full"] + k * mm10
        ln = 1.5 if k % 5 == 0 else 0.8
        cuts.append(s.box(f"t_tick{k}", (x - 0.25, x + 0.25), (ys_ - ln / 2, ys_ + ln / 2), (zr - 0.1, zr + eg)))
        k += 1
    cuts.append(s.box("t_tickbase", (L["xrear_full"], L["xrear_empty"] + 0.25), (ys_ - 0.25, ys_ + 0.25), (zr - 0.1, zr + eg)))
    gx0, gx1 = L["gear_x0"], L["gear_x1"]
    cuts.append(s.box("t_lgear", (gx0 - 0.3, L["x_r0"] - 0.1), (L["y_r"] - 3.6, L["y_r"] + 3.6), (zi - 0.2, zi + 0.25)))          # nut gear tip circle 6.6 > cavity height 6.6 - 0.05
    s.cut("top", cuts)
