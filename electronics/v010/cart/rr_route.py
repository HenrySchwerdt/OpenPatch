#!/usr/bin/env python3
"""Rip-up and re-route clean-up for the CART board (copy of cup/rr_route.py; imports cart/finish_route.py).

Input: a routed board (nego_route.py + finish_route.py) and the placed, unrouted board it came from (its copper is the fixed
fan-out: module vias in pad, wire / USB pad vias, A7-A8 bridge, A1 stub). Every round:
  1. KiCad DRC; routed items in a clearance / hole-clearance / short / rule-area error are deleted,
  2. every open non-GND connection is routed against all copper; if that fails it is searched again with routed foreign copper
     passable at a price, and the routed items on that path are deleted (they come back as open connections next round).
KiCad 10's python wrapper breaks after BOARD.Remove() or a second LoadBoard in one process, so items are deleted by editing the
.kicad_pcb text (by uuid) and every board operation runs in its own `kpy rr_route.py --step ...` process.

usage: python3 rr_route.py routed.kicad_pcb placed.kicad_pcb [rounds]   (driver; writes routed.kicad_pcb in place)
"""
import json
import math
import os
import re
import subprocess
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KPY = os.path.join(HERE, "..", "board", "kpy")
SOFT_COST = 40.0
RIP_TYPES = ("clearance", "hole_clearance", "shorting_items", "items_not_allowed", "tracks_crossing", "copper_edge_clearance")


def drc(pcb):
    out = tempfile.mktemp(suffix=".json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", out, pcb], capture_output=True)
    d = json.load(open(out))
    os.remove(out)
    return d


def remove_uuids(pcb, uuids):
    """delete (segment ...) / (via ...) / (arc ...) blocks whose uuid is listed"""
    if not uuids:
        return 0
    txt = open(pcb).read()
    out, i, n = [], 0, 0
    pat = re.compile(r"\n\t\((segment|via|arc)\b")
    while True:
        m = pat.search(txt, i)
        if not m:
            out.append(txt[i:])
            break
        s = m.start() + 1
        depth, k = 0, s
        while True:
            ch = txt[k]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        block = txt[s:k + 1]
        u = re.search(r'\(uuid "([^"]+)"\)', block)
        out.append(txt[i:m.start()])
        if u and u.group(1) in uuids:
            n += 1
        else:
            out.append(txt[m.start():k + 1])
        i = k + 1
    open(pcb, "w").write("".join(out))
    return n


PRIO = set()
PLATEAU = os.environ.get("OP_RR_PLATEAU", "0") == "1"


def step(args):
    env = dict(os.environ, RR_PRIO=json.dumps(sorted(PRIO)))
    r = subprocess.run([KPY, os.path.abspath(__file__), "--step"] + args, capture_output=True, text=True, env=env)
    lines = [l for l in r.stdout.splitlines() if l.startswith("@@")]
    if r.returncode != 0 or not lines:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit("step failed: %s" % args)
    return json.loads(lines[-1][2:])


