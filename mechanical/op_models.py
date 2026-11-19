"""Real component models (mechanical/components/) placed into the bench assembly.

The pod design (`OP-xx.sc`) is built with simple envelopes for the bought-in parts (fast, used by check.py).  This module
makes a second design `OP-xx_real.sc`: it removes the envelopes of the parts that exist in the component library
(NFP motor, two GHW gears, M1.6 rod, DIN 934 nut, spindle magnet, 30G needle, duckbill valve) and inserts the vendor-accurate STEP
models at the same poses.  Used for the renders, the exploded view, the glTF/GLB for the website and the real-part
interference check (`check.py`).

Pose convention: SolidCraft `file.insert_step` matrix = row-major 3x4 [R | t], the columns of R are the pod-frame images of the
component's local X, Y, Z axes (catalog.json `frame`).  Pod frame: X length, Y width, Z up.
"""
from __future__ import annotations

import math

COMP = "components/out"          # relative to mechanical/ (the CLI runs with cwd = mechanical/)

# envelope bodies that are replaced by library models
REPLACED = ["gearhead", "motor", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "motor_pins",
            "gear_a", "gear_b", "leadscrew", "nut", "magnet", "needle", "duckbill_valve"]

NFP_BODIES = ["gearbox", "motor_can", "front_boss", "shaft", "rear_boss", "term_block", "pin1", "pin2", "pin3", "pin4"]
# the motor library model is a one-piece assembly of overlapping solids (shaft through the boss, pins in the terminal block, ...)
NFP_INTERNAL = [[a, b] for i, a in enumerate(NFP_BODIES) for b in NFP_BODIES[i + 1:]]

# interference pairs that are intentional between real models (bores sized to the shaft, thread in the nut, press fits)
REAL_EXCLUDE = [["gear", "shaft"], ["gear (2)", "thrust_sleeve"], ["rod", "nut"], ["sleeve", "end_cap"], ["needle", "end_cap"], ["dbv", "end_cap"], ["dbv", "end_cap_lid"], ["needle", "end_cap_lid"],
                ["needle", "needle_hub"], ["gear", "gear (2)"]] + NFP_INTERNAL


def _mat(xl, yl, zl, t):
    """3x4 row-major matrix from the pod-frame images of local X, Y, Z and the translation t."""
    return [xl[0], yl[0], zl[0], t[0], xl[1], yl[1], zl[1], t[1], xl[2], yl[2], zl[2], t[2]]


def _along_x(t, theta_deg: float = 0.0):
    """Local Z -> pod +X; local X -> pod +Y (rotated by theta about X), local Y -> pod +Z."""
    c, s = math.cos(math.radians(theta_deg)), math.sin(math.radians(theta_deg))
    return _mat((0, c, s), (0, -s, c), (1, 0, 0), t)


def _ins(path: str, name: str, matrix: list[float]) -> dict:
    return {"command": "file.insert_step", "params": {"path": f"{COMP}/{path}.step", "flatten": True, "name": name, "matrix": [round(v, 12) for v in matrix]}}


def _box(name: str, x, y, z) -> dict:
    return {"command": "solid.box", "params": {"length": x[1] - x[0], "width": y[1] - y[0], "height": z[1] - z[0],
                                                 "corner": [x[0], y[0], z[0]], "body_name": name, "name": name}}


def _cut(target: str, tool: str) -> dict:
    return {"command": "solid.combine", "params": {"target": target, "tools": [tool], "operation": "cut", "name": f"cut {target}"}}


