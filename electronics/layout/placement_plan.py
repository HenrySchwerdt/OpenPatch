#!/usr/bin/env python
"""placement-plan.svg: placement plan (block level) based on the mechanical geometry (geometry.py).
Shows the top and bottom side of the PCB with height zones. All coordinates in the mechanical frame (mm)."""
import math, os, html
from geometry import load
from board_outline import outline_points, rounded_polyline, holes
G = load("OP-100"); c = G["pcb"]; H = G["housing"]
S = 17.0; MX, MY = 30, 125
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ant_y0 = 21.2; ant_x0 = 24.5; ant_x1 = 30.0

# (x0,y0,x1,y1,label,colour)
TOP = [
 (23.5, 13.2, 31.5, 21.2, "U1 ISP1807", "#eb6f92"),
 (c["x0"] + 0.2, 21.8, c["x0"] + 2.4, 23.7, "U8", "#31748f"),
 (24.0, 26.8, 26.0, 28.6, "U5", "#eb6f92"),
 (33.0, 18.9, 37.0, 21.3, "SW1", "#f6c177"),
 (37.4, 18.9, 40.4, 21.3, "Cs 3x0805", "#f6c177"),
 (36.4, 17.0, 39.4, 18.6, "Q1", "#9ccfd8"),
 (39.0, 14.6, 40.4, 17.2, "BT1", "#c4a7e7"),
 (36.0, 13.8, 38.4, 15.5, "Q2", "#9ccfd8"),
 (24.0, 7.2, 30.8, 12.6, "U4 STSPIN220 + R/C", "#9ccfd8"),
 (32.0, 11.0, 35.6, 12.8, "L4", "#c4a7e7"),
 (c["x0"] + 0.1, 3.0, c["x0"] + 1.6, 6.6, "MP1", "#908caa"),
 (27.0, 2.2, 31.0, 5.9, "J1 TC2030", "#908caa"),
 (33.0, 3.0, 40.2, 6.0, "TP1-13", "#908caa"),
]
BOT = [
 (24.0, 14.0, 30.2, 19.4, "U3 BQ25120A + C", "#9ccfd8"),
 (31.0, 14.0, 38.6, 19.4, "U2 BQ51003 + Qi-C", "#f6c177"),
 (31.0, 20.0, 36.6, 24.0, "U6 U7 + R", "#eb6f92"),
 (23.6, 21.2, 24.8, 24.3, "U9 U10", "#31748f"),
 (25.6, 20.0, 30.0, 25.6, "R/C rest", "#908caa"),
]

def tx(x, y, oy=0): return (MX + x * S, MY + oy + (H[1] - y) * S)

def pcb_path(oy):
    pts = rounded_polyline(outline_points(G)); d = []; n = len(pts); i = 0
    while i < n:
        a = pts[i]; ax, ay = tx(a[0], a[1], oy)
        d.append(("M" if not d else "L") + "%.1f,%.1f" % (ax, ay))
        if a[2] != 0:
            b = pts[i + 1]; bx, by = tx(b[0], b[1], oy)
            r = math.hypot(b[0] - a[0], b[1] - a[1]) / math.sqrt(2) * S
            d.append("A%.1f,%.1f 0 0 %d %.1f,%.1f" % (r, r, 0 if a[2] > 0 else 1, bx, by)); i += 2
        else: i += 1
    return " ".join(d) + " Z"

def rect(x0, y0, x1, y1, oy, **kw):
    x, y = tx(x0, y1, oy)
    attrs = " ".join('%s="%s"' % (k.replace("_", "-"), v) for k, v in kw.items())
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" %s/>' % (x, y, (x1 - x0) * S, (y1 - y0) * S, attrs)

def text(x, y, t, oy, size=9, fill="#191724", anchor="middle", bold=True):
    X, Y = tx(x, y, oy)
    return '<text x="%.1f" y="%.1f" font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>' % (X, Y, size, fill, anchor, ' font-weight="bold"' if bold else "", html.escape(t))

