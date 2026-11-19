"""Reservoir, Kolben (Kern + Dichtlippen), Schlitten, Antrieb, Spindel, Lager."""
from __future__ import annotations

from op_cmds import Script


def build_reservoir(s: Script, p: dict, L: dict, name: str = "reservoir") -> None:
    rs, sp, nd, dr, sl = p["reservoir"], p["septum"], p["needle"], p["drive"], p["seal"]
    zc = L["z_axis"]
    s.stadium(name, (L["x_r0"], L["x_r1"]), L["y_r"], zc, L["res_w_out"], L["res_h_out"])
    # Kammer: trockenes Ende offen (Kolben wird von hinten eingesetzt)
    s.stadium("t_chamber", (L["x_r0"] - 0.1, L["x_in1"]), L["y_r"], zc, rs["w_in"], rs["h_in"])
    tools = ["t_chamber"]
    if L["mode"] == "bench":     # frozen CNC interface: ONE press bore d2.0 H7 at the centre of the closed end, no fill port
        fz = p["reservoir_frozen"]
        tools.append(s.cyl("t_rport", "X", (0, L["y_r"], zc), fz["port_d"], L["x_in1"] - 0.1, L["x_r1"] + 0.1))
    else:
        tools.append(s.cyl("t_rport", "X", (0, L["y_n"], nd["channel_z"]), nd["channel_d"], L["x_r1"] - 0.9, L["x_r1"] + 0.1))
        tools.append(s.cyl("t_fport", "Y", (L["x_s"], 0, sp["z"]), sp["port_d"], L["y_r0"] - 0.1, L["y_r0"] + 1.5))
    slot_z = (zc - dr["arm_t"] / 2 - dr["slot_clr"], zc + dr["arm_t"] / 2 + dr["slot_clr"])
    y_in_max = L["y_r"] + rs["w_in"] / 2
    to = sl["tongue_off"]
    tools.append(s.box("t_slot", (L["xrear_full"] + to[0] - 0.2, L["xrear_empty"] + to[1] + 0.2),
                       (y_in_max - 0.2, y_in_max + rs["wall"] + 0.3), slot_z))
    s.cut(name, tools)


