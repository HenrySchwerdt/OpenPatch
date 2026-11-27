#!/usr/bin/env python3
"""Footprints of the cart A board that are not in the KiCad / V010 libraries -> cart/a/CARTA.pretty (plain python3).

TEST PROJECT, water only. Land patterns = the LCSC/EasyEDA footprint of the ordered part (the one JLC places against), checked against
the manufacturer drawing; origins = the EasyEDA origin, so the CPL needs no origin shift (gen_cart_a_rot_offsets.py measures it anyway).
  * SW_SPVS410100   Alps SPVS410100 (C160857) detector switch, 3.5 x 3.3 x 1.0, lever out of the local -y edge (body edge y -1.32,
                    lever tip y -3.10 at x +0.10 free; datasheet: tip 2.55 from the pivot line y -0.556, ON 1.5, total travel 1.0 from it,
                    i.e. ON at local y -2.056, total travel at y -1.556); pads 1 / 2 = COM / NO, 3 / 4 = frame legs (no net),
                    2 x d0.7 NPTH for the location lugs at x +-0.8, y -0.556 (Alps land drawing 1.6 apart).
  * SW_SKSGACE010   Alps SKSGACE010 (C127465) top-push tact 3.0 x 2.7 x 1.4, pads 1/3 (one contact, local -y row) and 2/4 (other),
                    0.65 x 0.6 at x +-1.55, y +-0.85 (Alps land: 3.75 / 2.5 x 2.25 / 1.1); no ground terminal on the ACE type.
  * IDC_AVX9175_2P  Kyocera AVX 9175 2-way IDC (C7434809 = 009175002702996, capped 9175-700 type; AVX: "identical PCB footprint to the
                    standard 9175"), 5.0 x 2.5 x 3.45 body (+ cap), pitch 2.5 along local x, wires along local y; split SMT tails = two
                    1.45 x 0.9 pads per contact (EasyEDA 009175002701106 land, the same series).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "CARTA.pretty")


def rect_lines(x0, y0, x1, y1, layer, w):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return "".join('  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %.2f) (type solid)) (layer "%s"))\n'
                   % (*pts[i], *pts[(i + 1) % 4], w, layer) for i in range(4))


def poly_lines(pts, layer, w):
    return "".join('  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %.2f) (type solid)) (layer "%s"))\n'
                   % (*a, *c, w, layer) for a, c in zip(pts, pts[1:]))


def pad(num, x, y, w, h):
    return '  (pad "%s" smd rect (at %.3f %.3f) (size %.3f %.3f) (layers F.Cu F.Paste F.Mask))\n' % (num, x, y, w, h)


def npth(x, y, d):
    return '  (pad "" np_thru_hole circle (at %.3f %.3f) (size %.3f %.3f) (drill %.3f) (layers *.Cu *.Mask))\n' % (x, y, d, d, d)


def write(name, descr, body, ref_y, val_y):
    s = '(footprint "%s" (version 20240108) (generator "cart_a_gen")\n  (layer "F.Cu")\n  (descr "%s")\n  (attr smd)\n' % (name, descr)
    s += '  (fp_text reference "REF**" (at 0 %.2f) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))\n' % ref_y
    s += '  (fp_text value "%s" (at 0 %.2f) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))\n' % (name, val_y)
    s += body + ")\n"
    open(os.path.join(LIB, name + ".kicad_mod"), "w").write(s)


def main():
    os.makedirs(LIB, exist_ok=True)
    # ---- Alps SPVS410100
    b = pad("1", 1.825, 0.854, 0.85, 1.10) + pad("2", -1.825, 0.855, 0.85, 1.10)
    b += pad("3", 2.000, -0.855, 0.60, 0.55) + pad("4", -2.000, -0.556, 0.60, 0.55)
    b += npth(0.8, -0.556, 0.7) + npth(-0.8, -0.556, 0.7)
    b += rect_lines(-1.78, -1.32, 1.72, 1.98, "F.Fab", 0.1)
    b += poly_lines([(-1.52, -1.32), (-0.50, -2.50), (0.10, -3.10), (0.10, -1.37)], "F.Fab", 0.1)
    crt = [(-2.55, -1.60), (-1.80, -1.60), (-1.80, -3.40), (0.45, -3.40), (0.45, -1.60), (2.55, -1.60), (2.55, 2.13), (-2.55, 2.13)]
    b += poly_lines(crt + crt[:1], "F.CrtYd", 0.05)          # one closed courtyard incl. the lever
    b += poly_lines([(-1.78, 1.98), (1.72, 1.98)], "F.SilkS", 0.12)
    write("SW_SPVS410100", "Alps SPVS410100 (LCSC C160857) detector switch 3.5 x 3.3 x 1.0, N/O, lever out of local -y (tip y -3.10 free, "
          "ON y -2.06, total travel y -1.56, pivot line y -0.556); pads 1 COM, 2 NO, 3/4 frame legs; 2 x d0.7 NPTH location lugs; "
          "land = EasyEDA C160857 (Alps land drawing 4.5/2.8, 3.4)", b, 2.9, -3.9)
    # ---- Alps SKSGACE010
    b = pad("1", -1.55, -0.85, 0.65, 0.60) + pad("2", -1.55, 0.85, 0.65, 0.60) + pad("3", 1.55, -0.85, 0.65, 0.60) + pad("4", 1.55, 0.85, 0.65, 0.60)
    b += rect_lines(-1.50, -1.35, 1.50, 1.35, "F.Fab", 0.1)
    b += '  (fp_circle (center 0 0) (end 0.85 0) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))\n'
    b += rect_lines(-2.13, -1.60, 2.13, 1.60, "F.CrtYd", 0.05)
    b += poly_lines([(-1.0, -1.45), (1.0, -1.45)], "F.SilkS", 0.12) + poly_lines([(-1.0, 1.45), (1.0, 1.45)], "F.SilkS", 0.12)
    write("SW_SKSGACE010", "Alps SKSGACE010 (LCSC C127465) top-push tact 3.0 x 2.7 x 1.4, 1.6 N; pads 1+3 one contact, 2+4 the other "
          "(Alps circuit diagram), land 0.65 x 0.6 at +-1.55 / +-0.85 (Alps 3.75/2.5 x 2.25/1.1, EasyEDA C127465)", b, -2.1, 2.1)
    # ---- AVX 9175 2-way IDC
    b = pad("1", -1.885, -0.725, 1.45, 0.90) + pad("1", -0.615, 0.725, 1.45, 0.90) + pad("2", 0.615, -0.725, 1.45, 0.90) + pad("2", 1.885, 0.725, 1.45, 0.90)
    b += rect_lines(-2.50, -1.25, 2.50, 1.25, "F.Fab", 0.1)
    b += poly_lines([(-1.25, -1.6), (-1.25, 1.6)], "F.Fab", 0.08) + poly_lines([(1.25, -1.6), (1.25, 1.6)], "F.Fab", 0.08)
    b += rect_lines(-2.85, -1.50, 2.85, 1.50, "F.CrtYd", 0.05)
    write("IDC_AVX9175_2P", "Kyocera AVX 9175 2-way IDC wire-to-board (LCSC C7434809 009175002702996, 9175-700 capped type, same footprint "
          "as 9175-000), 26-28 AWG, insulation 0.7-1.0, body 5.0 x 2.5 x 3.45 + cap; contacts at x -1.25 (1) / +1.25 (2), wires along "
          "local y; split SMT tails = 2 pads per contact (EasyEDA 009175002701106 land)", b, -2.1, 2.1)
    print("written", sorted(os.listdir(LIB)))


if __name__ == "__main__":
    main()
