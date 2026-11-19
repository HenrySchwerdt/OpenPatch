"""Fluid module = clamped two-part SANDWICH (microfluidic-manifold style), replaces the pressed-on end cap with blind pockets.

Split plane z = z_port (the reservoir port axis).  Parts, bottom to top:
  end_cap       lower half (printed): spigot half-pin, gasket recess, valve / septum pockets open from the top, shroud tube + hub bore, via and plenum
  cap_gasket    0.5 mm silicone sheet (plotter / punch cut): the CHANNELS are slots in this sheet (width slot_w), so every channel is an open slot while the
                module is open (inspectable, flushable, no blind d0.6 holes); recess 0.4 deep in the base -> 0.1 proud -> 20 % squeeze set by the lands
  end_cap_lid   upper half: flat underside on the lands, ceiling recesses that set the compression of the dropped-in valve and septum, O-ring half groove,
                spigot half pin, two M1.2 clamp screws
Soft parts are DROPPED into open pockets (O-ring, valve / check cartridge, septum disc, gasket); the halves close on hard lands, so every squeeze is
fixed by geometry and not by print tolerance.  Everything is parametric (params.json -> dock.cap, coax.valve_*): the duckbill pocket takes a cylindrical
check-valve cartridge (OD / length), the septum pocket a bought septum / port (disc d, thickness), the needle mount a hubbed (hub bore) or bare needle.
Needle hub: still pressed into the shroud bore from the front (hub_press), UV-bonded needle in a jig (see SEAL-AND-DEAD-VOLUME.md).

Channel network (all in the gasket slot layer z = z_port, slot width slot_w, height gasket.t):
  port (spigot half-grooves d prime_d) -> junction cell at x_jog -> via down to the valve plenum;  junction -> leg1 (-Y, lane_off) -> leg2 (+X to the septum x)
  -> leg3 (-Y to the septum cavity face): the fill branch, upstream of the valve.  Valve outlet -> d prime_d bore -> hub bore -> needle.
"""
from __future__ import annotations

from op_cmds import Script


def cap_geometry(p: dict, L: dict) -> dict:
    dk, cp, D = p["dock"], p["dock"]["cap"], L["dock"]
    xr = L["x_r1"]
    sw = cp["sandwich"]
    zs = L["z_axis"]
    return {"x_block": [xr, xr + dk["block_len"]], "y_block": [cp["block_y0"], D["y_c"] + cp["block_up_y"]],
            "z_block": [L["wall"], D["z_n"] + cp.get("block_up", dk["block_up"])], "z_split": zs,
            "x_jog": xr + cp["jog_x"], "x_sept": xr + cp["septum_x"],
            "valve_x": [xr + dk["valve_x0"], xr + dk["valve_x0"] + p["coax"]["valve_len"]], "z_port": zs, "sandwich": sw}


def oring_squeeze(p: dict) -> dict:
    og = p["dock"]["cap"]["oring"]
    stretch = og["groove_inner_d"] / og["id"]
    cs_eff = og["cs"] * (1.0 / stretch) ** 0.5            # constant-volume ring: cross-section shrinks with stretch
    return {"stretch": stretch - 1.0, "cs_eff": cs_eff, "squeeze": (cs_eff - og["groove_depth"]) / cs_eff}


def _half(s: Script, name: str, cyl_args: tuple, xlim: tuple, ylim: tuple, zlim: tuple) -> str:
    """Cylinder ∩ box (lower or upper half of a pin)."""
    s.cyl(name, *cyl_args)
    s.box(name + "_hb", xlim, ylim, zlim)
    s.add("solid.combine", target=name, tools=[name + "_hb"], operation="intersect", name=f"half {name}")
    return name


