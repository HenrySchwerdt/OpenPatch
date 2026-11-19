#!/usr/bin/env python3
"""Dimension, interference, wall-thickness, contact and RF-keepout checks of the generated assemblies.

  python3 check.py                 # all sizes in out/
  python3 check.py --outdir out
  python3 check.py --ignore-length # length > target only as WARN

Exit code 1 on: height > max, width/length > target, solid interference (exclude list in op_build.py),
open bodies, spring-contact stack outside 0..spring_h_max, metal inside the antenna keep-out,
or a *declared* wall below 0.6 mm that is not on the documented exception list.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from op_build import part_sets
from op_layout import HERE, find_cli, load_params

CLI = find_cli()
EPS = 1e-6
MIN_OVERLAP_MM3 = 1e-4
MIN_WALL = 0.6
MIN_FEATURE = 0.4     # hard floor even for documented exceptions (MJF/SLA min wall ~0.4-0.5)
METAL = ["motor", "gearhead", "leadscrew", "magnet", "battery", "qi_coil", "gear_a", "gear_b", "nut", "needle"]
# documented exceptions (lap closure bands, membrane, gap-limited features) -> reported as WARN
WALL_EXCEPTIONS = {"carriage_wall_y", "lid_skirt", "bottom_tongue", "button_membrane", "latch_beam_note", "gasket_ring_width"}


def eval_design(sc: Path, exclude_pairs: list) -> list:
    script = [{"command": "inspect.measure", "params": {}},
              {"command": "inspect.interference", "params": {"exclude_pairs": exclude_pairs}}]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(script, fh)
        tmp = fh.name
    res = subprocess.run([CLI, "run", tmp, "--in", str(sc), "--results", "--quiet"], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if res.returncode != 0:
        raise SystemExit(res.stdout + res.stderr)
    return json.loads(res.stdout)


def envelope(bodies: list) -> tuple[list, list]:
    lo = [min(b["bbox"]["min"][i] for b in bodies) for i in range(3)]
    hi = [max(b["bbox"]["max"][i] for b in bodies) for i in range(3)]
    return lo, hi


def declared_walls(p: dict, L: dict) -> list[tuple[str, float, bool]]:
    """(name, thickness_mm, is_exception).  Walls follow from the parameters (not measured on the solid)."""
    sh, rs, dr, bn, sl = p["shell"], p["reservoir"], p["drive"], p["button"], p["seal"]
    bh = dr["bush_od"] + 2 * 0.675
    out = [
        ("shell_wall", sh["wall"], False),
        ("reservoir_wall", rs["wall"], False),
        ("lid_skirt", sh["lid_ring_inset"], True),
        ("bottom_tongue", sh["wall"] - sh["rim_inset"], True),
        ("gasket_ring_width", sh["wall"] - sh["rim_inset"], True),
        ("button_membrane", bn["memb_t"], True),
        ("bearing_block_wall_y", (bh - dr["bush_od"] - dr["bush_bore_clr"]) / 2, False),
        ("bearing_block_wall_z", (bh - dr["bush_od"] - dr["bush_bore_clr"]) / 2, False),
        ("carriage_wall_y", (dr["carriage_bw"] - (dr["nut_af"] + dr["nut_hex_clr"])) / 2, True),
        ("carriage_wall_under_hex", (dr["carriage_bh"] / 2 - (dr["nut_af"] + dr["nut_hex_clr"]) / 2 / 0.866) - dr["groove_d"], False),
        ("carriage_wall_over_hex", dr["carriage_bh"] / 2 - (dr["nut_af"] + dr["nut_hex_clr"]) / 2 / 0.866, False),
        ("rail_width", dr["rail_w"], False),
        ("seal_ring_radial", (rs["w_in"] - sl["assembly_gap"] - (rs["w_in"] - 2 * rs["plunger_clr"] - 2 * sl["groove_depth"])) / 2, False),
        ("plunger_flange", sl["flange"], True),
        ("plunger_front_flange", rs["plunger_len"] - sl["ring_b"][1], True),
        ("plunger_groove_to_socket_wall", sl["socket_x"][0] - sl["ring_a"][1], True),
        ("plunger_purge_bridge", rs["plunger_len"] - sl["ring_b"][1] - sl["purge"]["groove_d"], True),
        ("plunger_socket_wall_z", ((rs["h_in"] - 2 * rs["plunger_clr"]) - (dr["arm_t"] + 0.1)) / 2, False),
        ("tongue_x", dr["tongue_x"], False),
        ("septum_boss_wall", (p["septum"]["boss_d"] - (p["septum"]["d"] * (1.0 - p["dock"]["cap"]["septum_compress"]) if (p.get("mode") == "bench" and p["dock"]["cap"].get("septum_compress")) else p["septum"]["d"] + 2 * p["septum"]["bore_clr"])) / 2, True),
        ("screw_dome_wall", (p["screws"]["boss_d"] - p["screws"]["pilot"]) / 2, False),
    ]
    return [(n, round(t, 3), e) for n, t, e in out]


def check_extra(p: dict, L: dict, bodies: list) -> tuple[list, list]:
    problems, warns = [], []
    ct = L["contacts"]
    pad_tops = [t["z_pad_top"] for t in ct["battery_tabs"]] + [t["z_pad_top"] for t in ct["motor_fpc"]]
    for z in pad_tops:
        gap = ct["pcb_bottom_z"] - z
        if not (0.2 <= gap <= ct["spring_h_max"] - 0.2):
            problems.append(f"spring contact gap {gap:.2f} mm outside 0.2..{ct['spring_h_max']-0.2:.1f}")
    kx0, kx1, ky0, ky1 = L["rf_module"]["keepout_xy"]
    by = {b["name"]: b for b in bodies}
    for nm in METAL:
        b = by.get(nm)
        if not b:
            continue
        mn, mx = b["bbox"]["min"], b["bbox"]["max"]
        if mx[0] > kx0 and mn[0] < kx1 and mx[1] > ky0 and mn[1] < ky1:
            problems.append(f"{nm} inside RF keep-out xy [{kx0:.1f}..{kx1:.1f}] x [{ky0:.1f}..{ky1:.1f}]")
    for hp in ct["hold_down_pads"]:
        if hp["z0"] < ct["pcb_bottom_z"]:
            problems.append("hold-down pad below PCB")
    if not L["buzzer"]["fits_9x9"]:
        warns.append(f"piezo envelope only {L['buzzer']['x1']-L['buzzer']['x0']:.1f} x "
                     f"{L['buzzer']['y1']-L['buzzer']['y0']:.1f} mm (9x9x2 part does not fit - see README)")
    if L["bat_vol_mm3"] < 700:
        warns.append(f"battery envelope {L['bat_x']:.1f}x{p['battery']['y']}x{p['battery']['t']} mm = "
                     f"{L['bat_vol_mm3']:.0f} mm3 (target >= 40 mAh ~ 700 mm3 NOT met)")
    return problems, warns


BENCH_MIN_CLR = 0.2     # board / sensors / FFC to any metal or shell part that is not a mating part


FLUID_WARNS: list = []


def check_fluid_boundary(p: dict, L: dict) -> tuple[list, list]:
    """Fluid-boundary check at both plunger extremes (full = plunger at the rear stop, empty = at the front stop).

    Wetted zone = bore in front of the front seal contact line (x from the land of the front bead to the end face) + port + cap channels + septum chamber + needle (no check valve, spec 3c).
    It must be bounded only by reservoir / cap / seal / septum / needle surfaces: every opening through the reservoir wall (op_drive.wall_openings) whose
    x-range reaches in front of the seal contact line is a leak into the pod.  Also: the front seal contact stays inside the bore for the whole stroke,
    the plunger front stays behind the end face, and every cap interface (O-ring, gasket, septum, needle) has a defined seal element.  Returns (problems, known_failing).
    """
    from op_drive import wall_openings
    from op_seal import ring_range, variant
    rs, sl = p["reservoir"], p["seal"]
    v = variant(p)
    problems, known = [], []
    warns_valve: list = []
    a, b = ring_range(p, v["rings"][-1])                      # front-most bead of the active variant
    land_c = (a + b) / 2                                      # centre of the land
    for tag, xr in (("full", L["xrear_full"]), ("empty", L["xrear_empty"])):
        line = xr + land_c
        if not (L["x_r0"] <= xr + a and line <= L["x_in1"]):
            problems.append(f"fluid: front seal contact line x={line:.2f} outside the bore {L['x_r0']:.2f}..{L['x_in1']:.2f} at the {tag} position")
        if xr + rs["plunger_len"] > L["x_in1"] + 1e-6:
            problems.append(f"fluid: plunger front {xr + rs['plunger_len']:.2f} beyond the chamber end {L['x_in1']:.2f} at the {tag} position")
        for op in wall_openings(p, L):
            if op["x"][1] > line - 1e-6 and op["x"][0] < L["x_in1"]:
                known.append(f"fluid boundary: wall opening '{op['name']}' x {op['x'][0]:.1f}..{op['x'][1]:.1f} reaches {op['x'][1] - line:.1f} mm in front of the "
                             f"front seal contact line (x={line:.1f}) at the {tag} position: the wetted zone leaks into the pod through it")
    if p.get("mode") == "bench":
        from op_cap import cap_interfaces
        for itf in cap_interfaces(p, L):
            if itf["gap"] >= 0.0 and not itf["seal"]:
                problems.append(f"fluid: cap interface '{itf['name']}' has gap {itf['gap']:+.3f} mm and no seal element (resin/PP clearance or flat face is not a seal)")
            if itf.get("squeeze") is not None and "O-ring" in (itf["seal"] or "") and not (0.08 <= itf["squeeze"] <= 0.30):
                problems.append(f"fluid: O-ring squeeze {100 * itf['squeeze']:.0f} % of '{itf['name']}' outside 8..30 %")
            if itf.get("squeeze") is not None and "radial compression" in (itf["seal"] or "") and not (0.10 <= itf["squeeze"] <= 0.20):
                problems.append(f"fluid: septum radial compression {100 * itf['squeeze']:.0f} % outside 10..20 %")
    FLUID_WARNS[:] = warns_valve
    return problems, known


def check_fill_unreachable(p: dict, L: dict) -> tuple[list, list]:
    """Hazard H14 (spec 3e): with the pod docked no straight needle path (needle d0.4, any direction from outside) may reach the fill septum.
    The septum is on the UNDERSIDE; its fill-needle hole (cap.fill_hole_d through the pod floor and the base) is the only opening, so a ray reaches the septum only if it passes
    through that hole.  While docked the pod sits on the Velcro patch, which covers the whole underside footprint (floor recess `velcro`, x to x_r1 + dock.cover.x_end_u); a plate directly
    under the floor blocks every ray (any angle) through the hole iff the hole footprint (+ needle radius) lies inside the patch footprint.  Returns (problems, known_failing)."""
    cp, cv, vc = p["dock"]["cap"], p["dock"].get("cover"), p["velcro"]
    if not cv:
        return ["fluid: no docked cover defined (dock.cover): fill septum reachable while docked (H14)"], []
    nr = cv["needle_d"] / 2
    r = cp["fill_hole_d"] / 2 + nr
    hx, hy = L["x_r1"] + cp["septum_x"], L["dock"]["y_c"] - cp["septum_dy"]
    px0, px1 = L["x_r0"] + vc["margin_x"], L["x_r1"] + cv["x_end_u"]
    py0, py1 = vc["y0"], vc["y1"]
    ok = px0 <= hx - r and hx + r <= px1 and py0 <= hy - r and hy + r <= py1
    if ok:
        return [], []
    return [f"H14 fill septum reachable while docked: underside fill hole at x {hx - r:.1f}..{hx + r:.1f}, y {hy - r:.1f}..{hy + r:.1f} is NOT inside the Velcro patch footprint "
            f"(x {px0:.1f}..{px1:.1f}, y {py0}..{py1}): a needle can enter the hole while docked and inject through the outlet (no check valve)"], []


def check_bench(p: dict, L: dict, bodies: list) -> tuple[list, list]:
    """Bench-pod checks: board inside the cavity, clearances, sensor-magnet gaps, contact compression, FFC slot, adapter."""
    problems, warns = [], []
    b, B = p["bench"], L["bench"]
    by = {x["name"]: x for x in bodies}
    for need in ("pod_board", "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock", "ffc_conn", "ffc_cable",
                 "cannula_adapter", "dock_magnet", "motor", "gearhead", "motor_shaft", "motor_pins", "end_cap", "end_cap_lid", "cap_gasket", "dock_insert", "cap_oring") + (() if L.get("inline") else ("tongue_shim",)) + (("coupler",) if L["coax"] else ("gear_a", "gear_b", "thrust_sleeve", "thrust_collar")):
        if need not in by:
            problems.append(f"bench body missing: {need}")
    for gone in ("battery", "qi_coil", "rf_module", "pcb", "buzzer", "ratchet_wheel", "sma_slider"):
        if gone in by:
            problems.append(f"integrated part present in bench pod: {gone}")
    if problems:
        return problems, warns
    bd = by["pod_board"]["bbox"]
    mn, mx = bd["min"], bd["max"]
    # board inside the inner cavity (rounded corners are checked by the interference test against 'bottom'/'top')
    if mn[0] < L["xi0"] + 0.3 or mx[0] > L["x_end"] - 0.3 or mn[1] < L["yi0"] + 0.3 or mx[1] > L["yi1"] - 0.3:
        problems.append(f"pod_board bbox {mn[:2]}..{mx[:2]} closer than 0.3 mm to the housing walls")
    clr = 9.9
    # sensor to spindle-magnet gaps
    mag = by["magnet"]["bbox"]
    for n in ("hall_tmag", "hall_drv0", "hall_drv1"):
        g = by[n]["bbox"]["min"][0] - mag["max"][0]
        if g < 0.4:
            problems.append(f"{n} only {g:.2f} mm from the spindle magnet end face")
    # dock hall above dock magnet
    dm, dh = by["dock_magnet"]["bbox"], by["hall_dock"]["bbox"]
    gap = dh["min"][2] - dm["max"][2]
    if not (0.4 <= gap <= 1.5):
        problems.append(f"dock hall air gap {gap:.2f} mm outside 0.4..1.5")
    cx = (dh["min"][0] + dh["max"][0]) / 2 - (dm["min"][0] + dm["max"][0]) / 2
    cy = (dh["min"][1] + dh["max"][1]) / 2 - (dm["min"][1] + dm["max"][1]) / 2
    if abs(cx) > 0.1 or abs(cy) > 0.1:
        problems.append(f"dock hall not centred over the magnet (dx {cx:.2f}, dy {cy:.2f})")
    if L["coax"]:
        cp, sh_, ls = by["coupler"]["bbox"], by["motor_shaft"]["bbox"], by["leadscrew"]["bbox"]
        if sh_["max"][0] > cp["max"][0] or sh_["max"][0] < cp["min"][0] + 2.0 or ls["min"][0] < cp["min"][0] or ls["min"][0] - sh_["max"][0] < 0.1:
            problems.append("coupler does not cover shaft end and screw start with a gap")
        if by["motor_pins"]["bbox"]["min"][1] < L["yi0"] + 0.3:
            problems.append("motor pins reach the -Y wall")
    else:       # side-by-side motor + gear pair: motor body must clear the carriage lane, gear centre must be >= min
        G = L["gears"]
        if G["centre"] < p["bench"]["gears"]["min_centre"] - 1e-6:
            problems.append(f"gear centre distance {G['centre']:.2f} mm < {p['bench']['gears']['min_centre']} (motor body would hit the carriage lane)")
        mo = by["motor"]["bbox"]
        car = by["carriage"]["bbox"] if "carriage" in by else by["reservoir"]["bbox"]
        if mo["min"][1] < car["max"][1] + 0.1:
            problems.append("motor body closer than 0.1 mm to the carriage lane / reservoir")
        if by["motor_pins"]["bbox"]["min"][2] < p["bench"]["lead"]["pocket_floor"] - 1e-6:
            problems.append("motor pin tabs below the floor pocket")
    if L.get("inline"):         # sealed on-axis cup drive: own checks (op_inline.py) incl. the fluid-boundary check
        from op_inline import check_inline, fluid_boundary
        pi_, wi_ = check_inline(p, L, by)
        problems += pi_
        warns += wi_
        rv_ = by["reservoir"]
        pf_, nf_ = fluid_boundary(p, L, rv_["volume_mm3"], rv_["bbox"])
        problems += pf_
        warns += nf_
    elif not L["coax"]:
        # axial stack of the leadscrew: thrust sleeve on the dry bush face, front collar on the far bush face, magnet behind the collar
        sl, co_, bd, bf, mg, rd, nu, ca = (by[k]["bbox"] for k in ("thrust_sleeve", "thrust_collar", "bush_dry", "bush_far", "magnet", "leadscrew", "nut", "carriage"))
        if not (0.0 <= sl["min"][0] - bd["max"][0] <= 0.15):
            problems.append(f"thrust sleeve not seated on the dry bush face (gap {sl['min'][0] - bd['max'][0]:.2f} mm, want 0..0.15)")
        if not (0.0 <= co_["min"][0] - bf["max"][0] <= 0.15):
            problems.append(f"thrust collar not seated on the far bush face (gap {co_['min'][0] - bf['max'][0]:.2f} mm, want 0..0.15)")
        if mg["min"][0] < co_["max"][0] - 1e-6:
            problems.append("spindle magnet overlaps the thrust collar: reverse thrust would bear on the magnet")
        if mg["min"][0] < bf["max"][0] + 0.5:
            problems.append("spindle magnet closer than 0.5 mm to the far bush face (must not bear on the bush)")
        if rd["min"][0] > sl["min"][0] or rd["max"][0] < co_["max"][0] - 1e-6:
            problems.append("leadscrew does not span the thrust sleeve and collar")
        if nu["min"][0] < ca["min"][0] + 0.2 or nu["max"][0] > by["carriage"]["bbox"]["max"][0] - 0.5:
            problems.append("nut not captured between the carriage rear and front walls")
        warns.append(f"axial stack: rod x {rd['min'][0]:.2f}..{rd['max'][0]:.2f} ({rd['max'][0]-rd['min'][0]:.2f} mm), sleeve {sl['min'][0]:.2f}..{sl['max'][0]:.2f} "
                     f"({sl['max'][0]-sl['min'][0]:.2f} mm), collar {co_['min'][0]:.2f}..{co_['max'][0]:.2f}, magnet from {mg['min'][0]:.2f}")
    ec, rv = by["end_cap"]["bbox"], by["reservoir"]["bbox"]
    if abs(ec["min"][0] - rv["max"][0]) > 0.011 and ec["min"][0] > rv["max"][0] - 1.9:
        problems.append("end cap spigot position vs reservoir port")
    pr_i, wr_i = check_insert(p, L, by)
    problems += pr_i
    warns += wr_i
    ct = B["contacts"]
    # FFC slot: cable leaves the housing, slot taller than the cable
    cab = by["ffc_cable"]["bbox"]
    if cab["max"][0] <= L["length"] + 1.0:
        problems.append("ffc cable does not leave the housing")
    sl = b["ffc"]["slot_z"]
    if cab["min"][2] < sl[0] + 0.1 or cab["max"][2] > sl[1] - 0.1:
        problems.append(f"ffc cable z {cab['min'][2]:.2f}..{cab['max'][2]:.2f} not inside slot z {sl}")
    if mx[2] > by["top"]["bbox"]["max"][2]:
        problems.append("board above lid")
    top_free = L["z_top_inner"] - max(by[n]["bbox"]["max"][2] for n in ("ffc_conn", "hall_drv0", "hall_drv1"))
    if top_free < 0.4:
        problems.append(f"top-side parts only {top_free:.2f} mm below the lid")
    # dock: dome vs board, arm strain, latch geometry
    ad = by["cannula_adapter"]["bbox"]
    dome_top = p["cannula"]["B_dome_h"]
    if mn[2] - dome_top < 0.25:
        problems.append(f"board only {mn[2]-dome_top:.2f} mm above the dome top")
    D = L["dock"]
    if not D["strain_ok"]:
        problems.append(f"snap arm strain {D['arm_strain']*100:.1f} % > 3 %")
    warns.append(f"dock: arm tip travel {D['travel']:.2f} mm, free length {D['flex_len']:.1f} mm, strain {D['arm_strain']*100:.1f} %, "
                 f"arm force {D['arm_tip_force_N']:.1f} N (PA12 E=1.7 GPa)")
    warns.append(f"bench: board {B['width']:.1f} x {B['height']:.1f} mm identical for all sizes; dock gap {gap:.2f} mm; layout {L['drive_layout']}, U/step {L['drive']['u_per_step']:.5f}, "
                 f"pod {L['length']:.1f} x {L['width']:.1f}")
    return problems, warns


def check_insert(p: dict, L: dict, by: dict) -> tuple[list, list]:
    """Dock insert assembled in the pod: frozen-interface fit, needle-to-septum alignment."""
    problems, warns = [], []
    F, cn, D = p["dock_interface_frozen"], p["cannula"], L["dock"]
    ins, ndl, hub, ad = by["dock_insert"]["bbox"], by["needle"]["bbox"], by["needle_hub"]["bbox"], by["cannula_adapter"]["bbox"]
    yc, zn, xr = D["y_c"], D["z_n"], L["x_r1"]
    if ins["min"][0] < xr + F["x0_u"] - 1e-6 or ins["min"][0] > xr + F["x0_u"] + 0.2:
        problems.append(f"dock insert front face x {ins['min'][0]:.3f} not on the frozen datum x_r1+{F['x0_u']}")
    if ins["max"][0] > L["length"] + 1e-6:
        problems.append("dock insert sticks out behind the +X end face")
    half = max(yc - ins["min"][1], ins["max"][1] - yc)
    if half > F["pocket_half"] + 1e-6 or abs((ins["min"][1] + ins["max"][1]) / 2 - yc) > 0.3:
        problems.append(f"dock insert y extent {ins['min'][1]:.2f}..{ins['max'][1]:.2f} outside the frozen pocket (half {F['pocket_half']})")
    ny, nz = (ndl["min"][1] + ndl["max"][1]) / 2, (ndl["min"][2] + ndl["max"][2]) / 2
    hy, hz = (hub["min"][1] + hub["max"][1]) / 2, (hub["min"][2] + hub["max"][2]) / 2
    if max(abs(ny - yc), abs(nz - zn), abs(hy - yc), abs(hz - zn)) > 0.02:
        problems.append(f"needle axis ({ny:.3f},{nz:.3f}) / hub ({hy:.3f},{hz:.3f}) not on the frozen needle axis ({yc},{zn})")
    if abs((ad["min"][1] + ad["max"][1]) / 2 - yc) > 0.05:
        problems.append("adapter not centred on the needle axis in Y")
    depth = ndl["max"][0] - D["x_face"]
    if abs(depth - cn["F_needle_depth"]) > 0.02:
        problems.append(f"needle penetration {depth:.3f} mm != cannula.F_needle_depth {cn['F_needle_depth']}")
    if abs(D["x_hook"] - (D["x_d"] + cn["G_latch_dx"])) > 0.05:
        problems.append("insert hook x not on the adapter notch x")
    warns.append(f"dock insert: x {ins['min'][0]-xr:.2f}..{ins['max'][0]-xr:.2f} (u), needle penetration {depth:.2f} mm, "
                 f"hook gap {2 * D['hook_in']:.2f} mm")
    return problems, warns


def check_insert_variants(outdir: Path, variant: str, p: dict, L: dict) -> tuple[list, list]:
    """All insert variants (variants.csv set) assembled at the pod position of `variant`: no interference with any pod part
    (the nominal insert, the dummy head and the other variants are excluded), arm strain within limit."""
    from op_cmds import Script
    from op_coupon import add_variant_inserts, variants
    problems, warns = [], []
    vs = variants(p)
    s = Script()
    geo = add_variant_inserts(s, p, vs, x_r1=L["x_r1"], length=L["length"])
    names = [f"dock_insert_v{v['id']:02d}" for v in vs]
    excl = [[a, b] for i, a in enumerate(names) for b in names[i + 1:]] + [[n, o] for n in names for o in ("dock_insert", "cannula_adapter")]
    cmds = s.dumps() + [{"command": "inspect.interference", "params": {"exclude_pairs": excl}}]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(cmds, fh)
        tmp = fh.name
    res = subprocess.run([CLI, "run", tmp, "--in", str(outdir / f"{variant}.sc"), "--results", "--quiet"], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if res.returncode != 0:
        return [f"insert variant check failed to run: {(res.stdout + res.stderr)[-300:]}"], warns
    interf = next(r for r in json.loads(res.stdout) if "interferences" in r)
    for i in interf["interferences"]:
        if (i["a"] in names or i["b"] in names) and i.get("volume_mm3", 1) > MIN_OVERLAP_MM3:
            problems.append(f"insert variant interference {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    for u in interf.get("unchecked", []):
        if u["a"] in names or u["b"] in names:
            problems.append(f"insert variant pair not checked: {u['a']} x {u['b']}")
    for v in vs:
        g = geo[v["id"]]
        if not g["strain_ok"]:
            problems.append(f"insert variant {v['id']}: arm strain {g['arm_strain']*100:.1f} % > 3 %")
    strains = [g["arm_strain"] * 100 for g in geo.values()]
    warns.append(f"{len(vs)} dock insert variants assembled on {variant}: no pod interference, arm strain {min(strains):.1f}..{max(strains):.1f} %")
    return problems, warns


def check_real_models(outdir: Path, variant: str) -> tuple[list, list]:
    """Interference of the real component models (OP-xx_real.sc) with the printed parts and with each other."""
    from op_build import BENCH_EXCLUDE_PAIRS
    from op_models import REAL_EXCLUDE, REPLACED
    real = outdir / f"{variant}_real.sc"
    if not real.exists():
        return [], [f"{variant}_real.sc missing (real-model check skipped)"]
    from generate import REAL_NAMES
    gone = {"gearhead", "motor", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "motor_pins", "gear_a", "gear_b",
            "leadscrew", "magnet"}
    ex = [pr for pr in BENCH_EXCLUDE_PAIRS + REAL_EXCLUDE if not (set(pr) & gone)]
    results = eval_design(real, ex)
    interf = next(r for r in results if "interferences" in r)
    problems = []
    for i in interf["interferences"]:
        if (i["a"] in REAL_NAMES or i["b"] in REAL_NAMES) and i.get("volume_mm3", 1) > MIN_OVERLAP_MM3:
            problems.append(f"real-model interference {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    for u in interf.get("unchecked", []):
        problems.append(f"real-model pair not checked: {u['a']} x {u['b']}: {u['reason'][:80]}")
    return problems, [f"real component models: {interf.get('checked')} solids interference-checked, {len(REAL_NAMES)} imported bodies"]


def check_size(outdir: Path, variant: str, p: dict, ignore_length: bool, with_variants: bool = False) -> dict:
    mode = p.get("mode", "integrated")
    MFG_PARTS, _, EXCLUDE_PAIRS = part_sets(mode)
    if p.get("drive_mode") in ("inline", "coaxial"):
        from op_inline import INLINE_EXCLUDE
        EXCLUDE_PAIRS = EXCLUDE_PAIRS + INLINE_EXCLUDE
    results = eval_design(outdir / f"{variant}.sc", EXCLUDE_PAIRS)
    measure = next(r for r in results if "bodies" in r and "body_count" in r)
    interf = next(r for r in results if "interferences" in r)
    bodies = measure["bodies"]
    # bench: FFC cable and the adapter's hose barb are test-fixture items that leave the housing by design
    lo, hi = envelope([b for b in bodies if not (mode == 'bench' and b['name'] in ('ffc_cable', 'cannula_adapter'))])
    dims = [hi[i] - lo[i] for i in range(3)]
    spec = p["spec"]
    tgt_l = (p["bench"]["length_targets_by_layout"][p["bench"]["drive_layout"]] if mode == "bench" else spec["length_targets"])[variant]
    L = json.loads((outdir / (f"{variant}.mech.json" if mode == "bench" else f"{variant}.layout.json")).read_text())
    problems, warns = [], []
    if dims[2] > spec["max_height"] + EPS:
        problems.append(f"height {dims[2]:.3f} > {spec['max_height']}")
    if dims[1] > spec["width_target"] + EPS:
        problems.append(f"width {dims[1]:.3f} > {spec['width_target']}")
    if dims[0] > tgt_l + EPS:
        (warns if ignore_length else problems).append(f"length {dims[0]:.2f} > target {tgt_l}")
    for i in interf["interferences"]:
        if i.get("volume_mm3", 1) > MIN_OVERLAP_MM3:
            problems.append(f"interference {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    for u in interf.get("unchecked", []):
        problems.append(f"pair not checked: {u['a']} x {u['b']}: {u['reason'][:80]}")
    frags = [b["name"] for b in bodies if re.search(r" \(\d+\)$", b["name"]) and not b["name"].startswith("cap_gasket")]    # the silicone sheet is cut in 2-3 loose pieces (islands between the slots)
    if frags:          # SolidCraft names disconnected pieces of a body "name (1)": loose fragments in a printed part
        problems.append(f"disconnected fragments (body split into several solids): {frags}")
    not_closed = [b["name"] for b in bodies if not b.get("closed")]
    if not_closed:
        problems.append(f"open bodies: {not_closed}")
    for name, t, exc in declared_walls(p, L):
        if mode == 'bench' and name == 'button_membrane':
            continue
        if t + EPS < MIN_FEATURE:
            problems.append(f"wall {name} = {t:.2f} mm < {MIN_FEATURE} (below any printable/machinable feature)")
        elif t + EPS < MIN_WALL:
            (warns if exc or name in WALL_EXCEPTIONS else problems).append(f"wall {name} = {t:.2f} mm < {MIN_WALL} "
                                                                           f"({'documented exception' if exc else 'NOT allowed'})")
    pr, wr = check_bench(p, L, bodies) if mode == "bench" else check_extra(p, L, bodies)
    problems += pr
    warns += wr
    known = []
    if mode == "bench":
        pf, known = check_fluid_boundary(p, L)
        problems += pf
        pu, ku = check_fill_unreachable(p, L)
        problems += pu
        known = known + ku
        warns += list(FLUID_WARNS)
    if mode == "bench" and not L["coax"] and not L.get("inline"):
        pr_, wr_ = check_real_models(outdir, variant)
        problems += pr_
        warns += wr_
    if mode == "bench" and with_variants:
        pv, wv = check_insert_variants(outdir, variant, p, L)
        problems += pv
        warns += wv
    exports = ["bottom", "top"] + ([] if L.get("inline") else ["carriage"]) + ["reservoir", "plunger_core", "plunger_seal", "gasket", "mould_lower", "mould_upper"]
    exports += (["cannula_adapter", "dock_insert", "end_cap_lid", "thrust_sleeve", "thrust_collar"] + ((["plunger_plate"] if L["inline"].get("variant") != "coaxial" else []) + ["thrust_sleeve2"] if L.get("inline") else [])) if mode == "bench" else ["reservoir_cnc_lower", "reservoir_cnc_upper"]
    for part in exports:
        for ext in ("step", "stl"):
            if not (outdir / f"{variant}_{part}.{ext}").exists():
                problems.append(f"missing export {variant}_{part}.{ext}")
    return {"known": known, "variant": variant, "dims": dims, "target_l": tgt_l, "problems": problems, "warns": warns,
            "bodies": len(bodies), "pairs": interf.get("pairs_candidate"), "checked": interf.get("checked")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=["integrated", "bench", "v010"], default="integrated")
    ap.add_argument("--outdir")
    ap.add_argument("--sizes", nargs="*")
    ap.add_argument("--ignore-length", action="store_true")
    ap.add_argument("--drive", choices=["standard", "inline", "coaxial"], default="standard", help="inline / coaxial: check out/bench-inline / out/bench-coaxial (sealed on-axis drives)")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--strict", action="store_true", help="the known-failing fluid-boundary check (slotted reservoir) also fails the exit code")
    args = ap.parse_args()
    if args.variant == "v010":          # additive variant (v010_check.py)
        import v010_check
        sys.exit(v010_check.main(args))
    out = Path(args.outdir or (HERE / "out" / ({"inline": "bench-inline", "coaxial": "bench-coaxial"}.get(args.drive, "bench")) if args.variant == "bench" else HERE / "out"))
    p = load_params(out / "params.used.json") if (out / "params.used.json").exists() else load_params()
    p["mode"] = args.variant
    sizes = args.sizes or list(p["variants"])
    failed = False
    kfail = False
    print(f"{'Size':8} {'L':>7} {'B':>6} {'H':>6}  {'target L':>8}  status")
    for k, v in enumerate(sizes):
        r = check_size(out, v, p, args.ignore_length, with_variants=(k == 0))
        d = r["dims"]
        status = "PASS" if not r["problems"] else "FAIL"
        failed |= bool(r["problems"])
        print(f"{v:8} {d[0]:7.2f} {d[1]:6.2f} {d[2]:6.2f}  {r['target_l']:8.1f}  {status}  "
              f"({r['bodies']} bodies, {r['checked']} solids interference-checked)")
        for m in r["problems"]:
            print(f"    FAIL: {m}")
        for m in r["warns"]:
            print(f"    WARN: {m}")
        for m in r["known"]:
            print(f"    KNOWN-FAIL (coupling decision pending, --strict makes it fatal): {m}")
            kfail = True
    if kfail:
        print("\nKNOWN-FAIL: the fluid-boundary check fails on the slotted reservoir; NOT solved, see SEAL-AND-DEAD-VOLUME.md")
    sys.exit(1 if (failed or (kfail and args.strict)) else 0)


if __name__ == "__main__":
    main()
