#!/usr/bin/env python3
"""Independent check of cart/a/jlc/CPL-jlcpcb.csv (copy of ../verify_cpl.py, B) (KiCad python): place the official LCSC/EasyEDA footprint of every CPL row the way JLC does
(at Mid X / Mid Y, rotated by the CPL Rotation; bottom rows mirrored as seen from the top) and compare every pad, by pad number, with the
pad of our board. usage: kpy verify_cpl_a.py board.kicad_pcb jlc_dir   -> jlc_dir/CPL-VERIFY.md, exit 1 if any part is off by > TOL or fits better turned by 180.

Conventions (JLC): CPL frame = KiCad pos file (x right, y UP); rotation counter-clockwise seen from the side the part sits on; a bottom
part is the top placement seen through the board, i.e. mirrored in x as seen from the top. The rule under test (export_cart_jlc.py) is
top = KiCad - delta, bottom = 180 - KiCad - delta (export_cart_a_jlc.py); this script does not use delta at all, so it checks that rule.
The 180-degree twin of every row is scored too: a symmetric land pattern (2-pad passives) passes both ways and is reported as such."""
import csv
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_cart_a_rot_offsets as GR  # noqa: E402  (EasyEDA pad reader with the local cache)

T = pcbnew.ToMM
TOL = 0.45          # land-pattern differences between our footprint and the LCSC one reach 0.425 mm (FUET-4020, jlc_rot_offsets maxdev); a wrong orientation is >= 0.9 mm


def rot(x: float, y: float, a: float) -> tuple:
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return x * c - y * s, x * s + y * c


def place(lp: list, x0: float, y0: float, a: float, bottom: bool) -> list:
    out = []
    for n, lx, ly in lp:
        px, py = rot(lx, -ly, a)            # EasyEDA y down -> y up, then CCW rotation
        if bottom:
            px = -px                         # seen from the top, a bottom part is mirrored in x
        out.append((n, x0 + px, y0 + py))
    return out


def main() -> None:
    b = pcbnew.LoadBoard(sys.argv[1])
    jdir = sys.argv[2]
    parts = {p["ref"]: p for p in json.load(open(os.path.join(HERE, "netlist_cart_a.json")))}
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    rows, worst = [], 0.0
    for r in csv.DictReader(open(os.path.join(jdir, "CPL-jlcpcb.csv"))):
        ref = r["Designator"]
        lcsc = parts[ref]["lcsc"]
        alias = GR.ALIAS.get(lcsc, {})
        _, lp = GR.easyeda_pads(lcsc)
        lp = [(alias.get(n, n), x, y) for n, x, y in lp]
        ours = [(alias.get(p.GetNumber(), p.GetNumber()), T(p.GetPosition().x), -T(p.GetPosition().y)) for p in fps[ref].Pads() if p.GetNumber()]
        bottom = r["Layer"] == "Bottom"

        def dev(a: float) -> float:
            th = place(lp, float(r["Mid X"]), float(r["Mid Y"]), a, bottom)
            d = 0.0
            for n, x, y in ours:
                c = [math.hypot(x - tx, y - ty) for m, tx, ty in th if m == n]
                if c:
                    d = max(d, min(c))
            return d
        a = float(r["Rotation"])
        d0, d180 = dev(a), dev(a + 180)
        worst = max(worst, d0)
        rows.append((ref, lcsc, r["Layer"], a, d0, d180))
    with open(os.path.join(jdir, "CPL-VERIFY.md"), "w") as f:
        f.write("# CPL verification (verify_cpl.py): official LCSC footprint placed at the CPL row vs our pads\n\n")
        f.write("Bottom rows are mirrored as seen from the top. 'max dev' = worst pad-centre distance by pad number at the CPL rotation; "
                "'at +180' = the same with the rotation turned by 180 (a large value there proves the orientation is unambiguous).\n\n")
        f.write("| Ref | LCSC | Side | CPL rot | max dev (mm) | at +180 (mm) | verdict |\n|---|---|---|---|---|---|---|\n")
        for ref, lc, side, a, d0, d180 in sorted(rows, key=lambda t: (t[2], t[0])):
            v = "OK" if d0 <= TOL and d0 < d180 else "**WRONG**"
            if d0 <= TOL and d180 <= TOL:
                v = "OK (symmetric pattern)"
            f.write("| %s | %s | %s | %g | %.3f | %.3f | %s |\n" % (ref, lc, side, a, d0, d180, v))
    bad = [r for r in rows if r[4] > TOL or (r[5] < r[4] and r[5] > TOL)]
    print("CPL verify: %d rows, worst %.3f mm, %d wrong -> %s" % (len(rows), worst, len(bad), os.path.join(jdir, "CPL-VERIFY.md")))
    for r in bad:
        print("  WRONG", r)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
