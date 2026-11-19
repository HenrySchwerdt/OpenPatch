# OpenPatch bench pod - fabrication folder (`out/bench/fab/`)

EXPERIMENTAL bench test sample (Rev A bench split, spec 4a): water only, NEVER on a person. No battery, Qi coil, RF module or
main PCB: the pod carries only the 2-layer pod sensor board (ordered separately as PCBA, see `electronics/`) and an FFC cable
to the bench controller. Folders: `OP-70/`, `OP-100/`, `OP-200/` (upload), `mould/` (three seal-variant sets, valid for all sizes), `dock-inserts/`
(12 swappable dock insert variants + pod-less fixture, order FIRST), `reservoir-sla-water-only/` (print copy of the frozen reservoir, WATER ONLY), `MANIFEST.csv`. Units mm; STEP is master, STL (fine) for the quote tool.

## Order sheet (every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
| `<SIZE>/bottom.stl` | MJF PA12 (JLC3DP: PA12-HP Nylon; PCBWay: MJF Nylon PA12) | PA12 | grey (natural) | bead-blasted standard; NO dye/vapour smoothing | 1 | +-0.2 mm. Contains the dock: two snap arms 0.8 mm thick x 9.5 mm free length (hook travel 1.8 mm, ~2.4 % strain). ORDER THE DOCK COUPON FIRST. Post-drill by hand: M1.2 pilot dia 1.0 (x5), hub bore dia 2.0 (test-fit), fluid channel dia 0.7. FFC exit slot is in the lid. Porous: NOT watertight. |
| `<SIZE>/top.stl` | SLA clear resin (JLC3DP clear, spec 2a) | clear resin | clear (polish / clear-coat the outside) | wash + UV; no window slot: the wall is closed | 1 | +-0.1 mm. CLEAR LID: reservoir, water level and drive are visible through it. Fill scale = 0.15 mm engraving on the inner face (tick / 10 U, long / 50 U). FFC slot 8.0 x 1.1 mm in the +X wall, dome mouth in the lap. Screw holes dia 1.4 may need a drill. WATER ONLY. |
| `<SIZE>/carriage.stl` | SLA (JLC3DP: resin 8001 / 9000-type tough; PCBWay: SLA Somos/8000-type) | tough resin | any (white/grey) | support marks on the outside only; do not sand the hex pocket | 2 | +-0.1 mm (hex pocket AF 3.8 = DIN 934 M1.6 AF 3.2 + 0.6 clearance (0.3 mm radial float), closed rear wall + top drop-in slot, dia 1.9 screw bore, rail groove 1.2 x 0.5). Order 2: nut fit is the first test. |
| `<SIZE>/plunger_core.stl` | SLA | tough or clear resin | any | no coating | 2 | +-0.1 mm. Seal grooves (0.8 mm wide) + socket for carriage tongue. Water test only. |
| `<SIZE>/reservoir.stl` | SLA (clear resin preferred, 'BioMed Clear'-class if offered, else standard clear) | clear resin | clear | wash + UV post-cure; inner bore stays unpolished | 1 | WATER ONLY (SLA copy; the CNC PP part in reservoir-cnc/ is only a material preparation for a future manufacturer) - not sterile, not validated. +-0.1 mm; check bore 16.0 x 5.0 with a pin gauge; bore may need light honing. Single piece; open dry end. |
| `<SIZE>/end_cap.stl` | SLA (tough resin; later PP / CNC) | tough resin | any | no coating; clear internal channels d0.7 with a 0.5 mm wire | 2 | +-0.05 mm. End cap pressed onto the d2.0 H7 port of the CNC reservoir (spigot d1.98 x 2.4, locating only; sealed by a face O-ring 2.0 x 0.5 in the cap groove): septum pocket (axis Z, 15 % axial compression on the d4.0 x 2.0 disc, underside fill), no check valve, needle guard tube d3.2 / bore d2.0, channels d0.5 (short, flushable while open), one gasket slot; needle UV-glued in the hub seat with a printed jig. WATER ONLY in SLA resin. |
| `<SIZE>/coupler.stl` | SLA (tough resin) - or turned brass tube (preferred) | tough resin / brass | any | no coating | 2 | +-0.05 mm. Sleeve coupler d3.0 x 6.0: D-bore d2.04 / flat 1.5 (3.2 deep) for the NFP shaft, M1.6 bore d1.64 (2.8 deep) for the leadscrew; retain with one drop of cyanoacrylate / Loctite 638. VERIFY the shaft D-flat on the real motor. |
| `<SIZE>/plunger_nose.stl` | SLA (JLC3DP resin 8001-type) | tough resin | any | no coating | 2 | +-0.1 mm. 0.7 mm stadium disc (14.6 x 3.6) glued (CA) onto the plunger front: dead layer 0.3 mm. WATER ONLY. |
| `<SIZE>/end_cap_lid.stl` | SLA (JLC3DP resin 8001-type) | tough resin | any | no coating | 2 | +-0.05 mm. Upper half of the clamped fluid sandwich: flat underside on the lands, septum chamber recess + spur groove, O-ring half groove, 2 x M1.2 x 6 clamp screws. WATER ONLY. |
| `<SIZE>/thrust_sleeve.stl` | SLA, or brass tube d2.0 x d1.6 x 2.05 (cut + deburr) | tough resin / brass | any | no coating | 2 | +-0.05 mm. Gear carrier and rear thrust shoulder: slides on the rod, rear face on the dry bush, GHW 753020 (bore 2.0) glued on it (Loctite 638). Printed d2.0 walls are thin: brass tube recommended. |
| `<SIZE>/thrust_collar.stl` | SLA, or brass tube d2.4 x d1.6 x 1.0 | tough resin / brass | any | no coating | 2 | +-0.05 mm. Front thrust shoulder at the rod end: bears on the far bush face; the magnet is glued to the rod end behind it and carries no thrust. |
| `<SIZE>/cannula_adapter.stl` | SLA (JLC3DP resin 8001-type; PCBWay SLA) | tough resin | clear or white | support marks off the dome sides and the notches | 2 | +-0.1 mm. Dummy cannula head (dome d 10, base plate, side septum recess d 3.6, two latch notches, hose barb d 1.6, magnet pocket d 2.1 x 1.05 in the rear lug). Glue a d2x1 N52 magnet (CA drop) and press a punched d2 silicone plug into the septum bore. Dimensions follow cannula.* placeholders (TODO-MEASURE). |
| `mould/mould*_lower.stl`, `mould*_upper.stl` (3 variants S1, S2, T) | SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA) | tough resin | any | print each half standing on its short end (cavity axis vertical), wash + UV cure; clear sprue dia 0.8 / vent dia 0.5 | 3 sets (all sizes) | THREE seal variants (S1, S2, T) = 3 sets for ALL sizes (SEAL-AND-DEAD-VOLUME.md). +-0.05 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2). |
| `dock-inserts/insert_v01..v12.stl` | SLA tough resin (or MJF PA12) | tough resin / PA12 | any | support marks off arms | 12 (shared by all sizes) | swappable dock insert variants (ID on the -Y arm), see `variants.csv` |
| `dock-inserts/dock_fixture.stl` | MJF PA12 or SLA | PA12 / tough resin | any | standard | 1 | pod-less fixture with the frozen dock interface: fit the inserts to a real cannula head without a pod |
| `reservoir-sla-water-only/<SIZE>_reservoir_WATER-ONLY_sla.stl` | SLA clear resin | clear | clear | wash + UV | 1 per size | **WATER ONLY - never insulin or any drug** (printed resin is not validated for any drug). Print copy of the frozen reservoir geometry; the CNC PP part in `reservoir-cnc/` is an optional material preparation, also never filled with insulin |

