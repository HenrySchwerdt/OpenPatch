#!/usr/bin/env python3
"""Negotiated-congestion router (PathFinder style) for the cup board (KiCad python).

Why: Freerouting 2.2.4 stalls at about 37 open connections on this board and hangs on pre-routed trunks; a plain sequential maze
router fails on ordering (early nets wall in later ones). Here every net is routed on a 0.05 mm grid over F.Cu, In2..In4, B.Cu
(In1 = GND plane, crossed by vias only), nets may overlap at a price, and the price of contested cells grows every iteration
until no two nets share space. Fixed copper (pads, fan-out vias, the A7-A8 bridge, keep-outs, the board edge) is never crossed.

Clearance model: a net's "footprint" is its centre line dilated by its half width + 0.10 mm clearance + 0.08 mm (the widest other
half width), so another net's centre line outside it keeps >= 0.10 mm copper clearance. Vias 0.4 / 0.2 mm.

usage: kpy nego_route.py in.kicad_pcb out.kicad_pcb [iterations]
"""
import heapq
import math
import sys
import time

import numpy as np
from scipy import ndimage

import pcbnew
import finish_route as FR

T, MM = pcbnew.ToMM, pcbnew.FromMM
G = FR.G
LAYERS = FR.LAYERS
NL = len(LAYERS)
CLR, VIA_D, VIA_H = 0.10, 0.40, 0.20
OTHER_HALF = 0.05        # signal half width; a power net (0.16 mm) carries the larger footprint itself, conflicts are checked both ways
VIA_COST = 25.0
HW = 1.4                     # weighted A*: heuristic weight (keeps the search and its heap small under congestion costs)
SQ2 = math.sqrt(2.0)
DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2)]


def fp_radius(w):
    return w / 2 + CLR + OTHER_HALF


