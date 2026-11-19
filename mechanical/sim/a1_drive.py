"""Analysis 1: force / torque budget of the drive chain (delivery and draw mode)."""
from __future__ import annotations

import math

import numpy as np

from common import CONST as C, GF_CM, PI, PALETTE, Ctx, Result, Row, fmt, perim_stadium, status, table

I_RATED_mA = C["motor_V"] / C["motor_R"] * 1000.0


def tri(rng, lo, nom, hi, n):
    return rng.triangular(lo, nom, hi, n)


# ---- elementary models --------------------------------------------------------------------------------------
def thread_coeff(ctx: Ctx, mu: float):
    """Torque per axial force of the M1.6x0.35 thread [N*mm/N] (power-screw formula, 60 deg flank)."""
    d, p = ctx.P["drive"]["screw_d"], ctx.pitch
    d2 = d - 0.6495 * p
    lam = math.atan(p / (PI * d2))
    ca = math.cos(math.radians(C["thread_half_angle_deg"]))
    return d2 / 2.0 * (math.tan(lam) + mu / ca) / (1.0 - mu * math.tan(lam) / ca)


def thread_eff(ctx: Ctx, mu: float):
    return (ctx.pitch / (2 * PI)) / thread_coeff(ctx, mu)


def collar_coeff(ctx: Ctx, mu: float, rm=None):
    dr = ctx.P["drive"]
    ro, ri = dr["bush_od"] / 2, dr["bush_id"] / 2
    if rm is None:
        rm = 2.0 / 3.0 * (ro ** 3 - ri ** 3) / (ro ** 2 - ri ** 2)
    return mu * rm


def motor_torque(I_mA=None, f_pps=None, hold=False):
    """Motor-shaft torque [N*mm] at current limit I_mA and step rate f (pull-out), derated from the single published point."""
    I_mA = C["I_set_mA"] if I_mA is None else I_mA
    kI = min(1.0, I_mA / I_RATED_mA)
    f = C["pullout_pps"] if f_pps is None else f_pps
    kf = 1.0 if f <= C["pullout_pps"] else (C["pullout_pps"] / f) ** C["pullout_droop_exp"]
    return C["T_pullout_gfcm"] * GF_CM * kI * kf * (C["hold_over_pullout"] if hold else 1.0)


def thrust(ctx, zm, zs, I_mA=None, f_pps=None, gh_eff=None, pair_eff=None, mu_t=None, mu_c=None, hold=False, rm=None):
    gh_eff = C["gh_eff"][1] if gh_eff is None else gh_eff
    pair_eff = C["pair_eff"][1] if pair_eff is None else pair_eff
    mu_t = C["mu_thread"][1] if mu_t is None else mu_t
    mu_c = C["mu_collar"][1] if mu_c is None else mu_c
    T = motor_torque(I_mA, f_pps, hold) * ctx.gh * gh_eff * (zs / zm) * pair_eff       # torque on the screw
    return T / (thread_coeff(ctx, mu_t) + collar_coeff(ctx, mu_c, rm)), T


def gent_E(shore):
    """Young's modulus [MPa] from Shore A (Gent 1958)."""
    return 0.0981 * (56 + 7.62336 * shore) / (0.137505 * (254 - 2.54 * shore))


def seal_friction(ctx: Ctx, dbore=0.0, mu=None, shore=None, n_rings=None, b_c=None, oversize=None):
    """Kinetic friction of the two cast silicone lip rings in the stadium bore [N] (squeeze x contact area x mu)."""
    P = ctx.P
    sl, rs = P["seal"], P["reservoir"]
    mu = C["mu_seal"][1] if mu is None else mu
    shore = C["shore_A"][1] if shore is None else shore
    widths = [sl["ring_a"][1] - sl["ring_a"][0], sl["ring_b"][1] - sl["ring_b"][0]]
    n = len(widths) if n_rings is None else n_rings
    b = sum(widths) / len(widths) if b_c is None else b_c
    over = sl["free_oversize"] if oversize is None else oversize
    over_eff = over - C["silicone_shrink"] * ctx.w_in
    wc = rs["w_in"] - 2 * rs["plunger_clr"]
    wg = wc - 2 * sl["groove_depth"]                       # groove floor width = ring inner width
    t_free = (ctx.w_in + over_eff - wg) / 2.0               # free radial thickness of the cast ring
    delta = (over_eff - dbore) / 2.0                        # radial interference per side in the bore
    eps = max(delta, 0.0) / t_free
    E = gent_E(shore)
    S = b / (2 * t_free)                                    # shape factor (loaded / bulge area)
    Ec = E * (1 + 2 * S * S)
    p = Ec * eps
    perim = perim_stadium(ctx.w_in + dbore, ctx.h_in + dbore)
    N = p * b * perim * n
    return {"F": mu * N, "N": N, "p": p, "eps": eps, "delta": delta, "E": E, "t_free": t_free, "perim": perim, "b": b, "n": n}


