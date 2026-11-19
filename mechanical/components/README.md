# OpenPatch vendor-accurate component library

TEST PROJECT, WATER ONLY (never insulin), never worn or used on a person (see `DISCLAIMER.md`). This library replaces envelope boxes with
models of the real bought-in parts so assemblies, renders and the website show the pump that is actually built.

* One generator per part family (`gen_*.py`), each emitting SolidCraft command JSON through `mechanical/op_cmds.py` (`Script`, imported, not modified).
* `python3 build_all.py [--only id,id] [--force] [--no-boards]` builds everything into `out/` and rewrites `catalog.json`.
  A part whose script is unchanged is only re-measured, not rebuilt (the modelled threads take about 3 min per rod).
* Outputs per part in `out/`: `<id>.step`, `.stl`, `.glb` (glTF binary, metres, Y up, PBR colours per body), `.png` (iso render), `.script.json` (replayable command list).
* `catalog.json`: id -> files, bounding box, mass estimate (volume x material density), material, colour per body, local frame, source, confidence, used_for. The assembly generator and the website read this.
* Needs SolidCraft CLI (`SOLIDCRAFT_CLI`, default `/usr/local/bin/solidcraft-cli`) and, for the boards, KiCad 10 with its stock 3D libraries (`apt install kicad-packages3d`, `KICAD10_3DMODEL_DIR`).

Confidence levels: **datasheet** (number read from a vendor drawing, catalogue table or standard), **estimated**
(derived from related data or a library model; listed with what to measure), **placeholder** (shape invented, part not
yet sourced). "TODO-measure" = verify with calipers on the sample order (`docs/PARTS-LOCK.md`).

Colours in renders are flat-shaded base colours; the metallic/roughness values travel in the glTF only.
glTF export refuses translucent bodies, so translucent parts (silicone, dome, FFC) are translucent in the PNG and opaque pale in glTF/STEP.

## Parts

Local frames are listed in `catalog.json` (`frame`) and in each script header. Units mm.

### 1. NFP-608-26.45-SGM geared stepper (`gen_motor.py`, `nfp_608_26_45`), confidence datasheet (outline), estimated (terminals)

Source: nfpshop.com outline drawing `stepper-gear-motor-spec-NFP-608-26.45-SGM.pdf` as transcribed in `mechanical/parts.md` 1.0 and `params.json drive_presets.nfp_608_26` (the drawing PDF itself is not in the repo).

| number | value | source |
|---|---|---|
| body diameter | 6.0 | drawing, d6 +-0.1 |
| gearbox / motor length | 8.1 / 8.0 | drawing (8.1 +-0.1, 8.0 +-0.1). parts.md says "total 15.1" but 8.1 + 8.0 = 16.1: model uses the sub-dimensions, **TODO-measure total** |
| front boss | d3.5 x 0.8 | drawing |
| shaft | d2.0 with D-flat to 1.5 across, flat length 2.5, free length 5.3 beyond the boss (tip at 6.1 from the face) | drawing (11.7 from flat start to the gearbox/motor junction gives the flat start at 3.6 from the face); free length derived, **TODO-measure** |
| rear boss | d2.6 x 0.7 | d2.6 drawing, length assumed |
| terminal block / pins | block 4.6 x 3.4 x 0.65 on the -Y side 11.0 behind the face, 4 pins 0.3 square, 1.2 pitch, 1.05 long | pin pitch and 11.0 drawing; block and pin size derived (parts.md), **TODO-measure** |
| lead | not in this model; see `lead_picoblade_plug` | product page: lead + JST 1.25 plug, drawing: 4 solder pins (conflict recorded in `motor-selection.md`) |

### 2. GHW-Modellbau brass spur gears, module 0.3 (`gen_gear.py`), confidence datasheet (catalogue table), tooth profile computed

Source: <https://ghw-modellbau.de/Spur-gear-Brass-Module-03-10-120-T> (table read 2026-11-19): da = m (z + 2), d = m z; brass Ms58.
Tooth form: 20 deg involute, root radius = pitch radius - 1.25 m (GHW publishes no profile: **TODO-measure** tip/root rounding). Parametric: `spur_gear(pid, title, m, z, bore, width, hub_d, hub_l)`.

| id | article | z | bore | OD da | width | hub (d x length) |
|---|---|---|---|---|---|---|
| `gear_m03_z15_753015` | 753015 | 15 | 2.0 | 5.1 | 1.4 | 4.0 x 2.5 |
| `gear_m03_z12_753012` | 753012 | 12 | 1.5 | 4.2 | 4.0 | none |
| `gear_m03_z16_390754` | 390754 | 16 | 2.0 | 5.4 | 5.0 | none |
| `gear_m03_z20_753020` | 753020 | 20 | 2.0 | 6.6 | 1.4 | 4.0 x 2.5 |
| `gear_m03_z18_390755` | 390755 | 18 | 2.0 | 6.0 | 5.0 | none |

