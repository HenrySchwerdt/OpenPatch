#!/usr/bin/env python3
"""Finish the routing of cup.kicad_pcb with a grid maze router (KiCad python).

Freerouting 2.2.4 routes this board to about 37 open connections and hangs on any pre-routed trunk, so the rest is done here:
every unconnected pair that KiCad's DRC reports is routed one at a time by A* on a 0.05 mm grid over F.Cu, In2..In4 and B.Cu
(In1 is the GND plane: only crossed by vias), with 0.4 / 0.2 mm vias, 0.10 mm signal / 0.16 mm power tracks and the board rules
(0.10 mm copper clearance, 0.25 mm copper to edge, rule areas). GND gaps are left to the pours and stitching of route_v3 finish.

usage: kpy finish_route.py cup.kicad_pcb drc.json   (writes the board in place, prints routed / failed)
"""
import heapq
import json
import math
import os
import re
import sys

import numpy as np
from matplotlib.path import Path
from scipy import ndimage

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
POWERNETS = ("VBAT", "VMOT", "VMOT_PRE", "BST_SW", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2", "VBUS_P")      # same as build_cup.POWERNETS

T, MM = pcbnew.ToMM, pcbnew.FromMM
G = 0.05                     # grid (mm)
CLR = 0.10                   # copper clearance
EDGE = 0.25                  # copper to board edge
VIA_D, VIA_H = (float(v) for v in os.environ.get("OP_VIA", "0.30/0.15").split("/"))     # routing vias; 0.15 drill is the board's fan-out drill already (POFV)
HOLE_CLR = 0.20             # copper to hole wall (board rule min_hole_clearance)
VIA_COST = 30.0              # in grid steps
MAX_EXPAND = 3_000_000
# In1 is the GND plane; with OP_IN1=1 (owner decision 2026-11-21) it may carry short signal pieces outside the zones in IN1_SOLID
IN1 = os.environ.get("OP_IN1", "1") == "1"
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu] + ([pcbnew.In1_Cu] if IN1 else [])
ALL_CU = LAYERS + ([] if IN1 else [pcbnew.In1_Cu])
# board-frame rectangles where In1 stays solid ground: HJ-840 + antenna strip (+0.6), USB bridge with the D+/D- pair
IN1_SOLID = [(27.7, -0.5, 36.0, 9.1)]      # module + antenna strip; the USB bridge is open too (full-speed USB 12 Mbit/s; within the owner decision of 2026-11-21 to use In1 partially)
OX, OY = 100.0, 80.0
IN1_COST = 2.0               # In1 steps cost twice as much: used only where the signal layers are full


def width_of(net):
    return 0.16 if net in POWERNETS else 0.10


class Grid:
    def __init__(self, b):
        bb = b.GetBoardEdgesBoundingBox()
        self.x0, self.y0 = T(bb.GetLeft()) - 0.5, T(bb.GetTop()) - 0.5
        self.nx = int((T(bb.GetWidth()) + 1.0) / G) + 1
        self.ny = int((T(bb.GetHeight()) + 1.0) / G) + 1
        xs = self.x0 + G * np.arange(self.nx)
        ys = self.y0 + G * np.arange(self.ny)
        self.cx, self.cy = np.meshgrid(xs, ys, indexing="ij")

    def idx(self, x, y):
        return int(round((x - self.x0) / G)), int(round((y - self.y0) / G))

    def xy(self, i, j):
        return self.x0 + G * i, self.y0 + G * j

    def fill_poly(self, arr, pts, value_fn):
        pts = np.asarray(pts)
        if len(pts) < 3:
            return
        i0, j0 = self.idx(pts[:, 0].min(), pts[:, 1].min())
        i1, j1 = self.idx(pts[:, 0].max(), pts[:, 1].max())
        i0, j0 = max(i0 - 1, 0), max(j0 - 1, 0)
        i1, j1 = min(i1 + 2, self.nx), min(j1 + 2, self.ny)
        if i1 <= i0 or j1 <= j0:
            return
        sub = np.stack([self.cx[i0:i1, j0:j1].ravel(), self.cy[i0:i1, j0:j1].ravel()], 1)
        m = Path(pts).contains_points(sub).reshape(i1 - i0, j1 - j0)
        value_fn(arr, (slice(i0, i1), slice(j0, j1)), m)


