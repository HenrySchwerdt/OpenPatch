#!/usr/bin/env python3
"""Collect the figures a technical file (MDR Annex II / FDA eSTAR) needs and index where the repository
already has them. Nothing is copied (no large binaries); the index lists paths, sizes and status.

Outputs: regulatory/figures/INDEX.md and regulatory/figures/figures.json

Usage:
  python3 regulatory/tools/collect_figures.py          # regenerate the index
  python3 regulatory/tools/collect_figures.py --check  # exit 1 if a REQUIRED figure has no source and no generator recipe
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_MD = ROOT / "regulatory/figures/INDEX.md"
OUT_JSON = ROOT / "regulatory/figures/figures.json"

# id, title, used in, patterns (repo-relative globs), status if none found, how to generate
FIGS = [
    ("F01", "Device overview, isometric render per size (OP-70/100/200)", "TF 01 device description; eSTAR device description",
     ["mechanical/out/bench/OP-*_iso.png", "mechanical/out/OP-*_iso.png", "site/public/renders/hero-1200.png", "site/public/renders/top*-900.png"],
     "Re-render: `python3 mechanical/generate.py --variant bench` then the SolidCraft render step in `site/scripts/render-product.sh` (about 12 min)."),
    ("F02", "Exploded view of the assembly", "TF 01, TF 03 design and manufacturing",
     ["mechanical/out/bench/OP-*_exploded.png", "mechanical/out/OP-*_exploded.png", "site/public/renders/exploded-1000.png"],
     "SolidCraft exploded render (site/scripts/render-product.sh)."),
    ("F03", "Section views: reservoir, motor, leadscrew, cannula dock", "TF 01, TF 03",
     ["mechanical/out/bench/OP-*_section_y_*.png", "mechanical/out/bench/OP-*_section_plan_z4.2.png"],
     "`python3 mechanical/generate.py --variant bench` (writes section PNGs)."),
    ("F04", "Annotated internal layout (reservoir, motor, gear pair, boards, dock)", "TF 01, TF 03",
     ["mechanical/out/bench/OP-*_layout_annotated.png", "mechanical/out/bench/OP-*_layout_annotated.svg"],
     "`python3 mechanical/annotate.py`. NOTE: STATUS.md flags a gear-ratio mismatch in the last snapshot; regenerate after the decision."),
    ("F05", "Frozen CNC reservoir drawings (dimensioned, per size)", "TF 03 design drawings; GSPR 10 (fluid path)",
     ["mechanical/out/bench/fab/reservoir-cnc/*.pdf", "mechanical/out/bench/fab/reservoir-cnc/*.svg"],
     "`python3 mechanical/cnc_reservoir.py`."),
    ("F06", "Dock coupon / dock insert renders and fit-test geometry", "TF 03; GSPR 14 (connection / interface)",
     ["mechanical/out/bench/fab/dock-coupon/*.png", "mechanical/out/fab/dock-coupon/*.png"],
     "`python3 mechanical/op_coupon.py`."),
    ("F07", "Controller board renders (top, bottom)", "TF 03 electronics design; IEC 60601-1 construction",
     ["electronics/bench/fab/jlcpcb/controller/*.png", "electronics/fab/render/*.png"],
     "`kicad-cli pcb render` or `electronics/bench/tools/export_fab.py`."),
    ("F08", "Pod sensor board render (top, bottom)", "TF 03", ["electronics/bench/fab/jlcpcb/pod/*.png"],
     "`/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb render -o regulatory/figures/pod-top.png --side top electronics/bench/pod/pod.kicad_pcb` (pod board not built yet; see STATUS.md)."),
    ("F09", "Schematic sheets as PDF (controller, pod) incl. hardware interlock", "TF 03; IEC 60601-1 clause 15; GSPR 17",
     ["electronics/bench/fab/**/*schematic*.pdf", "electronics/schematic/*.pdf", "electronics/schematic/*.svg"],
     "`kicad-cli sch export pdf -o regulatory/figures/controller-schematic.pdf <controller>.kicad_sch` (the controller is generated from a netlist; export the schematic from the generated project)."),
    ("F10", "Fabrication outputs (Gerber archives) - listed, not copied", "TF 03 manufacturing information",
     ["electronics/bench/fab/jlcpcb/controller/*.zip", "electronics/fab/jlcpcb/*.zip", "electronics/fab/pcbway/*.zip"],
     "`electronics/bench/tools/export_fab.py`."),
    ("F11", "Board outline drawing (DXF)", "TF 03", ["electronics/board-outline.dxf", "electronics/placement-plan.svg"],
     "CADCraft (2D) from `electronics/board-outline.dxf`; export to PDF."),
    ("F12", "Simulation plots: thrust, dose accuracy, tolerance, structure, fluidics", "TF 06 verification (design-stage evidence)",
     ["mechanical/sim/plots/*.png"], "`python3 mechanical/sim/run_all.py` (2 s)."),
    ("F13", "System architecture diagram (phone, pod, cannula)", "TF 01 device description; eSTAR",
     ["docs/01-architecture.md"],
     "The diagram is a Mermaid block in `docs/01-architecture.md` (text only). Render: `npx -y @mermaid-js/mermaid-cli -i <extracted.mmd> -o regulatory/figures/system-architecture.svg`."),
    ("F14", "Hardware interlock block diagram (MCU_EN AND watchdog latch AND (DOCKED OR DIR_REV))", "TF 03; RISK; GSPR 17, 23",
     ["docs/02-safety.md", "docs/v010/ARCHITECTURE.md"],
     "Text/Mermaid only today (docs/v010/ARCHITECTURE.md 7.1). Render as for F13; draw the final one from the electronics INTERLOCK document."),
    ("F15", "Firmware task / ownership diagram (safety task vs BLE task)", "SOFTWARE architecture (IEC 62304 5.3)",
     ["firmware-rs/docs/architecture.md"], "ASCII diagram in the document; redraw as SVG for the submission."),
    ("F16", "Pod and pair state diagram (suspended, active, released, faulted; two-pod handover)", "SOFTWARE, USABILITY, RISK",
     [], "To be generated from `firmware-rs/openpatch-core/src/pod.rs` and `ios/.../PairSwapCoordinator.swift` (state enums); draw with Mermaid `stateDiagram-v2`."),
    ("F17", "Dimensioned engineering drawings of housing parts (2D, DWG/PDF)", "TF 03 design drawings (Annex II 3)",
     [], "SolidCraft drawing export (`solidcraft-cli` drawing view of `mechanical/out/bench/fab/OP-100/*.step`) then CADCraft for dimensions; or `python3 mechanical/fab.py` extended. Not generated yet."),
    ("F18", "Labelling artwork: device label, symbols per ISO 15223-1, UDI carrier", "TF 02 labelling; MDR Annex I chapter III",
     [], "Legal manufacturer: label content and UDI are manufacturer-specific. Structure only in TECHNICAL-FILE/02-labelling-and-ifu.md."),
    ("F19", "Traceability matrix (hazard to verification)", "RISK; eSTAR traceability special control (880.5730)",
     ["regulatory/RISK/TRACE.md"], "`python3 regulatory/tools/trace.py --report regulatory/RISK/TRACE.md`."),
    ("F20", "Website product renders (marketing quality, not for the file)", "reference only", ["site/public/renders/*.png"],
     "Not suitable as regulatory drawings (not dimensioned); useful for the device description."),
]

REQUIRED = {"F01", "F02", "F03", "F05", "F07", "F09", "F14", "F17", "F18"}


def human(n: int) -> str:
    for u in ("B", "kB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def scan():
    res = []
    for fid, title, used, pats, how in FIGS:
        files = []
        for pat in pats:
            for p in sorted(ROOT.glob(pat)):
                if p.is_file() and p not in [f[0] for f in files]:
                    files.append((p, p.stat().st_size))
        # F13/F14 point to documents that contain the diagram: only 'present' when a rendered figure exists
        text_only = fid in ("F13", "F14", "F15")
        if files and not text_only:
            status = "present"
        elif files:
            status = "text only (render needed)"
        else:
            status = "missing"
        res.append({"id": fid, "title": title, "used_in": used, "status": status, "how": how,
                    "required": fid in REQUIRED,
                    "files": [{"path": str(p.relative_to(ROOT)), "bytes": s} for p, s in files]})
    return res


def render(res) -> str:
    o = ["# Figure index (generated)\n",
         "> GENERATED by `python3 regulatory/tools/collect_figures.py`. Nothing is copied; paths point into the repository. Do not edit by hand.",
         "> Test project, not a medical device.\n",
         "Figures are listed by the technical-file section that needs them (MDR Annex II, FDA eSTAR). Status: **present** (generated output exists), "
         "**text only** (the diagram exists as text in a document and must be rendered), **missing** (generator recipe given). "
         "Generated renders in `mechanical/out` are design snapshots, not controlled drawings: a legal manufacturer re-generates them under document control for each release.\n",
         "## Status\n", "| ID | Figure | Status | Required for first submission | Files |", "|---|---|---|---|---|"]
    for r in res:
        o.append(f"| {r['id']} | {r['title']} | {r['status']} | {'yes' if r['required'] else 'no'} | {len(r['files'])} |")
    for r in res:
        o.append(f"\n## {r['id']} {r['title']}\n")
        o.append(f"- Used in: {r['used_in']}\n- Status: **{r['status']}**\n- How to generate / update: {r['how']}")
        if r["files"]:
            o.append("- Files:")
            shown = r["files"][:14]
            for f in shown:
                o.append(f"  - `{f['path']}` ({human(f['bytes'])})")
            if len(r["files"]) > len(shown):
                o.append(f"  - ... and {len(r['files']) - len(shown)} more")
    o.append("")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    res = scan()
    n_present = sum(1 for r in res if r["status"] == "present")
    n_text = sum(1 for r in res if r["status"].startswith("text"))
    n_miss = sum(1 for r in res if r["status"] == "missing")
    print(f"{len(res)} figure slots: {n_present} present, {n_text} text-only, {n_miss} missing")
    for r in res:
        if r["required"] and r["status"] != "present":
            print(f"  required {r['id']} {r['status']}: {r['title']}")
    if a.check:
        bad = [r for r in res if not r["how"]]
        return 1 if bad else 0
    OUT_MD.write_text(render(res), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", OUT_MD.relative_to(ROOT), "and", OUT_JSON.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
