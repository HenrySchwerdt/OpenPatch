#!/usr/bin/env python3
"""Netlist of the CART main board (plain python3): cart/netlist_cart.json.

TEST PROJECT, bench only, water only. Same chip set and interlock as the cup board (INTERLOCK.md), new outline (cartgeom.py).

Source: cart/cup_netlist_snapshot.json = netlist_v4_cup.json of the cup board WITH the pre-order review fixes of 2026-11-24
(H5 supervisor SWD pads TPS1-3, H6 wire pads 0.7 x 1.6 / 1.0 x 1.6 + cell reverse-polarity P-FET Q1, M2 nSLEEP = MOT_ALLOW,
M3 100 nF at the gate chain), taken from the main checkout before it was committed. Cart deltas, nothing else changes:
  * the dock hall U4A (DRV5032) and its bypass C80 leave the board: they sit on the adapter-lock pigtail at the front wall
    (mechanical/V010-CART.md). The board gets 3 bare bottom-side pads LK1-LK3 (3V3, GND, DOCK_N) at the west end; RDK (100 k
    3V3 -> DOCK_N) stays on the board, so an open pigtail reads "not locked" (forward blocked, reverse allowed).
    The net keeps the name DOCK_N (firmware, supervisor and INTERLOCK tables use it); on the cart it means "adapter NOT locked".
  * HJ-840 GPIO pads re-assigned for the cart placement (cart/pin_assign.json, pinassign_cart.py), fixed pads unchanged.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "cup_netlist_snapshot.json")
OUT = os.path.join(HERE, "netlist_cart.json")
ASSIGN = os.path.join(HERE, "pin_assign.json")
DROP = ("U4A", "C80")
LOCK_PADS = (("LK1", "3V3"), ("LK2", "GND"), ("LK3", "DOCK_N"))
HJ_SIGNALS = ["APHASE", "BPHASE", "AENBL", "BENBL", "CHG_STAT", "OC_OK", "LATCH_Q", "DOCK_N", "SUP_OK", "LED_R", "LED_G", "LED_B", "SUP_TXD",
              "SUP_RXD", "SUP_BOOT0", "SUP_NRST", "MOT_FWD", "BTN_N", "I2C_SCL", "I2C_SDA", "ARM_CLK", "MCU_EN", "BUZ_A"]


def build() -> list[dict]:
    parts = [dict(p) for p in json.load(open(SNAP)) if p["ref"] not in DROP]
    tl = next(p for p in parts if p["ref"] == "TL1")
    for ref, net in LOCK_PADS:
        lk = dict(tl)
        lk.update(ref=ref, value="LOCK pigtail pad (%s)" % net, pins={"1": net}, group="lock", side="B",
                  note="bare bottom-side pad for the 3-wire adapter-lock pigtail (DRV5032FA + 100 nF on a small strip behind the front wall, "
                       "mechanical/V010-CART.md); open pigtail = DOCK_N high via RDK = not locked")
        parts.append(lk)
    if os.path.exists(ASSIGN):
        assign = json.load(open(ASSIGN))
        assert sorted(assign) == sorted(HJ_SIGNALS), "pin_assign.json must assign every HJ signal once"
        assert len(set(assign.values())) == len(assign), "two signals on one HJ-840 pad"
        u1 = next(p for p in parts if p["ref"] == "U1")
        pins = {pad: net for pad, net in u1["pins"].items() if net not in HJ_SIGNALS}
        for sig, pad in assign.items():
            assert not pins.get(pad), (sig, pad, pins.get(pad))
            pins[pad] = sig
        u1["pins"] = pins
    for p in parts:
        p["board"] = "CART"
    return parts


def main() -> None:
    parts = build()
    nets = {}
    for p in parts:
        for pad, net in p["pins"].items():
            if net:
                nets.setdefault(net, []).append(p["ref"] + "." + pad)
    single = [n for n, v in nets.items() if len(v) < 2 and n not in ("ANT",)]
    json.dump(parts, open(OUT, "w"), indent=1)
    print("cart netlist:", len(parts), "parts,", len(nets), "nets; single-pin nets:", single)


if __name__ == "__main__":
    main()
