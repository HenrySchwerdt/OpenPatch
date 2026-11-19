# OpenPatch Rev A - fabrication folder (`out/fab/`)

EXPERIMENTAL DIY device, not a medical device. Everything here is for bench/water testing.
Folders: `OP-70/`, `OP-100/`, `OP-200/` (upload these), `mould/` (one set for all sizes), `MANIFEST.csv`
(machine-readable version of the table below). Units: mm. STEP is the master, STL (fine tessellation) is for the
quote tool; `assembly_reference.step` and `reference_not_ordered/` are NOT to be uploaded.

## Per-file ordering sheet (same for every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
| `<SIZE>/bottom.stl` | MJF PA12 (JLC3DP: PA12-HP Nylon; PCBWay: MJF Nylon PA12) | PA12 | grey (natural, cheapest) | bead-blasted standard; NO dye/vapour smoothing | 1 | +-0.2 mm. Post-drill by hand: needle bore dia 0.5, M1.2 pilot dia 1.0 (test-fit), ream hub seat dia 2.0. Cannula pocket: TODO-MEASURE, order N_clearance 0.10/0.15/0.20 coupons first. Porous: NOT watertight. |
| `<SIZE>/top.stl` | MJF PA12 | PA12 | grey (natural) | bead-blasted standard | 1 | +-0.2 mm. 0.5 mm button membrane is at the printable limit - order 2 and keep the better one. Acoustic port dia 1.2 and screw holes dia 1.4 may need a drill. |
| `<SIZE>/carriage.stl` | SLA (JLC3DP: resin 8001 / 9000-type tough; PCBWay: SLA Somos/8000-type) | tough resin | any (white/grey) | support marks on the outside only; do not sand the hex pocket | 2 | +-0.1 mm (hex pocket AF 3.3 for DIN 934 M1.6 nut, dia 1.9 screw bore, rail groove 1.2 x 0.5). Order 2: nut fit is the first test. |
| `<SIZE>/plunger_core.stl` | SLA | tough or clear resin | any | no coating | 2 | +-0.1 mm. Seal grooves (0.8 mm wide) + socket for carriage tongue. Water test only. |
| `<SIZE>/reservoir.stl` | SLA (clear resin preferred, 'BioMed Clear'-class if offered, else standard clear) | clear resin | clear | wash + UV post-cure; inner bore stays unpolished | 1 | WATER ONLY - never insulin, not sterile, not validated. +-0.1 mm; check bore 16.0 x 5.0 with a pin gauge; bore may need light honing. Single piece; open dry end. |
| `mould/mould_lower.stl`, `mould_upper.stl` | SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA) | tough resin | any | wash + UV cure; drill sprue dia 0.7 / vent dia 0.5 clear | 1 set (all sizes) | One set for ALL sizes. +-0.05..0.1 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2). |

Not uploaded (reference geometry in `reference_not_ordered/`): `plunger_seal` (cast in the mould) and `gasket`
(die/laser-cut from silicone sheet). CNC reservoir halves (`reservoir_cnc_*`) are in `out/` only; they are the
optional material preparation for a future manufacturer (never filled with insulin) and are not part of the cheap monthly loop.

## Vendor choice (low cost first)

* **Default: JLC3DP** for everything (MJF PA12 housing, SLA small parts). Cheapest per set in the public price pages
  I could read (PA12 about 0.275-0.35 USD/g after the recent price cuts; from 0.30 USD/part for small parts).
* **PCBWay** only if (a) you want one order with PCBs + prints (shared shipping), (b) JLC3DP rejects thin walls
  (0.4 mm tongue, 0.5 mm membrane) - PCBWay engineers review files by hand - or (c) you need the CNC PP reservoir
  (CNC quotes start around 25 USD per part). Upload the same files; processes have the same names (MJF Nylon PA12, SLA).
* Details: `vendor-notes.md`.

## Estimated cost per monthly iteration (ESTIMATE - confirm with the instant quote)

Assumptions (edit in `fab.py`): MJF PA12 0.28 USD/g x density 1.0 x billing factor 1.6
(MJF bills offset volume), min 1.5 USD/part; SLA resin min 2.0 USD/part, volume term
~1.0 USD/cm3 x 1.5. Shipping 8-18 USD per order (one order).

| size | bottom | top | carriage x2 | plunger_core x2 | reservoir | subtotal |
|---|---|---|---|---|---|---|
| OP-70 (vol cm3: 1.96/1.31/0.09/0.23/0.56) | $1.5 | $1.5 | $4.0 | $4.0 | $2.0 | $13.0 |
| OP-100 (vol cm3: 2.07/1.44/0.09/0.23/0.68) | $1.5 | $1.5 | $4.0 | $4.0 | $2.0 | $13.0 |
| OP-200 (vol cm3: 2.45/1.87/0.09/0.23/1.10) | $1.5 | $1.5 | $4.0 | $4.0 | $2.0 | $13.0 |

* One set per size (OP-70/100/200): about **$39**; spares (1 extra bottom + top of OP-100): about $3;
  mould (once, reusable for a few casts): about $42.
* Printed parts per iteration (3 sizes + spares): about **$50 - $60** incl. shipping
  (without the mould). Realistic expectation: 40-60 USD for a 3-size iteration (about 20-25 USD for a single size); the per-part minimums dominate, not the volume.
* Purchased mechanical parts per iteration: see `../../parts.md` (AliExpress geared stepper, M1.6 rod/nuts, gears, magnet,
  needles): about 25-45 USD per pump, much of it reusable (motors, gears, screws are not consumed).