class Nego:
    def __init__(self, b):
        self.b = b
        R = FR.Router(b)              # fixed copper only (the board must not hold routed tracks yet)
        self.R = R
        self.g = R.g
        self.fixed = R.own            # {width: owner grid}, fixed items only
        self.viablock = R.viablock
        self.nx, self.ny = self.g.nx, self.g.ny
        self.cnt = np.zeros((NL, self.nx, self.ny), np.int16)      # how many routed nets cover each cell with their footprint
        self.hist = np.zeros((NL, self.nx, self.ny), np.float32)
        self.paths = {}               # net -> list of paths [(layer, i, j), ...]
        self.fpcells = {}             # net -> boolean footprint mask (NL, nx, ny) as index arrays
        self.disk = {}

    def dsk(self, r_mm):
        r = int(math.ceil(r_mm / G - 1e-9))
        if r not in self.disk:
            self.disk[r] = FR.disk(r)
        return self.disk[r]

    # ---------------------------------------------------------------- footprints
    def footprint(self, net, w, paths):
        m = np.zeros((NL, self.nx, self.ny), bool)
        vias = np.zeros((self.nx, self.ny), bool)
        for p in paths:
            for k, (l, i, j) in enumerate(p):
                m[l, i, j] = True
                if k + 1 < len(p) and p[k + 1][0] != l:
                    vias[i, j] = True
        for l in range(NL):
            if m[l].any():
                m[l] = ndimage.binary_dilation(m[l], structure=self.dsk(fp_radius(w)))
        if vias.any():
            vd = ndimage.binary_dilation(vias, structure=self.dsk(VIA_D / 2 + CLR + OTHER_HALF))
            m |= vd[None, :, :]
        return np.flatnonzero(m).astype(np.int32)

    def add_fp(self, net, idx, s):
        self.cnt.ravel()[idx] += s

    # ---------------------------------------------------------------- search
    def astar(self, net, w, starts, goals, pres, to_via=False):
        fixed = self.fixed[w]
        pas = (fixed == 0) | (fixed == net)
        other = np.maximum(self.cnt, 0)                         # this net's own footprint was taken out of cnt before the call
        cost = 1.0 + pres * other.astype(np.float32) + self.hist
        rv = int(math.ceil((VIA_D / 2 + CLR - (CLR + w / 2 + 0.01)) / G)) + 1
        via_ok = ~self.viablock
        for l in range(NL):
            via_ok = via_ok & ndimage.binary_erosion(pas[l], structure=FR.disk(rv), border_value=0)
        vcost = VIA_COST + pres * other.max(axis=0).astype(np.float32) * 4 + self.hist.max(axis=0) * 4
        if to_via:
            goalset = None
            tx = ty = 0.0
            trad = 0.0
        else:
            goals = [q for q in goals if pas[q]]
            if not goals:
                return None
            goalset = set(goals)
            gx = np.array([q[1] for q in goals], float); gy = np.array([q[2] for q in goals], float)
            tx, ty = gx.mean(), gy.mean()
            trad = float(np.hypot(gx - tx, gy - ty).max())
        nx, ny = self.nx, self.ny
        plane = nx * ny
        best = np.full(NL * plane, np.inf, np.float32)
        came = np.full(NL * plane, -1, np.int32)
        pas_f = pas.ravel(); cost_f = cost.ravel(); via_f = via_ok.ravel()
        goal_f = None
        if goalset is not None:
            goal_f = np.zeros(NL * plane, bool)
            for (l, i, j) in goalset:
                goal_f[(l * nx + i) * ny + j] = True
        pq = []
        for (l, i, j) in starts:
            k = (l * nx + i) * ny + j
            if pas_f[k] and best[k] > 0:
                best[k] = 0.0
                heapq.heappush(pq, (0.0, 0.0, k))
        nexp = 0
        steps = [(di * ny + dj, di, dj, c) for di, dj, c in DIRS]
        while pq:
            f, gc, k = heapq.heappop(pq)
            if gc > best[k] + 1e-6:
                continue
            l, r = divmod(k, plane)
            i, j = divmod(r, ny)
            if (goal_f is not None and goal_f[k]) or (goal_f is None and via_f[r]):
                path = [k]
                while came[path[-1]] >= 0:
                    path.append(int(came[path[-1]]))
                out = []
                for q in path[::-1]:
                    ll, rr = divmod(q, plane)
                    out.append((ll, rr // ny, rr % ny))
                return out
            nexp += 1
            if nexp > 400_000 or len(pq) > 3_000_000:
                return None
            for off, di, dj, c in steps:
                ni, nj = i + di, j + dj
                if ni < 0 or nj < 0 or ni >= nx or nj >= ny:
                    continue
                t = k + off
                if not pas_f[t]:
                    continue
                if di and dj and not (pas_f[k + di * ny] and pas_f[k + dj]):
                    continue
                ng = gc + c * cost_f[t]
                if ng < best[t]:
                    best[t] = ng; came[t] = k
                    hh = 0.0 if goal_f is None else HW * max(math.hypot(ni - tx, nj - ty) - trad, 0.0)
                    heapq.heappush(pq, (ng + hh, ng, t))
            if goal_f is not None and via_f[r]:
                vc = vcost[i, j]
                for l2 in range(NL):
                    if l2 == l:
                        continue
                    t = l2 * plane + r
                    ng = gc + vc
                    if ng < best[t]:
                        best[t] = ng; came[t] = k
                        hh = HW * max(math.hypot(i - tx, j - ty) - trad, 0.0)
                        heapq.heappush(pq, (ng + hh, ng, t))
        return None

    def route_net(self, net, w, groups, pres):
        """groups: list of cell lists (one per pad incl. its fan-out vias); grow a tree; returns (paths, n_failed)"""
        if not groups:
            return [], 0
        tree = list(groups[0])
        left = [g for g in groups[1:]]
        paths = []
        fails = 0
        while left:
            tx = np.mean([q[1] for q in tree]); ty = np.mean([q[2] for q in tree])
            left.sort(key=lambda g: math.hypot(np.mean([q[1] for q in g]) - tx, np.mean([q[2] for q in g]) - ty))
            goal = left.pop(0)
            if set(goal) & set(tree):
                tree += goal
                continue
            p = self.astar(net, w, tree, goal, pres)
            if p is None:
                fails += 1
                tree += goal
                continue
            paths.append(p)
            tree += p + goal
        return paths, fails


def pad_groups(b, R):
    """net name -> (code, width, [cells of each pad incl. the fixed vias / tracks touching it])"""
    vias = [t for t in b.GetTracks()]
    out = {}
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() <= 0 or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue
            cells = R.cells_of(p)
            for v in vias:
                if v.GetNetCode() == p.GetNetCode() and (p.HitTest(v.GetPosition()) if v.Type() == pcbnew.PCB_VIA_T else (p.HitTest(v.GetStart()) or p.HitTest(v.GetEnd()))):
                    cells += R.cells_of(v)
            n = p.GetNetname()
            out.setdefault(n, [p.GetNetCode(), FR.width_of(n), []])[2].append(cells)
    return out


def commit(b, R, net_code, w, path):
    k = 0
    netinfo = b.GetNetInfo().GetNetItem(net_code)
    while k < len(path) - 1:
        a, b2 = path[k], path[k + 1]
        if b2[0] != a[0]:
            v = pcbnew.PCB_VIA(b); x, y = R.g.xy(a[1], a[2])
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetNet(netinfo); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_H)); b.Add(v)
            k += 1
            continue
        d = (b2[1] - a[1], b2[2] - a[2])
        e = k + 1
        while e + 1 < len(path) and path[e + 1][0] == a[0] and (path[e + 1][1] - path[e][1], path[e + 1][2] - path[e][2]) == d:
            e += 1
        t = pcbnew.PCB_TRACK(b)
        x0, y0 = R.g.xy(a[1], a[2]); x1, y1 = R.g.xy(path[e][1], path[e][2])
        t.SetStart(pcbnew.VECTOR2I(MM(x0), MM(y0))); t.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
        t.SetLayer(LAYERS[a[0]]); t.SetWidth(MM(w)); t.SetNet(netinfo); b.Add(t)
        k = e


