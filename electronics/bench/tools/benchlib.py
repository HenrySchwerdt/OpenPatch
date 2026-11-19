"""Shared board-builder for the bench boards (run with KiCad's python3).

A board is described as code: parts (footprint + pad->net map + LCSC data), outline, keepouts, text.
build() writes the .kicad_pcb; route()/finish()/drc()/export() are in separate functions below.
"""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile

import pcbnew

KL = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
KCLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
JAVA = "/opt/homebrew/opt/openjdk/bin/java"
FREEROUTING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "freerouting-2.2.4.jar")
BENCHFP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "footprints", "Bench.pretty")
MM = pcbnew.FromMM
OX, OY = 100.0, 80.0     # board origin on the KiCad page (mm)

# JLC 4-layer 1.6 mm standard rules used by both boards
TRACK, CLEAR, VIA_D, VIA_H = 0.15, 0.15, 0.55, 0.3


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


class Board:
    def __init__(self, name, w, h, layers=4, corner=1.0, outline=None):
        self.name, self.w, self.h, self.layers, self.corner = name, w, h, layers, corner
        self.outline = outline            # optional list of polygon points (board coords)
        self.b = pcbnew.BOARD()
        self.nets = {}
        self.parts = {}                   # ref -> dict (bom data)
        self.pos = {}                     # ref -> (x, y, rot) overrides
        self.yshift = (1e9, 0.0)           # (y >= first) gets shifted by second (bulk placement helper)
        self.b.SetCopperLayerCount(layers)
        bds = self.b.GetDesignSettings()
        bds.SetBoardThickness(MM(1.6))

    # ------------------------------------------------------------ nets
    def net(self, n):
        if n not in self.nets:
            ni = pcbnew.NETINFO_ITEM(self.b, n)
            self.b.Add(ni)
            self.nets[n] = ni
        return self.nets[n]

    # ------------------------------------------------------------ parts
    def load_fp(self, lib, fpname):
        path = BENCHFP if lib == "Bench" else os.path.join(KL, lib + ".pretty")
        fp = pcbnew.FootprintLoad(path, fpname)
        if fp is None:
            raise SystemExit(f"footprint not found: {lib}:{fpname}")
        return fp

    def add(self, ref, value, fp, x, y, rot=0.0, side="F", pins=None, lcsc=None, mpn=None, bom=True, note="", hide_ref=False):
        lib, name = fp
        if ref in self.pos:
            x, y, rot = self.pos[ref]
        if y >= self.yshift[0] and not ref.startswith("H"):
            y += self.yshift[1]
        f = self.load_fp(lib, name)
        f.SetReference(ref)
        f.SetValue(value)
        f.SetPosition(P(x, y))
        f.SetOrientationDegrees(rot)
        self.b.Add(f)
        if side == "B":
            f.Flip(P(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        pins = pins or {}
        used = set()
        for pad in f.Pads():
            num = pad.GetNumber()
            if num in pins and pins[num]:
                pad.SetNet(self.net(pins[num]))
                used.add(num)
        missing = set(k for k, v in pins.items() if v) - used
        if missing:
            raise SystemExit(f"{ref}: pads {missing} not in footprint {name}")
        f.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        f.Reference().SetTextThickness(MM(0.12))
        f.Value().SetVisible(False)
        if hide_ref:
            f.Reference().SetVisible(False)
        self.parts[ref] = dict(ref=ref, value=value, fp=name, lcsc=lcsc, mpn=mpn, bom=bom, note=note, side=side)
        return f

    # ------------------------------------------------------------ outline & graphics
    def seg(self, a, b, layer=pcbnew.Edge_Cuts, w=0.1):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetLayer(layer); s.SetWidth(MM(w))
        self.b.Add(s)

    def arc(self, c, start_deg, r, layer=pcbnew.Edge_Cuts, w=0.1):
        # quarter arc around centre c, from start_deg sweeping +90 (screen, y down)
        a0 = math.radians(start_deg); a1 = math.radians(start_deg + 45); a2 = math.radians(start_deg + 90)
        pt = lambda a: (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(*pt(a0)), P(*pt(a1)), P(*pt(a2)))
        s.SetLayer(layer); s.SetWidth(MM(w))
        self.b.Add(s)

    def rounded_outline(self):
        w, h, r = self.w, self.h, self.corner
        self.seg((r, 0), (w - r, 0)); self.seg((w, r), (w, h - r))
        self.seg((w - r, h), (r, h)); self.seg((0, h - r), (0, r))
        self.arc((w - r, r), -90, r); self.arc((w - r, h - r), 0, r)
        self.arc((r, h - r), 90, r); self.arc((r, r), 180, r)

    def poly_outline(self, pts):
        for i, a in enumerate(pts):
            self.seg(a, pts[(i + 1) % len(pts)])

    def text(self, txt, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0.0, mirror=False, thick=0.15):
        t = pcbnew.PCB_TEXT(self.b)
        t.SetText(txt); t.SetPosition(P(x, y)); t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(thick))
        t.SetTextAngleDegrees(rot); t.SetMirrored(mirror)
        self.b.Add(t)

    def keepout(self, x0, y0, x1, y1, name, copper=True, vias=True, tracks=True, pours=True):
        z = pcbnew.ZONE(self.b)
        z.SetIsRuleArea(True); z.SetZoneName(name)
        z.SetDoNotAllowTracks(tracks); z.SetDoNotAllowVias(vias)
        z.SetDoNotAllowZoneFills(pours); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for l in self.copper_layers():
            ls.AddLayer(l)
        z.SetLayerSet(ls)
        ch = z.Outline(); ch.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ch.Append(MM(OX + x), MM(OY + y))
        self.b.Add(z)

    def copper_layers(self):
        return [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu][: (2 if self.layers == 2 else 4)] if self.layers == 4 else [pcbnew.F_Cu, pcbnew.B_Cu]

    def outline_points(self):
        if self.outline:
            return self.outline
        return [(0, 0), (self.w, 0), (self.w, self.h), (0, self.h)]

    def pour(self, name, layer, net, inset=0.3, prio=0):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(layer); z.SetNet(self.net(net)); z.SetZoneName(name)
        z.SetMinThickness(MM(0.15)); z.SetLocalClearance(MM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.2)); z.SetThermalReliefSpokeWidth(MM(0.3))
        z.SetAssignedPriority(prio)
        ch = z.Outline(); ch.NewOutline()
        x0 = min(p[0] for p in self.outline_points()) + inset; x1 = max(p[0] for p in self.outline_points()) - inset
        y0 = min(p[1] for p in self.outline_points()) + inset; y1 = max(p[1] for p in self.outline_points()) - inset
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ch.Append(MM(OX + x), MM(OY + y))
        self.b.Add(z)

    # ------------------------------------------------------------ rules
    def rules(self, power_nets=(), power_w=0.4, track=TRACK):
        bds = self.b.GetDesignSettings()
        bds.m_MinClearance = MM(CLEAR)
        bds.m_TrackMinWidth = MM(0.127)
        bds.m_ViasMinSize = MM(0.5)
        bds.m_MinThroughDrill = MM(0.3)
        bds.m_CopperEdgeClearance = MM(0.3)
        bds.m_HoleToHoleMin = MM(0.25)
        bds.m_ViasMinAnnulus = MM(0.1)
        bds.m_MinSilkClearance = 0
        ns = bds.m_NetSettings
        d = ns.GetDefaultNetclass()
        d.SetClearance(MM(CLEAR)); d.SetTrackWidth(MM(track)); d.SetViaDiameter(MM(VIA_D)); d.SetViaDrill(MM(VIA_H))
        if power_nets:
            pc = pcbnew.NETCLASS("Power")
            pc.SetClearance(MM(CLEAR)); pc.SetTrackWidth(MM(power_w)); pc.SetViaDiameter(MM(VIA_D)); pc.SetViaDrill(MM(VIA_H))
            ns.SetNetclass("Power", pc)
            for n in power_nets:
                ns.SetNetclassPatternAssignment(n, "Power")

    def save(self, path):
        self.b.BuildListOfNets()
        pcbnew.SaveBoard(path, self.b)


