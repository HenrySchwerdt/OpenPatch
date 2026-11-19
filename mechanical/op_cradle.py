# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Charging cradle for the v0.1.0 pod (printed, two spring test probes = pogo pins). TEST PROJECT, water only.

The pod is laid LID DOWN into the cradle (y mirrored: y_cradle = W - y_pod); two pogo pins enter the lid window and touch the two ENIG pads
(5 V / GND, 20 mA charger on the pod).  A bar on two M2 screws holds the pod down against the pin force.  One cradle per size (pad x depends on x_r1).

Cradle frame: X = pod X, Y = W - pod Y, Z up, z = 0 = bottom of the pin bosses (pin tails with the solder cups / wire lugs are at z = 0).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from op_cmds import Script
from op_layout import HERE, find_cli

CLI = find_cli()


def cradle_geometry(p: dict, L: dict) -> dict:
    cr, G = p["v010"]["cradle"], L["v010"]
    W, Ln, H = L["width"], L["length"], L["height"]
    zf = cr["pin_barrel"]                                   # tray floor = barrel top (pin barrel sits in the bore, flush with the floor)
    pads = [{"x": c["center_pod"][0], "y": W - c["center_pod"][1]} for c in G["charge_pads"]]
    depth_to_pad = H - G["ztop"] - p["v010"]["charge"]["pad_t"]   # lid outer face -> pad top (pod lid-down: lid face sits on the floor)
    tip_free = cr["pin_len"] - cr["pin_barrel"]
    clr, rt = cr["pocket_clr"], cr["rim_t"]
    return {"zf": zf, "pads": pads, "depth_to_pad": round(depth_to_pad, 3), "tip_free": tip_free, "compression": round(tip_free - depth_to_pad, 3),
            "pocket": [(-clr, Ln + clr), (-clr, W + clr)], "rim_t": rt, "plate_x": (-rt - 3.0, Ln + rt + 3.0), "plate_y": (-rt - 8.0, W + rt + 8.0),
            "posts": [(L["x_r1"] + cr["bar_x_u"], -rt - 4.0), (L["x_r1"] + cr["bar_x_u"], W + rt + 4.0)],
            "bar_z": [zf + H, zf + H + cr["bar_t"]], "pod_top_z": zf + H}


def build_cradle_script(p: dict, L: dict, tag: str, out: Path) -> tuple[Script, dict]:
    cr = p["v010"]["cradle"]
    C = cradle_geometry(p, L)
    W, Ln, H = L["width"], L["length"], L["height"]
    zf, rt = C["zf"], C["rim_t"]
    s = Script()
    (x0, x1), (y0, y1) = C["pocket"]
    px, py = C["plate_x"], C["plate_y"]
    s.rrect("cradle_base", px, py, 4.0, (zf - cr["plate_t"], zf))
    s.rrect("t_rim", (x0 - rt, x1 + rt), (y0 - rt, y1 + rt), 4.0 + rt, (zf - 0.01, zf + cr["rim_h"]))
    s.rrect("t_pocket", (x0, x1), (y0, y1), 4.0 + cr["pocket_clr"], (zf - 0.02, zf + cr["rim_h"] + 0.1))
    s.cut("t_rim", ["t_pocket"])
    joins = ["t_rim"]
    cuts = []
    for i, pd in enumerate(C["pads"]):
        joins.append(s.cyl(f"t_boss{i}", "Z", (pd["x"], pd["y"], 0), cr["boss_d"], 0.0, zf - cr["plate_t"] + 0.01))
        cuts.append(s.cyl(f"t_bore{i}", "Z", (pd["x"], pd["y"], 0), cr["bore_d"], -0.1, zf + 0.1))
    for i, (qx, qy) in enumerate(C["posts"]):
        joins.append(s.cyl(f"t_post{i}", "Z", (qx, qy, 0), cr["post_d"], zf - 0.01, C["bar_z"][0]))
        cuts.append(s.cyl(f"t_pil{i}", "Z", (qx, qy, 0), 1.6, C["bar_z"][0] - 5.0, C["bar_z"][0] + 0.1))
    s.join("cradle_base", joins)
    s.cut("cradle_base", cuts)
    # hold-down bar (flat, rests on the skin-side floor of the pod; M2 x 8 screws)
    s.box("cradle_bar", (C["posts"][0][0] - cr["bar_w"] / 2, C["posts"][0][0] + cr["bar_w"] / 2), (C["posts"][0][1] - cr["post_d"] / 2, C["posts"][1][1] + cr["post_d"] / 2), tuple(C["bar_z"]))
    s.cut("cradle_bar", [s.cyl(f"t_bh{i}", "Z", (qx, qy, 0), 2.2, C["bar_z"][0] - 0.1, C["bar_z"][1] + 0.1) for i, (qx, qy) in enumerate(C["posts"])])
    # purchased pogo pins (compressed state: tip at the pad plane)
    tip_z = zf + C["depth_to_pad"]
    for i, pd in enumerate(C["pads"]):
        s.cyl(f"pogo_{i + 1}", "Z", (pd["x"], pd["y"], 0), cr["pin_tube_d"], 0.0, zf)
        s.cyl(f"t_tip{i}", "Z", (pd["x"], pd["y"], 0), 0.74, zf - 0.05, tip_z)
        s.join(f"pogo_{i + 1}", [f"t_tip{i}"])
    # pod envelope, lid down, with the charge window (check body, not exported)
    s.rrect("pod_envelope", (0, Ln), (0, W), p["shell"]["corner_r"], (zf, zf + H))
    G = L["v010"]
    w = G["window"]
    s.box("t_win", (w["x"][0], w["x"][1]), (W - w["y"][1], W - w["y"][0]), (zf - 0.1, tip_z + 0.0))
    s.cut("pod_envelope", ["t_win"])
    for part in ("cradle_base", "cradle_bar"):
        s.export_step(str(out / f"{tag}_{part}.step"), [part])
        s.export_stl(str(out / f"{tag}_{part}.stl"), [part])
    return s, C


