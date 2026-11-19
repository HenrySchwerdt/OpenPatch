<!-- SPDX-License-Identifier: CERN-OHL-P-2.0 -->
# Measurement sheet: Accu-Chek Insight Flex - cannula head ("dome") and tubing-side connector

TEST PROJECT, bench use only. Roche publishes no dimensions. Everything below is a **TODO-MEASURE placeholder**, scaled from two
photos (a new tubing-side connector, and a cannula head on its patch with the connector slid on).

## How the real parts work (from the photos)

* **Cannula head on the patch:** a round, transparent **dome** (cannula hub with a septum in its side) stuck to the adhesive patch.
* **Tubing-side connector:** a U-shaped clip. Two flexible arms with hooks at the tips, a central cylinder carrying the needle
  **parallel to the arms**, the tube leaves at the bottom. It lies FLAT on the skin and is slid on **sideways**: the needle enters the
  septum horizontally, the arms grip around the dome and the hooks latch behind it. Release = squeeze the connector wings.
* **OpenPatch dock** copies this: the pod is pushed flat along the skin onto the dome. The pod base has a channel open at the +X end;
  at the closed end a 30G needle (press-fit hub) points toward the opening, guarded by a tube that enters the septum recess; two PA12
  snap arms (moulded into the bottom shell) spread over the dome equator and latch in a notch behind it.

## Side view (looking along Y; skin at the bottom, slide direction left = into the pod)

```
                       A  (dome diameter)
              |<----------------------->|
   hook arm   .-------------------------.
   ___________/       dome (top)          \          ---  ^
  |  H (latch |                           |  B  dome height above patch
  |  undercut)|        septum axis ---->--|---  C ----- septum axis height above patch
  |___________\                          /          ---
  ====patch====[base plate  L thick]=====+==========  skin / patch plane (z = 0)

   needle -->|<-- E recess depth, D recess diameter (septum face = recess floor)
   F = needle insertion depth, measured from the septum face to the needle tip
```

## Top view (X = slide direction)

```
          <--- connector / pod enters from the right --- 
                    J (base plate width, Y)
          .---------------------------------.
          |   arm  ._________________.  arm |
          |  ______/   .---------.    \_____|   M  arm inner spacing (relaxed)
   needle |==O====>   (  dome A  ) |hook|    |   G  latch notch position behind the dome centre
   O = hub|            '---------'  N hook h |   K  base plate length (X)
          |   arm  '-----------------' arm  |   O  central cylinder OD, P its length
          '---------------------------------'
```

## Measurement letters (all in `params.json` -> `cannula`)

Use a **new, unused** set (do not touch the cannula or needle: puncture and sterility hazard). Calipers 0.01 mm, three readings, enter the
mean. If you cannot measure a value leave the placeholder.

| letter | `params.json` key | meaning | placeholder |
|---|---|---|---|
| A | `A_dome_d` | dome diameter (widest, parallel to the patch) | 10.0 |
| B | `B_dome_h` | dome height above the patch | 5.0 |
| C | `C_septum_axis_z` | height of the septum axis above the patch | 3.0 |
| D | `D_septum_recess_d` | septum face / recess diameter (where the central cylinder enters) | 3.6 |
| E | `E_septum_recess_depth` | depth of that recess from the dome surface to the septum face | 1.0 |
| F | `F_needle_depth` | needle insertion depth from the septum face to the fluid path (tip depth) | 1.9 |
| G | `G_latch_dx` | latch undercut position: distance of the hook contact behind the dome centre, along X | 3.2 |
| H | `H_latch_depth` | latch undercut depth (radial) | 0.7 |
| I | `I_latch_w` | latch notch width along X | 1.2 |
| J | `J_base_w` | base plate footprint around the dome, width (Y) | 11.0 |
| K | `K_base_l` | base plate footprint length (X) | 11.0 |
| L | `L_base_t` | base plate thickness | 0.6 |
| M | (derived) | connector arm inner spacing: take from the connector, relaxed, between the hook tips (informational, CAD derives `2*hook_in`) | about 6.6 |
| N | `N_hook_h` | hook height (Z extent of the hook tooth) | 3.0 |
| O | `O_cyl_od` | central cylinder outer diameter (guard around the needle) | 3.2 |
| P | `P_cyl_len` | central cylinder length (hub face to its tip) | 2.4 |

Also useful, but not parameters yet: needle gauge / OD (est. 27-30G), free needle length, tubing-side hub diameter (the hub press fit
`dock.hub_d` = 2.0 in the pod is a guess).

### Photo alternative (if you have no calipers)
Put the cannula head and the connector on millimetre graph paper, photograph from the top, from the side (camera at table height,
lens 30 cm away, ruler visible in the picture) and straight along the slide axis. Send the three photos; we read A, B, C, J, K, M, N, O off
them (about +-0.3 mm).

## Fit-test coupon (do this before ordering pods)

`mechanical/out/fab/dock-coupon/dock_coupon.stl` (also `bench/fab/dock-coupon/`): a flat strip with 6 cells = the real dock (end block, guard
tube, floor opening, two snap arms with hooks) at six parameter sets, **no needle**, ID digit engraved in the plate between the cells.
Print one in **MJF PA12** (same as the pod housing) and one in **SLA tough resin** (arm stiffness differs).

| ID | A_dome_d | N_hook_h |
|---|---|---|
| 1 | 9.85 | 2.85 |
| 2 | 10.00 | 2.85 |
| 3 | 10.15 | 2.85 |
| 4 | 9.85 | 3.15 |
| 5 | 10.00 | 3.15 |
| 6 | 10.15 | 3.15 |

(`variants.csv` next to the STL has the same table; step 0.15 mm, `op_coupon.py` constant `STEP`.)

How to use (cannula head must be a spare/unused one, needle not involved):
1. Hold the strip flat on the table, open end (+X, the side with the digits) toward you.
2. Slide the dome (on its patch or loose) into cell n along the plate, as the connector would go on: **the arms must spread, then snap
   behind the dome** with an audible/palpable click, the dome stops against the guard tube.
3. Rate each cell: slides freely (Y/N), snaps (Y/N), rattles (Y/N), pull-off force (light / firm / stuck). Release by pulling the plate back;
   the hook ramp should let go with about 2-4 N.
4. Pick the best cell (snaps, no rattle, releases). Enter its values in `params.json -> cannula.A_dome_d` and `N_hook_h` (the other letters from the
   caliper measurement), then `python3 generate.py --variant bench && python3 check.py --variant bench`.
   If every cell is too tight or too loose, shift the centre value (`A_dome_d`, `N_hook_h` in `params.json`) by the trend and rebuild the coupon with
   `python3 generate.py --coupon`.

## Design numbers of the snap arms (for the drawing review; PA12 MJF, placeholders)

* Arm: 0.8 mm thick x 3.65 mm high, free length 9.5 mm (root bridge to hook centre), hook travel 1.8 mm.
* Strain at the root: `eps = 1.5 * t * y / l^2` = 2.4 % (limit used: 3 % for repeated snaps; PA12 yields at >> 5 %). Arm thickness 0.7 mm gives 2.1 %.
* Force at the hook tip to spread 1.8 mm: about 1.7 N per arm (E = 1.7 GPa). These values scale with the measured dome diameter and
  hook height (`check.py` recomputes and fails above 3 % strain).
* Release: the pod is pulled off; the hook has a pull-off ramp. A squeeze-pad release was NOT implemented: with the 32 mm wide pod the arms are
  12 mm apart and a pivot lever short enough to reach the pods sides would need a hinge strain above 5 %. A tweezers release slot or a slider is
  the next design step after the coupon result.