# ------------------------------------------------------------------------------------------------- in-process steps (KiCad python)
def _step_main(argv):
    import heapq
    import numpy as np
    from scipy import ndimage
    import pcbnew
    sys.path.insert(0, HERE)
    import finish_route as FR
    T = pcbnew.ToMM
    kind, pcb, placed, drcjson = argv[0], argv[1], argv[2], argv[3]
    b = pcbnew.LoadBoard(pcb)
    bf = pcbnew.LoadBoard(placed)

    def sig(t):
        if t.Type() == pcbnew.PCB_VIA_T:
            return ("v", round(T(t.GetPosition().x), 3), round(T(t.GetPosition().y), 3))
        return ("t", t.GetLayer(), round(T(t.GetStart().x), 3), round(T(t.GetStart().y), 3), round(T(t.GetEnd().x), 3), round(T(t.GetEnd().y), 3))
    fixed = {sig(t) for t in bf.GetTracks()}
    d = json.load(open(drcjson))
    if kind == "errors":
        rip = set()
        for v in d["violations"]:
            if v["severity"] != "error" or v["type"] not in RIP_TYPES:
                continue
            for it in v["items"]:
                a, _ = FR.find_item(b, it["description"], it["pos"])
                if a is not None and a.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_VIA_T) and sig(a) not in fixed:
                    rip.add(a.GetNetCode())
        uu = [t.m_Uuid.AsString() for t in b.GetTracks() if t.GetNetCode() in rip and sig(t) not in fixed]
        print("@@" + json.dumps(sorted(uu)))
        return
    # kind == "route"
    R = FR.Router(b)
    Rf = FR.Router(bf)
    jobs = []
    for u in d["unconnected_items"]:
        if len(u["items"]) != 2 or "[GND]" in u["items"][0]["description"]:
            continue
        a, na = FR.find_item(b, u["items"][0]["description"], u["items"][0]["pos"])
        c, _ = FR.find_item(b, u["items"][1]["description"], u["items"][1]["pos"])
        if a is None or c is None:
            continue
        dist = math.hypot(u["items"][0]["pos"]["x"] - u["items"][1]["pos"]["x"], u["items"][0]["pos"]["y"] - u["items"][1]["pos"]["y"])
        jobs.append((dist, na, a, c))
    prio = set(json.loads(os.environ.get("RR_PRIO", "[]")))
    import random
    rnd = random.Random(int(os.environ.get("RR_SEED", "0")))
    jit = float(os.environ.get("RR_JITTER", "0"))
    jobs.sort(key=lambda j: (j[1] not in prio, j[0] * (1 + jit * rnd.random())))      # nets that were ripped before go first; optional random order jitter
    soft_cost = SOFT_COST * (0.25 + 1.5 * rnd.random()) if jit else SOFT_COST
    routed, victims, blocked = 0, set(), []
    dirs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
    for dist, net, a, c in jobs:
        code = a.GetNetCode()
        st, go = R.cells_of(a), R.cells_of(c)
        path, w = R.route(code, st, go)
        if path is not None:
            R.commit(code, path, w)
            routed += 1
            continue
        if os.environ.get("RR_NOSOFT") == "1" or (os.environ.get("RR_SOFT_NET") and net != os.environ["RR_SOFT_NET"]):
            blocked.append(net)
            continue
        # soft search: routed foreign copper passable at a price
        w = FR.width_of(net)
        hard = (R.own[w] == 0) | (R.own[w] == code)
        pas = hard | ((Rf.own[w] == 0) | (Rf.own[w] == code))
        goals = [q for q in go if pas[q]]
        if not goals:
            blocked.append(net)
            continue
        goalset = set(goals)
        gx = np.array([g[1] for g in goals]); gy = np.array([g[2] for g in goals])
        tx, ty = gx.mean(), gy.mean()
        trad = float(np.hypot(gx - tx, gy - ty).max())
        rv = int(math.ceil((FR.VIA_KEEP - (FR.CLR + w / 2 + 0.01)) / FR.G)) + FR.VIA_SLACK     # same via rule as the hard router
        via_ok = ~Rf.viablock.copy()
        via_hard = ~R.viablock.copy()
        for li in range(len(FR.LAYERS)):
            via_ok &= ndimage.binary_erosion(pas[li], structure=FR.disk(rv), border_value=0)
            via_hard &= ndimage.binary_erosion(hard[li], structure=FR.disk(rv), border_value=0)
        best, came, pq = {}, {}, []
        for s in st:
            if pas[s]:
                best[s] = 0.0
                heapq.heappush(pq, (0.0, 0.0, s))
        sp, nexp = None, 0
        while pq:
            f, gcost, s = heapq.heappop(pq)
            if gcost > best.get(s, 1e18) + 1e-9:
                continue
            if s in goalset:
                sp = [s]
                while sp[-1] in came:
                    sp.append(came[sp[-1]])
                break
            nexp += 1
            if nexp > 1_500_000:
                break
            l, i, j = s
            for di, dj, cc in dirs:
                ni, nj = i + di, j + dj
                if not (0 <= ni < R.g.nx and 0 <= nj < R.g.ny) or not pas[l, ni, nj]:
                    continue
                t = (l, ni, nj)
                ng = gcost + cc * (1.0 if hard[l, ni, nj] else soft_cost)
                if ng < best.get(t, 1e18):
                    best[t] = ng; came[t] = s
                    heapq.heappush(pq, (ng + max(math.hypot(ni - tx, nj - ty) - trad, 0.0), ng, t))
            if via_ok[i, j]:
                extra = 0.0 if via_hard[i, j] else 4 * soft_cost
                for l2 in range(len(FR.LAYERS)):
                    if l2 != l:
                        t = (l2, i, j)
                        ng = gcost + FR.VIA_COST + extra
                        if ng < best.get(t, 1e18):
                            best[t] = ng; came[t] = s
                            heapq.heappush(pq, (ng + max(math.hypot(i - tx, j - ty) - trad, 0.0), ng, t))
        if sp is None:
            blocked.append(net)
            continue
        # only the cells the path could not use for real (blocked by routed foreign copper)
        cells = [(FR.LAYERS[l], *R.g.xy(i, j)) for (l, i, j) in sp if not hard[l, i, j]]
        if os.environ.get("RR_DEBUG"):
            print("DBG", net, len(sp), len(cells), cells[:6], file=sys.stderr)
        vcells = []         # soft via sites: foreign copper within the via keep-out (+ grid) of the via centre goes
        for k in range(len(sp) - 1):
            l, i, j = sp[k]
            if sp[k + 1][0] != l and not via_hard[i, j]:
                vcells.append(R.g.xy(i, j))
        for t in b.GetTracks():
            if sig(t) in fixed or t.GetNetCode() == code or t.GetNetCode() in victims:
                continue
            for lay, x, y in cells:
                if t.Type() == pcbnew.PCB_VIA_T:
                    p = t.GetPosition()
                    dd = math.hypot(T(p.x) - x, T(p.y) - y) - 0.2
                elif t.GetLayer() == lay:
                    dd = FR.seg_dist(x, y, t.GetStart(), t.GetEnd())
                else:
                    continue
                if dd < 0.22:
                    victims.add(t.GetNetCode())
                    break
            else:
                for x, y in vcells:
                    if t.Type() == pcbnew.PCB_VIA_T:
                        p = t.GetPosition()
                        dd = math.hypot(T(p.x) - x, T(p.y) - y) - FR.VIA_D / 2
                    else:
                        dd = FR.seg_dist(x, y, t.GetStart(), t.GetEnd()) - T(t.GetWidth()) / 2
                    if dd < FR.VIA_KEEP + 0.05:
                        victims.add(t.GetNetCode())
                        break
    pcbnew.SaveBoard(pcb, b)
    # whole victim nets go (fragments of a net left behind would block their own re-route)
    vu = [t.m_Uuid.AsString() for t in b.GetTracks() if t.GetNetCode() in victims and sig(t) not in fixed]
    print("@@" + json.dumps({"routed": routed, "jobs": len(jobs), "victims": sorted(vu), "blocked": blocked, "victim_nets": [b.GetNetInfo().GetNetItem(c).GetNetname() for c in victims]}))


