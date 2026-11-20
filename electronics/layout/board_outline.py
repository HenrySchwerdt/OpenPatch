#!/usr/bin/env python
"""PCB outline from the mechanical geometry -> ../board-outline.dxf (mm, mechanical frame).
Rectangle (x0..x1, y0..y1, corners R) minus an L-shaped cutout at the corner (x0,y0) for the cannula tower.
Usage: ../.venv/bin/python board_outline.py [OP-100|OP-70|OP-200]"""
import math, os, sys
import ezdxf
from ezdxf.math import Vec2
from geometry import load

def rounded_polyline(pts):
    n = len(pts); out = []
    for i in range(n):
        p0 = Vec2(pts[i - 1][:2]); p1 = Vec2(pts[i][:2]); p2 = Vec2(pts[(i + 1) % n][:2]); r = pts[i][2]
        if r <= 0:
            out.append((p1.x, p1.y, 0.0)); continue
        d1 = (p0 - p1).normalize(); d2 = (p2 - p1).normalize(); a = p1 + d1 * r; b = p1 + d2 * r
        bulge = math.tan(math.radians(90) / 4) * (1 if (p1 - p0).det(p2 - p1) > 0 else -1)
        out += [(a.x, a.y, bulge), (b.x, b.y, 0.0)]
    return out

def outline_points(G):
    c, nt = G["pcb"], G["notch"]; r = c["r"]
    nx, ny = nt["x1"], nt["y1"]
    return [(nx, c["y0"], 0.5), (c["x1"], c["y0"], r), (c["x1"], c["y1"], r), (c["x0"], c["y1"], r),
            (c["x0"], ny, 0.5), (nx, ny, 0.5)]            # CCW

def holes(G):
    c = G["pcb"]   # positions to be agreed with mechanical/ (housing domes); placeholders at the edge here
    return [(c["x1"] - 1.6, c["y0"] + 1.7), (c["x1"] - 1.6, 12.5)]

def main(variant="OP-100"):
    G = load(variant); c = G["pcb"]; H = G["housing"]
    doc = ezdxf.new("R2010", setup=True); doc.units = ezdxf.units.MM; msp = doc.modelspace()
    for name, color, lt in (("BOARD_OUTLINE", 7, "CONTINUOUS"), ("DRILL_MOUNT", 1, "CONTINUOUS"), ("KEEPOUT_ANTENNA", 6, "DASHED"),
                            ("REF_HOUSING", 8, "DASHDOT"), ("REF_RESERVOIR", 4, "DASHED"), ("REF_QI_COIL", 3, "DASHED"),
                            ("REF_BATTERY", 5, "DASHED"), ("REF_BUZZER", 30, "DASHED"), ("REF_MOTOR_SPINDLE", 4, "DASHED"),
                            ("REF_CANNULA_NEEDLE", 2, "CONTINUOUS"), ("REF_ISP1807_8x8", 6, "DASHED"), ("NOTES", 2, "CONTINUOUS")):
        doc.layers.add(name, color=color, linetype=lt)
    msp.add_lwpolyline(rounded_polyline(outline_points(G)), format="xyb", close=True, dxfattribs={"layer": "BOARD_OUTLINE"})
    for (x, y) in holes(G): msp.add_circle((x, y), 0.6, dxfattribs={"layer": "DRILL_MOUNT"})
    msp.add_lwpolyline([(0, 0), (H[0], 0), (H[0], H[1]), (0, H[1])], close=True, dxfattribs={"layer": "REF_HOUSING"})
    r = G["reservoir"]; msp.add_lwpolyline([(r["x0"], r["y0"]), (r["x1"], r["y0"]), (r["x1"], r["y1"]), (r["x0"], r["y1"])], close=True, dxfattribs={"layer": "REF_RESERVOIR"})
    msp.add_line((3.3, G["spindle_y"]), (r["x1"], G["spindle_y"]), dxfattribs={"layer": "REF_MOTOR_SPINDLE"})
    mo = G["motor"]; msp.add_lwpolyline([(0.0, mo["y"] - 3), (r["x1"] - 4, mo["y"] - 3), (r["x1"] - 4, mo["y"] + 3), (0.0, mo["y"] + 3)], close=True, dxfattribs={"layer": "REF_MOTOR_SPINDLE"})
    q = G["coil"]; msp.add_circle((q["cx"], q["cy"]), q["d"] / 2, dxfattribs={"layer": "REF_QI_COIL"})
    b = G["battery"]; msp.add_lwpolyline([(b["x0"], b["y0"]), (b["x1"], b["y0"]), (b["x1"], b["y1"]), (b["x0"], b["y1"])], close=True, dxfattribs={"layer": "REF_BATTERY"})
    z = G["buzzer"]; msp.add_lwpolyline([(z["x0"], z["y0"]), (z["x1"], z["y0"]), (z["x1"], z["y1"]), (z["x0"], z["y1"])], close=True, dxfattribs={"layer": "REF_BUZZER"})
    msp.add_circle(G["needle"], 0.5, dxfattribs={"layer": "REF_CANNULA_NEEDLE"})
    ax1, ay0 = 30.0, 21.2                # antenna keep-out above the ISP1807 edge (+y); dimensions TBD per datasheet (placeholder)
    ax0 = 24.5
    msp.add_lwpolyline([(ax0, ay0), (ax1, ay0), (ax1, ay0 + 4.3), (ax0, ay0 + 4.3)], close=True, dxfattribs={"layer": "KEEPOUT_ANTENNA"})
    msp.add_lwpolyline([(23.5, 13.2), (31.5, 13.2), (31.5, 21.2), (23.5, 21.2)], close=True, dxfattribs={"layer": "REF_ISP1807_8x8"})
    for txt, x, y, h in (("%s PCB outline (from mechanical/out/%s.layout.json)  4L 0.6mm ENIG" % (variant, variant), 0.0, -3.0, 0.9),
                         ("PCB %.1f x %.1f mm, corner R%.1f, L-notch %.2f x %.2f" % (c["x1"] - c["x0"], c["y1"] - c["y0"], c["r"], G["notch"]["x1"] - c["x0"], G["notch"]["y1"] - c["y0"]), 0.0, -5.0, 0.7),
                         ("ISP1807 8x8 (antenna edge +y); keep-out TBD per datasheet", 23.5, 12.0, 0.5), ("Antenna keep-out (all layers)", ax0, ay0 + 4.5, 0.5), ("Qi coil (above PCB)", q["cx"] - 5, q["cy"], 0.6),
                         ("Battery (below PCB)", b["x0"] + 2, b["y0"] + 1.0, 0.6), ("Piezo 9x9x2 (above PCB)", z["x0"] + 0.5, z["y0"] + 4, 0.6)):
        msp.add_text(txt, height=h, dxfattribs={"layer": "NOTES"}).set_placement((x, y))
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "board-outline.dxf" if variant == "OP-100" else "board-outline-%s.dxf" % variant))
    doc.saveas(path)
    d2 = ezdxf.readfile(path); aud = d2.audit()
    pl = list(d2.modelspace().query("LWPOLYLINE[layer=='BOARD_OUTLINE']"))[0]
    pts = [(x, y) for x, y, *_ in pl.get_points("xyb")]; xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    print("DXF:", path); print("Audit errors:", len(aud.errors), "Entities:", len(d2.modelspace()))
    print("PCB-BBox %.2f x %.2f mm (x %.2f..%.2f, y %.2f..%.2f)" % (max(xs) - min(xs), max(ys) - min(ys), min(xs), max(xs), min(ys), max(ys)))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "OP-100")
