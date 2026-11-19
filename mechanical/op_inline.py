"""Optional sealed bench drive `--drive inline` ("cup" drive): leadscrew ON the reservoir axis, nut in the plunger, closed reservoir.

Why: the side carriage + tongue needs a slot in the reservoir wall that spans the wetted zone (leaks at a full reservoir).  Here the reservoir is a closed
stadium bore with ONE opening (the dry rear end) and the port.  The only moving seal is the plunger lip seals (S2 seal unchanged).

Kinematics (all dimensions from params.json + the constants below; nothing of the default pod is changed):
  * motor + gear z16 (unchanged, beside the reservoir) -> gear_b z20 on the OLD lane axis y_s (now only an ENCODER shaft: M1.6 rod, far bush,
    collar, spindle magnet under the existing sensor board, exactly as before) -> idler gear_c z17 on a fixed pin (y_c = (y_s + y_r) / 2)
    -> gear_d z20 on the reservoir axis y_r.  gear_b -> gear_d ratio is exactly 1:1, so one encoder revolution = one screw revolution and the
    firmware drive preset (g16-20) is unchanged.
  * gear_d turns the drive screw (M1.6 x 0.35 rod, axially fixed: thrust sleeve on the dry bush face).  The screw enters the plunger from the rear.
  * plunger = stadium rear plate (holds the DIN 934 nut, keyed by the stadium bore = anti-rotation) + thin tube (hypodermic 13G, od 2.4 / id 1.8)
    + piston (printed core, 2 cast lip rings = S2 seal, 0.7 nose).  The tube is a DRY cup that swallows the screw: the screw never touches fluid.
  * Length cost: the dry cup is as long as the stroke, so the reservoir is ~one stroke longer (physics: see studies/drive/SEALED-DRIVE-STUDY.md).
"""
from __future__ import annotations

import math

CUP_EXTRA = 3.6          # cup length = stroke + CUP_EXTRA (plate 3.0 + nut engagement margin + piston front wall, see cup_geometry)
GEAR_X0 = 4.0            # gear plane start: lid screw bosses (x 0.9..3.1) must stay behind the gears
IDLER_Z = 17             # GHW module 0.3 idler (z17; z18 + z18 nut gear is the alternative with ratio 1.125)
NUT_GEAR_Z = 20
DRY_Y_SIDE = [4.2, 7.4, 27.8]      # lid screws at the dry end: clear of the three bearing blocks (y 9.1..13.3, 15.4..18.4, 20.4..24.6)
TUBE_OD, TUBE_ID = 2.4, 1.8        # hypodermic 13G stainless tube
SOCKET_D, SOCKET_DEPTH = 2.5, 3.0  # piston socket for the tube
PLATE_T, PLATE_POCKET, PLATE_CBORE_D, PLATE_CBORE = 3.0, 1.4, 2.5, 0.8
SCREW_HOLE_D = 1.9
TIP_BEYOND_NUT = 1.0     # screw tip beyond the nut front face at empty (engaged thread >= nut 1.3 + 1.0)
TIP_CLEAR = 0.4          # screw tip to the bottom of the piston socket at full
INLINE_EXCLUDE = [["gear_b", "gear_c"], ["gear_c", "gear_d"], ["gear_a", "gear_b"]]
LEN_MARGIN = 0.3


def cup_len(stroke: float) -> float:
    return stroke + CUP_EXTRA


