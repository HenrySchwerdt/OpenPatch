# Bench pod refill: assisted pressure fill (water only)

TEST PROJECT: bench use with **water only** (beaker, vial or syringe on a balance), **never filled with insulin or any other drug and never connected to a person** (see `DISCLAIMER.md`). The CNC polypropylene reservoir is an optional material preparation for a future manufacturer, never filled with insulin. Printed resin parts (end cap sandwich, SLA reservoir) are **water only**.

Decision 2026-11-19 (spec 3c): **no check valve, no suction draw.** The fill is an Omnipod-style *assisted pressure fill*: the user pushes water through the fill septum with a syringe while the motor **retracts the plunger at a fixed, slow rate**. The self-locking drive (M1.6 x 0.35 leadscrew behind the 26.45:1 gearhead) cannot be back-driven by reservoir pressure, and the reservoir stays at a small positive pressure during the fill, so no air can be pulled in through the outlet needle. Spec 4 (geared stepper, leadscrew, fixed nut) is unchanged.

## Fluid path (minimal module, `op_cap.py`)
reservoir port (d2.0 H7, O-ring 2.0 x 0.5 face seal) -> d0.5 channel in the locating spigot -> one 0.6 mm slot in the silicone gasket -> via d0.6 -> d0.5 needle bore -> hub seat with the UV-glued 30G blunt needle. The fill septum (4 mm disc, 2 mm thick) sits on the **underside** (axis Z) with its chamber (d1.2 x 0.4) on a short spur off the junction; the fill needle enters through a d2.0 hole in the pod floor. No valve, no branching channels.

## Procedure (bench, water)
1. Pod **undocked** (the firmware refuses to run the fill while the dock hall reads DOCKED) and held or lying with the fill hole in the floor reachable and the outlet needle free in the air over a container. Stand the pod on its outlet end (X up) if possible so the air rises to the needle.
2. In the app / test firmware choose "assisted fill" and the volume (e.g. 100 U = 1.0 ml for the OP-100). The motor homes the plunger against the end face by stall (zero dead layer) and then retracts it at the fill rate (start with 0.5 U/s; the rate limit and stall monitor are firmware, see the firmware notes in spec 3c).
3. Push water from the syringe (29-31G needle, bevel up) through the floor hole into the septum **at the same pace** as the plunger retracts. The reservoir stays at a few kPa positive; surplus leaves as drops at the outlet needle tip, which also primes the needle.
4. The motor stops at the requested volume; remove the syringe needle; wipe the drop at the needle tip. Level = step count from the front stop; the TMAG angle verifies the leadscrew angle: 1 turn = 0.35 mm x 74.63 mm2 = 26.1 mm3 = 2.61 U.
5. Weigh: prime-and-weigh check (water on a balance) is mandatory before the level is trusted (see the sim and the review notes: the level is a step count, not a measurement of liquid).

If the syringe pushes faster than the plunger retracts the pressure rises (the plunger is pushed back through the drive only if the drive is back-driven: it is not); if slower, the reservoir sees a small vacuum and the septum/O-ring must hold (40 kPa). Both are bench tests (below).

## Hard end stops (bear on the housing, never on the thread)
* **Rear stop:** `t_rstop0/1`, 0.55 x 2.2 mm contact faces each, x = carriage rear face - 0.02. Stall thrust of the motor about 9.5 N (spec 4, VERIFY).
* **Front stop:** the plunger front face against the reservoir end face (the plunger, not the carriage block, is the first hard stop; dead layer 0.04 mm nominal, homing by stall).

## Fill scale (clear lid)
The lid is clear SLA resin (spec 2a): no window slot, the wall stays closed; the carriage is visible through the lid. The scale is a 0.15 mm engraving on the lid inner face next to the carriage lane (`t_tick*`, `t_tickbase`): ticks every 10 U, long every 50 U, measured from the full position (carriage at the rear stop = 0 U delivered).

## Seals of the module (all dropped in, nothing pressed into blind holes)
O-ring 2.0 x 0.5 (face seal to the reservoir port, 16 % squeeze), gasket 0.5 mm silicone (20 % squeeze on hard lands), septum disc 15 % axial compression between the pocket floor and the lid face, needle UV-glued. The two halves close on hard lands with two M1.2 screws, so the squeezes do not depend on print tolerance. `check.py` runs a fluid-boundary check over every interface. See `SEAL-AND-DEAD-VOLUME.md` and `ASSEMBLY.md` B5.

## Occlusion / safety notes
* Occlusion = pulses without the expected TMAG angle increment + motor current rise.
* The fill needs the same hardware interlock as delivery (MCU enable AND TPL5010 latch), plus NOT DOCKED; reverse motion is rate-limited and stall-monitored.
* Water only, for all parts: nothing in this project is validated for insulin; the pump is never filled with insulin or any other drug.

## Bench tests
* Self-locking: 50 kPa on the reservoir with the motor unpowered, no plunger motion (spec 3c).
* Leak: 30 kPa positive and 40 kPa vacuum at the septum/needle with the plunger homed, 10 min, no drip and no air (septum, O-ring, gasket, needle bond).
* Fill: weigh water in (syringe) vs out (needle drops) vs plunger travel; look for bubbles at the plunger face with the outlet up.
* Prime volume: weigh water to the first drop at the needle (target <= 0.3 U).

## Open items
* Measure the real motor thrust and the seal friction (pull test, `SEAL-AND-DEAD-VOLUME.md`).
* Holding the module against the reservoir face (crush rib / clamp) so the O-ring squeeze is guaranteed.
* Coupling of the carriage to the plunger (slot leak, see README item 4).
