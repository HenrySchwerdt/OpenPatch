#!/usr/bin/env python3
"""Regenerate the fit-check print kit (mechanical/print/OP-100/*.stl).

- mechanism and dummies: exported from mechanical/out/v010-cup/OP-100.sc with solidcraft-cli (pod frame)
- populated board: electronics/v010/cup/print_model.py on a placed board built by build_cup.py (pod frame)
usage: python3 make_print_kit.py <placed cup board .kicad_pcb>
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
OUT = os.path.join(HERE, "OP-100")
GROUPS = {"motor_dummy": ["motor", "gearhead", "motor_shaft", "motor_term"], "gear_a": ["gear_a"], "gear_b": ["gear_b"],
          "rod_nut_collar": ["rod", "nut", "thrust_collar", "bush_rod"], "magnet": ["magnet"], "cell_dummy": ["ko_battery"]}


def main():
    os.makedirs(OUT, exist_ok=True)
    cmds = [{"command": "file.export_stl", "params": {"path": os.path.abspath(os.path.join(OUT, k + ".stl")), "bodies": v, "quality": "standard"}}
            for k, v in GROUPS.items()]
    tmp = tempfile.mktemp(suffix=".json")
    json.dump(cmds, open(tmp, "w"))
    sc = os.path.join(ROOT, "mechanical", "out", "v010-cup", "OP-100.sc")
    subprocess.run(["solidcraft-cli", "run", tmp, "--in", sc, "--quiet"], check=True)
    os.remove(tmp)
    if len(sys.argv) > 1:
        subprocess.run([sys.executable, os.path.join(ROOT, "electronics", "v010", "cup", "print_model.py"), sys.argv[1],
                        os.path.join(OUT, "cup_board_model.stl")], check=True)


if __name__ == "__main__":
    main()