# ---- "coaxial" variant (--drive coaxial): translating M1.6 screw through a ROTATING nut glued to the front face of gear_d (Omnipod style: the screw on the bore axis
# pushes the plunger centre; the tail of the screw lives behind the gear plane, the gear / sleeve / bush stack overlaps the tail so the rear zone is only s + 3.0 long).
# Anti-rotation of the screw: slot (hacksaw) across the screw tip engaging a tab in the plunger socket; the stadium bore keeps the plunger from turning.
COAX_NF_EXTRA = 3.0          # nut front face x = stroke + 3.0  (screw rear end at full x 1.2, engaged >= nut 1.3 + 0.5 at empty)
COAX_CLR = 0.52              # fit.clr_small: gear front face -> nut 1.32 -> 0.2 gap -> plunger rear at x_r0 + 1.0
NUT_THICK = 1.3
NUT_GLUE = 0.02
COAX_SOCKET = 2.0            # plunger socket depth (screw tip contact at the bottom)
COAX_TAB_T, COAX_SLOT_T, COAX_TAB_LEN = 0.3, 0.4, 1.0
COAX_SCREW_REAR = 1.2


def coax_gear_x1(stroke: float) -> float:
    return stroke + COAX_NF_EXTRA - (NUT_THICK + NUT_GLUE)


def mode_of(p: dict) -> str:
    return p.get("drive_mode", "inline")


def predicted_x_r1(p: dict, stroke: float) -> float:
    rs, dr = p["reservoir"], p["drive"]
    if mode_of(p) == "coaxial":
        x_r0 = coax_gear_x1(stroke) + COAX_CLR
        lin = rs["dead"] + stroke + 3.8 + rs["plunger_gap"]
    else:
        x_r0 = GEAR_X0 + dr["gear_t"] + p["fit"]["clr_small"]
        lin = rs["dead"] + stroke + cup_len(stroke) + rs["plunger_gap"]
    return x_r0 + lin + rs["wall"] + p["reservoir_frozen"]["end_wall"]


def apply_inline(p: dict, mode: str = "inline") -> dict:
    """Parameter overrides of the sealed drives (per-size values are applied by apply_variant)."""
    p["drive_mode"] = mode
    b = p["bench"]
    if mode == "inline":
        b["gears"]["x0"] = GEAR_X0
    p["screws"]["dry_y_side"] = list(DRY_Y_SIDE)
    tgt = {}
    for v, d in p["variants"].items():
        x_r1 = predicted_x_r1(p, d["stroke"])
        b["thrust"]["rod_len"][v] = round(x_r1 + 0.85 - 1.65, 2)       # encoder rod keeps its rear end at x 1.65
        tgt[v] = round(x_r1 + b["tail_len"] + p["shell"]["wall"] + LEN_MARGIN, 1)
    b["length_targets_by_layout"][b["drive_layout"]] = tgt
    return p


def apply_variant(p: dict, variant: str) -> None:
    s = p["variants"][variant]["stroke"]
    if mode_of(p) == "coaxial":
        g1 = coax_gear_x1(s)
        p["bench"]["gears"]["x0"] = g1 - p["drive"]["gear_t"]
        p["fit"]["clr_small"] = COAX_CLR
    else:
        p["reservoir"]["plunger_len"] = cup_len(s)


def cup_geometry(p: dict, L: dict) -> dict:
    """All x positions of the cup at the FULL state (plate rear at L['xrear'])."""
    dr, rs = p["drive"], p["reservoir"]
    s = L["stroke"]
    xp0 = L["xrear"]
    if mode_of(p) == "coaxial":     # plain 3.8 piston at the plunger rear x_p0; nut glued on the gear_d front face; screw tip 0.05 off the socket bottom
        nut0 = L["gear_x1"] + NUT_GLUE
        x_tip = xp0 + COAX_SOCKET - 0.05
        return {"plate": None, "nut": [nut0, nut0 + NUT_THICK], "x_tip": x_tip, "piston": [xp0, xp0 + pl_core(p)],
                "nose": [xp0 + pl_core(p), xp0 + pl_core(p) + rs["nose_len"]], "tube": None, "socket_bottom": xp0 + COAX_SOCKET,
                "cup_len": pl_core(p), "xpr": xp0, "x_rear": COAX_SCREW_REAR}
    nut = (xp0 + 0.05, xp0 + 0.05 + dr["nut_len"])
    x_tip = xp0 + PLATE_POCKET + TIP_BEYOND_NUT + s
    xpr = xp0 + s - 0.2                                  # piston rear face
    pl = rs["plunger_len"]
    return {"plate": [xp0, xp0 + PLATE_T], "nut": list(nut), "x_tip": x_tip,
            "piston": [xpr, xpr + pl_core(p)], "nose": [xpr + pl_core(p), xpr + pl_core(p) + rs["nose_len"]],
            "tube": [xp0 + PLATE_T - PLATE_CBORE, xpr + SOCKET_DEPTH], "socket_bottom": xpr + SOCKET_DEPTH,
            "cup_len": pl, "xpr": xpr}


