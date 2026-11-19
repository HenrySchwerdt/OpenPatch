# OpenPatch bench pod - fabrication folder (`out/bench/fab/`)

EXPERIMENTAL bench test sample (Rev A bench split, spec 4a): water only, NEVER on a person. No battery, Qi coil, RF module or
main PCB: the pod carries only the 2-layer pod sensor board (ordered separately as PCBA, see `electronics/`) and an FFC cable
to the bench controller. Folders: `OP-70/`, `OP-100/`, `OP-200/` (upload), `mould/` (one set for all sizes), `dock-coupon/`
(fit test, order FIRST), `MANIFEST.csv`. Units mm; STEP is master, STL (fine) for the quote tool.

## Order sheet (every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
| `<SIZE>/bottom.stl` | MJF PA12 (JLC3DP: PA12-HP Nylon; PCBWay: MJF Nylon PA12) | PA12 | grey (natural) | bead-blasted standard; NO dye/vapour smoothing | 1 | +-0.2 mm. Contains the dock: two snap arms 0.8 mm thick x 9.5 mm free length (hook travel 1.8 mm, ~2.4 % strain). ORDER THE DOCK COUPON FIRST. Post-drill by hand: M1.2 pilot dia 1.0 (x5), hub bore dia 2.0 (test-fit), fluid channel dia 0.7. FFC exit slot is in the lid. Porous: NOT watertight. |
| `<SIZE>/top.stl` | MJF PA12 | PA12 | grey (natural) | bead-blasted standard | 1 | +-0.2 mm. FFC slot 8.0 x 1.1 mm in the +X wall, dome mouth in the lap. Screw holes dia 1.4 may need a drill. |
| `<SIZE>/carriage.stl` | SLA (JLC3DP: resin 8001 / 9000-type tough; PCBWay: SLA Somos/8000-type) | tough resin | any (white/grey) | support marks on the outside only; do not sand the hex pocket | 2 | +-0.1 mm (hex pocket AF 3.3 for DIN 934 M1.6 nut, dia 1.9 screw bore, rail groove 1.2 x 0.5). Order 2: nut fit is the first test. |
| `<SIZE>/plunger_core.stl` | SLA | tough or clear resin | any | no coating | 2 | +-0.1 mm. Seal grooves (0.8 mm wide) + socket for carriage tongue. Water test only. |
| `<SIZE>/reservoir.stl` | SLA (clear resin preferred, 'BioMed Clear'-class if offered, else standard clear) | clear resin | clear | wash + UV post-cure; inner bore stays unpolished | 1 | WATER-TEST ONLY (SLA copy; for insulin use the CNC PP part in reservoir-cnc/) - not sterile, not validated. +-0.1 mm; check bore 16.0 x 5.0 with a pin gauge; bore may need light honing. Single piece; open dry end. |
| `<SIZE>/end_cap.stl` | SLA (tough resin; later PP / CNC) | tough resin | any | no coating; clear internal channels d0.7 with a 0.5 mm wire | 2 | +-0.05 mm. End cap pressed onto the d2.0 H7 port of the CNC reservoir (spigot d1.98 x 2.0): fill septum bore d4.2 (side), duckbill pocket d3.05 with open slot, needle guard tube d3.2 / bore d2.0, internal channels d0.7. WATER ONLY in SLA resin. |
| `<SIZE>/coupler.stl` | SLA (tough resin) - or turned brass tube (preferred) | tough resin / brass | any | no coating | 2 | +-0.05 mm. Sleeve coupler d3.0 x 6.0: D-bore d2.04 / flat 1.5 (3.2 deep) for the NFP shaft, M1.6 bore d1.64 (2.8 deep) for the leadscrew; retain with one drop of cyanoacrylate / Loctite 638. VERIFY the shaft D-flat on the real motor. |
| `<SIZE>/cannula_adapter.stl` | SLA (JLC3DP resin 8001-type; PCBWay SLA) | tough resin | clear or white | support marks off the dome sides and the notches | 2 | +-0.1 mm. Dummy cannula head (dome d 10, base plate, side septum recess d 3.6, two latch notches, hose barb d 1.6, magnet pocket d 2.1 x 1.05 in the rear lug). Glue a d2x1 N52 magnet (CA drop) and press a punched d2 silicone plug into the septum bore. Dimensions follow cannula.* placeholders (TODO-MEASURE). |
| `mould/mould_lower.stl`, `mould_upper.stl` | SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA) | tough resin | any | wash + UV cure; drill sprue dia 0.7 / vent dia 0.5 clear | 1 set (all sizes) | One set for ALL sizes. +-0.05..0.1 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2). |
| `dock-coupon/dock_coupon.stl` | MJF PA12 **and** SLA tough resin (1 each) | PA12 / tough resin | grey / any | standard | 1 + 1 | no needle; 6 dock variants, fit test on a real cannula head |

Not uploaded (`reference_not_ordered/`): `plunger_seal` (cast in the mould) and `gasket` (cut from 0.5 mm silicone sheet).
The reservoir is an SLA clear part (water test only), same as the integrated variant. CNC reservoir halves are not part of the bench loop.

## Process recommendation
* Housing (bottom/top): MJF PA12 grey - the snap arms are designed for PA12 (E about 1.7 GPa, 2.4 % strain at 1.8 mm hook travel).
  If JLC3DP flags the 0.8 mm arms or 0.4 mm lap tongue, re-order the same files in SLA tough resin (stiffer: arm force rises, retest with the coupon).
* Carriage, plunger core, cannula adapter, mould: SLA tough resin. Reservoir: SLA clear.
* Vendor: JLC3DP default (one order, one shipment with the PCBA); PCBWay as fallback. See `../../fab/vendor-notes.md` for notes.

## Estimated cost per iteration (ESTIMATE - confirm with the instant quote)

Price model identical to the integrated variant (MJF 0.28 USD/g x 1.6, min 1.5 USD/part; SLA min 2.0 USD/part). Shipping 8-18 USD (one order).

| size | bottom x1 | top x1 | carriage x2 | plunger_core x2 | reservoir x1 | cannula_adapter x2 | coupler x2 | end_cap x2 | subtotal |
|---|---|---|---|---|---|---|---|---|---|
| OP-70 | $1.5 | $1.5 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $25.0 |
| OP-100 | $1.5 | $1.5 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $25.0 |
| OP-200 | $1.5 | $1.5 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $25.0 |

* Printed parts for ONE pod size: about **$25** (+ shipping); all three sizes: about **$75**.
* Dock coupon (MJF + SLA): about $6 - order it with the first pod batch, it decides the cannula.* values.
* Mould (once, reusable): about $42.
* Per iteration (1 size + coupon + shipping, no mould): about **$39 - $49**; repeat iterations without coupon about $33 - $43.
* Not included: pod sensor board PCBA (see electronics), motor (reusable), spring contacts, FFC cable, magnets, needle hubs: see `../ASSEMBLY.md`.
