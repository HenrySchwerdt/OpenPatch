# OpenPatch v0.1.0 integrated pod - fabrication folder (`out/v010/fab/`)

EXPERIMENTAL TEST sample, **water only, never on a person or animal**. The pod is the bench pod (frozen CNC/SLA reservoir, dock interface, drive) plus the
electronics (main board over the dock tunnel, ~30 mAh Li-Po in the strip beside it, waterproof USB-C at the +X end, piezo, button, pressure vent; charge pads and cradle dropped, spec 2d). Folders: `OP-70/`, `OP-100/`, `OP-200/`
(upload), `usb-gasket/` (DXF, die/laser cut), `mould/` (all sizes), `dock-inserts/` (shared with the bench pod), `MANIFEST.csv`. Units mm; STEP is master.

## Order sheet (every size)

| file | process | material | colour | finish | qty / size | tolerance, notes |
|---|---|---|---|---|---|---|
| `<SIZE>/bottom.stl` | MJF PA12 (JLC3DP: PA12-HP Nylon; PCBWay: MJF Nylon PA12) | PA12 | grey (natural) | bead-blasted standard; NO dye/vapour smoothing | 1 | +-0.2 mm. Bench pod shell + v0.1.0: USB-C opening 9.4 x 3.4 mm in the +X wall (0.4 mm web above), battery bay ribs (0.5 mm), motor contact shelf, USB board posts, board posts/pins, M1.2 pilots dia 1.0 (x6). Order the dock-insert set (bench `dock-inserts/`, same frozen interface) first. Porous: splash-level only. |
| `<SIZE>/top.stl` | SLA (JLC3DP clear / transparent resin, spec 2a: clear lid, no fill-window slot) | clear resin | clear | wash + UV cure; no polish on the gasket seat | 1 | +-0.1 mm. Board, cell and LEDs are visible: keep the electronics tidy; optional light-blocking black ink / paint mask on the inside over the status LED only if needed. Lid features: piezo port dia 0.8 + membrane recess dia 4.0 x 0.2, button membrane 0.5 mm, pressure vent dia 0.8 + dia 5.0 x 0.2 recess (ePTFE disc). 0.5 mm membranes are at the printable floor: order 2. |
| `<SIZE>/carriage.stl` | SLA (JLC3DP: resin 8001 / 9000-type tough; PCBWay: SLA Somos/8000-type) | tough resin | any (white/grey) | support marks on the outside only; do not sand the hex pocket | 2 | +-0.1 mm (hex pocket AF 3.8 = DIN 934 M1.6 AF 3.2 + 0.6 clearance (0.3 mm radial float), closed rear wall + top drop-in slot, dia 1.9 screw bore, rail groove 1.2 x 0.5). Order 2: nut fit is the first test. |
| `<SIZE>/plunger_core.stl` | SLA | tough or clear resin | any | no coating | 2 | +-0.1 mm. Seal grooves (0.8 mm wide) + socket for carriage tongue. Water test only. |
| `<SIZE>/reservoir.stl` | SLA (clear resin preferred, 'BioMed Clear'-class if offered, else standard clear) | clear resin | clear | wash + UV post-cure; inner bore stays unpolished | 1 | WATER ONLY (SLA copy; the CNC PP part in reservoir-cnc/ is only a material preparation for a future manufacturer) - not sterile, not validated. +-0.1 mm; check bore 16.0 x 5.0 with a pin gauge; bore may need light honing. Single piece; open dry end. |
| `<SIZE>/end_cap.stl` | SLA (tough resin; later PP / CNC) | tough resin | any | no coating; clear internal channels d0.7 with a 0.5 mm wire | 2 | +-0.05 mm. End cap pressed onto the d2.0 H7 port of the CNC reservoir (spigot d1.98 x 2.0): fill septum bore d4.2 (side), duckbill pocket d3.05 with open slot, needle guard tube d3.2 / bore d2.0, internal channels d0.7. WATER ONLY in SLA resin. |
| `<SIZE>/coupler.stl` | SLA (tough resin) - or turned brass tube (preferred) | tough resin / brass | any | no coating | 2 | +-0.05 mm. Sleeve coupler d3.0 x 6.0: D-bore d2.04 / flat 1.5 (3.2 deep) for the NFP shaft, M1.6 bore d1.64 (2.8 deep) for the leadscrew; retain with one drop of cyanoacrylate / Loctite 638. VERIFY the shaft D-flat on the real motor. |
| `<SIZE>/plunger_nose.stl` | SLA (JLC3DP resin 8001-type) | tough resin | any | no coating | 2 | +-0.1 mm. 0.7 mm stadium disc (14.6 x 3.6) glued (CA) onto the plunger front: dead layer 0.3 mm. WATER ONLY. |
| `<SIZE>/valve_plug.stl` | SLA (JLC3DP resin 8001-type) | tough resin | any | no coating | 2 | +-0.05 mm. Press-fit plug (0.04 mm interference per side) that closes the duckbill insertion slot in the end cap; flush with the cap top. |
| `<SIZE>/thrust_sleeve.stl` | SLA, or brass tube d2.0 x d1.6 x 2.05 (cut + deburr) | tough resin / brass | any | no coating | 2 | +-0.05 mm. Gear carrier and rear thrust shoulder: slides on the rod, rear face on the dry bush, GHW 753020 (bore 2.0) glued on it (Loctite 638). Printed d2.0 walls are thin: brass tube recommended. |
| `<SIZE>/thrust_collar.stl` | SLA, or brass tube d2.4 x d1.6 x 1.0 | tough resin / brass | any | no coating | 2 | +-0.05 mm. Front thrust shoulder at the rod end: bears on the far bush face; the magnet is glued to the rod end behind it and carries no thrust. |
| `<SIZE>/cannula_adapter.stl` | SLA (JLC3DP resin 8001-type; PCBWay SLA) | tough resin | clear or white | support marks off the dome sides and the notches | 2 | +-0.1 mm. Dummy cannula head (dome d 10, base plate, side septum recess d 3.6, two latch notches, hose barb d 1.6, magnet pocket d 2.1 x 1.05 in the rear lug). Glue a d2x1 N52 magnet (CA drop) and press a punched d2 silicone plug into the septum bore. Dimensions follow cannula.* placeholders (TODO-MEASURE). |
| `mould/mould_lower.stl`, `mould_upper.stl` | SLA (high detail, e.g. JLC3DP 8001 / PCBWay SLA) | tough resin | any | wash + UV cure; drill sprue dia 0.7 / vent dia 0.5 clear | 1 set | One set for ALL sizes. +-0.05..0.1 mm. Check the 4 pin/hole fits (pin dia 2.0 / hole 2.2). |
| `usb-gasket/usb_gasket.dxf` | DO NOT PRINT - die/laser-cut 0.5 mm silicone sheet, Shore A 30-40, frame 0.8 mm wide (DXF in usb-gasket/) | silicone | - | - | 2 | frame 0.8 mm, 0.5 mm sheet |