def pl_core(p: dict) -> float:
    return 3.8      # piston core length: seal rings at 0.6..1.4 and 2.3..3.1 (params seal.ring_a/b) fit this core


def inline_layout(p: dict, L: dict) -> dict:
    ys, yr = L["y_s"], L["y_r"]
    z = L["gears"]
    yc = (ys + yr) / 2.0
    c_bc = ys - yc
    c_cd = yc - yr
    gm = p["bench"]["gears"]["module"]
    th_bc = gm * (z["z_screw"] + IDLER_Z) / 2
    th_cd = gm * (IDLER_Z + NUT_GEAR_Z) / 2
    sl = p["bench"]["thrust"]
    return {"y_c": yc, "y_r": yr, "idler_z": IDLER_Z, "nut_gear_z": NUT_GEAR_Z,
            "centre_bc": c_bc, "centre_cd": c_cd, "centre_bc_theory": th_bc, "centre_cd_theory": th_cd,
            "centre_add_bc": c_bc - th_bc, "centre_add_cd": c_cd - th_cd,
            "tip_c": gm * (IDLER_Z + 2), "tip_d": gm * (NUT_GEAR_Z + 2),
            "ratio_b_to_d": z["z_screw"] / NUT_GEAR_Z,                 # gear_b (z20) -> idler -> gear_d (z20): 1:1
            "sleeve_od": sl["sleeve_od"], "variant": mode_of(p),
            "dry_bush2": ([L["gear_x0"] - 1.65, L["gear_x0"] - 0.65] if mode_of(p) == "coaxial" else [L["wall"], L["wall"] + p["drive"]["bush_len"]]),
            "cup": None}


# ------------------------------------------------------------------------------------------------------------ CAD builders
def build_reservoir_closed(s, p: dict, L: dict, name: str = "reservoir") -> None:
    rs = p["reservoir"]
    zc = L["z_axis"]
    s.stadium(name, (L["x_r0"], L["x_r1"]), L["y_r"], zc, L["res_w_out"], L["res_h_out"])
    s.stadium("t_chamber", (L["x_r0"] - 0.1, L["x_in1"]), L["y_r"], zc, rs["w_in"], rs["h_in"])
    fz = p["reservoir_frozen"]
    port = s.cyl("t_rport", "X", (0, L["y_r"], zc), fz["port_d"], L["x_in1"] - 0.1, L["x_r1"] + 0.1)
    s.cut(name, ["t_chamber", port])          # NO side slot: the only openings are the dry rear end and the port


