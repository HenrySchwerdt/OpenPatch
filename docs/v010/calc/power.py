"""Power budget, battery life, peak current and leadscrew thrust vs supply voltage for the v0.1.0 pod.

TEST PROJECT, NOT A MEDICAL DEVICE. Every current below is a datasheet-class ESTIMATE (marked) to be replaced by bench measurements
(power profiler on the first pod). Run: python3 power.py
"""
import math

# ---- drive (spec 4 / mechanical/params.json) -------------------------------------------------------------------
STEPS_REV, RATIO_GEARHEAD = 20, 26.45
PITCH = 0.35                      # mm, M1.6 x 0.35
AREA = 74.6                       # mm^2 stadium 16x5
GEARS = {"18:18": 1.0, "15:12": 15 / 12}   # z_motor/z_screw -> motor turns per screw turn
R_PHASE, V_RATED = 26.5, 4.8      # NFP-608-26.45-SGM (spec)

def u_per_step(z_m, z_s):
    # screw turns per motor turn = z_m/z_s (15T motor gear drives the 12T screw gear -> screw turns faster, spec 4: 0.00617 U/step)
    return PITCH * (z_m / z_s) / (STEPS_REV * RATIO_GEARHEAD) * AREA / 10

# ---- usage -------------------------------------------------------------------------------------------------------
TDD = 50.0                        # U/day delivered (spec 1b: OP-100 covers up to ~50 U/day for 2 days)
BASAL_PULSES_PER_DAY = 288        # every 5 min
BOLUSES_PER_DAY = 6
PPS = 150                         # step rate during a burst (steps/s); bolus 1.5 U/min = 5 steps/s would be hold-current heavy -> burst + STBY
I_MOT = 0.16                      # A from the battery during a burst (estimate: 3.1 V / 26.5 ohm = 117 mA/phase x microstep factor 1.35)
I_MOT_BOOST = 0.38                # A from the battery if a 5 V boost (85 %) feeds the motor: 181 mA/phase x 1.35 x 4.8 V / 0.85 / 3.6 V (estimate)
T_EVENT_OVERHEAD = 0.030          # s per delivery event at ~6 mA (arm latch, VMOT up, TMAG read, checks) (estimate)
I_EVENT = 0.006

# ---- idle currents (uA) - estimates from datasheet classes -----------------------------------------------------
IDLE = {
    "nRF52840 System ON + RTC (RAM retention)": 3.0,
    "TPL5010 + MCU wake every 2 s for the watchdog (35 nA + 0.15 uA)": 0.2,
    "LDO XC6206 quiescent": 1.0,
    "DRV5032 dock hall (duty-cycled sensor, ~1 Hz)": 0.6,
    "TMAG5273 sleep + comparator/amp (gated supplies)": 0.5,
    "MCP73832 no input / leakage + dividers (FET-switched)": 1.0,
    "battery PCM + self-discharge (~3 %/month of 40 mAh)": 1.7,
}
def ble_avg_uA(conn_interval_s):
    # one connection event ~ 1.5 ms @ 4.6 mA (DC/DC) plus ramp overhead -> average
    return (4.6e3 * 0.0015 + 4.6e3 * 0.0004) / conn_interval_s   # uA

def day(z_m, z_s, i_mot, conn_interval_s, tdd=TDD):
    ups = u_per_step(z_m, z_s)
    steps = tdd / ups
    t_mot = steps / PPS
    events = BASAL_PULSES_PER_DAY + BOLUSES_PER_DAY
    q_mot = i_mot * t_mot / 3.6                  # mAh
    q_evt = I_EVENT * T_EVENT_OVERHEAD * events / 3.6
    q_idle = (sum(IDLE.values()) + ble_avg_uA(conn_interval_s)) * 24 / 1000
    return dict(ups=ups, steps=steps, t_mot=t_mot, q_mot=q_mot, q_evt=q_evt, q_idle=q_idle, total=q_mot + q_evt + q_idle)

def fill_cost(z_m, z_s, i_mot, units=100.0):
    steps = units / u_per_step(z_m, z_s)
    return steps, steps / PPS, i_mot * steps / PPS / 3.6   # steps, s, mAh

def thrust(v_motor, z_m, z_s, eta_gear_pair=0.95):
    # spec 4: 1.6 gf*cm pull-out at rated voltage -> torque scales with I = V/R at low speed
    t_nmm = 1.6 * 9.81e-3 * 10 * RATIO_GEARHEAD * 0.64 * (v_motor / V_RATED)      # N*mm at the gearhead output
    t_screw = t_nmm / (z_m / z_s) * eta_gear_pair                                  # speed-up pair 15:12 lowers torque
    return 2 * math.pi * 0.20 * t_screw / PITCH                                    # N, 20 % screw efficiency

