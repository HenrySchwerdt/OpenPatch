#!/usr/bin/env python3
"""Generate FMEA.md (component -> failure -> effect -> readback -> POST step -> diagnostic code) and validate every code against spec/diag-codes.csv.

Codes marked NEW are catalogue requests (rule 2.8 of docs/06-diagnostics.md): proposed identifiers in the reserved components 0F (HW-A) and 0D (over-current latch);
spec/diag-codes.csv is not edited here (owner: diagnostics work package)."""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CAT = {r["code"]: r for r in csv.DictReader(open(os.path.join(ROOT, "spec", "diag-codes.csv")))}

# FM id, ref, failure, effect on VMOT/motion, single-fault safe, readback, POST step, code(s), FRU
Y, N = "yes", "NO"
ROWS = [
    ("FM-Q4-1", "Q4", "drain-source short", "first series switch bypassed; **Q15 still cuts**", Y, "RB7 VMOT_SENSE, PGATE_MON", "S06, A01 (cut with Q15 only)", "1-06-001", "CTRL"),
    ("FM-Q15-1", "Q15", "drain-source short", "second series switch bypassed; Q4 still cuts", Y, "RB7, PGATE_MON", "S06, A01", "1-06-001", "CTRL"),
    ("FM-Q4-2", "Q4 / Q15", "open", "no motor supply", Y + " (fail-safe)", "RB7, PGATE_MON", "A01", "1-06-002", "CTRL"),
    ("FM-Q4/Q15-3", "Q4 and Q15", "both shorted (double fault)", "VMOT cannot be cut; HW-A still limits steps", "n/a (2 faults)", "RB7", "S06", "1-06-001", "CTRL"),
    ("FM-R9-1", "R9 or R10", "open", "gate still pulled up by the other resistor", Y, "none (masked); PGATE_MON / turn-off time", "A01 timing", "1-06-001 (only if both open)", "CTRL"),
    ("FM-R11-1", "R11", "open", "gate never pulled low: no motor supply", Y + " (fail-safe)", "PGATE_MON low?", "A01", "1-06-002", "CTRL"),
    ("FM-Q5-1", "Q5", "D-S short", "latch leg lost; MCU_EN, OC, dock legs remain", Y, "RB6, VMOT after LATCH_CLR_N", "A01", "1-07-002", "CTRL"),
    ("FM-Q8-1", "Q8", "D-S short", "MCU_EN leg lost", Y, "RB7 after MCU_EN low", "A01", "1-07-001", "CTRL"),
    ("FM-Q13-1", "Q13", "D-S short", "OC leg lost: the supply stays on after a trip", Y + " (chopper limit remains)", "OC_OK vs VMOT", "A01, OC_TEST", "1-0D-001 NEW", "CTRL"),
    ("FM-Q6-1", "Q6, Q7, Q7B", "Q6 shorted or Q7/Q7B stuck off", "DOCKED leg lost: undocked forward not blocked", N + " if firmware also commands it", "RB4 DOCKED_H, DOCK_TEST", "A02", "1-07-003", "CTRL"),
    ("FM-Q10-1", "Q10, Q11, R13", "Q10 shorted / DIR polarity wrong", "undocked forward not blocked", N + " if firmware also commands it", "RB5 (MOT_DIR readback), VMOT", "A02", "1-07-004, 4-40-003", "CTRL"),
    ("FM-Q5-2", "Q5, Q8, Q13, Q6 and Q10", "open", "motor never runs", Y + " (fail-safe)", "PGATE_MON", "A01", "1-07-005, 1-07-006", "CTRL"),
    ("FM-U4A-1", "U4A or U4B", "one hall stuck asserted (low)", "other hall still reads not docked: **blocked (2oo2)**", Y + " (new in v0.1.0)", "DOCK_N vs DOCKED_H mismatch", "S08, A10", "2-21-001", "DOCK (magnet/hall)"),
    ("FM-U4A-2", "U4A or U4B", "stuck not asserted / no supply", "forward blocked, pod never docks", Y + " (fail-safe)", "DOCK_N, DOCKED_H", "A10", "2-21-002, 1-07-006", "DOCK"),
    ("FM-U4A-3", "U4A and U4B", "both stuck asserted (double fault)", "undocked forward not blocked by the dock leg; DIR leg, latch, MCU_EN remain", "n/a (2 faults)", "TMAG field, DOCK_TEST", "A02", "1-07-003", "DOCK"),
    ("FM-R19-1", "R19/R20", "open", "DOCK_N floats (high-Z, pick-up)", "yes (floating high = not docked; noise can read docked, other hall/legs remain)", "DOCK_N chatter", "S08", "2-21-003", "CTRL"),
    ("FM-U6-1", "U6", "Q stuck 1", "latch and watchdog cannot cut", Y + " (MCU_EN, OC, dock legs)", "RB6 after LATCH_CLR_N", "S05, A01", "1-05-003, 1-05-001", "CTRL"),
    ("FM-U6-2", "U6", "Q stuck 0", "no motion", Y + " (fail-safe)", "RB6", "A01", "1-05-002", "CTRL"),
    ("FM-U5-1", "U5", "no WAKE", "watchdog dead", Y + " (other legs); protection reduced", "RB11", "continuous", "1-04-001", "CTRL"),
    ("FM-U5-2", "U5, D2", "RSTn not reaching MCU / latch", "watchdog ineffective", Y + " (protection reduced)", "RB11", "A08", "1-04-002", "CTRL"),
    ("FM-U10-1", "U10, C16, R30, D1", "DONE qualifier stuck", "TPL5010 resets every 2 s, or never fires on silence", Y, "WAKE counting", "A08", "1-04-001", "CTRL"),
    ("FM-R18-1", "R18", "MCU_EN pull-down open", "MCU_EN floats after reset (other legs hold)", "partly", "RB9 own-pin readback", "S05", "1-07-007", "CTRL"),
    ("FM-U9-1", "U9, R44", "INA180 / shunt open or offset", "I_SENSE dead or biased; OC cut blind", Y + " (chopper limit, encoder)", "RB8", "S06, A03, OC_TEST", "1-08-001, 1-08-002, 1-08-003", "CTRL"),
    ("FM-U11-1", "U11, R49-R51", "comparator stuck low (no trip)", "OC protection lost", Y + " (chopper 160 mA remains)", "OC_OK after OC_TEST", "A09 (OC_TEST)", "1-0D-001 NEW", "CTRL"),
    ("FM-U11-2", "U11", "comparator stuck high", "trips at once, VMOT never on", Y + " (fail-safe)", "OC_OK low after MCU_EN cycle", "A09", "1-0D-002 NEW", "CTRL"),
    ("FM-U12-1", "U12", "Q_N stuck 1 / cannot clear", "OC leg lost / never on", Y, "OC_OK", "A09", "1-0D-001 NEW", "CTRL"),
    ("FM-Q14-1", "Q14", "stuck on", "reference low: trips at once", Y, "OC_OK", "A09", "1-0D-002 NEW", "CTRL"),
    ("FM-U7-1", "U7", "bridge failure", "no motion or fault; short trips OC", Y, "RB10 EN/FAULT, OC_OK", "S05", "1-03-001, 1-03-002", "CTRL"),
    ("FM-R34-1", "R34/R35/R37/R38", "wrong current limit", "current up to 2x", Y + " (OC 0.39 A)", "RB8", "A03", "6-62-001", "CTRL"),
    ("FM-R41-1", "R41/R42", "MODE1/MODE2 pull-down open", "microstep mode undefined (torque/step size wrong)", "no hazard class change, dose ratio changes", "A05 step ratio", "A05", "4-41-002", "CTRL"),
    ("FM-U13-1", "U13, U14, C33, R59/R60", "window FF/Schmitt stuck open", "budget gate passes steps forever", "**NO (HW-A lost, other legs remain)**", "WIN, HWA_FULL, TMAG vs TIMER1", "A12 (new)", "1-0F-002 NEW", "CTRL"),
    ("FM-U13-2", "U13, U14", "window never opens", "no forward steps pass: no delivery", Y + " (fail-safe)", "WIN low after ARM", "A12", "1-0F-003 NEW", "CTRL"),
    ("FM-U15-1", "U15, Q18", "counter stuck 0 (never FULL)", "budget not enforced within the window (window still limits to 0.6 s = about 120 pulses at 200 Hz)", "partly", "HWA_FULL after 40 pulses", "A12", "1-0F-002 NEW", "CTRL"),
    ("FM-U15-2", "U15", "FULL stuck 1", "no forward pulses pass", Y + " (fail-safe)", "HWA_FULL high with window closed", "S05", "1-0F-004 NEW", "CTRL"),
    ("FM-U16-1", "U16-U19", "AND/OR output stuck high (U18)", "STCK passes ungated", "**NO (HW-A lost)**", "TMAG vs steps in A12", "A12", "1-0F-002 NEW", "CTRL"),
    ("FM-U17-1", "U17 / U19", "stuck low", "no forward pulses / reverse blocked", Y + " (fail-safe)", "TMAG motion", "A04, A12", "1-0F-003 NEW", "CTRL"),
    ("FM-R43-1", "R43", "STCK_MCU pull-down open", "STCK floats at reset (gate AND still needs window)", Y, "none", "S05", "1-07-007", "CTRL"),
    ("FM-U10T-1", "U10T TMAG5273", "no ACK / stuck / wrong ID", "delivery cannot be verified: firmware refuses", Y, "I2C", "S08", "2-20-001, 2-20-002, 2-20-003", "BOARD (TMAG)"),
    ("FM-J1-1", "J1 (PicoBlade)", "contact open / intermittent", "motor winding open", Y, "RB8", "S06", "3-31-001, 3-31-004", "MOTOR / CONNECTOR"),
    ("FM-U2-1", "U2 LDO", "no output / high", "logic off, VMOT off", Y, "RB13 VDD", "S04", "1-02-001, 1-02-002", "CTRL"),
    ("FM-U3-1", "U3, D3, D4, R2", "charger / pad failure", "no charge or over-charge", "H8 only (water bench)", "CHG_STAT, VBAT", "charge test", "A-A1-001", "CHARGER"),
    ("FM-BAT-1", "cell + PCM", "over/under voltage, high R_int", "brown-out or weak thrust", Y, "VBAT_SENSE, VMOT droop", "S04", "A-A0-001, A-A0-002, A-A0-003, 1-06-003, 1-01-002", "BATTERY"),
    ("FM-Q1-1", "Q1, Q2, R5-R8, RT1", "sense switch stuck on/off", "wrong VBAT/NTC reading or 20 uA leakage", Y, "VBAT_SENSE vs DMM", "S04", "1-09-001", "CTRL"),
    ("FM-BZ1-1", "BZ1, Q19, R70", "open / short", "no alarm sound (software alarms remain)", Y, "A11 user confirm", "A11", "1-0C-002", "CTRL"),
]


