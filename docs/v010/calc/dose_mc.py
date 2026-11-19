"""Monte-Carlo dose accuracy of the drive chain (water/insulin into a container on a balance; NEVER on a person).

TEST PROJECT, NOT A MEDICAL DEVICE. All tolerances below are ASSUMPTIONS (marked) to be replaced by measured values (caliper on the CNC bore,
thread gauge on the rod, first gravimetric runs). Target (docs/02-safety.md bench step 1): within +-5 % from 1 U.
Run: python3 dose_mc.py [N]
"""
import math, random, statistics, sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
random.seed(7)

PITCH, STEPS, GEARHEAD = 0.35, 20, 26.45
ZM, ZS = 18, 18                              # recommended pair (power.py); 15:12 changes only the nominal U/step

def stadium_area(w, h):
    r = h / 2
    return h * (w - h) + math.pi * r * r

def nominal_ups():
    return PITCH * (ZM / ZS) / (STEPS * GEARHEAD) * stadium_area(16.0, 5.0) / 10

def draw_pod():
    w = random.gauss(16.0, 0.03)             # mm, CNC PP bore width: sigma 0.03 (3 sigma = 0.09)       ASSUMPTION
    h = random.gauss(5.0, 0.02)              # mm, bore height: sigma 0.02                                 ASSUMPTION
    pitch = random.gauss(PITCH, 0.35 * 0.002)  # M1.6x0.35 rolled/cut rod pitch error sigma 0.2 %           ASSUMPTION
    expansion = random.gauss(0.0, 0.003)     # thermal/creep of the PP bore 25 -> 37 C, sigma 0.3 %        ASSUMPTION
    backlash = abs(random.gauss(0.03, 0.02)) # mm axial play carriage/nut, taken up once after a reversal ASSUMPTION
    thrust_avail = random.gauss(5.9, 0.6)    # N at 3.1 V motor voltage (power.py, 18:18)                  ESTIMATE
    friction = random.gauss(2.0, 0.9)        # N plunger seal drag, depends on seal hardness / lubrication  ASSUMPTION
    return w, h, pitch, expansion, backlash, thrust_avail, friction

def delivered(units, pod, after_reversal=False):
    w, h, pitch, exp, backlash, thr, fr = pod
    steps = round(units / nominal_ups())                                  # firmware quantisation (exact rational in firmware)
    stall = 0.0
    if fr > thr * 0.85:                                                   # drag above 85 % of pull-out thrust -> random step loss
        stall = min(1.0, (fr - thr * 0.85) / (thr * 0.5))
    lost = steps * stall * random.random() * 0.3
    stroke = (steps - lost) * PITCH / (STEPS * GEARHEAD) * (ZM / ZS) * (pitch / PITCH)
    if after_reversal:
        stroke = max(stroke - backlash, 0.0)
    return stroke * stadium_area(w, h) * (1 + exp) / 10

def run(units, after_reversal=False):
    errs, cal_errs, enc_flag = [], [], 0
    for _ in range(N):
        pod = draw_pod()
        # per-pod gravimetric calibration with a 5 U run on a 0.1 mg balance (residual sigma 0.3 %)
        k = delivered(5.0, pod) / 5.0 * (1 + random.gauss(0, 0.003))
        d = delivered(units, pod, after_reversal)
        errs.append((d / units - 1) * 100)
        cal_errs.append((d / (units * k) - 1) * 100 if k else 0)
    def ptile(x, p): return sorted(x)[int(p * len(x))]
    return statistics.mean(errs), statistics.pstdev(errs), ptile([abs(e) for e in errs], 0.95), statistics.mean(cal_errs), statistics.pstdev(cal_errs), ptile([abs(e) for e in cal_errs], 0.95)

def main():
    print(f"nominal {nominal_ups():.5f} U/step at {ZM}:{ZS}; N={N} pods per row")
    print("dose     steps  | uncalibrated: mean  sd   p95|err|  | after 5 U gravimetric calibration: mean  sd   p95|err|   (percent)")
    for u in (0.05, 0.1, 0.5, 1.0, 5.0):
        m, s, p95, mc, sc, pc = run(u)
        print(f"{u:5.2f} U {round(u/nominal_ups()):6d} |        {m:6.2f} {s:5.2f} {p95:6.2f}        |        {mc:6.2f} {sc:5.2f} {pc:6.2f}")
    print("\nafter a direction reversal (first dose after a refill draw, backlash 0.03 mm not yet taken up):")
    for u in (0.05, 0.5, 1.0):
        m, s, p95, mc, sc, pc = run(u, True)
        print(f"{u:5.2f} U  uncal mean {m:6.2f} sd {s:5.2f} p95 {p95:6.2f} | cal mean {mc:6.2f} sd {sc:5.2f} p95 {pc:6.2f}")
    print("\nReading: the quantisation (10 steps = 0.0494 U for a 0.05 U command) and the backlash after reversal dominate below 0.5 U -> firmware must (a) take up the backlash with a")
    print("priming run of >= 0.2 mm after every refill, (b) keep exact rational U/step with carry, (c) report encoder-verified steps. Step-loss tail comes from seal drag vs thrust (seal-hardness variants in the order).")

if __name__ == "__main__":
    main()
