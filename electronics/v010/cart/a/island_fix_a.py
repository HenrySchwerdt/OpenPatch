#!/usr/bin/env python3
"""Small rip-up loop for the last open connections of a routed cart A board (plain python3; every board step runs in its own kpy process).

Each round: island routing of every open non-GND connection (island_route_a.py, the net of the last rip first); for the first one that
still fails, the soft search of rr_route_a.py (foreign routed copper passable at a price) finds the cheapest path and only the track /
via PIECES in its way are deleted (RR_FRAGMENT=1, not whole nets as rr_route_a.py does); they come back as open connections next round.
The board with the fewest opens (then fewest DRC errors) is kept as <board>.best. Use OP_LAYERS / OP_IN1 as for the routers.

usage: python3 island_fix_a.py routed.kicad_pcb placed.kicad_pcb [rounds]   (writes routed.kicad_pcb in place). TEST PROJECT, water only."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KPY = os.path.join(HERE, "..", "..", "board", "kpy")
CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
sys.path.insert(0, HERE)
import rr_route_a as RR  # noqa: E402


def drc(pcb: str) -> dict:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", out, pcb], capture_output=True)
    d = json.load(open(out))
    d["_path"] = out
    return d


def opens(d: dict) -> list:
    return [u["items"][0]["description"].split("[")[1].split("]")[0] for u in d["unconnected_items"]
            if not any("[GND]" in i["description"] for i in u["items"])]


def errors(d: dict) -> int:
    return sum(1 for v in d["violations"] if v["severity"] == "error" and v["type"] != "starved_thermal")


def main() -> None:
    pcb, placed = sys.argv[1], sys.argv[2]
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    best = None
    first = ""
    for k in range(rounds):
        d = drc(pcb)
        o = opens(d)
        if o:
            env = dict(os.environ, OP_FIRST=first)
            r = subprocess.run([KPY, os.path.join(HERE, "island_route_a.py"), pcb, d["_path"]], capture_output=True, text=True, env=env)
            print(" ", [l for l in r.stdout.splitlines() if l.startswith("routed")][-1:], flush=True)
            d = drc(pcb)
            o = opens(d)
        score = (len(o), errors(d))
        print("round %d: opens %s errors %d" % (k, o, score[1]), flush=True)
        if best is None or score < best:
            best = score
            shutil.copy(pcb, pcb + ".best")
        if not o or score[1]:
            break
        net = o[0]
        tmp = tempfile.mktemp(suffix=".kicad_pcb")
        shutil.copy(pcb, tmp)
        env = dict(os.environ, RR_SOFT_NET=net, RR_FRAGMENT="1", RR_PRIO="[]")
        r = subprocess.run([KPY, os.path.join(HERE, "rr_route_a.py"), "--step", "route", tmp, placed, d["_path"]], capture_output=True, text=True, env=env)
        lines = [l for l in r.stdout.splitlines() if l.startswith("@@")]
        if not lines:
            print("soft search failed", r.stderr[-500:])
            break
        res = json.loads(lines[-1][2:])
        n = RR.remove_uuids(pcb, res["victims"])
        print("   rip for %s: %d pieces of %s" % (net, n, res["victim_nets"]), flush=True)
        first = net         # nothing ripped: the plain route exists now (an earlier rip freed it), the next round takes it
    print("best (opens, errors):", best)


if __name__ == "__main__":
    main()