def build_plunger(s: Script, p: dict, L: dict) -> None:
    """Plunger core (printed) + cast silicone bead seal(s) in assembly state.  See SEAL-AND-DEAD-VOLUME.md."""
    from op_seal import bead_bodies, ring_range, variant
    rs, dr, sl = p["reservoir"], p["drive"], p["seal"]
    zc, yr, xr = L["z_axis"], L["y_r"], L["xrear"]
    c = rs["plunger_clr"]
    wc, hc = rs["w_in"] - 2 * c, rs["h_in"] - 2 * c
    gd = sl["groove_depth"]
    xf = xr + rs["plunger_len"]                       # front face of the core (dead layer = rs.dead in front of it at the stop)
    s.stadium("plunger_core", (xr, xf), yr, zc, wc, hc)
    tools = []
    for k, (a, b) in enumerate((sl["ring_a"], sl["ring_b"])):
        s.stadium_ring(f"t_gr{k}", (xr + a, xr + b), yr, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
        tools.append(f"t_gr{k}")
    sx = sl["socket_x"]
    y_end = yr + wc / 2
    tools.append(s.box("t_sock", (xr + sx[0], xr + sx[1]), (y_end - sl["socket_depth"], y_end + 0.1),
                       (zc - dr["arm_t"] / 2 - 0.05, zc + dr["arm_t"] / 2 + 0.05)))
    pg = sl["purge"]          # purge grooves in the front face: long-axis groove, cross groove, centre spot (flow path to the port, no air pockets)
    x0g = xf - pg["groove_d"]
    tools.append(s.box("t_pg_y", (x0g, xf + 0.1), (yr - wc / 2 - 0.1, yr + wc / 2 + 0.1), (zc - pg["groove_w"] / 2, zc + pg["groove_w"] / 2)))
    tools.append(s.box("t_pg_z", (x0g, xf + 0.1), (yr - pg["groove_w"] / 2, yr + pg["groove_w"] / 2), (zc - hc / 2 - 0.1, zc + hc / 2 + 0.1)))
    tools.append(s.cyl("t_pg_c", "X", (0, yr, zc), pg["centre_d"], x0g, xf + 0.1))
    s.cut("plunger_core", tools)
    if L["mode"] == "bench" and rs.get("nose_len", 0) > 0:      # legacy separate printed nose (nose_len = 0 since the seal study)
        s.stadium("plunger_nose", (xf, xf + rs["nose_len"]), yr, zc, wc, hc)
    # cast silicone beads (assembly state: land at bore - assembly_gap; cast size is bigger, see op_mould.py)
    v = variant(p)
    ao = sl["assembly_gap"]
    for which in v["rings"]:
        nm = "seal_" + which
        a, b = ring_range(p, which)
        parts = bead_bodies(s, nm, xr + a, xr + b, yr, zc, wc, hc, rs["w_in"] - ao, rs["h_in"] - ao, v["land"])
        s.join(nm, parts[1:])
        s.stadium(f"t_{nm}_floor", (xr + a - 0.1, xr + b + 0.1), yr, zc, wc - 2 * gd, hc - 2 * gd)
        s.cut(nm, [f"t_{nm}_floor"])


def build_carriage(s: Script, p: dict, L: dict) -> None:
    dr, sl = p["drive"], p["seal"]
    zc, ys, xr = L["z_axis"], L["y_s"], L["xrear"]
    bw, bh, cl = dr["carriage_bw"], dr["carriage_bh"], dr["carriage_len"]
    s.box("carriage", (xr, xr + cl), (ys - bw / 2, ys + bw / 2), (zc - bh / 2, zc + bh / 2))
    to = sl["tongue_off"]
    y_end = L["y_r"] + (p["reservoir"]["w_in"] - 2 * p["reservoir"]["plunger_clr"]) / 2
    sh = p["bench"]["shim"] if L["mode"] == "bench" else None
    if sh is None:      # integrated variant: printed tongue
        tongue = s.box("t_tongue", (xr + to[0], xr + to[1]), (y_end - sl["socket_depth"] + 0.1, ys - bw / 2 + 0.2),
                       (zc - dr["arm_t"] / 2, zc + dr["arm_t"] / 2))
        s.join("carriage", [tongue])
    apo = (dr["nut_af"] + dr["nut_hex_clr"]) / 2
    cuts = [s.cyl("t_chole", "X", (0, ys, zc), 1.9, xr - 0.1, xr + cl + 0.1),
            s.hexprism("t_hexp", (xr - 0.1, xr + dr["nut_len"] + 0.1), ys, zc, apo, angle=0.0),
            s.box("t_groove", (xr - 0.1, xr + cl + 0.1), (ys - dr["groove_w"] / 2, ys + dr["groove_w"] / 2),
                  (zc - bh / 2 - 0.1, zc - bh / 2 + dr["groove_d"]))]
    if sh is not None:      # pocket for the stainless tongue shim (open towards the reservoir)
        xm = xr + (to[0] + to[1]) / 2
        cuts.append(s.box("t_shimpocket", (xm - sh["t"] / 2 - sh["clr"], xm + sh["t"] / 2 + sh["clr"]), (ys - bw / 2 - 0.1, ys - bw / 2 + sh["pocket_depth"]),
                          (zc - sh["h"] / 2 - sh["clr"], zc + sh["h"] / 2 + sh["clr"])))
    s.cut("carriage", cuts)
    if sh is not None:
        s.box("tongue_shim", (xm - sh["t"] / 2, xm + sh["t"] / 2), (y_end - sl["socket_depth"] + 0.1, ys - bw / 2 + sh["pocket_depth"] - 0.1),
              (zc - sh["h"] / 2, zc + sh["h"] / 2))
    # M1.6-Mutter (DIN 934), Kauf
    s.hexprism("nut", (xr + 0.05, xr + 0.05 + dr["nut_len"]), ys, zc, dr["nut_af"] / 2, angle=0.0)
    s.cyl("t_nbore", "X", (0, ys, zc), dr["screw_d"] + 0.05, xr - 0.1, xr + 2.0)
    s.cut("nut", ["t_nbore"])


def build_drive(s: Script, p: dict, L: dict) -> None:
    if L["mode"] == "bench" and L["coax"]:
        from op_coax import build_coax_parts
        return build_coax_parts(s, p, L)
    dr = p["drive"]
    zc, ys, ym = L["z_axis"], L["y_s"], L["y_m"]
    gx0 = L["gear_x0"]
    s.cyl("gearhead", "X", (0, ym, zc), dr["motor_d"], L["gh_x"][0], L["gh_x"][1])
    s.cyl("motor", "X", (0, ym, zc), dr["motor_d"], L["mo_x"][0], L["mo_x"][1])
    # Zahnräder (Modul 0.3, z=18) als Fußkreis modelliert (Kopfkreis Ø6.0)
    s.cyl("gear_a", "X", (0, ym, zc), L["gears"]["tip_motor"], gx0, L["gear_x1"])   # tip envelope (meshes with gear_b: see EXCLUDE pair)
    if L["nfp"]:                                   # D-shaft bore (flat modelled as a plain bore d2.04)
        s.cyl("t_gab", "X", (0, ym, zc), dr["shaft_d"] + 0.04, gx0 - 0.1, L["gear_x1"] + 0.1)
        s.cut("gear_a", ["t_gab"])
    s.cyl("gear_b", "X", (0, ys, zc), L["gears"]["tip_screw"], gx0, L["gear_x1"])
    s.cyl("t_gbb", "X", (0, ys, zc), dr["screw_d"] + 0.04, gx0 - 0.1, L["gear_x1"] + 0.1)
    s.cut("gear_b", ["t_gbb"])
    s.cyl("leadscrew", "X", (0, ys, zc), dr["screw_d"], L["dry_bush"][0] + 0.1, L["screw_tip"])
    s.tube("bush_dry", "X", (0, ys, zc), dr["bush_od"], dr["bush_id"], L["dry_bush"][0], L["dry_bush"][1])
    s.tube("bush_far", "X", (0, ys, zc), dr["bush_od"], dr["bush_id"], L["far_bush"][0], L["far_bush"][1])
    s.cyl("magnet", "X", (0, ys, zc), dr["mag_d"], L["mag_x"][0], L["mag_x"][1])
    if L["nfp"]:
        x_boss0 = L["mx0"] - dr["boss_front"]
        s.cyl("motor_boss", "X", (0, ym, zc), dr["boss_d"], x_boss0, L["mx0"])
        s.cyl("motor_shaft", "X", (0, ym, zc), dr["shaft_d"], max(dr["shaft_cut_x"], gx0 - 0.2), x_boss0)
        s.cyl("motor_rear_boss", "X", (0, ym, zc), dr["rear_boss_d"], L["mo_x"][1], L["mot_end"])
        n = L["nfp_term"]
        s.box("motor_term", tuple(n["block_x"]), tuple(n["block_y"]), tuple(n["block_z"]))
        s.box("motor_pins", tuple(n["pins_x"]), tuple(n["pins_y"]), tuple(n["pins_z"]))
