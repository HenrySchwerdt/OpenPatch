"""Analysis 2: dose resolution and accuracy (Monte Carlo)."""
from __future__ import annotations

import math

import numpy as np

from common import CONST as C, PI, PALETTE, Ctx, Result, Row, area_stadium, status, table

DOSES = (0.05, 0.1, 0.5, 1.0, 5.0, 10.0)
LEAD_SIGMA = 0.002          # [ASM] rolled M1.6 rod, lead error sigma 0.2 % (truncated +-0.5 %)
PERIODIC_UM = 3.0           # [ASM] once-per-revolution axial error amplitude (runout, thread form), um
GEAR_TE_UM = 20.0           # [ASM] DIN 58405 q8 tooth-to-tooth composite error at the pitch circle
NUT_PLAY = (0.03, 0.05, 0.08)   # [ASM] axial play of a DIN 934 M1.6 nut on an M1.6 rod (ISO 6H/6g), mm


def simulate(ctx: Ctx, dose: float, n: int, rng, tol_plus: float, tol_minus: float, lag_amp_mm3: float, calibrated: bool, bubble_mm3: float,
             zm: int, zs: int, periodic_um: float = PERIODIC_UM):
    u = ctx.u_per_step(zm, zs)
    steps = max(1, round(dose / u))
    V_nom_cmd = steps * u * 10.0                    # mm3 the firmware believes it delivers
    pitch = ctx.pitch
    # --- static factors (per pod) ---
    w = ctx.w_in + rng.uniform(-tol_minus, tol_plus, n)
    h = ctx.h_in + rng.uniform(-tol_minus, tol_plus, n)
    area = area_stadium(w, h)
    lead = np.clip(rng.normal(0, LEAD_SIGMA, n), -0.005, 0.005)
    if calibrated:
        # gravimetric per-pod calibration removes area, lead error and the calibration-temperature scale; residual = balance + repeatability
        static = rng.normal(0, 0.004, n)
    else:
        static = area / ctx.A - 1.0 + lead
    # --- temperature (5..40 C, calibrated/assumed at 20 C) ---
    dT = rng.uniform(5 - 20, 40 - 20, n)
    alpha = rng.uniform(1.0e-4, 1.8e-4, n)          # PP bore area grows with 2*alpha
    beta = rng.uniform(2.0e-4, 3.5e-4, n)           # liquid expansion -> fewer U per ml when warm
    thermal = 2 * alpha * dT - beta * dT
    # --- dynamic errors, in mm3 ---
    travel = steps * pitch / (ctx.spr * ctx.gh) * zm / zs               # screw travel mm
    th0 = rng.uniform(0, 2 * PI, n)
    th1 = th0 + 2 * PI * travel / pitch
    periodic = periodic_um * 1e-3 * (np.sin(th1) - np.sin(th0))          # mm
    te = rng.uniform(-1, 1, n) * GEAR_TE_UM * 1e-3 / (ctx.module * zs / 2) * pitch / (2 * PI) * 2   # mm
    step_err = rng.uniform(-0.05, 0.05, n) * (pitch / (ctx.spr * ctx.gh) * zm / zs)
    dyn_mm = periodic + te + step_err
    lag = rng.triangular(-1, 0, 1, n) * lag_amp_mm3
    bub = rng.triangular(-1, 0, 1, n) * bubble_mm3
    V_true = (V_nom_cmd * (1 + static) * (1 + thermal)) + dyn_mm * area + lag + bub
    return V_true / (dose * 10.0) - 1.0, steps, u


