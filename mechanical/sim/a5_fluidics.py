"""Analysis 5: fluidics - priming / dead volume, bubbles, compliance, occlusion detection time."""
from __future__ import annotations

import math

import numpy as np

import a1_drive as a1
from common import CONST as C, PI, PALETTE, Ctx, Result, Row, status, table

THRESH_FW = 2.0              # U, firmware OCCLUSION (limits.rs) = spec 7
MAX_PRIME_U = 0.524          # limits.rs MAX_PRIME


def cyl(d, l):
    return PI / 4 * d * d * l


def path_volume(ctx: Ctx):
    """Wetted volume downstream of the reservoir chamber, from the cap geometry in op_cap.py and the frozen port (mm3)."""
    P = ctx.P
    fz, nd, dk, cp, cx, cn = P["reservoir_frozen"], P["needle"], P["dock"], P["dock"]["cap"], P["coax"], P["cannula"]
    d = nd["channel_d"]
    zn, zp = nd["channel_z"] if False else cn["C_septum_axis_z"], ctx.mech[ctx.sizes[0]]["z_axis"] if ctx.sizes[0] in ctx.mech else 4.2
    items = {
        "frozen port bore d%.1f x %.1f mm" % (fz["port_d"], fz["end_wall"]): cyl(fz["port_d"], fz["end_wall"]),
        "cap port channel d%.1f x %.1f" % (d, cp["spigot_len"] + 0.1 + cp["jog_x"] + 0.2): cyl(d, cp["spigot_len"] + 0.1 + cp["jog_x"] + 0.2),
        "jog down to the needle axis x %.1f" % (zp - zn + 0.4): cyl(d, zp - zn + 0.4),
        "junction -> valve x 0.8": cyl(d, 0.8),
        "fill side branch (c+b+a) x %.1f" % (2.4 + 2.3 + 5.2): cyl(d, 2.4 + 2.3 + 5.2),
        "septum port d1.0 x 0.8": cyl(1.0, 0.8),
        "duckbill pocket d%.2f x %.1f, 30 %% void [ASM]" % (cx["valve_d"] + 0.05, cx["valve_len"]): 0.30 * cyl(cx["valve_d"] + 0.05, cx["valve_len"]),
        "valve -> hub x 1.0": cyl(d, 1.0),
        "needle lumen d0.159 x 4.2": cyl(0.159, 4.2),
    }
    return items