def main():
    src, dst = sys.argv[1], sys.argv[2]
    iters = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    b = pcbnew.LoadBoard(src)
    N = Nego(b)
    groups = pad_groups(b, N.R)
    names = [n for n in groups if n != "GND" and len(groups[n][2]) >= 2]

    def bbox(n):
        cs = [q for g in groups[n][2] for q in g]
        xs = [q[1] for q in cs]; ys = [q[2] for q in cs]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))
    names.sort(key=bbox)
    pres = 0.5
    for it in range(iters):
        t0 = time.time()
        fails = 0
        for n in names:
            code, w, gl = groups[n]
            if code in N.fpcells:
                N.add_fp(code, N.fpcells[code], -1)
            paths, f = N.route_net(code, w, gl, pres)
            fails += f
            N.paths[code] = (n, w, paths)
            idx = N.footprint(code, w, paths)
            N.fpcells[code] = idx
            N.add_fp(code, idx, 1)
        # overuse: centre-line cells of a net that lie in another net's footprint
        over = 0
        overmask = np.zeros((NL, N.nx, N.ny), bool)
        for code, (n, w, paths) in N.paths.items():
            own = np.zeros((NL, N.nx, N.ny), np.int16)
            own.ravel()[N.fpcells[code]] = 1
            for p in paths:
                for (l, i, j) in p:
                    if N.cnt[l, i, j] - own[l, i, j] > 0:
                        overmask[l, i, j] = True
                        over += 1
        N.hist[overmask] += 1.0
        print("iter %d: overused cells %d, unroutable connections %d, pres %.2f, %.0f s" % (it, over, fails, pres, time.time() - t0), flush=True)
        if over == 0:
            break
        pres = min(pres * 1.3, 30.0)
        best_over = min(globals().get('best_over', 1e9), over)
        np.save(dst + '.over.npy', np.argwhere(overmask).astype(np.int32))
    for code, (n, w, paths) in N.paths.items():
        for p in paths:
            commit(b, N.R, code, w, p)
    pcbnew.SaveBoard(dst, b)
    print("written", dst, "overused", over, "unroutable", fails)


if __name__ == "__main__":
    main()