def build_cradle_files(p: dict, out: Path) -> None:
    fab = out / "cradle"
    fab.mkdir(exist_ok=True)
    for sz in p["variants"]:
        mj = out / f"{sz}.mech.json"
        if not mj.exists():
            continue
        L = json.loads(mj.read_text())
        s, C = build_cradle_script(p, L, f"cradle_{sz}", fab)
        sj = fab / f"cradle_{sz}.script.json"
        sj.write_text(json.dumps(s.dumps()), encoding="utf-8")
        r = subprocess.run([CLI, "run", str(sj), "--save", str(fab / f"cradle_{sz}.sc"), "--quiet"], capture_output=True, text=True, cwd=HERE)
        if r.returncode != 0:
            raise SystemExit(r.stdout[-1500:] + r.stderr[-1500:])
        sj.unlink()
        (fab / f"cradle_{sz}.geometry.json").write_text(json.dumps(C, indent=1), encoding="utf-8")
        print(f"cradle {sz}: pins at x {C['pads'][0]['x']:.2f}, y {C['pads'][0]['y']:.2f}/{C['pads'][1]['y']:.2f}; compression {C['compression']} mm")


def check_cradle(p: dict, out: Path) -> tuple[list, list]:
    problems, warns = [], []
    fab = out / "cradle"
    cr = p["v010"]["cradle"]
    for sz in p["variants"]:
        sc = fab / f"cradle_{sz}.sc"
        if not sc.exists():
            problems.append(f"cradle for {sz} missing (run generate.py --variant v010)")
            continue
        C = json.loads((fab / f"cradle_{sz}.geometry.json").read_text())
        script = [{"command": "inspect.measure", "params": {}}, {"command": "inspect.interference", "params": {"exclude_pairs": [["pogo_1", "cradle_base"], ["pogo_2", "cradle_base"]]}}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(script, fh)
            tmp = fh.name
        r = subprocess.run([CLI, "run", tmp, "--in", str(sc), "--results", "--quiet"], capture_output=True, text=True, cwd=HERE)
        Path(tmp).unlink(missing_ok=True)
        if r.returncode != 0:
            problems.append(f"cradle {sz} check failed to run: {(r.stdout + r.stderr)[-200:]}")
            continue
        res = json.loads(r.stdout)
        interf = next(x for x in res if "interferences" in x)
        for i in interf["interferences"]:
            if i.get("volume_mm3", 1) > 1e-4:
                problems.append(f"cradle {sz}: interference {i['a']} x {i['b']} {i['volume_mm3']:.4f} mm3")
        for u in interf.get("unchecked", []):
            problems.append(f"cradle {sz}: pair not checked {u['a']} x {u['b']}")
        if not (0.4 <= C["compression"] <= 1.8):
            problems.append(f"cradle {sz}: pogo compression {C['compression']} mm outside 0.4..1.8 (stroke ~2 mm)")
        warns.append(f"cradle {sz}: pogo compression {C['compression']} mm, tip free {C['tip_free']} mm, pad plane {C['depth_to_pad']} mm below the lid face, pins {cr['pin_tube_d']} mm tube in d{cr['bore_d']} bores")
    return problems, warns
