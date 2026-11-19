# end_cap

> TEST PROJECT: not a medical device. WATER ONLY, never on a person.

| item | value |
|---|---|
| process | SLA (JLC3DP 8001/9000-type tough resin) |
| material | tough resin |
| colour | any |
| finish | no coating; clear channels with a 0.5 mm wire |
| quantity per pod | 2 |
| uploaded to the vendor | yes |
| volume OP-100 / OP-200 (cm3) | 0.13 / 0.13 |

**Tolerances / features:** +-0.2 mm (vendor). Lower half of the fluid sandwich: spigot d1.98 x 1.8 (locating only), O-ring face groove, gasket recess 0.4, septum pocket axis Z (underside fill, inside the footprint), fill-needle hole d2.0 through the pod floor, via d0.6, needle bore, guard tube d3.2.

**Post-processing:** Ream the spigot-to-port fit only if it does not enter the port d2.0 H7 by hand (spigot d1.98 prints 2.0-2.2: sand to 1.95 with 1500 grit). Hub seat d2.0: ream with a 2.0 drill. Channels d0.5-0.6 are at the SLA hole minimum: clear them with a 0.5 mm wire; water test only.

**Notes:** Module retention against the reservoir: two printed crush ribs in the bottom shell push the reservoir against the cap, O-ring land contact guaranteed (check.py).

JLC3DP vendor tolerances: SLA +-0.2 mm (holes shrink, +-0.3), MJF +-0.3 mm (holes shrink, +-0.3); the CAD clearances already assume them (dfm_rules.json).
