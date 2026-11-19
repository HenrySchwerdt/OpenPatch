# OpenPatch v0.1.0 integrated pod - fabrication folder (`out/v010/fab/`)

EXPERIMENTAL TEST sample, **water only, never on a person or animal, never insulin or any drug**. One coherent model (`generate.py --variant v010`, `V010.md`): coaxial one-rod drive, motor in the rear zone,
closed CNC reservoir (re-frozen interface), minimal fluid module, dock insert on the frozen interface, MAIN / POWER / SENSOR boards, waterproof USB-C in the rear wall, clear lid.
Folders: `OP-100/`, `OP-200/` (upload), `reservoir-cnc/` (STEP for the CNC order), `mould/`, `dock-inserts/` (shared with the bench pod), `gasket/`, `cap-gasket/`, `usb-gasket/` (DXF for die/laser cutting),
`parts/` (one README per part: process, material, tolerances, post-processing), `MANIFEST.csv`. Units mm; STEP is master.

JLC3DP vendor tolerances: SLA +-0.2 mm (holes shrink, +-0.3), MJF +-0.3 mm (holes shrink, +-0.3); the CAD clearances already assume them (dfm_rules.json).

## Order sheet (every size)

| file | process | material | colour | finish | qty | tolerance / features |
|---|---|---|---|---|---|---|
| `<SIZE>/bottom.stl` | MJF PA12 (JLC3DP Nylon / PA12-HP) | PA12 | grey (natural) | bead-blasted standard; no dye, no vapour smoothing | 1 | +-0.3 mm (vendor). Bearing-block bore d3.05 for the bush, M1.2 pilots d1.0, USB-C opening 9.4 x 3.4 mm with a 0.4 mm web, spine channel 0.3 deep (floor 0.6 left), crush ribs printed 0.4 mm proud. |
| `<SIZE>/top.stl` | SLA (JLC3DP clear / transparent resin; spec 2a: CLEAR LID) | clear resin | clear (polish / clear-coat the outside) | wash + UV cure; clear-coat the outside; do not polish the gasket seat or the engraving | 1 | +-0.2 mm (vendor). Lid wall 0.9 mm, 0.75 mm over the reservoir recess, 0.6 mm under the scale engraving (0.15 deep), button membrane 0.5 mm, vent d0.8 + d5.0 x 0.2 recess, piezo port d1.2 + d4.0 x 0.2 recess. |
| `<SIZE>/end_cap.stl` | SLA (JLC3DP 8001/9000-type tough resin) | tough resin | any | no coating; clear channels with a 0.5 mm wire | 2 | +-0.2 mm (vendor). Lower half of the fluid sandwich: spigot d1.98 x 1.8 (locating only), O-ring face groove, gasket recess 0.4, septum pocket axis Z (underside fill, inside the footprint), fill-needle hole d2.0 through the pod floor, via d0.6, needle bore, guard tube d3.2. |
| `<SIZE>/end_cap_lid.stl` | SLA (JLC3DP 8001/9000-type tough resin) | tough resin | any | no coating | 2 | +-0.2 mm (vendor). Upper half of the clamped sandwich: flat underside on the lands, septum chamber recess, spur groove, O-ring half groove, spigot half pin, 2 x M1.2 x 6 clamp screws (clearance d1.4). |
| `<SIZE>/plunger_core.stl` | SLA (JLC3DP 8001/9000-type tough resin) | tough resin | any | no coating | 2 | +-0.2 mm (vendor) on a 4.5 x 25.5 mm stadium (core clearance 0.1 per side in the CAD: the vendor +-0.2 is absorbed by the seal bead (squeeze 0.03 mm) and the PTFE-tape recess). |
| `reservoir-cnc/<SIZE>_reservoir_cnc.step` | CNC (PCBWay / JLCCNC CNC; polypropylene PP-H) | PP | natural | as machined | 2 | +-0.1 mm; bore 25.7 x 4.7 +0.05/-0 (corner R2.35 = D4.7 end mill), wall 1.0 (JLCCNC absolute plastic minimum), end wall 2.0, port d2.0 H7 offset 5.95 mm from the bore centre, outer 27.7 x 6.7. Inspection report requested for bore height and port. |
| `mould/mould_lower.stl`, `mould_upper.stl` | SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA) | tough resin | any | print each half standing on its short end (cavity axis vertical), wash + UV cure; clear sprue dia 0.8 / vent dia 0.5 | 1 set | THREE seal variants (S1, S2, T) = 3 sets for ALL sizes (SEAL-AND-DEAD-VOLUME.md). +-0.05 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2). |
| `dock-inserts/` | SLA (JLC3DP tough resin) or MJF PA12 | | | | 12 | shared with the bench pod |

