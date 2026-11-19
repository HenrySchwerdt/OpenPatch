"""OpenPatch v0.1.0 integrated pod: candidate BOM (single source for the envelope/routability/cost scripts).

TEST PROJECT, NOT A MEDICAL DEVICE. Never worn, never used with insulin on a person (see DISCLAIMER.md).

Fields per line (a line = one part number, qty pieces):
  usd   unit price in USD (see status)          area  TOTAL placed area of the line in mm^2 (incl. ~0.4 mm spacing)
  h     tallest body in mm                      side  T  top (lid side, 1.5 mm free height)
                                                      B  bottom, free-air tail zone (4.4 mm free)
                                                      L  bottom, over the battery (<= 0.8 mm)
                                                      D  bottom, over the dock (only the dock hall, 0.4 mm)
  pads  TOTAL pad count of the line             jlc   basic / ext (+3 USD loading fee per unique part) / cons (consigned) / mech
  status BENCH  = LCSC number taken from electronics/bench/*/parts.json (verified there)
         WEB    = price/stock read from a web page on 2026-11-19 (refs in ARCHITECTURE.md)
         EST    = estimate;  VERIFY = LCSC number / dimension must be checked before ordering
"""
from collections import namedtuple

P = namedtuple("P", "grp name mpn lcsc qty usd area h side pads jlc status note")

R4, R6, C8 = 2.3, 4.5, 6.0   # placed area of 0402 / 0603 / 0805 (mm^2)
S23 = 11.8                   # SOT-23-x


def p(*a):
    return P(*a) if len(a) == 13 else P(*a, "")


