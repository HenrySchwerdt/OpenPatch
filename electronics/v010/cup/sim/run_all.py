#!/usr/bin/env python3
"""Run every cup-board SPICE case and write results/summary.json.  Usage: ./run_all.sh  (needs ngspice, numpy, matplotlib, network for the TI models)."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    subprocess.run([os.path.join(HERE, "fetch_models.sh")], check=True)
    import spice_compat
    for src, dst in (("TPS61023_TRANS.lib", "TPS61023_ng.lib"), ("TPS2553_TRANS.lib", "TPS2553_ng.lib")):
        txt = spice_compat.convert(open(os.path.join(HERE, "models", src), errors="replace").read())
        if "61023" in src:
            txt = spice_compat.patch_tps61023(txt)
        open(os.path.join(HERE, "models", dst), "w").write(txt)
    import simlib as S
    summary = {}
    # case 0: vendor TPS61023 model in ngspice (documented failure)
    deck = open(os.path.join(HERE, "netlists", "vendor_tps61023_ti_circuit.cir")).read()
    w, log = S.run_wave(deck, "c0_vendor", ["vout", "sw", "iin"], mode="ps")
    summary["vendor_tps61023"] = None if w is None else {"vout_max_v": float(w["vout"].max()), "iin_max_a": float(abs(w["iin"]).max()), "expected_vout_v": 5.0,
                                                          "physical": bool(w["vout"].max() < 5.6)}
    for name in ("case1_boost", "case2_switch", "case3_logic", "case4_drv"):
        mod = __import__(name)
        print("running", name, flush=True)
        summary[name] = mod.run()
    json.dump(summary, open(os.path.join(S.RES, "summary.json"), "w"), indent=1, default=str)
    print("done; see results/summary.json and REPORT.md")


if __name__ == "__main__":
    main()