def main():
    out = ["> TEST ONLY - NOT FOR HUMAN USE. Generated by `tools/gen_fmea.py`; every code is checked against `spec/diag-codes.csv`.\n",
           "# v0.1.0 pod: FMEA and diagnostics mapping\n",
           "Format of `docs/06-diagnostics.md` 3.6. Reference designators are those of `netlist.json` (`CTRL.<ref>` in the catalogue). Safe = a single failure cannot cause forward delivery the firmware did not authorise.",
           "Codes with **NEW** do not exist in the catalogue yet: they are requests (rule 2.8) for the reserved components `0F` (HW-A step budget) and `0D` (over-current latch; `0D` is unallocated in layer 1); nothing was added to `spec/diag-codes.csv` by this work package.\n",
           "| FM id | Ref | Failure mode | Effect on VMOT / motion | Single-fault safe? | Readback | Detection step | Diagnostic code | FRU |", "|---|---|---|---|---|---|---|---|---|"]
    bad = []
    for r in ROWS:
        codes = r[7]
        for c in codes.replace(",", " ").split():
            if c.count("-") == 2 and c[0] in "0123456789AB" and len(c) == 8 and "NEW" not in codes.split(c)[1][:5]:
                if c not in CAT:
                    bad.append((r[0], c))
        out.append("| " + " | ".join(r) + " |")
    out.append("\n## Catalogue names of the existing codes used\n")
    used = sorted({c for r in ROWS for c in r[7].replace(",", " ").split() if c in CAT})
    out.append("| Code | Name | Severity | FRU |\n|---|---|---|---|")
    for c in used:
        out.append("| `%s` | %s | %s | %s |" % (c, CAT[c]["name"], CAT[c]["sev"], CAT[c]["fru"]))
    out.append("\n## Requested new codes (not yet in the catalogue)\n")
    out.append("| Code | Name | Detection | Sev | FRU | Hazard |\n|---|---|---|---|---|---|")
    for row in [("1-0D-001", "OC_LATCH_STUCK_OK", "OC_TEST high with I > 5 mA: OC_OK stays 1 / VMOT stays up (POST A09)", "L", "CTRL", "H1 H11"),
                ("1-0D-002", "OC_LATCH_STUCK_TRIPPED", "OC_OK low after a MCU_EN low-high cycle with no load", "F", "CTRL", "H2"),
                ("1-0F-002", "HWA_BUDGET_NOT_ENFORCED", "A12: 40 forward pulses commanded, TMAG moved more than 32 steps +5 %, or HWA_FULL never set", "L", "CTRL", "H1 H11"),
                ("1-0F-003", "HWA_WINDOW_NEVER_OPENS", "A12: WIN low after ARM_CLK, or no motion in the window", "F", "CTRL", "H2"),
                ("1-0F-004", "HWA_FULL_STUCK", "HWA_FULL high while WIN low at idle", "F", "CTRL", "H2")]:
        out.append("| `%s` | %s | %s | %s | %s | %s |" % row)
    out.append("\nProof-test additions (POST-A, docked, water only): **A12** HW-A budget (arm, 40 forward pulses, expect `HWA_FULL`=1 and 32 steps of TMAG motion; no arm, 8 pulses, expect 0), **A09** over-current latch with `OC_TEST`.")
    open(os.path.join(HERE, "..", "FMEA.md"), "w").write("\n".join(out) + "\n")
    print("rows", len(ROWS), "missing existing codes:", bad)


if __name__ == "__main__":
    main()