def poly_points(sps):
    out = []
    for k in range(sps.OutlineCount()):
        o = sps.Outline(k)
        out.append([(T(o.CPoint(n).x), T(o.CPoint(n).y)) for n in range(o.PointCount())])
    return out


def item_poly(item, layer, inflate):
    sps = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(sps, layer, MM(inflate), MM(0.005), pcbnew.ERROR_OUTSIDE)
    return poly_points(sps)


def mark_owner(arr, sl, m, net):
    sub = arr[sl]
    free = m & (sub == 0)
    other = m & (sub != 0) & (sub != net)
    sub[free] = net
    sub[other] = -1


class Router:
    def __init__(self, b):
        self.b = b
        self.g = Grid(b)
        self.netcode = {}
        # owner grids per track width class: 0 free, >0 net code, -1 blocked
        self.own = {w: np.zeros((len(LAYERS), self.g.nx, self.g.ny), np.int32) for w in (0.10, 0.16)}
        self.viablock = np.zeros((self.g.nx, self.g.ny), bool)
        self.cu = np.zeros((len(LAYERS), self.g.nx, self.g.ny), np.int32)     # actual copper: net code, -1 = copper without net
        self._edges()
        self._keepouts()
        self._in1_solid()
        for t in b.GetTracks():
            self.add_item(t)
        for f in b.GetFootprints():
            for p in f.Pads():
                self.add_item(p)

    def _edges(self):
        sps = pcbnew.SHAPE_POLY_SET()
        self.b.GetBoardPolygonOutlines(sps, True)
        inside = np.zeros((self.g.nx, self.g.ny), bool)
        for pts in poly_points(sps):
            self.g.fill_poly(inside, pts, lambda a, sl, m: a.__setitem__(sl, a[sl] | m))
        for w, own in self.own.items():
            r = int(math.ceil((EDGE + w / 2) / G))
            ok = ndimage.binary_erosion(inside, structure=disk(r))
            for li in range(len(LAYERS)):
                own[li][~ok] = -1
        r = int(math.ceil((EDGE + VIA_D / 2) / G))
        self.viablock |= ~ndimage.binary_erosion(inside, structure=disk(r))

    def _in1_solid(self):
        if pcbnew.In1_Cu not in LAYERS:
            return
        li = LAYERS.index(pcbnew.In1_Cu)
        for x0, y0, x1, y1 in IN1_SOLID:
            pts = [(OX + x0, OY + y0), (OX + x1, OY + y0), (OX + x1, OY + y1), (OX + x0, OY + y1)]
            for w, own in self.own.items():
                self.g.fill_poly(own[li], pts, lambda a, sl, m: a[sl].__setitem__(m, -1))

    def _keepouts(self):
        for z in self.b.Zones():
            if not z.GetIsRuleArea():
                continue
            pts = [(T(z.Outline().COutline(0).CPoint(n).x), T(z.Outline().COutline(0).CPoint(n).y)) for n in range(z.Outline().COutline(0).PointCount())]
            for li, l in enumerate(LAYERS):
                if not z.IsOnLayer(l):
                    continue
                if z.GetDoNotAllowTracks():
                    for w, own in self.own.items():
                        m = np.zeros((self.g.nx, self.g.ny), bool)
                        self.g.fill_poly(m, pts, lambda a, sl, mm: a.__setitem__(sl, a[sl] | mm))
                        m = ndimage.binary_dilation(m, structure=disk(int(math.ceil(w / 2 / G))))
                        own[li][m] = -1
            if z.GetDoNotAllowVias():
                m = np.zeros((self.g.nx, self.g.ny), bool)
                self.g.fill_poly(m, pts, lambda a, sl, mm: a.__setitem__(sl, a[sl] | mm))
                self.viablock |= ndimage.binary_dilation(m, structure=disk(int(math.ceil(VIA_D / 2 / G))))

    def add_item(self, item):
        net = item.GetNetCode()
        if item.Type() == pcbnew.PCB_PAD_T and item.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            net = 0
        mark = net if net > 0 else -1
        for li, l in enumerate(LAYERS):
            if item.Type() == pcbnew.PCB_VIA_T:
                on = True
            elif item.Type() == pcbnew.PCB_PAD_T:
                on = item.IsOnLayer(l) or (item.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)
            else:
                on = item.GetLayer() == l
            if not on:
                continue
            lay = l if item.Type() != pcbnew.PCB_PAD_T or item.IsOnLayer(l) else pcbnew.F_Cu
            for pts in item_poly(item, lay, 0.0):
                self.g.fill_poly(self.cu[li], pts, lambda a, sl, m: a[sl].__setitem__(m, mark))
            for w, own in self.own.items():
                for pts in item_poly(item, lay, CLR + w / 2 + 0.01):
                    self.g.fill_poly(own[li], pts, lambda a, sl, m: mark_owner(a, sl, m, mark) if mark > 0 else a[sl].__setitem__(m, -1))
        # drilled pads: copper keeps HOLE_CLR from the hole wall on every layer (NPTH have no copper of their own), vias keep it too
        if item.Type() == pcbnew.PCB_PAD_T and item.GetDrillSizeX() > 0:
            for w, own in self.own.items():
                sps = pcbnew.SHAPE_POLY_SET()
                item.TransformHoleToPolygon(sps, MM(HOLE_CLR + w / 2 + 0.01), MM(0.005), pcbnew.ERROR_OUTSIDE)
                for pts in poly_points(sps):
                    for li in range(len(LAYERS)):
                        self.g.fill_poly(own[li], pts, lambda a, sl, m: mark_owner(a, sl, m, mark) if mark > 0 else a[sl].__setitem__(m, -1))
            sps = pcbnew.SHAPE_POLY_SET()
            item.TransformHoleToPolygon(sps, MM(HOLE_CLR + VIA_D / 2 + 0.01), MM(0.005), pcbnew.ERROR_OUTSIDE)
            for pts in poly_points(sps):
                self.g.fill_poly(self.viablock, pts, lambda a, sl, m: a.__setitem__(sl, a[sl] | m))

    # ------------------------------------------------------------------ search
    def route(self, net, starts, goals, to_via=False):
        w = width_of(self.b.GetNetInfo().GetNetItem(net).GetNetname())
        own = self.own[w]
        pas = (own == 0) | (own == net)
        rv = int(math.ceil((VIA_D / 2 + CLR - (CLR + w / 2 + 0.01)) / G)) + 1
        via_ok = ~self.viablock.copy()
        for li in range(len(LAYERS)):
            via_ok &= ndimage.binary_erosion(pas[li], structure=disk(rv), border_value=0)
        if to_via:
            goalset = None

            def h(i, j):
                return 0.0
        else:
            goals = [q for q in goals if pas[q]]
            if not goals:
                return None, w
            goalset = set(goals)
            gx = np.array([g[1] for g in goals]); gy = np.array([g[2] for g in goals])
            tx, ty = gx.mean(), gy.mean()
            trad = max(np.hypot(gx - tx, gy - ty).max(), 0)

            def h(i, j):
                d = math.hypot(i - tx, j - ty) - trad
                return d if d > 0 else 0.0

        best = {}
        came = {}
        pq = []
        for s in starts:
            if not pas[s]:
                continue
            best[s] = 0.0
            heapq.heappush(pq, (h(s[1], s[2]), 0.0, s))
        dirs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
        n = 0
        while pq:
            f, gc, s = heapq.heappop(pq)
            if gc > best.get(s, 1e18) + 1e-9:
                continue
            if (goalset is not None and s in goalset) or (goalset is None and via_ok[s[1], s[2]]):
                path = [s]
                while path[-1] in came:
                    path.append(came[path[-1]])
                return path[::-1], w
            n += 1
            if n > MAX_EXPAND:
                return None, w
            li, i, j = s
            for di, dj, c in dirs:
                ni, nj = i + di, j + dj
                if not (0 <= ni < self.g.nx and 0 <= nj < self.g.ny) or not pas[li, ni, nj]:
                    continue
                if di and dj and not (pas[li, i + di, j] and pas[li, i, j + dj]):
                    continue
                t = (li, ni, nj)
                ng = gc + c
                if ng < best.get(t, 1e18):
                    best[t] = ng; came[t] = s
                    heapq.heappush(pq, (ng + h(ni, nj), ng, t))
            if via_ok[i, j] and goalset is not None:
                for lj in range(len(LAYERS)):
                    if lj == li:
                        continue
                    t = (lj, i, j)
                    ng = gc + VIA_COST
                    if ng < best.get(t, 1e18):
                        best[t] = ng; came[t] = s
                        heapq.heappush(pq, (ng + h(i, j), ng, t))
        return None, w

    def commit(self, net, path, w, end_via=False):
        items = []
        if end_via:
            v = pcbnew.PCB_VIA(self.b); x, y = self.g.xy(path[-1][1], path[-1][2])
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetNet(self.b.GetNetInfo().GetNetItem(net)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); self.b.Add(v); items.append(v)
        # compress into straight runs
        k = 0
        while k < len(path) - 1:
            a = path[k]
            b2 = path[k + 1]
            if b2[0] != a[0]:
                v = pcbnew.PCB_VIA(self.b); x, y = self.g.xy(a[1], a[2])
                v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetNet(self.b.GetNetInfo().GetNetItem(net)); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); self.b.Add(v); items.append(v)
                k += 1
                continue
            d = (b2[1] - a[1], b2[2] - a[2])
            e = k + 1
            while e + 1 < len(path) and path[e + 1][0] == a[0] and (path[e + 1][1] - path[e][1], path[e + 1][2] - path[e][2]) == d:
                e += 1
            t = pcbnew.PCB_TRACK(self.b)
            x0, y0 = self.g.xy(a[1], a[2]); x1, y1 = self.g.xy(path[e][1], path[e][2])
            t.SetStart(pcbnew.VECTOR2I(MM(x0), MM(y0))); t.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
            t.SetLayer(LAYERS[a[0]]); t.SetWidth(MM(w)); t.SetNet(self.b.GetNetInfo().GetNetItem(net)); self.b.Add(t); items.append(t)
            k = e
        for it in items:
            self.add_item(it)
        self.last_items = items
        return len(items)

    def cells_of(self, item):
        """grid cells (layer index, i, j) that lie inside the copper of item"""
        out = []
        for li, l in enumerate(LAYERS):
            if item.Type() == pcbnew.PCB_VIA_T:
                on = True
            elif item.Type() == pcbnew.PCB_PAD_T:
                on = item.IsOnLayer(l)
            else:
                on = item.GetLayer() == l
            if not on:
                continue
            m = np.zeros((self.g.nx, self.g.ny), bool)
            for pts in item_poly(item, l, -0.01):
                self.g.fill_poly(m, pts, lambda a, sl, mm: a.__setitem__(sl, a[sl] | mm))
            if not m.any():          # very thin item: take the cell nearest to its position
                i, j = self.g.idx(T(item.GetPosition().x), T(item.GetPosition().y))
                m[i, j] = True
            for i, j in zip(*np.nonzero(m)):
                out.append((li, int(i), int(j)))
        return out


