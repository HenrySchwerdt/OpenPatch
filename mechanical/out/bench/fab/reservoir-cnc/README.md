# CNC polypropylene reservoir (frozen interface) - PCBWay CNC package

BENCH TEST PART: water only (beaker or vial on a balance); not a medical device; never connected to a person.
Per size: `OP-xx_reservoir_cnc.step` (master), `OP-xx_reservoir_cnc_drawing.pdf` (+ `.svg`, `.png`). Order **once per size, qty 2** (spare).

## What the part is (and is not)
One piece of PP: stadium bore 16.00 x 5.00 (+0.05/-0.0), blind from the open dry end, closed end wall 2.5 mm with ONE port d2.0 H7 (+0.012/0)
(centre of the end face), carriage-arm slot through the +Y wall. **No** septum, valve, needle or dock features: these are on the separate end cap (`end_cap`, SLA now, PP later), which presses onto the port
with a d1.98 spigot. Outer 17.6 x 6.6, wall 0.8.

## Frozen numbers (`params.json -> reservoir_frozen`, do not change after the order)
bore 16.00 x 5.00 (R2.50 ends), tolerance +0.05/-0; outer 17.6 x 6.6 +-0.1 (R3.3 ends); wall 0.8; closed end wall 2.5; port d2.0 H7 at the centre of the closed end face; Ra bore <= 0.8 um;
length per size below (+-0.1); arm slot height 1.60 on the bore axis; datums A open end face, B bottom flat, C bore centre plane.

| size | volume | overall length | bore depth | depth / d5 | min. flute (cut) length [mm] |
|---|---|---|---|---|---|
| OP-70 | 70 U (9.4 mm stroke) | 17.70 | 15.20 | 3.0 x D | 16.2 |
| OP-100 | 100 U (13.4 mm stroke) | 21.70 | 19.20 | 3.8 x D | 20.2 |
| OP-200 | 200 U (26.8 mm stroke) | 35.10 | 32.60 | 6.5 x D | 33.6 |

## Machinability (Ø5 end mill)
* 70 U and 100 U: depth 15 / 19 mm = 3.0 / 3.8 x D: standard long-flute d5 carbide end mills (flute 20 mm) are enough; PP is soft, one roughing + one finishing pass (0.1 mm stock), climb milling.
* 200 U: depth about 33 mm = 6.5 x D: needs a long-reach d5 (reduced-neck, flute >= 34 mm); PCBWay may decline > 5 x D. **Lowest-risk fallback for 200 U (decide before ordering):** order the 200 U as a through
  bore (open both ends, machinable from both sides, 16.5 mm per side = 3.3 x D) with a separate PP closing plug (stadium plug with the d2.0 port, pressed + bonded) - this changes only the closed end,
  every frozen outer/bore/port dimension stays. Ask PCBWay support to confirm the blind 6.5 x D before paying; if they refuse use the fallback. 70/100 U stay blind (no risk).
* Wall 0.8 mm in PP: clamp on the outside flats with soft jaws, do not squeeze the 0.8 mm walls (fixture on the full-length side flats).
* Bore finish: Ra 0.8 um is the limit of a finishing end-mill pass in PP; no vapour polishing; a stamped/pulled bore would be better but is out of scope.

## PCBWay order form (exact settings; the form changes, VERIFY on the live page)
* Service: **CNC Machining** (3-axis is enough). Upload `OP-xx_reservoir_cnc.step` and attach the PDF drawing.
* Material: **Plastic -> Polypropylene (PP)**, colour natural/white. If a medical/USP Class VI grade is offered select it, otherwise standard PP-H and say so in the remarks (bench only).
* Quantity: **2**.  Surface finish: **As machined** (Ra 1.6); remark: "bore Ra <= 0.8 um, no polishing compound".
* Tolerance: **Standard (ISO 2768-m)**; critical: bore 16.00 +0.05/-0 and 5.00 +0.05/-0, port d2.0 H7 (use the drawing).
* Remarks: "blind stadium pocket d5 end mill R2.5 corners, deburr, no burrs in the bore, clean without oil residue, see drawing; check feasibility of depth/d5 (OP-200: 6.5 x D)".
* Threads: none. Inspection report: optional (bore size), not required for 2 pcs.

## Seals
Plunger lip seals are cast from **platinum-cure medical silicone** (Shore A 40-50, e.g. a 2-part LSR/RTV marked ISO 10993 / USP VI; SEARCH-TERM "platinum cure silicone USP class VI Shore 40") in the mould of this folder's sibling `mould/`.
Material note only (water-only project, never filled with insulin or any other drug): a bromobutyl plunger stopper cut to the stadium shape is one possible seal material for a future manufacturer; the stadium bore does not accept a standard round O-ring.
