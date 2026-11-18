"""Baut das OpenPatch-Modell als SolidCraft-Kommandoskript."""
from __future__ import annotations

from op_cmds import Script
from op_layout import compute_layout

PART_NAMES = ["bottom", "top", "reservoir", "plunger", "leadscrew", "motor", "gearhead",
              "gear_stage_a", "gear_stage_b", "battery", "pcb", "pcb_keepout", "qi_coil",
              "septum", "buzzer", "needle"]
# Paare, die sich konstruktiv berühren/überlappen dürfen (Bauteil sitzt im Keep-out)
EXCLUDE_PAIRS = [["buzzer", "pcb_keepout"]]


def _flatten(prefix: str, d: dict, out: list) -> None:
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict):
            _flatten(f"{prefix}{k}_", v, out)
        elif isinstance(v, (int, float)):
            out.append((f"{prefix}{k}", v))


def add_parameter_table(s: Script, p: dict, lay: dict) -> None:
    rows: list = []
    for key in ("shell", "fit", "velcro", "reservoir", "septum", "needle", "drive",
                "battery", "pcb", "coil", "buzzer", "cannula"):
        _flatten(f"p_{key}_", p[key], rows)
    rows.append(("p_stroke", lay["stroke"]))
    rows.append(("p_length", lay["length"]))
    for name, val in rows:
        s.parameter(name, val, "Generator-Wert (Info). Änderungen: params.json + generate.py")


def build_bottom(s: Script, p: dict, L: dict) -> None:
    sh, sp, nd, cn, vc = p["shell"], p["septum"], p["needle"], p["cannula"], p["velcro"]
    w, wd, r = L["length"], L["width"], sh["corner_r"]
    wall = sh["wall"]
    s.rrect("bottom", (0, w), (0, wd), r, (0, sh["lap_low"]))
    s.rrect("t_rim", (sh["rim_inset"], w - sh["rim_inset"]), (sh["rim_inset"], wd - sh["rim_inset"]),
            r - sh["rim_inset"], (sh["lap_low"] - 0.01, sh["lap_high"]))
    s.join("bottom", ["t_rim"])
    s.rrect("t_cav", (wall, w - wall), (wall, wd - wall), r - wall, (wall, sh["lap_high"] + 0.5))
    s.cut("bottom", ["t_cav"])

    # Kanülen-Turm (Aufnahmetasche) + Septum-Boss + Spindel-Lagerbock
    tx0 = L["x_r1"]
    s.box("t_tower", (tx0, tx0 + L["tower_x"]), (wall - 0.1, L["y_p"] + cn["B_plate_width"] / 2 + cn["N_clearance"] + 0.9),
          (wall - 0.1, nd["tower_top"]))
    s.cyl("t_boss", "Y", (L["x_s"], 0, sp["z"]), sp["boss_d"], wall - 0.1, L["y_r0"])
    post_x = (L["x_r0"], L["x_in0"] + 0.1)
    s.box("t_post", post_x, (L["y_s"] - 1.8, L["y_s"] + 1.8), (wall - 0.1, L["z_axis"] + 1.8))
    s.join("bottom", ["t_tower", "t_boss", "t_post"])

    # Schnitte
    cut = []
    ph = L["pocket_h"]
    px = cn["A_plate_length"] / 2 + cn["N_clearance"]
    py = cn["B_plate_width"] / 2 + cn["N_clearance"]
    cut.append(s.box("t_pocket", (L["x_p"] - px, L["x_p"] + px), (L["y_p"] - py, L["y_p"] + py), (-0.1, ph)))
    gy = cn["E_wing_len"] / 2
    gz = (cn["G_wing_z"], cn["G_wing_z"] + cn["F_wing_height"])
    cut.append(s.box("t_gr1", (L["x_p"] + px - 0.01, L["x_p"] + px + cn["D_wing_groove_depth"]),
                     (L["y_p"] - gy, L["y_p"] + gy), gz))
    cut.append(s.box("t_gr2", (L["x_p"] - px - cn["D_wing_groove_depth"], L["x_p"] - px + 0.01),
                     (L["y_p"] - gy, L["y_p"] + gy), gz))
    cut.append(s.cyl("t_nb", "Z", (L["x_n"], L["y_n"], 0), nd["bore_d"], ph - 0.1, nd["channel_z"] + 0.1))
    cut.append(s.cyl("t_nc", "X", (0, L["y_n"], nd["channel_z"]), nd["channel_d"], L["x_r1"] - 0.5, L["x_n"]))
    cut.append(s.cyl("t_sb", "Y", (L["x_s"], 0, sp["z"]), sp["d"] + 2 * sp["bore_clr"], -0.1, sp["len"] + 0.3))
    cut.append(s.cyl("t_sc", "Y", (L["x_s"], 0, sp["z"]), sp["port_d"], sp["len"] + 0.2, L["y_r0"] + 0.01))
    cut.append(s.cyl("t_pb", "X", (0, L["y_s"], L["z_axis"]), p["drive"]["post_bore_d"], post_x[0] - 0.1, post_x[1] + 0.1))
    cut.append(s.rrect("t_vel", (L["x_r0"] + vc["margin_x"], L["x_r1"] - 1.5), (vc["y0"], vc["y1"]), vc["r"],
                       (-0.1, vc["depth"])))
    s.cut("bottom", cut)


