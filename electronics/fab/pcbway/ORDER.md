> TEST ONLY - NOT FOR HUMAN USE (see ../../../DISCLAIMER.md). Bench sample; never wear or use on a person.

# PCBWay order guide (secondary vendor) - OpenPatch OP-100 Rev A

PCBWay is more expensive than JLCPCB for this build (see ../COST.md); use it if JLC cannot do the via-in-pad/consignment or the ISP1807 must be sourced by the fab.
**Do not order until the blockers in `../jlcpcb/ORDER.md` section 4 are closed** (same board).

Files: `openpatch-reva-gerbers.zip` (Gerber + Excellon), `BOM-pcbway.csv` (Designator, Quantity, Manufacturer, MPN, Description, Package, Type, LCSC), `CPL-pcbway.csv` (Designator, Mid X, Mid Y, Layer, Rotation), `../NOT-ASSEMBLED.csv`.

| Field | Value |
|---|---|
| Layers / material | 4 layers, FR4 TG150 |
| Thickness | **0.8 mm** (0.6 mm is available at PCBWay but costs more; the mechanical stack assumed 0.6 mm: choose 0.6 only if the quote delta is small) |
| Min track / space | 4/4 mil (0.1 mm) |
| Min hole size | 0.2 mm |
| Surface finish | ENIG (1-2 u") |
| Via process | **via in pad: epoxy filled and capped** (ISP1807 inner pads) |
| Outer / inner copper | 1 oz / 0.5 oz |
| Board outline | milled, slot 2.8 x 2.8 mm |
| Quantity | 5 PCBs |
| Assembly | Turnkey or consignment; both sides; qty 2; special assembly: ISP1807 module and the FPC/spring contacts consigned or fitted by hand by the fab ("customer-supplied parts") |
| Special notes | same as JLC order remarks (see ../jlcpcb/ORDER.md section 3); PCBWay may require the antenna keep-out confirmation and X-ray for LGA |

The pre-order checklist is identical to `../jlcpcb/ORDER.md` section 4.