def duckbill_force(ctx, kPa=None):
    return (3.0 if kPa is None else kPa) * 1e-3 * ctx.A          # N


def run(ctx: Ctx) -> Result:
    res = Result("A1 Drive chain force budget")
    P = ctx.P
    A = ctx.A
    zm0, zs0 = ctx.active
    md = ["## 1. Force / torque budget of the drive chain\n"]
    md.append(
        "**Model.** Motor pull-out torque (1.6 gf*cm at 500 pps, rated 4.8 V = %.0f mA) x current-limit ratio x planetary ratio %.2f x gearhead "
        "efficiency x gear-pair ratio z_screw/z_motor x pair efficiency gives the **screw torque**; the axial force follows from the power-screw "
        "formula T = F*[ (d2/2)(tan(lam)+mu/cos(30deg))/(1-mu*tan(lam)/cos(30deg)) + mu_c*r_collar ] with d2 = 1.373 mm, lead angle %.2f deg and a "
        "thrust collar at the bush end face (r_m = %.2f mm; the dry-end bush face takes the delivery thrust).  Required force = plunger seal "
        "friction (squeeze x contact area x mu, Gent E(Shore A)) x breakaway factor + duckbill/needle back-pressure x bore area %.2f mm2.  "
        "Hagen-Poiseuille is used for needle and cannula.\n" % (I_RATED_mA, ctx.gh, math.degrees(math.atan(ctx.pitch / (PI * (1.6 - 0.6495 * ctx.pitch)))),
                                                                collar_coeff(ctx, 1.0), A))
    md.append("Sources / assumptions: motor point [DS vendor page]; current limit 105 mA is what the **controller board is designed for** "
              "(`limits.rs`, `electronics/bench/pin-assignment.md`: VREF 0.105 V / 1.0 ohm, 'tune R69' still open); efficiencies, friction "
              "coefficients, seal mu and breakaway factor are [ASM] ranges in `common.CONST` (seal mu 0.15 lubed ... 0.9 dry).  "
              "No pull-out curve exists, so torque above 500 pps is derated as (500/f)^0.5 [ASM].\n")

    # ---------- nominal thrust, by gear option --------------------------------------------------------------------
    sf = seal_friction(ctx)
    F_back = duckbill_force(ctx, 3.0) + 0.0
    be = C["breakaway"][1]
    F_req_static = be * sf["F"] + F_back
    rows = []
    best = None
    opt_data = []
    for name, zm, zs in ctx.gear_options():
        ctr = ctx.centre(zm, zs)
        Fa, Ts = thrust(ctx, zm, zs)
        Fr, _ = thrust(ctx, zm, zs, I_mA=I_RATED_mA)
        fits = ctr >= ctx.min_centre - 1e-9 or ctx.layout_kind != "side_gears"
        u = ctx.u_per_step(zm, zs)
        opt_data.append((name, zm, zs, ctr, u, Fa, Fr, fits))
        rows.append([name, f"{ctr:.2f}", "yes" if fits else "NO (needs >= %.1f)" % ctx.min_centre, f"{u:.5f}", f"{Ts:.2f}", f"{Fa:.2f}", f"{Fr:.2f}",
                     f"{Fa / F_req_static:.2f}", f"{Fr / F_req_static:.2f}"])
    md.append("### 1.1 Available thrust by gear pair (nominal efficiencies, mu_thread %.2f, mu_collar %.2f)\n" % (C["mu_thread"][1], C["mu_collar"][1]))
    md.append(table(["pair (motor:screw)", "centre mm", "fits motor lane", "U/step", "screw torque N*mm @105 mA", "F avail N @105 mA", "F avail N @181 mA (rated)",
                     "margin @105 mA", "margin @181 mA"], rows))
    md.append("Margin = F available / F required (static) with F required = %.1f x seal friction %.1f N + back-pressure %.2f N = **%.1f N**.  "
              "The spec text (spec 4) quotes 9.5 N by assuming a flat 20 %% overall screw efficiency; the power-screw model with a collar gives the "
              "numbers above (thread efficiency %.0f %% at mu %.2f, collar torque is as large as the thread torque).\n"
              % (be, sf["F"], F_back, F_req_static, 100 * thread_eff(ctx, C["mu_thread"][1]), C["mu_thread"][1]))

    # ---------- seal friction detail ---------------------------------------------------------------------------
    md.append("### 1.2 Plunger seal friction model (the dominant unknown)\n")
    md.append("Geometry from `params.json`: 2 rings x %.1f mm wide, bore perimeter %.1f mm, cast oversize %.2f mm (diametral) minus %.1f %% shrink, free ring thickness "
              "%.2f mm -> radial squeeze %.3f mm per side = %.1f %% -> contact pressure %.2f MPa (Shore A %.0f, E = %.2f MPa, shape factor %.2f) -> normal force %.1f N -> "
              "kinetic friction **%.1f N** at mu = %.2f (range below).  Cross-check: the same formula for a 1 ml insulin syringe stopper (perimeter 15 mm, 2 ribs of 0.5 mm, "
              "0.1 mm squeeze, siliconised mu 0.2) gives 1-2 N, in line with usual syringe glide forces of a few N [LIT, order of magnitude].  "
              "Our seal has about 4x the contact area of that stopper and is not siliconised.\n"
              % (sf["b"], sf["perim"], P["seal"]["free_oversize"], 100 * C["silicone_shrink"], sf["t_free"], sf["delta"], 100 * sf["eps"], sf["p"], C["shore_A"][1],
                 sf["E"], sf["b"] / (2 * sf["t_free"]), sf["N"], sf["F"], C["mu_seal"][1]))
    rows = []
    for mu in C["mu_seal"]:
        for db in (0.0, 0.05):
            s2 = seal_friction(ctx, dbore=db, mu=mu)
            rows.append([f"{mu:.2f}", f"+{db:.2f}", f"{s2['delta']:.3f}", f"{s2['F']:.1f}", f"{be * s2['F']:.1f}"])
    md.append(table(["mu seal", "CNC bore oversize (frozen tol +0.05/0)", "squeeze/side mm", "F kinetic N", "F breakaway N"], rows))

    # design sweep for the seal: what squeeze / width / rings give friction <= budget
    Fa_nom, _ = thrust(ctx, zm0, zs0)
    budget = (Fa_nom - F_back) / be / 1.5          # keep 1.5 margin on breakaway
    rows = []
    sweep = {}
    for n_r in (2, 1):
        for b in (0.8, 0.4):
            for over in (0.3, 0.2, 0.1):
                s2 = seal_friction(ctx, n_rings=n_r, b_c=b, oversize=over, mu=0.25, dbore=0.025)
                sweep[(n_r, b, over)] = s2["F"]
                rows.append([n_r, b, over, f"{s2['delta']:.3f}", f"{s2['F']:.1f}", "ok" if s2["F"] <= budget else "too high"])
    md.append("Design sweep (mu 0.25 i.e. wetted + a little silicone oil, bore +0.025 mean).  Friction budget at the CAD gear pair, %.0f mA: "
              "(F avail - back-pressure)/breakaway/1.5 = **%.1f N** kinetic.\n" % (C["I_set_mA"], budget))
    md.append(table(["rings", "contact width mm", "cast oversize mm (diam.)", "squeeze/side mm", "F kinetic N", "vs budget"], rows))

    # ---------- sensitivity (tornado) on F available -----------------------------------------------------------------
    base, _ = thrust(ctx, zm0, zs0)
    sens = []
    for label, kw, lo, hi in (
        ("gearhead efficiency 0.50..0.81", "gh_eff", C["gh_eff"][0], C["gh_eff"][2]),
        ("gear pair efficiency 0.90..0.98", "pair_eff", C["pair_eff"][0], C["pair_eff"][2]),
        ("thread mu 0.35..0.15", "mu_t", C["mu_thread"][2], C["mu_thread"][0]),
        ("collar mu 0.30..0.10", "mu_c", C["mu_collar"][2], C["mu_collar"][0]),
        ("motor current 105 mA .. 181 mA", "I_mA", 105.0, I_RATED_mA),
        ("thrust collar mean radius 1.2 mm (bush face) .. 0.4 mm (ball/pin end)", "rm", 1.2, 0.4),
    ):
        a = thrust(ctx, zm0, zs0, **{kw: lo})[0]
        b = thrust(ctx, zm0, zs0, **{kw: hi})[0]
        sens.append((label, a, b))
    md.append("### 1.3 Sensitivity of the available thrust (CAD pair %s, base %.2f N at %.0f mA)\n" % (ctx.active, base, C["I_set_mA"]))
    md.append(table(["parameter (low .. high)", "F avail N (low)", "F avail N (high)"], [[s[0], f"{s[1]:.2f}", f"{s[2]:.2f}"] for s in sens]))

    # ---------- Monte Carlo of start-up (breakaway) -----------------------------------------------------------------
    rng = np.random.default_rng(1)
    N = 40000
    out = {}
    for tag, I in (("105 mA (as designed)", C["I_set_mA"]), ("181 mA (rated)", I_RATED_mA)):
        gh = tri(rng, *C["gh_eff"], N)
        pe = tri(rng, *C["pair_eff"], N)
        mt = tri(rng, *C["mu_thread"], N)
        mc = tri(rng, *C["mu_collar"], N)
        dr = ctx.P["drive"]
        T = motor_torque(I) * ctx.gh * gh * (zs0 / zm0) * pe
        # vectorised thread / collar coefficients
        d2 = dr["screw_d"] - 0.6495 * ctx.pitch
        lam = math.atan(ctx.pitch / (PI * d2))
        ca = math.cos(math.radians(30))
        cth = d2 / 2 * (math.tan(lam) + mt / ca) / (1 - mt * math.tan(lam) / ca)
        cc = mc * collar_coeff(ctx, 1.0)
        Fa = T / (cth + cc)
        mu_s = rng.uniform(C["mu_seal"][0], C["mu_seal"][2], N)
        shore = rng.uniform(C["shore_A"][0], C["shore_A"][2], N)
        db = rng.uniform(0, ctx.P["reservoir_frozen"]["bore_tol_plus"], N)
        brk = tri(rng, *C["breakaway"], N)
        over = P["seal"]["free_oversize"] - C["silicone_shrink"] * ctx.w_in
        wc = P["reservoir"]["w_in"] - 2 * P["reservoir"]["plunger_clr"]
        wg = wc - 2 * P["seal"]["groove_depth"]
        tf = (ctx.w_in + over - wg) / 2
        eps = np.maximum((over - db) / 2, 0) / tf
        Es = 0.0981 * (56 + 7.62336 * shore) / (0.137505 * (254 - 2.54 * shore))
        S = sf["b"] / (2 * tf)
        pc = Es * (1 + 2 * S * S) * eps
        per = perim_stadium(ctx.w_in + db, ctx.h_in + db)
        Fs = mu_s * pc * sf["b"] * per * sf["n"]
        Pb = rng.uniform(1.0, 5.0, N) * 1e-3 * A
        Freq = brk * Fs + Pb
        out[tag] = {"Fa": Fa, "Freq": Freq, "Fs": Fs, "p_stall": float(np.mean(Fa < Freq)), "p_margin15": float(np.mean(Fa < 1.5 * Freq))}
    md.append("### 1.4 Monte Carlo: can the motor break the plunger loose? (N = %d, uniform/triangular over all ranges above)\n" % N)
    rows = []
    for tag, o in out.items():
        rows.append([tag, f"{np.median(o['Fa']):.2f} ({np.percentile(o['Fa'], 5):.2f}..{np.percentile(o['Fa'], 95):.2f})",
                     f"{np.median(o['Fs']):.1f} ({np.percentile(o['Fs'], 5):.1f}..{np.percentile(o['Fs'], 95):.1f})",
                     f"{100 * o['p_stall']:.0f} %", f"{100 * o['p_margin15']:.0f} %"])
    md.append(table(["current limit", "F avail N median (5..95 %)", "seal kinetic friction N median (5..95 %)", "P(F avail < F req static)", "P(margin < 1.5)"], rows))

    # ---------- draw mode -----------------------------------------------------------------------------------------
    md.append("### 1.5 Reverse (draw) mode: suction through the fill needle\n")
    md.append("Delivery rates are tiny (bolus 1.5 U/min = %.1f steps/s, basal 0.5 U/h = one step every %.0f s) so the motor runs at low speed where torque >= the 500 pps value.  "
              "Draw is the only fast mode: DRAW_MAX_PPS = 1000 pps = %.2f U/s (100 U in %.0f s).  The syringe/vial needle through the septum is the restriction; "
              "the plunger must also pull a vacuum dP = Q*R_needle.  Needle ID from gauge tables [LIT]; viscosity 1.1 mPa*s (1.6 at 10 C), needle length 12.7 mm "
              "(insulin syringe) + 0.7 mm cap channel (negligible).  Vacuum above about 30 kPa risks degassing and air bubbles in the fill (dissolved air supersaturates); "
              "stored-volume effects of the vacuum are in analysis 5.\n"
              % (1.5 / 60.0 / ctx.u_per_step(zm0, zs0), ctx.u_per_step(zm0, zs0) / (0.5 / 3600),
             1000 * ctx.u_per_step(zm0, zs0), 100 / (1000 * ctx.u_per_step(zm0, zs0))))
    L_n = 12.7e-3
    mu_v = C["mu_insulin"]
    rows = []
    draw_ok = {}
    for g, (od, idd) in C["needles"].items():
        d = idd * 1e-3
        Rn = 128 * mu_v[1] * L_n / (PI * d ** 4)      # Pa*s/m3
        for pps in (250, 500, 1000):
            Q = pps * ctx.u_per_step(zm0, zs0) * 10 * 1e-9      # m3/s (1 U = 10 mm3)
            dP = Rn * Q / 1e3                                    # kPa
            dP_cold = dP * mu_v[2] / mu_v[1]
            F_draw = sf["F"] + dP * 1e-3 * A
            Fa_f = thrust(ctx, zm0, zs0, f_pps=pps)[0]
            rows.append([g, f"{idd:.3f}", pps, f"{pps * ctx.u_per_step(zm0, zs0):.2f}", f"{dP:.1f}", f"{dP_cold:.1f}", f"{F_draw:.1f}", f"{Fa_f:.2f}",
                         "ok" if (dP_cold <= 30 and Fa_f >= 1.5 * F_draw) else "no"])
            draw_ok[(g, pps)] = (dP, dP_cold, F_draw, Fa_f)
    md.append(table(["needle", "ID mm", "pps", "U/s", "vacuum dP kPa (25 C)", "dP kPa (10 C)", "F draw N (seal + dP*A)", "F avail N at pps", "dP<=30 kPa and margin>=1.5"], rows))
    # max pps for 29G: dP <= 30 kPa
    mx = {}
    for g, (od, idd) in C["needles"].items():
        d = idd * 1e-3
        Rn = 128 * mu_v[2] * L_n / (PI * d ** 4)
        Qmax = 30e3 / Rn
        mx[g] = Qmax * 1e9 / 10 / ctx.u_per_step(zm0, zs0)     # pps at 10 C
    md.append("Max step rate that keeps the vacuum <= 30 kPa at 10 C: " + ", ".join(f"{g} {v:.0f} pps ({v * ctx.u_per_step(zm0, zs0):.2f} U/s)" for g, v in mx.items()) + ".\n")

    # ---------- occlusion capability / thrust ceilings ------------------------------------------------------------------
    Fa_nom, _ = thrust(ctx, zm0, zs0)
    Fh_nom, _ = thrust(ctx, zm0, zs0, hold=True)
    P_stall = max(Fa_nom - sf["F"], 0.0) / A * 1e3          # kPa
    md.append("### 1.6 Pressure the pump can build (occlusion)\n")
    md.append("P_stall = (F avail - kinetic seal friction) / A = (%.2f - %.1f) N / %.1f mm2 = **%.0f kPa** (CAD pair, %.0f mA, nominal).  Stall thrust incl. holding torque "
              "x%.1f = %.2f N.  Cracking pressure of a duckbill (1-5 kPa) is only %.2f-%.2f N, i.e. small compared to the seal.\n"
              % (Fa_nom, sf["F"], A, P_stall, C["I_set_mA"], C["hold_over_pullout"], Fh_nom, duckbill_force(ctx, 1), duckbill_force(ctx, 5)))

    # ---------- thermal one-liner -----------------------------------------------------------------------------------
    Pw = 2 * (C["I_set_mA"] / 1000) ** 2 * C["motor_R"]
    Pw_r = 2 * (I_RATED_mA / 1000) ** 2 * C["motor_R"]
    md.append("### 1.7 Winding dissipation (one-line thermal check)\n")
    md.append("Both phases energised: %.2f W at 105 mA, %.2f W at the rated 181 mA for a 6 mm motor (no heat path except the printed saddles).  A 20 s refill is fine, "
              "a continuously energised hold is not: the firmware must switch the driver off between pulses (to be confirmed on the bench by motor temperature).\n" % (Pw, Pw_r))

    # ---------- rows ----------------------------------------------------------------------------------------------
    Fa_nom, _ = thrust(ctx, zm0, zs0)
    Fa_rated, _ = thrust(ctx, zm0, zs0, I_mA=I_RATED_mA)
    F_ball, _ = thrust(ctx, zm0, zs0, rm=0.4)
    F_ball_best, _ = thrust(ctx, 16, 20, I_mA=I_RATED_mA, rm=0.4)
    F_step_down, _ = thrust(ctx, 16, 20)
    res.rows += [
        Row("1.1", "Drive", "Plunger thrust >= 5 N (spec 4) at 105 mA controller limit", f"{Fa_nom:.1f} N (CAD pair {ctx.active[0]}:{ctx.active[1]})", f"{Fa_nom / 5.0:.2f}x",
            status(Fa_nom >= 5.0, Fa_nom >= 3.5), "spec quotes ~9.5 N; power-screw + collar + current limit gives less"),
        Row("1.2", "Drive", "Plunger thrust >= 5 N at rated 181 mA", f"{Fa_rated:.1f} N", f"{Fa_rated / 5.0:.2f}x", status(Fa_rated >= 5.0, Fa_rated >= 3.5),
            "needs VREF raised to ~0.18 V (R69) and thermal check"),
        Row("1.3", "Drive", "Thrust margin >= 1.5 over static seal friction + back-pressure (nominal)", f"{Fa_nom:.1f} N vs {F_req_static:.1f} N", f"{Fa_nom / F_req_static:.2f}x",
            status(Fa_nom / F_req_static >= 1.5, Fa_nom / F_req_static >= 1.0), "seal friction is a model, bench pull test decides"),
        Row("1.4", "Drive", "P(motor cannot break the plunger loose) <= 1 % (MC, 105 mA)", f"{100 * out['105 mA (as designed)']['p_stall']:.0f} %", "-",
            status(out['105 mA (as designed)']['p_stall'] <= 0.01, out['105 mA (as designed)']['p_stall'] <= 0.10), "uniform ranges of seal mu, squeeze, Shore, breakaway"),
        Row("1.5", "Drive", "same at rated 181 mA", f"{100 * out['181 mA (rated)']['p_stall']:.0f} %", "-",
            status(out['181 mA (rated)']['p_stall'] <= 0.01, out['181 mA (rated)']['p_stall'] <= 0.10), ""),
        Row("1.6", "Drive", "Seal friction within budget at 105 mA (kinetic, margin 1.5 on breakaway)", f"{sf['F']:.1f} N vs budget {budget:.1f} N", f"{budget / sf['F']:.2f}x",
            status(sf['F'] <= budget, sf['F'] <= 1.5 * budget), "reduce squeeze/contact width, see 1.2 sweep"),
        Row("1.7", "Drive", "Draw mode: suction <= 30 kPa at 1000 pps, 29G fill needle, 10 C", f"{draw_ok[('29G', 1000)][1]:.0f} kPa", f"{30 / draw_ok[('29G', 1000)][1]:.2f}x",
            status(draw_ok[('29G', 1000)][1] <= 30, draw_ok[('29G', 1000)][1] <= 45), "limit pps or use a larger needle (see table 1.5)"),
        Row("1.8", "Drive", "Draw mode force margin >= 1.5 (29G, 1000 pps)", f"{draw_ok[('29G', 1000)][3]:.1f} N vs {draw_ok[('29G', 1000)][2]:.1f} N",
            f"{draw_ok[('29G', 1000)][3] / draw_ok[('29G', 1000)][2]:.2f}x",
            status(draw_ok[('29G', 1000)][3] >= 1.5 * draw_ok[('29G', 1000)][2], draw_ok[('29G', 1000)][3] >= draw_ok[('29G', 1000)][2]), ""),
        Row("1.9", "Drive", "Occlusion pressure the pump can build (info; typical pumps 100-300 kPa)", f"{P_stall:.0f} kPa", "-", "INFO", "limited by thrust minus seal friction"),
        Row("1.11", "Drive", "Option: ball/pin thrust end (r_m 0.4 mm) at 105 mA; 16:20 pair at 105 mA; both at 181 mA", f"{F_ball:.1f} N; {F_step_down:.1f} N; {F_ball_best:.1f} N", f"{F_ball_best / 5.0:.2f}x vs 5 N", "INFO", "levers to recover thrust"),
        Row("1.10", "Drive", "Winding dissipation, both phases on (info)", f"{Pw:.2f} W @105 mA / {Pw_r:.2f} W @181 mA", "-", "INFO", "driver must be off between pulses"),
    ]
    # gear option summary for the report header
    ctx.shared["a1"] = {"F_avail": Fa_nom, "F_avail_rated": Fa_rated, "F_seal": sf["F"], "F_seal_break": be * sf["F"], "F_back": F_back, "P_stall_kPa": P_stall,
                        "F_hold": Fh_nom, "mx_pps": mx, "F_ball": F_ball, "F_step_down": F_step_down, "F_best": F_ball_best, "budget": budget, "opt": opt_data, "p_stall": out["105 mA (as designed)"]["p_stall"]}

    # ---------- figures -----------------------------------------------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    names = [o[0] for o in opt_data]
    x = np.arange(len(names))
    ax[0].bar(x - 0.2, [o[5] for o in opt_data], 0.4, color=PALETTE[0], label="105 mA (controller as designed)")
    ax[0].bar(x + 0.2, [o[6] for o in opt_data], 0.4, color=PALETTE[2], label="181 mA (rated)")
    lo, hi = np.percentile(out["105 mA (as designed)"]["Freq"], [5, 95])
    ax[0].axhspan(lo, hi, color=PALETTE[1], alpha=0.25, label="required (static), 5-95 %")
    ax[0].axhline(5.0, color="k", ls="--", lw=1, label="spec 5 N")
    ax[0].set_xticks(x)
    ax[0].set_xticklabels(names, rotation=30, ha="right")
    ax[0].set_ylabel("plunger thrust [N]")
    ax[0].set_title("Thrust vs gear pair (motor:screw)")
    ax[0].legend(fontsize=7)
    for a_, hv in zip(ax, (None, None)):
        a_.spines[["top", "right"]].set_visible(False)
    gs = list(C["needles"])
    for pps, col in ((250, PALETTE[5]), (500, PALETTE[0]), (1000, PALETTE[1])):
        ax[1].plot(gs, [draw_ok[(g, pps)][1] for g in gs], "o-", color=col, label=f"{pps} pps")
    ax[1].axhline(30, color="k", ls="--", lw=1)
    ax[1].text(0.02, 31, "30 kPa degassing limit", fontsize=7)
    ax[1].set_ylabel("vacuum during draw [kPa] (10 C)")
    ax[1].set_title("Draw suction vs fill needle gauge")
    ax[1].legend(fontsize=7)
    ax[1].spines[["top", "right"]].set_visible(False)
    figp = ctx.save(fig, "a1_force.png")
    plt.close(fig)
    md.append("![thrust and draw](%s)\n" % figp)
    res.md = "\n".join(md)
    return res
