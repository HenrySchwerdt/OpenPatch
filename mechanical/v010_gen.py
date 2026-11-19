# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Driver of `generate.py --variant v010` (kept out of generate.py to stay additive). TEST PROJECT, water only."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import op_v010
from generate import BENCH_COLORS, BENCH_EXPLODE, REAL_NAMES, envelope_info, run_cli
from op_build import BENCH_MFG_PARTS, BENCH_PART_NAMES, build_model
from op_cmds import Script
from op_layout import HERE
from op_mould import build_mould

V_EXPLODE = dict(BENCH_EXPLODE)
V_EXPLODE.update({"e73": (0, 0, -9), "pico_conn": (0, 0, -9), "pico_plug": (-8, 0, -9), "battery": (0, 0, -5), "bat_foam": (0, 0, -7), "bat_pad_p": (0, 0, -5), "bat_pad_n": (0, 0, -5),
                  "spring_p": (0, 0, 3), "spring_n": (0, 0, 3), "piezo": (0, 0, 14), "switch": (0, 0, 14), "chg_pad_1": (0, 0, 10), "chg_pad_2": (0, 0, 10),
                  "charge_gasket": (0, 0, 17), "pod_board": (0, 0, 8)})
V_COLORS = BENCH_COLORS + ["--body", "e73:color=#222222", "--body", "battery:color=#3a5fcd", "--body", "bat_foam:color=#e8d8a0", "--body", "piezo:color=#d0b030",
                           "--body", "pico_conn:color=#eeeeee", "--body", "charge_gasket:color=#cc5555", "--body", "chg_pad_1:color=#e8c36a", "--body", "chg_pad_2:color=#e8c36a"]


def generate_size(p: dict, variant: str, outdir: Path, snapshots: bool) -> dict:
    s, L = build_model(p, variant)
    G = op_v010.geometry(p, L)
    op_v010.build(s, p, L, G)
    L["v010"] = G
    MFG, NAMES = op_v010.part_lists(BENCH_MFG_PARTS, BENCH_PART_NAMES)
    created = {c["params"].get("body_name") for c in s.dumps() if c["params"].get("body_name")}
    created |= {"e73", "pico_conn", "pico_plug"}
    created -= {"ffc_conn", "ffc_cable"}
    asm = [b for b in NAMES if b != "pcb_keepout" and b in created]
    MFG = {k: [b for b in v if b in created] for k, v in MFG.items() if any(b in created for b in v)}
    tag = variant
    s.export_step(str(outdir / f"{tag}_assembly.step"), asm)
    for part, bodies in MFG.items():
        s.export_step(str(outdir / f"{tag}_{part}.step"), bodies)
        s.export_stl(str(outdir / f"{tag}_{part}.stl"), bodies)
    script = outdir / f"{tag}.script.json"
    script.write_text(json.dumps(s.dumps(), indent=1), encoding="utf-8")
    sc = outdir / f"{tag}.sc"
    run_cli("run", str(script), "--save", str(sc), "--quiet")
    real_sc = sc
    if not L["coax"]:
        from op_models import REPLACED, glb_cmds, real_model_cmds
        mcmds = real_model_cmds(p, L, variant) + glb_cmds(os.path.relpath(outdir / f"{tag}_assembly.glb", HERE))
        mjson = outdir / f"{tag}.models.script.json"
        mjson.write_text(json.dumps(mcmds, indent=1), encoding="utf-8")
        real_sc = outdir / f"{tag}_real.sc"
        run_cli("run", str(mjson), "--in", str(sc), "--save", str(real_sc), "--quiet")
        created = (created - set(REPLACED)) | set(REAL_NAMES)
    L["envelope"] = envelope_info(p, L)
    (outdir / f"{tag}.mech.json").write_text(json.dumps(L, indent=1), encoding="utf-8")
    (outdir / f"{tag}.layout.json").write_text(json.dumps(op_v010.layout_json(p, L, G), indent=1), encoding="utf-8")
    for f in ("mould_lower.step", "mould_upper.step", "mould_lower.stl", "mould_upper.stl"):
        shutil.copy(outdir / f, outdir / f"{tag}_{f}")
    if snapshots:
        shots(real_sc, outdir, tag, L, created)
    return L


def shots(sc: Path, outdir: Path, tag: str, L: dict, created: set) -> None:
    cols = [x for k, x in enumerate(V_COLORS) if x == "--body" and k + 1 < len(V_COLORS) and V_COLORS[k + 1].split(":")[0] in created
            or (k > 0 and V_COLORS[k - 1] == "--body" and x.split(":")[0] in created)]
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_iso.png"), "--view", "iso", "--width", "1600", "--height", "900", *cols)
    ex = Script()
    ex.add("parameters.add", name="p_dummy_explode", expression="0", comment="exploded-view helper")
    for b, t in V_EXPLODE.items():
        if b in created:
            ex.move([b], t)
    exj = outdir / f"{tag}.explode.json"
    exj.write_text(json.dumps(ex.dumps()), encoding="utf-8")
    run_cli("snapshot", str(exj), "--in", str(sc), "--out", str(outdir / f"{tag}_exploded.png"), "--view", "iso", "--width", "2000", "--height", "1300", "--no-grid", "--no-axes", *cols)
    exj.unlink()
    G = L["v010"]
    secs = [("section_y_electronics", G["cell_yc"]), ("section_y_dock", L["dock"]["y_c"]), ("section_y_charge", G["charge_pads"][0]["center_pod"][1])]
    for nm, y in secs:
        cam = {"target": [L["length"] / 2, y, L["height"] / 2], "yaw": 3.14159, "pitch": 0.0, "distance": 0.75 * L["length"]}
        run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_{nm}.png"), "--camera", json.dumps(cam), "--section", f"y={y:.2f}", "--width", "2000", "--height", "600",
                "--no-grid", "--no-axes", *cols)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_section_plan_bottom.png"), "--view", "top", "--section", "z=3.9", "--width", "2000", "--height", "800", "--no-grid", "--no-axes", *cols)
    run_cli("snapshot", str(sc), "--out", str(outdir / f"{tag}_top.png"), "--view", "top", "--width", "2000", "--height", "800", "--no-grid", "--no-axes", *cols)


def main(p0: dict, sizes: list[str] | None, outdir: str | None, no_snapshots: bool, snapshot_sizes: list[str]) -> None:
    p = op_v010.prepare(p0)
    out = Path(outdir or (HERE / "out" / "v010"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "params.used.json").write_text(json.dumps(p, indent=1), encoding="utf-8")
    ms, _ = build_mould(p)
    mj = out / "mould.script.json"
    mj.write_text(json.dumps(ms.dumps()).replace("__OUT__", os.path.relpath(out, HERE)), encoding="utf-8")
    run_cli("run", str(mj), "--save", str(out / "mould.sc"), "--quiet")
    import copy
    for v in sizes or list(p["variants"]):
        L = generate_size(copy.deepcopy(p), v, out, (not no_snapshots) and v in snapshot_sizes)
        print(f"{v}: L={L['length']:.2f} W={L['width']:.1f} H={L['height']:.1f} U/step={L['drive']['u_per_step']:.5f} env={L['envelope']['bbox_volume_ml']} ml -> {out}")
    try:
        from op_cradle import build_cradle_files
        build_cradle_files(p, out)
    except ImportError:
        pass