def main():
    print("== drive resolution")
    for k, (m, s) in {"18:18": (18, 18), "15:12": (15, 12)}.items():
        print(f"  gear {k}: {u_per_step(m, s):.5f} U/step  -> 0.05 U = {0.05 / u_per_step(m, s):.1f} steps; {TDD:.0f} U/day = {TDD / u_per_step(m, s):.0f} steps")
    print("\n== thrust at the leadscrew vs motor voltage (>= 5 N required, spec 4; estimate: V/R scaling, 20 % screw efficiency)")
    print("  V_motor   18:18    15:12")
    for v in (4.8, 4.2, 3.7, 3.3, 3.1, 2.8):
        print(f"  {v:4.1f} V  {thrust(v,18,18):5.1f} N  {thrust(v,15,12):5.1f} N")
    print("  -> 15:12 needs >= ~3.3 V at the motor for 5 N and has no margin on a sagging Li-Po; 18:18 keeps >= 5.9 N at 3.1 V and has 25 % finer resolution")

    print("\n== daily charge (mAh/day), TDD 50 U, 288 basal pulses + 6 boluses")
    print("  config                         steps/d  motor s/d  motor  events  idle+BLE  total/day  48 h   72 h (=2 d + 50 %)")
    cfgs = [("18:18 direct 3.1 V", 18, 18, I_MOT), ("15:12 direct", 15, 12, I_MOT), ("15:12 via 5 V boost", 15, 12, I_MOT_BOOST), ("18:18 via 5 V boost", 18, 18, I_MOT_BOOST)]
    for name, m, s, i in cfgs:
        for ci in (1.0, 4.0):
            r = day(m, s, i, ci)
            print(f"  {name:20s} conn {ci:3.0f} s  {r['steps']:7.0f} {r['t_mot']:8.0f}  {r['q_mot']:6.2f} {r['q_evt']:6.2f} {r['q_idle']:8.2f} {r['total']:9.2f} {2*r['total']:6.1f} {3*r['total']:6.1f}")
    print("\n== idle detail (uA): " + "; ".join(f"{k.split('(')[0].strip()} {v}" for k, v in IDLE.items()) + f"; BLE @1 s {ble_avg_uA(1):.1f}, @4 s {ble_avg_uA(4):.1f}")
    tot_idle = sum(IDLE.values()) + ble_avg_uA(1)
    print(f"  average idle incl. BLE (1 s interval) = {tot_idle:.1f} uA (spec 1b assumed ~100 uA average -> margin x{100/tot_idle:.1f}, but estimates!)")

    print("\n== fill (draw mode, on the charger cradle): 100 U")
    for name, m, s, i in cfgs[:3]:
        st, t, q = fill_cost(m, s, i)
        print(f"  {name:20s}: {st:6.0f} steps, {t:5.0f} s, {q:5.2f} mAh")

    print("\n== battery sizing: required charge for 72 h incl. 100 U fill margin; usable = 85 % of nominal x 0.8 end-of-life (spec 1b: 2 d + 50 %)")
    need = 3 * day(18, 18, I_MOT, 1.0)["total"]
    need_b = 3 * day(18, 18, I_MOT_BOOST, 1.0)["total"]
    print(f"  need (18:18 direct) {need:.1f} mAh ; (18:18 boost) {need_b:.1f} mAh")
    for cap in (25, 40, 60):
        use = cap * 0.85 * 0.8
        print(f"  cell {cap} mAh -> usable {use:.1f} mAh -> life {use/day(18,18,I_MOT,1.0)['total']:.1f} d direct / {use/day(18,18,I_MOT_BOOST,1.0)['total']:.1f} d boost ; peak {I_MOT*1000:.0f}-{I_MOT_BOOST*1000:.0f} mA = {I_MOT/ (cap/1000):.1f}-{I_MOT_BOOST/(cap/1000):.1f} C")

    print("\n== peak current / sag (burst):")
    for rint in (1.0, 2.0, 4.0):
        for i, name in ((I_MOT, "direct"), (I_MOT_BOOST, "boost")):
            v = 3.7 - i * (rint + 0.06 + 0.2)   # R_int + AO3401A + shunt
            print(f"  R_int {rint:.0f} ohm, {name:6s} {i*1000:.0f} mA: battery terminal {3.7 - i*rint:.2f} V, VMOT_SW {v:.2f} V" + ("  <- below 3.0 V: brown-out risk for the 3V3 LDO input (module min 1.7 V OK, but motor torque low)" if v < 3.0 else ""))
    print("  mitigation: 2x47 uF bulk on VMOT (sag ride-through ~ 94 uF * 0.5 V / 0.19 A = %.2f ms), UVLO policy: no motor start below 3.4 V open-circuit, boost keeps the motor at 5 V." % (94e-6 * 0.5 / I_MOT * 1e3))
    print("  LDO XC6206 max 200 mA: radio TX 0 dBm 4.8 mA + CPU -> fine; the motor path does not go through the LDO.")

if __name__ == "__main__":
    main()