Open point: GHW lists "hub length 2.5" next to "width 1.4"; the model puts the hub **beyond** the tooth width (total 3.9). Verify on the sample.
The 18 T gear is only sold at width 5 (the 18:18 option in `parts.md` needs it turned to 1.2-2 mm; no thin z18 article was found).
**Final pair (mechanical owner): 16 T on the motor (390754) -> 20 T on the screw (753020)**, nominal centre 0.3 x 36 / 2 = 5.40, built centre 5.51 mm (clearance). Other options kept: 15:12 = 4.05, 18:18 = 5.40.

### 3. Fastener set (`gen_fasteners.py`)

| id | geometry | source | confidence |
|---|---|---|---|
| `rod_m1p6_19/22/37` | d1.6 rod, **modelled helical thread** M1.6x0.35 (SolidCraft `solid.thread`, ISO profile, chamfered ends), cut lengths 19/22/37 for OP-70/100/200 | ISO 261/965 coarse pitch; PARTS-LOCK #4 | datasheet (standard) |
| `nut_din934_m1p6_brass` | AF 3.2, m 1.3, e 3.41, 30 deg corner chamfer (0.28 x 0.16 est.), bore 1.3 (about thread minor; no internal helix) | DIN 934 / ISO 4032 table; PARTS-LOCK #5 | datasheet (standard) |
| `screw_iso7045_m1p2x3/x4` | M1.2x0.25 modelled thread, pan head d2.4 x 0.9 with fillet, simplified cross recess | ISO 7045 starts at M1.6 (dk 3.2, k 1.3); M1.2 head dims estimated from vendor listings, **TODO-measure** | estimated |

### 4. NdFeB magnets (`gen_magnet.py`), colouring N red / S blue

