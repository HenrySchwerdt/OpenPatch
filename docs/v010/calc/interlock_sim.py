"""Exhaustive fault-injection model of the hardware interlock (behavioural, not SPICE).

TEST PROJECT, NOT A MEDICAL DEVICE.
  MOT_ALLOW = MCU_EN AND LATCH_Q AND (DOCKED OR DIR_REVERSE) ; VMOT (and the boost EN) is on iff MOT_ALLOW.
  LATCH_Q is cleared by: TPL5010 timeout (watchdog not serviced), over-current comparator trip, LATCH_CLR_N from the MCU; set only by an ARM_CLK edge
  while none of the clears is active.
The firmware is treated as ADVERSARIAL (it may drive MCU_EN=1, ARM_CLK, any DIR). Hazard states are physical (sensor/hall/current/timer truth), not software state.
For every single and double hardware fault (stuck-at-0/1 of each node) we check whether the motor can get power in a hazard state.
Run: python3 interlock_sim.py
"""
import itertools

NODES = ["MCU_EN", "LATCH_Q", "DOCK_TERM", "DIRREV_TERM", "WDT_CLR_PATH", "OC_CLR_PATH", "PFET_GATE_DRIVE"]
# fault = (node, 'sa0'|'sa1'); WDT_CLR_PATH sa0 = "timeout can no longer clear the latch"; OC_CLR_PATH sa0 = "trip can no longer clear the latch"

def motor_power(sw_en, sw_arm, sw_dirrev, docked, wdt_expired, oc_trip, faults, latch_prev):
    f = dict(faults)
    def node(name, v):
        s = f.get(name)
        return 1 if s == "sa1" else 0 if s == "sa0" else v
    wdt_clr = node("WDT_CLR_PATH", 1 if wdt_expired else 0)          # sa0 => never clears
    oc_clr = node("OC_CLR_PATH", 1 if oc_trip else 0)
    clear = wdt_clr or oc_clr
    latch = 0 if clear else (1 if (sw_arm or latch_prev) else 0)      # ARM edge sets, state holds until cleared
    latch = node("LATCH_Q", latch)
    en = node("MCU_EN", 1 if sw_en else 0)
    dock = node("DOCK_TERM", 1 if docked else 0)
    dirrev = node("DIRREV_TERM", 1 if sw_dirrev else 0)
    allow = en and latch and (dock or dirrev)
    return node("PFET_GATE_DRIVE", 1 if allow else 0)

def hazards(docked, wdt_expired, oc_trip, sw_dirrev, powered):
    h = []
    if powered and wdt_expired: h.append("H1 runaway (watchdog expired)")
    if powered and oc_trip: h.append("H2 over-current")
    if powered and (not docked) and (not sw_dirrev): h.append("H3 forward motion undocked")
    return h

def scan(faults):
    bad = set()
    for sw_en, sw_arm, sw_dirrev, docked, wdt_expired, oc_trip, latch_prev in itertools.product([0, 1], repeat=7):
        p = motor_power(sw_en, sw_arm, sw_dirrev, docked, wdt_expired, oc_trip, faults, latch_prev)
        for h in hazards(docked, wdt_expired, oc_trip, sw_dirrev, p):
            bad.add(h)
    return bad

def main():
    print("fault-free:", scan({}) or "no hazard reachable (all 128 input combinations)")
    singles = [(n, s) for n in NODES for s in ("sa0", "sa1")]
    print("\nsingle faults (hardware only, firmware adversarial):")
    spf = 0
    for n, s in singles:
        b = scan({n: s})
        flag = "HAZARD: " + ", ".join(sorted(b)) if b else "safe"
        spf += bool(b)
        print(f"  {n:16s} {s}: {flag}")
    print(f"  -> {spf} of {len(singles)} single faults reach a hazard")
    dbl = 0
    tot = 0
    worst = {}
    for (a, b_) in itertools.combinations(singles, 2):
        if a[0] == b_[0]: continue
        tot += 1
        r = scan({a[0]: a[1], b_[0]: b_[1]})
        if r:
            dbl += 1
            for h in r: worst[h] = worst.get(h, 0) + 1
    print(f"\ndouble faults: {dbl} of {tot} reach a hazard; by hazard: {worst}")
    print("\nReading: with firmware adversarial, every hazard needs at least one HARDWARE fault. The single points are: LATCH_Q stuck high, WDT/OC clear path open, PFET stuck on")
    print("(H1/H2), and DOCK_TERM / DIRREV_TERM stuck high (H3). Redundancy does not cover them (one AND chain), so they are covered by diagnostics = proof tests:")
    print("  - latch proof test (boot + every 24 h): pulse LATCH_CLR_N and read the latch/MOT_ALLOW read-back: must fall (catches LATCH_Q stuck high and a dead clear path).")
    print("  - proof test at boot and every 24 h: with VMOT sense ADC, try to power the motor with exactly ONE term de-asserted at a time (MCU_EN=0 / no ARM / undocked+forward) and read VMOT_SENSE and I_MOT: must stay 0.")
    print("  - watchdog proof test: skip one TPL5010 DONE on purpose and read SMA/MOT_ALLOW read-back low within 2.2 s (done in a safe state, motor idle).")
    print("  - OC proof test: pulse the reference (OC_REF test injection resistor) and check LATCH_Q drops.")
    print("  - PFET-stuck-on detection: VMOT_SENSE > 0.3 V while MOT_ALLOW=0 -> alarm + MCU holds STBY low + (v0.2: series fuse/second PFET).")

if __name__ == "__main__":
    main()
