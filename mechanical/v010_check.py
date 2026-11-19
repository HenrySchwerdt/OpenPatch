# SPDX-License-Identifier: LicenseRef-OpenPatch
"""`check.py --variant v010`: envelope, interference (real E73 / PicoBlade / drive models), battery / board / antenna keep-outs, walls. TEST PROJECT."""
from __future__ import annotations

import json
import re
from pathlib import Path

import check as C
from op_build import BENCH_EXCLUDE_PAIRS
from op_layout import HERE

V010_WALLS = {"retention_rib": ("battery", "rib_t"), }
ANTENNA_METAL = ["battery", "motor", "gearhead", "magnet", "leadscrew", "dock_magnet", "nut", "needle", "gear_a", "gear_b", "spring_p", "spring_n", "pico_conn",
                 "bat_pad_p", "bat_pad_n", "piezo", "switch"]
TOP_PARTS = ["piezo", "switch", "chg_pad_1", "chg_pad_2", "charge_gasket", "hall_drv0", "hall_drv1"]


def check_v010(p: dict, L: dict, by: dict) -> tuple[list, list]:
    problems, warns = [], []
    G, v = L["v010"], p["v010"]
    need = ("pod_board", "e73", "pico_conn", "pico_plug", "battery", "bat_foam", "bat_pad_p", "bat_pad_n", "spring_p", "spring_n", "piezo", "switch", "chg_pad_1",
            "chg_pad_2", "charge_gasket", "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock", "dock_magnet", "dock_insert", "cannula_adapter", "end_cap", "motor", "gearhead")
    for n in need:
        if n not in by:
            problems.append(f"v010 body missing: {n}")
    for gone in ("ffc_conn", "ffc_cable", "qi_coil", "rf_module", "pcb"):
        if gone in by:
            problems.append(f"leftover body in the v010 pod: {gone}")
    if problems:
        return problems, warns
    bb = {k: x["bbox"] for k, x in by.items()}
    z0, ztop, zi = G["z0"], G["ztop"], G["zi"]
    xr = L["x_r1"]

    def g(name: str, ax: int, mm: str) -> float:
        return bb[name][mm][ax]

    # ---- board inside the cavity / over the supports -------------------------------------------------------------------
    b = bb["pod_board"]
    if b["min"][0] < L["xi0"] + 0.3 or b["max"][0] > L["x_end"] - 0.3 or b["min"][1] < L["yi0"] + 0.3 or b["max"][1] > L["yi1"] - 0.3:
        problems.append(f"pod_board bbox x {b['min'][0]:.2f}..{b['max'][0]:.2f} y {b['min'][1]:.2f}..{b['max'][1]:.2f} closer than 0.3 mm to the housing walls")
    if abs(b["min"][2] - z0) > 1e-3 or abs(b["max"][2] - ztop) > 1e-3:
        problems.append("pod_board z not on the stack plane")
    e = bb["e73"]
    if e["min"][0] < b["min"][0] or e["max"][0] > b["max"][0] or e["min"][1] < b["min"][1] or e["max"][1] > b["max"][1]:
        problems.append("E73 module not fully under the board bbox")
    if abs(e["max"][2] - z0) > 0.05:
        problems.append(f"E73 module top z {e['max'][2]:.2f} not on the board bottom {z0}")
    # ---- strip rule: no tall bottom-side part over the dock tunnel ---------------------------------------------------------
    yc, ym = L["dock"]["y_c"], 6.2
    for n in ("e73", "pico_conn", "pico_plug", "battery", "bat_foam", "spring_p", "spring_n"):
        x = bb[n]
        if x["min"][2] < z0 - 0.01 and x["min"][1] < yc + ym and x["max"][1] > yc - ym and x["max"][0] > xr + G["plan"]["arms_end_u"] + 0.0:
            # allowed to dip into the band only beyond the arms by the dome radius (extension tunnel: dome only)
            if x["min"][1] < G["plan"]["y_lo_dome"] - 1e-3:
                problems.append(f"{n} y_min {x['min'][1]:.2f} < dome path limit {G['plan']['y_lo_dome']:.2f} (tunnel)")
        if x["min"][0] < xr + G["plan"]["arms_end_u"] and x["min"][1] < G["plan"]["y_lo_arms"] - 1e-3 and n != "pico_plug":
            problems.append(f"{n} y_min {x['min'][1]:.2f} < snap-arm clearance {G['plan']['y_lo_arms']:.2f}")
    # ---- battery stack ------------------------------------------------------------------------------------------------------
    bt = bb["battery"]
    gap = z0 - (bt["max"][2] + 0.05)
    t = v["battery"]["t"]
    gap_lo, gap_hi = gap, gap + 0.3          # thinner cell (class 3.0 nominal vs modelled 3.2 max): gap range
    comp_lo, comp_hi = v["battery"]["spring_free_max"] - gap_hi, v["battery"]["spring_free_max"] - gap_lo
    if not (0.2 <= gap <= v["battery"]["spring_free_max"] - 0.2):
        problems.append(f"spring contact gap {gap:.2f} mm outside 0.2..{v['battery']['spring_free_max'] - 0.2:.1f}")
    warns.append(f"battery {v['battery']['class']} class envelope {v['battery']['l']} x {v['battery']['w']} x {t} mm: cell top z {bt['max'][2]:.2f}, spring gap {gap:.2f} mm "
                 f"(0.3 mm thinner cell: {gap_hi:.2f}), SMD spring compression {comp_lo:.2f}..{comp_hi:.2f} mm of {v['battery']['spring_free_max']} free")
    if comp_lo < 0.15:
        warns.append(f"thinnest cell leaves only {comp_lo:.2f} mm spring compression: use a 0.5 mm foam or contact with >= 1.2 mm free height")
    ba = bb["bat_foam"]
    if abs(ba["min"][2] - L["wall"]) > 1e-3:
        problems.append("battery foam not on the floor")
    # retention: ribs are part of 'bottom'; cell must sit between them (clearance both sides)
    for r in G["ribs"][:2]:
        d = abs((r["y"][0] if r["id"] == "rib_yp" else r["y"][1]) - (bt["max"][1] if r["id"] == "rib_yp" else bt["min"][1]))
        if not (0.05 <= d <= 0.3):
            problems.append(f"battery rib clearance {d:.2f} mm out of 0.05..0.3")
    # ---- antenna keep-out ---------------------------------------------------------------------------------------------------
    ak = G["e73"]["antenna_keepout_u"]
    kx0, kx1 = xr + ak[0] - 3.0, L["x_end"] + 1.0      # 3 mm extra around the copper-free zone for metal parts
    ky0, ky1 = G["e73"]["y"][0] - 3.0, G["e73"]["y"][1] + 3.0
    for n in ANTENNA_METAL:
        if n in bb and bb[n]["max"][0] > kx0 and bb[n]["min"][0] < kx1 and bb[n]["max"][1] > ky0 and bb[n]["min"][1] < ky1:
            problems.append(f"{n} inside the antenna keep-out x {kx0:.1f}..{kx1:.1f} y {ky0:.1f}..{ky1:.1f}")
    ant_x = xr + G["e73"]["u"][1] - 2.0
    dmin = min((ant_x - bb[n]["max"][0]) for n in ("battery", "bat_pad_p", "pico_conn", "spring_p") if n in bb)
    warns.append(f"antenna end (E73 ceramic at +X) is {dmin:.1f} mm from the nearest cell/connector metal; antenna keep-out u {ak[0]:.1f}..{ak[1]:.1f}, "
                 f"charge pads {ant_x - max(c['center_pod'][0] for c in G['charge_pads']):.1f} mm from the antenna end")
    if dmin < 10.0:
        problems.append(f"battery/connector only {dmin:.1f} mm from the antenna (>= 10 mm required)")
    # ---- top side ------------------------------------------------------------------------------------------------------------
    for n in TOP_PARTS:
        if bb[n]["max"][2] > zi - 0.05:
            problems.append(f"{n} top z {bb[n]['max'][2]:.2f} touches the lid inner z {zi:.2f}")
    warns.append(f"top-side parts: piezo {bb['piezo']['max'][2] - ztop:.2f} mm, tact switch {bb['switch']['max'][2] - ztop:.2f} mm; free under the lid {zi - ztop:.2f} mm")
    # ---- charge window ---------------------------------------------------------------------------------------------------------
    w, gk = G["window"], bb["charge_gasket"]
    for c in G["charge_pads"]:
        hs = c["size"] / 2
        x, y = c["center_pod"]
        if x - hs < w["x"][0] + 0.2 or x + hs > w["x"][1] - 0.2 or y - hs < w["y"][0] + 0.2 or y + hs > w["y"][1] - 0.2:
            problems.append("charge pad not inside the lid window with >= 0.2 mm margin")
    if gk["min"][2] < ztop or gk["max"][2] > zi:
        problems.append("charge gasket outside board top .. lid inner")
    if gk["max"][1] > b["max"][1] or gk["min"][1] < b["min"][1]:
        problems.append("charge gasket ring leaves the board")
    gw = v["charge"]["gasket_w"]
    if gw < C.MIN_FEATURE:
        problems.append("gasket ring narrower than 0.4 mm")
    warns.append(f"charge window {w['x'][1] - w['x'][0]:.1f} x {w['y'][1] - w['y'][0]:.1f} mm in the lid, gasket ring {gw} mm wide x {gk['max'][2] - gk['min'][2]:.2f} mm "
                 f"(compressed state), pads {v['charge']['pad']} mm at {v['charge']['pitch']} mm pitch")
    # ---- pressure-equalisation vent (review 2026-11-19) ---------------------------------------------------------------------
    vn = G["vent"]
    vx, vy = vn["center_pod"]
    r = vn["recess_d"] / 2
    if vn["hole_d"] < 0.8 - 1e-9:
        problems.append("vent hole below the printable 0.8 mm")
    if L["wall"] - vn["recess_depth"] < C.MIN_WALL + 0.05 - 1e-9:
        problems.append(f"lid wall under the vent recess {L['wall'] - vn['recess_depth']:.2f} mm < {C.MIN_WALL}")
    if vx - r < L["xi0"] + 0.5 or vy - r < L["yi0"] + 0.5 or vy + r > L["yi1"] - 0.5:
        problems.append("vent recess too close to the lid walls")
    for n in TOP_PARTS:
        b_ = bb[n]
        if b_["max"][0] > vx - r and b_["min"][0] < vx + r and b_["max"][1] > vy - r and b_["min"][1] < vy + r:
            problems.append(f"{n} under the vent membrane area")
    for q in p["bench"]["mount"]["hd"]:
        if ((xr + q[0]) - vx) ** 2 + (q[1] - vy) ** 2 < (r + 1.0) ** 2:
            problems.append("vent recess collides with a lid hold-down pad")
    warns.append(f"vent: d{vn['hole_d']} hole + d{vn['recess_d']} ePTFE membrane recess in the lid at x {vx:.1f}, y {vy:.1f} (lid wall left {L['wall'] - vn['recess_depth']:.2f} mm)")
    # ---- lead -------------------------------------------------------------------------------------------------------------------
    if G["lead_len_est"] > v["connector"]["lead_max_mm"]:
        problems.append(f"motor lead estimate {G['lead_len_est']:.1f} mm > {v['connector']['lead_max_mm']} mm (NFP factory lead is clipped to <= 25 mm)")
    warns.append(f"motor lead terminal -> PicoBlade: estimate {G['lead_len_est']:.1f} mm (limit {v['connector']['lead_max_mm']} mm: clip the factory lead to length, flat in the floor groove)")
    if G["lead_len_est"] > v["connector"]["lead_nominal_mm"]:
        warns.append(f"lead longer than the 25 mm of docs/v010/ARCHITECTURE.md ({G['lead_len_est']:.1f} mm): order the NFP lead long enough or add a PicoBlade extension lead (plug-in, no soldering)")
    # ---- dock / hall (unchanged vs. the bench pod) --------------------------------------------------------------------------------
    dm, dh = bb["dock_magnet"], bb["hall_dock"]
    dgap = dh["min"][2] - dm["max"][2]
    if not (0.4 <= dgap <= 1.5):
        problems.append(f"dock hall air gap {dgap:.2f} mm outside 0.4..1.5")
    cx = (dh["min"][0] + dh["max"][0]) / 2 - (dm["min"][0] + dm["max"][0]) / 2
    cy = (dh["min"][1] + dh["max"][1]) / 2 - (dm["min"][1] + dm["max"][1]) / 2
    if abs(cx) > 0.1 or abs(cy) > 0.1:
        problems.append(f"dock hall not centred over the magnet (dx {cx:.2f}, dy {cy:.2f})")
    mag = bb["magnet"]
    for n in ("hall_tmag", "hall_drv0", "hall_drv1"):
        gg = bb[n]["min"][0] - mag["max"][0]
        if gg < 0.4:
            problems.append(f"{n} only {gg:.2f} mm from the spindle magnet end face")
    if L["dock"]["strain_ok"] is not True:
        problems.append("snap arm strain > 3 %")
    pr_i, wr_i = C.check_insert(p, L, by)
    problems += pr_i
    warns += wr_i
    # ---- no new part touches the dock tunnel clearance (dome silhouette): dome vs everything is covered by the adapter interference check
    warns.append(f"v010 pod {L['length']:.2f} x {L['width']:.1f} x {L['height']:.1f} mm (bench tail {p['bench']['tail_len']:.1f} mm from x_r1); strip items u: connector {G['plan']['conn_u']:.1f}, "
                 f"cell {G['plan']['cell_u0']:.1f}..{G['plan']['cell_u1']:.1f}, E73 {G['plan']['e73_u0']:.1f}..{G['plan']['e73_u1']:.1f}")
    if G.get("electronics_file"):
        warns.append(f"board outline read from {G['electronics_file']}")
    return problems, warns