def score_of(d):
    errs = [v for v in d["violations"] if v["severity"] == "error" and v["type"] in RIP_TYPES]
    opens = [u for u in d["unconnected_items"] if "[GND]" not in u["items"][0]["description"]]
    return len(opens) + 2 * len(errs), opens


def greedy(pcb, placed, rounds):
    """rip-up with rollback: one open net at a time is routed through routed foreign copper, the victims are re-routed
    (hard), and the trial is kept only if open connections + 2 x DRC errors went down"""
    tmp = tempfile.mktemp(suffix=".json")
    cur, opens = score_of(drc(pcb))
    best_sc = cur
    shutil.copy(pcb, pcb + ".best")
    print("start score", cur, flush=True)
    for rd in range(rounds):
        improved = False
        nets = []
        for u in opens:
            n = re.search(r"\[([^\]]+)\]", u["items"][0]["description"]).group(1)
            if n not in nets:
                nets.append(n)
        if os.environ.get("RR_JITTER"):
            import random
            random.Random(rd).shuffle(nets)
        for k_try, net in enumerate(["__errors__"] + nets):
            os.environ["RR_SEED"] = str(1000 * rd + k_try)
            trial = os.path.splitext(pcb)[0] + "_trial.kicad_pcb"
            shutil.copy(pcb, trial)
            shutil.copy(os.path.splitext(pcb)[0] + ".kicad_pro", os.path.splitext(trial)[0] + ".kicad_pro")   # DRC rules live in the project
            d = drc(trial)
            json.dump(d, open(tmp, "w"))
            if net == "__errors__":
                rip = step(["errors", trial, placed, tmp])
                if not rip:
                    continue
                remove_uuids(trial, set(rip))
            else:
                os.environ["RR_SOFT_NET"] = net
                res = step(["route", trial, placed, tmp])
                del os.environ["RR_SOFT_NET"]
                remove_uuids(trial, set(res["victims"]))
                PRIO.clear(); PRIO.add(net)        # the target net re-routes first, before its victims take the space back
            for _ in range(2):
                d = drc(trial)
                json.dump(d, open(tmp, "w"))
                os.environ["RR_NOSOFT"] = "1"
                step(["route", trial, placed, tmp])
                del os.environ["RR_NOSOFT"]
            sc, op = score_of(drc(trial))
            print("  round %d %s: %d -> %d" % (rd, net, cur, sc), flush=True)
            if sc < cur or (sc == cur and PLATEAU and net != "__errors__"):      # plateau moves (OP_RR_PLATEAU=1) let the search walk
                shutil.copy(trial, pcb)
                improved = improved or sc < cur
                cur, opens = sc, op
                if sc < best_sc:
                    best_sc = sc
                    shutil.copy(pcb, pcb + ".best")
        if (not improved and not PLATEAU) or cur == 0:
            break
    print("final score", cur)