def disk(r):
    r = max(int(r), 0)
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r + 0.5


def find_item(b, desc, pos):
    m = re.search(r"\[([^\]]+)\]", desc)
    net = m.group(1) if m else None
    px, py = pos["x"], pos["y"]
    best = None
    cands = []
    if desc.startswith(("Pad", "PTH pad")):
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname() == net:
                    cands.append(p)
    elif desc.startswith(("Track", "Via")):
        cands = [t for t in b.GetTracks() if t.GetNetname() == net]
    for c in cands:
        d = c.GetPosition()
        if c.Type() == pcbnew.PCB_TRACE_T:
            s, e = c.GetStart(), c.GetEnd()
            dd = min(math.hypot(T(s.x) - px, T(s.y) - py), math.hypot(T(e.x) - px, T(e.y) - py), seg_dist(px, py, s, e))
        else:
            dd = math.hypot(T(d.x) - px, T(d.y) - py)
        if best is None or dd < best[0]:
            best = (dd, c)
    return (best[1], net) if best and best[0] < 0.05 else (None, net)


def seg_dist(px, py, s, e):
    ax, ay, bx, by = T(s.x), T(s.y), T(e.x), T(e.y)
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


ORDER_FIRST = ["BST_SW", "VMOT_PRE", "VMOT", "VBAT", "MOT_A1", "MOT_A2", "MOT_B1", "MOT_B2", "USB_DP", "USB_DM", "VBUS_P", "CC1", "CC2", "ANT"]