# ---------------------------------------------------------------- project file
def write_project(path, power_nets=(), power_w=0.3, track=TRACK, edge=0.3, clear=None):
    clear = clear or CLEAR
    nc = [{"name": "Default", "clearance": clear, "track_width": track, "via_diameter": VIA_D, "via_drill": VIA_H,
           "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.2, "diff_pair_via_gap": 0.25,
           "priority": 2147483647, "pcb_color": "rgba(0,0,0,0.000)", "schematic_color": "rgba(0,0,0,0.000)", "wire_width": 6,
           "bus_width": 12, "line_style": 0}]
    pats = []
    if power_nets:
        nc.append(dict(nc[0], name="Power", track_width=power_w, priority=0))
        pats = [{"netclass": "Power", "pattern": n} for n in power_nets]
    pro = {"meta": {"filename": os.path.basename(path), "version": 3},
           "board": {"design_settings": {
               "rules": {"min_clearance": clear, "min_copper_edge_clearance": edge, "min_hole_clearance": 0.25,
                         "min_hole_to_hole": 0.25, "min_through_hole_diameter": 0.3, "min_track_width": 0.127,
                         "min_via_annular_width": 0.1, "min_via_diameter": 0.5, "min_silk_clearance": 0.0,
                         "min_text_height": 0.55, "min_text_thickness": 0.08, "min_connection_width": 0.2,
                         "solder_mask_min_width": 0.1, "solder_mask_to_copper_clearance": 0.0},
               "rule_severities": {"silk_over_copper": "ignore", "silk_overlap": "ignore", "silk_edge_clearance": "ignore",
                                   "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                                   "footprint_symbol_mismatch": "ignore", "courtyards_overlap": "warning",
                                   "solder_mask_bridge": "warning", "npth_inside_courtyard": "warning"}}},
           "net_settings": {"classes": nc, "meta": {"version": 4}, "net_colors": None, "netclass_assignments": None,
                            "netclass_patterns": pats}}
    json.dump(pro, open(path, "w"), indent=2)


