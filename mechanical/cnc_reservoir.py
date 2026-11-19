#!/usr/bin/env python3
"""Frozen CNC polypropylene reservoir package: out/bench/fab/reservoir-cnc/  (STEP + 2D drawing PDF/SVG per size + README).

  python3 cnc_reservoir.py            # after generate.py --variant bench (uses out/bench/OP-xx.mech.json)
The part is the 'reservoir' body of the bench CAD: blind stadium bore from the open dry end, ONE d2.0 H7 port in the closed end,
the carriage-arm slot in the +Y wall.  No septum, valve, dock or fill features (they are on the end cap).
"""
from __future__ import annotations

import html
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "bench"
DST = OUT / "fab" / "reservoir-cnc"
S = 14.0


def svg_drawing(variant: str, p: dict, L: dict) -> str:
    fz, rs = p["reservoir_frozen"], p["reservoir"]
    x0 = L["x_r0"]
    length = L["res_len"]
    bore_depth = L["x_in1"] - x0
    ow, oh = L["res_w_out"], L["res_h_out"]
    slot_x0 = L["xrear_full"] + p["seal"]["tongue_off"][0] - 0.2 - x0
    slot_x1 = L["xrear_empty"] + p["seal"]["tongue_off"][1] + 0.2 - x0
    slot_h = p["drive"]["arm_t"] + 2 * p["drive"]["slot_clr"]
    X0, Y0 = 130.0, 90.0
    els: list[str] = []

    def rect(x, y, w, h, fill="none", stroke="#000", sw=1.2, rx=0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def line(x0_, y0_, x1_, y1_, stroke="#000", sw=0.8, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<line x1="{x0_:.1f}" y1="{y0_:.1f}" x2="{x1_:.1f}" y2="{y1_:.1f}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(x, y, t, size=11, anchor="start", weight="normal", fill="#000"):
        els.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{html.escape(t, quote=False)}</text>')

    def hdim(xa, xb, y, label, off=18):
        line(xa, y, xa, y + off + 4, "#06c", 0.5)
        line(xb, y, xb, y + off + 4, "#06c", 0.5)
        line(xa, y + off, xb, y + off, "#06c", 0.8)
        text((xa + xb) / 2, y + off - 3, label, 11, "middle", fill="#06c")

    def vdim(x, ya, yb, label, off=-18):
        line(x, ya, x + off - 4, ya, "#06c", 0.5)
        line(x, yb, x + off - 4, yb, "#06c", 0.5)
        line(x + off, ya, x + off, yb, "#06c", 0.8)
        text(x + off - 4, (ya + yb) / 2, label, 11, "end", fill="#06c")

    # ---- view 1: longitudinal section (X horizontal, Z vertical) -------------------------------------------
    sx, sy = X0, Y0 + 40
    Lw, Hh = length * S, oh * S
    rect(sx, sy, Lw, Hh, "#e8eef4")
    ib = (oh - rs["h_in"]) / 2 * S
    rect(sx - 0.0, sy + ib, bore_depth * S, rs["h_in"] * S, "#ffffff", dash="5,3")        # blind bore
    pz = sy + Hh / 2
    line(sx + bore_depth * S, pz - fz["port_d"] / 2 * S, sx + Lw, pz - fz["port_d"] / 2 * S, "#000", 1.2)
    line(sx + bore_depth * S, pz + fz["port_d"] / 2 * S, sx + Lw, pz + fz["port_d"] / 2 * S, "#000", 1.2)
    line(sx - 10, pz, sx + Lw + 10, pz, "#a00", 0.6, "10,3,2,3")
    text(sx, sy - 22, "SECTION B-B  (longitudinal, plane y = bore centre)", 13, weight="bold")
    hdim(sx, sx + Lw, sy + Hh, f"{length:.2f} +-0.1 overall", 22)
    hdim(sx, sx + bore_depth * S, sy + Hh, f"{bore_depth:.2f} bore depth (blind, +0.1/0)", 48)
    hdim(sx + bore_depth * S, sx + Lw, sy, f"{fz['end_wall']:.1f} end wall", -16)
    text(sx + bore_depth * S + 4, pz + 22, f"port d{fz['port_d']:.1f} {fz['port_tol'].split()[0]}, chamfer {fz['port_chamfer']}x45", 10)
    text(sx + 4, sy + ib + 14, "stadium bore 16.00 x 5.00, open dry end (datum A)", 10)
    vdim(sx, sy, sy + Hh, f"{oh:.1f}", -18)
    vdim(sx + 0, sy + ib, sy + ib + rs["h_in"] * S, f"{rs['h_in']:.2f}", -50)

    # ---- view 2: top view with arm slot -----------------------------------------------------------------------
    ty = sy + Hh + 110
    rect(sx, ty, Lw, ow * S * 0.0 + 17.6 * S * 0.5, "#e8eef4", rx=0)
    els.pop()
    wpx = ow * S
    rect(sx, ty, Lw, wpx, "#e8eef4", rx=3.3 * S)
    rect(sx + slot_x0 * S, ty - 3, (slot_x1 - slot_x0) * S, 10, "#ffffff", "#c00", 1.0)
    text(sx, ty - 22, "TOP VIEW (slot in the +Y end wall; arm slot height %.2f, centred on the bore axis)" % slot_h, 13, weight="bold")
    hdim(sx + slot_x0 * S, sx + slot_x1 * S, ty + wpx, f"slot {slot_x0:.2f} .. {slot_x1:.2f}  (width {slot_h:.2f} +0.1/0)", 22)

    # ---- view 3: end view (stadium cross-section) ---------------------------------------------------------------
    cx, cy = sx + Lw + 230, sy + 60
    wo, ho, wi, hi = ow * S, oh * S, fz["bore_w"] * S, fz["bore_h"] * S
    rect(cx - wo / 2, cy - ho / 2, wo, ho, "#e8eef4", rx=ho / 2)
    rect(cx - wi / 2, cy - hi / 2, wi, hi, "#ffffff", rx=hi / 2)
    els.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{fz["port_d"]/2*S:.1f}" fill="none" stroke="#000" stroke-width="1.2" stroke-dasharray="3,2"/>')
    line(cx - wo / 2 - 12, cy, cx + wo / 2 + 12, cy, "#a00", 0.6, "10,3,2,3")
    text(cx, cy - ho / 2 - 30, "VIEW A (from the open end)", 13, "middle", "bold")
    hdim(cx - wo / 2, cx + wo / 2, cy + ho / 2, f"{ow:.1f} +-0.1", 22)
    hdim(cx - wi / 2, cx + wi / 2, cy + ho / 2, "16.00 +0.05/0", 50)
    vdim(cx - wo / 2, cy - ho / 2, cy + ho / 2, f"{oh:.1f}", -18)
    vdim(cx + wo / 2, cy - hi / 2, cy + hi / 2, "5.00 +0.05/0", 60)
    text(cx, cy + ho / 2 + 85, "bore end radii R2.50 = d5 end mill; outer end radii R3.30", 10, "middle")

    # ---- title block + notes --------------------------------------------------------------------------------------
    tb_y = ty + wpx + 80
    reach = bore_depth + fz["tool_extra_flute"]
    rows = [
        ("Part", f"OP-RES-{variant[3:]}  reservoir, CNC, ONE piece (frozen interface)"),
        ("Material", fz["material"]),
        ("Qty", f"{fz['qty']} pcs (one order per size)"),
        ("General tolerance", "ISO 2768-m; marked dimensions as shown"),
        ("Bore 16.00 x 5.00", f"+{fz['bore_tol_plus']}/-{fz['bore_tol_minus']} mm, length {bore_depth:.1f} mm, Ra <= {fz['Ra_bore_um']} um (finishing pass, no polishing compounds)"),
        ("Port", f"d{fz['port_d']:.1f} {fz['port_tol']}, centred on the closed end face, chamfer {fz['port_chamfer']} x 45 deg, Ra <= 1.6 um"),
        ("Other surfaces", f"Ra <= {fz['Ra_other_um']} um; break all edges 0.1-0.2; no burrs inside the bore and slot"),
        ("Datums", fz["datums"]),
        ("Tooling", f"d5.0 end mill, required flute (cut) length >= {reach:.1f} mm for bore depth {bore_depth:.1f} mm (L/D {bore_depth/5:.1f})"),
        ("Cleaning", "ultrasonic clean in IPA / water, no cutting-oil residue, pack in a clean bag"),
        ("Use", "water or insulin into containers on a bench ONLY; not a medical device, never connected to a person"),
    ]
    text(70, tb_y - 12, f"OpenPatch {variant} reservoir - CNC drawing (mm, 1st angle not applicable: sections as drawn)", 14, weight="bold")
    for i, (a, b) in enumerate(rows):
        yy = tb_y + 18 * i
        line(70, yy + 4, 70 + 1180, yy + 4, "#999", 0.4)
        text(74, yy + 16, a, 11, weight="bold")
        text(260, yy + 16, b, 11)
    height = int(tb_y + 18 * len(rows) + 30)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="{height}" viewBox="0 0 1320 {height}" font-family="Helvetica,Arial,sans-serif">'
            '<rect width="100%" height="100%" fill="#fff"/>' + "\n".join(els) + "</svg>")


def main() -> None:
    p = json.loads((OUT / "params.used.json").read_text())
    DST.mkdir(parents=True, exist_ok=True)
    info = []
    for v in p["variants"]:
        L = json.loads((OUT / f"{v}.mech.json").read_text())
        shutil.copy(OUT / f"{v}_reservoir.step", DST / f"{v}_reservoir_cnc.step")
        svg = DST / f"{v}_reservoir_cnc_drawing.svg"
        svg.write_text(svg_drawing(v, p, L), encoding="utf-8")
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", str(svg.with_suffix(".pdf")), str(svg)], check=True)
        subprocess.run(["rsvg-convert", "-b", "white", "-o", str(svg.with_suffix(".png")), str(svg)], check=True)
        bd = L["x_in1"] - L["x_r0"]
        info.append((v, p["variants"][v]["stroke"], L["res_len"], bd, bd + p["reservoir_frozen"]["tool_extra_flute"]))
    fz = p["reservoir_frozen"]
    rows = "\n".join(f"| {v} | {int(round(s*74.63/10 / 1))} U ({s} mm stroke) | {rl:.2f} | {bd:.2f} | {bd/5:.1f} x D | {fl:.1f} |" for v, s, rl, bd, fl in info)
    (DST / "README.md").write_text(f"""# CNC polypropylene reservoir (frozen interface) - PCBWay CNC package

BENCH TEST PART: water or insulin into containers (vial on a balance) only; not a medical device; never connected to a person.
Per size: `OP-xx_reservoir_cnc.step` (master), `OP-xx_reservoir_cnc_drawing.pdf` (+ `.svg`, `.png`). Order **once per size, qty {fz['qty']}** (spare).

## What the part is (and is not)
One piece of PP: stadium bore {fz['bore_w']:.2f} x {fz['bore_h']:.2f} (+{fz['bore_tol_plus']}/-{fz['bore_tol_minus']}), blind from the open dry end, closed end wall {fz['end_wall']} mm with ONE port d{fz['port_d']} {fz['port_tol']}
(centre of the end face), carriage-arm slot through the +Y wall. **No** septum, valve, needle or dock features: these are on the separate end cap (`end_cap`, SLA now, PP later), which presses onto the port
with a d1.98 spigot. Outer {fz['outer_w']} x {fz['outer_h']}, wall {fz['wall']}.

## Frozen numbers (`params.json -> reservoir_frozen`, do not change after the order)
bore 16.00 x 5.00 (R2.50 ends), tolerance +0.05/-0; outer 17.6 x 6.6 +-0.1 (R3.3 ends); wall 0.8; closed end wall 2.5; port d2.0 H7 at the centre of the closed end face; Ra bore <= 0.8 um;
length per size below (+-0.1); arm slot height {p['drive']['arm_t'] + 2*p['drive']['slot_clr']:.2f} on the bore axis; datums A open end face, B bottom flat, C bore centre plane.

| size | volume | overall length | bore depth | depth / d5 | min. flute (cut) length [mm] |
|---|---|---|---|---|---|
{rows}

## Machinability (Ø5 end mill)
* 70 U and 100 U: depth 15 / 19 mm = 3.0 / 3.8 x D: standard long-flute d5 carbide end mills (flute 20 mm) are enough; PP is soft, one roughing + one finishing pass (0.1 mm stock), climb milling.
* 200 U: depth about 33 mm = 6.5 x D: needs a long-reach d5 (reduced-neck, flute >= 34 mm); PCBWay may decline > 5 x D. **Lowest-risk fallback for 200 U (decide before ordering):** order the 200 U as a through
  bore (open both ends, machinable from both sides, 16.5 mm per side = 3.3 x D) with a separate PP closing plug (stadium plug with the d2.0 port, pressed + bonded) - this changes only the closed end,
  every frozen outer/bore/port dimension stays. Ask PCBWay support to confirm the blind 6.5 x D before paying; if they refuse use the fallback. 70/100 U stay blind (no risk).
* Wall 0.8 mm in PP: clamp on the outside flats with soft jaws, do not squeeze the 0.8 mm walls (fixture on the full-length side flats).
* Bore finish: Ra 0.8 um is the limit of a finishing end-mill pass in PP; no vapour polishing; a stamped/pulled bore would be better but is out of scope.

## PCBWay order form (exact settings; the form changes, VERIFY on the live page)
* Service: **CNC Machining** (3-axis is enough). Upload `OP-xx_reservoir_cnc.step` and attach the PDF drawing.
* Material: **Plastic -> Polypropylene (PP)**, colour natural/white. If a medical/USP Class VI grade is offered select it, otherwise standard PP-H and say so in the remarks (bench only).
* Quantity: **{fz['qty']}**.  Surface finish: **As machined** (Ra 1.6); remark: "bore Ra <= 0.8 um, no polishing compound".
* Tolerance: **Standard (ISO 2768-m)**; critical: bore 16.00 +0.05/-0 and 5.00 +0.05/-0, port d2.0 H7 (use the drawing).
* Remarks: "blind stadium pocket d5 end mill R2.5 corners, deburr, no burrs in the bore, clean without oil residue, see drawing; check feasibility of depth/d5 (OP-200: 6.5 x D)".
* Threads: none. Inspection report: optional (bore size), not required for 2 pcs.

## Seals
Plunger lip seals are cast from **platinum-cure medical silicone** (Shore A 40-50, e.g. a 2-part LSR/RTV marked ISO 10993 / USP VI; SEARCH-TERM "platinum cure silicone USP class VI Shore 40") in the mould of this folder's sibling `mould/`.
Alternative for a first insulin test: a **bromobutyl** plunger stopper from an insulin cartridge/vial cut to the stadium shape (the stadium bore does not accept a standard round O-ring; a round O-ring variant would
need a circular bore). VERIFY material compatibility with the insulin used; platinum-cure silicone is common in insulin infusion sets but silicone oil lubrication can aggregate some insulins.
""", encoding="utf-8")
    print(f"reservoir-cnc written: {DST}")


if __name__ == "__main__":
    main()
