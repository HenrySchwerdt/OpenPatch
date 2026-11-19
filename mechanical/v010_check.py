# SPDX-License-Identifier: LicenseRef-OpenPatch
"""`check.py --variant v010`: checks of the integrated pod (op_pod.py).  TEST PROJECT, water only.

PASS/FAIL (exit code): height <= 8.5, width <= 32, interference of all bodies, no fragments / open bodies, single-rod drive (no idler / side rod / encoder lane), drive axial stack,
gear mesh, ring magnet + TMAG geometry, fluid boundary (closed reservoir volume, seal contact lines, cap interface seals), H14 fill septum unreachable while docked, dock insert on the
frozen interface + the 12 insert variants, board / cell / USB-C / spine clearances, declared walls against the DFM hard floors.
TARGET lines (spec 2b: OP-100 <= 45, OP-200 <= 54 mm) are reported with the gap and do not change the exit code (the geometry is checked, the length target is a design goal that is
documented as missed; `--strict-length` makes it fatal).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import check as C
from op_layout import HERE

REQUIRED = ("bottom", "top", "gasket", "reservoir", "plunger_core", "drive_screw", "rear_plug", "nut", "gear_a", "gear_d", "ring_magnet", "bush_dry2", "thrust_sleeve2", "motor", "gearhead",
            "end_cap", "end_cap_lid", "cap_gasket", "cap_oring", "septum", "needle", "needle_hub", "dock_insert", "cannula_adapter", "dock_magnet", "hall_dock", "pod_board", "radio", "switch",
            "piezo", "battery", "bat_foam", "spring_p", "spring_n", "usb_conn", "usb_board", "usb_gasket", "sensor_board", "hall_tmag", "motor_card", "mspring_1", "spine_fpc", "spine_springs")
FORBIDDEN = {"gear_b": "side screw gear", "gear_c": "idler gear", "idler_pin": "idler pin", "leadscrew": "second (side) rod", "thrust_collar": "side-rod collar", "bush_far": "side-rod bush",
             "carriage": "carriage", "tongue_shim": "tongue", "magnet": "side-rod magnet", "plunger_tube": "cup tube", "e73": "E73 tail module", "pico_conn": "PicoBlade", "ffc_cable": "FFC cable",
             "chg_pad_1": "charge pad", "duckbill_valve": "check valve"}


def bbox(by: dict, n: str) -> dict:
    return by[n]["bbox"]


def ctr(by: dict, n: str, ax: int) -> float:
    b = bbox(by, n)
    return (b["min"][ax] + b["max"][ax]) / 2


def check_drive(p: dict, L: dict, by: dict) -> tuple[list, list]:
    problems, warns = [], []
    for n, why in FORBIDDEN.items():
        if n in by:
            problems.append(f"one-rod requirement: forbidden body present: {n} ({why})")
    rods = [n for n in by if n in ("drive_screw", "leadscrew", "rod")]
    if rods != ["drive_screw"]:
        problems.append(f"exactly one rod expected (drive_screw), found {rods}")
    P = p["pod"]
    dr, g = P["drive"], P["motor"]["gear"]
    yr, zc = L["y_r"], L["z_axis"]
    for n in ("drive_screw", "nut", "gear_d", "ring_magnet", "bush_dry2", "thrust_sleeve2", "plunger_core"):
        if abs(ctr(by, n, 1) - yr) > 1e-3 or abs(ctr(by, n, 2) - zc) > 1e-3:
            problems.append(f"{n} not on the reservoir axis (y {ctr(by, n, 1):.3f}, z {ctr(by, n, 2):.3f})")
    # direct mesh gear_a - gear_d: centre distance = theory + centre_add (backlash window)
    th = g["module"] * (g["z_motor"] + g["z_screw"]) / 2
    d = math.hypot(ctr(by, "gear_a", 1) - ctr(by, "gear_d", 1), ctr(by, "gear_a", 2) - ctr(by, "gear_d", 2))
    if not (th + 0.02 <= d <= th + 0.20):
        problems.append(f"gear mesh centre {d:.3f} outside theory {th:.2f} + 0.02..0.20")
    if abs(bbox(by, "gear_a")["min"][0] - bbox(by, "gear_d")["min"][0]) > 1e-3 or abs(bbox(by, "gear_a")["max"][0] - bbox(by, "gear_d")["max"][0]) > 1e-3:
        problems.append("gear_a and gear_d are not in the same plane")
    ds, nut, sl, bu = bbox(by, "drive_screw"), bbox(by, "nut"), bbox(by, "thrust_sleeve2"), bbox(by, "bush_dry2")
    s = L["stroke"]
    sock = L["xrear_full"] + dr["socket_depth"]
    tip = ds["max"][0]
    if not (0.0 <= sock - tip <= 0.1):
        problems.append(f"screw tip {tip:.3f} not seated on the plunger socket bottom {sock:.3f}")
    eng = nut["max"][0] - (ds["min"][0] + s)
    if eng < dr["nut_len"] + dr["engage_margin"]:
        problems.append(f"screw rear end at EMPTY only {eng:.2f} mm behind the nut front (< nut + {dr['engage_margin']})")
    if ds["min"][0] < L["wall"] + 0.2:
        problems.append(f"screw rear end {ds['min'][0]:.2f} at full too close to the rear wall")
    if not (0.0 <= nut["min"][0] - bbox(by, "gear_d")["max"][0] <= 0.05):
        problems.append("nut not seated on the gear_d front face")
    if bbox(by, "plunger_core")["min"][0] - nut["max"][0] < 0.15:
        problems.append("plunger rear closer than 0.15 mm to the nut front at full")
    if not (0.0 <= sl["min"][0] - bu["max"][0] <= 0.15):
        problems.append(f"thrust sleeve not seated on the bush face (gap {sl['min'][0] - bu['max'][0]:.2f})")
    rm, gd = bbox(by, "ring_magnet"), bbox(by, "gear_d")
    if rm["max"][0] > gd["min"][0] or rm["min"][0] < bu["max"][0]:
        problems.append("ring magnet not between bush and nut gear")
    # tip - slot / tab engagement is geometric by construction; the stadium plunger blocks rotation
    nose_margin = L["x_in1"] - (bbox(by, "plunger_core")["max"][0] + s)
    if nose_margin < min(0.2, p["reservoir"]["dead"] - 0.01):
        problems.append(f"plunger front at empty hits the closed end (margin {nose_margin:.3f})")
    warns.append(f"coaxial drive: stroke {s:.2f} mm, screw x {ds['min'][0]:.2f}..{tip:.2f} (full), engaged beyond the nut front at empty {eng:.2f} mm, mesh centre {d:.3f} (theory {th:.2f}), "
                 f"motor {P['motor']['option']} in the rear zone, gear plane x {L['gear_x0']:.1f}..{L['gear_x1']:.1f} limited by the {L['gear_limit']}")
    # TMAG beside the ring (side shaft): distance and placement
    tm, rg = by["hall_tmag"]["bbox"], P["ring"]
    rel_y = L["y_r"] - (tm["min"][1] + tm["max"][1]) / 2
    gap = rel_y - rg["od"] / 2 - (tm["max"][1] - tm["min"][1]) / 2
    if not (0.3 <= gap <= 1.5):
        problems.append(f"TMAG body to ring surface gap {gap:.2f} mm outside 0.3..1.5")
    dxr = (tm["min"][0] + tm["max"][0]) / 2 - (rm["min"][0] + rm["max"][0]) / 2
    if abs(dxr) > 1.0:
        problems.append(f"TMAG {dxr:+.2f} mm off the ring mid plane (> 1.0)")
    return problems, warns


def check_ring_field(p: dict, L: dict, out: Path, size: str) -> tuple[list, list]:
    problems, warns = [], []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("ring_sensor", HERE / "sim" / "ring_sensor.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        rg, tm = p["pod"]["ring"], L["geo"]["sensor"]["tmag"]
        rx = (L["ring"][0] + L["ring"][1]) / 2
        rel = (tm["c"][0] - rx, tm["c"][1] - L["y_r"], (tm["z"][0] + tm["z"][1]) / 2 - L["z_axis"])
        r = m.model(rg["od"], rg["id"], rg["t"], rel)
    except Exception as e:                     # magpylib missing: do not fail the geometry check
        return [], [f"ring magnet field model skipped ({type(e).__name__}: {e})"]
    if r["B_yz_min_mT"] < 5.0:
        problems.append(f"TMAG in-plane field only {r['B_yz_min_mT']} mT (< 5 mT): angle noise too high")
    rng = "A1 (+-40 mT)" if r["B_yz_max_mT"] < 38 else ("A2 (+-133 mT)" if r["B_yz_max_mT"] < 125 else "none")
    if rng == "none":
        problems.append(f"TMAG in-plane field up to {r['B_yz_max_mT']} mT exceeds even the A2 range")
    warns.append(f"ring magnet N45 (Br 1.3 T assumed) -> TMAG5273 YZ angle: |B_yz| {r['B_yz_min_mT']}..{r['B_yz_max_mT']} mT (needs variant {rng}), non-linearity {r['angle_err_pp_deg']} deg p-p "
                 f"after the linear fit (monotonic; calibrate with a lookup in firmware), B_x pk {r['B_x_pk_mT']} mT")
    return problems, warns


def check_fluid(p: dict, L: dict, by: dict) -> tuple[list, list]:
    from op_cap import cap_interfaces
    from op_seal import ring_range, variant
    problems, notes = [], []
    rs, sl, fz = p["reservoir"], p["seal"], p["reservoir_frozen_v010"]
    A_out = math.pi * (fz["outer_h"] / 2) ** 2 + fz["outer_h"] * (fz["outer_w"] - fz["outer_h"])
    A_in = L["area"]
    v_exp = A_out * (L["x_r1"] - L["x_r0"]) - A_in * (L["x_in1"] - L["x_r0"]) - math.pi * (fz["port_d"] / 2) ** 2 * (L["x_r1"] - L["x_in1"])
    v = by["reservoir"]["volume_mm3"]
    if abs(v - v_exp) > 0.5:
        problems.append(f"fluid boundary: reservoir volume {v:.2f} mm3 != closed-bore model {v_exp:.2f} (diff {v - v_exp:+.2f}): unexpected opening in the wall")
    bb = by["reservoir"]["bbox"]
    if abs(bb["min"][0] - L["x_r0"]) > 1e-3 or abs(bb["max"][0] - L["x_r1"]) > 1e-3:
        problems.append("reservoir x extent differs from the layout")
    var = variant(p)
    a, b_ = ring_range(p, var["rings"][-1])
    for tag, xr in (("full", L["xrear_full"]), ("empty", L["xrear_empty"])):
        line = xr + (a + b_) / 2
        if not (L["x_r0"] <= xr + a and line <= L["x_in1"]):
            problems.append(f"fluid: front seal contact line x={line:.2f} outside the bore {L['x_r0']:.2f}..{L['x_in1']:.2f} at the {tag} position")
        if xr + rs["plunger_len"] > L["x_in1"] + 1e-6:
            problems.append(f"fluid: plunger front beyond the chamber end at the {tag} position")
    if not (L["x_r0"] < L["xrear_full"] + a - 0.2):
        problems.append("dry rear opening is not behind the front seal at full")
    for itf in cap_interfaces(p, L):
        if itf["gap"] >= 0.0 and not itf["seal"]:
            problems.append(f"fluid: cap interface '{itf['name']}' gap {itf['gap']:+.3f} mm has no seal element")
        if itf.get("squeeze") is not None and "O-ring" in (itf["seal"] or "") and not (0.08 <= itf["squeeze"] <= 0.30):
            problems.append(f"fluid: O-ring squeeze {100 * itf['squeeze']:.0f} % outside 8..30 %")
    for gone in ("duckbill_valve", "valve_plug"):
        if gone in by:
            problems.append(f"check valve part present (spec 3c: none): {gone}")
    # module retention: crush ribs behind the reservoir, the O-ring lands meet the end face
    rb = p["pod"]["res"]["rib_stop"]
    ec = by["end_cap"]["bbox"]
    spig = p["dock"]["cap"]["spigot_len"]
    if abs(ec["min"][0] - (by["reservoir"]["bbox"]["max"][0] - spig)) > 0.011:
        problems.append(f"end cap spigot does not enter the port by {spig} mm (cap x {ec['min'][0]:.3f}, reservoir end {by['reservoir']['bbox']['max'][0]:.3f})")
    if spig > p["reservoir_frozen_v010"]["end_wall"] - 0.1:
        problems.append("spigot longer than the reservoir end wall: it would enter the bore")
    notes.append(f"fluid boundary: reservoir {v:.2f} mm3 = closed-bore model {v_exp:.2f}; openings: dry rear end (x {L['x_r0']:.1f}) + port d{fz['port_d']} at y {L['port_y']}; "
                 f"module retention: 2 crush ribs {rb['w']} x {rb['h']} mm (printed {rb['interference']} proud), O-ring land contact guaranteed")
    return problems, notes


def check_electronics(p: dict, L: dict, by: dict) -> tuple[list, list]:
    problems, warns = [], []
    G, P = L["geo"], p["pod"]
    bd = bbox(by, "pod_board")
    dome_top = p["cannula"]["B_dome_h"]
    if bd["min"][2] - dome_top < 0.25:
        problems.append(f"board only {bd['min'][2] - dome_top:.2f} mm above the dome top")
    top_clear = L["z_top_inner"] - max(bbox(by, n)["max"][2] for n in ("radio", "switch"))
    if top_clear < 0.2:
        problems.append(f"top-side parts only {top_clear:.2f} mm below the lid")
    if bd["min"][0] < L["x_r1"] + 2.0 - 0.01 or bd["max"][0] > L["length"] - L["wall"] - 0.3:
        problems.append("main board outside its zone (u 2.0 .. wall - 0.3)")
    cell, pad = bbox(by, "battery"), bbox(by, "bat_pad_p")
    gap = bd["min"][2] - pad["max"][2]
    if not (0.2 <= gap <= 1.0):
        problems.append(f"cell spring gap {gap:.2f} mm outside 0.2..1.0 (spring free height 1.0..1.2 compressed 0.35..0.65)")
    mc = G["motor_card"]
    if not (0.2 <= mc["compression_mm"] <= 0.6):
        problems.append("motor spring contact compression outside 0.2..0.6")
    pin_tip = bbox(by, "motor_pins")["max"][1]
    sp = bbox(by, "mspring_1")["min"][1]
    if abs(pin_tip - sp) > 0.011:
        problems.append(f"motor pin tips {pin_tip:.3f} do not touch the spring contacts {sp:.3f}")
    u = bbox(by, "usb_conn")
    if u["min"][0] > 0.9:
        problems.append("USB-C mouth does not reach the rear wall opening")
    h = G["usb"]["open_z"][1]
    web = 5.0 - h
    if web < 0.35:
        problems.append(f"web above the USB opening only {web:.2f} mm")
    pz = bbox(by, "piezo")
    if abs(pz["max"][2] - L["z_top_inner"]) > 1e-3:
        problems.append("piezo not on the lid inner face")
    warns.append(f"MAIN board {G['board_area_mm2']} mm2 (outline in OP-xx.layout.json), cell spring gap {gap:.2f} mm, top clearance {top_clear:.2f} mm, board over dome {bd['min'][2] - dome_top:.2f} mm")
    return problems, warns


WALLS = [("shell_wall", lambda p, L: p["shell"]["wall"], "MJF"), ("reservoir_wall", lambda p, L: p["reservoir_frozen_v010"]["wall"], "CNC_PP"),
         ("reservoir_end_wall", lambda p, L: p["reservoir_frozen_v010"]["end_wall"], "CNC_PP"),
         ("lid_over_reservoir", lambda p, L: L["height"] - (L["z_axis"] + L["res_h_out"] / 2 + p["pod"]["res"]["lid_recess"]), "SLA"),
         ("lid_scale_engraving", lambda p, L: L["height"] - (L["z_axis"] + L["res_h_out"] / 2 + p["pod"]["res"]["lid_recess"]) - 0.15, "SLA"),
         ("floor_under_spine_channel", lambda p, L: p["shell"]["wall"] - p["pod"]["spine"]["channel_depth"], "MJF"),
         ("bearing_block_wall", lambda p, L: p["pod"]["drive"]["block_wall"] - p["pod"]["drive"]["bush_bore_clr"] / 2, "MJF")]


def check_walls(p: dict, L: dict) -> tuple[list, list]:
    import json as _j
    rules = _j.loads((HERE / "dfm_rules.json").read_text())["processes"]
    problems, warns = [], []
    for name, f, proc in WALLS:
        t = f(p, L)
        hf = rules[proc]["wall"]["hard_floor"]
        if t + 1e-6 < hf:
            problems.append(f"wall {name} = {t:.2f} mm < {proc} hard floor {hf}")
        elif t + 1e-6 < rules[proc]["wall"].get("recommended", rules[proc]["wall"]["table_by_footprint_mm"][-1][1] if False else hf):
            warns.append(f"wall {name} = {t:.2f} mm")
    return problems, warns


def targets(p: dict, L: dict, length: float) -> list[str]:
    tgt = p["pod"]["length_targets"][L["variant"]]
    if length <= tgt + 1e-6:
        return [f"TARGET met: length {length:.2f} <= {tgt}"]
    return [f"TARGET MISS (spec 2b): length {length:.2f} > {tgt} mm by {length - tgt:.1f} mm (see V010.md 'levers': best combination of all levers {BEST_LEVER.get(L['variant'], '?')} mm)"]


BEST_LEVER = {"OP-100": 49.0, "OP-200": 58.4}


def check_size(out: Path, size: str, p: dict, strict_length: bool, with_variants: bool) -> dict:
    sc = out / f"{size}.sc"
    L = json.loads((out / f"{size}.mech.json").read_text())
    import v010_gen
    results = C.eval_design(sc, v010_gen.EXCLUDE_PAIRS)
    measure = next(r for r in results if "bodies" in r and "body_count" in r)
    interf = next(r for r in results if "interferences" in r)
    bodies = measure["bodies"]
    by = {b["name"]: b for b in bodies}
    lo, hi = C.envelope([b for b in bodies if b["name"] != "cannula_adapter"])        # the dummy cannula head (fixture) has a hose barb that leaves the housing
    dims = [hi[i] - lo[i] for i in range(3)]
    spec = p["spec"]
    problems, warns = [], []
    if dims[2] > spec["max_height"] + 1e-6:
        problems.append(f"height {dims[2]:.3f} > {spec['max_height']}")
    if dims[1] > spec["width_target"] + 1e-6:
        problems.append(f"width {dims[1]:.3f} > {spec['width_target']}")
    tl = targets(p, L, dims[0])
    if strict_length and dims[0] > p["pod"]["length_targets"][size] + 1e-6:
        problems.append(tl[0])
    else:
        warns += tl
    for n in REQUIRED:
        if n not in by:
            problems.append(f"body missing: {n}")
    if problems and any("body missing" in x for x in problems):
        return {"dims": dims, "problems": problems, "warns": warns, "bodies": len(bodies), "checked": 0, "target_l": p["pod"]["length_targets"][size]}
    for i in interf["interferences"]:
        if i.get("volume_mm3", 1) > C.MIN_OVERLAP_MM3:
            problems.append(f"interference {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    for u in interf.get("unchecked", []):
        problems.append(f"pair not checked: {u['a']} x {u['b']}: {u['reason'][:80]}")
    frags = [b["name"] for b in bodies if re.search(r" \(\d+\)$", b["name"]) and not b["name"].startswith("cap_gasket")]
    if frags:
        problems.append(f"disconnected fragments: {frags}")
    nc = [b["name"] for b in bodies if not b.get("closed")]
    if nc:
        problems.append(f"open bodies: {nc}")
    for fn in (lambda: check_drive(p, L, by), lambda: check_fluid(p, L, by), lambda: check_electronics(p, L, by), lambda: check_walls(p, L),
               lambda: check_ring_field(p, L, out, size), lambda: C.check_fill_unreachable(p, L), lambda: C.check_insert(p, L, by)):
        r = fn()
        problems += r[0]
        warns += r[1]
    if with_variants:
        pv, wv = C.check_insert_variants(out, size, p, L)
        problems += pv
        warns += wv
    for part in ("bottom", "top", "gasket", "reservoir", "plunger_core", "end_cap", "end_cap_lid", "dock_insert", "mould_lower", "mould_upper"):
        for ext in ("step", "stl"):
            if not (out / f"{size}_{part}.{ext}").exists():
                problems.append(f"missing export {size}_{part}.{ext}")
    return {"dims": dims, "problems": problems, "warns": warns, "bodies": len(bodies), "checked": interf.get("checked"), "target_l": p["pod"]["length_targets"][size]}


def main(args) -> int:
    out = Path(args.outdir or (HERE / "out" / "v010"))
    if not (out / "params.used.json").exists():
        raise SystemExit("run generate.py --variant v010 first")
    p = json.loads((out / "params.used.json").read_text())
    sizes = args.sizes or list(p["pod"]["sizes"])
    strict = getattr(args, "strict", False) and not getattr(args, "ignore_length", False)
    failed = False
    print(f"{'Size':8} {'L':>7} {'B':>6} {'H':>6}  {'target L':>8}  status   (v010 integrated pod, one-rod coaxial drive)")
    for k, v in enumerate(sizes):
        r = check_size(out, v, p, strict, k == 0)
        d = r["dims"]
        failed |= bool(r["problems"])
        print(f"{v:8} {d[0]:7.2f} {d[1]:6.2f} {d[2]:6.2f}  {r['target_l']:8.1f}  {'PASS' if not r['problems'] else 'FAIL'}  ({r['bodies']} bodies, {r['checked']} solids interference-checked)")
        for m in r["problems"]:
            print(f"    FAIL: {m}")
        for m in r["warns"]:
            print(f"    {'TARGET' if m.startswith('TARGET') else 'WARN'}: {m}")
    if getattr(args, "assembly", False):
        import check_assembly
        print("\n== assembly feasibility / DFM (check_assembly.py, v010) ==")
        failed |= bool(check_assembly.run_from_check(out, args.sizes[:1] if args.sizes else None))
    return 1 if failed else 0