Not uploaded: `plunger_seal` (cast), `gasket`, `cap_gasket`, `usb_gasket` (silicone sheet cut from the DXFs).

## Purchased items (not printed)

| item | source | qty |
|---|---|---|
| Drive screw M1.6 x 0.35 A2 stainless threaded rod, cut to 14.5 mm (OP-100) / 23.0 mm (OP-200) + hacksaw slot 0.4 x 1.0 across the tip | hardware / AliExpress | 1 + spare |
| DIN 934 M1.6 brass nut AF 3.2, glued (Loctite 638) on the front face of the nut gear | hardware | 2 |
| NFP-608-26.45-SGM stepper gearmotor, FPC / pin version (motor pins face +Y toward the contact card) | nfpshop.com | 1 + spare |
| GHW module 0.3 brass gears 390754 (z16, motor) and 753020 (z20, nut gear, hub turned off) | GHW-Modellbau | 1 + spare |
| Thrust sleeve: brass tube d2.0 x d1.64 x 3.1 mm (cut + deburr); dry bush d3.0 x d1.7 x 1.0 (PTFE/brass) | hardware | 1 each + spare |
| Diametric RING magnet N45/N52 d5 x d2 x 1.5 mm (custom order; VERIFY availability) glued on the sleeve | magnet vendor | 2 |
| 30G needle + printed hub, O-ring 2.0 x 0.7 (NBR/silicone), silicone septum disc d3.2 x 2, 0.5 mm silicone sheet | generic | 1 set |
| ISP1807 radio SiP 8 x 8 x 1.0 (on the MAIN PCBA, consigned) + MAIN / POWER / SENSOR boards (electronics/v010) | JLCPCB PCBA | 1 set |
| Li-Po cell 301012 class (3.0 x 10 x 12 mm incl. PCM, ~30 mAh) + 0.6 mm foam tape | AliExpress | 3 candidates |
| Waterproof USB-C 16P mid-mount receptacle (IPX7 class, 8.94 x 7.35 x 3.26 mm, drawing VERIFY) + USB board | AliExpress / LCSC | 1 + spare |
| SMD spring contacts (1.0-1.2 mm free height): 2 on MAIN for the cell, 4 on the motor contact card, 8 on the MAIN tongue for the FPC spine | LCSC | 14 + spares |
| FPC spine (flex, 0.1 mm, ~4 mm wide x 45 mm) between the motor card, SENSOR board and the MAIN tongue | JLCPCB / PCBWay flex | 1 + spare |
| SMD piezo 9 x 9 x 1.0 on the lid inner face, ePTFE vent disc d5, PU film d4, M1.2 x 6 self-tapping screws (x9) + M1.2 x 6 (cap clamp x2) | generic | 1 set |

## Estimated printed-part cost (ESTIMATE, same price model as the bench pod)

| size | bottom x1 | top x2 | end_cap x2 | end_cap_lid x2 | plunger_core x2 | cannula_adapter x2 | subtotal (printed) |
|---|---|---|---|---|---|---|---|
| OP-100 | $1.5 | $5.4 | $4.0 | $4.0 | $4.0 | $4.0 | $22.9 |
| OP-200 | $1.5 | $6.1 | $4.0 | $4.0 | $4.0 | $4.0 | $23.6 |

* + shipping 8-18 USD; the CNC reservoir quote comes from the vendor (qty 2 per size).
* The PCBAs (outlines in `OP-xx.layout.json`) are ordered separately (`electronics/v010`).