def check_size(outdir: Path, variant: str, p: dict, ignore_length: bool, with_variants: bool) -> dict:
    results = C.eval_design(outdir / f"{variant}.sc", BENCH_EXCLUDE_PAIRS + [["pico_conn", "pico_plug"]])
    measure = next(r for r in results if "bodies" in r and "body_count" in r)
    interf = next(r for r in results if "interferences" in r)
    bodies = measure["bodies"]
    lo, hi = C.envelope([b for b in bodies if b["name"] not in ("cannula_adapter",)])
    dims = [hi[i] - lo[i] for i in range(3)]
    L = json.loads((outdir / f"{variant}.mech.json").read_text())
    spec = p["spec"]
    tgt_l = L["length"] + 0.01          # v010 length is derived from the strip plan (target = computed length; ARCHITECTURE estimate in V010.md)
    problems, warns = [], []
    if dims[2] > spec["max_height"] + C.EPS:
        problems.append(f"height {dims[2]:.3f} > {spec['max_height']}")
    if dims[1] > spec["width_target"] + C.EPS:
        problems.append(f"width {dims[1]:.3f} > {spec['width_target']}")
    if dims[0] > tgt_l + C.EPS:
        problems.append(f"length {dims[0]:.2f} > planned {tgt_l:.2f}")
    for i in interf["interferences"]:
        if i.get("volume_mm3", 1) > C.MIN_OVERLAP_MM3:
            problems.append(f"interference {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    for u in interf.get("unchecked", []):
        problems.append(f"pair not checked: {u['a']} x {u['b']}: {u['reason'][:80]}")
    frags = [b["name"] for b in bodies if re.search(r" \(\d+\)$", b["name"])]
    if frags:
        problems.append(f"disconnected fragments (body split into several solids): {frags}")
    nc = [b["name"] for b in bodies if not b.get("closed")]
    if nc:
        problems.append(f"open bodies: {nc}")
    for name, t, exc in C.declared_walls(p, L):
        if name == "button_membrane":
            continue
        if t + C.EPS < C.MIN_FEATURE:
            problems.append(f"wall {name} = {t:.2f} mm < {C.MIN_FEATURE}")
        elif t + C.EPS < C.MIN_WALL:
            (warns if exc or name in C.WALL_EXCEPTIONS else problems).append(f"wall {name} = {t:.2f} mm < {C.MIN_WALL} ({'documented exception' if exc else 'NOT allowed'})")
    # v0.1.0 walls: battery ribs, lid membranes, window rim
    bv, ch = p["v010"]["battery"], p["v010"]["charge"]
    for name, t in (("battery_retention_rib", bv["rib_t"]), ("button_membrane", p["button"]["memb_t"]), ("charge_gasket_ring", ch["gasket_w"])):
        if t + C.EPS < C.MIN_FEATURE:
            problems.append(f"wall {name} = {t:.2f} mm < {C.MIN_FEATURE}")
        elif t + C.EPS < C.MIN_WALL:
            warns.append(f"wall {name} = {t:.2f} mm < {C.MIN_WALL} (documented exception, printable floor 0.4)")
    wall_win = min(L["v010"]["window"]["x"][0] - 0.0 - L["v010"]["gasket"]["outer_x"][0], 99)
    by = {b["name"]: b for b in bodies}
    pr, wr = check_v010(p, L, by)
    problems += pr
    warns += wr
    if not L["coax"]:
        pr_, wr_ = C.check_real_models(outdir, variant)
        problems += pr_
        warns += wr_
    if with_variants:
        pv, wv = C.check_insert_variants(outdir, variant, p, {**L, "length": L["x_r1"] + p["dock_interface_frozen"]["tail_u"]})
        problems += pv
        warns += wv
    exports = ["bottom", "top", "carriage", "reservoir", "plunger_core", "plunger_seal", "gasket", "mould_lower", "mould_upper", "cannula_adapter", "dock_insert",
               "plunger_nose", "valve_plug", "thrust_sleeve", "thrust_collar", "charge_gasket"]
    for part in exports:
        for ext in ("step", "stl"):
            if not (outdir / f"{variant}_{part}.{ext}").exists():
                problems.append(f"missing export {variant}_{part}.{ext}")
    return {"variant": variant, "dims": dims, "target_l": tgt_l, "problems": problems, "warns": warns, "bodies": len(bodies), "checked": interf.get("checked")}


def main(args) -> int:
    out = Path(args.outdir or (HERE / "out" / "v010"))
    p = json.loads((out / "params.used.json").read_text()) if (out / "params.used.json").exists() else None
    if p is None:
        raise SystemExit("run generate.py --variant v010 first")
    sizes = args.sizes or list(p["variants"])
    failed = False
    print(f"{'Size':8} {'L':>7} {'B':>6} {'H':>6}  {'planned L':>9}  status   (v010 integrated pod)")
    for k, v in enumerate(sizes):
        r = check_size(out, v, p, args.ignore_length, k == 0)
        d = r["dims"]
        failed |= bool(r["problems"])
        print(f"{v:8} {d[0]:7.2f} {d[1]:6.2f} {d[2]:6.2f}  {r['target_l']:9.2f}  {'PASS' if not r['problems'] else 'FAIL'}  ({r['bodies']} bodies, {r['checked']} solids interference-checked)")
        for m in r["problems"]:
            print(f"    FAIL: {m}")
        for m in r["warns"]:
            print(f"    WARN: {m}")
    try:
        from op_cradle import check_cradle
        pr, wr = check_cradle(p, out)
        failed |= bool(pr)
        print("cradle: " + ("PASS" if not pr else "FAIL"))
        for m in pr:
            print(f"    FAIL: {m}")
        for m in wr:
            print(f"    WARN: {m}")
    except ImportError:
        pass
    return 1 if failed else 0
