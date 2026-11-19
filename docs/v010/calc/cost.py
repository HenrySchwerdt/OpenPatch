"""Cost model for the v0.1.0 order against spec 1d (<= 200 EUR all-in per pump = one pod; MOQ overhead allocated to the first pump;
one-time tools excluded). All prices are ESTIMATES (ex VAT) unless the BOM marks WEB/BENCH; 19 % German import VAT is added on everything;
1 USD = 0.92 EUR (assumed, not looked up). Run: python3 cost.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bom

EUR, VAT = 0.92, 1.19


def order(n_boards, n_pods, n_inserts, mult=1.0, label=""):
    ext = len({b.lcsc for b in bom.BOM if b.jlc == "ext"})
    comp = sum(b.usd * b.qty for b in bom.BOM if b.jlc != "mech") * n_boards * 1.3
    items = {
        "PCB 4L 0.8 mm ENIG ~33x63 mm (5 pcs MOQ)": 26 * mult,
        "PCBA setup + stencil (2-sided, standard)": 28 * mult,
        f"extended-part loading ({ext} unique x 3 USD)": ext * 3,
        "SMT work": 3 + 1 * n_boards,
        f"electronic components ({n_boards} boards x BOM x 1.3 overbuy)": comp,
        "shipping JLC/LCSC": 30 * mult,
        "Li-Po cells: 3 candidate types (AliExpress)": 3 * 2.5 * max(1, n_boards // 2) + 8,
        "housings/lids/carriages/caps (JLC3DP PA12/SLA)": 15 * n_pods * mult,
        f"dock inserts x{n_inserts} (small prints, 8a)": n_inserts * 1.2 * mult,
        "CNC PP reservoir OP-100, qty 2 (PCBWay)": 60 * mult,
        "NFP motors (+1 spare) + shipping": 6.6 * (n_pods + 1) + 10,
        "GHW gear pairs + shipping from DE": 6.5 * 1.08 * (n_pods + 1) + 9,
        "rod, nuts, screws, magnets, needles, duckbills (sets)": 25 + 4 * n_pods,
        "silicone cast kit + septum sheet": 30,
        "Velcro, misc": 8,
    }
    sub = sum(items.values())
    tot_eur = sub * VAT * EUR
    return items, sub, tot_eur


def main():
    print("Per-pod marginal BOM (electronics components only, x1.0): %.2f USD" % sum(b.usd * b.qty for b in bom.BOM if b.jlc != "mech"))
    scen = [("A. minimum first pump (2 boards assembled, 1 pod, 12 inserts)", 2, 1, 12),
            ("B. recommended ONE order (5 boards, 4 pods, 12 inserts)", 5, 4, 12),
            ("C. B plus a 2nd order of 4 more pods, marginal (no CNC/stencil/inserts again)", None, None, None)]
    res = {}
    for name, nb, npod, ni in scen[:2]:
        for lab, mult in (("low", 0.8), ("mid", 1.0), ("high", 1.4)):
            items, sub, eur = order(nb, npod, ni, mult)
            res[(name, lab)] = (items, sub, eur)
        print("\n== " + name)
        for k, v in res[(name, "mid")][0].items():
            print(f"   {v:7.1f} USD  {k}")
        lo, mi, hi = (res[(name, l)][2] for l in ("low", "mid", "high"))
        print(f"   total incl. 19 % VAT: {lo:.0f} / {mi:.0f} / {hi:.0f} EUR (low/mid/high);  per pod: {lo/npod:.0f} / {mi/npod:.0f} / {hi/npod:.0f} EUR")
    # marginal pod: board+components share, housing, motor, gears, small parts, no CNC / stencil / inserts / silicone kit
    comp = sum(b.usd * b.qty for b in bom.BOM if b.jlc != "mech") * 1.3
    marg = comp + 26 / 5 + 8 + 15 + 6.6 + 7 + 4 + 5 + 6   # PCB share, SMT+loading share, housing, motor, gears, parts, cell, shipping share
    print(f"\n== marginal pod (everything above that scales per pod): {marg:.0f} USD = {marg * VAT * EUR:.0f} EUR incl. VAT")
    print("\nVerdict vs spec 1d (<= 200 EUR first pump with MOQ overhead allocated to it): scenario A FAILS (see numbers); scenario B passes only as an average over 4 pods;")
    print("the marginal pod is well below 200 EUR. One-time tools (programmer, balance, calipers) are excluded as in spec 1d.")


if __name__ == "__main__":
    main()