def build_top(s: Script, p: dict, L: dict) -> None:
    sh = p["shell"]
    w, wd, r, wall = L["length"], L["width"], sh["corner_r"], sh["wall"]
    s.rrect("top", (0, w), (0, wd), r, (sh["lap_low"], sh["height"]))
    if sh["top_fillet"] > 0:
        s.fillet_chain("top", (w / 2, 0.0, sh["height"]), sh["top_fillet"])
    ri = sh["lid_ring_inset"]
    s.rrect("t_lca", (ri, w - ri), (ri, wd - ri), r - ri, (sh["lap_low"] - 0.1, sh["lap_high"] + sh["lap_gap"]))
    s.rrect("t_lcb", (wall, w - wall), (wall, wd - wall), r - wall, (sh["lap_high"], sh["height"] - wall))
    s.cut("top", ["t_lca", "t_lcb"])


def build_reservoir_group(s: Script, p: dict, L: dict) -> None:
    rs, sp, nd, dr = p["reservoir"], p["septum"], p["needle"], p["drive"]
    zc = L["z_axis"]
    s.stadium("reservoir", (L["x_r0"], L["x_r1"]), L["y_r"], zc, L["res_w_out"], L["res_h_out"])
    s.stadium("t_chamber", (L["x_in0"], L["x_in1"]), L["y_r"], zc, rs["w_in"], rs["h_in"])
    tools = ["t_chamber"]
    tools.append(s.cyl("t_rport", "X", (0, L["y_n"], nd["channel_z"]), nd["channel_d"], L["x_r1"] - 0.9, L["x_r1"] + 0.1))
    tools.append(s.cyl("t_fport", "Y", (L["x_s"], 0, sp["z"]), sp["port_d"], L["y_r0"] - 0.1, L["y_r0"] + 1.5))
    slot_z = (zc - dr["arm_t"] / 2 - dr["slot_clr"], zc + dr["arm_t"] / 2 + dr["slot_clr"])
    y_in_max = L["y_r"] + rs["w_in"] / 2
    tools.append(s.box("t_slot", (L["x_in0"], L["x_in0"] + L["stroke"] + 1.7),
                       (y_in_max - 0.2, y_in_max + rs["wall"] + 0.3), slot_z))
    s.cut("reservoir", tools)

    # Kolben: Stadion-Kern + Arm durch den Schlitz + Mutterblock (Mutter M1.6, Gewinde nicht modelliert)
    c = rs["plunger_clr"]
    xr = L["xrear"]
    s.stadium("plunger", (xr, xr + rs["plunger_len"]), L["y_r"], zc, rs["w_in"] - 2 * c, rs["h_in"] - 2 * c)
    nb, nl = dr["nut_block"], dr["nut_len"]
    arm = s.box("t_arm", (xr, xr + nl), (y_in_max - 0.4, L["y_s"]), (zc - dr["arm_t"] / 2, zc + dr["arm_t"] / 2))
    blk = s.box("t_nut", (xr, xr + nl), (L["y_s"] - nb / 2, L["y_s"] + nb / 2), (zc - nb / 2, zc + nb / 2))
    s.join("plunger", [arm, blk])
    hole = s.cyl("t_nhole", "X", (0, L["y_s"], zc), dr["nut_hole_d"], xr - 0.1, xr + nl + 0.1)
    s.cut("plunger", [hole])

    # Spindel (Gewinde nicht modelliert) neben dem Reservoir, im Kolbenarm-Mutterblock geführt
    x_tip = L["xrear_empty"] + nl - 0.1
    s.cyl("leadscrew", "X", (0, L["y_s"], zc), dr["screw_d"], L["gear_x1"], x_tip)


