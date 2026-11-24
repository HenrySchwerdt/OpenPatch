#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Check the v0.1.0 "cart" pump in out/v010-cart (run cart_gen.py first). TEST PROJECT, water only.

Interference at FULL (as modelled) and at EMPTY (rod, slider, pusher, stopper moved by the stroke), envelope vs the Accu-Chek Insight,
stroke available in the cartridge, rod engaged in the gear nut over the whole stroke, slider in its channel, rod never wet, gear mesh
clearances, thrust vs need, unchanged cup-pod board outline, exports present.  Exit code 1 on any FAIL.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import check as C
import op_cart
from op_cmds import Script
from op_layout import HERE, load_params

TAG = "OP-CART"
SEAL_BREAKAWAY_N = 8.0          # ESTIMATE: glass cartridge + bromobutyl stopper, dry/water; MEASURE on the sample (docs/insight-research.md)
OCCLUSION_KPA = 150.0           # bench design point for the occlusion force budget (Insight alarm <= 330 kPa, max 350 kPa: user manual VERIFIED)
MARGIN = 1.5


def thrust(p: dict, L: dict) -> dict:
    g, rd = p["cart"]["gears"], p["cart"]["rod"]
    T_gb = 1.6 * 9.80665e-3 * 10.0 * 26.45 * 0.64                     # N mm at the NFP gearhead output (pull-out 1.6 gf cm x 26.45 x 0.64, parts.md)
    T_nut = T_gb * (g["z_rod"] / g["z_pinion"]) * g["eta"]
    F = 2 * math.pi * rd["eta_screw"] * T_nut / rd["pitch"]
    A = L["bore_area"]
    f_occ = OCCLUSION_KPA * 1e3 * A * 1e-6
    need = SEAL_BREAKAWAY_N + f_occ
    return {"T_gearhead_Nmm": round(T_gb, 2), "T_nut_Nmm": round(T_nut, 2), "F_avail_N": round(F, 1), "F_seal_N": SEAL_BREAKAWAY_N, "F_occ_N": round(f_occ, 1),
            "F_need_N": round(need, 1), "ratio": round(F / need, 2), "stall_pressure_kPa": round(F / A * 1e3, 0)}


def empty_bodies(p: dict, L: dict) -> tuple[Script, list]:
    """Moving parts at EMPTY (copies, prefix e_) + the exclude pairs that are overlaps by design."""
    c = p["cart"]
    yc, zc = L["y_c"], L["zc"]
    E = L["empty"]
    s = Script()
    s.cyl("e_rod", "X", (0, yc, zc), c["rod"]["d"], *E["rod"])
    s.box("e_slider", tuple(E["slider"]), (yc - c["slider"]["w"] / 2, yc + c["slider"]["w"] / 2), (zc - c["slider"]["h"] / 2, zc + c["slider"]["h"] / 2))
    s.cyl("e_pusher", "X", (0, yc, zc), c["pusher"]["d"], *E["pusher"])
    s.cyl("e_stopper", "X", (0, yc, zc), c["cartridge"]["id"], *E["stopper"])
    moving = ["rod", "slider", "pusher", "stopper"]
    ex = []
    for a in ("e_rod", "e_slider", "e_pusher", "e_stopper"):
        ex += [[a, m] for m in moving]
        ex += [[a, b] for b in ("e_rod", "e_slider", "e_pusher", "e_stopper") if b != a]
    ex += [["e_rod", "rod_nut"], ["e_rod", "gear_rod"], ["e_stopper", "cartridge"]]
    return s, ex