# ---------------------------------------------------------------- routing
def prep_route(pcb_path, dsn_path, gnd_layers=(pcbnew.In1_Cu,)):
    b = pcbnew.LoadBoard(pcb_path)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea():
            b.Remove(z)
    pcbnew.SaveBoard(pcb_path, b)
    pcbnew.ExportSpecctraDSN(b, dsn_path)


def freeroute(dsn, ses, passes=40, threads=4):
    cmd = [JAVA, "-jar", FREEROUTING, "-de", dsn, "-do", ses, "-mp", str(passes)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(ses + ".log", "w").write(r.stdout + r.stderr)
    return r.returncode


def import_ses(pcb_path, ses):
    b = pcbnew.LoadBoard(pcb_path)
    ok = pcbnew.ImportSpecctraSES(b, ses)
    pcbnew.SaveBoard(pcb_path, b)
    return ok


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("WARN", " ".join(cmd[:5]), r.returncode, r.stderr[-300:])
    return r


def drc(pcb_path, out_json):
    run([KCLI, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "--all-track-errors", "-o", out_json, pcb_path])
    d = json.load(open(out_json))
    viol = d.get("violations", []); unc = d.get("unconnected_items", [])
    errs = [v for v in viol if v["severity"] == "error"]; warns = [v for v in viol if v["severity"] == "warning"]
    from collections import Counter
    return dict(errors=len(errs), warnings=len(warns), unconnected=len(unc),
                err_types=Counter(v["type"] for v in errs), warn_types=Counter(v["type"] for v in warns), raw=d)


# ---------------------------------------------------------------- simple legalizer
def _box(f):
    f.BuildCourtyardCaches()
    side = pcbnew.B_CrtYd if f.GetSide() == pcbnew.B_Cu else pcbnew.F_CrtYd
    c = f.GetCourtyard(side)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False, False)
    t = pcbnew.ToMM
    return [t(bb.GetLeft()) - OX, t(bb.GetTop()) - OY, t(bb.GetRight()) - OX, t(bb.GetBottom()) - OY]


def legalize(board, fixed, extra_boxes=(), margin=0.15, edge=0.5, step=0.3, rmax=14.0, inside=None, forbid=()):
    """Push non-fixed footprints (greedy spiral) until no courtyard overlaps (per side) and everything is inside the board.

    extra_boxes / forbid: boxes [x0,y0,x1,y1] blocked on both sides.  inside(box)->bool replaces the rectangular edge test.
    """
    fps = {f.GetReference(): f for f in board.b.GetFootprints()}
    placed = {"F": [list(b) for b in list(extra_boxes) + list(forbid)], "B": [list(b) for b in list(extra_boxes) + list(forbid)]}
    side = lambda f: "B" if f.GetSide() == pcbnew.B_Cu else "F"
    for r in fixed:
        placed[side(fps[r])].append(_box(fps[r]))
    for f in fps.values():                              # mounting holes (both sides)
        if f.GetReference().startswith("H"):
            for sd in "FB":
                placed[sd].append(_box(f))
    ov = lambda a, b: a[0] < b[2] + margin and a[2] > b[0] - margin and a[1] < b[3] + margin and a[3] > b[1] - margin
    area = lambda b: (b[2] - b[0]) * (b[3] - b[1])
    todo = sorted((r for r in fps if r not in fixed and not r.startswith("H")), key=lambda r: -area(_box(fps[r])))
    moved = 0
    for r in todo:
        f = fps[r]; b0 = _box(f); sd = side(f)
        cand = [(0.0, 0.0)]
        n = int(rmax / step)
        for k in range(1, n + 1):
            ring = []
            for i in range(-k, k + 1):
                ring += [(i * step, -k * step), (i * step, k * step), (-k * step, i * step), (k * step, i * step)]
            cand += sorted(set(ring), key=lambda d: d[0] ** 2 + d[1] ** 2)
        for dx, dy in cand:
            b1 = [b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy]
            ok_in = inside(b1) if inside else not (b1[0] < edge or b1[1] < edge or b1[2] > board.w - edge or b1[3] > board.h - edge)
            if not ok_in or any(ov(b1, p) for p in placed[sd]):
                continue
            if dx or dy:
                f.Move(pcbnew.VECTOR2I(MM(dx), MM(dy))); moved += 1
            placed[sd].append(b1)
            break
        else:
            print("LEGALIZE FAILED for", r)
            placed[sd].append(b0)
    return moved


