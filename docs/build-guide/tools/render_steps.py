#!/usr/bin/env python3
"""Render the cumulative assembly step images of the OP-100 bench pod (build guide).

TEST PROJECT: bench pod, water only, never worn. Reads mechanical/out/bench/OP-100.sc (made by
`python3 mechanical/generate.py --variant bench --sizes OP-100`), hides every body that is not yet
built in a step (SolidCraft `browser.visibility`), colours the parts that are new in the step, greys the
rest, renders an assembled view and an exploded view with `solidcraft-cli snapshot`, and composes
one PNG per step with the exploded inset and numbered callouts (Pillow).

    python3 docs/build-guide/tools/render_steps.py            # all steps
    python3 docs/build-guide/tools/render_steps.py --only s06 s07
    python3 docs/build-guide/tools/render_steps.py --compose-only   # re-compose from cached raw renders

Needs `solidcraft-cli` (SOLIDCRAFT_CLI, else PATH) and Pillow. Raw renders go to the scratch dir
(--raw, default docs/build-guide/img/.raw, git-ignored), composites to docs/build-guide/img/.
All sizes use the same layout; only the stroke (reservoir length) differs, so OP-100 is the reference.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MECH = ROOT / "mechanical"
SC = MECH / "out" / "bench" / "OP-100.sc"
IMG = HERE.parent / "img"
CLI = os.environ.get("SOLIDCRAFT_CLI") or shutil.which("solidcraft-cli") or "/usr/local/bin/solidcraft-cli"

# ---- body groups (names in the .sc; bodies named t_* are cut tools and are not displayed) -------------------
G = {
    "shell": ["bottom"],
    "lid": ["top"],
    "gasket": ["gasket"],
    "plunger": ["plunger_core", "plunger_nose", "seal_a", "seal_b"],
    "reservoir": ["reservoir"],
    "cap": ["end_cap", "septum", "duckbill_valve", "needle_hub", "needle"],
    "motor": ["motor", "gearhead", "motor_boss", "motor_shaft", "motor_rear_boss", "motor_term", "motor_pins", "gear_a"],
    "gearb": ["gear_b"],
    "screw": ["leadscrew", "bush_dry", "bush_far"],
    "mag": ["magnet"],
    "carriage": ["carriage", "nut", "tongue_shim"],
    "board": ["pod_board", "hall_tmag", "hall_drv0", "hall_drv1", "hall_dock", "ffc_conn", "ffc_cable"],
    "dock": ["dock_insert"],
    "adapter": ["cannula_adapter", "dock_magnet"],
}
ALL = [b for v in G.values() for b in v]

# colours of the parts that are new in a step (everything built earlier is neutral grey)
COL = {
    "bottom": ("#d3d9df", 1.0), "top": ("#5f86ad", 0.4), "gasket": ("#111111", 1.0),
    "reservoir": ("#7fd0e0", 0.45), "plunger_core": ("#e0803a", 1.0), "plunger_nose": ("#f0a060", 1.0),
    "seal_a": ("#dd3333", 1.0), "seal_b": ("#dd3333", 1.0),
    "carriage": ("#f0c040", 1.0), "nut": ("#b8860b", 1.0), "tongue_shim": ("#e8e8e8", 1.0),
    "motor": ("#4f7fb8", 1.0), "gearhead": ("#7da3d6", 1.0), "motor_boss": ("#7da3d6", 1.0), "motor_shaft": ("#e0e0e0", 1.0),
    "motor_rear_boss": ("#7da3d6", 1.0), "motor_term": ("#2e8b57", 1.0), "motor_pins": ("#d4a017", 1.0),
    "gear_a": ("#d4a017", 1.0), "gear_b": ("#e0b030", 1.0),
    "leadscrew": ("#cfd8dc", 1.0), "bush_dry": ("#1aa6a6", 1.0), "bush_far": ("#1aa6a6", 1.0), "magnet": ("#cc2222", 1.0),
    "pod_board": ("#2e8b57", 1.0), "hall_tmag": ("#222222", 1.0), "hall_drv0": ("#222222", 1.0), "hall_drv1": ("#222222", 1.0),
    "hall_dock": ("#222222", 1.0), "ffc_conn": ("#222222", 1.0), "ffc_cable": ("#e8c36a", 1.0),
    "end_cap": ("#3a6ea5", 1.0), "septum": ("#f5f5f5", 1.0), "duckbill_valve": ("#5ec8e8", 1.0),
    "needle": ("#e8e8e8", 1.0), "needle_hub": ("#444444", 1.0),
    "dock_insert": ("#e07ac0", 1.0), "cannula_adapter": ("#7a5cc7", 0.9), "dock_magnet": ("#cc2222", 1.0),
}
GREY = ("#aab2ba", 0.85)
GREY_SHELL = ("#c9d3dd", 0.4)

# pod centre (OP-100: 47 x 32 x 8.4)
C = [23.5, 15.0, 3.0]


def cam(target=None, yaw=0.05, pitch=0.85, dist=60.0):
    return {"target": list(target or C), "yaw": yaw, "pitch": pitch, "distance": dist}


# ---- steps: build order of the guide. `new` = groups added in this step; `gone` = groups to hide although earlier ---
STEPS = [
    dict(id="s00", name="parts overview (exploded)", groups=["shell", "lid", "gasket", "plunger", "reservoir", "cap", "motor", "gearb",
         "screw", "mag", "carriage", "board", "dock", "adapter"], new=["lid", "gasket", "plunger", "reservoir", "cap", "motor", "gearb", "screw", "mag",
         "carriage", "board", "dock", "adapter", "shell"], camera=cam([22, 14, 12], dist=88.0), explode_only=True,
         explode={"top": (0, 0, 34), "gasket": (0, 0, 27), "ffc_cable": (16, 0, 22), "ffc_conn": (0, 0, 20), "hall_drv0": (0, 0, 20), "hall_drv1": (0, 0, 20),
                  "pod_board": (0, 0, 18), "hall_tmag": (0, 0, 14), "hall_dock": (0, 0, 14),
                  "carriage": (0, 0, 22), "nut": (0, 0, 22), "tongue_shim": (0, 0, 22),
                  "plunger_core": (0, 0, 28), "plunger_nose": (0, 0, 28), "seal_a": (0, 0, 28), "seal_b": (0, 0, 28),
                  "leadscrew": (0, 0, 14), "magnet": (0, 0, 14), "bush_far": (0, 0, 14), "bush_dry": (0, 0, 14),
                  "gear_a": (0, 0, 12), "gear_b": (0, 0, 12), "reservoir": (0, 0, 10),
                  "end_cap": (6, 0, 10), "septum": (6, -12, 10), "duckbill_valve": (6, 0, 16), "needle": (10, 0, 4), "needle_hub": (8, 0, 4),
                  "motor": (0, 10, 12), "gearhead": (0, 10, 12), "motor_boss": (0, 10, 12), "motor_shaft": (0, 10, 12), "motor_rear_boss": (0, 10, 12),
                  "motor_term": (0, 10, 12), "motor_pins": (0, 10, 12),
                  "dock_insert": (14, 0, -4), "cannula_adapter": (14, 0, -16), "dock_magnet": (14, 0, -22)}),
    dict(id="s03", name="plunger", groups=["plunger"], new=["plunger"], camera=cam([6, 11, 4], yaw=0.5, pitch=0.6, dist=34.0),
         explode={"plunger_nose": (7, 0, 0), "seal_a": (0, 0, 7), "seal_b": (0, 0, 7)}, only_new=True),
    dict(id="s04", name="carriage", groups=["carriage"], new=["carriage"], camera=cam([7, 22.5, 4.2], yaw=0.5, pitch=0.6, dist=20.0),
         explode={"nut": (-6, 0, 0), "tongue_shim": (0, -6, 0)}, only_new=True),
    dict(id="s05", name="reservoir and end cap", groups=["reservoir", "cap", "plunger"], new=["reservoir", "cap", "plunger"],
         camera=cam([20, 11, 4], yaw=0.55, pitch=0.65, dist=60.0),
         explode={"end_cap": (9, 0, 0), "septum": (9, -10, 0), "duckbill_valve": (9, 0, 10), "needle_hub": (16, 0, 0), "needle": (16, 0, 0),
                  "plunger_core": (-10, 0, 0), "plunger_nose": (-10, 0, 0), "seal_a": (-10, 0, 0), "seal_b": (-10, 0, 0)}, only_new=True),
    dict(id="s06", name="bottom shell, reservoir in place", groups=["shell", "reservoir", "cap", "plunger"], new=["shell"],
         camera=cam()),
    dict(id="s07", name="leadscrew, carriage, gear B", groups=["shell", "reservoir", "cap", "plunger", "screw", "gearb", "carriage"],
         new=["screw", "gearb", "carriage"], camera=cam()),
    dict(id="s08", name="motor, gear A, spindle magnet", groups=["shell", "reservoir", "cap", "plunger", "screw", "gearb", "carriage", "motor", "mag"],
         new=["motor", "mag"], camera=cam()),
    dict(id="s09", name="pod sensor board and FFC", groups=["shell", "reservoir", "cap", "plunger", "motor", "gearb", "screw", "mag", "carriage", "board"],
         new=["board"], camera=cam()),
    dict(id="s10", name="gasket and lid", groups=["shell", "reservoir", "cap", "plunger", "motor", "gearb", "screw", "mag", "carriage", "board", "gasket", "lid"],
         new=["gasket", "lid"], camera=cam()),
    dict(id="s11", name="dock insert and dummy cannula head", groups=["shell", "reservoir", "cap", "plunger", "motor", "gearb", "screw", "mag", "carriage", "board", "gasket", "lid", "dock", "adapter"],
         new=["dock", "adapter"], camera=cam([36, 11, 3], yaw=0.5, pitch=0.6, dist=45.0)),
]

DEFAULT_EXPLODE = {
    "plunger": (0, 0, 10), "carriage": (0, 0, 9), "cap": (0, 0, 9), "reservoir": (0, 0, 8), "motor": (0, 0, 9), "gearb": (0, 0, 9), "mag": (6, 0, 4),
    "screw": (0, 0, 9), "board": (0, 0, 9), "gasket": (0, 0, 9), "lid": (0, 0, 14), "dock": (14, 0, 3), "adapter": (14, 0, 0), "shell": (0, 0, -8),
}


def run(args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True, cwd=MECH)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-1500:] + r.stderr[-1500:])
        raise SystemExit("solidcraft-cli failed: " + " ".join(args[:3]))
    return r


def make_script(step, exploded, raw):
    vis = {b for g in step["groups"] for b in G[g]}
    hide = [b for b in ALL if b not in vis]
    cmds = []
    if hide:
        cmds.append({"command": "browser.visibility", "params": {"visible": False, "items": hide}})
    if exploded:
        ex = step.get("explode")
        if ex is None:
            ex = {}
            for g in step["new"]:
                t = DEFAULT_EXPLODE.get(g, (0, 0, 9))
                for b in G[g]:
                    ex[b] = t
        for b, t in ex.items():
            if b in vis and any(t):
                cmds.append({"command": "solid.move", "params": {"bodies": [b], "translate": list(t)}})
    p = raw / f"{step['id']}{'_x' if exploded else ''}.json"
    p.write_text(json.dumps(cmds), encoding="utf-8")
    return p


def body_args(step):
    out = []
    new = {b for g in step["new"] for b in G[g]}
    vis = {b for g in step["groups"] for b in G[g]}
    for b in ALL:
        if b not in vis:
            continue
        if b in new:
            c, o = COL[b]
        else:
            c, o = GREY_SHELL if b in ("bottom", "top") else (("#9fc4cc", 0.3) if b == "reservoir" else GREY)
        out += ["--body", f"{b}:color={c},opacity={o}"]
    return out


def render(step, exploded, raw, width, height):
    out = raw / f"{step['id']}{'_x' if exploded else ''}.png"
    script = make_script(step, exploded, raw)
    args = ["snapshot", str(script), "--in", str(SC), "--out", str(out), "--camera", json.dumps(step["camera"]),
            "--width", str(width), "--height", str(height), "--no-grid", "--no-axes", "--quality", "normal"]
    args += body_args(step)
    run(args)
    return out


def render_section(out):
    """Plan section through the drive axis plane (z = 4.2 mm), full colour, close framing -> img/section_plan_z4.2.png."""
    cols = []
    for b, (c, o) in COL.items():
        cols += ["--body", f"{b}:color={c},opacity={o}"]
    cols += ["--body", "top:opacity=0.05", "--body", "bottom:color=#c9d3dd,opacity=0.55"]
    cam_ = {"target": [23.5, 16.0, 4.2], "yaw": 0.0, "pitch": 1.5707, "distance": 56.0}
    run(["snapshot", str(SC), "--out", str(out), "--camera", json.dumps(cam_), "--section", "z=4.2", "--width", "1400", "--height", "900",
         "--no-grid", "--no-axes", *cols])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--raw", default=str(IMG / ".raw"))
    ap.add_argument("--compose-only", action="store_true")
    ap.add_argument("--section", action="store_true", help="render the plan section figure only")
    ap.add_argument("--x-only", action="store_true", help="only (re)render the exploded inset")
    a = ap.parse_args()
    raw = Path(a.raw)
    raw.mkdir(parents=True, exist_ok=True)
    if a.section:
        render_section(raw / "section_plan.png")
        print("section rendered")
        return
    for st in STEPS:
        if a.only and st["id"] not in a.only:
            continue
        if not a.compose_only:
            if st.get("explode_only"):
                render(st, True, raw, 1600, 1100)
            else:
                if not a.x_only:
                    render(st, False, raw, 1200, 800)
                render(st, True, raw, 900, 600)
            print("rendered", st["id"], st["name"], flush=True)
    compose(a)


def compose(a):
    try:
        from compose_steps import compose_all, compose_section
    except ImportError:
        sys.path.insert(0, str(HERE))
        from compose_steps import compose_all, compose_section
    compose_all(STEPS, Path(a.raw), IMG, only=a.only)
    if not a.only:
        compose_section(Path(a.raw), IMG)


if __name__ == "__main__":
    main()