def run(ctx: Ctx) -> Result:
    res = Result("A5 Fluidics")
    P = ctx.P
    A = ctx.A
    a1r, a4r = ctx.shared["a1"], ctx.shared["a4"]
    zm0, zs0 = ctx.active
    md = ["## 5. Fluidics: priming, dead volume, bubbles, compliance, occlusion detection\n"]

    # ---------------- 5.1 volumes ------------------------------------------------------------------------------
    items = path_volume(ctx)
    V_path = sum(items.values())
    dead_mm = P["reservoir"]["dead"]
    V_dead_gap = dead_mm * A
    md.append("### 5.1 Priming and dead volume\n")
    md.append(table(["element (from `op_cap.py`, `reservoir_frozen`)", "volume mm3"], [[k, f"{v:.2f}"] for k, v in items.items()] + [["**path total**", f"**{V_path:.1f} mm3 = {V_path / 10:.2f} U**"]]))
    md.append("The reservoir chamber itself keeps a **%.1f mm dead layer** in front of the plunger at the end of its stroke (`reservoir.dead`, front stop): %.1f mm3 = **%.1f U**, which is air after "
              "assembly and cannot be expelled through the single port in the centre of the closed end unless the pod is held with the outlet up.  REFILL.md quotes ~0.5 U priming and 3 mm3 dead volume; "
              "the geometry gives %.1f U for the fluid path, and `MAX_PRIME` in the firmware is %.3f U per prime command.\n" % (dead_mm, V_dead_gap, V_dead_gap / 10, V_path / 10, MAX_PRIME_U))
    rows = []
    for s in ctx.sizes:
        st = ctx.stroke(s)
        cap_u = st * A / 10
        rows.append([s, f"{cap_u:.1f}", f"{(st + dead_mm) * A / 10:.1f}", f"{V_dead_gap / 10 + V_path / 10:.1f}", f"{100 * (V_dead_gap + V_path) / 10 / cap_u:.1f} %"])
    md.append(table(["size", "deliverable U (stroke)", "chamber + dead layer U", "unusable dead + path U", "share of capacity"], rows))

    # ---------------- 5.2 outlet resistance --------------------------------------------------------------------
    md.append("### 5.2 Outlet flow resistance (Hagen-Poiseuille)\n")
    mu = C["mu_insulin"][2]
    rows = []
    for tag, d_mm, L_mm in (("30G blunt needle d0.159, 4.2 mm cut", 0.159, 4.2), ("30G, 6.35 mm (uncut)", 0.159, 6.35), ("Insight Flex cannula d0.25 x 8 mm [ASM]", 0.25, 8.0)):
        for tag2, Qu in (("bolus 1.5 U/min", 1.5 / 60), ("basal 0.5 U/h", 0.5 / 3600), ("priming 1 U/s", 1.0)):
            Q = Qu * 10e-9                                        # m3/s
            dP = 128 * mu * L_mm * 1e-3 * Q / (PI * (d_mm * 1e-3) ** 4)
            rows.append([tag, tag2, f"{dP:.2f} Pa" if dP < 1000 else f"{dP / 1e3:.2f} kPa"])
    md.append("Viscosity %.1f mPa*s (10 C worst case).  The outlet is not a restriction at delivery rates (tens of pascal); only the duckbill cracking pressure (1-5 kPa [ASM]) and, on a body, tissue back-pressure "
              "would matter (bench: containers, ~0).\n" % (1e3 * mu))
    md.append(table(["element", "flow", "pressure drop"], rows))

    # ---------------- 5.3 compliance ---------------------------------------------------------------------------
    md.append("### 5.3 System compliance (mm3 per kPa)\n")
    E_pp, nu = C["PP_E"], C["PP_nu"]
    Ep = E_pp / (1 - nu ** 2)
    t_w = P["reservoir_frozen"]["wall"]
    b = ctx.w_in - ctx.h_in
    w_per_kPa = 1e-3 * b ** 4 / (32 * Ep * t_w ** 3) * 0.533           # mean deflection of a clamped strip (mm per kPa)
    Vb = 10.0
    rows = []
    comp = {}
    for s in ctx.sizes:
        L = ctx.stroke(s) + dead_mm
        C_wall = 2 * b * L * w_per_kPa
        C_train_asdrawn = A * (A * 1e-3 / a4r["k_train"])
        C_train_fix = A * (A * 1e-3 / a4r["k_train_alt"])
        C_bub = Vb / C["P_atm_kPa"]
        C_sil = 0.05          # duckbill + septum + cap [ASM]
        C_liq = 4.6e-7 * (L * A)                # liquid compressibility 4.6e-10 /Pa = 4.6e-7 per kPa, times volume
        comp[s] = dict(wall=C_wall, train=C_train_asdrawn, train_fix=C_train_fix, bub=C_bub, sil=C_sil, liq=C_liq)
        tot = C_wall + C_train_asdrawn + C_bub + C_sil + C_liq
        tot_fix = C_wall + C_train_fix + C_bub + C_sil + C_liq
        comp[s]["tot"], comp[s]["tot_fix"] = tot, tot_fix
        rows.append([s, f"{C_wall:.3f}", f"{C_train_asdrawn:.3f} ({C_train_fix:.3f})", f"{C_bub:.3f}", f"{C_sil:.3f}", f"{C_liq:.4f}", f"{tot:.2f} ({tot_fix:.2f})"])
    md.append("PP reservoir flat walls (strip %.0f mm, t %.1f mm, clamped, no support from the housing = upper bound), thrust-train wind-up (A^2/k_train, from 4.2; value in brackets with the 1.2 mm tongue), a "
              "10 mm3 air bubble (isothermal, V/p_atm), silicone duckbill/septum/cap [ASM], liquid compressibility.\n" % (b, t_w))
    md.append(table(["size", "PP walls", "train wind-up (tongue 1.2)", "bubble 10 mm3", "silicone parts", "liquid", "total mm3/kPa (tongue 1.2)"], rows))

    # ---------------- 5.4 occlusion ---------------------------------------------------------------------------
    md.append("### 5.4 Occlusion detection (spec 7: alarm at <= 2 U undelivered)\n")
    md.append("The firmware detects occlusion as (commanded - encoder-confirmed) > 2 U (`safety.rs`), i.e. only **after the motor has stalled** (the encoder measures the leadscrew, not the plunger).  "
              "Pressure therefore builds to P_stall = (F available - F kinetic) / A first; the volume stored in the compliance V_st = C x P_stall is *additional* undelivered insulin, "
              "and it is released as a bolus when the line is cleared.  Total undelivered at alarm = V_st + 2 U; time to alarm = that / flow rate.\n")
    size_ref = ctx.sizes[1] if len(ctx.sizes) > 1 else ctx.sizes[0]
    cc = comp[size_ref]
    F_hi = a1r["F_avail_rated"]
    F_lo = a1r["F_avail"]
    rows = []
    occ = {}
    for fa_tag, Fa in (("105 mA", F_lo), ("181 mA", F_hi)):
        for Fk in (1.0, 2.0, 4.0, a1r["F_seal"]):
            Pst = max(Fa - Fk, 0) / A * 1e3
            for tr_tag, ct in (("as drawn", cc["tot"]), ("tongue 1.2", cc["tot_fix"])):
                Vst = ct * Pst / 10.0                            # U (1 U = 10 mm3)
                thr_ok = max(THRESH_FW - Vst, 0.0)
                t_bol = (Vst + THRESH_FW) / 1.5                   # min
                t_bas = (Vst + THRESH_FW) / 0.5                   # h
                occ[(fa_tag, Fk, tr_tag)] = (Pst, Vst, thr_ok, t_bol, t_bas)
                rows.append([fa_tag, f"{Fk:.1f}", tr_tag, f"{Fa:.1f}", f"{Pst:.0f}", f"{Vst:.2f}", f"{Vst + THRESH_FW:.2f}", f"{thr_ok:.2f}", f"{t_bol:.1f} min", f"{t_bas:.1f} h"])
    md.append("Reference size %s (compliance from 5.3).\n" % size_ref)
    md.append(table(["current limit", "F kinetic N", "train", "F avail N", "P_stall kPa", "stored V_st U", "undelivered at alarm U (V_st + 2)", "firmware threshold needed for <= 2 U total", "t alarm @ bolus 1.5 U/min", "t alarm @ basal 0.5 U/h"], rows))
    md.append("Reading: with the threshold at 2 U the *total* undelivered insulin at alarm is always > 2 U; to meet the spec literally the threshold has to be lowered by V_st (last-but-one column), "
              "and at basal 0.5 U/h the alarm takes about 4 hours or more regardless (the 2 U criterion is volume-based).  If the seal friction is as high as the model in 1.2 (%.1f N) the pump never reaches a "
              "pressure above the seal friction at 105 mA, so P_stall = 0 and every dose looks like an occlusion.\n" % a1r["F_seal"])
    # pressure vs time figure for bolus
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for (fa_tag, Fa), col in zip((("105 mA", F_lo), ("181 mA", F_hi)), PALETTE):
        Fks = np.linspace(0.2, min(Fa, 8), 60)
        Pst = np.maximum(Fa - Fks, 0) / A * 1e3
        ax[0].plot(Fks, Pst * cc["tot_fix"] / 10, color=col, label=f"{fa_tag}, tongue 1.2 mm")
        ax[0].plot(Fks, Pst * cc["tot"] / 10, color=col, ls="--", label=f"{fa_tag}, tongue as drawn")
    ax[0].axhline(THRESH_FW, color="k", ls=":", lw=1)
    ax[0].set_xlabel("plunger kinetic friction [N]")
    ax[0].set_ylabel("stored volume at stall [U]")
    ax[0].set_title("Insulin stored in compliance before the alarm path starts")
    ax[0].legend(fontsize=7)
    ax[0].spines[["top", "right"]].set_visible(False)
    Vbs = np.linspace(0, 80, 80)
    ax[1].plot(Vbs, Vbs / C["P_atm_kPa"] * 5 / 10, color=PALETTE[0], label="start lag at 5 kPa crack")
    ax[1].plot(Vbs, Vbs * (C["P_atm_kPa"] / 75.0 - 1) / 10, color=PALETTE[1], label="expansion at 75 kPa (cabin 2400 m)")
    ax[1].plot(Vbs, Vbs * (310.0 / 293.0 - 1) / 10, color=PALETTE[2], label="expansion 20 -> 37 C")
    ax[1].axvline(V_dead_gap, color="#999", ls="--")
    ax[1].text(V_dead_gap + 1, 0.2, "dead layer %.0f mm3" % V_dead_gap, fontsize=7)
    ax[1].set_xlabel("trapped air volume [mm3]")
    ax[1].set_ylabel("volume effect [U]")
    ax[1].set_title("Bubble effects")
    ax[1].legend(fontsize=7)
    ax[1].spines[["top", "right"]].set_visible(False)
    figp = ctx.save(fig, "a5_fluidics.png")
    plt.close(fig)

    # ---------------- 5.5 bubbles -----------------------------------------------------------------------------
    md.append("### 5.5 Bubbles\n")
    rows = []
    for Vb_ in (2.0, 5.0, 10.0, V_dead_gap):
        rows.append([f"{Vb_:.0f} mm3", f"{Vb_ / C['P_atm_kPa'] * 5 / 10:.3f}", f"{Vb_ * (C['P_atm_kPa'] / 75.0 - 1) / 10:.2f}", f"{Vb_ * (310.0 / 293.0 - 1) / 10:.2f}", f"{Vb_ / C['P_atm_kPa'] / 10:.3f} U/kPa"])
    md.append("A bubble acts as a spring: it delays the start of flow by V_b x P_crack / P_atm, expands when pressure drops (altitude, 75 kPa) or temperature rises and pushes that volume out "
              "(into the container) without a motor step, and adds compliance to the occlusion path.\n")
    md.append(table(["trapped air", "start lag at 5 kPa crack U", "expansion at 75 kPa cabin U", "expansion 20 -> 37 C U", "compliance"], rows))
    md.append("Draw mode adds air through the vacuum: dissolved gas nucleates above roughly 30 kPa suction (1.5); the check valve prevents air from the outlet only if it seals against that suction "
              "(the REFILL.md test pressure of 20 kPa is below the 25-35 kPa of a 29G fill needle at full speed).  The duckbill pocket in the cap is bored d%.2f for a d%.1f valve and has an open slot to the pod interior "
              "(`t_cap_vs`): unless the valve has its own sealing flange / interference fit, flow can bypass the valve around its outer diameter and leak into the pod.\n" % (P["coax"]["valve_d"] + 0.05, P["coax"]["valve_d"]))
    md.append("![fluidics](%s)\n" % figp)

    o = occ[("181 mA", 2.0, "tongue 1.2")]
    o2 = occ[("105 mA", 2.0, "as drawn")]
    o3 = occ[("105 mA", 1.0, "as drawn")]
    start_lag_u = 10.0 / C["P_atm_kPa"] * 5 / 10
    res.rows += [
        Row("5.1", "Fluidics", f"Priming path volume <= MAX_PRIME {MAX_PRIME_U:.2f} U (one prime command)", f"{V_path / 10:.2f} U path (+ {V_dead_gap / 10:.1f} U dead layer)", f"{MAX_PRIME_U / (V_path / 10):.2f}x",
            status(V_path / 10 <= MAX_PRIME_U, V_path / 10 <= 2 * MAX_PRIME_U), "REFILL.md says ~0.5 U; several prime commands or a bigger limit for the bench"),
        Row("5.2", "Fluidics", "Dead layer in front of the plunger <= 0.5 U (air trap, central port)", f"{V_dead_gap / 10:.1f} U (reservoir.dead = {dead_mm} mm)", f"{0.5 / (V_dead_gap / 10):.2f}x", status(V_dead_gap / 10 <= 0.5, V_dead_gap / 10 <= 2.5),
            "move the front stop (not the CNC part) to <= 0.3 mm, prime outlet-up"),
        Row("5.3", "Fluidics", "Outlet resistance negligible: needle dP at 1.5 U/min", "%.0f Pa" % (128 * mu * 4.2e-3 * (1.5 / 60 * 10e-9) / (PI * (0.159e-3) ** 4)), "-", "PASS", "duckbill cracking dominates, not the needle"),
        Row("5.4", "Fluidics", "Undelivered volume at occlusion alarm <= 2 U (threshold 2 U), 181 mA, F_kin 2 N, tongue 1.2", f"{o[1] + THRESH_FW:.2f} U (V_st {o[1]:.2f})", f"{2 / (o[1] + THRESH_FW):.2f}x",
            status(o[1] <= 1e-6, o[1] <= 0.5), f"set firmware threshold to {o[2]:.1f} U to meet 2 U"),
        Row("5.5", "Fluidics", "same, as designed: 105 mA, F_kin 2 N, tongue as drawn", f"{o2[1] + THRESH_FW:.2f} U (V_st {o2[1]:.2f})", "-", status(o2[1] <= 1e-6, o2[1] <= 0.5), f"P_stall {o2[0]:.0f} kPa"),
        Row("5.6", "Fluidics", "Occlusion alarm time at basal 0.5 U/h (info)", f"{o[4]:.1f} h", "-", "INFO", "2 U volume criterion; a time or current criterion is needed for basal"),
        Row("5.7", "Fluidics", "Occlusion alarm time at bolus 1.5 U/min (info)", f"{o[3]:.1f} min", "-", "INFO", ""),
        Row("5.8", "Fluidics", "Start-of-flow lag from a 10 mm3 bubble <= 0.05 U", f"{start_lag_u:.3f} U", f"{0.05 / start_lag_u:.2f}x", status(start_lag_u <= 0.05, start_lag_u <= 0.1), "dead layer air (%.0f mm3) would be %.2f U" % (V_dead_gap, V_dead_gap / C['P_atm_kPa'] * 5 / 10)),
        Row("5.9", "Fluidics", "Bubble expansion at cabin pressure, 10 mm3 (info)", f"{10 * (C['P_atm_kPa'] / 75.0 - 1) / 10:.2f} U", "-", "INFO", "pushed out without steps (bench: into a container)"),
    ]
    ctx.shared["a5"] = {"V_path_U": V_path / 10, "V_dead_U": V_dead_gap / 10, "comp": comp, "occ": {str(k): v for k, v in occ.items()}}
    res.md = "\n".join(md)
    return res