Not uploaded (`reference_not_ordered/`): `plunger_seal` (cast in the mould) and `gasket` (cut from 0.5 mm silicone sheet).
The reservoir is an SLA clear part (water test only), same as the integrated variant. CNC reservoir halves are not part of the bench loop.

## Process recommendation
* Housing (bottom/top): MJF PA12 grey - the snap arms are designed for PA12 (E about 1.7 GPa, 2.4 % strain at 1.8 mm hook travel).
  If JLC3DP flags the 0.8 mm arms or 0.4 mm lap tongue, re-order the same files in SLA tough resin (stiffer: arm force rises, retest with the insert set).
* Carriage, plunger core, cannula adapter, mould: SLA tough resin. Reservoir: SLA clear.
* Vendor: JLC3DP default (one order, one shipment with the PCBA); PCBWay as fallback. See `../../fab/vendor-notes.md` for notes.

## Estimated cost per iteration (ESTIMATE - confirm with the instant quote)

Price model identical to the integrated variant (MJF 0.28 USD/g x 1.6, min 1.5 USD/part; SLA min 2.0 USD/part). Shipping 8-18 USD (one order).

| size | bottom x1 | top x1 | carriage x2 | plunger_core x2 | reservoir x1 | cannula_adapter x2 | end_cap x2 | end_cap_lid x2 | thrust_sleeve x2 | thrust_collar x2 | subtotal |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OP-70 | $1.5 | $2.0 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $4.0 | $4.0 | $33.5 |
| OP-100 | $1.5 | $2.2 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $4.0 | $4.0 | $33.7 |
| OP-200 | $1.5 | $2.7 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $4.0 | $4.0 | $34.2 |

* Printed parts for ONE pod size: about **$34** (+ shipping); all three sizes: about **$101**.
* Dock insert set (12 SLA inserts + 1 fixture): about $26 - order it with the first pod batch, it decides the cannula.* values; later iterations only need the inserts that changed.
* Mould (once, reusable): about $126.
* Per iteration (1 size + coupon + shipping, no mould): about **$67 - $77**; repeat iterations without coupon about $42 - $52.
* Not included: pod sensor board PCBA (see electronics), motor (reusable), spring contacts, FFC cable, magnets, needle hubs: see `../ASSEMBLY.md`.