def build_inline_drive(s, p: dict, L: dict) -> None:
    from op_drive import build_drive
    dr, rs, sl = p["drive"], p["reservoir"], p["seal"]
    zc, yr, ys = L["z_axis"], L["y_r"], L["y_s"]
    I = L["inline"]
    C = cup_geometry(p, L)
    I["cup"] = C
    build_reservoir_closed(s, p, L)
    c = rs["plunger_clr"]
    wc, hc = rs["w_in"] - 2 * c, rs["h_in"] - 2 * c
    gd = sl["groove_depth"]
    # ---- piston (printed core + 2 cast lip rings + nose) -----------------------------------------------------------
    xpr = C["xpr"]
    s.stadium("plunger_core", (xpr, xpr + pl_core(p)), yr, zc, wc, hc)
    tools = []
    for k, (a, b) in enumerate((sl["ring_a"], sl["ring_b"])):
        s.stadium_ring(f"t_gr{k}", (xpr + a, xpr + b), yr, zc, wc + 0.8, hc + 0.8, wc - 2 * gd, hc - 2 * gd)
        tools.append(f"t_gr{k}")
    coax = mode_of(p) == "coaxial"
    tools.append(s.cyl("t_psock", "X", (0, yr, zc), SOCKET_D, xpr - 0.1, xpr + (COAX_SOCKET if coax else SOCKET_DEPTH)))
    s.cut("plunger_core", tools)
    if coax:       # anti-rotation tab at the socket bottom: engages the hacksaw slot across the screw tip
        s.box("t_ptab", (xpr + COAX_SOCKET - COAX_TAB_LEN, xpr + COAX_SOCKET + 0.05), (yr - COAX_TAB_T / 2, yr + COAX_TAB_T / 2), (zc - 1.1, zc + 1.1))
        s.join("plunger_core", ["t_ptab"])
    s.stadium("plunger_nose", (C["nose"][0], C["nose"][1]), yr, zc, wc, hc)
    ao = sl["assembly_gap"]
    for k, nm in enumerate(("seal_a", "seal_b")):
        a, b = (sl["ring_a"], sl["ring_b"])[k]
        s.stadium_ring(nm, (xpr + a, xpr + b), yr, zc, rs["w_in"] - ao, rs["h_in"] - ao, wc - 2 * gd, hc - 2 * gd)
    if not coax:
        # ---- tube + rear plate with the nut -------------------------------------------------------------------------
        s.tube("plunger_tube", "X", (0, yr, zc), TUBE_OD, TUBE_ID, C["tube"][0], C["tube"][1])
        x0 = C["plate"][0]
        s.stadium("plunger_plate", (x0, x0 + PLATE_T), yr, zc, wc, hc)
        apo = (dr["nut_af"] + 0.1) / 2
        cuts = [s.hexprism("t_phex", (x0 - 0.1, x0 + PLATE_POCKET), yr, zc, apo, angle=0.0),
                s.cyl("t_phole", "X", (0, yr, zc), SCREW_HOLE_D, x0 - 0.1, x0 + PLATE_T + 0.1),
                s.cyl("t_pcb", "X", (0, yr, zc), PLATE_CBORE_D, x0 + PLATE_T - PLATE_CBORE, x0 + PLATE_T + 0.1)]
        s.cut("plunger_plate", cuts)
    nx0, nx1 = C["nut"]
    s.hexprism("nut", (nx0, nx1), yr, zc, dr["nut_af"] / 2, angle=0.0)
    s.cyl("t_nbore", "X", (0, yr, zc), dr["screw_d"] + 0.05, nx0 - 0.1, nx1 + 0.1)
    s.cut("nut", ["t_nbore"])
    # ---- encoder lane (gear_b, rod y_s, bushes, collar, magnet, motor, gear_a): the existing builder, unchanged -------
    build_drive(s, p, L)
    # ---- drive axis y_r: bush, thrust sleeve (gear carrier), gear_d, drive screw ---------------------------------
    gx0, gx1 = L["gear_x0"], L["gear_x1"]
    db = I["dry_bush2"]
    sd = I["sleeve_od"]
    s.cyl("drive_screw", "X", (0, yr, zc), dr["screw_d"], C["x_rear"] if coax else 1.65, C["x_tip"])
    if coax:       # hacksaw slot across the tip (full diameter in z, 0.4 wide in y, 1.0 deep) for the plunger tab
        s.cut("drive_screw", [s.box("t_sslot", (C["x_tip"] - COAX_TAB_LEN, C["x_tip"] + 0.1), (yr - COAX_SLOT_T / 2, yr + COAX_SLOT_T / 2), (zc - 1.0, zc + 1.0))])
    s.tube("bush_dry2", "X", (0, yr, zc), dr["bush_od"], dr["bush_id"], db[0], db[1])
    s.tube("thrust_sleeve2", "X", (0, yr, zc), sd, dr["screw_d"] + 0.04, db[1] + p["bench"]["thrust"]["sleeve_gap"], gx1)
    s.cyl("gear_d", "X", (0, yr, zc), I["tip_d"], gx0, gx1)
    s.cyl("t_gdb", "X", (0, yr, zc), sd + 0.04, gx0 - 0.1, gx1 + 0.1)
    s.cut("gear_d", ["t_gdb"])
    # ---- idler gear_c on a fixed pin ---------------------------------------------------------------------------------
    yc = I["y_c"]
    s.cyl("gear_c", "X", (0, yc, zc), I["tip_c"], gx0, gx1)
    s.cyl("t_gcb", "X", (0, yc, zc), 2.04, gx0 - 0.1, gx1 + 0.1)
    s.cut("gear_c", ["t_gcb"])
    s.cyl("idler_pin", "X", (0, yc, zc), 2.0, (gx0 - 1.65) if coax else (L["wall"] + 0.3), gx1 + 0.25)


