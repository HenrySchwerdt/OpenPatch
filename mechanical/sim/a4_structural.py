"""Analysis 4: structural checks (snap arms, thrust path, carriage tongue, leadscrew, gears, motor mount)."""
from __future__ import annotations

import math

import numpy as np

import a1_drive as a1
from common import CONST as C, PI, PALETTE, Ctx, Result, Row, lewis_Y, status, table

MATS = ("PA12_MJF", "SLA_tough", "SLA_std")


def run(ctx: Ctx) -> Result:
    res = Result("A4 Structural")
    P = ctx.P
    dr, sh, sl = P["drive"], P["shell"], P["seal"]
    zm0, zs0 = ctx.active
    A = ctx.A
    md = ["## 4. Structural checks\n"]
    md.append("All printed parts: PA12 MJF (E %.0f MPa, snap strain allowable %.1f %%) or SLA (Tough-class E %.0f MPa, %.1f %%; standard resin E %.0f MPa, %.1f %%).  "
              "These are [ASM] values from typical vendor data; replace by the datasheet of the resin you really order (`common.CONST`).\n"
              % (C["PA12_MJF"]["E"], 100 * C["PA12_MJF"]["eps_allow_snap"], C["SLA_tough"]["E"], 100 * C["SLA_tough"]["eps_allow_snap"], C["SLA_std"]["E"],
                 100 * C["SLA_std"]["eps_allow_snap"]))

    # worst-case thrust the motor can ever put into the structure (rated current, holding torque, best efficiencies, lowest friction)
    F_max, _ = a1.thrust(ctx, zm0, zs0, I_mA=a1.I_RATED_mA, hold=True, gh_eff=C["gh_eff"][2], pair_eff=C["pair_eff"][2], mu_t=C["mu_thread"][0], mu_c=C["mu_collar"][0])
    T_out_max = a1.motor_torque(a1.I_RATED_mA, hold=True) * ctx.gh * C["gh_eff"][2]       # gearhead output torque N*mm
    md.append("Design load for all structure checks: **F_max = %.1f N** (rated 181 mA, holding torque x%.1f, best efficiency, lowest friction) and a gearhead output torque of "
              "%.1f N*mm; the as-designed 105 mA limit gives %.1f N.\n" % (F_max, C["hold_over_pullout"], T_out_max, a1.thrust(ctx, zm0, zs0, hold=True)[0]))

    # ----------------------------------------------------------------------------------------------------------
    # 4.1 snap arms
    # ----------------------------------------------------------------------------------------------------------
    md.append("### 4.1 Dock snap arms (cantilever, from `mech.json -> dock`)\n")
    D = None
    for s in ctx.sizes:
        if s in ctx.mech and "dock" in ctx.mech[s]:
            D = ctx.mech[s]["dock"]
            break
    cn, dk = P["cannula"], P["dock"]
    if D is None:
        import op_dock  # noqa
        D = op_dock.dock_geometry(P, 25.0, sh["wall"])
    t, h, L, trav = D["arm_t"], D["arm_h"], D["flex_len"], D["travel"]
    I = h * t ** 3 / 12
    rows = []
    snap = {}
    for m in MATS:
        E = C[m]["E"]
        eps = 1.5 * t * trav / L ** 2
        Ft = 3 * E * I * trav / L ** 3
        snap[m] = (eps, Ft)
        rows.append([m, f"{E:.0f}", f"{100 * eps:.2f} %", f"{100 * C[m]['eps_allow_snap']:.1f} %", f"{C[m]['eps_allow_snap'] / eps:.2f}", f"{Ft:.2f}",
                     f"{E * eps:.0f} MPa (lin.)"])
    md.append("Arm t = %.2f mm, height %.2f mm, free length L = %.1f mm, deflection while the dome passes = %.2f mm (R %.1f + clearance - hook_in).  "
              "Strain at the root = 1.5 t d / L^2; tip force = 3 E I d / L^3.\n" % (t, h, L, trav, D["R"]))
    md.append(table(["material", "E MPa", "peak strain", "allowable", "safety factor", "tip force N (per arm)", "root stress"], rows))
    # retention / insertion force with 45 deg ramps (hook_ramp rise over ramp length), friction mu 0.3
    mu_f = 0.3
    ramp = math.atan2(dk["hook_ramp"], dk["hook_ramp"])       # 45 deg: profile (-w2+rmp, ri) to (-w2, ri+rmp)
    wedge = (mu_f + math.tan(ramp)) / (1 - mu_f * math.tan(ramp))
    overlap = cn["H_latch_depth"] - dk["hook_clr"]
    kk = {m: snap[m][1] / trav for m in MATS}
    rows = []
    for m in MATS:
        ins = 2 * wedge * kk[m] * trav
        ret = 2 * wedge * kk[m] * overlap
        rows.append([m, f"{kk[m]:.2f}", f"{ins:.1f}", f"{ret:.1f}"])
    md.append("Hook faces are 45 deg ramps on both sides (`op_dock.py`), so insertion and pull-off both ride the wedge: F = P (mu+tan a)/(1-mu tan a) = %.2f x arm force "
              "(mu %.1f).  Pull-off only needs the overlap (H - hook_clr = %.2f mm) of deflection, insertion the full %.2f mm.\n" % (wedge, mu_f, overlap, trav))
    md.append(table(["material", "arm stiffness N/mm", "insertion force N (2 arms)", "pull-off force N (2 arms)"], rows))
    # Monte Carlo on printed arm thickness, travel (cannula dims) and overlap
    rng = np.random.default_rng(2)
    n = 20000
    mc = {}
    for m, tol in (("PA12_MJF", C["tol_MJF"]), ("SLA_tough", C["tol_SLA"]), ("SLA_std", C["tol_SLA"])):
        tt = t + rng.uniform(-tol, tol, n)
        trv = trav + rng.uniform(-0.15, 0.15, n) + rng.uniform(-tol, tol, n)             # dome dia +-0.15 [ASM] + hook position
        ov = overlap + rng.uniform(-tol, tol, n) + rng.uniform(-0.1, 0.1, n) + rng.uniform(-tol, tol, n)   # hook protrusion, cannula notch depth [ASM], arm position
        eps = 1.5 * tt * trv / L ** 2
        k = 3 * C[m]["E"] * (h * tt ** 3 / 12) / L ** 3
        ret = 2 * wedge * k * np.maximum(ov, 0)
        mc[m] = {"eps": eps, "ret": ret, "ov": ov, "p_over": float(np.mean(eps > C[m]["eps_allow_snap"])), "p_noret": float(np.mean(ov <= 0.05))}
    rows = [[m, f"{100 * np.percentile(v['eps'], 50):.2f} ({100 * np.percentile(v['eps'], 99):.2f}) %", f"{100 * v['p_over']:.0f} %",
             f"{np.percentile(v['ret'], 1):.1f} / {np.percentile(v['ret'], 50):.1f} / {np.percentile(v['ret'], 99):.1f}", f"{np.percentile(v['ov'], 1):.2f}", f"{100 * v['p_noret']:.1f} %"]
            for m, v in mc.items()]
    md.append("Monte Carlo (arm thickness +-print tolerance, dome travel +-0.15 mm, notch depth +-0.1 mm [ASM: cannula dims unmeasured]):\n")
    md.append(table(["material", "strain median (99 %)", "P(strain > allowable)", "pull-off N 1/50/99 %", "overlap mm 1 %", "P(overlap < 0.05)"], rows))
    Lmin = {m: math.sqrt(1.5 * t * trav / C[m]["eps_allow_snap"]) for m in MATS}
    md.append("Minimum free arm length for strain <= allowable at the current deflection: " + ", ".join(f"{m} {v:.1f} mm" for m, v in Lmin.items()) + f" (now {L:.1f} mm).  "
              "Strain falls with L^2 and rises linearly with the deflection, i.e. with how far off the dome equator the hook notch sits (G = %.1f mm).\n" % cn["G_latch_dx"])
    # figure: strain vs travel
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    tr = np.linspace(0.5, 3.0, 50)
    for m, col in zip(MATS, PALETTE):
        ax[0].plot(tr, 100 * 1.5 * t * tr / L ** 2, color="#999", lw=0.0)
        ax[0].axhline(100 * C[m]["eps_allow_snap"], color=col, ls="--", lw=1, label=f"allowable {m}")
    ax[0].plot(tr, 100 * 1.5 * t * tr / L ** 2, color="k", label=f"strain, L={L:.1f}, t={t}")
    ax[0].plot(tr, 100 * 1.5 * t * tr / (L + 3) ** 2, color="k", ls=":", label=f"strain, L={L + 3:.1f}")
    ax[0].axvline(trav, color="#999", lw=0.8)
    ax[0].set_xlabel("arm deflection while the dome passes [mm]")
    ax[0].set_ylabel("root strain [%]")
    ax[0].legend(fontsize=7)
    ax[0].set_title("Snap arm strain")
    ax[0].spines[["top", "right"]].set_visible(False)
    ax[1].hist(100 * mc["PA12_MJF"]["eps"], bins=50, color=PALETTE[0], alpha=0.7, label="PA12 MJF")
    ax[1].hist(100 * mc["SLA_tough"]["eps"], bins=50, color=PALETTE[1], alpha=0.7, label="SLA tough")
    ax[1].axvline(100 * C["PA12_MJF"]["eps_allow_snap"], color=PALETTE[0], ls="--")
    ax[1].axvline(100 * C["SLA_tough"]["eps_allow_snap"], color=PALETTE[1], ls="--")
    ax[1].set_xlabel("root strain [%] (Monte Carlo)")
    ax[1].legend(fontsize=7)
    ax[1].spines[["top", "right"]].set_visible(False)
    figp = ctx.save(fig, "a4_snap.png")
    plt.close(fig)
    md.append("![snap](%s)\n" % figp)

    # ----------------------------------------------------------------------------------------------------------
    # 4.2 thrust train: dry-end block, carriage tongue, floor
    # ----------------------------------------------------------------------------------------------------------
    md.append("### 4.2 Thrust path (screw collar -> end wall block; nut -> carriage -> tongue -> plunger socket)\n")
    wall = sh["wall"]
    zc = wall + (ctx.h_in + 2 * P["reservoir"]["wall"]) / 2
    bh = dr["bush_od"] + 2 * 0.675
    blk_t = dr["gear_x0"] - 0.05 - (wall + 0.02)
    h_load = zc - wall
    E = C["PA12_MJF"]["E"]
    out_blk = {}
    for tag, tt in (("block only", blk_t), ("block + end wall (merged)", blk_t + wall)):
        I_b = bh * tt ** 3 / 12
        sig = F_max * h_load / (bh * tt ** 2 / 6)
        k = 3 * E * I_b / h_load ** 3
        out_blk[tag] = (sig, k)
    # tongue
    to = sl["tongue_off"]
    t_x = to[1] - to[0]
    b_z = dr["arm_t"]
    SHIM = P.get("bench", {}).get("shim")           # stainless tongue shim replaces the printed tongue (CAD 2026-11-19)
    E_t = 193000.0 if SHIM else E
    SIG_T = 200.0 if SHIM else C["PA12_MJF"]["sigma_flex"]     # annealed 1.4301 yield strength, no safety factor
    if SHIM:
        t_x, b_z = SHIM["t"], SHIM["h"]
    ys = (ctx.mech[ctx.sizes[0]]["y_s"] if ctx.sizes[0] in ctx.mech else 22.6)
    yr = (ctx.mech[ctx.sizes[0]]["y_r"] if ctx.sizes[0] in ctx.mech else 11.5)
    y_end = yr + (P["reservoir"]["w_in"] - 2 * P["reservoir"]["plunger_clr"]) / 2
    y_face = ys - dr["carriage_bw"] / 2
    y_load = y_end - sl["socket_depth"] / 2 + 0.05
    lever = y_face - y_load
    I_t = b_z * t_x ** 3 / 12
    c_t = t_x / 2
    sig_t_per_N = lever * c_t / I_t
    k_t = 3 * E_t * I_t / lever ** 3
    tau_t = 1.0 / (t_x * b_z)
    # thicker tongue alternative
    t_alt = 1.2
    I_alt = b_z * t_alt ** 3 / 12
    sig_alt = lever * (t_alt / 2) / I_alt
    k_alt = 3 * E_t * I_alt / lever ** 3
    # floor tension path
    k_floor = E * (wall * 12.0) / 20.0
    k_train = 1.0 / (1.0 / k_t + 1.0 / out_blk["block + end wall (merged)"][1] + 1.0 / k_floor)
    k_train_alt = 1.0 / (1.0 / k_alt + 1.0 / out_blk["block + end wall (merged)"][1] + 1.0 / k_floor)
    k_train_blk = 1.0 / (1.0 / k_t + 1.0 / out_blk["block only"][1] + 1.0 / k_floor)
    rows = [["dry-end bearing block, block only (%.2f mm thick x %.2f wide, load %.1f mm above floor)" % (blk_t, bh, h_load), f"{out_blk['block only'][0]:.0f}", f"{out_blk['block only'][1]:.0f}", "%.0f" % C["PA12_MJF"]["sigma_flex"]],
            ["same, merged with the 0.9 mm end wall", f"{out_blk['block + end wall (merged)'][0]:.0f}", f"{out_blk['block + end wall (merged)'][1]:.0f}", "%.0f" % C["PA12_MJF"]["sigma_flex"]],
            ["carriage tongue as drawn: %.2f (x) x %.2f (z) mm, lever %.2f mm" % (t_x, b_z, lever), f"{F_max * sig_t_per_N:.0f}", f"{k_t:.0f}", "%.0f" % SIG_T],
            ["carriage tongue %.1f mm thick (proposal)" % t_alt, f"{F_max * sig_alt:.0f}", f"{k_alt:.0f}", "%.0f" % SIG_T]]
    md.append("Bending stress at F_max = %.1f N, stiffness, and the PA12 flexural allowable.  The tongue carries the whole push force in its thin direction (0.6 mm in x), "
              "cantilevered %.2f mm out of the carriage, root stress %.1f MPa per newton (shear only %.1f MPa/N).\n" % (F_max, lever, sig_t_per_N, tau_t))
    md.append(table(["element", "stress at F_max MPa", "stiffness N/mm", "allowable MPa"], rows))
    md.append("Allowable thrust through the tongue as drawn: **%.1f N** (PA12) / %.1f N (SLA tough); with a %.1f mm tongue %.1f N.  Series stiffness of the whole train: "
              "%.0f N/mm (as drawn), %.0f N/mm (tongue %.1f mm), %.0f N/mm (block alone).  Elastic wind-up at 3 N: %.3f mm = %.2f U (as drawn).\n"
              % (SIG_T / sig_t_per_N, C["SLA_tough"]["sigma_flex"] / sig_t_per_N, t_alt, SIG_T / sig_alt, k_train, k_train_alt, t_alt,
                 k_train_blk, 3 / k_train, 3 / k_train * A / 10))

    # rear/front stops
    stop_area = 2 * 0.55 * 2.2
    sig_stop = F_max / stop_area
    # ----------------------------------------------------------------------------------------------------------
    # 4.3 leadscrew
    # ----------------------------------------------------------------------------------------------------------
    md.append("### 4.3 Leadscrew M1.6 x 0.35 (A2 stainless): buckling, torsion\n")
    d2 = dr["screw_d"] - 0.6495 * ctx.pitch
    d3 = dr["screw_d"] - 1.22687 * ctx.pitch
    d_eq = (d2 + d3) / 2
    Is = PI * d_eq ** 4 / 64
    EI = C["steel_E"] * Is
    rows = []
    bk = {}
    for s in ctx.sizes:
        Ls = ctx.screw_span(s)
        Pcr = PI ** 2 * EI / (1.0 * Ls) ** 2
        Pcr_f = PI ** 2 * EI / (2.0 * Ls) ** 2          # worst: free-ish end (nut carriage floats in its lane)
        bk[s] = (Ls, Pcr, Pcr_f)
        rows.append([s, f"{Ls:.1f}", f"{Pcr:.0f}", f"{Pcr / F_max:.0f}x", f"{Pcr_f:.0f}", f"{Pcr_f / F_max:.0f}x"])
    md.append("Equivalent diameter (d2+d3)/2 = %.3f mm, EI = %.0f N*mm2.  The screw is in compression between the dry-end collar and the nut (delivery) with the carriage "
              "at the front.  Pinned-pinned (K=1) and a pessimistic K=2.\n" % (d_eq, EI))
    md.append(table(["size", "free length mm", "P_cr pinned N", "margin vs F_max", "P_cr K=2 N", "margin"], rows))
    tau_s = 16 * T_out_max / PI / d3 ** 3
    md.append("Torsion at the maximum screw torque %.1f N*mm: tau = %.1f MPa on the root diameter %.2f mm (yield > 200 MPa): not critical.\n" % (T_out_max, tau_s, d3))

    # ----------------------------------------------------------------------------------------------------------
    # 4.4 gears
    # ----------------------------------------------------------------------------------------------------------
    md.append("### 4.4 Gear teeth (module %.1f, brass), shaft and bonding\n" % ctx.module)
    rows = []
    gear_worst = 0.0
    for name, zm, zs in ctx.gear_options():
        dp = ctx.module * zm
        Wt = 2 * T_out_max / dp
        Ks = 2.0                                           # dynamic / shock factor [ASM]
        worst = 0
        for z, which in ((zm, "motor"), (zs, "screw")):
            b = dr["gear_t"]
            sig = Ks * Wt / (b * ctx.module * lewis_Y(z))
            worst = max(worst, sig)
        gear_worst = max(gear_worst, worst) if name.endswith("(CAD)") else gear_worst
        rows.append([name, f"{Wt:.2f}", f"{dr['gear_t']:.1f}", f"{worst:.0f}", f"{C['brass_sigma_bend'] / worst:.1f}x"])
    md.append("Lewis bending stress sigma = Ks Wt / (b m Y), Ks = 2, b = %.1f mm (CAD gear_t; the purchasable thin discs are 1.4 mm), Wt = 2 T / d_pitch at the maximum torque "
              "(T = %.1f N*mm).  Allowable %.0f MPa (brass, bending).\n" % (dr["gear_t"], T_out_max, C["brass_sigma_bend"]))
    md.append(table(["pair", "tangential force N", "face width mm", "max tooth stress MPa", "safety"], rows))
    Wt0 = 2 * T_out_max / (ctx.module * zm0)
    rad = Wt0 * math.tan(math.radians(20))
    M_sh = math.hypot(Wt0, rad) * 0.7
    sig_sh = 32 * M_sh / (PI * ctx.preset.get("shaft_d", 2.0) ** 3)
    L_bond = PI * ctx.preset.get("shaft_d", 2.0) * dr["gear_t"]
    T_bond = 7.5 * L_bond * ctx.preset.get("shaft_d", 2.0) / 2          # 15 MPa Loctite on steel, x0.5 for the D flat / gap
    md.append("Motor shaft: radial load %.2f N at ~0.7 mm from the gearhead boss -> bending %.1f MPa (trivial).  Whether the gearhead output bearing accepts %.1f N radial is "
              "**not in the vendor data** (bench item).  Adhesive joint (Loctite 638 class, 15 MPa x 0.5): capacity %.0f N*mm vs %.1f N*mm -> %.0fx.\n"
              % (math.hypot(Wt0, rad), sig_sh, math.hypot(Wt0, rad), T_bond, T_out_max, T_bond / T_out_max))
    md.append("Motor reaction torque on the housing: %.1f N*mm; the printed saddles are 0.1 mm clear of the body (`t_mcut` d6.1), so the torque must be taken by the terminal-block pocket "
              "or a clamp: lever 3 mm -> %.1f N on a printed rib (fine if a positive anti-rotation feature exists, to be verified in the CAD review).\n" % (T_out_max, T_out_max / 3.0))

    # ----------------------------------------------------------------------------------------------------------
    # 4.5 reservoir wall, stops
    # ----------------------------------------------------------------------------------------------------------
    bspan = ctx.w_in - ctx.h_in
    F_seal_low = a1.seal_friction(ctx, mu=C['mu_seal'][0], dbore=0.05)['F']
    P_max = (F_max - F_seal_low) / A * 1e3          # kPa at F_max minus the lowest plausible seal friction
    q = P_max * 1e-3
    tw = P["reservoir_frozen"]["wall"]
    sig_w = q * bspan ** 2 / (2 * tw ** 2)
    md.append("### 4.5 CNC reservoir wall and end stops\n")
    md.append("Maximum pressure the drive can build: (F_max - lowest plausible seal friction %.1f N)/A = %.0f kPa.  Flat wall (strip %.0f mm span, t %.1f mm, clamped): sigma = q b^2/(2 t^2) = %.1f MPa vs PP yield %.0f MPa -> %.0fx.  "
              "Rear/front hard stop bearing area %.1f mm2: %.1f MPa at F_max vs PA12 ~40 MPa (REFILL.md).\n" % (F_seal_low, P_max, bspan, tw, sig_w, C["PP_yield"], C["PP_yield"] / sig_w, stop_area, sig_stop))

    # ----------------------------------------------------------------------------------------------------------
    # rows
    # ----------------------------------------------------------------------------------------------------------
    pa = snap["PA12_MJF"]
    sla = snap["SLA_tough"]
    res.rows += [
        Row("4.1", "Structural", "Snap arm peak strain <= allowable, PA12 MJF", f"{100 * pa[0]:.2f} % vs {100 * C['PA12_MJF']['eps_allow_snap']:.1f} %", f"{C['PA12_MJF']['eps_allow_snap'] / pa[0]:.2f}x",
            status(pa[0] <= C["PA12_MJF"]["eps_allow_snap"] * 0.8, pa[0] <= C["PA12_MJF"]["eps_allow_snap"]), f"MC P(over) {100 * mc['PA12_MJF']['p_over']:.0f} %; cannula dims unmeasured"),
        Row("4.2", "Structural", "Snap arm peak strain <= allowable, SLA (tough class)", f"{100 * sla[0]:.2f} % vs {100 * C['SLA_tough']['eps_allow_snap']:.1f} %", f"{C['SLA_tough']['eps_allow_snap'] / sla[0]:.2f}x",
            status(sla[0] <= C["SLA_tough"]["eps_allow_snap"] * 0.8, sla[0] <= C["SLA_tough"]["eps_allow_snap"]), f"needs L >= {Lmin['SLA_tough']:.1f} mm; standard resin needs {Lmin['SLA_std']:.1f} mm"),
        Row("4.3", "Structural", "Pull-off force 1.5-10 N (stays on, removable by hand) [ASM], PA12", f"{2 * wedge * kk['PA12_MJF'] * overlap:.1f} N (pull-off), {2 * wedge * kk['PA12_MJF'] * trav:.1f} N (insertion)", "-",
            status(1.5 <= 2 * wedge * kk['PA12_MJF'] * overlap and 2 * wedge * kk['PA12_MJF'] * trav <= 10, True), f"hook overlap only {overlap:.2f} mm, P(no overlap) {100 * mc['PA12_MJF']['p_noret']:.1f} %"),
        Row("4.4", "Structural", "Carriage tongue bending stress at F_max <= PA12 allowable", f"{F_max * sig_t_per_N:.0f} MPa vs {SIG_T:.0f}", f"{SIG_T / (F_max * sig_t_per_N):.2f}x",
            status(F_max * sig_t_per_N <= C["PA12_MJF"]["sigma_flex"], F_max * sig_t_per_N <= 1.5 * C["PA12_MJF"]["sigma_flex"]), f"tongue is {t_x:.1f} mm thick in the load direction; allowable thrust {C['PA12_MJF']['sigma_flex'] / sig_t_per_N:.1f} N"),
        Row("4.5", "Structural", "Tongue stress at the as-designed 105 mA thrust (F %.1f N)" % a1.thrust(ctx, zm0, zs0, hold=True)[0], f"{a1.thrust(ctx, zm0, zs0, hold=True)[0] * sig_t_per_N:.0f} MPa", "-",
            status(a1.thrust(ctx, zm0, zs0, hold=True)[0] * sig_t_per_N <= SIG_T, a1.thrust(ctx, zm0, zs0, hold=True)[0] * sig_t_per_N <= 1.5 * SIG_T), "stall (holding torque) load"),
        Row("4.6", "Structural", "Thrust train stiffness >= 100 N/mm (wind-up <= 0.03 mm at 3 N)", f"{k_train:.0f} N/mm", f"{k_train / 100:.2f}x",
            status(k_train >= 100, k_train >= 50), "tongue dominates; feeds start-lag (A2) and occlusion stored volume (A5)"),
        Row("4.7", "Structural", "Dry-end block + wall bending stress at F_max (PA12)", f"{out_blk['block + end wall (merged)'][0]:.0f} / {out_blk['block only'][0]:.0f} MPa (merged / block only)", "-",
            status(out_blk['block only'][0] <= C['PA12_MJF']['sigma_flex'], out_blk['block + end wall (merged)'][0] <= C['PA12_MJF']['sigma_flex']), "depends on how the block ties into the end wall"),
    ]
    for s in ctx.sizes:
        Ls, Pcr, Pcr_f = bk[s]
        res.rows.append(Row(f"4.8-{s}", "Structural", f"Leadscrew Euler buckling margin >= 5 (K=2), {s}", f"{Pcr_f:.0f} N at L={Ls:.0f} mm", f"{Pcr_f / F_max:.0f}x", status(Pcr_f >= 5 * F_max, Pcr_f >= 2 * F_max), ""))
    res.rows += [
        Row("4.9", "Structural", "Gear tooth bending safety >= 2 (brass, max torque)", f"{gear_worst:.0f} MPa", f"{C['brass_sigma_bend'] / gear_worst:.1f}x", status(C['brass_sigma_bend'] / gear_worst >= 2, C['brass_sigma_bend'] / gear_worst >= 1.2), "CAD pair"),
        Row("4.10", "Structural", "CNC reservoir wall stress at max pressure", f"{sig_w:.1f} MPa vs {C['PP_yield']:.0f}", f"{C['PP_yield'] / sig_w:.1f}x", status(C['PP_yield'] / sig_w >= 2, C['PP_yield'] / sig_w >= 1.2), ""),
        Row("4.11", "Structural", "Hard stop bearing stress at F_max", f"{sig_stop:.1f} MPa vs ~40", f"{40 / sig_stop:.0f}x", status(sig_stop <= 20, sig_stop <= 40), ""),
    ]
    ctx.shared["a4"] = {"k_train": k_train, "k_train_alt": k_train_alt, "k_tongue": k_t, "F_max": F_max, "lever": lever, "sig_t_per_N": sig_t_per_N, "snap": snap,
                        "F_allow_tongue": SIG_T / sig_t_per_N, "Lmin": Lmin, "arm_L": L, "wedge": wedge, "overlap": overlap, "trav": trav}
    res.md = "\n".join(md)
    return res
