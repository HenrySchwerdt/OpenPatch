# Decision 2026-11-19: electronics lessons from an Omnipod teardown (user-approved)

Test project, not a medical device. Applies to the next v0.1.0 electronics spin, **after** the mechanics are rebuilt on drive concept B (one rotating rod, two gears, cup plunger, closed tank, fill septum underside).

1. **Spring contacts / gold pads instead of connectors.** No FFC/ZIF/PicoBlade between boards or to motor and cell: gold landing pads on the boards, low-profile SMD spring contacts (or pogo pins) pressed by the housing, Omnipod-style.
2. **Move most of the discrete safety logic into the supervisor MCU** (STM32C011 or equivalent) to shrink the POWER board (today ~16 discrete NFET/gate legs, OC latch etc.). **Keep a minimal pure-hardware cut path** (required by `CLAUDE.md` / `docs/02-safety.md`): motor supply switch conducts only if the **external watchdog latch (TPL5010-class) AND DOCKED** (plus the existing over-current trip if it fits in 3–4 parts). Document the new split in `INTERLOCK.md` and the FMEA.
3. **HDI / 6-layer allowed** where it clearly shrinks the board (via-in-pad, 0201), cost impact stated in `COST.md`.
4. **Rechargeable stays** (LiPo + charger + protection + USB-C) — the deliberate difference from the disposable Omnipod.

Goal: fewer boards (ideally MAIN + a small SENSOR strip), total area that fits the free space of the concept-B pod, verified by a 3D fit check **before** routing.
