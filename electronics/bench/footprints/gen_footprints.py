#!/usr/bin/env python3
"""Generate the custom footprints of the bench boards into Bench.pretty (plain python3).

E73-2G4M08S1C / E73-2G4M08S1CX : Ebyte datasheet page 3 (mechanical drawing), PCB view (seen from above = mirror of the 'Bottom pad' drawing).
Buzzer MLT-8530               : Jiangsu Huaneng datasheet page 2.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Bench.pretty")


def pad(num, x, y, w, h, kind="smd", layers="F.Cu F.Paste F.Mask", shape="rect", extra=""):
    return (f'  (pad "{num}" {kind} {shape} (at {x:.4f} {y:.4f}) (size {w:.4f} {h:.4f}) (layers {layers}){extra})')


def line(x1, y1, x2, y2, layer="F.SilkS", w=0.12):
    return f'  (fp_line (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) (stroke (width {w}) (type solid)) (layer "{layer}"))'


def rect(x1, y1, x2, y2, layer, w=0.05):
    return "\n".join([line(x1, y1, x2, y1, layer, w), line(x2, y1, x2, y2, layer, w), line(x2, y2, x1, y2, layer, w), line(x1, y2, x1, y1, layer, w)])


def write(name, descr, body):
    txt = f'(footprint "{name}" (version 20240108) (generator "bench_gen")\n  (layer "F.Cu")\n  (descr "{descr}")\n'
    txt += '  (attr smd)\n'
    txt += '  (fp_text reference "REF**" (at 0 -11) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
    txt += '  (fp_text value "' + name + '" (at 0 11) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))\n'
    txt += body + "\n)\n"
    open(os.path.join(OUT, name + ".kicad_mod"), "w").write(txt)


def e73():
    W, H, P = 13.0, 18.0, 1.27
    cx, cy = W / 2, H / 2
    pads = []
    EXT = 0.65          # land extends 0.65 mm outside the module edge (castellation fillet), datasheet 0.65 dim
    LEN = 1.0           # module pad length 1.0 (datasheet bottom pad), width 0.8
    PW = 0.8
    L = LEN + EXT
    # PCB view (from above) is the datasheet "top view": pins 1..10 on the right edge (1 bottom), 11..25 along the top (11 at right),
    # 26..43 on the left edge (26 top). Datasheet footprint drawing is the mirror image (module bottom view): x -> W-x.
    def X(u):  # datasheet bottom-view u -> PCB top-view x relative to centre
        return (W - u) - cx
    for k in range(1, 11):                      # right edge in PCB view (pad 10 at top, pad 1 at bottom)
        v = 2.60 + (10 - k) * P
        pads.append(pad(k, W / 2 - LEN / 2 + EXT / 2, v - cy, L, PW))
    for j, n in enumerate(range(11, 26, 2)):    # outer top row: 11,13,...,25  (datasheet u = 2.06 + j*1.27)
        pads.append(pad(n, X(2.06 + j * P), -cy + LEN / 2 - EXT / 2, PW, L))
    for j, n in enumerate(range(12, 25, 2)):    # inner row 12,...,24
        pads.append(pad(n, X(2.06 + P / 2 + j * P), 2.60 - cy, PW, PW))
    for i, n in enumerate([26, 27, 29, 31, 33, 35, 37, 39, 41, 43]):   # left edge outer
        v = 2.60 + i * P
        pads.append(pad(n, -(W / 2 - LEN / 2 + EXT / 2), v - cy, L, PW))
    for i, n in enumerate(range(28, 43, 2)):    # left inner column, 2.0 mm from the edge
        v = 2.60 + P / 2 + P + i * P
        pads.append(pad(n, 2.0 - cx, v - cy, PW, PW))
    body = "\n".join(pads)
    body += "\n" + rect(-cx, -cy, cx, cy, "F.SilkS", 0.12)
    body += "\n" + rect(-cx - 0.7, -cy - 0.7, cx + 0.7, cy + 0.7, "F.CrtYd", 0.05)
    body += "\n" + f'  (fp_text user "ANT END" (at 0 {cy - 1.7:.2f}) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))'
    write("Ebyte_E73-2G4M08S1C_13x18", "Ebyte E73 module 13x18 mm, 43 castellated pads, PCB (top) view, antenna end at +y", body)


def buzzer():
    # bottom view in datasheet: + lead top-left, - lead bottom-left, dummy pads right. Body 8.5x8.5, pad inner gap 5.5.
    pads = [pad(1, -3.5, -3.5, 1.9, 1.9), pad(2, -3.5, 3.5, 1.9, 1.9), pad(3, 3.5, -3.5, 1.9, 1.9), pad(4, 3.5, 3.5, 1.9, 1.9)]
    body = "\n".join(pads) + "\n" + rect(-4.25, -4.25, 4.25, 4.25, "F.SilkS", 0.12)
    body += "\n" + rect(-4.6, -4.6, 4.6, 4.6, "F.CrtYd", 0.05)
    body += '\n  (fp_text user "+" (at -4.9 -3.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))'
    write("Buzzer_MLT-8530_8.5x8.5", "Huaneng MLT-8530 SMD magnetic transducer, pad 1 = +, 2 = -, 3/4 dummy anchor pads", body)


def x2son():
    # TI DMR0004B (X2SON-4, 1.1 x 1.4 mm) example land pattern, DRV5032 datasheet Figure "EXAMPLE BOARD LAYOUT": pads 0.22 x 0.40, pitch 0.5, rows 1.4 apart, thermal pad 0.8 x 0.6
    pads = [pad(1, -0.25, -0.70, 0.22, 0.40, shape="roundrect", extra=" (roundrect_rratio 0.2)"),
            pad(2, -0.25, 0.70, 0.22, 0.40, shape="roundrect", extra=" (roundrect_rratio 0.2)"),
            pad(3, 0.25, 0.70, 0.22, 0.40, shape="roundrect", extra=" (roundrect_rratio 0.2)"),
            pad(4, 0.25, -0.70, 0.22, 0.40, shape="roundrect", extra=" (roundrect_rratio 0.2)"),
            pad(5, 0.0, 0.0, 0.80, 0.60, shape="roundrect", extra=" (roundrect_rratio 0.1)")]
    body = "\n".join(pads) + "\n" + rect(-0.55, -0.7, 0.55, 0.7, "F.Fab", 0.05) + "\n" + rect(-0.6, -1.05, 0.6, 1.05, "F.CrtYd", 0.05)
    body += "\n" + line(-0.55, -1.0, 0.55, -1.0, "F.SilkS", 0.1)
    write("DRV5032_X2SON-4_DMR0004B", "TI DMR0004B land pattern, pad 1 top-left, 2 bottom-left, 3 bottom-right, 4 top-right, 5 thermal", body)


def motor_pad():
    body = pad(1, 0, 0, 2.4, 2.0, extra=" (roundrect_rratio 0.1)", shape="roundrect", layers="F.Cu F.Mask")
    body += "\n" + rect(-1.5, -1.0, 1.5, 1.0, "F.CrtYd", 0.05)
    write("SMA_Clamp_Pad_2.4x2.0", "bare copper land for an SMA wire crimp ferrule under an M1.2 screw (no paste, solder-mask opening = pad)", body)


def npth(d):
    n = f"NPTH_{d}mm"
    body = f'  (pad "" np_thru_hole circle (at 0 0) (size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask"))\n' + rect(-d / 2 - 0.3, -d / 2 - 0.3, d / 2 + 0.3, d / 2 + 0.3, "F.CrtYd", 0.05)
    txt = f'(footprint "{n}" (version 20240108) (generator "bench_gen")\n  (layer "F.Cu")\n  (descr "NPTH {d} mm")\n  (attr exclude_from_pos_files exclude_from_bom)\n'
    txt += '  (fp_text reference "REF**" (at 0 -2) (layer "F.SilkS") hide (effects (font (size 1 1) (thickness 0.15))))\n'
    txt += body + "\n)\n"
    open(os.path.join(OUT, n + ".kicad_mod"), "w").write(txt)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    e73()
    buzzer()
    x2son()
    motor_pad()
    npth(1.2)
    npth(1.4)
    print("footprints written to", OUT)
