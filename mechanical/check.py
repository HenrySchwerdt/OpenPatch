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
import subprocess
import sys
import tempfile
from pathlib import Path

from op_build import part_sets
from op_layout import HERE, load_params

CLI = "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli"
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
        ("plunger_flange", sl["flange"], False),
        ("plunger_socket_wall_z", ((rs["h_in"] - 2 * rs["plunger_clr"]) - (dr["arm_t"] + 0.1)) / 2, False),
        ("tongue_x", dr["tongue_x"], False),
        ("septum_boss_wall", (p["septum"]["boss_d"] - (p["septum"]["d"] + 2 * p["septum"]["bore_clr"])) / 2, True),
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


def check_bench(p: dict, L: dict, bodies: list) -> tuple[list, list]:
    """Bench-pod checks: board inside the cavity, clearances, sensor-magnet gaps, contact compression, FFC slot, adapter."""
    problems, warns = [], []
    b, B = p["bench"], L["bench"]
    by = {x["name"]: x for x in bodies}
    for need in ("pod_board", "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock", "spring0", "ffc_conn", "ffc_cable",
                 "cannula_adapter", "dock_magnet", "motor_strip"):
        if need not in by:
            problems.append(f"bench body missing: {need}")
    for gone in ("battery", "qi_coil", "rf_module", "pcb", "buzzer"):
        if gone in by:
            problems.append(f"integrated part present in bench pod: {gone}")
    if problems:
        return problems, warns
    bd = by["pod_board"]["bbox"]
    mn, mx = bd["min"], bd["max"]
    # board inside the inner cavity (rounded corners are checked by the interference test against 'bottom'/'top')
    if mn[0] < L["xi0"] + 0.3 or mx[0] > L["x_end"] - 0.3 or mn[1] < L["yi0"] + 0.3 or mx[1] > L["yi1"] - 0.3:
        problems.append(f"pod_board bbox {mn[:2]}..{mx[:2]} closer than 0.3 mm to the housing walls")
    # motor: board edge to the motor body (cylinder, radius 3 about y_m)
    mo = by["motor"]["bbox"]
    gap_y = mn[1] if False else None
    ymot = L["y_m"] - p["drive"]["motor_d"] / 2
    zr = b["board_z0"] - L["z_axis"]
    half = (p["drive"]["motor_d"] ** 2 / 4 - zr * zr) ** 0.5
    wing_top = p["bench"]["wing_v"][1]
    clr = (L["y_m"] - half) - wing_top
    if mn[0] < mo["max"][0] + 0.2 and clr < BENCH_MIN_CLR:
        problems.append(f"board wing to motor clearance {clr:.2f} mm")
    # board (z-range 4.9..5.7) must not meet the motor tail region: lobe starts beyond motor end
    if L["x_r1"] + b["lobe_u"] < L["mot_end"] + 0.3 - 1e-6:
        problems.append("board lobe overlaps the motor end region")
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
    # contact compression
    ct = B["contacts"]
    if not (0.2 <= ct["preload_compression_mm"] <= 0.5):
        problems.append(f"spring contact compression {ct['preload_compression_mm']:.2f} mm outside 0.2..0.5")
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
    warns.append(f"bench: board {B['width']:.1f} x {B['height']:.1f} mm identical for all sizes; dock gap {gap:.2f} mm, "
                 f"contact compression {ct['preload_compression_mm']:.2f} mm, motor-wing clearance {clr:.2f} mm")
    return problems, warns


def check_size(outdir: Path, variant: str, p: dict, ignore_length: bool) -> dict:
    mode = p.get("mode", "integrated")
    MFG_PARTS, _, EXCLUDE_PAIRS = part_sets(mode)
    results = eval_design(outdir / f"{variant}.sc", EXCLUDE_PAIRS)
    measure = next(r for r in results if "bodies" in r and "body_count" in r)
    interf = next(r for r in results if "interferences" in r)
    bodies = measure["bodies"]
    # bench: FFC cable and the adapter's hose barb are test-fixture items that leave the housing by design
    lo, hi = envelope([b for b in bodies if not (mode == 'bench' and b['name'] in ('ffc_cable', 'cannula_adapter'))])
    dims = [hi[i] - lo[i] for i in range(3)]
    spec = p["spec"]
    tgt_l = spec["length_targets"][variant]
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
    exports = ["bottom", "top", "carriage", "reservoir", "plunger_core", "plunger_seal", "gasket", "mould_lower", "mould_upper"]
    exports += ["cannula_adapter"] if mode == "bench" else ["reservoir_cnc_lower", "reservoir_cnc_upper"]
    for part in exports:
        for ext in ("step", "stl"):
            if not (outdir / f"{variant}_{part}.{ext}").exists():
                problems.append(f"missing export {variant}_{part}.{ext}")
    return {"variant": variant, "dims": dims, "target_l": tgt_l, "problems": problems, "warns": warns,
            "bodies": len(bodies), "pairs": interf.get("pairs_candidate"), "checked": interf.get("checked")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=["integrated", "bench"], default="integrated")
    ap.add_argument("--outdir")
    ap.add_argument("--sizes", nargs="*")
    ap.add_argument("--ignore-length", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    out = Path(args.outdir or (HERE / "out" / "bench" if args.variant == "bench" else HERE / "out"))
    p = load_params(out / "params.used.json") if (out / "params.used.json").exists() else load_params()
    p["mode"] = args.variant
    sizes = args.sizes or list(p["variants"])
    failed = False
    print(f"{'Size':8} {'L':>7} {'B':>6} {'H':>6}  {'target L':>8}  status")
    for v in sizes:
        r = check_size(out, v, p, args.ignore_length)
        d = r["dims"]
        status = "PASS" if not r["problems"] else "FAIL"
        failed |= bool(r["problems"])
        print(f"{v:8} {d[0]:7.2f} {d[1]:6.2f} {d[2]:6.2f}  {r['target_l']:8.1f}  {status}  "
              f"({r['bodies']} bodies, {r['checked']} solids interference-checked)")
        for m in r["problems"]:
            print(f"    FAIL: {m}")
        for m in r["warns"]:
            print(f"    WARN: {m}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
