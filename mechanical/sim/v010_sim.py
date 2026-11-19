#!/usr/bin/env python3
"""Simulations of the v0.1.0 integrated pod (coaxial one-rod drive, direct 16:20 mesh, wide bore, no valve): thrust margin, dose resolution, lost motion, angle sensing, dead volume / prime path.

  python3 mechanical/sim/run_all.py            # runs this module (default); the bench-pod simulations stay available as run_all.py --bench
  python3 mechanical/sim/v010_sim.py [--sizes OP-100 OP-200]

Inputs: params.json (pod, reservoir_frozen_v010, seal, drive) via op_pod.prepare, out/v010/*.mech.json (when present), the constants of common.CONST ([DS] / [LIT] / [ASM] tags).
Writes mechanical/sim/REPORT-v010.md and out/v010/sim.json.  TEST PROJECT: water only, never on a person.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
MECH = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(MECH))

from common import CONST as C, GF_CM, area_stadium, perim_stadium, table  # noqa: E402
import op_pod  # noqa: E402
import seal_model  # noqa: E402


def thread_coeff(dr: dict, mu_t: float) -> tuple[float, float]:
    """(thread torque per N [N*mm/N], efficiency) of the M1.6 x 0.35 screw (60 deg ISO thread)."""
    d, pit = dr["screw_d"], dr["screw_pitch"]
    d2 = d - 0.6495 * pit
    lam = math.atan(pit / (math.pi * d2))
    ca = math.cos(math.radians(C["thread_half_angle_deg"]))
    t = d2 / 2 * (math.tan(lam) + mu_t / ca) / (1 - mu_t * math.tan(lam) / ca)
    return t, pit / (2 * math.pi) / t


def thrust(P: dict, I_mA: float, mu_t: float = 0.22, mu_c: float = 0.18, gh_eff: float = 0.64, pair_eff: float = 0.95, z_motor: int | None = None) -> float:
    """Plunger thrust [N] of the direct (single-mesh) chain: motor pull-out torque x current / 181 mA x gearhead 26.45 x eta x z_screw / z_motor x eta_pair / (thread + collar)."""
    dr, g = P["drive"], P["pod"]["motor"]["gear"]
    zm = z_motor or g["z_motor"]
    T = C["T_pullout_gfcm"] * GF_CM * (I_mA / 181.0) * dr["gh_ratio"] * gh_eff * (g["z_screw"] / zm) * pair_eff
    rm = 1.205                                    # mean collar radius (bush face)
    tot = thread_coeff(dr, mu_t)[0] + mu_c * rm
    return T / tot


def run(sizes: list[str] | None = None) -> str:
    t0 = time.time()
    p0 = json.loads((MECH / "params.json").read_text())
    p0["drive"] = {**p0["drive"], **p0["drive_presets"][p0["drive"]["active_preset"]]}          # active motor preset (NFP-608-26.45), as generate.py applies it
    p = op_pod.prepare(p0)
    P, fz = p["pod"], p["reservoir_frozen_v010"]
    sizes = sizes or list(P["sizes"])
    dr, g = p["drive"], P["motor"]["gear"]
    A = area_stadium(fz["bore_w"], fz["bore_h"])
    per = perim_stadium(fz["bore_w"], fz["bore_h"])
    mm_step = dr["screw_pitch"] * (g["z_motor"] / g["z_screw"]) / (dr["steps_per_rev"] * dr["gh_ratio"])
    u_step = mm_step * A / 10.0
    out: dict = {"A_mm2": round(A, 2), "perimeter_mm": round(per, 2), "u_per_step": u_step, "mm_per_step": mm_step, "sizes": {}}
    rows = []

    def row(id_, req, val, margin, status, note=""):
        rows.append([id_, req, val, margin, f"**{status}**" if status != "PASS" else status, note])

    # ---- 1. thrust ------------------------------------------------------------------------------------------------------------------
    sd = seal_model.SealDesign(p, shrink=C["silicone_shrink"])
    sd.e = 0.0                                          # coaxial push: no eccentric lever (the old tongue pushed 7.2 mm off-axis)
    fr = sd.friction(C["mu_seal_design"][1], mu_g=C["mu_guide"][1])
    F_kin = float(fr["F_seal"])                         # kinetic seal force at the 56.8 mm perimeter, S2 bead
    F_brk = C["breakaway"][1] * F_kin
    P_occ = 40.0                                        # kPa: a detectable occlusion (sim REPORT 1.x convention)
    F_back = P_occ * 1e-3 * A
    F160, F181, F105 = thrust(p, 160), thrust(p, 181), thrust(p, 105)
    req = F_brk + F_back
    out["thrust"] = {"F105": F105, "F160": F160, "F181": F181, "F_seal_kin": F_kin, "F_seal_break": F_brk, "F_back_40kPa": F_back, "margin160": F160 / req, "margin105": F105 / req,
                     "perimeter_scale_vs_16x5": per / perim_stadium(16.0, 5.0)}
    row("1.1", "plunger thrust at 160 mA (single mesh z16:z20)", f"{F160:.2f} N", f"{F160 / F_brk:.1f} x seal breakaway", "PASS" if F160 > 2 * F_brk else "WARN", f"105 mA: {F105:.2f} N, 181 mA: {F181:.2f} N")
    row("1.2", "seal force, bore perimeter %.1f mm (x%.2f vs 16x5), coaxial push (no cocking)" % (per, per / perim_stadium(16.0, 5.0)), f"{F_kin:.2f} N kinetic / {F_brk:.2f} N breakaway", "", "INFO", "S2 bead, FE table")
    m160 = F160 / req
    row("1.3", "thrust margin >= 2 at 160 mA vs seal breakaway + %d kPa back-pressure x %.0f mm2 (= %.2f N)" % (P_occ, A, F_back), f"{F160:.2f} / {req:.2f} N = {m160:.2f}", f"{m160:.2f}",
        "PASS" if m160 >= 2 else "FAIL",
        "the wide bore multiplies the force of every kPa by %.2f; margin 2 needs %.1f N (z %d:20 gives %.2f N) or an occlusion criterion of <= %.0f kPa" % (A / 74.63, 2 * req, 12, thrust(p, 160, z_motor=12),
                                                                                                                       (F160 / 2 - F_brk) / A * 1e3))
    row("1.4", "pressure the drive can build at 160 mA (stall) / 105 mA", f"{(F160 - F_kin) / A * 1e3:.0f} kPa / {(F105 - F_kin) / A * 1e3:.0f} kPa", "", "INFO",
        "occlusion is detected by the encoder slip / current rise before this pressure is reached")
    p_margin2 = (F160 / 2 - F_brk) / A * 1e3
    out["thrust"]["P_for_margin2_kPa"] = p_margin2
    # ---- 2. dose resolution -------------------------------------------------------------------------------------------------------
    row("2.1", "dose per full step", f"{u_step:.5f} U ({mm_step * 1000:.3f} um of screw travel)", f"{0.05 / u_step:.1f} steps per 0.05 U", "PASS" if u_step <= 0.0125 else "WARN",
        "firmware drive preset g16-20: bore area changed 74.63 -> %.2f mm2, mm/step unchanged (%.6f): the preset constant must be rescaled (3 948.6 -> %.1f uU/step)" % (A, mm_step, u_step * 1e6))
    q = u_step / 2
    row("2.2", "quantisation error of a 0.05 U dose (+-1/2 step)", f"+-{q:.4f} U = +-{100 * q / 0.05:.1f} %", "", "PASS" if 100 * q / 0.05 <= 5 else "WARN", "spec 7: +-5 % at >= 1 U")
    lm = {}
    for nm, mm in (("thread backlash 0.08 mm (assumed)", 0.08), ("thread backlash worst 0.15 mm", 0.15)):
        lm[nm] = mm * A / 10.0
    row("2.3", "lost motion (one thread backlash, reversal only; the plunger is only ever pushed)", " / ".join(f"{v:.2f} U" for v in lm.values()), "", "PASS",
        "removed by a firmware take-up after every fill (steps: %d)" % math.ceil(0.15 / mm_step))
    out["dose"] = {"u_step": u_step, "steps_per_0p05U": 0.05 / u_step, "lost_motion_U": lm}
    # ---- 3. angle sensing (ring magnet on the nut gear) ------------------------------------------------------------------------------
    nut_rev_U = dr["screw_pitch"] * A / 10.0
    deg_per_U = 360.0 / nut_rev_U
    try:
        import ring_sensor
        mech = {}
        f = MECH / "out" / "v010" / f"{sizes[0]}.mech.json"
        L = json.loads(f.read_text()) if f.exists() else op_pod.layout(p, sizes[0]) | {"geo": None}
        if L.get("geo") is None:
            L["geo"] = op_pod.geometry(p, L)
        rg, tm = P["ring"], L["geo"]["sensor"]["tmag"]
        rx = (L["ring"][0] + L["ring"][1]) / 2
        rel = (tm["c"][0] - rx, tm["c"][1] - L["y_r"], (tm["z"][0] + tm["z"][1]) / 2 - L["z_axis"])
        rs_ = ring_sensor.model(rg["od"], rg["id"], rg["t"], rel)
    except Exception as e:      # noqa: BLE001
        rs_ = None
        row("3.0", "ring magnet field model", f"skipped ({type(e).__name__})", "", "INFO")
    row("3.1", "one revolution of the nut gear = one revolution of the ring magnet = %.2f U delivered" % nut_rev_U, f"{deg_per_U:.1f} deg per U, {0.05 * deg_per_U:.2f} deg per 0.05 U", "", "INFO",
        "the ring turns 1:1 with the nut gear; the motor turns %.2f x per ring turn" % (g["z_screw"] / g["z_motor"]))
    if rs_:
        pp = rs_["angle_err_pp_deg"]
        unc = pp / 2 / deg_per_U
        row("3.2", "TMAG5273 side-shaft angle: field / non-linearity (uncalibrated)", f"{rs_['B_yz_min_mT']}..{rs_['B_yz_max_mT']} mT, {pp:.0f} deg p-p", f"+-{unc:.2f} U", "WARN",
            "encoder deviation limit 10 %% over 1 U (spec 7) needs <= +-%.1f deg: calibrate (8-point lookup / 2nd+3rd harmonic correction in firmware); the field needs the A2 range (+-133 mT)" % (0.1 * deg_per_U))
        out["angle"] = rs_
    out["angle_deg_per_U"] = deg_per_U
    # ---- 4. dead volume / prime path -----------------------------------------------------------------------------------------------
    cp = p["dock"]["cap"]
    sw = cp["sandwich"]
    dprime = cp["prime_d"]
    v = {}
    v["port channel (spigot half grooves d0.5 x %.2f)" % (cp["spigot_len"] + sw["gasket"]["x"][0])] = math.pi / 4 * dprime ** 2 * (cp["spigot_len"] + sw["gasket"]["x"][0]) / 2 * 2
    xd = cp["septum_x"]
    v["gasket slot 0.6 x 0.5 x %.2f" % (xd + sw["slot_w"] / 2 - sw["gasket"]["x"][0])] = sw["slot_w"] * sw["gasket"]["t"] * (xd + sw["slot_w"] / 2 - sw["gasket"]["x"][0])
    zn = p["cannula"]["C_septum_axis_z"]
    zs = 4.25
    v["via d%.1f x %.2f" % (sw["via_d"], zs - sw["gasket"]["recess"] - zn + 0.4)] = math.pi / 4 * sw["via_d"] ** 2 * (zs - sw["gasket"]["recess"] - zn + 0.4)
    nb = p["dock"]["hub_x0"] - (xd - 0.3)
    v["needle bore d0.5 x %.2f" % nb] = math.pi / 4 * dprime ** 2 * nb
    v["septum chamber d%.1f x %.1f + spur" % (sw["chamber_d"], sw["chamber_h"])] = math.pi / 4 * sw["chamber_d"] ** 2 * sw["chamber_h"] + sw["spur_w"] * sw["spur_depth"] * 3.0
    needle_len = p["dock"]["hub_t"] + p["dock"]["needle_free"]
    v["needle ID 0.159 x %.1f" % needle_len] = math.pi / 4 * 0.159 ** 2 * needle_len
    prime = sum(v.values()) / 10.0
    pg = p["seal"]["purge"]
    purge = (pg["groove_w"] * pg["groove_d"] * (fz["bore_w"] - 0.2 + (fz["bore_h"] - 0.2)) + math.pi / 4 * pg["centre_d"] ** 2 * pg["groove_d"]) / 10.0
    dead_layer = A * P["res"]["dead"] / 10.0
    out["dead"] = {"prime_path_U": prime, "purge_grooves_U": purge, "dead_layer_U": dead_layer, "items_mm3": {k: round(x, 3) for k, x in v.items()}}
    row("4.1", "prime path (port -> needle tip), no valve, no side branch: dead volume <= 0.5 U", f"{prime:.3f} U (%s)" % ", ".join(f"{x:.2f}" for x in v.values()), f"{0.5 / prime:.1f} x", "PASS" if prime <= 0.5 else "FAIL",
        "REFILL.md / firmware MAX_PRIME 0.524 U")
    row("4.2", "air-sensitive layer at the plunger front at the empty stop (dead layer %.2f mm + purge grooves)" % P["res"]["dead"], f"{dead_layer:.2f} + {purge:.2f} U", "", "INFO",
        "the bore is %.1fx wider than the old one: the same 0.04 mm layer holds %.2f U; keep the outlet up while filling" % (A / 74.63, dead_layer))
    # ---- 5. geometry of the stroke -----------------------------------------------------------------------------------------------
    for s in sizes:
        st = P["volume_ul"][s] / A
        out["sizes"][s] = {"stroke_mm": st}
        row("5." + s[-3:], f"{s}: stroke for {int(P['volume_ul'][s] / 10)} U", f"{st:.2f} mm ({st / mm_step:.0f} steps, {st / dr['screw_pitch'] / (g['z_motor'] / g['z_screw']) / dr['gh_ratio']:.2f} motor-gearbox-output turns of the screw drive)", "", "INFO")
    cnt = {k: sum(1 for r in rows if k in r[4]) for k in ("PASS", "WARN", "FAIL", "INFO")}
    md = ["# OpenPatch v0.1.0 integrated pod: simulation report (drive, dose, sensing, dead volume)\n",
          "TEST PROJECT, WATER ONLY, never on a person. Generated by `python3 mechanical/sim/run_all.py` (v010 geometry; %.0f s). Inputs: `params.json` (pod, reservoir_frozen_v010), `out/v010/*.mech.json`; "
          "assumptions in `common.CONST` ([DS] vendor, [LIT] literature, [ASM] bench to settle). The bench-pod report is `REPORT.md` (`run_all.py --bench`).\n" % (time.time() - t0),
          "**Geometry:** bore %.1f x %.1f mm (A = %.1f mm2, perimeter %.1f mm), coaxial M1.6 screw, one mesh z%d:z%d (centre %.2f mm), NFP-608 (26.45:1, 20 st/rev) at %s.\n" %
          (fz["bore_w"], fz["bore_h"], A, per, g["z_motor"], g["z_screw"], g["module"] * (g["z_motor"] + g["z_screw"]) / 2 + g["centre_add"], P["motor"]["option"]),
          "**%d PASS, %d WARN, %d FAIL**, %d info\n" % (cnt["PASS"], cnt["WARN"], cnt["FAIL"], cnt["INFO"]),
          table(["ID", "Requirement", "Value", "Margin", "Status", "Note"], rows)]
    (HERE / "REPORT-v010.md").write_text("\n".join(md))
    (MECH / "out" / "v010").mkdir(parents=True, exist_ok=True)
    (MECH / "out" / "v010" / "sim.json").write_text(json.dumps(out, indent=1, default=float))
    print("REPORT-v010.md written: %d PASS, %d WARN, %d FAIL, %d INFO" % (cnt["PASS"], cnt["WARN"], cnt["FAIL"], cnt["INFO"]))
    return "\n".join(md)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="*")
    run(ap.parse_args().sizes)
