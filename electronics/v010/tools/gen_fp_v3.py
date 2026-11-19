#!/usr/bin/env python3
"""Generate the v3 custom footprints into footprints/V010.pretty (UFQFPN-20 supervisor, board-to-board pad rows, ISP1807 copy)."""
import os, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
PRETTY = os.path.join(HERE, "..", "footprints", "V010.pretty")


def head(name, descr):
    return ['(footprint "%s" (version 20240108) (generator "v010_gen")' % name, '  (layer "F.Cu")', '  (descr "%s")' % descr, '  (attr smd)',
            '  (fp_text reference "REF**" (at 0 -2) (layer "F.SilkS") (effects (font (size 0.6 0.6) (thickness 0.1))))',
            '  (fp_text value "%s" (at 0 2) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))' % name]


def rect(x0, y0, x1, y1, layer="F.CrtYd", w=0.05):
    return ['  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %.2f) (type solid)) (layer "%s"))' % (a + (w, layer)) for a in
            ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0))]


def pad(n, x, y, w, h, shape="rect", extra=""):
    return '  (pad "%s" smd %s (at %.4f %.4f) (size %.3f %.3f) (layers F.Cu F.Paste F.Mask)%s)' % (n, shape, x, y, w, h, extra)


def ufqfpn20():
    L = head("UFQFPN-20_3x3_P0.5", "ST UFQFPN20 3x3x0.55 mm P0.5, EP 1.6x1.6 (pin 21). Land pattern derived from the usual 0.25x0.6 / 3.0 mm QFN rule: VERIFY against ST DS13866 package drawing")
    c, ln, wd = 1.3, 0.6, 0.25
    # pin 1 top-left, counter-clockwise: left side top->bottom 1-5, bottom left->right 6-10, right bottom->top 11-15, top right->left 16-20
    ys = [-1.0, -0.5, 0, 0.5, 1.0]
    for i in range(5):
        L.append(pad(1 + i, -c, ys[i], ln, wd))
        L.append(pad(6 + i, ys[i], c, wd, ln))
        L.append(pad(11 + i, c, -ys[i], ln, wd))
        L.append(pad(16 + i, -ys[i], -c, wd, ln))
    L.append(pad(21, 0, 0, 1.6, 1.6))
    L += rect(-1.9, -1.9, 1.9, 1.9)
    L += rect(-1.5, -1.5, 1.5, 1.5, "F.Fab", 0.1)
    L.append('  (fp_circle (center -1.75 -1.55) (end -1.65 -1.55) (stroke (width 0.1) (type solid)) (fill yes) (layer "F.SilkS"))')
    return L + [")"]


def b2b(name, mirror, npairs=16, pitch=0.8, w=0.55, h=1.0, gap=1.1):
    L = head(name, "board-to-board bare pad rows (elastomeric strip / spring contacts, mating pad pattern is the X mirror image on the other board)")
    s = -1 if mirror else 1
    for i in range(npairs):
        x = s * (i - (npairs - 1) / 2) * pitch
        L.append(pad(1 + i, x, -(gap + h) / 2, w, h))
        L.append(pad(1 + npairs + i, x, (gap + h) / 2, w, h))
    W = npairs * pitch / 2 + 0.4
    return L + rect(-W, -(gap + 2 * h) / 2 - 0.3, W, (gap + 2 * h) / 2 + 0.3) + [")"]


def row(name, n, pitch=0.8, w=0.5, h=1.2):
    L = head(name, "bare pad row for an FFC (ACF/elastomer) link to the SENSOR board: pad order = SENSOR J3S pins 1..%d" % n)
    for i in range(n):
        L.append(pad(1 + i, (i - (n - 1) / 2) * pitch, 0, w, h))
    W = n * pitch / 2 + 0.3
    return L + rect(-W, -h / 2 - 0.3, W, h / 2 + 0.3) + [")"]


def tp(name, d):
    L = head(name, "round test pad D%.1f mm (SMD)" % d)
    L.append('  (pad "1" smd circle (at 0 0) (size %.2f %.2f) (layers F.Cu F.Paste F.Mask))' % (d, d))
    return L + rect(-d / 2 - 0.1, -d / 2 - 0.1, d / 2 + 0.1, d / 2 + 0.1) + [")"]


for name, L in (("UFQFPN-20_3x3_P0.5", ufqfpn20()), ("B2B_Pads_2x16_P0.8", b2b("B2B_Pads_2x16_P0.8", False)), ("B2B_Pads_2x16_P0.8_M", b2b("B2B_Pads_2x16_P0.8_M", True)),
                ("SENSOR_Pads_9_P0.8", row("SENSOR_Pads_9_P0.8", 9)), ("TP_Pad_D0.8", tp("TP_Pad_D0.8", 0.8))):
    open(os.path.join(PRETTY, name + ".kicad_mod"), "w").write("\n".join(L) + "\n")
shutil.copy(os.path.join(HERE, "..", "..", "kicad", "OpenPatch.pretty", "ISP1807.kicad_mod"), os.path.join(PRETTY, "ISP1807.kicad_mod"))
print("footprints written")