def panel(title, parts, oy, top):
    o = [text(0, H[1] + 2.5, title, oy, 14, "#e0def4", "start")]
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="none" stroke="#6e6a86" stroke-dasharray="6 3"/>' %
             (MX, MY + oy, H[0] * S, H[1] * S, 4 * S))
    r = G["reservoir"]; o.append(rect(r["x0"], r["y0"], r["x1"], r["y1"], oy, fill="#191724", stroke="#9ccfd8", stroke_dasharray="5 4"))
    o.append(text((r["x0"] + r["x1"]) / 2, (r["y0"] + r["y1"]) / 2, "Reservoir (mechanical/)", oy, 11, "#9ccfd8"))
    sy = G["spindle_y"]; mo = G["motor"]
    o.append(rect(0.9, sy - 1.2, r["x1"], sy + 1.2, oy, fill="none", stroke="#908caa", stroke_dasharray="3 3"))
    o.append(rect(3.3, mo["y"] - 3, r["x1"] - 4, mo["y"] + 3, oy, fill="#191724", stroke="#908caa", stroke_dasharray="3 3"))
    o.append(text(12, mo["y"], "Motor + gearbox / spindle (y=%.1f)" % sy, oy, 10, "#908caa"))
    o.append('<path d="%s" fill="#2a273f" stroke="#e0def4" stroke-width="1.6"/>' % pcb_path(oy))
    b = G["battery"]
    if not top: o.append(rect(b["x0"], b["y0"], b["x1"], b["y1"], oy, fill="#3e8fb0", fill_opacity="0.18", stroke="#3e8fb0", stroke_dasharray="6 3"))
    if top:
        q = G["coil"]; cx, cy = tx(q["cx"], q["cy"], oy)
        o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#f6c177" fill-opacity="0.08" stroke="#f6c177" stroke-width="2" stroke-dasharray="6 3"/>' % (cx, cy, q["d"] / 2 * S))
        o.append(text(q["cx"], q["cy"] + 5.5, "Qi coil O%.1f (z %.2f..%.2f): components below <= 1.05 mm" % (q["d"], q["z0"], q["z0"] + q["t"]), oy, 10, "#f6c177"))
        z = G["buzzer"]; o.append(rect(z["x0"], z["y0"], z["x1"], z["y1"], oy, fill="#ea9a97", fill_opacity="0.85", stroke="#191724"))
        o.append(text((z["x0"] + z["x1"]) / 2, (z["y0"] + z["y1"]) / 2, "BZ1 Piezo 9x9x2", oy, 10))
        o.append(rect(ant_x0, ant_y0, ant_x1, ant_y0 + 4.3, oy, fill="#eb6f92", fill_opacity="0.10", stroke="#eb6f92", stroke_dasharray="3 3"))
        o.append(text((ant_x0 + ant_x1) / 2, ant_y0 + 2.0, "Antenna keep-out (TBD)", oy, 8, "#eb6f92"))
    else:
        o.append(text((b["x0"] + b["x1"]) / 2, b["y1"] - 0.8, "LiPo (z %.2f..%.2f) -> bottom components <= 0.5 mm, only y >= %.1f" % (b["z0"], b["z0"] + b["t"], b["y0"]), oy, 9, "#3e8fb0"))
        nx, ny = G["needle"]; X, Y = tx(nx, ny, oy)
        o.append('<circle cx="%.1f" cy="%.1f" r="9" fill="none" stroke="#f6c177"/>' % (X, Y))
        o.append(text(nx, ny - 1.6, "Cannula tower: NO components on the bottom (y < %.1f)" % b["y0"], oy, 9, "#f6c177"))
    for (x0, y0, x1, y1, lab, col) in parts:
        o.append(rect(x0, y0, x1, y1, oy, fill=col, fill_opacity="0.9", stroke="#191724", stroke_width="0.8"))
        o.append(text((x0 + x1) / 2, (y0 + y1) / 2 - 0.1, lab, oy, 8 if (x1 - x0) * S < 70 else 9))
    for (hx, hy) in holes(G):
        X, Y = tx(hx, hy, oy); o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#191724" stroke="#e0def4"/>' % (X, Y, 0.6 * S))
    return "\n".join(o)

def main():
    W = int(MX * 2 + H[0] * S) + 330; oy2 = int(H[1] * S + 70); Ht = int(MY + oy2 + H[1] * S + 40)
    s = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Helvetica, Arial, sans-serif">' % (W, Ht, W, Ht),
         '<rect width="100%" height="100%" fill="#191724"/>',
         '<text x="%d" y="28" font-size="18" font-weight="bold" fill="#e0def4">OpenPatch OP-100 - Placement plan (block level)</text>' % MX,
         '<text x="%d" y="48" font-size="11" fill="#908caa">PCB %.1f x %.1f mm (x %.1f..%.1f, y %.1f..%.1f) from mechanical/out/OP-100.layout.json; housing 42 x 32 x 8.5. Placement = draft, no routing yet.</text>' % (MX, c["x1"] - c["x0"], c["y1"] - c["y0"], c["x0"], c["x1"], c["y0"], c["y1"]),
         '<text x="%d" y="64" font-size="11" fill="#908caa">Z stack: floor 0-0.9 | LiPo 1.05-4.25 | PCB 4.9-5.5 | top components 5.5-6.55 (1.05) | Qi coil 6.55-7.15 | lid from 7.6 (piezo up to 7.5)</text>' % MX]
    s.append(panel("TOP SIDE (lid/coil side)", TOP, 0, True)); s.append(panel("BOTTOM SIDE (battery side)", BOT, oy2, False))
    lx = int(MX + H[0] * S + 30)
    for i, t in enumerate(["Height rules (from the mechanical stack):", "- top, under the coil: max 1.05 mm (QFN48 0.9 is tight!)", "- top, outside the coil: up to ~2.1 mm (piezo, button, 0805)",
                           "- bottom, over the battery (y>=13.7): max 0.5 mm: WCSP, X2SON, 0402", "- bottom, over the cannula tower: no components", "- ISP1807: antenna edge +y, keep-out on all layers (dimensions TBD, datasheet)",
                           "- Hall: DRV5032 (0.4 mm) on the bottom near the spindle end, TMAG5273 on top", "- Conflict: Hall (spindle end y=22.5) lies at the antenna keep-out -> TBD"]):
        s.append('<text x="%d" y="%d" font-size="12" fill="#e0def4"%s>%s</text>' % (lx, MY + 14 + i * 18, ' font-weight="bold"' if i == 0 else "", t))
    s.append("</svg>")
    path = os.path.join(OUT, "placement-plan.svg"); open(path, "w").write("\n".join(s)); print("SVG:", path)

if __name__ == "__main__":
    main()
