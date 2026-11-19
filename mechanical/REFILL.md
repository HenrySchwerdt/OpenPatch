# Bench pod refill: automatic draw mode (water only)

TEST PROJECT: bench use with **water only**, never on a person, never with insulin (see `DISCLAIMER.md`). Spec §4: geared stepper NFP-608-26.45-SGM, coaxial sleeve coupler,
fixed nut in the carriage, one-way duckbill check valve in the outlet path. No crank, no slider, no half-nut, no ratchet (SMA research is only a note in `parts.md`).

## Procedure (bench, water)
1. Pod **undocked** (the firmware refuses to draw while the dock hall reads DOCKED) and suspended or lying flat on the bench, outlet needle free in the air.
2. In the app/test firmware choose the volume to draw (e.g. 100 U = 1.0 ml for the OP-100).
3. Hold a syringe (or a 30G needle on a tube from the water cup) with its needle through the **fill septum** in the +/-Y wall so the tip is in water; keep it in place.
4. Start the draw: the motor **retracts the carriage by exactly that volume** and the water is drawn in through the septum channel. The duckbill valve in the outlet path blocks air coming
   back through the outlet needle. Step count: 0.00494 U/step, 100 U = 20 243 full steps (about 20 s at 1 000 steps/s, use micro-stepping and a current-limited ramp; the stepper
   has 20 steps/rev before the 26.45:1 gearbox, so 100 U is about 38 leadscrew turns).
5. The motor stops by itself at the requested volume. If the volume exceeds the free space, the carriage reaches the **rear hard stop** (two printed blocks on the housing beside
   the coupler) and the firmware sees the stall (current rise + TMAG angle stops changing): it stops and reports the volume actually drawn from the step count.
6. Remove the needle, prime (forward steps until water appears at the outlet needle, about 0.5 U incl. the valve dead volume), dock on the cannula adapter, run the test.

## Hard end stops (bear on the housing, never on the thread)
* **Rear stop:** `t_rstop0/1`, 0.55 x 2.2 mm contact faces each, x = carriage rear face - 0.02. Stall thrust of the motor about 9.5 N (spec §4, VERIFY) -> 9.5 N / 2.4 mm2 = 4 MPa on PA12 (limit about 40 MPa).
* **Front stop:** the far bearing block in front of the carriage (`t_fblk`, 0.3 mm gap when empty, plunger dead volume 1.0 mm reached first).

## Fill window and scale
A window in the lid over the carriage lane (`t_fillwin`, 2 mm wide) shows the carriage; scale ticks every 10 U, long every 50 U, measured from the full position (carriage at the rear stop = 0 U delivered).
Firmware level = step count from the rear stop (exact); the TMAG angle verifies the leadscrew angle: 1 turn = 0.35 mm x 74.63 mm2 = 26.1 mm3 = 2.61 U (so 0.00494 U = 0.68 deg of leadscrew).

## Duckbill check valve
* Function: forward flow (reservoir -> needle) opens it at the cracking pressure; reverse flow (air or insulin back toward the reservoir) closes it harder. It also stops free flow
  when the reservoir is under pressure from outside and blocks siphoning.
* Part (SEARCH-TERM, all VERIFY, no listing was fetched): miniature silicone duckbill valve, **OD <= 3.0 mm, length about 3.4 mm** (`cannula/coax valve_d / valve_len`), e.g. Minivalve International
  silicone duckbill valves (smallest standard sizes), Vernay miniature duckbill (VA series), or AliExpress "silicone duckbill check valve 3 mm micro". Typical cracking pressure of micro silicone
  duckbills is 1-5 kPa (about 0.15-0.7 psi) forward, sealing pressure rises with back-pressure. Pick the lowest cracking pressure that still holds 20 kPa back-pressure without leaking
  (test with the syringe).
* Pocket: bore d3.05 along the outlet axis in the dock end block (x_r1 + 0.6 .. +4.0) with an open slot on top: drop the valve in with tweezers before the board and lid go on; the printed block
  holds it, the hub shroud continues the flow channel d0.7 to the needle hub.
* Effect on accuracy: the cracking pressure adds a few kPa to the delivery pressure (negligible vs. the occlusion limit); dead volume about 3 mm3 (0.3 U) is primed once.

## Occlusion / safety notes
* Occlusion = pulses without the expected TMAG angle increment + motor current rise; the duckbill cracking pressure is part of the baseline.
* Draw mode needs the same hardware interlock as delivery (MCU enable AND TPL5010 latch), plus NOT DOCKED.
* Water only on the bench: the printed reservoir and the valve are not validated for insulin.

## Open items
* Measure the real motor thrust and the seal friction (pull test); choose the valve (cracking pressure).
* Confirm the shaft D-flat and free shaft length on the real NFP motor (drawing is not to scale) before ordering the coupler.
