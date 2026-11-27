#!/usr/bin/env python3
"""kpy lcsc_origin_a.py board.kicad_pcb offsets.json -> prints JSON {ref: [x, y]}: where the LCSC footprint origin (origin_mm in the
footprint's own frame, jlc_rot_offsets.json) lies on the board, in the pos-file frame (x = page x, y = -page y, mm).

Used by export_cart_a_jlc.py for every part whose LCSC origin is not ours, top AND bottom (B's export only handled the top side).
The footprint's transform (mirror for bottom parts, rotation, translation) is fitted on its own pads: library pad positions vs board pad
positions, so no rotation sign convention is assumed; the fit residual is reported."""
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "bench", "tools"))
import benchlib as bl  # noqa: E402

T = pcbnew.ToMM
LIBS = {"V010": os.path.join(HERE, "..", "..", "footprints", "V010.pretty"), "CARTA": os.path.join(HERE, "CARTA.pretty")}


def lib_pads(lib: str, name: str) -> dict:
    path = LIBS.get(lib) or (bl.BENCHFP if lib == "Bench" else os.path.join(bl.KL, lib + ".pretty"))
    f = pcbnew.FootprintLoad(path, name)
    out = {}
    for p in f.Pads():
        if p.GetNumber():
            out.setdefault(p.GetNumber(), []).append((T(p.GetPosition().x), T(p.GetPosition().y)))
    return out


def fit(local: list, board: list) -> tuple:
    """board = R(a) * diag(s, 1) * local + t ; returns (s, a, tx, ty, residual)"""
    best = None
    for s in (1, -1):
        L = [(s * x, y) for x, y in local]
        lc = (sum(x for x, _ in L) / len(L), sum(y for _, y in L) / len(L))
        bc = (sum(x for x, _ in board) / len(board), sum(y for _, y in board) / len(board))
        num = sum((lx - lc[0]) * (by - bc[1]) - (ly - lc[1]) * (bx - bc[0]) for (lx, ly), (bx, by) in zip(L, board))
        den = sum((lx - lc[0]) * (bx - bc[0]) + (ly - lc[1]) * (by - bc[1]) for (lx, ly), (bx, by) in zip(L, board))
        a = math.atan2(num, den)
        c, sn = math.cos(a), math.sin(a)
        tx, ty = bc[0] - (c * lc[0] - sn * lc[1]), bc[1] - (sn * lc[0] + c * lc[1])
        res = max(math.hypot(c * lx - sn * ly + tx - bx, sn * lx + c * ly + ty - by) for (lx, ly), (bx, by) in zip(L, board))
        if best is None or res < best[4]:
            best = (s, a, tx, ty, res)
    return best


def main() -> None:
    b = pcbnew.LoadBoard(sys.argv[1])
    off = json.load(open(sys.argv[2]))
    parts = {p["ref"]: p for p in json.load(open(os.path.join(HERE, "netlist_cart_a.json")))}
    out = {}
    for f in b.GetFootprints():
        ref = f.GetReference()
        p = parts.get(ref)
        if not p or not p.get("lcsc") or p["lcsc"] not in off:
            continue
        lp = lib_pads(*p["fp"])
        loc, brd = [], []
        seen = {}
        for pd in f.Pads():
            n = pd.GetNumber()
            # pads that share a number (mounting tabs "MP") are matched in footprint order: the board footprint is an instance of the
            # same library footprint. They matter: a single row of signal pads alone cannot tell a mirrored footprint from a turned one.
            k = seen.get(n, 0)
            seen[n] = k + 1
            if n and k < len(lp.get(n, [])):
                loc.append(lp[n][k]); brd.append((T(pd.GetPosition().x), T(pd.GetPosition().y)))
        if len(loc) < 2:
            continue
        s, a, tx, ty, res = fit(loc, brd)
        ox, oy = off[p["lcsc"]].get("origin_mm", [0.0, 0.0])
        c, sn = math.cos(a), math.sin(a)
        x, y = c * s * ox - sn * oy + tx, sn * s * ox + c * oy + ty
        out[ref] = [round(x, 4), round(-y, 4), round(res, 4)]
    print("@@" + json.dumps(out))


if __name__ == "__main__":
    main()