def main():
    if sys.argv[1] == "--step":
        _step_main(sys.argv[2:])
        return
    if sys.argv[1] == "--greedy":
        greedy(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 4)
        return
    pcb, placed = sys.argv[1], sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    tmp = tempfile.mktemp(suffix=".json")
    best = None
    for rd in range(rounds):
        d = drc(pcb)
        json.dump(d, open(tmp, "w"))
        rip = step(["errors", pcb, placed, tmp])
        n = remove_uuids(pcb, set(rip))
        d = drc(pcb)
        json.dump(d, open(tmp, "w"))
        errs = [v for v in d["violations"] if v["severity"] == "error" and v["type"] in RIP_TYPES]
        opens = [u for u in d["unconnected_items"] if "[GND]" not in u["items"][0]["description"]]
        score = len(opens) + 2 * len(errs)
        if best is None or score < best:      # rip-up can oscillate: keep the best state seen
            best = score
            shutil.copy(pcb, pcb + ".best")
        print("round %d: ripped %d items in DRC errors, now %d errors, %d open non-GND" % (rd, n, len(errs), len(opens)), flush=True)
        if not errs and not opens:
            break
        res = step(["route", pcb, placed, tmp])
        k = remove_uuids(pcb, set(res["victims"]))
        PRIO.update(res["victim_nets"])
        print("   routed %d of %d, ripped %d blocking items, no path at all: %s" % (res["routed"], res["jobs"], k, res["blocked"]), flush=True)
    d = drc(pcb)
    errs = [v for v in d["violations"] if v["severity"] == "error"]
    opens = [u for u in d["unconnected_items"] if "[GND]" not in u["items"][0]["description"]]
    print("final: %d DRC errors, %d open non-GND, %d open GND" % (len(errs), len(opens), len(d["unconnected_items"]) - len(opens)))


if __name__ == "__main__":
    main()
