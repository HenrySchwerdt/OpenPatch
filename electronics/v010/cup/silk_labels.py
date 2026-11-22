"""Place the wire / cell pad labels (A+ A- B+ B- + -) on a routed cup board so that they do not overlap each other,
component silkscreen, exposed pads or the board edge.

The build script places them at fixed offsets; with the 1.25 mm pad pitch the 0.9 mm labels overlap. This script
searches, per label, the closest free spot around its own pad (rotation 0 or 90 deg, text height from large to the
0.55 mm minimum) and accepts a spot only if the label is closer to its own pad than to any other labelled pad.
Also raises the back-side warning text to the minimum text height.

usage: kpy silk_labels.py <board.kicad_pcb> [out.kicad_pcb]
"""
import math
import sys

import pcbnew

MM = pcbnew.FromMM
T = pcbnew.ToMM
LABELS = {"A+": "MP1", "A-": "MP2", "B+": "MP3", "B-": "MP4", "+": "SP1", "-": "SP2"}
HEIGHTS = {"+": (1.3, 1.1, 0.9, 0.8, 0.7), "-": (1.3, 1.1, 0.9, 0.8, 0.7)}
DEFAULT_HEIGHTS = (0.9, 0.8, 0.7)
SILK_CLR = MM(0.16)        # board rule 0.15
PAD_CLR = MM(0.12)         # solder mask opening + margin
EDGE_CLR = MM(0.25)
LABEL_CLR = MM(0.45)       # between two pad labels, so that 'A+' and 'A-' read as two words
MIN_TEXT = 0.6             # board rule 0.55


