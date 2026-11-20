#!/usr/bin/env python3
"""Deterministic routing of the critical nets (KiCad python): A* maze router on a 0.05 mm grid over the signal layers
F.Cu, In2, In3, In4, B.Cu (In1 = GND plane), writes pcbnew tracks and vias, then Freerouting handles the rest (existing wiring is protected).

usage: kpy route_critical.py [cup.kicad_pcb]     order and widths: see NETS below (same list as cup/ROUTING-GUIDE.md)"""
import heapq
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bench", "tools"))
import pcbnew
import benchlib as bl

MM = pcbnew.FromMM
T = pcbnew.ToMM
G = 0.1
CLR = 0.10
VIA_D, VIA_H = 0.40, 0.20
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
LNAME = {l: i for i, l in enumerate(LAYERS)}
# (net, width, preferred layers or None, [pads to exclude from the tree: Kelvin or dedicated])
NETS = [
    ("KELVIN_PRE", 0.15, None), ("KELVIN_MOT", 0.15, None),          # shunt sense: U9 IN+ / IN- straight to the shunt pads
    ("VMOT_RAW", 0.40, None), ("BST_SW", 0.40, None), ("VMOT_PRE", 0.40, None), ("VMOT", 0.30, None),
    ("MOT_A1", 0.20, None), ("MOT_A2", 0.20, None), ("MOT_B1", 0.20, None), ("MOT_B2", 0.20, None),
    ("SNSA", 0.20, None), ("SNSB", 0.20, None), ("VBAT", 0.30, None), ("VMOT_A", 0.30, None),
    ("USB_DP", 0.12, None), ("USB_DM", 0.12, None),
]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "cup.kicad_pcb")
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = T(bb.GetLeft()), T(bb.GetTop())
    W, H = int((T(bb.GetRight()) - x0) / G) + 2, int((T(bb.GetBottom()) - y0) / G) + 2
    nl = len(LAYERS)
    own = [dict() for _ in range(nl)]           # cell -> net code (or -1 = several nets)
    code = {}

    def netcode(n):
        return code.setdefault(n, len(code) + 1)

    # board outline mask: inside polygon test through edge segments (even-odd)
    segs = []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            segs.append((T(d.GetStart().x), T(d.GetStart().y), T(d.GetEnd().x), T(d.GetEnd().y)))

    def inside(x, y):
        c = False
        for ax, ay, bx, by in segs:
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                c = not c
        return c

    def seg_d(x, y, s):
        ax, ay, bx, by = s
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(x - ax - t * dx, y - ay - t * dy)

    def mark(li, xa, ya, xb, yb, nc, infl):
        i0, i1 = int((xa - infl - x0) / G), int((xb + infl - x0) / G) + 1
        j0, j1 = int((ya - infl - y0) / G), int((yb + infl - y0) / G) + 1
        d = own[li]
        for i in range(max(i0, 0), min(i1, W)):
            for j in range(max(j0, 0), min(j1, H)):
                k = (i, j)
                v = d.get(k)
                d[k] = nc if v is None or v == nc else -1

    def lidx(layer):
        return LNAME.get(layer)

    for f in b.GetFootprints():
        for pd in f.Pads():
            r = pd.GetBoundingBox()
            xa, ya, xb, yb = T(r.GetLeft()), T(r.GetTop()), T(r.GetRight()), T(r.GetBottom())
            nc = netcode(pd.GetNetname()) if pd.GetNetname() else -1
            for li, l in enumerate(LAYERS):
                if pd.IsOnLayer(l):
                    mark(li, xa, ya, xb, yb, nc, CLR)
    for t in b.GetTracks():
        nc = netcode(t.GetNetname()) if t.GetNetname() else -1
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y, rr = T(t.GetPosition().x), T(t.GetPosition().y), T(t.GetWidth(pcbnew.F_Cu)) / 2
            for li in range(nl):
                mark(li, x - rr, y - rr, x + rr, y + rr, nc, CLR)
        else:
            li = lidx(t.GetLayer())
            if li is not None:
                x1, y1, x2, y2 = T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y)
                mark(li, min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), nc, CLR + T(t.GetWidth()) / 2)
    # keep-out zones (antenna) block everything
    for z in b.Zones():
        if z.GetIsRuleArea():
            zb = z.GetBoundingBox()
            for li in range(nl):
                mark(li, T(zb.GetLeft()), T(zb.GetTop()), T(zb.GetRight()), T(zb.GetBottom()), -1, 0.0)
    outside_cache = {}

    memo = {}

    def free(li, i, j, nc, w):
        k0 = (li, i, j, nc, w)
        v0 = memo.get(k0)
        if v0 is None:
            v0 = memo[k0] = _free(li, i, j, nc, w)
        return v0

    def _free(li, i, j, nc, w):
        """cell centre free for a track of width w of net nc (checks the inflated footprint of the track: half width)"""
        r = int(math.ceil(w / 2 / G))
        d = own[li]
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                v = d.get((i + di, j + dj))
                if v is not None and v != nc:
                    return False
        x, y = x0 + i * G, y0 + j * G
        key = (i, j)
        o = outside_cache.get(key)
        if o is None:
            o = inside(x, y) and min(seg_d(x, y, s) for s in segs) >= 0.45
            outside_cache[key] = o
        return o

    def via_ok(i, j, nc):
        r = int(math.ceil((VIA_D / 2) / G))
        for li in range(nl):
            d = own[li]
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    v = d.get((i + di, j + dj))
                    if v is not None and v != nc:
                        return False
        x, y = x0 + i * G, y0 + j * G
        key = (i, j)
        o = outside_cache.get(key)
        if o is None:
            o = inside(x, y) and min(seg_d(x, y, s) for s in segs) >= 0.45
            outside_cache[key] = o
        return o

    def astar(starts, goals, nc, w):
        goalset = set(goals)
        pq = []
        best = {}
        for s in starts:
            best[s] = 0
            heapq.heappush(pq, (0, s, None))
        prev = {}
        gx = [g for g in goals]
        while pq:
            c, s, p = heapq.heappop(pq)
            if best.get(s, 1e9) < c - 1e-9:
                continue
            prev[s] = p
            if s in goalset:
                path = []
                while s is not None:
                    path.append(s); s = prev[s]
                return path[::-1]
            li, i, j = s
            nbrs = [(li, i + 1, j, 1.0), (li, i - 1, j, 1.0), (li, i, j + 1, 1.0), (li, i, j - 1, 1.0),
                    (li, i + 1, j + 1, 1.41), (li, i - 1, j - 1, 1.41), (li, i + 1, j - 1, 1.41), (li, i - 1, j + 1, 1.41)]
            for nli in (li - 1, li + 1):
                if 0 <= nli < nl:
                    nbrs.append((nli, i, j, 60.0))
            for nli, ni, nj, cost in nbrs:
                if not (0 <= ni < W and 0 <= nj < H):
                    continue
                t = (nli, ni, nj)
                nc2 = c + cost
                if best.get(t, 1e9) <= nc2:
                    continue
                if nli != li:
                    if not via_ok(ni, nj, nc):
                        continue
                elif not free(nli, ni, nj, nc, w):
                    continue
                if abs(ni - i) + abs(nj - j) == 2 and not (free(li, i + (ni - i), j, nc, w) and free(li, i, j + (nj - j), nc, w)):
                    continue
                best[t] = nc2
                heapq.heappush(pq, (nc2 + 0.0, t, s))
        return None

    # pad lists by net
    pads = {}
    for f in b.GetFootprints():
        for pd in f.Pads():
            if pd.GetNetname():
                pads.setdefault(pd.GetNetname(), []).append((f.GetReference(), pd))

    def cell_of(pt):
        return int(round((T(pt.x) - x0) / G)), int(round((T(pt.y) - y0) / G))

    def pad_cells(pd):
        r = pd.GetBoundingBox()
        out = []
        for l in LAYERS:
            if pd.IsOnLayer(l):
                li = LNAME[l]
                i0, i1 = int((T(r.GetLeft()) - x0) / G) + 1, int((T(r.GetRight()) - x0) / G)
                j0, j1 = int((T(r.GetTop()) - y0) / G) + 1, int((T(r.GetBottom()) - y0) / G)
                ci, cj = cell_of(pd.GetPosition())
                out.append((li, ci, cj))
                for i in range(i0, i1 + 1, 2):
                    for j in range(j0, j1 + 1, 2):
                        out.append((li, i, j))
        return out

    added = []

    def emit(path, nc_name, w, netinfo):
        # compress to segments / vias
        pts = [(x0 + i * G, y0 + j * G, li) for li, i, j in path]
        k = 0
        while k < len(pts) - 1:
            xa, ya, la = pts[k]
            if pts[k + 1][2] != la:
                v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(xa), MM(ya))); v.SetNet(netinfo); v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); b.Add(v); added.append(v)
                k += 1
                continue
            m = k + 1
            dx, dy = pts[m][0] - xa, pts[m][1] - ya
            while m + 1 < len(pts) and pts[m + 1][2] == la and abs((pts[m + 1][0] - pts[m][0]) - dx) < 1e-6 and abs((pts[m + 1][1] - pts[m][1]) - dy) < 1e-6 and \
                    abs(pts[m][0] - pts[m - 1][0] - dx) < 1e-6:
                m += 1
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(MM(xa), MM(ya))); t.SetEnd(pcbnew.VECTOR2I(MM(pts[m][0]), MM(pts[m][1])))
            t.SetLayer(LAYERS[la]); t.SetWidth(MM(w)); t.SetNet(netinfo); b.Add(t); added.append(t)
            k = m
        # register in the obstacle map
        for li, i, j in path:
            nc = netcode(nc_name)
            r = int(math.ceil((w / 2 + CLR) / G))
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    k2 = (i + di, j + dj)
                    v = own[li].get(k2)
                    own[li][k2] = nc if v is None or v == nc else -1

    def route_net(name, width, pad_list, report):
        netinfo = b.FindNet(name)
        nc = netcode(name)
        if len(pad_list) < 2:
            return
        # Prim tree: connect the nearest unconnected pad to the connected set
        conn = [pad_list[0]]
        rest = pad_list[1:]
        tree_cells = set(pad_cells(pad_list[0][1]))
        ok = True
        while rest:
            rest.sort(key=lambda r: min(math.hypot(T(r[1].GetPosition().x) - T(c[1].GetPosition().x), T(r[1].GetPosition().y) - T(c[1].GetPosition().y)) for c in conn))
            r = rest.pop(0)
            starts = pad_cells(r[1])
            # allow the start cells (pad area) regardless of the occupancy map: they carry the net
            path = None
            for w in (width, max(0.15, width * 0.6), 0.12):
                path = astar(starts, tree_cells, nc, w)
                if path:
                    break
            if not path:
                report.append("FAIL %s %s.%s" % (name, r[0], r[1].GetNumber()))
                ok = False
                continue
            emit(path, name, w, netinfo)
            for s in path:
                tree_cells.add(s)
            conn.append(r)
        report.append("%s %s" % (name, "ok" if ok else "PARTIAL"))

    report = []
    for name, width, _ in NETS:
        if name == "KELVIN_PRE":
            u9 = [p for p in pads.get("VMOT_PRE", []) if p[0] == "U9" and p[1].GetNumber() == "3"]
            r44 = [p for p in pads.get("VMOT_PRE", []) if p[0] == "R44"]
            route_net("VMOT_PRE", width, u9 + r44, report)
        elif name == "KELVIN_MOT":
            u9 = [p for p in pads.get("VMOT", []) if p[0] == "U9" and p[1].GetNumber() == "4"]
            r44 = [p for p in pads.get("VMOT", []) if p[0] == "R44"]
            route_net("VMOT", width, u9 + r44, report)
        else:
            pl = [p for p in pads.get(name, []) if not (p[0] == "U9")]
            if name in ("VMOT_PRE", "VMOT"):
                pl = [p for p in pl if p[0] != "R44"] + [p for p in pads.get(name, []) if p[0] == "R44"][:1]
            route_net(name, width, pl, report)
    b.BuildListOfNets()
    pcbnew.SaveBoard(path, b)
    print("\n".join(report))
    print("tracks/vias added:", len(added))


if __name__ == "__main__":
    main()
