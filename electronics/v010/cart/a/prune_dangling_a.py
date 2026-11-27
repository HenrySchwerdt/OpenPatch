#!/usr/bin/env python3
"""python3 prune_dangling_a.py board.kicad_pcb : delete router leftovers that KiCad's DRC reports as dangling (track_dangling: a track end
that touches nothing; via_dangling: a via connected on one layer only, e.g. an in-pad via the route did not use), repeated until none
is left (a dead branch goes piece by piece; every removal is checked and undone if it opens a connection), and exact duplicate track
segments. The board must have 0 unconnected items before (checked). TEST PROJECT, water only."""
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

FIND = r'''
import json, sys, pcbnew
sys.path.insert(0, %r)
import finish_route_a as FR
b = pcbnew.LoadBoard(sys.argv[1])
d = json.load(open(sys.argv[2]))
out = []
for v in d["violations"]:
    if v["type"] in ("track_dangling", "via_dangling"):
        for it in v["items"]:
            a, _ = FR.find_item(b, it["description"], it["pos"])
            if a is not None and a.Type() in (pcbnew.PCB_TRACE_T, pcbnew.PCB_VIA_T):
                out.append(a.m_Uuid.AsString())
seen, dup = {}, []
for t in b.GetTracks():
    s, e = (t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)
    k = (t.Type(), t.GetNetCode(), -1 if t.Type() == pcbnew.PCB_VIA_T else t.GetLayer(), min(s, e), max(s, e))
    if k in seen:
        dup.append(t.m_Uuid.AsString())
    else:
        seen[k] = 1
print("@@" + json.dumps({"dangling": sorted(set(out)), "dup": dup}))
''' % HERE


def drc(pcb: str) -> tuple:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", out, pcb], capture_output=True)
    return out, json.load(open(out))


def main() -> None:
    pcb = sys.argv[1]
    path, d = drc(pcb)
    if d["unconnected_items"]:
        raise SystemExit("board has %d unconnected items: route first" % len(d["unconnected_items"]))
    script = tempfile.mktemp(suffix=".py")
    open(script, "w").write(FIND)
    keep = tempfile.mktemp(suffix=".kicad_pcb")
    total, kept, tried = 0, [], set()
    first = True
    while True:
        r = subprocess.run([KPY, script, pcb, path], capture_output=True, text=True)
        res = json.loads([l for l in r.stdout.splitlines() if l.startswith("@@")][-1][2:])
        if first and res["dup"]:
            total += RR.remove_uuids(pcb, res["dup"])        # exact duplicates: removing one copy never changes connectivity
            first = False
            path, d = drc(pcb)
            continue
        cand = [u for u in res["dangling"] if u not in tried]
        if not cand:
            break
        # one piece at a time, each checked: a "dangling" piece can still carry a connection that lands in the middle of it
        u = cand[0]
        tried.add(u)
        shutil.copy(pcb, keep)
        RR.remove_uuids(pcb, [u])
        p2, d2 = drc(pcb)
        if d2["unconnected_items"]:
            shutil.copy(keep, pcb)
            kept.append(u)
            continue
        total += 1
        path, d = p2, d2
    print("pruned", total, "items, kept", len(kept), "(they carry a connection); unconnected 0")


if __name__ == "__main__":
    main()