def bottom_extra(s, p: dict, L: dict) -> None:
    """Bearing blocks for the drive axis and the idler pin, floor relief under gear_d (added after the standard bottom is built)."""
    dr, wall, zc = p["drive"], L["wall"], L["z_axis"]
    I = L["inline"]
    bh = dr["bush_od"] + 2 * 0.675
    gx0 = L["gear_x0"]
    xb = (gx0 - 1.7) if mode_of(p) == "coaxial" else (wall + 0.02)          # coaxial: the bearing blocks sit right behind the gear plane
    joins = [s.box("t_dblk_r", (xb, gx0 - 0.05), (I["y_r"] - bh / 2, I["y_r"] + bh / 2), (wall - 0.1, zc + bh / 2)),
             s.box("t_dblk_c", (xb, gx0 - 0.05), (I["y_c"] - 1.5, I["y_c"] + 1.5), (wall - 0.1, zc + 1.5))]
    s.join("bottom", joins)
    bb = dr["bush_od"] + dr["bush_bore_clr"]
    cuts = [s.cyl("t_dbore_r", "X", (0, I["y_r"], zc), bb, min(I["dry_bush2"][0], xb - 0.05), gx0 + 0.05),
            s.cyl("t_pinbore", "X", (0, I["y_c"], zc), 2.0, xb - 0.05, gx0 + 0.05)]
    lr = p["bench"]["lid_recess"]
    cuts.append(s.box("t_grelief_d", (gx0 - 0.3, L["gear_x1"] + 0.3), (I["y_r"] - 3.6, I["y_r"] + 3.6), (wall - lr["floor_relief_gear_b"], wall + 0.01)))
    s.cut("bottom", cuts)


def top_extra_cuts(s, p: dict, L: dict) -> list:
    lr = p["bench"]["lid_recess"]
    zi = L["height"] - L["wall"]
    return [s.box("t_lgear_d", (L["gear_x0"] - 0.3, L["gear_x1"] + 0.3), (L["y_r"] - 3.6, L["y_r"] + 3.6), (zi - 0.2, zi + lr["over_gear_b"]))]