def run(ctx: Ctx) -> Result:
    res = Result("A2 Dose resolution & accuracy")
    P = ctx.P
    A = ctx.A
    zm0, zs0 = ctx.active
    a1 = ctx.shared["a1"]
    a4 = ctx.shared["a4"]
    md = ["## 2. Dose resolution and accuracy\n"]
    md.append("**Resolution.** U/step = pitch x (z_motor/z_screw) / (steps/rev x gearhead ratio) x A / 10, A = %.2f mm2 (16 x 5 stadium).\n" % A)
    rows = []
    for name, zm, zs in ctx.gear_options():
        u = ctx.u_per_step(zm, zs)
        n005 = 0.05 / u
        r = round(n005)
        rows.append([name, f"{u:.5f}", f"{1 / u:.0f}", f"{n005:.2f}", f"{100 * (r * u / 0.05 - 1):+.1f} %", f"{0.35 / (ctx.spr * ctx.gh) * zm / zs * 1000:.3f}"])
    md.append(table(["pair", "U/step", "steps per U", "steps in 0.05 U", "rounding error of 0.05 U", "um/step at the nut"], rows))
    md.append("Firmware keeps an exact rational per preset (no default), so the pair in the CAD and the firmware feature must match: "
              "the 18:18 and 15:12 presets differ by 25 % in U/step.\n")

    # ---------------- error budget ----------------------------------------------------------------------------
    fz = P["reservoir_frozen"]
    dA_plus = area_stadium(ctx.w_in + fz["bore_tol_plus"], ctx.h_in + fz["bore_tol_plus"]) / A - 1
    dA_020 = area_stadium(ctx.w_in + 0.02, ctx.h_in + 0.02) / A - 1
    dA_m020 = area_stadium(ctx.w_in - 0.02, ctx.h_in - 0.02) / A - 1
    md.append("### 2.1 Error sources (relative to the firmware's nominal %.2f mm2 / 0.35 mm pitch)\n" % A)
    rows = [
        ["Reservoir area, frozen drawing +%.2f/-0 on both axes" % fz["bore_tol_plus"], f"0 ... {100 * dA_plus:+.2f} % (mean {50 * dA_plus:+.2f} %)", "static per pod; removable by calibration; mean bias could be put in the preset"],
        ["Reservoir area, CNC +-0.02 (task statement)", f"{100 * dA_m020:+.2f} ... {100 * dA_020:+.2f} %", "static"],
        ["Leadscrew lead error (rolled rod)", f"sigma {100 * LEAD_SIGMA:.1f} % (max +-0.5 %) [ASM]", "static per rod"],
        ["Once-per-rev periodic error (runout, thread form)", f"+-{PERIODIC_UM:.0f} um -> up to +-{2 * PERIODIC_UM * 1e-3 * A / 10:.3f} U per dose, dose-independent [ASM]", "dominates small doses"],
        ["Temperature 5-40 C: PP bore area vs liquid expansion", "2*alpha*dT - beta*dT: +-0.3 % (they nearly cancel)", "dynamic"],
        ["Gear transmission error (DIN 58405 q8, 20 um)", f"+-{GEAR_TE_UM * 1e-3 / (ctx.module * zs0 / 2) * ctx.pitch / (2 * PI) * 2 * A / 10:.4f} U", "negligible"],
        ["Elastic wind-up of the thrust train (stick-slip)", "amplitude = A * 0.25 * F_kinetic / k_train (see 2.3)", "dominates once friction is high / train soft"],
        ["Bubble / compliance at start of flow (duckbill 1-5 kPa)", "bubble V_b/P_atm * P_crack (see 2.3)", "dynamic"],
        ["Quantisation (whole steps)", "see table above", "deterministic"],
    ]
    md.append(table(["source", "magnitude", "nature"], rows))

    # Backlash at reversal (draw then deliver)
    md.append("### 2.2 Backlash and the start of a bolus\n")
    gh_bl_deg = 6.0   # [ASM] output-shaft backlash of a 2-stage Ø6 planetary gearhead
    j_t = 0.06        # mm transverse gear backlash at pitch circle [ASM]
    bl_gear = j_t / (ctx.module * zs0 / 2) / (2 * PI) * ctx.pitch                  # mm nut travel
    bl_gh = gh_bl_deg / 360 * ctx.pitch * zm0 / zs0
    rows = [
        ["gear pair (j_t %.2f mm at the pitch circle)" % j_t, f"{bl_gear * 1000:.2f} um", f"{bl_gear * A / 10:.4f} U"],
        ["gearhead (%.0f deg at the output shaft [ASM])" % gh_bl_deg, f"{bl_gh * 1000:.2f} um", f"{bl_gh * A / 10:.3f} U"],
        ["nut on rod, axial play %.2f-%.2f mm [ASM]" % (NUT_PLAY[0], NUT_PLAY[2]), "%.0f-%.0f um" % (NUT_PLAY[0] * 1000, NUT_PLAY[2] * 1000), "%.2f-%.2f U" % (NUT_PLAY[0] * A / 10, NUT_PLAY[2] * A / 10)],
    ]
    md.append("Delivery always pushes the same flank, so backlash only matters after a **direction reversal** (every draw, and when backing off the end stop).  Un-compensated, the first delivery "
              "after a draw loses the whole play; the firmware has no backlash term (`grep -ri backlash firmware-rs` finds nothing), so a take-up routine (reverse draw ends with a forward "
              "move of >= %.0f steps before counting delivered volume) is required.\n" % math.ceil(NUT_PLAY[2] / (ctx.pitch / (ctx.spr * ctx.gh) * zm0 / zs0)))
    md.append(table(["source", "loss at reversal (nut travel)", "volume"], rows))

    # ---------------- Monte Carlo ----------------------------------------------------------------------------
    k0, k1 = a4["k_train"], a4["k_train_alt"]
    Fk = a1["F_seal"]
    scenarios = [
        ("S1 as drawn: tongue 0.6 mm (k=%.0f N/mm), F_kin %.1f N" % (k0, Fk), A * 0.25 * Fk / k0, False),
        ("S2 tongue 1.2 mm (k=%.0f N/mm), F_kin %.1f N" % (k1, Fk), A * 0.25 * Fk / k1, False),
        ("S3 tongue 1.2 mm, seal redesigned F_kin 1.5 N", A * 0.25 * 1.5 / k1, False),
        ("S4 as S3 + per-pod gravimetric calibration", A * 0.25 * 1.5 / k1, True),
    ]
    rng = np.random.default_rng(3)
    N = 40000
    bubble = 10.0 / C["P_atm_kPa"] * 5.0        # 10 mm3 bubble compressed by a 5 kPa crack pressure
    md.append("### 2.3 Monte Carlo accuracy (N = %d per dose and scenario)\n" % N)
    md.append("Error = delivered volume / commanded - 1 after whole-step rounding.  Tolerances: bore +0.05/0 (frozen drawing), lead sigma %.1f %%, periodic %.0f um, temperature 5-40 C, "
              "bubble 10 mm3 against 5 kPa crack (%.2f mm3), stick-slip lag amplitude = A * 0.25 * F_kin / k_train (the stop force of the plunger varies by about 25 %% of F_kin [ASM]).  "
              "Reported: 95 %% interval half-width = 97.5th percentile of |error|.  **Target: +-5 %% at >= 1 U.**\n" % (100 * LEAD_SIGMA, PERIODIC_UM, bubble))
    tab = {}
    rows = []
    for tag, lag_mm3, cal in scenarios:
        row = [tag]
        for d in DOSES:
            e, steps, u = simulate(ctx, d, N, rng, fz["bore_tol_plus"], 0.0, lag_mm3, cal, bubble, zm0, zs0)
            hw = float(np.percentile(np.abs(e), 95))
            tab[(tag, d)] = (hw, float(np.mean(e)), e)
            row.append(f"{100 * hw:.1f} %")
        rows.append(row)
    md.append(table(["scenario"] + [f"{d:g} U" for d in DOSES], rows))
    # contribution split at 1 U, S3 uncalibrated
    base = dict(tol_plus=fz["bore_tol_plus"], tol_minus=0.0, lag_amp_mm3=0.0, calibrated=False, bubble_mm3=0.0, zm=zm0, zs=zs0)
    parts = {}
    for label, kw in (("area+lead (static)", {}), ("periodic 3 um", {"periodic_um": PERIODIC_UM}), ("stick-slip lag S1", {"lag_amp_mm3": scenarios[0][1]}),
                      ("stick-slip lag S3", {"lag_amp_mm3": scenarios[2][1]}), ("bubble", {"bubble_mm3": bubble})):
        kw2 = dict(base)
        kw2.update(kw)
        pu = kw2.pop("periodic_um", 0.0)
        e, _, _ = simulate(ctx, 1.0, N, np.random.default_rng(5), **kw2, periodic_um=pu)
        parts[label] = float(np.percentile(np.abs(e), 95))
    md.append("Contribution of single sources at 1 U (alone, 95 % half-width): " + ", ".join(f"{k} {100 * v:.1f} %" for k, v in parts.items()) + " (thermal and gear terms are always on).\n")
    # tolerance +-0.02 scenario for the static part
    e02, _, _ = simulate(ctx, 1.0, N, np.random.default_rng(6), 0.02, 0.02, 0.0, False, 0.0, zm0, zs0, periodic_um=0.0)
    e05, _, _ = simulate(ctx, 1.0, N, np.random.default_rng(6), 0.05, 0.0, 0.0, False, 0.0, zm0, zs0, periodic_um=0.0)
    md.append("Static part only (no lag, no periodic) at 1 U: bore +-0.02 -> %.2f %%, bore +0.05/-0 -> %.2f %% (95 %% half-width); the +0.05/-0 band is biased by %.2f %% on average, which can be absorbed "
              "by shifting the preset area by +%.2f %%.\n" % (100 * np.percentile(np.abs(e02), 95), 100 * np.percentile(np.abs(e05), 95), 50 * dA_plus, 50 * dA_plus))

    # sensitivity to the periodic error amplitude (the least known input)
    rows = []
    for a_p in (0.0, 1.5, 3.0, 6.0, 10.0):
        r_ = [f"{a_p:g} um"]
        for d in (1.0, 5.0):
            e, _, _ = simulate(ctx, d, N, np.random.default_rng(7), fz["bore_tol_plus"], 0.0, scenarios[2][1], True, bubble, zm0, zs0, periodic_um=a_p)
            r_.append(f"{100 * np.percentile(np.abs(e), 95):.1f} %")
        rows.append(r_)
    md.append("Sensitivity to the once-per-revolution axial error (S4 settings, calibrated): the largest unknown of the lead screw, only a measurement of a real rod can settle it.\n")
    md.append(table(["periodic amplitude", "1 U error (95 %)", "5 U error (95 %)"], rows))
    ctx.shared.setdefault("a2_periodic", rows)
    # reversal
    lost_u = [p * A / 10 for p in NUT_PLAY]
    md.append("First 1 U after a draw without take-up: loses %.2f-%.2f U = %.0f-%.0f %% of a 1 U dose.  With a take-up routine (residual 20 %% of the play) %.2f-%.2f U.\n"
              % (lost_u[0], lost_u[2], 100 * lost_u[0], 100 * lost_u[2], 0.2 * lost_u[0], 0.2 * lost_u[2]))

    # figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for (tag, lag, cal), col in zip(scenarios, PALETTE):
        ax[0].plot(DOSES, [100 * tab[(tag, d)][0] for d in DOSES], "o-", color=col, label=tag.split(":")[0] + (": " + tag.split(":")[1][:34] if ":" in tag else ""))
    ax[0].axhline(5, color="k", ls="--", lw=1)
    ax[0].set_xscale("log")
    ax[0].set_yscale("log")
    ax[0].set_xlabel("dose [U]")
    ax[0].set_ylabel("95 % error half-width [%]")
    ax[0].set_title("Dose accuracy by scenario (target 5 % at >= 1 U)")
    ax[0].legend(fontsize=6)
    ax[0].spines[["top", "right"]].set_visible(False)
    for (tag, lag, cal), col in list(zip(scenarios, PALETTE))[::2]:
        ax[1].hist(100 * tab[(tag, 1.0)][2], bins=80, range=(-30, 30), color=col, alpha=0.6, label=tag.split(":")[0])
    ax[1].axvline(-5, color="k", ls="--", lw=1)
    ax[1].axvline(5, color="k", ls="--", lw=1)
    ax[1].set_xlabel("error of a 1 U dose [%]")
    ax[1].legend(fontsize=7)
    ax[1].spines[["top", "right"]].set_visible(False)
    figp = ctx.save(fig, "a2_dose.png")
    plt.close(fig)
    md.append("![dose](%s)\n" % figp)

    def stat(hw, lim=0.05):
        return status(hw <= lim, hw <= 2 * lim)

    s1, s3, s4 = scenarios[0][0], scenarios[2][0], scenarios[3][0]
    u0 = ctx.u_per_step(zm0, zs0)
    res.rows += [
        Row("2.1", "Dose", "Resolution <= 0.03 U/step (parts.md target 0.008-0.03)", f"{u0:.5f} U/step (CAD pair {zm0}:{zs0}); 0.05 U = {0.05 / u0:.1f} steps", f"{0.03 / u0:.1f}x", status(u0 <= 0.03), "15:12 gives 0.00617"),
        Row("2.2", "Dose", "Rounding of the smallest dose 0.05 U <= 5 %", f"{100 * (round(0.05 / u0) * u0 / 0.05 - 1):+.1f} %", "-", status(abs(round(0.05 / u0) * u0 / 0.05 - 1) <= 0.05), ""),
        Row("2.3", "Dose", "Static error (area + lead) 95 % <= 2 %, uncalibrated, 1 U", f"{100 * parts['area+lead (static)']:.1f} %", "-", status(parts['area+lead (static)'] <= 0.02, parts['area+lead (static)'] <= 0.05), "bore +0.05/-0 biased +0.6 % on average"),
        Row("2.4", "Dose", "1 U dose within +-5 % (95 %), design as drawn (S1)", f"{100 * tab[(s1, 1.0)][0]:.1f} %", f"{0.05 / tab[(s1, 1.0)][0]:.2f}x", stat(tab[(s1, 1.0)][0]), "tongue wind-up x seal friction"),
        Row("2.5", "Dose", "1 U within +-5 % with 1.2 mm tongue + seal F_kin 1.5 N (S3, uncalibrated)", f"{100 * tab[(s3, 1.0)][0]:.1f} %", f"{0.05 / tab[(s3, 1.0)][0]:.2f}x", stat(tab[(s3, 1.0)][0]), "periodic 3 um error dominates"),
        Row("2.6", "Dose", "1 U within +-5 % with S3 + per-pod calibration (S4)", f"{100 * tab[(s4, 1.0)][0]:.1f} %", f"{0.05 / tab[(s4, 1.0)][0]:.2f}x", stat(tab[(s4, 1.0)][0]), ""),
        Row("2.7", "Dose", "10 U within +-5 % (95 %), S1 / S3", f"{100 * tab[(s1, 10.0)][0]:.1f} % / {100 * tab[(s3, 10.0)][0]:.1f} %", "-", stat(max(tab[(s1, 10.0)][0], tab[(s3, 10.0)][0])), ""),
        Row("2.8", "Dose", "0.05 U error (info, no requirement), S3", f"{100 * tab[(s3, 0.05)][0]:.0f} %", "-", "INFO", "minimum bolus is a dose-quantum, not an accuracy claim"),
        Row("2.9", "Dose", "First 1 U after a draw without backlash take-up <= 5 %", f"-{100 * lost_u[0]:.0f}...-{100 * lost_u[2]:.0f} %", "-", status(False), "firmware needs a take-up step after every draw"),
    ]
    ctx.shared["a2"] = {"nut_play_max": NUT_PLAY[2], "tab": {k: v[0] for k, v in tab.items()}, "parts": parts, "lost_u": lost_u}
    res.md = "\n".join(md)
    return res
