#!/usr/bin/env python3
"""Write the HJ-840 signal -> nRF pin assignment (cup/pin_assign.json + design/netlist_v4.py HJ_PIN) into
firmware-rs/openpatch-bench/src/board/cup_v4.rs (the `take()` pin moves and the doc table). Run after pinassign.py."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "..")
RS = os.path.join(ROOT, "firmware-rs", "openpatch-bench", "src", "board", "cup_v4.rs")
FIELD = {"aphase": "APHASE", "bphase": "BPHASE", "aenbl": "AENBL", "benbl": "BENBL", "chg_stat": "CHG_STAT", "oc_ok": "OC_OK", "latch_q": "LATCH_Q",
         "dock_n": "DOCK_N", "sup_ok": "SUP_OK", "led_r": "LED_R", "led_g": "LED_G", "led_b": "LED_B", "sup_rx": "SUP_TXD", "sup_tx": "SUP_RXD",
         "sup_boot0": "SUP_BOOT0", "sup_nrst": "SUP_NRST", "mot_fwd": "MOT_FWD", "button": "BTN_N", "i2c_scl": "I2C_SCL", "i2c_sda": "I2C_SDA",
         "arm_clk": "ARM_CLK", "mcu_en": "MCU_EN", "buz_a": "BUZ_A"}


def main():
    s = open(RS).read()
    pa = json.load(open(os.path.join(HERE, "pin_assign.json")))
    src = open(os.path.join(HERE, "..", "design", "netlist_v4.py")).read()
    hj = eval(re.search(r"HJ_PIN = (\{.*?\})\n", src, re.S).group(1))
    used = set()
    for f, n in FIELD.items():
        q = hj[pa[n]]
        assert q not in used, q
        used.add(q)
        emb = "P%s_%s" % (q[1], q[3:].zfill(2))
        s, c = re.subn(r"(\n        %s: p\.)P\d_\d\d(\.into\(\),)" % f, r"\g<1>%s\2" % emb, s)
        assert c == 1, f
        s, c = re.subn(r"\n//! \| [A-H]\d +\| P\d\.\d\d \| `%s` *\|" % n, lambda m: "\n//! | %-3s | %s | `%s`%s|" % (pa[n], q, n, " " * max(1, 10 - len(n) - 1)), s)
        assert c == 1, (n, c)
    open(RS, "w").write(s)
    print("cup_v4.rs pin map updated")


if __name__ == "__main__":
    main()