def fluid_boundary(p: dict, L: dict, reservoir_volume_mm3: float, reservoir_bbox: dict) -> tuple[list, list]:
    """Wetted zone = bore ahead of the plunger front at the FULL state.  The reservoir body may have only two openings: the dry rear end
    (x_r0, behind the plunger even when full) and the d2.0 port in the closed end.  Verified by the measured solid volume of the reservoir
    (a slot of any size removes volume) and by its bounding box."""
    from op_layout import stadium_area
    rs, fz = p["reservoir"], p["reservoir_frozen"]
    problems, notes = [], []
    A_out = stadium_area(L["res_w_out"], L["res_h_out"])
    A_in = stadium_area(rs["w_in"], rs["h_in"])
    v_exp = A_out * (L["x_r1"] - L["x_r0"]) - A_in * (L["x_in1"] - L["x_r0"]) - math.pi * (fz["port_d"] / 2) ** 2 * (L["x_r1"] - L["x_in1"])
    err = reservoir_volume_mm3 - v_exp
    if abs(err) > 0.5:
        problems.append(f"fluid boundary: reservoir volume {reservoir_volume_mm3:.2f} mm3 != closed-bore volume {v_exp:.2f} (diff {err:+.2f}): unexpected opening in the wall")
    C = L["inline"]["cup"]
    x_wet0 = C["nose"][1] if False else C["piston"][1]          # piston front at full = start of the wetted zone
    if not (L["x_r0"] < x_wet0 - 1.0):
        problems.append("dry rear opening is not behind the plunger at full")
    bb_lo, bb_hi = reservoir_bbox["min"], reservoir_bbox["max"]
    if abs(bb_lo[0] - L["x_r0"]) > 1e-3 or abs(bb_hi[0] - L["x_r1"]) > 1e-3:
        problems.append("reservoir x extent differs from the layout")
    notes.append(f"fluid boundary: reservoir volume {reservoir_volume_mm3:.2f} mm3 = closed-bore model {v_exp:.2f} (|diff| {abs(err):.3f}); openings: dry rear end at x {L['x_r0']:.2f} "
                 f"(wetted zone starts x {x_wet0:.2f}, plunger front at full) + port d{fz['port_d']} at x {L['x_in1']:.2f}..{L['x_r1']:.2f}")
    return problems, notes