def route_all(pcb):
    """route every net of a placed board (only the fixed fan-out copper present): GND pads -> nearest via (In1 plane) first,
    then the power / USB nets, then the remaining nets by ascending bounding box; each net grows a tree pad by pad"""
    b = pcbnew.LoadBoard(pcb)
    R = Router(b)
    pads = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() > 0 and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                pads.setdefault(p.GetNetname(), []).append(p)
    gnd = b.GetNetInfo().GetNetItem("GND").GetNetCode() if "GND" in pads else None
    fails = []

    def bbox(n):
        xs = [T(p.GetPosition().x) for p in pads[n]]; ys = [T(p.GetPosition().y) for p in pads[n]]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))
    order = [n for n in ORDER_FIRST if n in pads] + sorted([n for n in pads if n not in ORDER_FIRST and n != "GND"], key=bbox)
    for n in order:
        pl = pads[n]
        if len(pl) < 2:
            continue
        code = pl[0].GetNetCode()
        tree = R.cells_of(pl[0])
        left = pl[1:]
        while left:
            tx = np.mean([q[1] for q in tree]); ty = np.mean([q[2] for q in tree])
            left.sort(key=lambda p: math.hypot(R.g.idx(T(p.GetPosition().x), 0)[0] - tx, R.g.idx(0, T(p.GetPosition().y))[1] - ty))
            p = left.pop(0)
            goal = R.cells_of(p)
            if set(goal) & set(tree):
                tree += goal; continue
            path, w = R.route(code, tree, goal)
            if path is None:
                fails.append((n, p.GetParentFootprint().GetReference() + "." + p.GetNumber()))
                print("FAIL", n, fails[-1][1], flush=True)
                tree += goal          # keep growing from the pad (the gap is reported)
                continue
            R.commit(code, path, w)
            for it in R.last_items:
                tree += R.cells_of(it)
            tree += goal
        print("net", n, "done", flush=True)
    gfails = []
    # last: GND: every SMD GND pad without a via of its own gets a short stub to a via
    vias_at = [(T(t.GetPosition().x), T(t.GetPosition().y)) for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
    for p in pads.get("GND", []):
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        px, py = T(p.GetPosition().x), T(p.GetPosition().y)
        if any(math.hypot(px - x, py - y) < 0.05 for x, y in vias_at):
            continue
        path, w = R.route(gnd, R.cells_of(p), None, to_via=True)
        if path is None:
            gfails.append(p.GetParentFootprint().GetReference() + "." + p.GetNumber()); continue
        R.commit(gnd, path, w, end_via=True)
    print("GND pads without a via (left to the pours):", gfails, flush=True)
    pcbnew.SaveBoard(pcb, b)
    print("FAILED", len(fails), fails)


def main():
    if sys.argv[1] == "--all":
        route_all(sys.argv[2])
        return
    pcb, drc = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(pcb)
    d = json.load(open(drc))
    R = Router(b)
    jobs = []
    for u in d["unconnected_items"]:
        if len(u["items"]) != 2:
            continue
        a, na = find_item(b, u["items"][0]["description"], u["items"][0]["pos"])
        c, nc = find_item(b, u["items"][1]["description"], u["items"][1]["pos"])
        if na == "GND" or a is None or c is None:
            continue
        dist = math.hypot(u["items"][0]["pos"]["x"] - u["items"][1]["pos"]["x"], u["items"][0]["pos"]["y"] - u["items"][1]["pos"]["y"])
        jobs.append((dist, na, a, c))
    jobs.sort(key=lambda j: j[0])
    ok, fail = 0, []
    for dist, net, a, c in jobs:
        code = a.GetNetCode()
        starts, goals = R.cells_of(a), R.cells_of(c)
        path, w = R.route(code, starts, goals)
        if path is None:
            path, w = R.route(code, goals, starts)
        if path is None:
            fail.append((net, round(dist, 1)))
            print("FAIL", net, round(dist, 1), flush=True)
            continue
        n = R.commit(code, path, w)
        ok += 1
        print("ok  ", net, round(dist, 1), "items", n, flush=True)
    pcbnew.SaveBoard(pcb, b)
    print("routed", ok, "failed", len(fail), fail)


if __name__ == "__main__":
    main()