def build_drive(s: Script, p: dict, L: dict) -> None:
    dr = p["drive"]
    zc = L["z_axis"]
    gx0 = dr["gear_x0"]
    mx0 = L["gear_x1"] + p["fit"]["clr_small"]
    s.cyl("gearhead", "X", (0, L["y_m"], zc), dr["motor_d"], mx0, mx0 + dr["gearhead_len"])
    s.cyl("motor", "X", (0, L["y_m"], zc), dr["motor_d"], mx0 + dr["gearhead_len"],
          mx0 + dr["gearhead_len"] + dr["motor_len"])
    s.cyl("gear_stage_a", "X", (0, L["y_m"], zc), dr["gear_d"], gx0, L["gear_x1"])
    s.cyl("gear_stage_b", "X", (0, L["y_s"], zc), dr["gear_d"], gx0, L["gear_x1"])


def build_electronics(s: Script, p: dict, L: dict) -> None:
    bt, pc, co, bz, sp, nd, fit = (p["battery"], p["pcb"], p["coil"], p["buzzer"], p["septum"],
                                  p["needle"], p["fit"])
    wall, x_end, yi1 = L["wall"], L["x_end"], L["yi1"]
    m = bt["margin"]
    bz0 = wall + fit["bat_gap"]
    s.rrect("battery", (L["x_r1"] + m, L["x_r1"] + m + L["bat_x"]), (yi1 - m - bt["y"], yi1 - m),
            p["shell"]["corner_r"] - wall - m, (bz0, bz0 + bt["t"]))
    pm = pc["margin"]
    px = (L["x_r1"] + co["gap_x"], x_end - pm)
    py = (wall + pm, yi1 - pm)
    rr = p["shell"]["corner_r"] - wall - pm
    for name, z in (("pcb", (pc["z0"], pc["z0"] + pc["t"])),
                    ("pcb_keepout", (pc["z0"] + pc["t"], pc["z0"] + pc["t"] + pc["keepout"]))):
        s.rrect(name, px, py, rr, z)
        notch = s.box(f"t_notch_{name}", (px[0] - 0.1, L["x_r1"] + pc["notch_x"] + sp_boss_half(p)),
                      (py[0] - 0.1, wall + pc["notch_y"] + 0.4), (z[0] - 0.1, z[1] + 0.1))
        s.cut(name, [notch])
    s.cyl("qi_coil", "Z", (L["coil_cx"], L["coil_cy"], 0), co["d"], co["z0"], co["z0"] + co["t"])
    bx1 = x_end - bz["edge_gap"]
    s.box("buzzer", (bx1 - bz["x"], bx1), (bz["y0"], bz["y0"] + bz["y"]),
          (pc["z0"] + pc["t"], pc["z0"] + pc["t"] + bz["z"]))
    sz = sp["z"]
    s.cyl("septum", "Y", (L["x_s"], 0, sz), sp["d"], sp["recess"], sp["recess"] + sp["len"])
    s.cyl("needle", "Z", (L["x_n"], L["y_n"], 0), nd["od"], L["z_tip"], nd["channel_z"])


def sp_boss_half(p: dict) -> float:
    """Halbe Boss-Ausdehnung in +X über x_r1 hinaus (für PCB-Notch)."""
    return p["septum"]["boss_d"] / 2 - 0.6 + 0.0


def build_model(p: dict, variant: str) -> tuple[Script, dict]:
    L = compute_layout(p, variant)
    s = Script()
    add_parameter_table(s, p, L)
    build_bottom(s, p, L)
    build_top(s, p, L)
    build_reservoir_group(s, p, L)
    build_drive(s, p, L)
    build_electronics(s, p, L)
    return s, L
