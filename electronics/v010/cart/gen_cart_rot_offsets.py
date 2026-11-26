#!/usr/bin/env python3
"""Generate cart/jlc_rot_offsets.json (copy of tools/gen_jlc_rot_offsets.py of the cup board, pre-order review H2, pointed at the cart board): rotation delta and origin offset of the official JLC/LCSC (EasyEDA) footprint of every ordered
part relative to OUR footprint, measured pad by pad on the part number that is actually ordered.

usage: kpy gen_cart_rot_offsets.py      (KiCad python; network for the EasyEDA API, answers cached in cart/.easyeda_cache/)

Method, per LCSC number in cart/parts.json (BOM parts with an LCSC code):
  * our pads: the footprint from the board's library (netlist_v4_cup.json -> fp [lib, name]), local frame, y down, origin = our origin;
  * LCSC pads: EasyEDA product API -> packageDetail.dataStr.shape "PAD~..." lines, centre x/y in 10 mil units, relative to the package
    origin (head.x / head.y), y down;
  * for phi in 0/90/180/270 (counter-clockwise as seen from the top): ours = R(phi) * lcsc + t, pads matched by pad NUMBER (several pads
    with the same number, e.g. the 4 USB shield tabs, are matched to the nearest one); the phi with the smallest worst pad deviation wins,
    t = where the LCSC origin lies in our footprint frame.
  * CPL convention used by tools/export_cup_jlc.py: delta_ccw = -phi; top side Rotation = KiCad rotation - delta, bottom side
    Rotation = KiCad rotation + delta (JLC shows the bottom side mirrored, a mirror reverses the rotation sense: review H3 2026-11-24);
    the CPL Mid X / Mid Y is moved from our origin to the LCSC origin (t rotated with the part; review H1).
Pad-number aliases (pads that are electrically tied in pairs) are listed in ALIAS.  The script prints the margin to the second-best angle:
a small margin means the land pattern is (nearly) symmetric and the pin-1 orientation rests on the pad numbering only.
"""
import json
import math
import os
import sys
import subprocess
import time

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CUP = HERE                       # cart/: parts.json, netlist, cache, output
sys.path.insert(0, os.path.join(ROOT, "..", "bench", "tools"))
import benchlib as bl  # noqa: E402  (KL / BENCHFP footprint paths)

CACHE = os.path.join(CUP, ".easyeda_cache")
API = "https://easyeda.com/api/products/%s/components?version=6.4.19.5"
U = 0.254          # EasyEDA unit = 10 mil
T = pcbnew.ToMM
# SKSCLAE010: pads 1+2 and 3+4 are the two contact pairs; numbering inside a pair is irrelevant
ALIAS = {"C130445": {"2": "1", "4": "3"}}


def easyeda_pads(lcsc):
    os.makedirs(CACHE, exist_ok=True)
    fn = os.path.join(CACHE, lcsc + ".json")
    if not os.path.exists(fn):
        for i in range(5):
            try:
                # curl: KiCad's bundled python has no CA bundle on macOS
                data = subprocess.run(["curl", "-s", "-m", "30", "-A", "openpatch-jlc-rot/1.0", API % lcsc], capture_output=True, check=True).stdout
                json.loads(data)["result"]["packageDetail"]
                open(fn, "wb").write(data)
                break
            except Exception as e:      # retried, then reported
                err = e
                time.sleep(10 * (i + 1))
        else:
            raise SystemExit("EasyEDA fetch failed for %s: %s" % (lcsc, err))
    res = json.load(open(fn))["result"]
    ds = res["packageDetail"]["dataStr"]
    ox, oy = float(ds["head"]["x"]), float(ds["head"]["y"])
    pads = []
    for s in ds["shape"]:
        if not s.startswith("PAD~"):
            continue
        f = s.split("~")
        pads.append((f[8], (float(f[2]) - ox) * U, (float(f[3]) - oy) * U))
    return res["packageDetail"].get("title", ""), pads


def our_pads(lib, name):
    path = bl.BENCHFP if lib == "Bench" else (os.path.join(ROOT, "footprints", "V010.pretty") if lib == "V010" else os.path.join(bl.KL, lib + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit("footprint not found %s:%s" % (lib, name))
    return [(p.GetNumber(), T(p.GetPosition().x), T(p.GetPosition().y)) for p in fp.Pads() if p.GetNumber()]


def rot(x, y, phi):
    """counter-clockwise as seen from the top, in a y-down frame"""
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    return x * c + y * s, -x * s + y * c


def fit(ours, lcsc, alias):
    norm = lambda n: alias.get(n, n)
    best = []
    for phi in (0, 90, 180, 270):
        L = [(norm(n), *rot(x, y, phi)) for n, x, y in lcsc]
        O = [(norm(n), x, y) for n, x, y in ours]
        # translation from the pad-number centroids of the numbers both have
        common = sorted({n for n, _, _ in O} & {n for n, _, _ in L})
        if not common:
            continue
        cen = lambda P, n: (sum(x for m, x, _ in P if m == n) / sum(1 for m, _, _ in P if m == n),
                            sum(y for m, _, y in P if m == n) / sum(1 for m, _, _ in P if m == n))
        tx = sum(cen(O, n)[0] - cen(L, n)[0] for n in common) / len(common)
        ty = sum(cen(O, n)[1] - cen(L, n)[1] for n in common) / len(common)
        dev = 0.0
        for n, x, y in O:
            cand = [(lx + tx, ly + ty) for m, lx, ly in L if m == n]
            if cand:
                dev = max(dev, min(math.hypot(x - a, y - b) for a, b in cand))
        best.append((dev, phi, tx, ty, len(common)))
    best.sort()
    return best


def main():
    parts = json.load(open(os.path.join(CUP, "parts.json")))
    nl = {p["ref"]: p for p in json.load(open(os.path.join(HERE, "netlist_cart.json")))}
    seen, table = {}, {}
    for ref, p in sorted(parts.items()):
        if not p.get("bom") or not p.get("lcsc") or p.get("dnp"):
            continue
        seen.setdefault(p["lcsc"], []).append(ref)
    rows = []
    for lcsc, refs in sorted(seen.items()):
        lib, name = nl[refs[0]]["fp"]
        title, lp = easyeda_pads(lcsc)
        res = fit(our_pads(lib, name), lp, ALIAS.get(lcsc, {}))
        dev, phi, tx, ty, n = res[0]
        margin = (res[1][0] - dev) if len(res) > 1 else 99
        delta = (-phi) % 360
        table[lcsc] = {"fp": name, "refs": refs, "lcsc_fp": title, "delta_ccw": delta, "origin_mm": [round(tx, 3), round(ty, 3)],
                       "maxdev_mm": round(dev, 3), "matched_pads": n, "margin_mm": round(margin, 3)}
        rows.append((lcsc, name, ",".join(refs), delta, tx, ty, dev, margin))
    out = os.path.join(CUP, "jlc_rot_offsets.json")
    json.dump(table, open(out, "w"), indent=1)
    print("%-10s %-44s %-22s %5s %7s %7s %6s %6s" % ("LCSC", "footprint", "refs", "delta", "t_x", "t_y", "dev", "margin"))
    for r in rows:
        print("%-10s %-44s %-22s %5d %7.3f %7.3f %6.3f %6.3f" % (r[0], r[1][:44], r[2][:22], r[3], r[4], r[5], r[6], r[7]))
    print("written", out, len(table), "parts")


if __name__ == "__main__":
    main()
