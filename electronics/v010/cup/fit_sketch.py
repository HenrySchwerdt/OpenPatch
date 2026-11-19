#!/usr/bin/env python3
"""FIT-CHECK sketches (top view + side section) as SVG, and the per-block area table.  kpy fit_sketch.py [placement.json]  (pod frame, mm)"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
sys.path.insert(0, HERE)
import cupgeom as G
import place_cup as PC

MECH = json.load(open(os.path.join(HERE, "..", "..", "..", "mechanical", "out", "v010-cup", "OP-100.mech.json")))
S = 18.0   # px per mm
COL = dict(tank="#cfe3f5", motor="#e9c7c7", cell="#e8e0c0", usb="#d8c8ee", ko="#f0f0f0", board="#bfe8c4", dock="#ffd9a8", ant="#ff9d9d")


def rect(x0, y0, x1, y1, fill, stroke="#444", op=1.0, sw=0.8, dash=None):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-width="%.1f"%s/>' % (x0 * S, y0 * S, (x1 - x0) * S, (y1 - y0) * S, fill, op, stroke, sw, d)


def text(x, y, t, size=9, fill="#222", anchor="middle"):
    return '<text x="%.1f" y="%.1f" font-family="Helvetica,Arial" font-size="%d" fill="%s" text-anchor="%s">%s</text>' % (x * S, y * S, size, fill, anchor, t)


def top_view(parts, geo, pl):
    W, H = MECH["length"], MECH["width"]
    Y = lambda y: H - y          # pod +Y up -> svg down
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="-20 -20 %d %d" style="background:#fff">' % ((W + 3) * S, (H + 3) * S, (W + 3) * S, (H + 3) * S)]
    o.append(rect(0, 0, W, H, "#fafafa", "#000", sw=1.5))
    # tank, motor, cell etc. in the pod frame
    o.append(rect(10.17, Y(22.6), 35.11, Y(0.9), COL["tank"], op=0.8)); o.append(text(22.6, Y(11.7), "tank + plunger (z 0.9-7.6)"))
    o.append(rect(1.47, Y(32.15), 7.47, Y(16.05), COL["motor"], op=0.9)); o.append(text(4.5, Y(24), "motor", 9))
    c = MECH["battery"]; o.append(rect(c["x"][0], Y(c["y"][1]), c["x"][1], Y(c["y"][0]), COL["cell"], op=0.9)); o.append(text(24, Y(23.6), "cell 301030 z 0.9-4.1", 8))
    u = MECH["usb"]; o.append(rect(u["x"][0], Y(u["y"][1]), u["x"][1], Y(u["y"][0]), COL["usb"], op=0.9)); o.append(text(12.3, Y(27.1), "USB-C", 8))
    o.append(rect(34.86, Y(16.25), 43.86, Y(7.25), COL["dock"], op=0.9)); o.append(text(40, Y(8.2), "dock pocket + adapter (z<4.2)", 8))
    o.append(rect(35.4, Y(6.35), 44.16, Y(1.0), COL["ko"], op=0.9, dash="3,2")); o.append(rect(35.16, Y(22.5), 46.76, Y(17.15), COL["ko"], op=0.9, dash="3,2"))
    o.append(rect(*[2.67, Y(10.45), 5.57, Y(7.25)], "#ffe9a0", op=0.9)); o.append(text(4.1, Y(6.4), "TMAG", 8))
    o.append(rect(4.0, Y(7.25), 9.97, Y(1.0), COL["ko"], op=0.9, dash="3,2")); o.append(text(7, Y(4), "ko_io", 8))
    # board
    pts = " ".join("%.1f,%.1f" % (x * S, Y(y) * S) for x, y in G.OUTLINE_POD)
    o.append('<polygon points="%s" fill="%s" fill-opacity="0.55" stroke="#0a7a1f" stroke-width="1.6"/>' % (pts, COL["board"]))
    a = G.ANT_POD; o.append(rect(a[0], Y(a[3]), a[2] + 3.2, Y(a[1]), COL["ant"], op=0.35, stroke="#c00", dash="4,3")); o.append(text(44.6, Y(28), "antenna", 8, "#c00"))
    # parts
    for ref, st in pl.items():
        bb = PC.box_of(geo[ref], st)
        x0, y0 = G.p(bb[0], bb[1]); x1, y1 = G.p(bb[2], bb[3])
        top = st[3] == "F"
        o.append(rect(min(x0, x1), Y(max(y0, y1)), max(x0, x1), Y(min(y0, y1)), "#1f6fd0" if top else "#d06f1f", op=0.35 if top else 0.3, stroke="#123" if top else "#a50", sw=0.4))
    for ref, lab in (("U1", "ISP1807"), ("U7", "STSPIN220"), ("U30", "supervisor"), ("JU1", "USB-C")):
        bb = PC.box_of(geo[ref], pl[ref]); x0, y0 = G.p(bb[0], bb[1]); x1, y1 = G.p(bb[2], bb[3])
        o.append(text((x0 + x1) / 2, Y((y0 + y1) / 2), lab, 7, "#003"))
    o.append(text(W / 2, -0.4, "top view (pod frame, mm): green = rigid board outline, blue = top-side parts, orange = bottom-side parts", 10, "#000"))
    o.append("</svg>")
    return "\n".join(o)


def side_view():
    # section along X through lane 2 (y = 28): z stack
    W = MECH["length"]; Zt = 8.5
    Z = lambda z: (Zt - z) * 1.0
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="-20 -30 %d %d" style="background:#fff">' % ((W + 3) * S, (Zt + 4) * S, (W + 3) * S, (Zt + 4) * S)]
    o.append(rect(0, Z(8.5), W, Z(0), "#fafafa", "#000", sw=1.5))
    o.append(rect(0.9, Z(7.6), W - 0.9, Z(0.9), "#fff", "#999", sw=0.6, dash="2,2"))
    o.append(rect(7.87, Z(4.1), 39.37, Z(0.9), COL["cell"], op=0.9)); o.append(text(23, Z(2.4), "cell z 0.9-4.1", 9))
    o.append(rect(7.87, Z(7.46), 16.81, Z(4.2), COL["usb"], op=0.9)); o.append(text(12.3, Z(5.6), "USB-C 4.2-7.46", 8))
    o.append(rect(7.6, Z(G.Z_TOP), 43.2, Z(G.Z_BOT), COL["board"], op=1.0, stroke="#0a7a1f")); o.append(text(28, Z(5.7) + 0.35, "board z 5.3-6.1", 8))
    o.append(rect(17.2, Z(7.3), 27, Z(6.1), "#fff2c0", op=0.9, stroke="#a80", dash="3,2")); o.append(text(22, Z(6.6) + 0.2, "top parts <= 1.2 (piezo disc above)", 8))
    o.append(rect(17.2, Z(5.3), 39.4, Z(4.2), "#ffe0cc", op=0.9, stroke="#a50", dash="3,2")); o.append(text(28, Z(4.75) + 0.2, "bottom parts <= 1.1 (0201..QFN)", 8))
    o.append(rect(39.4, Z(5.3), 43.2, Z(0.9), "#ffe0cc", op=0.5, stroke="#a50", dash="3,2"))
    o.append(rect(36.0, Z(5.3), 42.0, Z(4.9), "#555", op=0.9)); o.append(text(40, Z(4.5), "dock hall z 4.9-5.3", 8))
    o.append(rect(42.4, Z(7.6), 46.4, Z(5.9), COL["ant"], op=0.4, stroke="#c00", dash="4,3")); o.append(text(44.4, Z(6.6), "ISP antenna", 8, "#c00"))
    o.append(rect(38.4, Z(7.0), 46.4, Z(6.1), "#7aa0e0", op=0.9)); o.append(text(42.4, Z(6.5) + 0.2, "ISP1807", 8))
    o.append(text(W / 2, -1.2, "side section through lane 2 (z up, mm): lid inner 7.6", 10, "#000"))
    o.append("</svg>")
    return "\n".join(o)


def main():
    plf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "placement.json")
    parts = json.load(open(os.path.join(HERE, "..", "netlist_v4_cup.json")))
    pl = json.load(open(plf))
    geo = PC.geometry(parts)
    open(os.path.join(HERE, "fit_top.svg"), "w").write(top_view(parts, geo, pl))
    open(os.path.join(HERE, "fit_side.svg"), "w").write(side_view())
    grp = {}
    for p in parts:
        bb = PC.box_of(geo[p["ref"]], pl[p["ref"]])
        a = (bb[2] - bb[0]) * (bb[3] - bb[1])
        grp.setdefault(p["group"], {"F": 0, "B": 0, "n": 0})
        grp[p["group"]][pl[p["ref"]][3]] += a
        grp[p["group"]]["n"] += 1
    tot = {"F": 0, "B": 0}
    print("| block | parts | top mm2 | bottom mm2 | sum |")
    print("|---|---|---|---|---|")
    for g, d in sorted(grp.items(), key=lambda kv: -(kv[1]["F"] + kv[1]["B"])):
        print("| %s | %d | %.0f | %.0f | %.0f |" % (g, d["n"], d["F"], d["B"], d["F"] + d["B"]))
        tot["F"] += d["F"]; tot["B"] += d["B"]
    print("| **total** | %d | %.0f | %.0f | %.0f |" % (len(parts), tot["F"], tot["B"], tot["F"] + tot["B"]))
    # outline area
    poly = G.OUTLINE
    ar = 0.5 * abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))))
    print("outline area %.0f mm2" % ar)


if __name__ == "__main__":
    main()
