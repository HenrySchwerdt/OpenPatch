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

TARGET_L = {"OP-100": 45.0, "OP-200": 52.0}
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


def thrust(p: dict, L: dict) -> dict:
    """NFP-608-26.45 pull-out torque -> rod -> screw -> plunger force vs. seal friction + occlusion pressure (estimates, VERIFY on the bench)."""
    g = p["cup"]["gears"]
    T_gb = 1.6 * 9.80665e-3 * 10.0 * 26.45 * 0.64                 # N mm at the gearhead output (1.6 gf cm pull-out x 26.45 x 0.64, parts.md)
    eta_b, eta_s, pitch = 0.9, 0.2, p["drive"]["screw_pitch"]
    T_rod = T_gb * (g["z_rod"] / g["z_motor"]) * eta_b
    F = 2 * math.pi * eta_s * T_rod / pitch
    A = L["bore_area"]
    perim = 2 * (L["bore_w"] - L["bore_h"]) + math.pi * L["bore_h"]
    f_seal = 1.6 * perim / (2 * (16.0 - 5.0) + math.pi * 5.0)      # bench breakaway ~1.6 N at the 16 x 5 perimeter (spec 3b), scaled by perimeter
    f_occ = 30e3 * A * 1e-6                                       # 30 kPa occlusion alarm threshold
    need = f_seal + f_occ
    return {"T_rod_Nmm": round(T_rod, 2), "F_avail_N": round(F, 1), "F_seal_N": round(f_seal, 1), "F_occ_N": round(f_occ, 1), "F_need_N": round(need, 1),
            "F_need_SF2_N": round(2 * need, 1), "perimeter_mm": round(perim, 1), "area_mm2": round(A, 1)}


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
    for n in ("carriage", "tongue_shim", "gear_c", "gear_d", "idler_pin", "leadscrew", "drive_screw", "end_cap", "end_cap_lid", "cap_gasket", "dock_insert", "pod_board"):
        if n in by:
            problems.append(f"removed part present (simplicity rule): {n}")
    if problems and any(n.startswith("body missing") for n in problems):
        return {"variant": variant, "dims": dims, "problems": problems, "warns": warns, "targets": targets, "bodies": len(bodies), "checked": interf.get("checked"), "L": L}
    bb = lambda n: by[n]["bbox"]
    ctr = lambda n, ax: (bb(n)["min"][ax] + bb(n)["max"][ax]) / 2
    zc, yr, w = L["zc"], L["y_r"], L["wall"]
    # ---- one rod on the tank axis, rotating + axially fixed; nut / plunger bore on the same axis
    for n in ("rod", "nut", "bush_rod", "magnet", "thrust_sleeve", "thrust_collar", "gear_b", "plunger_core"):
        if abs(ctr(n, 1) - yr) > 1e-3 or abs(ctr(n, 2) - zc) > 1e-3:
            problems.append(f"{n} not on the tank axis (y {ctr(n, 1):.3f}, z {ctr(n, 2):.3f})")
    sl, bs, rd, mg, tm, cl, gbb = bb("thrust_sleeve"), bb("bush_rod"), bb("rod"), bb("magnet"), bb("hall_tmag"), bb("thrust_collar"), bb("gear_b")
    if not (0.0 <= cl["min"][0] - bs["max"][0] <= 0.15):
        problems.append(f"collar not seated on the bush tank-side face (gap {cl['min'][0] - bs['max'][0]:.3f}): -X thrust has no stop")
    if not (0.0 <= bs["min"][0] - sl["max"][0] <= 0.15):
        problems.append(f"gear B sleeve not seated on the bush motor-side face (gap {bs['min'][0] - sl['max'][0]:.3f}): +X thrust has no stop")
    if abs(mg["max"][0] - gbb["min"][0]) > 0.011:
        problems.append("magnet not on the rear (motor-side) face of gear B")
    if abs(rd["min"][0] - gbb["min"][0]) > 0.011:
        problems.append("rod does not end flush with gear B (rod must end at gear B)")
    if rd["max"][0] < cl["max"][0]:
        problems.append("rod does not span gear B .. collar")
    gap_y = mg["min"][1] - tm["max"][1]
    if gap_y < p["cup"]["tmag"]["gap"] - 1e-6:
        problems.append(f"TMAG only {gap_y:.2f} mm from the magnet edge (< {p['cup']['tmag']['gap']})")
    behind = [n for n, b in by.items() if n not in ("bottom", "top") and not n.startswith("ko_") and b["bbox"]["min"][0] < L["xc"] - 3.0 - 0.011]
    if behind:
        problems.append(f"parts behind the motor column (nothing may be left of it): {behind}")
    # ---- exactly two gears, meshing as a miter pair (axes cross at the apex)
    ga, gb = bb("gear_a"), bb("gear_b")
    if abs((ga["min"][0] + ga["max"][0]) / 2 - L["xc"]) > 1e-3:
        problems.append("motor bevel gear not centred on the apex x")
    gears = [n for n in by if n.startswith("gear") and n != "gearhead"]
    if sorted(gears) != ["gear_a", "gear_b"]:
        problems.append(f"gear count != 2: {gears}")
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
        problems.append("rod tip not 0.5 mm beyond the nut front face at empty")
    if p["cup"]["plunger"]["bore_d"] / 2 <= p["cup"]["rod"]["d"] / 2:
        problems.append("rod radius >= plunger bore radius")
    wet = Script()
    wet.stadium("wet_full", (L["x_pf_full"], L["x_in"]), yr, zc, L["bore_w"], L["bore_h"])
    wet.stadium("wet_empty", (L["x_pf_empty"] - 0.001, L["x_in"]), yr, zc, L["bore_w"], L["bore_h"])
    hh = p["cup"]["dock"]["head"]
    wet.box("dome_sweep", (K["x_f"], K["x_d"] + K["R"] + K["slide"]), (K["y_c"] - K["R"], K["y_c"] + K["R"]), (0.0, hh["B_dome_h"] + 0.05))
    wet.box("plate_sweep", (K["plate_x"][0] + 0.2, K["plate_x"][1] - 0.2), (K["y_c"] - hh["base_w"] / 2, K["y_c"] + hh["base_w"] / 2), (0.0, hh["base_t"]))
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
    if by["septum"]["bbox"]["min"][2] < 0.89 or by["septum"]["bbox"]["max"][2] > fl["pocket_top"] + 1e-6:
        problems.append("fill septum not on the underside of the tank")
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
    if K["pocket_len"] > 12.0 + 1e-9 or 2 * K["half"] > 10.0 + 1e-9:
        problems.append(f"dock pocket {K['pocket_len']:.1f} x {2 * K['half']:.1f} exceeds the 12 x 10 budget")
    plate_len = K["plate_x"][1] - K["plate_x"][0]
    if plate_len > 12.0:
        warns.append(f"base-plate window {plate_len:.1f} mm long (> 12): base plate {p['cup']['dock']['head']['base_l']} + 2 x {p['cup']['dock']['clr']} clearance + {K['slide']} slide; <= 12 needs a base plate <= {12 - 0.4 - K['slide']:.1f} mm (TODO-MEASURE)")
    st = dock.clip_stress(p, K)
    if st["sigma_need"] > p["cup"]["dock"]["clip"]["allow_MPa"]:
        problems.append(f"U-clip bending stress {st['sigma_need']:.0f} MPa > allowable {p['cup']['dock']['clip']['allow_MPa']}")
    warns.append(f"U-clip 301 FH 0.1 mm: arm {st['arm_len']:.1f} mm, needed travel {st['need_travel']:.2f} -> {st['sigma_need']:.0f} MPa (allow {p['cup']['dock']['clip']['allow_MPa']}), tip force {st['F_need_N']:.3f} N/clip; "
                 f"1.8 mm travel -> {st['sigma_1p8']:.0f} MPa; a 3.5 mm arm allows only {st['short_arm_3p5_travel']:.2f} mm, 1.8 mm needs >= {st['arm_for_1p8']:.1f} mm")
    hw = dock.hall_window(p)
    if hw["assert_radius_mm"] > 0.8 or hw["assert_radius_mm"] <= 0.0:
        problems.append(f"dock hall asserts within {hw['assert_radius_mm']} mm of the final position (> 0.8): not only when slid + latched")
    warns.append(f"dock hall (dipole model, VERIFY): B0 {hw['B0_mT']} mT, Bop {hw['bop_mT']} mT -> asserts only within {hw['assert_radius_mm']} mm of the final position (slide {hw['slide_mm']} mm)")
    # ---- reserved volumes inside the cavity, not overlapping each other (interference test above) 
    for n in op_cup.KEEPOUT:
        b = bb(n)
        if b["min"][0] < w - 1e-6 or b["max"][0] > L["length"] - w + 1e-6 or b["min"][1] < w - 1e-6 or b["max"][1] > L["width"] - w + 1e-6 or b["max"][2] > L["height"] - w + 1e-6:
            problems.append(f"keep-out {n} outside the cavity")
    # ---- thrust / U per step
    th = thrust(p, L)
    if th["F_avail_N"] < THRUST_MIN_N:
        problems.append(f"thrust {th['F_avail_N']} N < {THRUST_MIN_N} N")
    if th["F_avail_N"] < 1.5 * th["F_need_N"]:
        problems.append(f"thrust margin {th['F_avail_N'] / th['F_need_N']:.2f}x < 1.5x: use the 16:20 ratio (z_rod 20)")
    warns.append(f"thrust margin {th['F_avail_N'] / th['F_need_N']:.2f}x (available {th['F_avail_N']} N / needed {th['F_need_N']} N)")
    guide = (L["L_pl"] / (L["bore_w"] - 0.2))
    if guide < 0.5:
        problems.append(f"plunger guide length/width {guide:.2f} < 0.5: add guide fins")
    warns.append(f"anti-tilt: cup body {L['L_pl']:.1f} mm sliding on {L['bore_w'] - 0.2:.1f} mm width (L/W {guide:.2f}) + 2 rings {p['cup']['plunger']['ring_front_a'][0] - p['cup']['plunger']['ring_front_b'][0]:.2f} mm apart")
    if th["F_avail_N"] < th["F_need_SF2_N"]:
        warns.append(f"thrust {th['F_avail_N']} N covers the {th['F_need_N']} N need (seal {th['F_seal_N']} + 30 kPa occlusion {th['F_occ_N']}) but NOT a safety factor 2 ({th['F_need_SF2_N']} N): z16:z20 pair (+25 %) is the margin option")
    warns.append(f"thrust: rod torque {th['T_rod_Nmm']} N mm, screw eta 0.2, bevel eta 0.9 -> {th['F_avail_N']} N available (>= {THRUST_MIN_N} required); seal perimeter {th['perimeter_mm']} mm")
    warns.append(f"U/step = {L['u_per_step']:.5f} (0.35 mm x {L['ratio']:.2f} / (20 x 26.45) x {L['bore_area']:.1f} mm2 / 10); 1 mm of plunger = {L['bore_area'] / 10:.1f} U; plunger aspect {L['aspect']:.1f} (limit 4.5)")
    if L["aspect"] > 4.5:
        problems.append(f"plunger aspect ratio {L['aspect']:.1f} > 4.5")
    dv = (math.pi * (fl["out_d"] / 2) ** 2 * (L["x_t0"] - L["x_in"]) + L["bore_area"] * dead) / 10.0
    warns.append(f"dead volume at empty ~ {dv:.2f} U (outlet bore d{fl['out_d']} through the front wall + gap {dead} mm x {L['bore_area']:.0f} mm2)")
    warns.append(f"layout A: motor column x {L['xc'] - 3:.1f}..{L['xc'] + 3:.1f} (rear), tank x {L['x_dry']:.1f}..{L['x_t0']:.1f} ({L['tank_len']:.1f}), dock x {K['x_bf']:.1f}..{K['x_far']:.1f}; lane 2 y {L['lane2_y'][0]:.1f}..{L['lane2_y'][1]:.1f}: "
                 f"battery x {L['battery']['x'][0]:.1f}..{L['battery']['x'][1]:.1f}, board above, USB-C (+Y wall) x {L['usb']['x'][0]:.1f}..{L['usb']['x'][1]:.1f}, aux/piezo/button x {L['aux']['x'][0]:.1f}..{L['aux']['x'][1]:.1f}")
    import cup_packing
    pk = cup_packing.run(outdir, variant)
    if pk["rect_4x4_found"]:
        problems.append(f"packing: empty full-height rectangle >= 4 x 4 mm remains (first at x,y = {pk['rect_4x4_first']}, {pk['n_4x4_cells']} cells): shorten/narrow or fill it")
    warns.append(f"packing: free plan area {pk['free_mm2']} of {pk['plan_mm2']} mm2 (full-height bbox model), largest empty rectangle {pk['largest_empty_rect']['area_mm2']} mm2 at {pk['largest_empty_rect']['x0y0x1y1']}, no 4 x 4 hole")
    for part in ("bottom", "top", "reservoir", "plunger_core", "plunger_seal"):
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