def check_inline(p: dict, L: dict, by: dict) -> tuple[list, list]:
    problems, warns = [], []
    I = L["inline"]
    C = I["cup"] if I.get("cup") else cup_geometry(p, L)
    coax = I.get("variant") == "coaxial"
    for need in (() if coax else ("plunger_tube", "plunger_plate")) + ("drive_screw", "gear_c", "gear_d", "idler_pin", "bush_dry2", "thrust_sleeve2", "nut", "plunger_core", "plunger_nose",
                 "gear_a", "gear_b", "leadscrew", "bush_dry", "bush_far", "thrust_sleeve", "thrust_collar", "magnet"):
        if need not in by:
            problems.append(f"inline body missing: {need}")
    for gone in ("carriage", "tongue_shim"):
        if gone in by:
            problems.append(f"slot/tongue part present in the sealed drive: {gone}")
    if problems:
        return problems, warns
    bb = lambda n: by[n]["bbox"]
    ctr = lambda n, ax: (bb(n)["min"][ax] + bb(n)["max"][ax]) / 2
    # gear chain: centre distances = theory + centre_add (backlash window 0.10..0.12), no gear overlap except the three meshes
    for a, b_, th in (("gear_b", "gear_c", I["centre_bc_theory"]), ("gear_c", "gear_d", I["centre_cd_theory"])):
        d = abs(ctr(a, 1) - ctr(b_, 1))
        if not (th + 0.02 <= d <= th + 0.20):
            problems.append(f"gear mesh {a}-{b_} centre {d:.3f} mm outside theory+0.02..0.20 (theory {th:.3f})")
    for a, b_ in (("gear_a", "gear_c"), ("gear_a", "gear_d"), ("gear_b", "gear_d")):
        d = math.hypot(ctr(a, 1) - ctr(b_, 1), 0.0)
        ra, rb = (bb(a)["max"][1] - bb(a)["min"][1]) / 2, (bb(b_)["max"][1] - bb(b_)["min"][1]) / 2
        if d < ra + rb + 0.2:
            problems.append(f"gears {a} and {b_} too close for non-meshing gears: {d:.2f} < {ra + rb + 0.2:.2f}")
    if abs(ctr("drive_screw", 1) - L["y_r"]) > 1e-3 or (not coax and abs(ctr("plunger_tube", 1) - L["y_r"]) > 1e-3) or abs(ctr("nut", 1) - L["y_r"]) > 1e-3:
        problems.append("drive screw / tube / nut not on the reservoir axis")
    # axial stack of the drive screw: thrust sleeve on the dry bush face, gear_d on the sleeve, screw spans bush .. tip
    sl2, bd2, ds = bb("thrust_sleeve2"), bb("bush_dry2"), bb("drive_screw")
    if not (0.0 <= sl2["min"][0] - bd2["max"][0] <= 0.15):
        problems.append(f"drive thrust sleeve not seated on the dry bush face (gap {sl2['min'][0] - bd2['max'][0]:.2f})")
    if (ds["min"][0] > sl2["min"][0] and not coax) or ds["max"][0] < C["x_tip"] - 1e-6:
        problems.append("drive screw does not span sleeve .. tip")
    # screw tip inside the dry cup at FULL; engaged at EMPTY
    s = L["stroke"]
    tip = ds["max"][0]
    socket_bottom = C["socket_bottom"]
    nut = bb("nut")
    if coax:       # translating screw: tip touches the socket bottom (push contact), rear end stays in the pod, thread engaged >= nut + 0.5 at empty
        if not (0.0 <= socket_bottom - tip <= 0.1):
            problems.append(f"screw tip {tip:.2f} not seated on the plunger socket bottom {socket_bottom:.2f}")
        engaged_empty = nut["max"][0] - (ds["min"][0] + s)
        if engaged_empty < p["drive"]["nut_len"] + 0.4:
            problems.append(f"screw rear end at empty only {engaged_empty:.2f} mm behind the nut front (< nut + 0.4)")
        if ds["min"][0] < L["wall"] + 0.2:
            problems.append(f"screw rear end {ds['min'][0]:.2f} at full too close to the rear wall")
        g = nut["min"][0] - bb("gear_d")["max"][0]
        if not (0.0 <= g <= 0.05):
            problems.append(f"nut not seated on the gear_d front face (gap {g:.3f})")
        pg = bb("plunger_core")["min"][0] - nut["max"][0]
        if pg < 0.15:
            problems.append(f"plunger rear only {pg:.2f} mm from the nut front at full")
    else:
        if socket_bottom - tip < TIP_CLEAR - 1e-6:
            problems.append(f"screw tip {tip:.2f} closer than {TIP_CLEAR} to the piston socket bottom {socket_bottom:.2f} at full")
        engaged_empty = tip - (nut["max"][0] + s)
        if engaged_empty < 0.9:
            problems.append(f"screw beyond the nut front at empty only {engaged_empty:.2f} mm (< 0.9)")
    # nose at empty must stay behind the closed end (dead layer)
    nose_empty = bb("plunger_nose")["max"][0] + s
    if L["x_in1"] - nose_empty < 0.2:
        problems.append(f"piston nose at empty {nose_empty:.2f} hits the closed end x {L['x_in1']:.2f}")
    # plate inside the bore at full (behind it only the dry strip), screw passes the plate hole
    if not coax:
        pl = bb("plunger_plate")
        if pl["min"][0] < L["x_r0"] + 0.5:
            problems.append("plunger plate leaves the bore at full")
    warns.append(f"{'coaxial translating-screw drive' if coax else 'cup drive'}: stroke {s:.1f}, {'plunger core' if coax else 'cup length'} {C['cup_len']:.1f}, screw x {ds['min'][0]:.2f}..{tip:.2f}, engaged beyond nut at empty {engaged_empty:.2f}, "
                 f"tip clear to piston socket at full {socket_bottom - tip:.2f}, nose margin at empty {L['x_in1'] - nose_empty:.2f}; encoder lane gear_b -> idler z{I['idler_z']} -> gear_d z{I['nut_gear_z']} (1:1)")
    return problems, warns