def glyph_spot(b, lab, oc, pad, free, centers, pads, optional=()):
    """try a drawn glyph above, then below the pad, sizes 0.6 .. 0.35 mm; returns ([shapes], size, dy) or None.
    second pass: the outline silk of small passives (optional) may be dropped where the glyph needs the room"""
    half_h = pad.GetSize().y / 2
    for ign, size in [(ig, sz) for ig in ((), tuple(optional)) for sz in (0.6, 0.5, 0.45, 0.4)]:
        for side in (-1, 1):
            for gap in (0.14, 0.18, 0.22, 0.26, 0.3):
                cy = int(oc.y + side * (half_h + MM(gap + size / 2)))
                segs = []
                arms = [((-size / 2, 0), (size / 2, 0))] + ([((0, -size / 2), (0, size / 2))] if lab == "+" else [])
                for (x0, y0), (x1, y1) in arms:
                    sh = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
                    sh.SetLayer(pcbnew.F_SilkS); sh.SetWidth(MM(0.1))
                    sh.SetStart(pcbnew.VECTOR2I(oc.x + MM(x0), cy + MM(y0))); sh.SetEnd(pcbnew.VECTOR2I(oc.x + MM(x1), cy + MM(y1)))
                    segs.append(sh)
                if all(free(sh, ign) for sh in segs):
                    for g in ign:
                        if any(g.GetEffectiveShape(pcbnew.F_SilkS).Collide(sh.GetEffectiveShape(pcbnew.F_SilkS), SILK_CLR) for sh in segs):
                            g.GetParentFootprint().Remove(g)
                    for sh in segs:
                        b.Add(sh)
                    return segs, size, T(cy - oc.y)
    return None


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else src
    b = pcbnew.LoadBoard(src)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    labels = [t for t in b.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS
              and t.GetText() in LABELS]
    for t in b.GetDrawings():
        if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.B_SilkS and T(t.GetTextHeight()) < MIN_TEXT:
            t.SetTextSize(pcbnew.VECTOR2I(MM(MIN_TEXT), MM(MIN_TEXT)))
    pads = {lab: next(iter(fps[ref].Pads())) for lab, ref in LABELS.items() if ref in fps}
    centers = {lab: p.GetPosition() for lab, p in pads.items()}

    # obstacles: component silkscreen, F.Cu pads (mask openings), placed labels
    silk = []
    for f in b.GetFootprints():
        for g in f.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS:
                silk.append(g)
        for txt in (f.Reference(), f.Value()):
            if txt.IsVisible() and txt.GetLayer() == pcbnew.F_SilkS:
                silk.append(txt)
    for g in b.GetDrawings():
        if g.GetLayer() == pcbnew.F_SilkS and g not in labels:
            silk.append(g)
    fpads = [p for f in b.GetFootprints() for p in f.Pads() if p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.F_Mask)
             or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)]
    outline = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, False)
    placed = []

    def free(t, ignore=()):
        sh = t.GetEffectiveShape(pcbnew.F_SilkS)
        bb = t.GetBoundingBox()
        big = bb.GetInflated(EDGE_CLR)
        xs = [big.GetLeft() + (big.GetWidth()) * k // 4 for k in range(5)]
        ys = [big.GetTop() + (big.GetHeight()) * k // 4 for k in range(5)]
        for x in xs:
            for y in ys:
                if not outline.Contains(pcbnew.VECTOR2I(x, y)):
                    return False
        for g in silk + placed:
            if g in ignore:
                continue
            clr = LABEL_CLR if g in placed else SILK_CLR
            if g.GetBoundingBox().Intersects(bb.GetInflated(clr)) and g.GetEffectiveShape(pcbnew.F_SilkS).Collide(sh, clr):
                return False
        for p in fpads:
            if p.GetBoundingBox().Intersects(bb.GetInflated(PAD_CLR)) and p.GetEffectiveShape(pcbnew.F_Cu).Collide(sh, PAD_CLR):
                return False
        return True

    # the labels of the middle column have the fewest unambiguous spots: place them first
    labels.sort(key=lambda t: (t.GetText() not in ("+", "A-"), t.GetText()))
    report = []
    for t in labels:
        lab = t.GetText()
        oc = centers[lab]
        orig = (t.GetPosition(), t.GetTextAngleDegrees(), t.GetTextSize())
        best = None
        for h in HEIGHTS.get(lab, DEFAULT_HEIGHTS):
            t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
            t.SetTextThickness(MM(max(0.1, round(h * 0.15, 2))))
            cands = []
            for ix in range(-30, 31):
                for iy in range(-30, 31):
                    dx, dy = ix * 0.1, iy * 0.1
                    if math.hypot(dx, dy) > 3.0:
                        continue
                    cands.append((dx, dy))
            for rot in ((0,) if lab in ("+", "-") else (0, 90)):      # a rotated '-' would read as '|'
                t.SetTextAngleDegrees(rot)
                for dx, dy in sorted(cands, key=lambda c: math.hypot(*c)):
                    pos = pcbnew.VECTOR2I(oc.x + MM(dx), oc.y + MM(dy))
                    # unambiguous: nearer to its own pad than to any other labelled pad (pad edge distance)
                    de = {k: math.hypot(max(0, abs(pos.x - c.x) - pads[k].GetSize().x / 2), max(0, abs(pos.y - c.y) - pads[k].GetSize().y / 2)) for k, c in centers.items()}
                    if any(de[k] - de[lab] < MM(0.3) for k in de if k != lab):
                        continue
                    t.SetPosition(pos)
                    if free(t):
                        score = math.hypot(dx, dy) + (0.0 if rot == 0 else 0.4) + (1.0 - h) * 2.0
                        if best is None or score < best[0]:
                            best = (score, pos, rot, h)
                        break
            if best:
                break
        if best is None and lab in ("+", "-"):
            # fallback: a small drawn + / - glyph (two / one 0.1 mm silk lines) in the narrow gap next to the pad
            optional = [g for f in b.GetFootprints() if f.GetReference()[:1] in "RC" and f.GetReference()[1:].isdigit()
                            for g in f.GraphicalItems() if g.GetLayer() == pcbnew.F_SilkS]
            g = glyph_spot(b, lab, oc, pads[lab], free, centers, pads, optional)
            if g:
                b.Remove(t)
                placed.extend(g[0])
                report.append(f"{lab}: drawn glyph {g[1]} mm wide at {g[2]:+.2f} mm from its pad centre")
                continue
        if best is None:
            t.SetPosition(orig[0]); t.SetTextAngleDegrees(orig[1]); t.SetTextSize(orig[2])
            report.append(f"{lab}: no free spot, left in place")
            continue
        _, pos, rot, h = best
        t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
        t.SetTextThickness(MM(max(0.1, round(h * 0.15, 2))))
        t.SetTextAngleDegrees(rot)
        t.SetPosition(pos)
        placed.append(t)
        report.append(f"{lab}: {T(pos.x - oc.x):+.1f},{T(pos.y - oc.y):+.1f} mm from its pad, {h} mm, {rot} deg")
    pcbnew.SaveBoard(out, b)
    print("\n".join(report))


if __name__ == "__main__":
    main()
