import json
import subprocess
import sys

sys.path.insert(0, ".")
import op_dock
import op_pod
import op_pod_shell
from op_cmds import Script
from op_layout import find_cli

p = op_pod.prepare(json.load(open("params.json")))
L = op_pod.layout(p, "OP-100")
L["geo"] = op_pod.geometry(p, L)


def run(label, fn):
    op_dock.build_mouth_cut = fn
    s = Script()
    op_pod_shell.build_bottom(s, p, L)
    tmp = "/tmp/claude-0/-home-user-ai-insulin-pump/81d3c0e6-4bc1-5e65-bb19-a2d3a00bcb66/scratchpad/qm.json"
    open(tmp, "w").write(json.dumps(s.dumps()))
    r = subprocess.run([find_cli(), "run", tmp, "--quiet"], capture_output=True, text=True)
    print(label, r.returncode, (r.stdout + r.stderr)[-90:].strip())


def mk(zb, xe_a, xe_b, zt, ya=0.0, yb=0.0):
    def f(s, p, L, name, top_part=False):
        dk, D = p["dock"], L["dock"]
        y0, y1 = D["y_c"] - D["mouth_half"], D["y_c"] + D["mouth_half"]
        lap = p["shell"]["lap_low"]
        x0 = L["length"] - L["wall"] - 0.3
        if top_part:
            return [s.box(name, (x0, L["length"] + xe_b), (y0, y1), (lap - 0.1, zt))]
        return [s.box(name + "a", (x0, L["length"] + xe_a), (y0, y1), (-0.1, lap - 0.05)), s.box(name + "b", (x0, L["length"] + xe_b), (y0 + yb, y1 - yb), (lap + zb, zt))]
    return f


def mk2(split, zt2):
    def f(s, p, L, name, top_part=False):
        D = L["dock"]
        y0, y1 = D["y_c"] - D["mouth_half"], D["y_c"] + D["mouth_half"]
        lap = p["shell"]["lap_low"]
        x0 = L["length"] - L["wall"] - 0.3
        lo = (-0.1, lap - 0.05)
        if top_part:
            return [s.box(name + "1", (x0, L["length"] - split), (y0, y1), (lap - 0.1, 5.6)), s.box(name + "2", (L["length"] - split - 0.05, L["length"] + 0.1), (y0, y1), (lap - 0.1, zt2))]
        return [s.box(name + "a", (x0, L["length"] + 0.1), (y0, y1), lo), s.box(name + "b", (x0, L["length"] - split), (y0, y1), (lap - 0.1, 5.6)),
                s.box(name + "c", (L["length"] - split - 0.05, L["length"] + 0.1), (y0, y1), (lap - 0.1, zt2))]
    return f


run("split 0.3 / 5.3", mk2(0.3, 5.3))
run("split 0.3 / 5.2", mk2(0.3, 5.2))
run("split 0.45 / 5.3", mk2(0.45, 5.3))
run("split 0.2 / 5.3", mk2(0.2, 5.3))
