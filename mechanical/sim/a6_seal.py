"""Analysis 6: plunger seal variants (FE bead model), tolerance Monte Carlo, guide (cocking) effect, alternative concepts."""
from __future__ import annotations

import numpy as np

import a1_drive as a1
from common import CONST as C, PALETTE, Ctx, Result, Row, status, table
from seal_model import SealDesign, cocking_factor, cup_lip, gent_E, hertz_line, monte_carlo

LEAK_MIN_MPA = 0.12            # mean contact pressure that gives >= 3x margin over 40 kPa suction (peak pressure is 1.3-1.5x the mean)
F_KIN_MAX, F_BRK_MAX = 1.5, 2.5


def run(ctx: Ctx) -> Result:
    res = Result("A6 Seal")
    P = ctx.P
    rng = np.random.default_rng(7)
    N = 20000
    md = ["## 6. Plunger seal variants (FE bead model, tolerance Monte Carlo)\n"]
    md.append("Model chain in `seal_model.py`: Gent E(Shore A); plane-strain Q4/B-bar FE of the cast ring in its groove (floor bonded, groove walls frictionless up to the core OD, bead top pushed onto the bore wall) "
              "-> line load F' [N/mm] and contact width; N = F' x perimeter x beads; kinetic force = mu x N; breakaway = k x kinetic; **cocking factor** 1/(1 - 2 mu_g e/L_g) from the eccentric push "
              "(tongue contact %.1f mm off the plunger axis, guide span %.1f mm).  The FE reproduces the confined-block closed form exactly and the Hertz thick-ring bound is its upper limit.  "
              "Monte Carlo: bore +0.05/0, printed cavity +-%.2f mm (diameter), shrink 0.1-0.3 %%, Shore A +-%.0f, mu_seal %s, breakaway %s, guide mu %s (PTFE-taped flanges) .\n"
              % (a1.design(ctx).e, a1.design(ctx).L_g, C["mould_tol_diam"], C["shore_scatter"], C["mu_seal_design"], C["breakaway"], C["mu_guide"]))
    rows = []
    stats = {}
    for key in ("S1", "S2", "T"):
        d = a1.design(ctx, key)
        for tag, mug in (("taped guide", C["mu_guide"]), ("bare guide", C["mu_guide_bare"])):
            m = monte_carlo(d, C, rng, N, mu_g=mug)
            nom = d.friction(C["mu_seal_design"][1], mu_g=mug[1])
            st = {"nom": nom, "seal_med": float(np.median(m["F_seal"])), "push_med": float(np.median(m["F_push"])), "push_p95": float(np.percentile(m["F_push"], 95)),
                  "p_kin": float(np.mean(m["F_push"] <= F_KIN_MAX)), "p_brk": float(np.mean(m["F_break"] <= F_BRK_MAX)),
                  "p_leak_ok": float(np.mean((m["p_mean"] >= LEAK_MIN_MPA) & (m["delta"] > 0))), "p_clear": float(np.mean(m["delta"] <= 0)),
                  "pmean_med": float(np.median(m["p_mean"])), "b": float(np.median(m["b"]))}
            stats[(key, tag)] = st
            rows.append([key, tag, f"{d.delta():.3f}", f"{nom['Fp']:.3f}", f"{nom['b']:.2f}", f"{1e3 * nom['p_mean']:.0f}", f"{nom['F_seal']:.2f}", f"{nom['f_cock']:.2f}", f"{nom['F_push']:.2f}",
                         f"{st['push_med']:.2f} ({st['push_p95']:.2f})", f"{100 * st['p_kin']:.0f} %", f"{100 * st['p_brk']:.0f} %", f"{100 * st['p_leak_ok']:.0f} %"])
    md.append("### 6.1 Variants: nominal values (mu %.2f, bore +0.025, Shore %.0f) and Monte Carlo (N = %d)\n" % (C["mu_seal_design"][1], P["seal"]["variants"]["S1"]["shore_target"], N))
    md.append(table(["variant", "guide", "net squeeze/side mm", "F' N/mm", "contact b mm", "mean contact p kPa", "F seal alone N", "cocking x", "F at plunger N", "MC median (95 %) N",
                     "P(F <= 1.5 N)", "P(breakaway <= 2.5 N)", "P(leak-tight: p >= 120 kPa)"], rows))

    # reference: old design and alternative concepts (analytic)
    so = a1.seal_friction(ctx, dbore=0.0, mu=C["mu_seal"][1], mu_g=C["mu_guide_bare"][1], legacy=True)
    per = a1.design(ctx).perim()
    E55 = gent_E(55.0)
    mu_n = C["mu_seal_design"][1]
    alt = []
    f_o = hertz_line(E55, 0.05) * per * mu_n
    alt.append(["O-ring cord d1.0 spliced (CA), Shore 55, 0.05 squeeze (Hertz bound)", f"{f_o:.2f}", f"{hertz_line(E55, 0.05) * 1e3 / 0.45:.0f}", "needs a 1.1 mm wide groove (not the shared core), cord is round-spliced: joint = leak/friction bump; stiffer", "no"])
    c1 = cup_lip(gent_E(30), 0.3, 0.9, 0.1, 30.0)
    alt.append(["pair of back-to-back thin cup lips (t 0.3, L 0.9), pressure-energised", f"{c1 * per * mu_n:.2f} at 30 kPa", "3 unpressurised, >= 30 under load", "lowest friction, seals only when energised (bubbles/air at < 5 kPa); needs a 1 mm free skirt: not castable in the shared groove", "Rev B"])
    alt.append(["PTFE-tape jacket on the S1 bead (0.1 mm skived tape, one overlap)", f"{0.10 * stats[('S1', 'taped guide')]['nom']['N']:.2f}", f"{1e3 * stats[('S1', 'taped guide')]['nom']['p_mean']:.0f}", "mu 0.10 and no stick-slip; seam crosses the contact line (leak path), tape creep; test as an add-on to S1", "option"])
    alt.append(["rolling diaphragm (stadium 16 x 5)", "~0.1-0.3 (rolling resistance)", "-", "needs >= 0.8 mm radial convolution gap each side (piston 14.4 x 3.4, -25 % area), a clamp ring in the frozen CNC part, a cast stadium diaphragm; not a hobby part", "no"])
    alt.append(["superseded: 2 full-width 0.8 mm bands, 0.13 squeeze, Shore 40", f"{so['F_seal']:.1f} (x{so['f_cock']:.1f} cocking = {so['F']:.0f})", "975", "FE with the groove walls; the earlier block model said 9.6 N", "replaced"])
    md.append("### 6.2 Alternative concepts (nominal, analytic or FE)\n")
    md.append(table(["concept", "F kinetic seal alone N (mu %.2f)" % mu_n, "contact pressure kPa", "remarks", "taken"], alt))

    # guide effect
    d1 = a1.design(ctx, "S1")
    rows = []
    for tag, mug in (("PTFE tape + oil", 0.10), ("bare resin, oil wetted", 0.15), ("bare resin, damp", 0.25), ("bare resin, dry", 0.35)):
        fc = cocking_factor(mug, d1.e, d1.L_g)
        rows.append([tag, f"{mug:.2f}", f"{2 * mug * d1.e / d1.L_g:.2f}", "JAM" if fc == float('inf') or fc > 8 else f"{fc:.2f}", "JAM" if fc > 8 else f"{d1.friction(mu_n, mu_g=mug)['F_seal'] * fc:.2f}"])
    md.append("### 6.3 Guide friction and the eccentric push (S1)\n")
    md.append("The carriage tongue pushes %.1f mm off the plunger axis, so the core is pressed against the bore by a couple; the push needed is F_seal / (1 - 2 mu_g e / L_g) and the plunger jams when 2 mu_g e / L_g >= 1 "
              "(mu_g >= %.2f here).  This is why the core flanges are turned down for a PTFE tape wrap (`seal.guide.tape_recess`).  The robust fix is a central push (1.2 mm stainless blade reaching the plunger centre, slot +0.6 mm): "
              "cocking disappears (listed in `SEAL-AND-DEAD-VOLUME.md`, not applied).\n" % (d1.e, d1.L_g / (2 * d1.e)))
    md.append(table(["guide condition", "mu_g", "2 mu_g e / L_g", "cocking factor", "F at plunger N (S1, mu 0.22)"], rows))

    # figure
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    dl = np.linspace(0.005, 0.09, 40)
    for key, col in (("S1", PALETTE[0]), ("S2", PALETTE[2]), ("T", PALETTE[1])):
        d = a1.design(ctx, key)
        fp = [float(d.line_load(x, d.shore)[0]) * d.perim() * d.n * mu_n for x in dl]
        ax[0].plot(dl, fp, color=col, label=key)
    ax[0].axhline(F_KIN_MAX, color="k", ls="--", lw=1)
    ax[0].set_xlabel("net squeeze per side [mm]")
    ax[0].set_ylabel("kinetic friction, seal alone [N] (mu %.2f)" % mu_n)
    ax[0].set_title("Friction vs squeeze (Shore A 30)")
    ax[0].legend(fontsize=8)
    m = monte_carlo(d1, C, rng, N)
    ax[1].hist(m["F_push"], bins=np.linspace(0, 6, 60), color=PALETTE[0], alpha=0.8)
    ax[1].axvline(F_KIN_MAX, color="k", ls="--", lw=1)
    ax[1].set_xlabel("kinetic force at the plunger [N], S1, taped guide")
    ax[1].set_title("Monte Carlo (tolerances, mu, Shore)")
    for a_ in ax:
        a_.spines[["top", "right"]].set_visible(False)
    figp = ctx.save(fig, "a6_seal.png")
    plt.close(fig)
    md.append("![seal](%s)\n" % figp)

    act = P["seal"]["active_variant"]
    others = [k for k in ("S1", "S2", "T") if k != act]
    s1 = stats[(act, "taped guide")]
    s1b = stats[(act, "bare guide")]
    res.rows += [
        Row("6.1", "Seal", f"Active seal {act}: kinetic friction, seal alone <= 1.5 N (nominal, mu 0.22 oil-wetted)", f"{s1['nom']['F_seal']:.2f} N", f"{F_KIN_MAX / s1['nom']['F_seal']:.2f}x", status(s1["nom"]["F_seal"] <= F_KIN_MAX, s1["nom"]["F_seal"] <= 2.0), "FE bead model"),
        Row("6.2", "Seal", f"{act} force at the plunger incl. guide friction <= 1.5 N, P (MC, taped guide)", f"{s1['nom']['F_push']:.2f} N nominal, P = {100 * s1['p_kin']:.0f} %", f"{F_KIN_MAX / s1['nom']['F_push']:.2f}x",
            status(s1["p_kin"] >= 0.9, s1["p_kin"] >= 0.5), "cocking x%.2f; bare guide: P = %.0f %%" % (s1["nom"]["f_cock"], 100 * s1b["p_kin"])),
        Row("6.3", "Seal", f"{act} breakaway <= 2.5 N, P (MC, taped guide)", f"P = {100 * s1['p_brk']:.0f} %", "-", status(s1["p_brk"] >= 0.9, s1["p_brk"] >= 0.5), "breakaway factor 1.2-2.5 (dwell); needs the pull test"),
        Row("6.4", "Seal", f"{act} leak-tight to >= 30 kPa / 40 kPa suction: mean contact pressure >= 120 kPa, P (MC)", f"P = {100 * s1['p_leak_ok']:.0f} %, median {1e3 * s1['pmean_med']:.0f} kPa", "-", status(s1["p_leak_ok"] >= 0.95, s1["p_leak_ok"] >= 0.8),
            "P(no interference) = %.1f %%" % (100 * s1["p_clear"])),
    ]
    for n_, k in enumerate(others, 5):
        st = stats[(k, "taped guide")]
        res.rows.append(Row(f"6.{n_}", "Seal", f"Mould variant {k}: force at the plunger / P(F <= 1.5 N) / P(leak-tight)", f"{st['nom']['F_push']:.2f} N / {100 * st['p_kin']:.0f} % / {100 * st['p_leak_ok']:.0f} %", "-", "INFO", P["seal"]["variants"][k]["role"][:70]))
    ctx.shared["a6"] = {"stats": {f"{k[0]}|{k[1]}": {kk: vv for kk, vv in v.items() if kk != "nom"} | {"nom": {a: float(b) for a, b in v["nom"].items()}} for k, v in stats.items()}, "old": so}
    res.md = "\n".join(md)
    return res
