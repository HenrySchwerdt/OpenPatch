# Measurement sheet: Accu-Chek Insight Flex - cannula head (connector plate)

Goal: the receiving pocket on the underside of the pod only fits if we know the real geometry of the cannula head.
Roche does not publish it. Please measure with **calipers (0.01 mm)**.

**Important:** do **not** measure the head while it is on the body. Use a *new, unused* set (tubing pulled off,
connector plate exposed). Do not touch the needle/cannula (puncture hazard, sterility). Measure each dimension 3 times
and enter the mean. If a dimension cannot be measured, leave it empty: the placeholder stays active.

## Sketch (top view from the tubing side, X = long side of the plate)

```
                 A  (plate length, X)
      |<------------------------------------->|
      |      K (corner radius)                |
   ---+---------------------------------------+---   ^
   |  ,-------------------------------------,  |     |
   |  |                                     |  |     |
 D |->|        ( H  septum dia )            |<-|     B  (plate width, Y)
   |  |            +  <- septum centre       |  |     |
   |  |          I,J = centre offset         |  |     |
   |  '-------------------------------------'  |     |
   ---+---------------------------------------+---   v
      |<-E->|  snap wings (left/right)
```

Side view (looking along Y):

```
        ____________________           ---
       |  connector plate   |           ^
   ====|=== wings ======    |==== G     | C  (plate thickness)
       |        (F high)    |           v
       |____________________|          ---
            |  cannula |   <- L  (plate underside to cannula exit / socket)
    M = needle penetration depth into the septum (from the plate top)
```

## Measurements

| Letter | What to measure | Caliper method | Placeholder (mm) | Entry in `params.json` (`cannula.`) | Your value |
|---|---|---|---|---|---|
| **A** | plate length (long edge) | outside size | 14.0 | `A_plate_length` | |
| **B** | plate width (short edge) | outside size | 10.0 | `B_plate_width` | |
| **C** | plate thickness without wings | outside size, side view | 3.0 | `C_plate_thickness` | |
| **D** | depth of the snap groove / height of the wing nose (how far the nose stands out from the plate edge) | depth gauge, or difference of outside sizes with/without wing | 1.0 | `D_wing_groove_depth` | |
| **E** | length of the wing nose along the edge | inside jaws | 3.0 | `E_wing_len` | |
| **F** | height (thickness) of the wing nose | side view | 1.0 | `F_wing_height` | |
| **G** | distance plate underside to wing-nose underside | depth gauge | 1.0 | `G_wing_z` | |
| **H** | septum diameter (visible silicone area) | inside jaws | 4.0 | `H_septum_dia` *(not yet wired into geometry, documentation only)* | |
| **I** | offset septum centre to plate centre in A direction (+ = toward wing side 1) | edge-to-septum-rim distance, then convert | 0.0 | `I_septum_off_x` | |
| **J** | offset septum centre to plate centre in B direction | as I | 0.0 | `J_septum_off_y` | |
| **K** | corner radius of the plate (radius gauge or photo) | radius gauge | 0.0 | `K_corner_r` *(not yet wired)* | |
| **L** | distance plate underside to the cannula exit from the socket (height that stands out below the plate) | depth gauge | 0.0 | `L_head_standoff` *(not yet wired; will decide whether the floor needs a recess)* | |
| **M** | how deep the 30G needle may go into the septum (septum thickness from the plate top) | measure septum thickness, subtract 0.1 mm reserve | 1.9 | `M_needle_depth` | |
| **N** | wanted clearance pocket-to-plate (per side) | - (design decision: MJF 0.2 / SLA 0.15) | 0.2 | `N_clearance` | |

Additionally please note (for the later refinement of the pocket and the **snap latch**):

1. Does the head latch with a **click**, and from which direction is it pushed on (from above onto the plate / sideways)?
2. Photos of the plate from the top, side and bottom (with a scale / coin next to it).
3. Is the septum **flush** with the plate surface or recessed (depth in mm)?
4. Material/hardness of the wings (flexible? how much travel until release? squeezed by about ___ mm).
5. **Latch (TODO-MEASURE):** at which height above the plate underside do the wings sit (G), and how far must a
   wing be pushed in to pass the pocket tooth (dimension D minus the tooth protrusion)? The CAD latch is a
   wedge tooth in the pocket wall plus two relief slits (cantilever tab); beam stiffness and tooth height are guesses.

## After measuring

1. Enter the values into `mechanical/params.json` under `"cannula"`.
2. Run `python3 generate.py && python3 check.py` (see README.md).
3. Test-print **only the receiving pocket** (cut-out, about 20 x 20 mm) with 3 clearance variants
   (`N_clearance` = 0.10 / 0.15 / 0.20) and check the snap feel on the real head - before printing the whole pod.

Note: the model assumes **snap wings on the two X sides** of the plate (grooves in the pocket walls at +-A/2).
If the wings are actually on the Y sides or elsewhere, please send the photo back - then the pocket in
`op_shell.py` (`build_bottom`) will be rebuilt.