def build_cap(s: Script, p: dict, L: dict) -> dict:
    nd, cn, dk, cp, D, cx = p["needle"], p["cannula"], p["dock"], p["dock"]["cap"], L["dock"], p["coax"]
    sw = cp["sandwich"]
    G = cap_geometry(p, L)
    xr, yc, zn, zp = L["x_r1"], D["y_c"], D["z_n"], G["z_port"]
    zs = G["z_split"]
    x0, x1 = G["x_block"]
    y0, y1 = G["y_block"]
    z0, zt = G["z_block"]
    ws, gt, rec = sw["slot_w"], sw["gasket"]["t"], sw["gasket"]["recess"]
    gx0, gx1, gm = sw["gasket"]["x"][0], sw["gasket"]["x"][1], sw["gasket"]["y_margin"]
    og = cp["oring"]
    dp = cp["prime_d"]
    ya = yc - cp["lane_off"]
    sd = sw["septum"]["depth"]
    vd, vlen, vx0 = cx["valve_d"], cx["valve_len"], dk["valve_x0"]
    vcomp, vfl = sw["valve"]["compress"], sw["valve"]["float"]
    scomp, sfl, sdia = sw["septum"]["compress"], sw["septum"]["float"], p["septum"]["d"]
    jx = cp["jog_x"]
    xs = cp["septum_x"]
    nsh = 2.8                                           # pilot depth of the clamp screws
    gy1 = yc + sw["gasket"]["y_max_rel"]                # the gasket stays south of the screw-A land
    nb_y, nh = sw["screws"]["pos"][1][1], sw["screws"]["notch_half"]
    # ------------------------------------------------------------------ base
    s.box("end_cap", (x0, x1), (y0, y1), (z0, zs))
    j = [_half(s, "t_spg_l", ("X", (0, yc, zp), cp["spigot_d"], xr - cp["spigot_len"], xr + 0.01), (xr - cp["spigot_len"] - 0.1, xr + 0.1), (yc - 2, yc + 2), (zp - 2, zs)),
         s.cyl("t_cap_shroud", "X", (0, yc, zn), cn["O_cyl_od"], x1 - 0.05, D["shroud_end"])]
    s.join("end_cap", j)
    s.tube("t_og_b", "X", (0, yc, zp), og["groove_inner_d"] + 2 * og["groove_w"], og["groove_inner_d"], xr - 0.1, xr + og["groove_depth"])
    cuts = [
        "t_og_b",
        s.box("t_g_rec_a", (xr + gx0, xr + 2.85), (y0 + gm, gy1), (zs - rec, zs + 0.1)),                               # gasket recess (0.4 deep), west part
        s.box("t_g_rec_b", (xr + 2.85, xr + gx1), (y0 + gm, yc + nb_y - nh), (zs - rec, zs + 0.1)),                    # east part below the screw-B land
        s.box("t_g_rec_c", (xr + 2.85, xr + gx1), (yc + nb_y + nh, gy1), (zs - rec, zs + 0.1)),                        # east part above the screw-B land
        s.cyl("t_cap_p", "X", (0, yc, zp), dp, xr - cp["spigot_len"] - 0.1, xr + gx0 + 0.1),                          # port channel (half groove in the spigot)
        s.cyl("t_cap_via", "Z", (xr + jx, yc, 0), sw["via_d"], zn - 0.3, zs - rec + 0.1),                             # via: slot layer -> valve plenum
        s.cyl("t_cap_plen", "X", (0, yc, zn), sw["plenum_d"], xr + jx - 0.4, xr + vx0 + 0.05),                        # valve inlet plenum
        s.box("t_cap_vp", (xr + vx0, xr + vx0 + vlen), (yc - vd / 2 - vfl, yc + vd / 2 + vfl), (zn - vd / 2 * (1 - vcomp), zs + 0.05)),   # valve pocket (open top)
        s.cyl("t_cap_vo", "X", (0, yc, zn), dp, xr + vx0 + vlen - 0.1, D["x_h0"] + 0.1),                              # valve outlet -> hub bore
        s.cyl("t_cap_hb", "X", (0, yc, zn), dk["hub_d"] - cp["hub_press"], D["x_h0"], D["shroud_end"] + 0.1),         # hub press fit
        s.box("t_cap_sp", (xr + xs - (sdia + sfl) / 2, xr + xs + (sdia + sfl) / 2), (y0 - 0.1, y0 + sd), (zn - sdia / 2 * (1 - scomp), zs + 0.05)),  # septum pocket (open top)
    ]
    for k, (sx, sy) in enumerate(sw["screws"]["pos"]):
        cuts.append(s.cyl(f"t_cap_pil{k}", "Z", (xr + sx, yc + sy, 0), sw["screws"]["pilot"], zs - nsh, zs + 0.1))
    s.cut("end_cap", cuts)
    # ------------------------------------------------------------------ lid
    s.box("end_cap_lid", (x0, x1), (y0, y1), (zs, zt))
    s.join("end_cap_lid", [_half(s, "t_spg_u", ("X", (0, yc, zp), cp["spigot_d"], xr - cp["spigot_len"], xr + 0.01), (xr - cp["spigot_len"] - 0.1, xr + 0.1), (yc - 2, yc + 2), (zs, zp + 2))])
    s.tube("t_og_u", "X", (0, yc, zp), og["groove_inner_d"] + 2 * og["groove_w"], og["groove_inner_d"], xr - 0.1, xr + og["groove_depth"])
    lcuts = [
        "t_og_u",
        s.cyl("t_cap_pu", "X", (0, yc, zp), dp, xr - cp["spigot_len"] - 0.1, xr + gx0 + 0.1),
        s.box("t_cap_vc", (xr + vx0, xr + vx0 + vlen), (yc - vd / 2 - vfl, yc + vd / 2 + vfl), (zs - 0.05, zn + vd / 2 * (1 - vcomp))),   # valve ceiling (sets the squeeze)
        s.box("t_cap_sc", (xr + xs - (sdia + sfl) / 2, xr + xs + (sdia + sfl) / 2), (y0 - 0.1, y0 + sd), (zs - 0.05, zn + sdia / 2 * (1 - scomp))),  # septum ceiling
    ]
    sc = sw["screws"]
    for k, (sx, sy) in enumerate(sc["pos"]):
        lcuts.append(s.cyl(f"t_cap_cl{k}", "Z", (xr + sx, yc + sy, 0), sc["clear"], zs - 0.1, zt + 0.1))
        lcuts.append(s.cyl(f"t_cap_hd{k}", "Z", (xr + sx, yc + sy, 0), sc["head_d"], zt - sc["head_depth"], zt + 0.1))
    s.cut("end_cap_lid", lcuts)
    # ------------------------------------------------------------------ gasket (silicone sheet, channels = slots)
    s.box("cap_gasket", (xr + gx0, xr + gx1), (y0 + gm, gy1), (zs - rec, zs - rec + gt))
    gc = [
        s.box("t_gs_p", (xr + gx0 - 0.1, xr + jx + ws / 2), (yc - ws / 2, yc + ws / 2), (zs - 1, zs + 1)),                      # port slot
        s.box("t_gs_1", (xr + jx - ws / 2, xr + jx + ws / 2), (ya - ws / 2, yc + ws / 2), (zs - 1, zs + 1)),                    # leg 1 (junction -> lane)
        s.box("t_gs_2", (xr + jx - ws / 2, xr + xs + ws / 2), (ya - ws / 2, ya + ws / 2), (zs - 1, zs + 1)),                    # leg 2 (lane -> septum x)
        s.box("t_gs_3", (xr + xs - ws / 2, xr + xs + ws / 2), (y0 + sd - 0.1, ya + ws / 2), (zs - 1, zs + 1)),                  # leg 3 (-> septum cavity)
        s.box("t_gs_v", (xr + vx0, xr + vx0 + vlen), (yc - vd / 2 - vfl, yc + vd / 2 + vfl), (zs - 1, zs + 1)),                  # valve pocket opening
        s.box("t_gs_s", (xr + xs - (sdia + sfl) / 2, xr + xs + (sdia + sfl) / 2), (y0 - 0.1, y0 + sd), (zs - 1, zs + 1)),        # septum pocket opening
    ]
    gc.append(s.box("t_gs_notch", (xr + 2.85, xr + gx1 + 0.1), (yc + nb_y - nh, yc + nb_y + nh), (zs - 1, zs + 1)))      # land for clamp screw B
    s.cut("cap_gasket", gc)
    return G