Not uploaded: `plunger_seal` (cast in the mould), `gasket` (0.5 mm silicone sheet), `usb_gasket` (cut from 0.5 mm silicone).

## Purchased items specific to v0.1.0 (not printed)

| item | source | qty |
|---|---|---|
| Radio module <= 1.3 mm on the lid side (ISP1807-class SiP; electronics agent decides) | on the PCBA | 1 per pod |
| Li-Po cell 301012 class (3.0 x 10 x 12 mm incl. PCM, ~30 mAh) AND 301015/301020 class as spare candidates | AliExpress / generic | 3 candidates |
| Waterproof USB Type-C receptacle, mid-mount, IPX7 class, ~8.94 x 7.35 x 3.26 mm (vendor drawing VERIFY) + USB board + 2 elastomer/pogo links 2.1 mm | AliExpress / LCSC | 1 + spare |
| NFP-608 motor with FPC tail (custom, spec 1c) or 4-trace flex jumper; 4 SMD spring contacts 0.9 mm | group buy / LCSC | 1 + spare |
| SMD spring contacts, 1.0-1.2 mm free height, 2 per pod (MPN VERIFY; fallback M1.2 clamp pads) | LCSC / DigiKey | 2 + spares |
| Double-sided foam tape 0.6 mm (cell bed) | generic | 1 strip |
| SMD piezo 9 x 9 x 1.0 (Murata PKMCS0909E4000-R1 class) | on the PCBA | 1 |
| Silicone sheet 0.5 mm Shore A 30-40 (main gasket, USB-C gasket) | generic | 1 sheet |
| ePTFE adhesive vent / acoustic membrane discs d5 and d4 (PU film for the buzzer port) | generic | 4+ |
| M1.2 x 6 self-tapping screws (lid, x6), M1.2 x 4 (board, x1), M2 x 8 (cradle, x2) | generic | 1 set |

## Estimated printed-part cost (ESTIMATE, same price model as the bench pod; confirm with the instant quote)

| size | bottom x1 | top x1 | carriage x2 | plunger_core x2 | plunger_nose x2 | reservoir x1 | cannula_adapter x2 | end_cap x2 | valve_plug x2 | thrust_sleeve x2 | thrust_collar x2 | cradle | subtotal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OP-100 | $1.5 | $2.7 | $4.0 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $4.0 | $4.0 | $0.0 | $38.2 |
| OP-200 | $1.5 | $3.2 | $4.0 | $4.0 | $4.0 | $2.0 | $4.0 | $4.0 | $4.0 | $4.0 | $4.0 | $0.0 | $38.7 |

* One OP-100 set about **$38** (+ shipping 8-18 USD, + dock-insert set about $26 if not already ordered for the bench pod, + mould about $42 once).
* The PCBA (board outline from `OP-xx.layout.json`) is ordered separately; see `../V010.md` for the open items.