BOM = [
    # ---- radio / MCU ----------------------------------------------------------------------------------
    p("radio", "nRF52840 module, ceramic antenna (primary: bench-proven E73)", "Ebyte E73-2G4M08S1C", "C356849", 1, 6.00, 234, 2.4, "B", 43, "basic", "BENCH",
      "13x18 mm, castellated 43 pads, height ~2.2-2.4 (VERIFY on the drawing); LCSC-stocked per docs/PARTS-LOCK.md #11 (~5-7 USD) -> no consignment; firmware board bench-e73 and its pin map already exist. CX variant (C2764963) has an IPEX connector instead of the antenna = bench"),
    p("radio", "32.768 kHz crystal 3215 (DNP if the module has one)", "Q13FC13500004", "C32346", 1, 0.10, 9.2, 0.8, "T", 2, "basic", "BENCH", "footprint kept"),
    p("radio", "crystal C0G 15 pF", "0402CG150J500NT", "C1548", 2, 0.01, 2 * R4, 0.5, "T", 4, "basic", "BENCH"),
    p("radio", "decoupling 100n/4u7/1u", "CL05B104KO5NNNC etc.", "C1525/C23733/C52923", 6, 0.01, 6 * R4, 0.5, "T", 12, "basic", "BENCH"),
    # ---- power ----------------------------------------------------------------------------------------
    p("power", "LDO 3V3, Iq 1 uA", "XC6206P332MR-G", "C5446", 1, 0.10, S23, 1.1, "T", 3, "basic", "BENCH"),
    p("power", "LDO caps 1u + 10u", "CL05A105KA5NQNC / CL10A106KP8NNNC", "C52923/C19702", 2, 0.03, R4 + R6, 0.8, "T", 4, "basic", "BENCH"),
    p("power", "Li-Po 3.0-3.2 mm class with PCM, ~40 mAh", "AliExpress, 3 candidates in the order", "-", 1, 2.5, 0, 3.2, "mech", 0, "mech", "EST",
      "dimensions/capacity NOT verified (no AliExpress listing fetched). Cited reference: 401015 = 4.0x10x15 mm, 40 mAh (makerbazar.in)"),
    p("power", "battery contacts: SMD spring finger <= 1.2 mm (x2) or screw-clamp pads", "MPN to be selected", "VERIFY", 2, 0.25, 16, 1.2, "L", 2, "ext", "VERIFY",
      "spec 1a; fallback M1.2 screw clamp of the Ni tabs on ENIG pads"),
    p("power", "Li-Po charger 4.2 V (PROG 50k = 20 mA)", "MCP73832T-2ACI/OT", "VERIFY", 1, 0.45, S23, 1.1, "T", 5, "ext", "VERIFY", "bench README used MCP73832; check the LCSC number"),
    p("power", "charge input: Schottky SOD-123 + TVS + 2 caps", "B5819W / ESD diode", "VERIFY", 1, 0.15, 4 * R4 + 14, 1.0, "T", 6, "basic", "VERIFY"),
    p("power", "charge contact pads (2x ENIG, window in lid)", "PCB feature", "-", 2, 0.0, 20, 0.0, "T", 2, "mech", "EST"),
    p("power", "VMOT boost 5.0 V (EN = MOT_ALLOW), 2.2 uH, 2x22 uF; or 0R bypass", "TPS61023-class", "VERIFY", 1, 0.9, 12 + 9 + 2 * C8, 1.0, "T", 12, "ext", "VERIFY",
      "populate-or-bypass variant on the same board; needed only if the bench shows thrust < 5 N at ~3.1 V (power.py)"),
    p("power", "NTC 10k 0402 + divider", "NCP15XH103F03RC-class", "VERIFY", 1, 0.10, 2 * R4, 0.5, "T", 4, "ext", "VERIFY", "pod temperature (H8)"),
    p("power", "VBAT/VMOT sense dividers 1M/1M + FET", "passives + 2N7002", "C25741/C8545", 2, 0.03, 4 * R4 + S23, 1.1, "T", 12, "basic", "BENCH"),
    # ---- safety / interlock ---------------------------------------------------------------------------
    p("safety", "watchdog", "TPL5010DDCR", "C473912", 1, 0.60, S23, 1.1, "T", 6, "ext", "BENCH"),
    p("safety", "interlock latch D-FF", "SN74AUP1G74DCUR", "C140267", 1, 0.45, 11, 0.9, "T", 8, "ext", "BENCH"),
    p("safety", "high-side P-FET VMOT switch", "AO3401A", "C15127", 1, 0.05, S23, 1.1, "T", 3, "basic", "BENCH"),
    p("safety", "series N-FETs (latch, MCU_EN, dock, dir_rev, inverter)", "2N7002", "C8545", 5, 0.03, 5 * S23, 1.1, "T", 15, "basic", "BENCH"),
    p("safety", "over-current comparator (nano-power, gated supply) + ref", "TLV7011-class", "VERIFY", 1, 0.35, S23 + 3 * R4, 1.1, "T", 9, "ext", "VERIFY",
      "NEW vs bench: the OC trip clears the latch in hardware"),
    p("safety", "current-sense amp for the ADC (diagnostics)", "INA180A1IDBVR", "C122228", 1, 0.30, S23, 1.1, "T", 5, "ext", "BENCH"),
    p("safety", "shunts 0603 + RC", "RS-03L1R00FT / VERIFY", "C174300", 2, 0.05, 2 * R6, 0.55, "T", 4, "basic", "BENCH"),
    p("safety", "interlock pull-ups/downs/RC (about 20 x 0402)", "0402 100k etc.", "C25741 ...", 20, 0.003, 20 * R4, 0.4, "T", 40, "basic", "BENCH"),
    # ---- motor ----------------------------------------------------------------------------------------
    p("motor", "stepper driver", "STSPIN220", "C2150516", 1, 1.00, 14.4, 1.0, "T", 16, "ext", "BENCH"),
    p("motor", "driver passives (VS 10u, 100n, TOFF, sense)", "various", "C19702/C1525", 8, 0.02, 2 * R6 + 6 * R4, 0.8, "T", 16, "basic", "BENCH"),
    p("motor", "VMOT bulk 2x 47 uF 0805 (battery sag)", "VERIFY", "VERIFY", 2, 0.12, 2 * C8, 1.0, "T", 4, "basic", "VERIFY", "battery R_int 1-4 ohm"),
    p("motor", "motor connector PicoBlade 4P (factory lead plugs in)", "A1251WR-S-4P", "C225113", 1, 0.30, 28, 3.3, "B", 6, "ext", "BENCH",
      "deviates from spec 1c (no cable in the pod) - see ARCHITECTURE.md section 6"),
    # ---- sensors --------------------------------------------------------------------------------------
    p("sensor", "3-axis angle sensor on the leadscrew magnet", "TMAG5273A1QDBVR", "C3716049", 1, 1.80, S23, 1.45, "B", 6, "ext", "BENCH", "hangs under the board as on the bench pod"),
    p("sensor", "dock hall (fixed position, frozen interface)", "DRV5032FADMR", "C2152496", 1, 0.35, 3.8, 0.4, "D", 4, "ext", "BENCH",
      "bench note: FA (3.9 mT) switches ~4 mm early; AJ variant C2152498 not in JLC stock"),
    p("sensor", "optional DRV5032 pair (coarse QDEC), DNP", "DRV5032FADMR", "C2152496", 2, 0.35, 2 * 3.8, 0.4, "T", 8, "ext", "BENCH"),
    p("sensor", "sensor decoupling", "CL05B104KO5NNNC", "C1525", 3, 0.01, 3 * R4, 0.5, "T", 6, "basic", "BENCH"),
    # ---- UI -------------------------------------------------------------------------------------------
    p("ui", "button (tact)", "TS-1187A-B-A-B (bench) / 3.0x2.6x0.55 class", "C318884", 1, 0.06, 13, 1.5, "T", 2, "basic", "BENCH",
      "spec button is 3.0x2.6x0.55: verify a part of that class"),
    p("ui", "buzzer magnetic 8.5x8.5x3.0 + FET + flyback", "MLT-8530 / 2N7002 / 1N4148W", "C94599", 1, 0.20, 81 + S23 + 8, 3.0, "B", 6, "basic", "BENCH",
      "fits the tail zone; spec 9x9x2 piezo never fitted the old board"),
    p("ui", "status LEDs 0603 + 1k", "KT-0603R / KT-0603G", "C2286", 2, 0.02, 2 * R6 + 2 * R4, 0.6, "T", 4, "basic", "BENCH", "bring-up only, may be DNP"),
    p("ui", "SWD pads TC2030 + RESET pad (no part)", "PCB feature", "-", 1, 0.0, 17, 0, "T", 6, "mech", "BENCH"),
    p("ui", "test points 1.0 mm (about 14)", "PCB feature", "-", 14, 0.0, 14 * 1.8, 0, "T", 14, "mech", "EST", "probe pads for the test fixture"),
]


def cost(f=lambda x: True):
    return sum(x.usd * x.qty for x in BOM if f(x))


def area(side=None, f=lambda x: True):
    return sum(x.area for x in BOM if f(x) and (side is None or x.side == side))


def pads(f=lambda x: True):
    return sum(x.pads for x in BOM if f(x))


if __name__ == "__main__":
    print(f"lines {len(BOM)}  parts cost {cost():.2f} USD  pads {pads()}  area T {area('T'):.0f} B {area('B'):.0f} L {area('L'):.0f} D {area('D'):.0f}")