`magnet_d2x1_diametric` (spindle, PARTS-LOCK #7), `magnet_d2x1_axial` (dock, #8), `magnet_d3x1p5_diametric` (**final spindle magnet**, d3 x 1.5, mechanical owner decision), `magnet_d4x1_diametric` (option, thickness assumed).
Dimensions: `params.json drive.mag_d/mag_t`, `parts.md` 1.5. Two half-bodies per magnet for the pole marker.

### 5-7. Fluid path (`gen_fluid.py`)

| id | numbers | source | confidence |
|---|---|---|---|
| `needle_30g_efd_14in` | needle OD 0.31, ID 0.15, length 6.35 (1/4 in); lavender PP luer-lock hub: nose cone d1.6-4.2 x 2.8, body d6.4 x 4.4, lock ears d8.0 x 0.9 with 6.6 flats | Nordson EFD "General Purpose Dispense Tips" catalogue: gauge 30, lavender, 0.15 / 0.31 mm, stainless, polypropylene SafetyLok hub (part 7018424, 1/4 in). Hub dimensions not published | needle datasheet, hub **estimated** |
| `duckbill_valve_generic` | OD 3.0 sleeve (ID 2.0 x 2.0 long), two bills 2.2 long closing to a 0.08 slit | only "OD <= 3 mm, cracking 1-5 kPa" from PARTS-LOCK #16 | **placeholder** (no sourced part) |
| `septum_d4x2` | d4.0 x 2.0 punched silicone disc | `params.json septum`; PARTS-LOCK #18 | datasheet (spec size) |

### 8-9. Electronics (`gen_ic.py`)

| id | package numbers | source |
|---|---|---|
| `ebyte_e73_2g4m08s1c` | 13.0 x 18.0 x 2.2 module, 43 castellated pads (positions from `electronics/bench/footprints/.../Ebyte_E73-2G4M08S1C_13x18.kicad_mod`), pad pitch 1.27; **estimated:** PCB 0.8 thick, shield can 12.2 x 12.6, ceramic chip antenna 3.2 x 1.6 x 1.0 at the -Y end | Ebyte E73-2G4M08S1C data sheet (outline); can and antenna **TODO-measure** |
| `ic_tmag5273_sot23_6` | body 2.9 x 1.6, height 1.45 max, pitch 0.95, lead span 2.8 | TI TMAG5273 DS (DBV0006A); `params.json bench.tmag.pkg` |
| `ic_tpl5010_sot23_6` | SOT-23-THIN-6 (DDC), 2.9 x 1.6, height 1.1 | TI TPL5010 DS |
| `ic_drv5032_x2son` / `ic_drv5032_sot23` | X2SON-4 (DMR0004B) 1.1 x 1.4 x 0.4; SOT-23-3 (DBZ) 2.9 x 1.3 x 1.1, pitch 0.95, span 2.4 | TI DRV5032 DS; X2SON pad centres from the project footprint |
| `ic_stspin220_vfqfpn16` | 3 x 3 x 1.0, pitch 0.5, pad 0.25 x 0.4, EP 1.7 x 1.7 | ST STSPIN220 DS (VFQFPN 3x3x1.0 16L) |
| `c_0402_100nf`, `r_0402`, `c_0603_10uf`, `r_0603` | 1.0 x 0.5 x 0.5/0.35 (term. 0.25); 1.6 x 0.8 x 0.8/0.45 (term. 0.35) | EIA 0402/0603 typical |

Gull-wing lead profiles are simplified (flat foot, straight riser).

### 9b. Boards with components (`gen_boards.py`)

`kicad-cli pcb export step` of `electronics/bench/pod/pod.kicad_pcb` and `electronics/bench/controller/controller.kicad_pcb`
(flags: `--subst-models --include-tracks --include-pads --include-soldermask`, plus silkscreen on the pod; the STEP is re-exported
to glTF/STL with an opaque soldermask because glTF refuses translucent bodies). Result and the list of footprints without a 3D model:
`out/boards/boards.models.json` (also in `catalog.json`).

* pod board: 5 of 11 footprints have models; **missing:** DRV5032 X2SON-4 (use `ic_drv5032_x2son`), 3 NPTH holes (not parts).
* controller: 86 of 125 have models; **no model assigned:** E73 module (use `ebyte_e73_2g4m08s1c`), buzzer MLT-8530, Tag-Connect TC2030, M3 mounting holes, test pads; **model file not in KiCad 10 stock lib:** TS-1187A switch, HRO TYPE-C-31-M-12 USB-C.
* Board coordinates are KiCad's (board at x ~ 100 mm). The controller STEP is 8 MB and the glTF 14 MB; STL is skipped (would be 180 MB). These large files are git-ignored (`out/.gitignore`), regenerate with `python3 gen_boards.py`.

### 10. Connectors and cables (`gen_connectors.py`)

| id | numbers | source | confidence |
|---|---|---|---|
| `hirose_fh12_10s_0p5sh` | B 8.1, C 9.1 (with tabs), **height 2.0**, pitch 0.5, slot 6.1 x 0.34, 10 tails | Hirose FH12 catalogue table (0.5 mm bottom contact, 10 pos: A 4.5, B 8.1, C 9.1, D 5.57) and "standard type connector height 2 mm"; pad geometry from KiCad footprint | datasheet (B, C, H), estimated (slot, lever) |
| `ffc_05mm_10p_same_side` | 6.0 wide, 0.30 thick, 10 x 0.3 conductors at 0.5, stiffened contact ends 3.5, same side | Hirose FPC spec t = 0.30 +-0.05; `params.json bench.ffc.cable_w` | estimated |
| `molex_picoblade_53261_0471` | housing 6.68 x 4.13 x 3.4, pitch 1.25, solder tabs to +-5.08, tails to y = +2.6 | read off the KiCad stock footprint/3D model of this Molex part; **Molex drawing not read** (molex.com timed out) | estimated |
| `lead_picoblade_plug` | plug 5.6 x 3.6 x 2.0, 4 x 30 AWG (OD 0.45), 30 mm shown (product page: 200 mm) | nfpshop product page; plug size estimated | estimated |

**Conflict to resolve:** the FH12 is 2.0 mm tall; `params.json bench.ffc.conn` uses 1.0 and spec section 4a asks for <= 1.2 mm. Either the pod stack takes 2.0 mm or a lower ZIF (for example a 0.3 pitch FH35C / FPC with 1.0 mm height) is chosen.

### 11. Li-Po with PCM (`gen_battery_cannula.py`, `battery_lipo_3x12x20`), placeholder

3.0 x 12 x 20 mm pouch + seal + Ni tabs + PCM board with two ICs, from the task brief (docs/v010 size class, about 40 mAh). Not a sourced cell.
Note it does not fit the Rev A pocket in `params.json battery` (3.2 x 11.2 x 19.8 max; width 12 > 11.2).

### 12. Accu-Chek Insight Flex cannula head dummy (`cannula_head_dummy`), placeholder

Dome d10.0, height 5.0, septum axis 3.0 above the patch, recess d3.6 x 1.0, patch 11 x 11 x 0.6 with 2.5 corner radius: all **assumed**, copied from `mechanical/cannula-measurement.md` / `params.json cannula` (TODO-measure; Roche publishes no drawing).
No soft cannula or introducer needle is modelled, and the latch notch (G, H, I) is not modelled yet.

## Rebuilding / extending

1. Add a `build()` returning `Part`s and a `META` dict (title, material, colour, frame, source, confidence, notes) to a `gen_*.py`; list it in `build_all.py` `MODULES`.
2. `python3 build_all.py --only <id> --force`.
3. Update the table above with the source of every new number.

## Decisions applied from the mechanical owner

Pod board: 0.6 mm 2-layer with Hirose FH12-10S-0.5SH(55). The board STEP in `out/boards/` was exported from the current `pod.kicad_pcb` (1.5 mm stack in that file): re-run `python3 gen_boards.py` after the board file is updated.
