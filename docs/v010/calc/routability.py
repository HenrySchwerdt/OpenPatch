"""Routability estimate: failed integrated board (electronics/fab/STATUS.md) vs the v0.1.0 board.

TEST PROJECT, NOT A MEDICAL DEVICE. Heuristic (estimate, not a router): placed-area fill + track-capacity utilisation.
The real gate is: Freerouting (or KiCad router) must reach 100 % with DRC 0 on the generated board BEFORE any order.
Run: python3 routability.py
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import bom
from envelope import option

NETS_V010 = {
    "rails": ["GND", "VBAT", "VBAT_SW", "3V3", "VMOT_SW", "VCHG_IN", "VMOT_BOOST(opt)"],
    "motor": ["MOT_STCK", "MOT_DIR(=DIR_REV)", "MOT_MODE2", "MOT_STBY", "MOT_EN_FAULT", "PH_A+", "PH_A-", "PH_B+", "PH_B-", "I_SENSE_HI"],
    "safety": ["ARM_CLK", "LATCH_CLR_N", "MCU_EN", "MOT_ALLOW", "WDT_DONE", "WDT_WAKE", "NRST", "DOCK_N", "DOCKED_H", "OC_TRIP_N", "OC_REF", "PGATE", "LATCH_Q_N"],
    "sensing": ["I2C_SDA", "I2C_SCL", "TMAG_INT", "I_MOT", "VBAT_SENSE", "VBAT_SENSE_EN", "VMOT_SENSE", "NTC", "NTC_EN"],
    "ui": ["BTN_N", "BUZ_PWM", "BUZ_DRV", "LED_G", "LED_R"],
    "charge": ["CHG_STAT", "CHG_PROG", "CHG_PAD+", "CHG_PAD-"],
    "debug_clk": ["SWDIO", "SWDCLK", "XL1", "XL2"],
    "analog_dividers_internal": ["~20 internal nodes of dividers/RC/pull networks"],
}


def n_nets():
    n = 0
    for k, v in NETS_V010.items():
        n += 20 if k.startswith("analog") else len(v)
    return n


def metrics(name, conn, area_top, area_bot, layers, parts, note="", demand=0.0):
    A_tot = area_top + area_bot
    # average Manhattan length of a connection ~ 0.25 * sqrt(A_side) (local nets dominate) - heuristic
    L_avg = 0.25 * math.sqrt(max(area_top, 1))
    total_len = conn * L_avg
    sig_layers = max(layers - 2, 0) + 0.5 * 2          # inner layers + half of the two outer layers (rest is pads/GND pour)
    pitch = 0.30                                        # mm incl. space, 4/4 mil class at JLC with vias
    cap = (area_top) * sig_layers / pitch              # mm of track
    util = total_len / cap
    print(f"{name:34s} parts {parts:3d} conn {conn:4d} | usable {area_top:5.0f}+{area_bot:4.0f} mm2, conn/mm2 {conn/A_tot:.3f}, placed-area fill {demand/A_tot:4.2f} | track util {util:4.2f} | {note}")
    return util


def main():
    pads = bom.pads()
    nets = n_nets()
    conn = pads - nets
    NP = sum(x.qty for x in bom.BOM if x.jlc != 'mech')
    dem = bom.area('T') + bom.area('B') + bom.area('L')
    print(f"v0.1.0 candidate: pads {pads}, nets ~{nets}, connections ~{conn}, parts lines {len(bom.BOM)}, placed area T {bom.area('T'):.0f} B {bom.area('B'):.0f} L {bom.area('L'):.0f} mm2")
    print("(pads include the 43 E73 castellated pads; about 30 of them are connected)\n")
    # failed design (electronics/fab/STATUS.md): 212 connections, 17.1x29 = 454 mm2 board, usable top ~400, bottom ~100, 4 layers, ~125 parts
    metrics("failed integrated (17.1x29, 4L)", 212, 400, 100, 4, 125, "81 % routed, 63 DRC errors (measured)", demand=494)
    metrics("failed, if bottom were not limited", 212, 454, 454, 4, 125, "(what would help: 2nd full side)", demand=494)
    for Lt in (8, 12, 16, 20):
        o = option(Lt)
        metrics(f"v0.1.0 Lt={Lt:2d} (4L 0.8 mm)", conn, o["top"], o["bot_free"] + o["bot_low"], 4, NP, "", demand=dem)
    o = option(12)
    metrics("v0.1.0 Lt=12 (6L 0.8 mm)", conn, o["top"], o["bot_free"] + o["bot_low"], 6, NP, "6L only if Lt must stay <= 12", demand=dem)
    print("\nNote: the track-utilisation heuristic does NOT separate the failed board (0.27) from the new one (0.19): the failed board died of local congestion\n(pad escape under the ISP1807, keep-outs, 0.5 mm height limit), not of global track capacity. The discriminating numbers are the placed-area fill and the\nvia-in-pad / keep-out situation below.")
    print("\nWhy the new board routes (or what must hold):")
    print("  1. Area: both sides usable (module, buzzer, motor connector, TMAG hang in free air under the board) -> placed-area fill ~0.50 at Lt=22 (0.53 at Lt=20) vs ~1.0 for the failed board.")
    print("  2. No via-in-pad: the E73 has castellated edge pads (43, escape on the outer layer, bench-routed) ; the failed ISP1807 needed VIP on every inner pad.")
    print("  3. No Qi front end (RECT/AC1/AC2/COM/CLAMP/FOD/TS_CTRL/COIL nets, 1206 C0G caps) -> ~20 nets and the most crowded part of the old board disappear.")
    print("  4. No 0.5 mm bottom height limit (battery 3.2 mm leaves 1.05 mm; tall parts live in the tail), no dock-tower no-component zone on the bottom (hall only).")
    print("  5. Antenna keep-out is at the +x end of the tail, no longer fighting the battery/dock for the same corner.")
    print("  6. Same 4-layer 0.8 mm, 0402, 3.5 mil class JLC process as the routed bench controller; no HDI, no 0201.")
    print("  Must hold: gate = 100 % routed + DRC 0 in simulation; interlock + driver + sense loops placed by hand, the rest autorouted.")


if __name__ == "__main__":
    main()
