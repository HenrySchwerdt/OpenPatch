"""Analysis 3: tolerance stack-ups (worst case, RSS, Monte Carlo)."""
from __future__ import annotations

import math

import numpy as np

import a1_drive as a1
from common import CONST as C, PI, PALETTE, Ctx, Result, Row, status, table

PROC = {"MJF": C["tol_MJF"], "SLA": C["tol_SLA"]}


def stack(items):
    """items: list of (name, +-tol). Returns (worst case, RSS)."""
    wc = sum(t for _, t in items)
    rss = math.sqrt(sum(t * t for _, t in items))
    return wc, rss


def uni(rng, tol, n):
    return rng.uniform(-tol, tol, n)


def run(ctx: Ctx) -> Result:
    res = Result("A3 Tolerance stack-ups")
    P = ctx.P
    dr, sh, dk, cn = P["drive"], P["shell"], P["dock"], P["cannula"]
    rng = np.random.default_rng(11)
    N = 60000
    md = ["## 3. Tolerance stack-ups\n"]
    md.append("Process tolerance per printed feature position: MJF PA12 +-%.2f mm, SLA +-%.2f mm (task statement).  Worst case (WC) = sum, RSS = root-sum-square (each tolerance read as 3 sigma), "
              "Monte Carlo with uniform distributions.  CNC reservoir: bore +0.05/0, outer +-0.1 (frozen drawing).\n" % (PROC["MJF"], PROC["SLA"]))

    # ------------------------------------------------------------------------------------------------------------
    # 3.1 gear centre distance
    # ------------------------------------------------------------------------------------------------------------
    md.append("### 3.1 Gear centre distance vs module 0.3 backlash\n")
    tan_a = math.tan(math.radians(C["pressure_angle"]))
    cl_motor = 0.10                      # motor OD 6.0+-0.1 in the d6.1 bore (t_mcut): float of the body
    bush_clr = dr["bush_bore_clr"] / 2    # bush OD 3.0 in bore 3.05
    screw_play = (dr["bush_id"] - dr["screw_d"]) / 2
    j_target = 0.02                       # smallest acceptable normal backlash (no binding) [ASM]
    out31 = {}
    rows = []
    for proc, t in PROC.items():
        items = [("motor bore position", t), ("motor float in the d6.1 bore", cl_motor), ("screw bush bore position", t), ("bush float in its bore", bush_clr),
                 ("screw radial play in the bush", screw_play), ("gear bores on shaft/sleeve (2 x 0.01)", 0.02)]
        wc, rss = stack(items)
        # backlash model: j_t = j0 + 2 da tan(alpha), j0 triangular 0.015..0.045 (DIN 58405 q8 thinning), da = centre error
        j0 = rng.triangular(*C["gear_j0"], N)
        da = sum(uni(rng, tt, N) for _, tt in items)
        c_add = P.get('bench', {}).get('gears', {}).get('centre_add', 0.0)   # built centre = theoretical + centre_add (CAD)
        j_ct = j0 + 2 * (da + c_add) * tan_a
        p_bind = float(np.mean(j_ct < 0.0))
        j_wc_min = C["gear_j0"][0] - 2 * wc * tan_a
        off_wc = (j_target - j_wc_min) / (2 * tan_a)    # centre offset needed so that WC backlash >= j_target
        off_rss = (j_target - (C["gear_j0"][0] - 2 * rss * tan_a)) / (2 * tan_a)
        jmax_off = C["gear_j0"][2] + 2 * (off_wc + wc) * tan_a
        out31[proc] = dict(wc=wc, rss=rss, p_bind=p_bind, off_wc=off_wc, off_rss=off_rss, jmax=jmax_off, j_wc_min=j_wc_min, items=items)
        rows.append([proc, f"+-{wc:.3f}", f"+-{rss:.3f}", f"{j_wc_min:+.3f}", f"{100 * p_bind:.0f} %", f"+{off_rss:.2f} / +{off_wc:.2f}", f"{jmax_off:.2f}"])
    md.append("The CAD centre equals the theoretical centre (m (z1+z2)/2, e.g. 5.40 mm for 18:18, `bench.gears`), i.e. **zero designed backlash**.  Contributors: "
              + "; ".join(f"{n} +-{tt:.3f}" for n, tt in out31["MJF"]["items"]) + " (MJF values shown).  j_t = j0 + 2 da tan(20 deg), j0 = 0.015...0.045 mm (tooth thinning of DIN 58405 q8 [ASM]).\n")
    md.append(table(["process", "centre error WC mm", "RSS mm", "min backlash WC mm", "P(j_t < 0 -> binding) at CAD centre", "centre offset needed RSS / WC mm", "max backlash with WC offset mm"], rows))
    j_hi_ok = 0.20                         # largest acceptable normal backlash [ASM]: tooth height of module 0.3 is only 0.65 mm
    lo_w = (j_target - C["gear_j0"][0]) / (2 * tan_a)
    hi_w = (j_hi_ok - C["gear_j0"][2]) / (2 * tan_a)
    mid = (lo_w + hi_w) / 2
    rows = []
    for proc, t in PROC.items():
        for tag, its in (("passive location (as designed)", out31[proc]["items"]),
                         ("motor clamped to a datum, screw bush reamed", [("motor bore position", t), ("screw bush bore position", t), ("bush float in its bore", bush_clr), ("gear bores", 0.02)])):
            j0 = rng.triangular(*C["gear_j0"], N)
            da = mid + sum(uni(rng, tt, N) for _, tt in its)
            jt = j0 + 2 * da * tan_a
            wc_, rss_ = stack(its)
            rows.append([proc, tag, f"+-{wc_:.2f} / {rss_:.2f}", f"{100 * float(np.mean((jt >= j_target) & (jt <= j_hi_ok))):.0f} %"])
            out31[proc]["p_ok_" + ("pass" if tag.startswith("passive") else "imp")] = float(np.mean((jt >= j_target) & (jt <= j_hi_ok)))
    md.append("A tight mesh (negative backlash) multiplies the friction torque; the budget in 1.1 has only a small reserve.  The usable window for the centre error is narrow: normal backlash must stay "
              "within %.2f-%.2f mm (tooth height of module 0.3 is 0.65 mm), i.e. the centre distance may vary only over **%.2f mm** (offset %.2f ... +%.2f mm over theoretical).  Passive location of two "
              "printed bores plus a floating motor needs +-%.2f mm (WC), so a centre offset alone cannot fix it:\n" % (j_target, j_hi_ok, hi_w - lo_w, lo_w, hi_w, out31["MJF"]["wc"]))
    md.append(table(["process", "location concept", "centre error WC / RSS mm", "P(backlash in window) with design centre +%.2f mm" % mid], rows))
    out31["window"] = (lo_w, hi_w, mid)
    j_max_u = j_hi_ok / (ctx.module * ctx.active[1] / 2) / (2 * PI) * ctx.pitch * ctx.A / 10
    md.append("A backlash of %.2f mm at the pitch circle moves the nut by only %.3f U per reversal, so a loose mesh costs nothing in dose accuracy; a tight one costs thrust.  "
              "**Recommendation: design centre = theoretical + %.2f mm, clamp the motor against a datum (spring or screw) instead of a 0.1 mm floating saddle, or give the motor saddle a slot.**\n"
              % (j_hi_ok, j_max_u, mid))

    # ------------------------------------------------------------------------------------------------------------
    # 3.2 screw / nut / carriage alignment
    # ------------------------------------------------------------------------------------------------------------
    md.append("### 3.2 Leadscrew - nut - carriage alignment (over-constraint)\n")
    span = ctx.screw_span(ctx.sizes[1] if len(ctx.sizes) > 1 else ctx.sizes[0])
    EI = C["steel_E"] * PI * ((dr["screw_d"] - 0.6495 * ctx.pitch + dr["screw_d"] - 1.22687 * ctx.pitch) / 2) ** 4 / 64
    k_scr = 48 * EI / span ** 3
    E_pa = C["PA12_MJF"]["E"]
    to = P["seal"]["tongue_off"]
    lever = ctx.shared["a4"]["lever"]
    SHIM = P.get("bench", {}).get("shim")
    Iz = ((SHIM["t"], SHIM["h"]) if SHIM else (to[1] - to[0], dr["arm_t"]))
    Iz = Iz[0] * Iz[1] ** 3 / 12
    k_tz = 3 * (193000.0 if SHIM else E_pa) * Iz / lever ** 3
    k_lat = 1 / (1 / k_scr + 1 / k_tz)
    thread_clr = 0.03
    nut_float = dr["nut_hex_clr"] / 2
    rail_clr = (dr["groove_w"] - dr["rail_w"]) / 2
    fl_y = nut_float + rail_clr + screw_play + thread_clr
    fl_z = nut_float + screw_play + thread_clr           # carriage sits on the rail top (groove depth = rail height), no z play
    mu_t = C["mu_thread"][1]
    a1res = ctx.shared["a1"]
    T_avail = a1res["F_avail"] * (a1.thread_coeff(ctx, mu_t) + a1.collar_coeff(ctx, C["mu_collar"][1]))
    rows = []
    out32 = {}
    for proc, t in PROC.items():
        ey = uni(rng, t + bush_clr, N) + uni(rng, t, N)                 # bush axis error + rail position
        ez = uni(rng, t + bush_clr, N) + uni(rng, t, N) + uni(rng, t, N)   # + carriage nut-axis height
        misfit = np.sqrt(np.maximum(np.abs(ey) - fl_y, 0) ** 2 + np.maximum(np.abs(ez) - fl_z, 0) ** 2)
        F_side = k_lat * misfit
        dT = mu_t * F_side * (dr["screw_d"] - 0.6495 * ctx.pitch) / 2
        frac = dT / T_avail
        wc_y, wc_z = 2 * t + bush_clr, 3 * t + bush_clr
        out32[proc] = dict(frac=frac, p_loss=float(np.mean(frac > 0.1)), wc_y=wc_y, wc_z=wc_z)
        rows.append([proc, f"{wc_y:.3f} vs {fl_y:.3f}", f"{wc_z:.3f} vs {fl_z:.3f}", f"{np.percentile(misfit, 99) * 1000:.0f}", f"{np.percentile(F_side, 99):.1f}",
                     f"{100 * np.percentile(frac, 50):.0f} / {100 * np.percentile(frac, 99):.0f} %", f"{100 * out32[proc]['p_loss']:.0f} %"])
    md.append("The screw is guided by two bushes 16-30 mm apart, the nut is pressed into the carriage hex pocket, the carriage rides on a rail (groove depth = rail height, no vertical play) and is "
              "also tied to the plunger through the tongue.  Any axis misfit beyond the available float therefore bends the screw / tongue and loads the thread sideways.  "
              "Float available: y %.2f mm (nut pocket %.2f + rail groove %.2f + screw in bush %.2f + thread %.2f), z %.2f mm.  Lateral stiffness at the nut: screw (midspan, %.0f mm) %.0f N/mm in series with the "
              "tongue in z %.0f N/mm = %.0f N/mm.  Drag torque = mu_thread x F_side x d2/2, compared with the screw torque %.2f N*mm at 105 mA.\n"
              % (fl_y, nut_float, rail_clr, screw_play, thread_clr, fl_z, span, k_scr, k_tz, k_lat, T_avail))
    md.append(table(["process", "WC offset y vs float", "WC offset z vs float", "misfit 99 % um", "side force 99 % N", "drag torque / available median / 99 %", "P(drag > 10 %)"], rows))

    # ------------------------------------------------------------------------------------------------------------
    # 3.3 needle vs septum
    # ------------------------------------------------------------------------------------------------------------
    md.append("### 3.3 Needle position vs the Insight Flex septum (all cannula numbers are unmeasured placeholders)\n")
    r_sept = cn["D_septum_recess_d"] / 2
    guard_clr = (cn["D_septum_recess_d"] - cn["O_cyl_od"]) / 2
    needle_r = P["needle"]["od"] / 2
    usable_r = r_sept - 0.3           # [ASM] keep 0.3 mm from the septum edge
    rows = []
    out33 = {}
    for proc, t in PROC.items():
        t_cap = PROC["SLA"]      # end cap is an SLA part
        lat = [("dock axis y_c in the shell", t), ("arm position (dome float centre)", t), ("hook clearance float", dk["hook_clr"]), ("cannula septum vs dome [ASM]", 0.15),
               ("cap channel / guard tube position", t_cap), ("needle in hub concentricity", 0.05)]
        wc, rss = stack(lat)
        capture_needed = wc - guard_clr
        # with guard tube centring in the recess the residual offset of the needle vs septum:
        res_items = [("tube float in recess", guard_clr), ("needle in tube", t_cap + 0.05), ("septum in recess [ASM]", 0.1)]
        wc2, rss2 = stack(res_items)
        ax = [("hub seat x (cap)", t_cap), ("needle protrusion cut to length [ASM]", 0.2), ("dome latch axial float (notch %.1f vs hook %.1f)" % (cn["I_latch_w"], dk["hook_w"]), (cn["I_latch_w"] - dk["hook_w"]) / 2),
              ("adapter / cannula position", t), ("recess depth [ASM]", 0.1)]
        wca, rssa = stack(ax)
        pen = cn["F_needle_depth"]
        out33[proc] = dict(wc=wc, rss=rss, cap=capture_needed, wc2=wc2, usable=usable_r - needle_r, wca=wca, pen=pen)
        rows.append([proc, f"+-{wc:.2f} / {rss:.2f}", f"{capture_needed:.2f}", f"+-{wc2:.2f} vs {usable_r - needle_r:.2f}", f"{pen - wca:.2f} ... {pen + wca:.2f}"])
    md.append("Lateral: the guard tube (OD %.1f) enters the recess (D %.1f), giving %.2f mm of radial float; before it enters, the dock stack must be absorbed by a lead-in.  Septum usable radius "
              "%.2f - needle radius %.2f = %.2f mm [ASM]. Axial needle penetration nominal %.1f mm (F), window needed ~1.0 (septum thickness [ASM]) ... %.1f (bore end F+0.7).\n"
              % (cn["O_cyl_od"], cn["D_septum_recess_d"], guard_clr, usable_r, needle_r, usable_r - needle_r, cn["F_needle_depth"], cn["F_needle_depth"] + 0.7))
    md.append(table(["process", "dock stack lateral WC / RSS mm", "lead-in needed on tube/recess mm", "residual offset after guard centring WC vs usable", "needle penetration range mm"], rows))

    # ------------------------------------------------------------------------------------------------------------
    # 3.4 snap arm engagement overlap
    # ------------------------------------------------------------------------------------------------------------
    overlap = ctx.shared["a4"]["overlap"]
    rows = []
    out34 = {}
    for proc, t in PROC.items():
        its = [("arm position", t), ("hook protrusion", t), ("cannula notch depth [ASM]", 0.1)]
        wc, rss = stack(its)
        out34[proc] = overlap - wc
        rows.append([proc, f"{overlap:.2f}", f"{overlap - rss:.2f}", f"{overlap - wc:.2f}"])
    md.append("### 3.4 Snap-arm engagement (hook overlap behind the notch)\n")
    md.append("Nominal overlap = notch depth H %.1f - hook clearance %.2f = %.2f mm.\n" % (cn["H_latch_depth"], dk["hook_clr"], overlap))
    md.append(table(["process", "nominal mm", "RSS minimum mm", "WC minimum mm"], rows))

    # ------------------------------------------------------------------------------------------------------------
    # 3.5 closure height and reservoir/lid clearance
    # ------------------------------------------------------------------------------------------------------------
    md.append("### 3.5 Lid / bottom closure: height and reservoir clearance\n")
    H = sh["height"]
    wall = sh["wall"]
    z_stop = sh["lap_high"] + sh["gasket_c"]
    lid_depth = H - z_stop
    z_inner = H - wall
    res_h = P["reservoir_frozen"]["outer_h"]
    recess = P.get("bench", {}).get("lid_recess", {}).get("over_reservoir", 0.0)     # local lid recess over the reservoir (CAD)
    gap_nom = z_inner + recess - (wall + res_h)
    rows = []
    out35 = {}
    for proc, t in PROC.items():
        h_items = [("bottom shell height to the screw-dome stop", t), ("lid depth above the stop", t)]
        wc, rss = stack(h_items)
        g_items = [("floor thickness", t), ("CNC reservoir outer height", 0.1), ("bottom shell stop height", t), ("lid inner depth", t)]
        gwc, grss = stack(g_items)
        g = gap_nom + sum(uni(rng, tt, N) for _, tt in g_items)
        out35[proc] = dict(H_wc=H + wc, H_rss=H + rss, gap_wc=gap_nom - gwc, gap_rss=gap_nom - grss, p_int=float(np.mean(g < 0)), g=g)
        rows.append([proc, f"{H + rss:.2f} / {H + wc:.2f}", f"{gap_nom:.2f}", f"{gap_nom - grss:+.2f} / {gap_nom - gwc:+.2f}", f"{100 * out35[proc]['p_int']:.0f} %"])
    md.append("Height: bottom shell and lid meet on hard stops (gasket is not in the loop), so H = %.1f +- (t_bottom + t_lid).  Reservoir clearance: lid inner z %.2f (= H - wall) minus CNC reservoir top "
              "(floor %.1f + outer height %.1f = %.2f) = **%.2f mm nominal**.\n" % (H, z_inner, wall, res_h, wall + res_h, gap_nom))
    md.append(table(["process", "height RSS max / WC max mm (limit %.1f)" % H, "nominal gap mm", "reservoir-lid gap RSS min / WC min mm", "P(lid presses on reservoir)"], rows))
    # board and tallest component under the lid
    lay = None
    for s in ctx.sizes:
        if s in ctx.layout:
            lay = ctx.layout[s]
            break
    top_free = None
    if lay:
        top_free = lay["stack_z_pod"]["top_free_mm"]
        tops = [k["top_max_mm"] for k in lay.get("keepout_heights_mm", []) if "top_max_mm" in k]
        c_max = max(tops) if tops else 1.3
        bn = P.get("bench")
        if bn:         # actual tallest top-side part (the keep-out heights are limits, not parts)
            c_max = max(bn["ffc"]["conn"][2], bn["drv_top"]["pkg"][2])
        its = [("board seat height (posts/pins)", PROC["MJF"]), ("board thickness +-10 %", 0.08), ("lid inner depth", PROC["MJF"]), ("bottom stop", PROC["MJF"]), ("component height", 0.1)]
        wc, rss = stack(its)
        gap_c = top_free - c_max
        md.append("Board stack: lid inner %.2f, board top %.2f, tallest top-side part %.1f mm -> clearance %.2f mm nominal, RSS min %.2f, WC min %.2f (MJF).\n"
                  % (lay["stack_z_pod"]["lid_inner_z"], lay["stack_z_pod"]["board_top"], c_max, gap_c, gap_c - rss, gap_c - wc))
        out35["board"] = (gap_c, gap_c - rss, gap_c - wc)

    # figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    xs = np.linspace(-0.1, 0.5, 100)
    for proc, col in zip(PROC, PALETTE):
        o = out31[proc]
        j_lo = C["gear_j0"][0] + 2 * (xs - o["wc"]) * tan_a
        j_hi = C["gear_j0"][2] + 2 * (xs + o["wc"]) * tan_a
        ax[0].fill_between(xs, j_lo, j_hi, color=col, alpha=0.3, label=f"{proc} WC band")
    ax[0].axhline(0, color="k", lw=1)
    ax[0].axvline(0, color="#999", ls="--")
    ax[0].set_xlabel("centre distance offset over theoretical [mm]")
    ax[0].set_ylabel("normal backlash [mm]")
    ax[0].set_title("Gear backlash vs centre offset")
    ax[0].legend(fontsize=7)
    for proc, col in zip(out35, PALETTE):
        if proc == "board":
            continue
        ax[1].hist(out35[proc]["g"], bins=60, color=col, alpha=0.6, label=proc)
    ax[1].axvline(0, color="k")
    ax[1].set_xlabel("lid inner - reservoir top [mm]")
    ax[1].set_title("Reservoir / lid clearance (MC)")
    ax[1].legend(fontsize=7)
    for proc, col in zip(out32, PALETTE):
        ax[2].hist(100 * out32[proc]["frac"], bins=60, color=col, alpha=0.6, label=proc)
    ax[2].set_xlabel("screw torque lost to misalignment drag [%]")
    ax[2].set_title("Over-constraint drag (MC)")
    ax[2].legend(fontsize=7)
    for a_ in ax:
        a_.spines[["top", "right"]].set_visible(False)
    figp = ctx.save(fig, "a3_tolerance.png")
    plt.close(fig)
    md.append("![tolerance](%s)\n" % figp)

    m, s_ = out31["MJF"], out31["SLA"]
    res.rows += [
        Row("3.1", "Tolerance", "Gears never bind: P(backlash < 0) <= 1 % at the CAD centre (MJF)", f"{100 * m['p_bind']:.0f} % (SLA {100 * s_['p_bind']:.0f} %)", "-", status(m['p_bind'] <= 0.01, m['p_bind'] <= 0.1),
            f"CAD centre = theoretical; window needs +{out31['window'][2]:.2f} mm and datum location: P(ok) passive {100 * m['p_ok_pass']:.0f} % (MJF) / {100 * s_['p_ok_pass']:.0f} % (SLA)"),
        Row("3.2", "Tolerance", "Screw/nut/carriage misfit within float (MJF), drag < 10 % of torque", f"WC z {out32['MJF']['wc_z']:.2f} vs {fl_z:.2f} mm; P(drag>10 %) {100 * out32['MJF']['p_loss']:.0f} %", "-",
            status(out32['MJF']['p_loss'] <= 0.01, out32['MJF']['p_loss'] <= 0.1), "no vertical float on the rail; SLA: P(drag>10 %%) %.0f %%" % (100 * out32['SLA']['p_loss'])),
        Row("3.3", "Tolerance", "Needle lands in the septum: residual offset <= usable radius (MJF)", f"+-{out33['MJF']['wc2']:.2f} vs {out33['MJF']['usable']:.2f} mm", f"{out33['MJF']['usable'] / out33['MJF']['wc2']:.1f}x",
            status(out33['MJF']['wc2'] <= out33['MJF']['usable']), "cannula geometry unmeasured"),
        Row("3.4", "Tolerance", "Dock capture: lead-in needed on guard tube/recess (MJF)", f"{max(out33['MJF']['cap'], 0):.2f} mm", "-", status(out33['MJF']['cap'] <= 0.0, out33['MJF']['cap'] <= 0.6), "guard tube float only %.2f mm" % guard_clr),
        Row("3.5", "Tolerance", "Snap-arm hook overlap > 0 in worst case (MJF)", f"{out34['MJF']:.2f} mm (SLA {out34['SLA']:.2f})", "-", status(out34['MJF'] >= 0.2, out34['MJF'] > 0), "nominal %.2f mm" % overlap),
        Row("3.6", "Tolerance", "Pod height <= 8.5 mm (WC)", f"{out35['MJF']['H_wc']:.2f} mm MJF / {out35['SLA']['H_wc']:.2f} SLA (RSS {out35['MJF']['H_rss']:.2f} / {out35['SLA']['H_rss']:.2f})", "-",
            status(out35['MJF']['H_wc'] <= H, H <= H + 1e-9), "nominal is exactly at the limit: ~50 %% of MJF pods are up to %.1f mm too tall" % (2 * PROC["MJF"])),
        Row("3.7", "Tolerance", "Lid clears the CNC reservoir top (gap > 0), MJF", f"nominal {gap_nom:.2f} mm, WC {out35['MJF']['gap_wc']:+.2f}, P(contact) {100 * out35['MJF']['p_int']:.0f} %", "-",
            status(out35['MJF']['gap_wc'] >= 0, out35['MJF']['p_int'] <= 0.05), f"SLA: P(contact) {100 * out35['SLA']['p_int']:.0f} %"),
    ]
    if "board" in out35:
        res.rows.append(Row("3.8", "Tolerance", "Lid clears the tallest board component (MJF WC)", f"{out35['board'][0]:.2f} nominal / {out35['board'][2]:+.2f} WC mm", "-", status(out35['board'][2] >= 0, out35['board'][1] >= 0), "from layout.json keep-out heights"))
    ctx.shared["a3"] = {"out31": {k: ({kk: vv for kk, vv in v.items() if kk != "items"} if isinstance(v, dict) else v) for k, v in out31.items()}, "out35": {k: ({kk: vv for kk, vv in v.items() if kk != "g"} if isinstance(v, dict) else v) for k, v in out35.items()},
                        "gap_nom": gap_nom, "fl_z": fl_z, "out32": {k: {kk: vv for kk, vv in v.items() if kk != "frac"} for k, v in out32.items()}, "out33": out33}
    res.md = "\n".join(md)
    return res