def build_oring(s: Script, p: dict, L: dict) -> None:
    """The face O-ring in assembly state (axial squeeze overlaps the reservoir end face by design: interference exclude pair)."""
    og = p["dock"]["cap"]["oring"]
    G = cap_geometry(p, L)
    q = oring_squeeze(p)
    xr = G["x_block"][0]
    D = L["dock"]
    s.tube("cap_oring", "X", (0, D["y_c"], G["z_port"]), og["groove_inner_d"] + 2 * q["cs_eff"], og["groove_inner_d"], xr - (q["cs_eff"] - og["groove_depth"]), xr + og["groove_depth"])


def cap_interfaces(p: dict, L: dict) -> list[dict]:
    """Every sealing interface of the wetted module: gap (mm, > 0 clearance, 0 touching, < 0 interference / compression) and the seal element that closes it."""
    fz, cp, sp, dk = p["reservoir_frozen"], p["dock"]["cap"], p["septum"], p["dock"]
    sw = cp["sandwich"]
    og = cp.get("oring")
    q = oring_squeeze(p) if og else None
    seal_o = ("face O-ring %.1f x %.1f in the clamped halves, axial squeeze %.0f %%" % (og["id"], og["cs"], 100 * q["squeeze"])) if og else None
    gk = sw["gasket"]
    gsq = (gk["t"] - gk["recess"]) / gk["t"]
    vd = p["coax"]["valve_d"]
    vgap = -vd * sw["valve"]["compress"]
    return [
        {"name": "cap spigot d%.2f in reservoir port d%.2f H7 (locating only)" % (cp["spigot_d"], fz["port_d"]), "gap": fz["port_d"] - cp["spigot_d"], "seal": seal_o, "squeeze": q["squeeze"] if q else None},
        {"name": "module rear face on the reservoir end face", "gap": 0.0, "seal": seal_o, "squeeze": q["squeeze"] if q else None},
        {"name": "base / lid split plane (channels)", "gap": 0.0, "seal": "silicone sheet gasket %.1f mm, %.0f %% squeeze on hard lands" % (gk["t"], 100 * gsq), "squeeze": gsq},
        {"name": "septum disc d%.1f in its pocket" % sp["d"], "gap": -sp["d"] * sw["septum"]["compress"], "seal": "%.0f %% compression set by the lid ceiling" % (100 * sw["septum"]["compress"]), "squeeze": sw["septum"]["compress"]},
        {"name": "check valve / cartridge d%.1f in its pocket" % vd, "gap": vgap, "seal": "%.0f %% compression set by the lid ceiling" % (100 * sw["valve"]["compress"]), "squeeze": None},
        {"name": "needle hub in shroud bore", "gap": -cp.get("hub_press", 0.0) / 2 if cp.get("hub_press") else dk["hub_clr"],
         "seal": "press fit %.2f per side" % (cp["hub_press"] / 2) if cp.get("hub_press") else None, "squeeze": None},
    ]
