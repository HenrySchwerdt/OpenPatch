# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Driver of `generate.py --variant v010` (the integrated pod of op_pod.py).  TEST PROJECT, water only.

The earlier tail-based / stack layouts (op_v010.py, op_v010s.py, op_cradle.py) are superseded and not used any more (kept in git history).
"""
from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

import op_pod
import op_pod_shell
from generate import envelope_info, run_cli
from op_cmds import Script
from op_layout import HERE
from op_mould import build_mould

MFG_PARTS = {"bottom": ["bottom"], "top": ["top"], "gasket": ["gasket"], "reservoir": ["reservoir"], "plunger_core": ["plunger_core"], "plunger_seal": ["seal_a", "seal_b"],
             "end_cap": ["end_cap"], "end_cap_lid": ["end_cap_lid"], "cap_gasket": ["cap_gasket"], "dock_insert": ["dock_insert"], "cannula_adapter": ["cannula_adapter"],
             "usb_gasket": ["usb_gasket"]}
PURCHASED = ["drive_screw", "rear_plug", "nut", "bush_dry2", "thrust_sleeve2", "gear_d", "gear_a", "ring_magnet", "motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss",
             "motor_term", "motor_pins", "cap_oring", "septum", "needle", "needle_hub", "dock_magnet", "hall_dock", "pod_board", "radio", "switch", "piezo", "battery", "bat_foam",
             "bat_pad_p", "bat_pad_n", "spring_p", "spring_n", "usb_conn", "usb_board", "sensor_board", "hall_tmag", "motor_card", "mspring_1", "mspring_2", "mspring_3", "mspring_4",
             "spine_fpc", "spine_springs"]
PART_NAMES = [b for v in MFG_PARTS.values() for b in v] + PURCHASED
EXCLUDE_PAIRS = [["gear_a", "gear_d"], ["motor_term", "motor_pins"],            # meshing teeth: both modelled as tip circles
                 ["needle_hub", "end_cap"], ["needle", "end_cap"], ["septum", "end_cap"], ["septum", "end_cap_lid"], ["cap_oring", "reservoir"], ["cap_oring", "end_cap"],
                 ["cap_oring", "end_cap_lid"], ["cap_gasket", "end_cap"], ["cap_gasket", "end_cap_lid"], ["end_cap", "end_cap_lid"], ["needle", "end_cap_lid"], ["cap_gasket", "cap_oring"]]

EXPLODE = {"top": (0, 0, 24), "piezo": (0, 0, 20), "switch": (0, 0, 16), "radio": (0, 0, 16), "pod_board": (0, 0, 12), "hall_dock": (0, 0, 12), "gasket": (0, 0, 17),
           "spine_springs": (0, 0, 8), "spine_fpc": (0, 0, -6), "battery": (0, 0, -3), "bat_foam": (0, 0, -6), "bat_pad_p": (0, 0, -3), "bat_pad_n": (0, 0, -3), "spring_p": (0, 0, 8), "spring_n": (0, 0, 8),
           "sensor_board": (0, 0, 9), "hall_tmag": (0, 0, 13), "usb_conn": (-10, 0, 0), "usb_board": (-6, 0, 0), "usb_gasket": (-12, 0, 0), "motor_card": (0, 14, 0),
           "mspring_1": (0, 14, 0), "mspring_2": (0, 14, 0), "mspring_3": (0, 14, 0), "mspring_4": (0, 14, 0),
           "ring_magnet": (0, 0, 14), "gear_d": (0, 0, 12), "gear_a": (0, 0, 12), "thrust_sleeve2": (0, 0, 10), "bush_dry2": (0, 0, 10), "nut": (0, 0, 12), "drive_screw": (0, 0, 18),
           "plunger_core": (0, 0, 10), "seal_a": (0, 0, 10), "seal_b": (0, 0, 10), "reservoir": (0, 0, 6),
           "motor": (0, 0, 8), "gearhead": (0, 0, 8), "motor_boss": (0, 0, 8), "motor_shaft": (0, 0, 8), "motor_rear_boss": (0, 0, 8), "motor_term": (0, 0, 8), "motor_pins": (0, 0, 8),
           "end_cap_lid": (0, 0, 16), "cap_gasket": (0, 0, 8), "cap_oring": (-3, 0, 4), "septum": (0, 0, -8), "needle": (0, 0, -6), "needle_hub": (0, 0, -3),
           "dock_insert": (0, 0, -8), "cannula_adapter": (0, 0, -12), "dock_magnet": (0, 0, -16), "bottom": (0, 0, -10)}
COLORS = ["--body", "top:opacity=0.16,color=#9fb3c8", "--body", "bottom:opacity=0.6,color=#c9d3dd", "--body", "reservoir:opacity=0.5,color=#7fd0e0", "--body", "plunger_core:color=#e0803a",
          "--body", "pod_board:color=#2e8b57", "--body", "sensor_board:color=#2e8b57", "--body", "usb_board:color=#2e8b57", "--body", "motor_card:color=#2e8b57", "--body", "spine_fpc:color=#e8c36a",
          "--body", "battery:color=#3a5fcd", "--body", "dock_insert:color=#e07ac0", "--body", "cannula_adapter:color=#7a5cc7", "--body", "motor:color=#888888", "--body", "gearhead:color=#aaaaaa",
          "--body", "dock_magnet:color=#cc2222", "--body", "ring_magnet:color=#cc2222", "--body", "drive_screw:color=#f0c040", "--body", "usb_conn:color=#bbbbbb", "--body", "radio:color=#222222",
          "--body", "gasket:color=#111111", "--body", "usb_gasket:color=#111111", "--body", "seal_b:color=#dd3333", "--body", "gear_d:color=#d4a017", "--body", "gear_a:color=#d4a017"]


def prepare(p0: dict) -> dict:
    return op_pod.prepare(p0)


def build_model(p: dict, size: str) -> tuple[Script, dict]:
    build_gasket = op_pod_shell.build_gasket
    L = op_pod.layout(p, size)
    L["geo"] = op_pod.geometry(p, L)
    s = Script()
    s.parameter("p_stroke", L["stroke"], "Generator value (info)")
    s.parameter("p_length", L["length"], "Generator value (info)")
    op_pod_shell.build_bottom(s, p, L)
    op_pod_shell.build_top(s, p, L)
    build_gasket(s, p, L)
    op_pod.build_reservoir(s, p, L)
    op_pod.build_plunger(s, p, L)
    op_pod.build_drive(s, p, L)
    op_pod.build_fluid(s, p, L)
    op_pod.build_dock_parts(s, p, L)
    op_pod.build_electronics(s, p, L)
    return s, L


def generate_size(p: dict, size: str, outdir: Path, snapshots: bool) -> dict:
    s, L = build_model(p, size)
    created = {c["params"].get("body_name") for c in s.dumps() if c["params"].get("body_name")}
    asm = [b for b in PART_NAMES if b in created]
    mfg = {k: [b for b in v if b in created] for k, v in MFG_PARTS.items() if any(b in created for b in v)}
    tag = size
    s.export_step(str(outdir / f"{tag}_assembly.step"), asm)
    for part, bodies in mfg.items():
        s.export_step(str(outdir / f"{tag}_{part}.step"), bodies)
        s.export_stl(str(outdir / f"{tag}_{part}.stl"), bodies)
    script = outdir / f"{tag}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = outdir / f"{tag}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    L["envelope"] = envelope_info(p, L)
    L["bodies_created"] = sorted(created)
    (outdir / f"{tag}.mech.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    (outdir / f"{tag}.layout.json").write_text(json.dumps(layout_json(p, L), indent=1), encoding="utf-8")
    for f in ("mould_lower.step", "mould_upper.step", "mould_lower.stl", "mould_upper.stl"):
        shutil.copy(outdir / f, outdir / f"{tag}_{f}")
    real = None
    try:
        import v010_real
        real = v010_real.make_real(p, L, outdir, tag, sc)
    except ImportError:
        pass
    if snapshots:
        shots(real or sc, outdir, tag, L, created)
    return L


def layout_json(p: dict, L: dict) -> dict:
    """Interface file for the electronics agent: schema openpatch-v010-layout/3 (integrated pod, coaxial drive).  All coordinates in the pod frame (mm)."""
    G = L["geo"]
    P = p["pod"]
    xr = L["x_r1"]
    ring = L["ring"]
    return {
        "schema": "openpatch-v010-layout/3", "size": L["variant"],
        "note": "TEST PROJECT, water only. Pod frame: X length (rear outer face 0, dock mouth +X), Y width, Z up (0 = skin). u = x - x_r1.",
        "pod_mm": [round(L["length"], 3), L["width"], L["height"]], "x_r1": round(xr, 3),
        "z_stack": {"board_bottom": G["z0"], "board_top": G["ztop"], "lid_inner": L["z_top_inner"], "dome_top": p["cannula"]["B_dome_h"], "insert_bridge_top": 5.2},
        "main_board": {"outline_pod_mm": G["board_outline_pod"], "outline_u_mm": G["board_outline_u"], "thickness": P["board"]["t"], "area_mm2": G["board_area_mm2"],
                       "locating_pins_u": G["board_holes_u"], "pin_hole_d": P["pins"]["hole_d"],
                       "zones": {"dock_tunnel": {"u": [P["board"]["u_left"], L["tail_u"] - 1.6], "y": P["board"]["tunnel_y"], "bottom_max_h_mm": 0.0, "note": "nothing on the bottom side except the dock hall (X2SON 0.4) at the dome centre + 5.6"},
                                 "cell_wing": {"y": P["board"]["wing_y"], "bottom_max_h_mm": 0.0, "note": "the cell lies below, 2 SMD spring contacts pointing down onto its pads"},
                                 "spine_tongue": {"note": "8-contact spring row pointing down onto the spine FPC on the shelf (G.spine.springs)"}},
                       "top_max_height_mm": round(L["z_top_inner"] - G["ztop"] - 0.4, 2),
                       "top_parts": {"radio_envelope": G["radio"], "button": G["switch"]},
                       "dock_hall": {"x": round(L["dock"]["x_d"] + p["bench"]["adapter"]["magnet_dx"], 3), "y": L["dock"]["y_c"], "pkg": p["bench"]["dock"]["pkg"]}},
        "cell": {"bay": G["cell"], "pads": G["cell_pads"], "spring_gap_mm": G["spring_gap"], "class": P["cell"]["class"], "envelope_mm": [P["cell"]["l"], P["cell"]["w"], P["cell"]["t"]]},
        "sensor_board": {**G["sensor"], "thickness": P["ring"]["tmag"]["board_t"], "magnet": {"type": "diametric ring", "x": [round(ring[0], 3), round(ring[1], 3)], "od": P["ring"]["od"], "id": P["ring"]["id"],
                                                                                         "axis": {"y": round(L["y_r"], 3), "z": round(L["z_axis"], 3)}, "ratio_to_screw_turn": 1.0,
                                                                                         "turns_per_motor_turn": round(P["motor"]["gear"]["z_motor"] / P["motor"]["gear"]["z_screw"], 4)}},
        "usb": {**G["usb"], "part": P["usb"]["part"]},
        "motor": {"option": P["motor"]["option"], "axis": {"y": round(L["y_m"], 3), "z": round(L["z_axis"], 3)}, "x_rear": round(L["x_mrear"], 3), "x_gearbox_front": round(L["x_gh1"], 3),
                  "terminal_pins": {"x": G["motor_pin_x"], "z": G["motor_card"]["spring"]["z_centres"], "tip_y": G["motor_card"]["pin_tip_y"], "pitch": 1.2, "order": ["B", "A-", "B+", "A"]},
                  "contact_card": G["motor_card"]},
        "spine_fpc": G["spine"],
        "vent": G["vent"], "piezo": G["piezo"],
        "drive": {"stroke_mm": round(L["stroke"], 3), "bore_area_mm2": round(L["area"], 2), "gear": [P["motor"]["gear"]["z_motor"], P["motor"]["gear"]["z_screw"]],
                  "u_per_step": round(u_per_step(p, L), 6), "screw_pitch": p["drive"]["screw_pitch"]},
        "envelope": L["envelope"],
    }


def u_per_step(p: dict, L: dict) -> float:
    dr, g = p["drive"], p["pod"]["motor"]["gear"]
    ratio = dr["gh_ratio"]
    # screw advance per motor turn = pitch * z_motor / z_screw; steps per motor-shaft turn = steps_per_rev * gearhead ratio
    mm_step = dr["screw_pitch"] * g["z_motor"] / g["z_screw"] / (dr["steps_per_rev"] * 26.45)
    return mm_step * L["area"] / 10.0


def shots(sc: Path, outdir: Path, tag: str, L: dict, created: set) -> None:
    cols = [x for k, x in enumerate(COLORS) if x == "--body" and k + 1 < len(COLORS) and COLORS[k + 1].split(":")[0] in created
            or (k > 0 and COLORS[k - 1] == "--body" and x.split(":")[0] in created)]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_iso.png"), "--view", "iso", "--width", "1600", "--height", "900", *cols)
    ex = Script()
    ex.add("parameters.add", name="p_dummy_explode", expression="0", comment="exploded-view helper")
    for b, t in EXPLODE.items():
        if b in created:
            ex.move([b], t)
    exj = outdir / f"{tag}.explode.json"
    exj.write_text(json.dumps(ex.dumps()), encoding="utf-8")
    run_cli("snapshot", str(exj), "--in", str(sc), "--out", str(outdir / f"{tag}_exploded.png"), "--view", "iso", "--width", "2000", "--height", "1300", "--no-grid", "--no-axes", *cols)
    exj.unlink()
    secs = [("section_y_drive", L["y_r"]), ("section_y_fluid", L["dock"]["y_c"]), ("section_y_motor", L["y_m"])]
    for nm, y in secs:
        cam = {"target": [L["length"] / 2, y, L["height"] / 2], "yaw": 3.14159, "pitch": 0.0, "distance": 0.8 * L["length"]}
        run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_{nm}.png"), "--camera", json.dumps(cam), "--section", f"y={y:.2f}", "--width", "2000", "--height", "600",
                "--no-grid", "--no-axes", *cols)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_section_plan_bottom.png"), "--view", "top", "--section", f"z={L['z_axis']:.2f}", "--width", "2000", "--height", "800", "--no-grid", "--no-axes", *cols)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_top.png"), "--view", "top", "--width", "2000", "--height", "800", "--no-grid", "--no-axes", *cols)


def main(p0: dict, sizes: list[str] | None, outdir: str | None, no_snapshots: bool, snapshot_sizes: list[str]) -> None:
    p = prepare(p0)
    sizes = sizes or list(p["pod"]["sizes"])           # spec 2c: OP-100 and OP-200 only
    out = Path(outdir or (HERE / "out" / "v010"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    ms, _ = build_mould(p)
    mj = out / "mould.script.json"
    mj.write_text(json.dumps(ms.dumps()).replace("__OUT__", os.path.relpath(out, HERE)), encoding="utf-8")
    run_cli("run", str(mj), "--save", str(out / "mould.sc"), "--quiet")
    for v in sizes:
        L = generate_size(copy.deepcopy(p), v, out, (not no_snapshots) and v in snapshot_sizes)
        print(f"{v}: L={L['length']:.2f} W={L['width']:.1f} H={L['height']:.1f} stroke={L['stroke']:.2f} U/step={u_per_step(p, L):.5f} (rear zone {L['rear_zone']:.1f}, limit: {L['gear_limit']}) "
              f"env={L['envelope']['bbox_volume_ml']} ml -> {out}")
