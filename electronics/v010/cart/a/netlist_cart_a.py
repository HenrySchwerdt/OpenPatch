#!/usr/bin/env python3
"""Netlist of the cart pump A v2 main board (plain python3) -> cart/a/netlist_cart_a.json.

TEST PROJECT, bench only, water only. Source: the B netlist recipe (../netlist_cart.py): cup snapshot ../cup_netlist_snapshot.json minus
the dock hall U4A + C80. A deltas (nothing else changes; interlock exactly as ../../INTERLOCK.md and B):
  * gone: TMAG strip pads TL1-4 (the TMAG5273 is on the board), motor wire pads MP1-4 and cell wire pads SP1 / SP2 (no soldering iron,
    spec 1a), the adapter-lock pigtail LK1-3 of B (never in the snapshot);
  * new: U10 TMAG5273A1QDBVR + C41 100 nF on I2C (pull-ups RI1 / RI2 as on B; pin map from the EasyEDA symbol of C3716049:
    1 SCL, 2 GND, 3 GND(TEST), 4 VCC, 5 INT# not used, 6 SDA);
    SW2 Alps SPVS410100 lock detector switch (N/O, closed = adapter locked) from LOCK_SW to GND; RLK 10 k LOCK_SW -> DOCK_N; CLK 100 nF
    DOCK_N -> 3V3 (debounce; a shorted capacitor pulls DOCK_N HIGH = "not locked" = forward blocked); RDK 100 k 3V3 -> DOCK_N kept, so an
    open switch, a broken joint or an open RLK reads "not locked". DOCK_N keeps its name and its meaning (low = adapter locked) for the
    XOR U33, the supervisor U30 (PB6) and the nRF;
    J2 Molex PicoBlade 53261-0471 (1.25 mm, 4 pin, right angle, bottom) for the NFP-608 leads (A+, A-, B+, B- on pins 1-4);
    J3 Kyocera AVX 9175 2-way IDC (bottom) for the bare cell leads (1 = + VCELL, 2 = - GND);
  * SW1: Alps SKSGACE010 top-push tact on the TOP face (B: SKSCLAE010 side tact on the bottom), same net BTN_N / GND.
  * HJ-840 GPIO pads re-assigned for the A placement (pin_assign.json from pinassign_cart_a.py), fixed pads unchanged.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CART = os.path.join(HERE, "..")
sys.path.insert(0, CART)
from netlist_cart import HJ_SIGNALS  # noqa: E402  (same 23 nRF signals as B)

SNAP = os.path.join(CART, "cup_netlist_snapshot.json")
OUT = os.path.join(HERE, "netlist_cart_a.json")
ASSIGN = os.path.join(HERE, "pin_assign.json")
DROP = ("U4A", "C80", "TL1", "TL2", "TL3", "TL4", "MP1", "MP2", "MP3", "MP4", "SP1", "SP2")


def part(ref, value, fp, pins, lcsc, mpn, side, group, note=""):
    return dict(ref=ref, value=value, fp=list(fp), pins=pins, lcsc=lcsc, mpn=mpn, side=side, bom=True, dnp=False, note=note, group=group)


NEW = [
    part("U10", "TMAG5273A1QDBVR", ("Package_TO_SOT_SMD", "SOT-23-6"), {"1": "I2C_SCL", "2": "GND", "3": "GND", "4": "3V3", "5": None, "6": "I2C_SDA"},
         "C3716049", "TMAG5273A1QDBVR", "F", "angle",
         "3D hall, I2C 0x35, on the board top at the rear-far corner, off-axis to the pinion magnet (y 33.435) through the plastic wall; "
         "pin 3 = GND(TEST), pin 5 INT# not used"),
    part("C41", "100nF", ("Capacitor_SMD", "C_0402_1005Metric"), {"1": "3V3", "2": "GND"}, "C1525", "CL05B104KO5NNNC", "F", "angle"),
    part("SW2", "SPVS410100 lock detector switch", ("CARTA", "SW_SPVS410100"), {"1": "GND", "2": "LOCK_SW"}, "C160857", "SPVS410100", "B", "lock",
         "Alps detector switch on the tongue underside, lever toward +x (head); N/O: closed = adapter locked (the d2 pin behind the 2 mm ball "
         "pushes the lever); open / broken = DOCK_N high = not locked = forward blocked (RDK); pads 3 / 4 = frame legs, no net"),
    part("RLK", "10k", ("Resistor_SMD", "R_0402_1005Metric"), {"1": "LOCK_SW", "2": "DOCK_N"}, "C25744", "0402WGF1002TCE", "F", "lock",
         "series resistor switch -> DOCK_N: with RDK 100 k the closed switch gives 0.3 V (AUP VIL 0.9 V); open RLK reads not locked"),
    part("CLK", "100nF", ("Capacitor_SMD", "C_0402_1005Metric"), {"1": "DOCK_N", "2": "3V3"}, "C1525", "CL05B104KO5NNNC", "F", "lock",
         "debounce: switch closes -> DOCK_N falls with 0.9 ms (RLK || RDK), opens -> rises with 10 ms (RDK), about 8 ms to VIH 2.0 V; "
         "to 3V3, not GND: a shorted capacitor reads NOT locked (fail safe)"),
    part("J2", "PicoBlade 1.25 4P right angle (motor)", ("Connector_Molex", "Molex_PicoBlade_53261-0471_1x04-1MP_P1.25mm_Horizontal"),
         {"1": "MOT_A1", "2": "MOT_A2", "3": "MOT_B1", "4": "MOT_B2", "MP": "GND"}, "C696092", "532610471", "B", "mot",
         "NFP-608-26.45-SGM lead connector 'JST 1.25 pitch' (family not stated by NFP: PicoBlade-compatible ASSUMED), A+, A-, B+, B- on 1-4 "
         "(phase sequence of the NFP datasheet; check the lead order on the motor before the first run); bottom face, opening toward -x; the two mounting tabs MP on GND"),
    part("J3", "AVX 9175 2-way IDC (cell)", ("CARTA", "IDC_AVX9175_2P"), {"1": "VCELL", "2": "GND"}, "C7434809", "009175002702996", "B", "batt",
         "bare cell leads (Ampul 301030, red + / black -) pressed into the IDC (26-28 AWG, insulation 0.7-1.0 mm), no soldering; "
         "bottom face near the front edge, wires along x from the front edge; + / - marked on the bottom silkscreen"),
]
SW1 = dict(value="SKSGACE010 top-push tact", fp=["CARTA", "SW_SKSGACE010"], lcsc="C127465", mpn="SKSGACE010", side="F",
           pins={"1": "BTN_N", "3": "BTN_N", "2": "GND", "4": "GND"},
           note="top face at (46.5, 22.05), pressed by the printed plunger; pads 1+3 / 2+4 are the two contacts (Alps)")


def build() -> list:
    parts = [dict(p) for p in json.load(open(SNAP)) if p["ref"] not in DROP]
    for p in parts:
        if p["ref"] == "SW1":
            p.update(SW1)
    parts += [dict(p) for p in NEW]
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
        p["board"] = "CART_A"
    return parts


def main() -> None:
    parts = build()
    nets = {}
    for p in parts:
        for pad, net in p["pins"].items():
            if net:
                nets.setdefault(net, []).append(p["ref"] + "." + pad)
    single = [n for n, v in nets.items() if len(set(x.split(".")[0] for x in v)) < 2 and n not in ("ANT",)]
    json.dump(parts, open(OUT, "w"), indent=1)
    print("cart A netlist:", len(parts), "parts,", len(nets), "nets; single-part nets:", single)


if __name__ == "__main__":
    main()
