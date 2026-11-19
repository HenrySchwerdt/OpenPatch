# exec'd by build_multi.py (shares its globals: pcbnew, bl, MM, W, H, Y, CFG)


def quad_place(b, fps, parts, fixed):
    import numpy as np
    T = pcbnew.ToMM
    movable = [p["ref"] for p in parts if p["ref"] not in fixed]
    if not movable:
        return
    idx = {r: i for i, r in enumerate(movable)}
    n = len(movable)
    A = np.zeros((n, n)); bx = np.zeros(n); by = np.zeros(n)
    netpins = {}
    for p in parts:
        for pad, net in p["pins"].items():
            if net:
                netpins.setdefault(net, []).append((p["ref"], pad))
    padpos = {}
    for r in fixed:
        for pd in fps[r].Pads():
            padpos[(r, pd.GetNumber())] = (T(pd.GetPosition().x) - bl.OX, T(pd.GetPosition().y) - bl.OY)
        c = fps[r].GetPosition()
        padpos[(r, None)] = (T(c.x) - bl.OX, T(c.y) - bl.OY)
    low = {"3V3": 0.01, "VBAT": 0.02, "VMOT": 0.3, "VMOT_RAW": 0.3, "VMOT_PRE": 0.5}
    for net, pl in netpins.items():
        if net == "GND" or len(pl) < 2 or len(pl) > 40:
            continue
        w = low.get(net, 1.0) / (len(pl) - 1)
        for i in range(len(pl)):
            for j in range(i + 1, len(pl)):
                (ra, pa), (rb, pb) = pl[i], pl[j]
                ia, ib = idx.get(ra), idx.get(rb)
                if ia is not None and ib is not None:
                    A[ia, ia] += w; A[ib, ib] += w; A[ia, ib] -= w; A[ib, ia] -= w
                elif ia is not None and rb in fixed:
                    x, y = padpos.get((rb, pb), padpos[(rb, None)]); A[ia, ia] += w; bx[ia] += w * x; by[ia] += w * y
                elif ib is not None and ra in fixed:
                    x, y = padpos.get((ra, pa), padpos[(ra, None)]); A[ib, ib] += w; bx[ib] += w * x; by[ib] += w * y
    for p in parts:
        if p["ref"] in idx:
            i = idx[p["ref"]]
            ax, ay = CFG["anchors"].get(p["group"], (W / 2, H / 2))
            A[i, i] += 0.03; bx[i] += 0.03 * ax; by[i] += 0.03 * Y(ay)
    A += np.eye(n) * 1e-6
    xs = np.linalg.solve(A, bx); ys = np.linalg.solve(A, by)
    for r in movable:
        f = fps[r]; c = f.GetPosition()
        tx = float(min(max(xs[idx[r]], 1.0), W - 1.0)); ty = float(min(max(ys[idx[r]], 1.0), H - 1.0))
        f.Move(pcbnew.VECTOR2I(MM(bl.OX + tx) - c.x, MM(bl.OY + ty) - c.y))


def legalize2(b, fps, fixed, forbid_both, margin=0.12, edge=0.45, step=0.25, rmax=40):
    side = lambda f: "B" if f.GetSide() == pcbnew.B_Cu else "F"
    placed = {"F": [list(x) for x in forbid_both], "B": [list(x) for x in forbid_both]}
    ov = lambda a, c: a[0] < c[2] + margin and a[2] > c[0] - margin and a[1] < c[3] + margin and a[3] > c[1] - margin
    for r in fixed:
        bx = bl._box(fps[r])
        if r.startswith("H"):
            placed["F"].append(bx); placed["B"].append(bx)
        else:
            placed[side(fps[r])].append(bx)
    area = lambda bb: (bb[2] - bb[0]) * (bb[3] - bb[1])
    todo = sorted((r for r in fps if r not in fixed), key=lambda r: -area(bl._box(fps[r])))
    for r in todo:
        f = fps[r]; b0 = bl._box(f); sd = side(f)
        cand = [(0.0, 0.0)]
        for k in range(1, int(rmax / step) + 1):
            ring = []
            for i in range(-k, k + 1):
                ring += [(i * step, -k * step), (i * step, k * step), (-k * step, i * step), (k * step, i * step)]
            cand += sorted(set(ring), key=lambda d: d[0] ** 2 + d[1] ** 2)
        done = False
        for flip in (False, True):
            if flip:
                c = f.GetPosition(); f.Flip(c, pcbnew.FLIP_DIRECTION_LEFT_RIGHT); sd = side(f); b0 = bl._box(f)
            for dx, dy in cand:
                b1 = [b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy]
                if b1[0] < edge or b1[1] < edge or b1[2] > W - edge or b1[3] > H - edge or any(ov(b1, p) for p in placed[sd]):
                    continue
                if dx or dy:
                    f.Move(pcbnew.VECTOR2I(MM(dx), MM(dy)))
                placed[sd].append(b1); done = True
                break
            if done:
                break
        if not done:
            print("LEGALIZE FAILED", r)