def run_extra(sc: Path, s: Script, exclude: list) -> dict:
    cmds = s.dumps() + [{"command": "inspect.interference", "params": {"exclude_pairs": exclude}}]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(cmds, fh)
        tmp = fh.name
    res = subprocess.run([C.CLI, "run", tmp, "--in", str(sc), "--results", "--quiet"], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if res.returncode != 0:
        raise SystemExit(res.stdout + res.stderr)
    return next(r for r in json.loads(res.stdout) if "interferences" in r)


def main() -> int:
    out = HERE / "out" / "v010-cart"
    sc = out / f"{TAG}.sc"
    if not sc.exists():
        print("run cart_gen.py first")
        return 2
    p = op_cart.prepare(load_params())
    p["cart"] = json.loads((out / "params.used.json").read_text())         # check what was generated (incl. --set overrides)
    L = json.loads((out / f"{TAG}.mech.json").read_text())
    c, tg = p["cart"], p["cart"]["targets"]
    prob, note = [], []
    res = C.eval_design(sc, op_cart.EXCLUDE_PAIRS)
    meas = next(r for r in res if "bodies" in r and "body_count" in r)
    by = {b["name"]: b for b in meas["bodies"]}
    for nm in op_cart.PART_NAMES:
        if nm not in by:
            prob.append(f"body {nm} missing")
    housing = [by[n] for n in ("bottom", "top") if n in by]
    lo, hi = C.envelope(housing)
    dims = [round(hi[i] - lo[i], 2) for i in range(3)]
    allb = [b for n, b in by.items() if not n.startswith("ko_") and n not in ("tubing",)]
    lo2, hi2 = C.envelope(allb)
    note.append(f"housing {dims[0]} x {dims[1]} x {dims[2]} mm; with adapter (tubing stub excluded) {round(hi2[0] - lo2[0], 2)} x {round(hi2[1] - lo2[1], 2)} x {round(hi2[2] - lo2[2], 2)} mm")
    if dims[2] > tg["height"] - 0.01 or hi2[2] - lo2[2] > tg["height"] - 0.01:
        prob.append(f"height {dims[2]} not below the Insight {tg['height']}")
    if dims[2] > tg["height_goal"]:
        note.append(f"TARGET: height {dims[2]} > goal {tg['height_goal']} (set by the receiver bore / cartridge OD estimate {L['big']})")
    if hi2[0] - lo2[0] >= tg["length_with_adapter"]:
        prob.append(f"length with adapter {hi2[0] - lo2[0]:.2f} not below the Insight {tg['length_with_adapter']}")
    if dims[1] >= tg["width"]:
        prob.append(f"width {dims[1]} not below the Insight {tg['width']}")
    for k in ("bottom", "top"):
        if k in by and not by[k].get("closed", True):
            prob.append(f"{k} is not a closed solid")
    inter = next(r for r in res if "interferences" in r)
    for i in inter["interferences"]:
        if i["volume_mm3"] > 1e-4:
            prob.append(f"interference FULL {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    s, ex = empty_bodies(p, L)
    r2 = run_extra(sc, s, op_cart.EXCLUDE_PAIRS + ex)
    for i in r2["interferences"]:
        if i["volume_mm3"] > 1e-4 and (i["a"].startswith("e_") or i["b"].startswith("e_")):
            prob.append(f"interference EMPTY {i['a']} x {i['b']}: {i['volume_mm3']:.4f} mm3")
    note.append(f"moving parts checked at FULL and EMPTY (stroke {L['stroke']} mm)")
    # stroke, engagement, channel, wet volume
    if L["stroke_avail"] < L["stroke"]:
        prob.append(f"stroke {L['stroke']} > available {L['stroke_avail']} in the cartridge (estimate)")
    E = L["empty"]
    g0, g1 = L["gear"]
    if E["rod"][0] > g0 - 0.1:
        prob.append(f"rod rear end {E['rod'][0]:.2f} passes the nut (starts {g0:.2f}) before EMPTY")
    if L["rod_full"][1] < g0 + c["nut"]["h"] + 0.5:
        prob.append("rod front end not through the nut at FULL")
    if E["slider"][1] > L["rib_r"][0] - 0.1:
        prob.append(f"slider leaves its channel at EMPTY ({E['slider'][1]:.2f} vs rib {L['rib_r'][0]:.2f})")
    if E["rod"][1] > E["stopper"][0] + 1e-6 or c["pusher"]["d"] >= c["cartridge"]["id"]:
        prob.append("rod / pusher would enter the wet volume")
    note.append(f"stroke {L['stroke']} / avail {L['stroke_avail']} mm; rod {L['rod_len']} mm, {-L['rod_past_nut_empty']:.2f} mm behind the nut at EMPTY; slider {L['slider_to_rib_empty']} mm off the rib at EMPTY")
    # gear mesh
    g = c["gears"]
    a = g["m"] * (g["z_rod"] + g["z_pinion"]) / 2
    if abs(L["a_gear"] - a) > 1e-6:
        prob.append("gear centre distance != m (z1 + z2) / 2")
    rp_tip = g["m"] * (g["z_pinion"] + 2) / 2
    if a - rp_tip - c["rod"]["d"] / 2 < 0.3:
        prob.append("pinion tip too close to the rod")
    if L["zc"] - L["gear_od"] / 2 < c["wall"] + 0.1:
        prob.append("gear tip circle touches the floor")
    # thrust
    t = thrust(p, L)
    note.append(f"thrust {t['F_avail_N']} N vs need {t['F_need_N']} N (seal {t['F_seal_N']} ESTIMATE + {OCCLUSION_KPA:.0f} kPa {t['F_occ_N']} N): {t['ratio']}x; "
                f"stall pressure {t['stall_pressure_kPa']:.0f} kPa (Insight max 350)")
    if t["ratio"] < MARGIN:
        prob.append(f"thrust margin {t['ratio']} < {MARGIN}")
    # board unchanged
    cb = p["cup"]["board"]
    if abs((cb["pcb_x"][1] - cb["pcb_x"][0]) - c["board"]["l"]) > 1e-6 or abs((cb["pcb_y"][1] - cb["pcb_y"][0]) - c["board"]["w"]) > 1e-6 or cb["pcb_z"] != c["board"]["pcb_z"]:
        prob.append("cart board envelope differs from the cup-pod main board (cup.board.pcb_*)")
    for part in op_cart.MFG_PARTS:
        for ext in ("step", "stl"):
            if not (out / f"{TAG}_{part}.{ext}").exists():
                prob.append(f"missing export {TAG}_{part}.{ext}")
    note.append(f"U/step {L['u_per_step']:.5f}; front set by {L['front_governed_by']} (neck {L['x_front_neck']}, board {L['x_front_board']})")
    rep = {"dims": dims, "thrust": t, "problems": prob, "notes": note}
    (out / "check.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    for n in note:
        print("  " + n)
    for q in prob:
        print("  FAIL " + q)
    print(f"{TAG}: {'PASS' if not prob else 'FAIL'}")
    return 1 if prob else 0


if __name__ == "__main__":
    sys.exit(main())