def real_model_cmds(p: dict, L: dict, size: str) -> list[dict]:
    dr = p["drive"]
    ym, ys, zc = L["y_m"], L["y_s"], L["z_axis"]
    gx0, gx1 = L["gear_x0"], L["gear_x1"]
    D = L["dock"]
    import os
    from pathlib import Path
    T = L["thrust"]
    rod_id = f"rod_m1p6_{T['rod_len']:g}"
    have_rod = (Path(__file__).resolve().parent / COMP / f"{rod_id}.step").exists()      # rod STEP files are gitignored (build_all.py --only)
    cmds: list[dict] = [{"command": "solid.remove", "params": {"bodies": [b for b in REPLACED if have_rod or b != "leadscrew"]}}]
    # NFP motor: local Z = shaft axis (tip +Z) -> pod -X; local Y -> pod +Z (terminal block on local -Y -> pod -Z); origin = gearbox mounting face
    cmds.append(_ins("nfp_608_26_45", "nfp", _mat((0, -1, 0), (0, 0, 1), (-1, 0, 0), (L["mx0"], ym, zc))))
    # pins as supplied are 1.05 mm long: trimmed flat to z 0.4 (parts.md 1.0) so they end in the floor pocket
    for k in range(1, 5):
        cmds += [_box(f"t_trim_pin{k}", (L["mx0"], L["mx0"] + 16), (ym - 8, ym + 8), (-2, 0.4)), _cut(f"pin{k}", f"t_trim_pin{k}")]
    cmds += [_box("t_trim_shaft", (-5, gx0 - 0.2), (ym - 3, ym + 3), (zc - 3, zc + 3)), _cut("shaft", "t_trim_shaft")]
    # gears: motor gear 16 T (390754, 5 wide -> skimmed to the pair's face width), screw gear 20 T (753020, hub turned off)
    G = L["gears"]
    za, zb = f"gear_m03_z{G['z_motor']}_390754", f"gear_m03_z{G['z_screw']}_753020"
    cmds.append(_ins(za, "gearA", _along_x((gx0, ym, zc))))
    cmds += [_box("t_trim_a", (gx1, gx1 + 6), (ym - 4, ym + 4), (zc - 4, zc + 4)), _cut("gear", "t_trim_a")]
    pitch_b = 360.0 / G["z_screw"]
    cmds.append(_ins(zb, "gearB", _along_x((gx0, ys, zc), theta_deg=pitch_b / 2)))        # tooth gap towards the motor gear
    cmds += [_box("t_trim_b", (gx0 - 4, gx0), (ys - 4, ys + 4), (zc - 4, zc + 4)), _cut("gear (2)", "t_trim_b")]
    # leadscrew M1.6 x 0.35 (modelled helical thread), cut length per size
    if have_rod:
        cmds.append(_ins(rod_id, "rod", _along_x((T["rod_x"][0], ys, zc))))
    # nut: hex corners along pod Z (like the carriage pocket), local X (flats) -> pod Y
    nut_x0 = L["xrear"] - p["bench"]["carriage"]["rear_wall"] + p["bench"]["carriage"]["nut_rear_wall"] + 0.1
    cmds.append(_ins("nut_din934_m1p6_brass", "nutM", _along_x((nut_x0, ys, zc))))
    # spindle magnet d3 x 1.5 diametric at the rod end (after the thrust collar)
    cmds.append(_ins("magnet_d3x1p5_diametric", "magM", _along_x((L["mag_x"][0], ys, zc))))
    # needle: component hub removed (the pod uses its own printed hub), needle cut to the pod's free length
    cmds.append(_ins("needle_30g_efd_14in", "ndl", _along_x((D["x_tip"] - 6.35, D["y_c"], D["z_n"]))))
    cmds += [{"command": "solid.remove", "params": {"bodies": ["hub"]}},
             _box("t_trim_n", (D["x_tip"] - 12, D["x_h0"]), (D["y_c"] - 2, D["y_c"] + 2), (D["z_n"] - 2, D["z_n"] + 2)), _cut("needle", "t_trim_n")]
    # duckbill valve in its cap pocket (inlet at valve_x0)
    cmds.append(_ins("duckbill_valve_generic", "dbv", _along_x((L["x_r1"] + p["dock"]["valve_x0"], D["y_c"], D["z_n"]))))
    return cmds


def glb_cmds(path: str) -> list[dict]:
    return [{"command": "file.export", "params": {"path": path, "format": "glb", "quality": "standard"}}]