def point_in_poly(pt, poly):
    x, y = pt; c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def box_in_poly(b, poly, m=0.3):
    pts = [(b[0] - m, b[1] - m), (b[2] + m, b[1] - m), (b[2] + m, b[3] + m), (b[0] - m, b[3] + m),
           ((b[0] + b[2]) / 2, b[1] - m), ((b[0] + b[2]) / 2, b[3] + m), (b[0] - m, (b[1] + b[3]) / 2), (b[2] + m, (b[1] + b[3]) / 2)]
    return all(point_in_poly(p, poly) for p in pts)


def place_labels(board, labels, size=0.7, avoid=(), edge=0.4, back_avoid=()):
    """labels: [(text, x, y)] anchor points (test points). Silk text goes to the first free spot around the anchor
    (no overlap with any footprint courtyard, other labels, `avoid` boxes or the board edge); labels without a free spot are dropped."""
    boxes = [_box(f) for f in board.b.GetFootprints()] + [list(a) for a in avoid]
    placed, dropped = [], []
    for text, x, y in labels:
        w, h = 0.62 * size * len(text), size * 1.1
        cands = []
        for ring in (0.0, 0.8, 1.6):
            r = 0.5 + 0.25 + h / 2 + ring; dx = 0.5 + 0.25 + w / 2 + ring
            cands += [(0, r), (0, -r), (dx, 0), (-dx, 0), (dx, r), (-dx, r), (dx, -r), (-dx, -r)]
        for ox, oy in cands:
            b = [x + ox - w / 2, y + oy - h / 2, x + ox + w / 2, y + oy + h / 2]
            if b[0] < edge or b[1] < edge or b[2] > board.w - edge or b[3] > board.h - edge:
                continue
            if any(b[0] < p[2] and b[2] > p[0] and b[1] < p[3] and b[3] > p[1] for p in boxes + placed):
                continue
            placed.append(b)
            board.text(text, x + ox, y + oy, size, thick=0.1)
            break
        else:
            dropped.append((text, x, y))
    # fallback: back-side silk (the bottom of the controller has no parts), mirrored, directly behind the pad
    bplaced = [[b[0], b[1], b[2], b[3]] for b in (back_avoid or [])]
    still = []
    for text, x, y in dropped:
        w, h = 0.62 * size * len(text), size * 1.1
        for oy in (0, 0.9, -0.9, 1.8, -1.8, 2.7, -2.7):
            for ox in (0, 1.0, -1.0):
                b = [x + ox - w / 2, y + oy - h / 2, x + ox + w / 2, y + oy + h / 2]
                if b[0] < edge or b[2] > board.w - edge or b[1] < edge or b[3] > board.h - edge:
                    continue
                if any(b[0] < p[2] and b[2] > p[0] and b[1] < p[3] and b[3] > p[1] for p in bplaced):
                    continue
                bplaced.append(b); board.text(text, x + ox, y + oy, size, layer=pcbnew.B_SilkS, mirror=True, thick=0.1)
                break
            else:
                continue
            break
        else:
            still.append(text)
    return still


def tidy_refs(board, hide_prefixes=("R", "C", "TP"), size=0.7):
    import re
    for f in board.b.GetFootprints():
        r = f.GetReference()
        f.Reference().SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        f.Reference().SetTextThickness(MM(0.1))
        if re.match(r"^(%s)\d" % "|".join(hide_prefixes), r) or r.startswith("H"):
            f.Reference().SetVisible(False)
