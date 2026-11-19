#!/usr/bin/env python3
"""Length levers of the integrated v0.1.0 pod (pure layout arithmetic of op_pod.layout, no CAD):  python3 mechanical/studies/pod_levers.py

Each row changes ONE or a few numbers of the baseline and recomputes the pod length of OP-100 / OP-200.  The baseline is what `generate.py --variant v010` builds.
Rows marked (decision) move a frozen number or need a decision in docs/STATUS.md; rows marked (owner) need the owner to relax a requirement.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import op_pod  # noqa: E402


def lengths(p: dict) -> dict:
    out = {}
    for sz in ("OP-100", "OP-200"):
        L = op_pod.layout(p, sz)
        out[sz] = (round(L["length"], 1), round(L["stroke"], 2), round(L["rear_zone"], 1))
    return out


def variant(base: dict, **kw) -> dict:
    p = copy.deepcopy(base)
    if "motor" in kw:
        p["pod"]["motor"]["option"] = kw["motor"]
    if "tail" in kw:
        p["dock_interface_frozen"]["tail_u"] = kw["tail"]
    if "bore_w" in kw:
        p["reservoir_frozen_v010"]["bore_w"] = kw["bore_w"]
        p["reservoir_frozen_v010"]["outer_w"] = kw["bore_w"] + 2 * p["reservoir_frozen_v010"]["wall"]
        p["pod"]["res"]["y0"] = 31.0 - p["reservoir_frozen_v010"]["outer_w"]
    if "end_wall" in kw:
        p["reservoir_frozen_v010"]["end_wall"] = kw["end_wall"]
    if "dry_strip" in kw:
        p["pod"]["res"]["dry_strip"] = kw["dry_strip"]
    if "nut_to_res" in kw:
        p["pod"]["drive"]["nut_to_res"] = kw["nut_to_res"]
    if "plunger_len" in kw:
        p["pod"]["res"]["plunger_len"] = kw["plunger_len"]
    return p


def main() -> None:
    p0 = op_pod.prepare(json.loads((HERE / "params.json").read_text()))
    rows = [("baseline: NFP-608 in the rear zone, bore 25.7 x 4.7, frozen dock tail 21.2", {}),
            ("Zhaowei d3.4 motor (envelope 14.1 mm stack, UNVERIFIED torque)", {"motor": "zw34"}),
            ("dock tail 21.2 -> 19.0 (decision: septum off the insert footprint, datum moves 2.2)", {"tail": 19.0}),
            ("dock tail 21.2 -> 17.2 (decision, f = 4 of the drive study)", {"tail": 17.2}),
            ("no lid-screw lane: bore 28.0 wide (decision: lid fixed by snap hooks)", {"bore_w": 28.0}),
            ("NFP + tail 19.0 + bore 28.0", {"tail": 19.0, "bore_w": 28.0}),
            ("Zhaowei + tail 19.0", {"motor": "zw34", "tail": 19.0}),
            ("Zhaowei + tail 17.2 + bore 28.0", {"motor": "zw34", "tail": 17.2, "bore_w": 28.0}),
            ("Zhaowei + tail 17.2 + bore 28.0 + end wall 1.5 + dry strip 0.5", {"motor": "zw34", "tail": 17.2, "bore_w": 28.0, "end_wall": 1.5, "dry_strip": 0.5})]
    res = {}
    print("| lever set | OP-100 L / stroke / rear zone | OP-200 L / stroke / rear zone |")
    print("|---|---|---|")
    for name, kw in rows:
        r = lengths(variant(p0, **kw))
        res[name] = r
        print(f"| {name} | **{r['OP-100'][0]}** / {r['OP-100'][1]} / {r['OP-100'][2]} | **{r['OP-200'][0]}** / {r['OP-200'][1]} / {r['OP-200'][2]} |")
    # reference: owner-rejected idler variant (motor beside the reservoir, 3-mesh chain): bore narrowed to 22.0 (motor lane 6.2), rear zone limited by the screw tail only
    print("\nReference (owner requirement 2026-11-19 forbids it: idler + side pin): motor beside the reservoir, bore 22.0 x 4.7, rear zone = screw tail only")
    pr = variant(p0, bore_w=22.0)
    for sz in ("OP-100", "OP-200"):
        L = op_pod.layout(pr, sz)
        x_r0 = op_pod_screw_limited(pr, L)
        print(f"  {sz}: stroke {L['stroke']:.2f}, x_r0 {x_r0:.1f} -> L {x_r0 + (L['x_r1'] - L['x_r0']) + L['tail_u']:.1f} mm (frozen tail 21.2)")
    (HERE / "studies" / "pod_levers.json").write_text(json.dumps(res, indent=1))


def op_pod_screw_limited(p: dict, L: dict) -> float:
    dr = p["pod"]["drive"]
    g1 = dr["screw_rear_min_x"] + L["stroke"] + dr["engage_margin"] + 0.5 - dr["nut_glue"]
    return g1 + dr["nut_to_res"]


if __name__ == "__main__":
    main()
