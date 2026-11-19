# 08 Required figures and where they come from

> Generated index: `../figures/INDEX.md` (`python3 regulatory/tools/collect_figures.py`). Nothing is copied; paths point into the repository.

| ID | Figure | Technical-file use | State (2026-11-19) | How to produce what is missing |
|---|---|---|---|---|
| F01 | isometric renders OP-70/100/200 | 01 | present (`mechanical/out/bench/*_iso.png`, `site/public/renders`) | SolidCraft render step |
| F02 | exploded view | 01, 03 | present | same |
| F03 | sections (reservoir, motor, screw, cannula, plan z 4.2) | 01, 03 | present | `mechanical/generate.py --variant bench` |
| F04 | annotated layout | 01, 03 | present, **gear-ratio snapshot mismatch flagged in STATUS.md** | `mechanical/annotate.py` after the gear decision |
| F05 | CNC reservoir drawings | 03 | present (PDF/SVG/PNG per size) | `mechanical/cnc_reservoir.py` |
| F06 | dock coupon / insert renders | 03 | present | `mechanical/op_coupon.py` |
| F07 | controller board renders | 03 | present | `kicad-cli pcb render` |
| F08 | pod sensor board renders | 03 | **missing** (pod board not built) | `kicad-cli pcb render` on `electronics/bench/pod/pod.kicad_pcb` after the final layout |
| F09 | schematic PDFs incl. interlock | 03, GSPR 17 | **missing** | `kicad-cli sch export pdf` |
| F10 | Gerber archives | 03 | present (listed only) | `electronics/bench/tools/export_fab.py` |
| F11 | board outline DXF | 03 | present | CADCraft export |
| F12 | simulation plots | 06 | present | `mechanical/sim/run_all.py` |
| F13 | system architecture diagram | 01 | **text only** (Mermaid in `docs/01-architecture.md`) | render with mermaid-cli |
| F14 | interlock block diagram | 03, RISK | **text only** | render from `docs/v010/ARCHITECTURE.md` 7.1 |
| F15 | firmware task diagram | SOFTWARE | **text only** | redraw `firmware-rs/docs/architecture.md` |
| F16 | pod / pair state diagram | SOFTWARE, USABILITY | **missing** | Mermaid `stateDiagram-v2` from `pod.rs` and `PairSwapCoordinator.swift` |
| F17 | dimensioned 2D drawings of parts | 03 | **missing** | SolidCraft drawing export, CADCraft dimensions |
| F18 | label artwork, symbols, UDI | 02 | **missing** (manufacturer) | legal manufacturer |
| F19 | traceability matrix | RISK | present after running `trace.py` | `trace.py --report` |
| F20 | website renders | reference only | present | |

Figure control: generated renders are snapshots; a manufacturer re-generates them under document control for each release (`../LIVING-PROCESS.md`).
