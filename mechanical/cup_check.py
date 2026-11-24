# SPDX-License-Identifier: LicenseRef-OpenPatch
"""`check.py --variant v010 --drive cup`: envelope, interference, rod never wet, plunger reaches the front wall, fill septum unreachable when docked, dock budget, thrust."""
from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

import check as C
import op_cup
import op_cup_dock as dock
from op_cmds import Script
from op_layout import HERE, stadium_area

TARGET_L = {"OP-100": 45.0, "OP-200": 54.0}                # spec 2b (owner decision 2026-11-19): OP-100 <= 45, OP-200 <= 54 with the full 200 U
THRUST_MIN_N = 5.0


def run_extra(sc: Path, s: Script, exclude: list) -> dict:
    """Append tool bodies (wet volumes, dome sweep) to the saved design and return the interference result."""
    cmds = s.dumps() + [{"command": "inspect.interference", "params": {"exclude_pairs": exclude}}]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(cmds, fh)
        tmp = fh.name
    res = subprocess.run([C.CLI, "run", tmp, "--in", str(sc), "--results", "--quiet"], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if res.returncode != 0:
        raise SystemExit(res.stdout + res.stderr)
    return next(r for r in json.loads(res.stdout) if "interferences" in r)


def screw_eta(mu: float, d: float = 1.6, pitch: float = 0.35) -> float:
    """Efficiency of a 60 deg metric thread driving the nut: tan(lead) / tan(lead + atan(mu / cos 30)), pitch diameter d - 0.6495 p."""
    d2 = d - 0.6495 * pitch
    lam = math.atan(pitch / (math.pi * d2))
    return math.tan(lam) / math.tan(lam + math.atan(mu / math.cos(math.radians(30.0))))


def thrust(p: dict, L: dict, lubricated: bool | None = None) -> dict:
    """NFP-608-26.45 pull-out torque -> rod -> screw + forward thrust face (collar on the PTFE shim on the bush) -> plunger force vs. seal friction + occlusion pressure
    (+ vacuum if the shell is sealed without a vent).  Challenge review #4: the collar friction torque mu_c F r_c was missing.  Estimates, VERIFY on the bench."""
    c, g = p["cup"], p["cup"]["gears"]
    rd, co, bu = c["rod"], c["collar"], c["bush"]
    lub = rd.get("lubricated", False) if lubricated is None else lubricated
    T_gb = 1.6 * 9.80665e-3 * 10.0 * 26.45 * 0.64                 # N mm at the gearhead output (1.6 gf cm pull-out x 26.45 x 0.64, parts.md)
    eta_b, pitch = 0.9, p["drive"]["screw_pitch"]
    mu_t = rd["mu_thread_greased"] if lub else rd["mu_thread_dry"]
    eta_s = screw_eta(mu_t, rd["d"], pitch)
    T_rod = T_gb * (g["z_rod"] / g["z_motor"]) * eta_b
    sh = co.get("shim")
    mu_c = sh["mu"] if (sh and lub) else co["mu_dry"]
    r1, r2 = max(bu["id"], sh["id"] if sh else 0.0) / 2, min(co["od"], bu["od"]) / 2
    r_c = 2.0 / 3.0 * (r2 ** 3 - r1 ** 3) / (r2 ** 2 - r1 ** 2)  # mean friction radius of the annular thrust face
    F = T_rod / (pitch / (2 * math.pi * eta_s) + mu_c * r_c)
    F_no_collar = 2 * math.pi * eta_s * T_rod / pitch
    A = L["bore_area"]
    perim = 2 * (L["bore_w"] - L["bore_h"]) + math.pi * L["bore_h"]
    beads = len(p["seal"]["variants"][p["seal"]["active_variant"]]["rings"])
    f_seal = 1.6 * perim / (2 * (16.0 - 5.0) + math.pi * 5.0) * (1.0 if beads == 1 else 1.7)   # bench breakaway ~1.6 N (single bead) at the 16 x 5 perimeter (spec 3b), twin bead 1.7x
    f_occ = 30e3 * A * 1e-6                                       # 30 kPa occlusion alarm threshold
    f_vac = 0.0 if c.get("vent", {}).get("hole_d") else 16e3 * A * 1e-6     # sealed shell without vent: about -16 kPa at empty
    need = f_seal + f_occ + f_vac
    return {"T_rod_Nmm": round(T_rod, 2), "F_avail_N": round(F, 2), "F_no_collar_N": round(F_no_collar, 2), "eta_screw": round(eta_s, 3), "mu_thread": mu_t, "mu_collar": mu_c,
            "r_collar_mm": round(r_c, 3), "lubricated": lub, "F_seal_N": round(f_seal, 2), "F_occ_N": round(f_occ, 2), "F_vac_N": round(f_vac, 2), "F_need_N": round(need, 2),
            "F_need_SF2_N": round(2 * need, 1), "margin": round(F / need, 2), "perimeter_mm": round(perim, 1), "area_mm2": round(A, 1), "beads": beads}


def stl_inside(path: Path):
    """Point-in-solid test on an exported STL (binary or ASCII): ray along +Z, crossing parity.  Returns a function (x, y, z) -> bool."""
    import struct
    data = path.read_bytes()
    tris = []
    if data[:5] == b"solid" and b"facet" in data[:400]:
        vs = [tuple(map(float, ln.split()[1:4])) for ln in data.decode("ascii", "replace").splitlines() if ln.strip().startswith("vertex")]
        tris = [vs[i:i + 3] for i in range(0, len(vs) - 2, 3)]
    else:
        n = struct.unpack("<I", data[80:84])[0]
        for k in range(n):
            v = struct.unpack("<12f", data[84 + 50 * k:84 + 50 * k + 48])
            tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))

    def inside(x: float, y: float, z: float) -> bool:
        x, y = x + 1.37e-4, y + 0.91e-4                                       # jitter: keep the ray off mesh edges / vertices on the axis planes
        cnt = 0
        for (a, b, c_) in tris:
            if min(a[0], b[0], c_[0]) > x or max(a[0], b[0], c_[0]) < x or min(a[1], b[1], c_[1]) > y or max(a[1], b[1], c_[1]) < y:
                continue
            d = (b[0] - a[0]) * (c_[1] - a[1]) - (c_[0] - a[0]) * (b[1] - a[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((b[0] - x) * (c_[1] - y) - (c_[0] - x) * (b[1] - y)) / d
            l2 = ((c_[0] - x) * (a[1] - y) - (a[0] - x) * (c_[1] - y)) / d
            l3 = 1.0 - l1 - l2
            if min(l1, l2, l3) < 0:
                continue
            if l1 * a[2] + l2 * b[2] + l3 * c_[2] > z:
                cnt += 1
        return cnt % 2 == 1
    return inside


def fluid_paths(outdir: Path, variant: str, p: dict, L: dict) -> tuple[list, list]:
    """Challenge review #1: probe the EXPORTED tank STL along the fill path (septum pocket -> channel -> bore) and the outlet (bore -> hub seat -> front face):
    every probe point must be outside the PP (open), and the path must end inside the bore."""
    fl, K = p["cup"]["fill"], L["dock"]
    stl = outdir / f"{variant}_reservoir.stl"
    if not stl.exists():
        return [f"fill/outlet probe: {stl.name} missing"], []
    ins = stl_inside(stl)
    z0, zch = L["z_tank0"], L["z_tank0"] + fl["chan_dz"]
    xs0 = L["x_s"] - 0.05                                                    # inside the channel, off its end face (the channel runs -X from the septum axis to the bore)
    probes = {"fill (septum pocket -> channel -> bore)": [(xs0, L["y_s"], z) for z in (z0 + fl["septum_h"] - 0.1, z0 + fl["septum_h"] - 0.02, z0 + fl["septum_h"] + 0.05, zch)]
              + [(xs0 + (L["x_in"] - 0.05 - xs0) * k / 20.0, L["y_s"], zch) for k in range(1, 21)],
              "outlet (bore -> hub seat -> front face)": [(L["x_in"] - 0.05 + (L["x_t0"] + 0.02 - L["x_in"]) * k / 24.0, L["y_r"], K["z_n"]) for k in range(25)]}
    prob, note = [], []
    for nm, pts in probes.items():
        blocked = [pt for pt in pts if ins(*pt)]
        if blocked:
            prob.append(f"{nm} BLOCKED in the exported STL at x {blocked[0][0]:.3f} (y {blocked[0][1]:.2f}, z {blocked[0][2]:.2f}): {len(blocked)} of {len(pts)} probe points inside PP")
        else:
            note.append(f"{nm}: open over {len(pts)} STL probe points (x {min(q[0] for q in pts):.2f}..{max(q[0] for q in pts):.2f})")
    return prob, note


def gear_mesh(p: dict, L: dict, ga: dict, gb: dict, mg: dict, sh: dict) -> tuple[list, list]:
    """Miter pair (module m, z : z, 90 deg): pitch geometry, apex alignment of the two CAD envelopes, engaged face width, clearances to the magnet and the motor shaft end."""
    g, mgp, dr = p["cup"]["gears"], p["cup"]["magnet"], p["drive_nfp"]
    prob, note = [], []
    m, za, zb = g["module"], g["z_motor"], g["z_rod"]
    if za != zb:
        prob.append(f"miter pair needs z_motor == z_rod (got {za} : {zb})")
    rp = m * za / 2.0
    dk = m * math.cos(math.radians(45.0))
    tip = 2 * (rp + dk)
    if abs(tip - g["tip_od"]) > 0.015:
        prob.append(f"gear tip OD {g['tip_od']} != m (z + 2 cos 45) = {tip:.3f}")
    rc = rp / math.sin(math.radians(45.0))
    # the CAD envelopes carry the right apex: gear A front measured from the rod axis, gear B front from the motor axis
    fa, fb = ga["min"][1] - L["y_r"], gb["min"][0] - L["xc"]
    if abs(fa - g["front_a"]) > 0.011 or abs(fb - g["front_b"]) > 0.011:
        prob.append(f"gear front faces off the apex: A {fa:.3f} (param {g['front_a']}), B {fb:.3f} (param {g['front_b']})")
    for nm, bx in (("A", ga), ("B", gb)):
        dims = [bx["max"][i] - bx["min"][i] for i in range(3)]
        d_tip = max(dims[0], dims[2]) if nm == "A" else max(dims[1], dims[2])
        if abs(d_tip - tip) > 0.02:
            prob.append(f"gear {nm} envelope OD {d_tip:.3f} != tip OD {tip:.3f}")
    face = rp - max(g["front_a"], g["front_b"])
    if face < 0.5:
        prob.append(f"engaged face width {face:.2f} mm < 0.5")
    # gear A front faced: radius of the angle magnet (rod axis) must keep >= 0.15 mm to it
    cl_mg = g["front_a"] - mgp["d"] / 2
    if cl_mg < 0.15 - 1e-9:
        prob.append(f"angle magnet rim only {cl_mg:.2f} mm from gear A front (< 0.15)")
    # motor shaft end (inside gear A) vs the gear B envelope: shaft end plane at front_a + 0.15 from the rod axis, shaft radius r; gear B tip-cone radius at its x
    r_sh = dr["shaft_d"] / 2
    y_end = g["front_a"] + 0.15
    rB = r_sh + dk                                           # gear B envelope radius at a = shaft radius (x = xc + r_sh)
    cl_sh = y_end - rB
    if cl_sh < 0.05:
        prob.append(f"motor shaft end only {cl_sh:.2f} mm from the gear B envelope")
    # tooth bending (Lewis, brass), full gearhead pull-out torque at the mean pitch radius, virtual tooth number z / cos 45
    T = 1.6 * 9.80665e-3 * 10.0 * 26.45 * 0.64
    r_m = rp - (rp - max(g["front_a"], g["front_b"])) / 2
    b_slant = face / math.cos(math.radians(45.0))
    Ft = T / r_m
    Y = 0.302                                                # Lewis form factor, z_v = 17
    sig = Ft / (b_slant * m * Y)
    note.append(f"miter pair m{m} z{za}:z{zb} 1:1 (ratio 1.00): pitch d {2 * rp:.2f}, tip OD {tip:.2f}, cone distance {rc:.2f}; faces A {g['front_a']} (faced from {g['drawing']['front']}) / B {g['front_b']}, backs A {g['back_a']} (faced from {g['drawing']['back_2mm_bore']}) / B {g['back_b']}; "
                f"engaged face {face:.2f} mm (slant {b_slant:.2f}); magnet rim to gear A {cl_mg:.2f}; shaft end to gear B {cl_sh:.2f}; Lewis tooth bending {sig:.0f} MPa at the {T:.2f} N mm gearhead limit (brass ~ 100+)")
    if sig > 80:
        prob.append(f"tooth bending {sig:.0f} MPa > 80")
    return prob, note


def check_size(outdir: Path, variant: str, p: dict) -> dict:
    sc = outdir / f"{variant}.sc"
    L = json.loads((outdir / f"{variant}.mech.json").read_text())
    K = L["dock"]
    problems, warns, targets = [], [], []
    present = C._present_bodies(sc)
    excl = [pr for pr in op_cup.EXCLUDE_PAIRS if all(n in present for n in pr)]
    results = C.eval_design(sc, op_cup.EXCLUDE_PAIRS)
    measure = next(r for r in results if "bodies" in r and "body_count" in r)
    interf = next(r for r in results if "interferences" in r)
    bodies = measure["bodies"]
    by = {b["name"]: b for b in bodies}
    lo, hi = C.envelope(bodies)
    dims = [hi[i] - lo[i] for i in range(3)]
    if dims[2] > p["spec"]["max_height"] + 1e-6:
        problems.append(f"height {dims[2]:.3f} > {p['spec']['max_height']}")
    if dims[1] > p["spec"]["width_target"] + 1e-6:
        targets.append(f"width {dims[1]:.2f} > spec width target {p['spec']['width_target']} (+{dims[1] - p['spec']['width_target']:.2f}): lane 1 = wide tank + lane 2")
    if dims[0] > TARGET_L[variant] + 1e-6:
        targets.append(f"length {dims[0]:.2f} > target {TARGET_L[variant]} (+{dims[0] - TARGET_L[variant]:.2f})")
    for i in interf["interferences"]:
        if i.get("volume_mm3", 1) > C.MIN_OVERLAP_MM3:
            problems.append(f"interference {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    for u in interf.get("unchecked", []):
        problems.append(f"pair not checked: {u['a']} x {u['b']}: {u['reason'][:80]}")
    frags = [n for n in by if re.search(r" \(\d+\)$", n)]
    if frags:
        problems.append(f"disconnected fragments: {frags}")
    if [n for n, b in by.items() if not b.get("closed")]:
        problems.append(f"open bodies: {[n for n, b in by.items() if not b.get('closed')]}")
    for n in op_cup.PART_NAMES:
        if n not in by:
            problems.append(f"body missing: {n}")
    for n in ("carriage", "tongue_shim", "gear_c", "gear_d", "idler_pin", "leadscrew", "drive_screw", "end_cap", "end_cap_lid", "cap_gasket", "dock_insert", "pod_board", "thrust_sleeve"):
        if n in by:
            problems.append(f"removed part present (simplicity rule): {n}")
    if problems and any(n.startswith("body missing") for n in problems):
        return {"variant": variant, "dims": dims, "problems": problems, "warns": warns, "targets": targets, "bodies": len(bodies), "checked": interf.get("checked"), "L": L}
    bb = lambda n: by[n]["bbox"]
    ctr = lambda n, ax: (bb(n)["min"][ax] + bb(n)["max"][ax]) / 2
    zc, yr, w = L["zc"], L["y_r"], L["wall"]
    # ---- one rod on the tank axis, rotating + axially fixed; nut / plunger bore on the same axis
    for n in ("rod", "nut", "bush_rod", "magnet", "thrust_collar", "gear_b", "plunger_core"):
        if abs(ctr(n, 1) - yr) > 1e-3 or abs(ctr(n, 2) - zc) > 1e-3:
            problems.append(f"{n} not on the tank axis (y {ctr(n, 1):.3f}, z {ctr(n, 2):.3f})")
    bs, rd, mg, tm, cl, gbb = bb("bush_rod"), bb("rod"), bb("magnet"), bb("hall_tmag"), bb("thrust_collar"), bb("gear_b")
    # axial load path (no sleeve): forward thrust (plunger pushed out, rod pulled -X): nut -> rod thread -> collar (bonded on the rod) -> bush rear face -> bush (bonded in the U rib) -> housing;
    # reverse thrust (plunger pulled back, rod pushed +X): nut -> rod thread -> thread in gear B hub (tapped M1.6 + retaining compound) -> hub back face -> bush front face -> bush -> housing
    shb = bb("collar_shim")
    if abs(shb["min"][0] - bs["max"][0]) > 0.011 or not (0.0 <= cl["min"][0] - shb["max"][0] <= 0.15):
        problems.append(f"collar not seated on the PTFE shim on the bush tank-side face (shim gap {shb['min'][0] - bs['max'][0]:.3f}, collar gap {cl['min'][0] - shb['max'][0]:.3f}): -X thrust has no stop")
    if not (0.0 <= bs["min"][0] - gbb["max"][0] <= 0.15):
        problems.append(f"gear B hub back face not seated on the bush motor-side face (gap {bs['min'][0] - gbb['max'][0]:.3f}): +X (reverse) thrust has no stop")
    cg_, bu_ = p["cup"]["gears"], p["cup"]["bush"]
    a_hub = math.pi * ((cg_["hub_b_d"] / 2) ** 2 - (bu_["id"] / 2) ** 2)
    a_col = math.pi * ((p["cup"]["collar"]["od"] / 2) ** 2 - (bu_["id"] / 2) ** 2)
    if cg_["hub_b_d"] > bu_["od"] + 1e-9 or p["cup"]["collar"]["od"] > bu_["od"] + 1e-9:
        problems.append("gear B hub / collar overhang the bush OD: bearing face not fully on the bush")
    if min(a_hub, a_col) < 1.5:
        problems.append(f"thrust bearing face too small (hub {a_hub:.2f} mm2, collar {a_col:.2f} mm2 < 1.5)")
    warns.append(f"axial load path (no thrust sleeve): forward = nut -> rod -> collar (bonded on the rod, bearing {a_col:.2f} mm2) -> bush rear face; reverse = nut -> rod -> M1.6 thread in the gear B hub (retaining compound) -> hub back face (bearing {a_hub:.2f} mm2) -> bush front face; bush bonded in the U rib; the magnet carries no thrust")
    if abs(mg["max"][0] - gbb["min"][0]) > 0.011:
        problems.append("magnet not on the rear (motor-side) face of gear B")
    if abs(rd["min"][0] - gbb["min"][0]) > 0.011:
        problems.append("rod does not end flush with gear B (rod must end at gear B)")
    if rd["max"][0] < cl["max"][0]:
        problems.append("rod does not span gear B .. collar")
    gap_y = mg["min"][1] - tm["max"][1]
    if gap_y < p["cup"]["tmag"]["gap"] - 1e-6:
        problems.append(f"TMAG only {gap_y:.2f} mm from the magnet edge (< {p['cup']['tmag']['gap']})")
    behind = [n for n, b in by.items() if n not in ("bottom", "top", "lid_gasket", "usb_gasket") and not n.startswith("ko_") and b["bbox"]["min"][0] < L["xc"] - 3.0 - 0.011]
    if behind:
        problems.append(f"parts behind the motor column (nothing may be left of it): {behind}")
    # ---- exactly two gears, meshing as a miter pair (axes cross at the apex)
    ga, gb = bb("gear_a"), bb("gear_b")
    if abs((ga["min"][0] + ga["max"][0]) / 2 - L["xc"]) > 1e-3:
        problems.append("motor bevel gear not centred on the apex x")
    gears = [n for n in by if n.startswith("gear") and n != "gearhead"]
    if sorted(gears) != ["gear_a", "gear_b"]:
        problems.append(f"gear count != 2: {gears}")
    pm, nm_ = gear_mesh(p, L, ga, gb, mg, by["motor_shaft"]["bbox"])
    problems += pm
    warns += nm_
    # nut pocket: real brass DIN 934 M1.6 is AF 3.5; pocket = AF + nut_clr, walls around the hex corners must stay >= 0.4 in the plunger section
    af_p = p["cup"]["nut"]["af"] + p["cup"]["plunger"]["nut_clr"]
    corner = af_p / math.cos(math.radians(30.0))
    wall = (L["bore_h"] - 2 * p["cup"]["plunger"]["clr"] - corner) / 2
    if wall < 0.4:
        problems.append(f"plunger wall around the nut hex pocket {wall:.2f} < 0.4 (AF {af_p:.2f}, across corners {corner:.2f})")
    if abs(p["drive_nfp"]["nut_af"] - 3.5) > 1e-9:
        problems.append("nut pocket not built for AF 3.5")
    warns.append(f"nut pocket AF {af_p:.2f} (nut AF {p['cup']['nut']['af']}, DIN 934 M1.6 brass h {p['cup']['nut']['len']}), across corners {corner:.2f}, plunger wall {wall:.2f} mm")
    # ---- plunger: cup length >= stroke, reaches the front wall, rod tip inside the cup at both ends, rod never wet
    s = L["stroke"]
    if L["L_pl"] < s:
        problems.append(f"plunger length {L['L_pl']:.2f} < stroke {s}")
    dead = p["cup"]["plunger"]["dead"]
    if L["x_in"] - L["x_pf_empty"] > 0.05 + 1e-9:
        problems.append(f"plunger does not reach the front wall at empty (gap {L['x_in'] - L['x_pf_empty']:.3f})")
    fw, clr = p["cup"]["plunger"]["front_wall"], p["cup"]["plunger"]["tip_clear_full"]
    tip = L["x_tip"]
    for st, xpf in (("full", L["x_pf_full"]), ("empty", L["x_pf_empty"])):
        gap = (xpf - fw) - tip
        if gap < clr - 1e-6:
            problems.append(f"rod tip only {gap:.2f} mm behind the cup bottom at {st} (< {clr})")
    nut_front_e = L["x_pr"] + L["nut_zone"] + L["stroke"]
    if not (p["cup"]["plunger"]["tip_in_nut_empty"] - 1e-6 <= tip - nut_front_e <= p["cup"]["plunger"]["tip_in_nut_empty"] + 1e-6):
        problems.append(f"rod tip not {p['cup']['plunger']['tip_in_nut_empty']} mm beyond the nut front face at empty")
    if tip - nut_front_e < 0.0:
        problems.append("nut not fully engaged at empty")
    if p["cup"]["plunger"]["bore_d"] / 2 <= p["cup"]["rod"]["d"] / 2:
        problems.append("rod radius >= plunger bore radius")
    wet = Script()
    wet.stadium("wet_full", (L["x_pf_full"], L["x_in"]), yr, zc, L["bore_w"], L["bore_h"])
    wet.stadium("wet_empty", (L["x_pf_empty"] - 0.001, L["x_in"]), yr, zc, L["bore_w"], L["bore_h"])
    hh = p["cup"]["dock"]["head"]
    open_end = p["cup"]["dock"].get("open_end")
    x_sw = L["length"] + 1.0 if open_end else K["x_d"] + K["R"] + K["slide"]          # open end: the head slides in from outside the end face
    wet.box("dome_sweep", (K["x_f"], x_sw), (K["y_c"] - K["R"], K["y_c"] + K["R"]), (0.0, hh["B_dome_h"] + 0.05))
    wet.box("plate_sweep", (K["plate_x"][0] + 0.2, x_sw if open_end else K["plate_x"][1] - 0.2), (K["y_c"] - hh["base_w"] / 2, K["y_c"] + hh["base_w"] / 2), (0.0, hh["base_t"]))
    ex2 = excl + [["wet_full", "wet_empty"], ["dome_sweep", "plate_sweep"]]
    ok_dock = ["cannula_adapter", "dock_magnet", "dock_clip", "needle", "needle_hub", "needle_guard"]
    ex2 += [[a, b] for a in ("dome_sweep", "plate_sweep") for b in ok_dock]
    ir = run_extra(sc, wet, ex2)
    for i in ir["interferences"]:
        if i.get("volume_mm3", 1) <= C.MIN_OVERLAP_MM3:
            continue
        a, b = i["a"], i["b"]
        if "wet_" in a + b and "rod" in (a, b):
            problems.append(f"ROD INSIDE THE WET VOLUME: {a} x {b}")
        elif "wet_" in a + b:
            problems.append(f"wet volume overlaps {a if 'wet_' not in a else b}: {i['volume_mm3']:.3f} mm3")
        elif "sweep" in a + b:
            problems.append(f"dome/base-plate slide path blocked by {a if 'sweep' not in a else b}: {i['volume_mm3']:.3f} mm3")
    for u in ir.get("unchecked", []):
        if "wet_" in u["a"] + u["b"] or "sweep" in u["a"] + u["b"]:
            problems.append(f"extra pair not checked: {u['a']} x {u['b']}")
    # ---- tank: closed walls (no slot), volume equals the closed-bore model minus the small outlet / fill channels
    A_out, A_in = stadium_area(L["res_w_out"], L["res_h_out"]), L["bore_area"]
    fz, fl = p["reservoir_frozen"], p["cup"]["fill"]
    v_exp = A_out * (L["x_t0"] - L["x_dry"]) - A_in * (L["x_in"] - L["x_dry"])
    vol = by["reservoir"]["volume_mm3"]
    if not (v_exp - 20.0 <= vol <= v_exp + 0.5):
        problems.append(f"tank volume {vol:.1f} mm3 outside closed-bore model {v_exp - 20.0:.1f}..{v_exp:.1f}: unexpected opening (slot) in the wall")
    rb = bb("reservoir")
    if abs(rb["min"][0] - L["x_dry"]) > 1e-3 or abs(rb["max"][0] - L["x_t0"]) > 1e-3:
        problems.append("tank x extent differs from the layout")
    # ---- fill septum: underside, covered by the patch, not reachable while docked (H14)
    hx, hy = L["x_s"], L["y_s"]
    r = fl["hole_d"] / 2 + fl["needle_d"] / 2
    vc = p["velcro"]
    px0, px1, py0, py1 = vc["margin_x"], L["length"] - vc["margin_x"], vc["y0"], L["width"] - vc["y0"]
    inside = px0 <= hx - r and hx + r <= px1 and py0 <= hy - r and hy + r <= py1
    win = (K["plate_x"][0], K["plate_x"][1], K["y_c"] - K["half"], K["y_c"] + K["half"])
    in_win = not (hx + r < win[0] or hx - r > win[1] or hy + r < win[2] or hy - r > win[3])
    if not inside:
        problems.append("H14: fill-septum hole is not inside the Velcro patch footprint")
    if in_win:
        problems.append("H14: fill-septum hole lies in the dock window (reachable while docked)")
    if by["septum"]["bbox"]["min"][2] < L["z_tank0"] - 0.01 or by["septum"]["bbox"]["max"][2] > L["z_tank0"] + fl["septum_h"] + 1e-6:
        problems.append("fill septum not on the underside of the tank")
    fp, fn = fluid_paths(outdir, variant, p, L)
    problems += fp
    warns += fn
    # ---- dock: needle covered, dome path, clips, hall, footprint budget
    nd = by["needle"]["bbox"]
    if K["guard_free_end"] - K["x_tip"] < 0.3:
        problems.append("undocked: needle tip not recessed by >= 0.3 mm inside the extended guard")
    if nd["min"][2] < 1.0:
        problems.append("needle reaches below z 1.0 (exposed under the floor)")
    if abs(nd["max"][0] - K["x_tip"]) > 1e-3 or abs(ctr("needle", 1) - K["y_c"]) > 1e-3:
        problems.append("needle axis / tip position mismatch")
    if abs(by["cannula_adapter"]["bbox"]["max"][0] - (K["x_d"] + hh["base_l"] / 2)) > 1e-3:
        problems.append("adapter position mismatch")
    dpen = nd["max"][0] - K["x_face"]
    if abs(dpen - hh["needle_depth"]) > 0.02:
        problems.append(f"needle penetration {dpen:.3f} != {hh['needle_depth']}")
    if L["lane2_fit"]["need_x"] > L["lane2_fit"]["have_x"] + 1e-6:
        problems.append(f"lane 2 contents ({L['lane2_fit']['need_x']:.1f} mm) longer than lane 1 ({L['lane2_fit']['have_x']:.1f} mm)")
    if not (3.0 <= K["slide"] <= 4.0):
        problems.append(f"slide travel {K['slide']} outside 3..4 mm")
    dkp = p["cup"]["dock"]
    if open_end and K["in_pod_reserve"] == 0.0 and abs(K["pocket_len"] - (2 * dkp["clr"] + hh["A_dome_d"])) > 1e-6:
        problems.append(f"open-end pocket {K['pocket_len']:.2f} != clr + A + clr")
    if open_end and K["in_pod_reserve"] == 0.0:
        warns.append(f"dock pocket {K['pocket_len']:.2f} = 0.2 + A {hh['A_dome_d']} (TODO-MEASURE) + 0.2; the {K['slide']} mm slide starts with the dome {K['slide'] + K['R'] - (K['x_far'] - K['x_d']) - w:.2f} mm outside the end face (open end, swept free above)")
    if K["pocket_len"] > 12.0 + 1e-9 or 2 * K["half"] > 10.0 + 1e-9:
        problems.append(f"dock pocket {K['pocket_len']:.1f} x {2 * K['half']:.1f} exceeds the 12 x 10 budget")
    plate_len = K["plate_x"][1] - K["plate_x"][0]
    if plate_len > 12.0:
        warns.append(f"base-plate window {plate_len:.1f} mm long (> 12): base plate {p['cup']['dock']['head']['base_l']} + 2 x {p['cup']['dock']['clr']} clearance + {K['slide']} slide; <= 12 needs a base plate <= {12 - 0.4 - K['slide']:.1f} mm (TODO-MEASURE)")
    st = dock.clip_stress(p, K)
    if st["sigma_need"] > p["cup"]["dock"]["clip"]["allow_MPa"]:
        problems.append(f"dock spring bending stress {st['sigma_need']:.0f} MPa > allowable {p['cup']['dock']['clip']['allow_MPa']}")
    warns.append(f"dock L-springs 301 FH {p['cup']['dock']['clip']['t']} mm: arm {st['arm_len']:.1f} mm, needed travel {st['need_travel']:.2f} -> {st['sigma_need']:.0f} MPa (allow {p['cup']['dock']['clip']['allow_MPa']}), tip force {st['F_need_N']:.3f} N/clip; "
                 f"1.8 mm travel -> {st['sigma_1p8']:.0f} MPa; a 3.5 mm arm allows only {st['short_arm_3p5_travel']:.2f} mm, 1.8 mm needs >= {st['arm_for_1p8']:.1f} mm")
    hw = dock.hall_window(p)
    if hw["assert_radius_mm"] > 0.8 or hw["assert_radius_mm"] <= 0.0:
        problems.append(f"dock hall asserts within {hw['assert_radius_mm']} mm of the final position (> 0.8): not only when slid + latched")
    warns.append(f"dock hall (dipole model, VERIFY): B0 {hw['B0_mT']} mT, Bop {hw['bop_mT']} mT -> asserts only within {hw['assert_radius_mm']} mm of the final position (slide {hw['slide_mm']} mm)")
    # ---- pocket-mouth seal (challenge review #5): plate covers the walls + roof end faces, squeeze, hole clears the guard; hidden vent
    ms = p["cup"]["dock"]["mouth_seal"]
    mg_ = bb("mouth_gasket")
    hy_ = K["half"] + p["cup"]["dock"]["pocket_wall"]
    z_rt = hh["B_dome_h"] + p["cup"]["dock"]["clr"] + p["cup"]["dock"]["roof"]
    if abs(mg_["min"][0] - L["x_t0"]) > 1e-3 or abs(mg_["max"][0] - K["x_bf"]) > 1e-3 or mg_["min"][1] > L["y_r"] - hy_ + 1e-3 or mg_["max"][1] < L["y_r"] + hy_ - 1e-3 or mg_["max"][2] < z_rt - 1e-3:
        problems.append("mouth seal does not span the tank face .. pocket mouth (walls + roof): open seam into the pod")
    sq_m = 1 - ms["gap"] / ms["t_free"]
    if not (0.1 <= sq_m <= 0.3):
        problems.append(f"mouth seal squeeze {sq_m:.0%} outside 10-30 %")
    if ms["hole_d"] < p["cup"]["dock"]["guard"]["od"] + 0.2 or ms["hole_d"] / 2 > p["cup"]["dock"]["head"]["recess_d"] / 2:
        problems.append("mouth seal hole does not clear the needle guard (or exceeds the septum recess)")
    vt = p["cup"]["vent"]
    vm = bb("vent_membrane")
    if vt["disc_d"] < vt["hole_d"] + 1.0 or vm["max"][1] > L["y_r"] - hy_ + 1e-3:
        problems.append("vent membrane does not cover the vent hole with >= 0.5 mm bond rim on the inner wall face")
    warns.append(f"pocket-mouth seal plate {2 * hy_:.1f} x {z_rt - L['z_tank0']:.1f} x {ms['t_free']} (Z4) in the {ms['gap']} gap tank face .. pocket walls + roof: squeeze {sq_m:.0%}; "
                 f"vent d{vt['hole_d']} through the -Y pocket wall at x {K['x_bf'] + vt['dx_bf']:.2f}, z {vt['z']}, ePTFE disc d{vt['disc_d']} inside (no vacuum on the plunger)")
    # ---- needle vs head septum: worst-case radial stack against the capture radius (recess d - guard OD) / 2 (challenge review section 4)
    hb_ = p["cup"]["dock"]["hub"]
    play = (hb_["id"] - p["needle"]["od"]) / 2
    free_len = K["x_tip"] - K["x_hub"][1]
    n_off = hb_["seat_tol"] + play + play / hb_["len"] * free_len        # seat position + radial play + tilt over the free length
    lat_spring = p["cup"]["dock"]["clip"]["arm_inner_clr"]
    lat_plate = K["half"] - hh["base_w"] / 2
    z_unc = abs(3.0 - hh["septum_z"])                                  # measurement sheet placeholder C = 3.0 vs CAD 2.6 (TODO-MEASURE)
    cap = (hh["recess_d"] - p["cup"]["dock"]["guard"]["od"]) / 2
    stack = n_off + lat_spring + z_unc
    stack_rss = math.sqrt(n_off ** 2 + lat_spring ** 2 + z_unc ** 2)
    stack_plate = n_off + lat_plate + z_unc
    if stack > cap + 1e-6:
        problems.append(f"needle vs septum worst case {stack:.2f} > capture {cap:.2f}")
    warns.append(f"needle vs head septum: needle tip off axis {n_off:.3f} (seat +-{hb_['seat_tol']}, play {play:.3f}, tilt over {free_len:.2f} free), dome lateral +-{lat_spring} (spring arms; base plate alone +-{lat_plate:.1f}), "
                 f"septum height unknown {z_unc:.1f} (C 3.0 sheet vs 2.6 CAD): worst case {stack:.2f} / RSS {stack_rss:.2f} vs capture {cap:.2f} (recess d{hh['recess_d']} - guard d{p['cup']['dock']['guard']['od']}); "
                 f"without the spring centring {stack_plate:.2f}{' > capture: measure C' if stack_plate > cap else ''}")
    # ---- reserved volumes inside the cavity, not overlapping each other (interference test above) 
    for n in op_cup.KEEPOUT:
        b = bb(n)
        if b["min"][0] < w - 1e-6 or b["max"][0] > L["length"] - w + 1e-6 or b["min"][1] < w - 1e-6 or b["max"][1] > L["width"] - w + 1e-6 or b["max"][2] > L["height"] - w + 1e-6:
            problems.append(f"keep-out {n} outside the cavity")
    # ---- thrust / U per step
    th = thrust(p, L)
    thd = thrust(p, L, lubricated=False)
    if th["F_avail_N"] < THRUST_MIN_N:
        problems.append(f"thrust {th['F_avail_N']} N < {THRUST_MIN_N} N")
    if th["F_avail_N"] < 1.5 * th["F_need_N"]:
        problems.append(f"thrust margin {th['margin']:.2f}x < 1.5x: no bought miter pair with a ratio < 1 exists (BUY-LIST 0), raise the screw efficiency (lubricant) or lower the collar friction")
    warns.append(f"thrust margin {th['margin']:.2f}x (greased thread mu {th['mu_thread']} -> eta {th['eta_screw']}, PTFE shim mu {th['mu_collar']} at r {th['r_collar_mm']}: available {th['F_avail_N']} N "
                 f"[{th['F_no_collar_N']} N without the collar term] / needed {th['F_need_N']} N = seal {th['F_seal_N']} ({th['beads']} bead) + 30 kPa {th['F_occ_N']} + vacuum {th['F_vac_N']} (vented))")
    warns.append(f"thrust DRY fallback (no grease, no shim): thread mu {thd['mu_thread']} -> eta {thd['eta_screw']}, collar mu {thd['mu_collar']}: {thd['F_avail_N']} N = {thd['margin']:.2f}x: "
                 f"the lubrication + PTFE shim are REQUIRED (ASSEMBLY-CUP step 2)")
    # rib / bush load path (estimates): bush bonded (CA) in the U rib bore, half of its surface carries the load; rib = cantilever wall from the floor
    bu_, cl_ = p["cup"]["bush"], p["cup"]["collar"]
    F = th["F_avail_N"]
    a_bond = math.pi * bu_["od"] / 2 * bu_["len"]
    b_rib = bu_["od"] + 2 * bu_["rib_wall"]
    arm = zc - 0.64 * bu_["od"] / 2 - w
    sig_rib = 6 * F * arm / (b_rib * bu_["len"] ** 2)
    warns.append(f"bush / rib at the available {F} N: bond shear {F / a_bond:.1f} MPa on {a_bond:.1f} mm2 (CA on brass / PA12 ~ 3-8 MPa), rib root bending {sig_rib:.0f} MPa ({b_rib:.2f} wide x {bu_['len']} thick, arm {arm:.2f}; PA12 MJF ~ 45, SLA tough ~ 50): marginal, VERIFY (thicker rib needs +x length)")
    if F / a_bond > 6.0 or sig_rib > 45.0:
        problems.append(f"bush bond shear {F / a_bond:.1f} MPa or rib bending {sig_rib:.0f} MPa too high")
    gd_ = L["dock"]
    travel = gd_["guard_free"][0] - gd_["guard_dock"][0]
    warns.append(f"needle guard spring (not a catalogue part, not in the order): needs about {p['cup']['dock']['guard']['spring_N'] / travel:.2f} N/mm ({p['cup']['dock']['guard']['spring_N']} N at the {travel:.2f} mm docked travel), wire <= 0.1, fits around the guard OD {p['cup']['dock']['guard']['od']}; to be wound or sourced")
    guide = (L["L_pl"] / (L["bore_w"] - 0.2))
    if guide < 0.5:
        problems.append(f"plunger guide length/width {guide:.2f} < 0.5: add guide fins")
    warns.append(f"anti-tilt: cup body {L['L_pl']:.1f} mm sliding on {L['bore_w'] - 0.2:.1f} mm width (L/W {guide:.2f}); seal beads {[n for n, _ in op_cup.active_rings(p)]} (variant {p['seal']['active_variant']})")
    if [n for n, _ in op_cup.active_rings(p)] != ["seal_b"]:
        problems.append("seal variant is not the single front bead: update op_cup.MFG_PARTS / ORDER (seal_a)")
    if th["F_avail_N"] < th["F_need_SF2_N"]:
        warns.append(f"thrust {th['F_avail_N']} N covers the {th['F_need_N']} N need (seal {th['F_seal_N']} + 30 kPa occlusion {th['F_occ_N']}) but NOT a safety factor 2 ({th['F_need_SF2_N']} N): the only bought miter pair is 1:1 (a z12 : z15 pair was not found), so the margin has to come from the screw efficiency / motor torque")
    warns.append(f"thrust: rod torque {th['T_rod_Nmm']} N mm, screw eta {th['eta_screw']}, bevel eta 0.9, collar term -> {th['F_avail_N']} N available (>= {THRUST_MIN_N} required); seal perimeter {th['perimeter_mm']} mm")
    dc = HERE.parent / "firmware-rs" / "openpatch-core" / "src" / "drive_cal.rs"
    if dc.exists():
        m_ = re.search(r"Nfp608_26_45CupMiter1_1,[^;]*bore_area_x100:\s*(\d+)", dc.read_text())
        if m_ and abs(int(m_.group(1)) - L["bore_area"] * 100) > 0.5:
            targets.append(f"FIRMWARE: preset 0x26 (drive_cal.rs) has bore_area_x100 {m_.group(1)} but the CAD bore is {L['bore_area']:.3f} mm2 ({L['bore_w']} x {L['bore_h']}, U/step {L['u_per_step']:.6f}): "
                           f"re-derive uu_num / uu_den / bore_area_x100 (+ tests/preset_cup.rs) before any dosing run, else every step delivers {L['bore_area'] * 100 / int(m_.group(1)) - 1:+.1%}")
    warns.append(f"U/step = {L['u_per_step']:.5f} (0.35 mm x {L['ratio']:.2f} / (20 x 26.45) x {L['bore_area']:.1f} mm2 / 10); 1 mm of plunger = {L['bore_area'] / 10:.1f} U; plunger aspect {L['aspect']:.1f} (limit 4.5)")
    if L["aspect"] > 4.5:
        problems.append(f"plunger aspect ratio {L['aspect']:.1f} > 4.5")
    dv = (math.pi * (fl["out_d"] / 2) ** 2 * (L["x_t0"] - L["x_in"]) + L["bore_area"] * dead) / 10.0
    warns.append(f"dead volume at empty ~ {dv:.2f} U (outlet bore d{fl['out_d']} through the front wall + gap {dead} mm x {L['bore_area']:.0f} mm2)")
    warns.append(f"layout A: motor column x {L['xc'] - 3:.1f}..{L['xc'] + 3:.1f} (rear), tank x {L['x_dry']:.1f}..{L['x_t0']:.1f} ({L['tank_len']:.1f}), dock x {K['x_bf']:.1f}..{K['x_far']:.1f}; lane 2 y {L['lane2_y'][0]:.1f}..{L['lane2_y'][1]:.1f}: "
                 f"battery x {L['battery']['x'][0]:.1f}..{L['battery']['x'][1]:.1f}, board above, USB-C (+Y wall) x {L['usb']['x'][0]:.1f}..{L['usb']['x'][1]:.1f}, aux keep-out x {L['aux']['x'][0]:.1f}..{L['aux']['x'][1]:.1f}")
    # ---- board interface (board review 2026-11-20): saddle below the board, USB-C on the board mid-plane and inside the lid, button window below the fillet,
    #      support / screw tops at the board underside, screws >= 3 mm from the HJ-840 antenna band, wire channel open
    cb, mo, us, bt, bsu = p["cup"]["board"], p["cup"]["motor"], p["cup"]["usb"], p["cup"]["button"], p["cup"]["board_support"]
    zb0, zb1 = cb["pcb_z"]
    if mo["lane2_lip_z"] >= zb0 - 0.05:
        problems.append(f"lane-2 saddle lip z {mo['lane2_lip_z']} not below the board underside {zb0}")
    if L["xc"] + mo["lane2_r_out"] > L["battery"]["x"][0] - 0.03:
        problems.append("lane-2 saddle reaches into the cell envelope")
    if abs(us["z_c"] - (zb0 + zb1) / 2) > 0.05:
        problems.append(f"USB-C centre z {us['z_c']} off the board mid-plane {(zb0 + zb1) / 2}")
    if us["z_c"] + us["open_h"] / 2 > L["height"] - w - 0.1:
        problems.append("USB-C opening reaches the lid roof")
    # side button cap (owner 2026-11-24): inside the lid wall between the joint and the roof, pad on the actuator, stroke 0.3-0.4, O-ring gland
    lap, H, tf = p["shell"]["lap_low"], L["height"], p["cup"]["top_fillet"]
    r_cb = bt["cbore_d"] / 2
    if bt["z_c"] - r_cb < lap + 0.1 or bt["z_c"] + r_cb > H - w - 0.03:
        problems.append(f"button counterbore z {bt['z_c'] - r_cb:.2f}..{bt['z_c'] + r_cb:.2f} not inside the lid wall ({lap + 0.1:.2f}..{H - w - 0.03:.2f})")
    zt = bt["z_c"] + r_cb                                                           # wall left behind the counterbore at its top (outer R1.8 fillet)
    y_out = L["width"] - tf + math.sqrt(max(tf ** 2 - max(0.0, zt - (H - tf)) ** 2, 0.0))
    wall_cb = y_out - (L["width"] - w + bt["cbore_depth"])
    if wall_cb < 0.15:
        problems.append(f"button counterbore leaves only {wall_cb:.2f} mm under the top fillet")
    stroke = bt["pad"]["face_y"] - bt["actuator_tip_y_max"] + bt["switch_travel"]
    stroke_max = bt["pad"]["face_y"] - bt.get("actuator_tip_y_min", bt["actuator_tip_y_max"]) + bt["switch_travel"]
    if not (0.29 <= stroke <= 0.41) or stroke_max > 0.45:
        problems.append(f"button stroke to actuate {stroke:.2f}..{stroke_max:.2f} outside 0.3-0.45")
    if bt["pad"]["face_y"] < bt["actuator_tip_y_max"] + 0.03:
        problems.append("button pad rests on (pre-loads) the SW1 actuator")
    if bt["flange"]["z"][0] < zb1 + 0.05 or bt["pad"]["z"][0] < zb1 + 0.05:
        problems.append("button flange / pad reach down to the board top (would hit the board edge when pressed)")
    if not (bt["pad"]["z"][0] - 1e-6 <= bt["actuator_z"] <= bt["pad"]["z"][1] + 1e-6):
        problems.append(f"button pad z {bt['pad']['z']} does not cover the actuator z {bt['actuator_z']}")
    gl = (bt["cbore_d"] - bt["stem_d"]) / 2
    sq = 1 - gl / bt["oring"]["cs"]
    if not (0.08 <= sq <= 0.3):
        problems.append(f"button O-ring radial squeeze {sq:.0%} outside 8-30 %")
    if bt["cbore_depth"] < bt["oring"]["cs"] - 1e-6:
        problems.append("button O-ring counterbore shallower than the cord")
    if bt["flange"]["x"][0] < us["x_c"] + us["gasket"]["half_x"] + 0.3:
        problems.append("button flange overlaps the USB-C gasket frame in x")
    # USB-C (challenge review: the plug must seat fully): overmold face (counterbore floor) 0.0-0.5 in front of the mouth, frame squeeze, groove skip covers the counterbore
    cbu, gu = us["cbore"], us["gasket"]
    y_mouth = cb["pcb_y"][1]
    om = (L["width"] - cbu["depth"]) - y_mouth
    if not (0.0 <= om <= 0.5 + 1e-6):
        problems.append(f"USB-C: plug overmold face {om:.2f} mm in front of the receptacle mouth (needs 0.0-0.5 to mate fully)")
    if w - cbu["depth"] < 0.25:
        problems.append(f"USB-C: wall left at the opening {w - cbu['depth']:.2f} < 0.25")
    gap_u = (L["width"] - w) - y_mouth
    sq_u = 1 - gap_u / gu["t_free"]
    if not (0.1 <= sq_u <= 0.3):
        problems.append(f"USB-C frame squeeze {sq_u:.0%} outside 10-30 % (gap {gap_u:.2f}, free {gu['t_free']})")
    sk_u = p["cup"]["joint"]["usb_skip_half"]
    if sk_u < cbu["w"] / 2 + 0.3 or gu["half_x"] < sk_u:
        problems.append(f"USB-C: rim-groove skip +-{sk_u} must exceed the counterbore half {cbu['w'] / 2} + 0.3 and lie inside the frame half {gu['half_x']}")
    if cbu["w"] < 12.35 or cbu["h"] < 6.5:
        warns.append(f"USB-C counterbore {cbu['w']} x {cbu['h']} smaller than the max USB-C plug overmold 12.35 x 6.5: large overmolds stop on the outer face")
    warns.append(f"USB-C: mouth (board north edge) y {y_mouth}, wall inner face {L['width'] - w}, outer counterbore {cbu['w']} x {cbu['h']} x {cbu['depth']} deep -> plug overmold face {om:.2f} in front of the mouth "
                 f"(was 1.1 + 0.4 recess), wall at the opening {w - cbu['depth']:.2f}; flat frame {2 * gu['half_x']:.1f} x {gu['z_max'] - gu['z0']:.1f} in the {gap_u:.2f} gap, free {gu['t_free']} -> squeeze {sq_u:.0%} (VERIFY: depends on the board position, screws W/E)")
    warns.append("button / board handshake (pre-order review H8): the cap is built for the SW1 tip at y %.2f-%.2f, i.e. SW1 moved back 0.45 mm on the board (board y 82.30, electronics agent); with the old tip 35.65-35.77 the pad would pre-load the switch" % (bt.get("actuator_tip_y_min", 0), bt["actuator_tip_y_max"]))
    warns.append(f"button cap: stem d{bt['stem_d']} at x {bt['x_c']}, z {bt['z_c']} in the lid wall, key face recess {bt['face_recess']}, stroke {stroke:.2f}..{stroke_max:.2f} (rest gap {bt['pad']['face_y'] - bt['actuator_tip_y_max']:.2f}..{bt['pad']['face_y'] - bt.get('actuator_tip_y_min', bt['actuator_tip_y_max']):.2f} + switch {bt['switch_travel']}), "
                 f"flange travels to y {L['width'] - w - bt['flange']['t'] - stroke_max:.2f} (SW1 body face must be below), "
                 f"O-ring {bt['oring']['id']} x {bt['oring']['cs']} squeeze {sq:.0%}, wall under the fillet behind the counterbore {wall_cb:.2f} mm")
    # shell joint: hard stop on the rim, seal squeeze and groove fill, posts / ribs / screw heads clear of the lid roof
    jt = p["cup"]["joint"]
    g_w = jt["groove_off"][1] - jt["groove_off"][0]
    t_w = jt["tongue_off"][1] - jt["tongue_off"][0]
    s_w = jt["seal_off"][1] - jt["seal_off"][0]
    comp = jt["groove_depth"] - jt["tongue_h"]
    squeeze = 1 - comp / jt["seal_h"]
    fill = s_w * jt["seal_h"] / (g_w * jt["groove_depth"] - t_w * jt["tongue_h"])
    if not (0.18 <= squeeze <= 0.27):
        problems.append(f"seal squeeze {squeeze:.0%} outside 18-27 %")
    if fill > 0.85:
        problems.append(f"seal groove fill {fill:.0%} > 85 %")
    if s_w * jt["seal_h"] / comp > g_w:
        problems.append("compressed seal wider than the groove")
    if not (jt["groove_off"][0] < jt["tongue_off"][0] and jt["tongue_off"][1] < jt["groove_off"][1]):
        problems.append("tongue not inside the groove")
    if min(jt["groove_off"][0], w - jt["groove_off"][1]) < 0.2:
        problems.append("groove wall < 0.2 mm")
    post_top, roof = H - w - jt["post_gap"], H - w
    if post_top > roof - 0.05:
        problems.append(f"lid posts (top {post_top:.2f}) can hold the lid off the rim (roof {roof:.2f})")
    if jt["rib_gap"] < 0.03:
        problems.append("lid hold-down ribs nominally touch the board: they can prop the lid off the rim")
    sh_top = zb1 + 0.8                                                             # M1.2 cheese head 0.8 on the board top
    warns.append(f"shell joint: lid on the rim at z {lap} (hard stop, no gap); groove {g_w:.2f} x {jt['groove_depth']} at {jt['groove_off'][0]} from the outer wall, tongue {t_w:.2f} x {jt['tongue_h']}, "
                 f"seal {s_w:.2f} x {jt['seal_h']} -> squeeze {squeeze:.0%}, fill {fill:.0%}; post tops {post_top:.2f} / ribs {zb1 + jt['rib_gap']:.2f} (board top {zb1}) / board screw heads {sh_top:.2f} vs lid roof {roof:.2f}: "
                 f"nothing reaches the roof. Earlier print: lid face 0.4 above the rim (flat 0.5 gasket) and post tops 0.05 below the roof -> 0.35 mm gap even without the gasket (0.7 mm at 2:1)")
    if bsu["z_top"] != zb0:
        problems.append("support tops not at the board underside")
    if (L["height"] - w) - zb1 < 0.8 + 0.3:
        problems.append("no head clearance for the board screws under the lid")
    for (sx, sy) in L["board_screws"]:
        dx, dy = max(0.0, 42.85 - sx, sx - 43.4), max(0.0, 24.0 - sy, sy - 32.0)
        if math.hypot(dx, dy) < 3.0:
            problems.append(f"board screw ({sx}, {sy}) closer than 3 mm to the HJ-840 antenna band")
    wc = L["elec_interface"]["wire_channel"]["x"]
    if wc[1] - wc[0] < 1.8:
        problems.append(f"wire channel x {wc} narrower than 1.8 mm")
    warns.append(f"board interface: USB-C opening x {us['x_c'] - us['open_w'] / 2:.1f}..{us['x_c'] + us['open_w'] / 2:.1f}, z {us['z_c'] - us['open_h'] / 2:.2f}..{us['z_c'] + us['open_h'] / 2:.2f}; "
                 f"wire channel x {wc[0]}..{wc[1]}; cell x {L['battery']['x'][0]:.2f}..{L['battery']['x'][1]:.2f}; board screws {L['board_screws']}; button pad x {bt['pad']['x']} face y {bt['pad']['face_y']}")
    # ---- assembly: every group drops in from above in ORDER (drop path = own bbox x-y swept from the part bottom to the cavity ceiling, free of the housing and of earlier groups)
    import op_cup_asm
    tools = Script()
    grp = {}
    for gi, (gname, names) in enumerate(op_cup_asm.ORDER):
        for n in names:
            grp[n] = gi
    for n, gi in grp.items():
        if n in ("bottom", "top", "lid_gasket", "usb_gasket", "button_cap", "button_oring") or n in op_cup_asm.FROM_BELOW or n not in by or gi >= 6:
            continue
        mn, mx = bb(n)["min"], bb(n)["max"]
        z_lo = zc + p["cup"]["motor"]["snap_h"] if n in ("motor", "gearhead", "motor_boss", "motor_rear_boss") else zc if n == "bush_rod" else mn[2] + 0.01
        if n in ("ko_board", "ko_side_b"):
            z_lo = p["cup"]["board"]["pcb_z"][0] + 0.01          # bottom parts sit between the part-free support pads; the bbox sweep tests the PCB from its underside up          # round parts in U seats: test from the axis up
        tools.box(f"drop_{n}", (mn[0], mx[0]), (mn[1], mx[1]), (z_lo, L["height"] - 0.9))
    names_t = [x for x in grp if f"drop_{x}" in {c_["params"].get("body_name") for c_ in tools.dumps()}]
    ex3 = excl + [[f"drop_{a}", f"drop_{b}"] for a in names_t for b in names_t if a < b] + [[f"drop_{a}", a] for a in names_t] + [["drop_gear_a", "gear_b"], ["drop_gear_b", "gear_a"]]
    ex3 += [[f"drop_{a}", b] for a in names_t for b in grp if grp[b] == grp[a]]
    ir3 = run_extra(sc, tools, ex3)
    blocked = {}
    for i in ir3["interferences"]:
        if i.get("volume_mm3", 1) <= C.MIN_OVERLAP_MM3:
            continue
        a_, b_ = i["a"], i["b"]
        d_, o_ = (a_, b_) if a_.startswith("drop_") else (b_, a_)
        if not d_.startswith("drop_") or o_.startswith("drop_"):
            continue
        if o_ == "bottom" or grp.get(o_, 99) < grp[d_[5:]]:
            blocked.setdefault(d_[5:], []).append(o_)
    for n, o in blocked.items():
        problems.append(f"assembly: {n} cannot drop in from above, blocked by {sorted(set(o))}")
    warns.append("assembly order (drop test passed for): " + "; ".join(f"{g}: {len([x for x in names if f'drop_{x}' in {c_['params'].get('body_name') for c_ in tools.dumps()}])} parts" for g, names in op_cup_asm.ORDER[:5]) + "; dock parts (centring hub + needle + guard + springs) are pressed in from BELOW through the pocket (documented exception); button cap + O-ring go into the lid from inside before it is closed")
    import cup_packing
    pk = cup_packing.run(outdir, variant)
    vd = L["voids"]
    side = cup_packing.MIN_SIDE

    def accepted(x0: float, y0: float) -> str | None:
        for nm_v, b_v in vd.items():
            if b_v["x"][0] - 1e-6 <= x0 and x0 + side <= b_v["x"][1] + 1e-6 and b_v["y"][0] - 1e-6 <= y0 and y0 + side <= b_v["y"][1] + 1e-6:
                return nm_v
        return None
    bad = [h for h in pk["hits"] if accepted(*h) is None]
    used = sorted({accepted(*h) for h in pk["hits"]} - {None})
    if bad:
        problems.append(f"packing: empty full-height 4 x 4 mm column outside the accepted voids (first at x,y = {[round(v, 1) for v in bad[0]]}, {len(bad)} cells): shorten/narrow or fill it")
    va = {k_: round((b_["x"][1] - b_["x"][0]) * (b_["y"][1] - b_["y"][0]), 1) for k_, b_ in vd.items()}
    warns.append(f"packing (honest: no empty reservation boxes): free plan area {pk['free_mm2']} of {pk['plan_mm2']} mm2 (full-height bbox model), largest empty rectangle {pk['largest_empty_rect']['area_mm2']} mm2 at "
                 f"{pk['largest_empty_rect']['x0y0x1y1']}; 4 x 4 columns only in the accepted, not tank-convertible voids {used} (plan mm2 {va}: {p['cup']['packing_voids']})")
    for part in ("bottom", "top", "reservoir", "plunger_core", "plunger_seal", "lid_gasket", "usb_gasket", "button_cap"):
        for ext in ("step", "stl"):
            if not (outdir / f"{variant}_{part}.{ext}").exists():
                problems.append(f"missing export {variant}_{part}.{ext}")
    return {"variant": variant, "dims": dims, "problems": problems, "warns": warns, "targets": targets, "bodies": len(bodies), "checked": interf.get("checked"), "L": L}


def main(args) -> int:
    out = Path(args.outdir or (HERE / "out" / "v010-cup"))
    p = json.loads((out / "params.used.json").read_text())
    sizes = args.sizes or list(p["cup"]["sizes"])
    failed = False
    print(f"{'Size':8} {'L':>7} {'B':>6} {'H':>6}  status")
    for v in sizes:
        r = check_size(out, v, p)
        d = r["dims"]
        failed |= bool(r["problems"])
        print(f"{v:8} {d[0]:7.2f} {d[1]:6.2f} {d[2]:6.2f}  {'PASS' if not r['problems'] else 'FAIL'}  ({r['bodies']} bodies, {r['checked']} solids interference-checked)")
        for m in r["problems"]:
            print(f"    FAIL: {m}")
        for m in r["targets"]:
            print(f"    TARGET: {m}")
        for m in r["warns"]:
            print(f"    NOTE: {m}")
    return 1 if failed else 0
