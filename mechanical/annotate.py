#!/usr/bin/env python3
"""Annotated top view (SVG + PNG) of the bench pod from out/bench/OP-xx.mech.json / .layout.json.

  python3 annotate.py [OP-100 ...]      -> out/bench/OP-xx_layout_annotated.svg / .png  (PNG needs rsvg-convert)
Schematic (to scale, simplified shapes): X to the right, Y up, skin side below the paper plane.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "bench"
S = 16.0           # px per mm
M = 60             # margin px


def draw(variant: str) -> Path:
    L = json.loads((OUT / f"{variant}.mech.json").read_text())
    LJ = json.loads((OUT / f"{variant}.layout.json").read_text())
    p = json.loads((OUT / "params.used.json").read_text())
    W, Ln = L["width"], L["length"]
    px = lambda x: M + x * S
    py = lambda y: M + (W - y) * S
    els: list[str] = []
    labels: list[tuple[float, float, str, float, float]] = []

    def rect(x0, y0, x1, y1, fill, stroke="#333", op=1.0, dash=None, r=0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<rect x="{px(x0):.1f}" y="{py(y1):.1f}" width="{(x1-x0)*S:.1f}" height="{(y1-y0)*S:.1f}" rx="{r*S:.1f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"{d}/>')

    def circ(cx, cy, r, fill, stroke="#333", op=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<circle cx="{px(cx):.1f}" cy="{py(cy):.1f}" r="{r*S:.1f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"{d}/>')

    def line(x0, y0, x1, y1, stroke="#333", w=1.5, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<line x1="{px(x0):.1f}" y1="{py(y0):.1f}" x2="{px(x1):.1f}" y2="{py(y1):.1f}" stroke="{stroke}" stroke-width="{w}"{d}/>')

    def poly(pts, fill, stroke="#333", op=1.0):
        s = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pts)
        els.append(f'<polygon points="{s}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"/>')

    def label(x, y, text, tx, ty):
        labels.append((x, y, text, tx, ty))

    # housing, reservoir, lanes
    rect(0, 0, Ln, W, "#f4f6f8", "#222", r=4.0)
    rect(L["wall"], L["wall"], Ln - L["wall"], W - L["wall"], "#ffffff", "#999", r=3.1)
    yr, rw, rh = L["y_r"], L["res_w_out"], L["res_h_out"]
    rect(L["x_r0"], yr - rw / 2, L["x_r1"], yr + rw / 2, "#bfe8f2", "#2a7f96", op=0.8, r=rh / 2)
    # plunger (full position) and carriage
    rect(L["xrear_full"], yr - 7.8, L["xrear_full"] + p["reservoir"]["plunger_len"], yr + 7.8, "#e0803a", "#a04a10", op=0.8)
    ys, zc = L["y_s"], L["z_axis"]
    C = L["coax"]
    rect(L["xrear_full"], ys - 2.2, L["xrear_full"] + p["drive"]["carriage_len"], ys + 2.2, "#f0c040", "#a08000")
    # motor chain
    if C:
        rect(C["x_m0"], ys - 3, C["x_m1"], ys + 3, "#8a8f98", "#444")
        rect(C["x_m1"], ys - 3, C["x_g1"], ys + 3, "#b9bec6", "#444")
        rect(C["x_rb0"], ys - 1.3, C["x_m0"], ys + 1.3, "#666", "#333")
        rect(C["x_fb0"], ys - 1.75, C["x_fb1"], ys + 1.75, "#999", "#444")
        line(C["x_fb1"], ys, C["x_tip"], ys, "#222", 3)
        rect(C["c0"], ys - 1.5, C["c1"], ys + 1.5, "#d4a017", "#7a5a00")
        line(C["screw_x0"], ys, L["screw_tip"], ys, "#222", 2)
        rect(*([C["block_x"][0], C["block_y"][0], C["block_x"][1], C["block_y"][1]]), "#c06020", "#703000")
        ytip = C["pin_tip_y"]
        line(C["pin_x"], C["block_y"][0], C["pin_x"], ytip, "#703000", 2.5)
        line(C["pin_x"], ytip, 0.0, ytip - 0.3, "#d02020", 1.4, "4,3")
        pin_xy, mot_mid, gb_mid, cpl_mid, cpl_y = (C["pin_x"], ytip), (C["x_m0"] + C["x_m1"]) / 2, (C["x_m1"] + C["x_g1"]) / 2, (C["c0"] + C["c1"]) / 2, ys + 1.5
        gear_note, ym_ = "Gearbox 26.45:1 (8.1 mm)", ys
    else:
        ym_, G, N = L["y_m"], L["gears"], L["nfp_term"]
        rect(L["gh_x"][0], ym_ - 3, L["gh_x"][1], ym_ + 3, "#b9bec6", "#444")
        rect(L["mo_x"][0], ym_ - 3, L["mo_x"][1], ym_ + 3, "#8a8f98", "#444")
        rect(L["mo_x"][1], ym_ - 1.3, L["mot_end"], ym_ + 1.3, "#666", "#333")
        rect(L["mx0"] - 0.8, ym_ - 1.75, L["mx0"], ym_ + 1.75, "#999", "#444")
        rect(L["gear_x1"] - 1.2, ys - G["root_screw"] / 2, L["gear_x1"], ys + G["root_screw"] / 2, "#d4a017", "#7a5a00")
        rect(L["gear_x1"] - 1.2, ym_ - G["root_motor"] / 2, L["gear_x1"], ym_ + G["root_motor"] / 2, "#d4a017", "#7a5a00")
        line(1.0, ys, L["screw_tip"], ys, "#222", 2)
        rect(N["block_x"][0], N["block_y"][0], N["block_x"][1], N["block_y"][1], "#c06020", "#703000")
        ld = p["bench"]["lead"]
        line(N["x_center"], ld["groove_y"], Ln + 3, ld["groove_y"], "#d02020", 1.6, "4,3")
        pin_xy, mot_mid, gb_mid, cpl_mid, cpl_y = (N["x_center"], ld["groove_y"]), (L["mo_x"][0] + L["mo_x"][1]) / 2, (L["gh_x"][0] + L["gh_x"][1]) / 2, L["gear_x1"] - 0.6, ys + 2.0
        gear_note, ytip = "Gearbox 26.45:1 (8.1 mm)", ld["groove_y"]
    # reservoir stops, magnet
    rect(L["xrear_full"] - 0.7, ys + 1.6, L["xrear_full"], ys + 2.15, "#555", "#222")
    rect(L["xrear_full"] - 0.7, ys - 2.15, L["xrear_full"], ys - 1.6, "#555", "#222")
    circ((L["mag_x"][0] + L["mag_x"][1]) / 2, ys, 1.0, "#cc2222", "#880000")
    # dock
    D, dk = L["dock"], p["dock"]
    xr = L["x_r1"]
    cp = dk["cap"]
    rect(xr, cp["block_y0"], xr + dk["block_len"], D["y_c"] + cp["block_up_y"], "#d8dde3", "#555")                 # end cap (septum, valve, guard)
    rect(xr + dk["block_len"], D["y_c"] - D["arm_in"] - dk["arm_t"], xr + dk["block_len"] + dk["root_len"], D["y_c"] + D["arm_in"] + dk["arm_t"], "#9fb3c8", "#445")
    rect(xr + cp["septum_x"] - 2.0, cp["block_y0"], xr + cp["septum_x"] + 2.0, cp["block_y0"] + 2.0, "#f2c6a0", "#a05020")
    rect(xr + dk["valve_x0"], D["y_c"] - 1.5, xr + dk["valve_x0"] + p["coax"]["valve_len"], D["y_c"] + 1.5, "#5ec8e8", "#1a6a85")
    line(D["x_h0"], D["y_c"], D["x_tip"], D["y_c"], "#111", 1.2)
    rect(xr + dk["block_len"], D["y_c"] - D["floor_half"], Ln, D["y_c"] + D["floor_half"], "#ffffff", "#aaa", op=0.0, dash="5,4")
    for sg in (-1, 1):
        y0, y1 = sorted((D["y_c"] + sg * D["arm_in"], D["y_c"] + sg * (D["arm_in"] + dk["arm_t"])))
        rect(xr + dk["block_len"] + dk["root_len"], y0, D["x_hook"] + 0.9, y1, "#9fb3c8", "#445")
        line(D["x_hook"], D["y_c"] + sg * D["hook_in"], D["x_hook"], D["y_c"] + sg * D["arm_in"], "#445", 3)
    circ(D["x_d"], D["y_c"], D["R"], "#e8f6ff", "#2a6a9a", op=0.45, dash="6,3")
    # pod board
    ox, oy = LJ["transform"]["board_origin_in_pod_mm"]
    poly([(ox + x, oy + y) for x, y in LJ["board"]["outline_polygon_board_mm"]], "#2e8b57", "#145a32", op=0.35)
    for sn in LJ["hall_sensors"]:
        cx, cy = sn["center_pod_mm"]
        rect(cx - sn["body_xyz_mm"][0] / 2, cy - sn["body_xyz_mm"][1] / 2, cx + sn["body_xyz_mm"][0] / 2, cy + sn["body_xyz_mm"][1] / 2,
             "#ffd400" if sn["id"] != "HALL_DOCK" else "#ff7f00", "#333")
    fc = LJ["ffc_connector"]["center_pod_mm"]
    bd = LJ["ffc_connector"]["body_mm"]
    rect(fc[0] - bd["depth_along_cable_x"] / 2, fc[1] - bd["width_y"] / 2, fc[0] + bd["depth_along_cable_x"] / 2, fc[1] + bd["width_y"] / 2, "#222", "#000", op=0.8)
    line(fc[0] + bd["depth_along_cable_x"] / 2, fc[1], Ln + 4, fc[1], "#e8c36a", 4)
    # fill window
    rect(L["xrear_full"] + 0.5, ys - 1.0, L["xrear_empty"] + 3.5, ys + 1.0, "#ffffff", "#c00", op=0.0, dash="3,2")

    tm = next(s for s in LJ["hall_sensors"] if s["id"] == "HALL_3D")["center_pod_mm"]
    dh = next(s for s in LJ["hall_sensors"] if s["id"] == "HALL_DOCK")["center_pod_mm"]
    items = [
        (mot_mid, ym_ + 3 if not C else ys + 3, "Stepper motor NFP-608 (motor part 8.0 mm)", 0, 0),
        (gb_mid, ym_ + 3 if not C else ys + 3, gear_note, 0, 0),
        (pin_xy[0], pin_xy[1], "4 motor pins -> factory lead (red) -> wall slot", 0, 0),
        (cpl_mid, cpl_y, "Sleeve coupler" if C else "Gear pair module 0.3 (z%d : z%d, centre %.2f)" % (L["gears"]["z_motor"], L["gears"]["z_screw"], L["gears"]["centre"]), 0, 0),
        (L["xrear_full"] + 6, ys, "M1.6 leadscrew (thread side)", 0, 0),
        (L["xrear_full"] + 2, ys + 2.2, "Carriage + fixed nut (full position)", 0, 0),
        ((L["x_r0"] + L["x_r1"]) / 2, yr, "Reservoir (stadium 16 x 5 inside)", 0, 0),
        (xr + dk["valve_x0"] + 1.7, D["y_c"] + 1.5, "Duckbill check valve (in the end cap)", 0, 0),
        (xr + 2.2, cp["block_y0"] + 1.0, "Fill septum (end cap, needle through the -Y wall hole)", 0, 0),
        (D["x_d"], D["y_c"], "Cannula dome (latched) + snap arms", 0, 0),
        (tm[0], tm[1], "TMAG5273 (under board)", 0, 0),
        (dh[0], dh[1], "Dock hall (above adapter magnet)", 0, 0),
        (fc[0] + 3, fc[1], "FFC connector + cable exit (+X)", 0, 0),
        (L["mag_x"][0] + 0.5, ys - 1.0, "Spindle magnet", 0, 0),
        ((L["xrear_full"] + L["xrear_empty"]) / 2, ys - 1.0, "Fill window (scale in U) in the lid", 0, 0),
    ]
    H = int(W * S + 2 * M + 40 + 20 * ((len(items) + 1) // 2))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(Ln*S+2*M)}" height="{H}" viewBox="0 0 {int(Ln*S+2*M)} {H}" font-family="Helvetica,Arial,sans-serif">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           f'<text x="{M}" y="26" font-size="18" font-weight="bold">OpenPatch bench pod {variant}: top view (X right, Y up), {Ln:.1f} x {W:.1f} x 8.5 mm</text>',
           f'<text x="{M}" y="46" font-size="12" fill="#555">schematic to scale; bench only (water/insulin into containers, never a person); green = pod sensor board (z 5.3..6.1, above the drive)</text>'] + els
    base = int(W * S + 2 * M + 10)
    for n, (x, y, text, tx, ty) in enumerate(items, 1):
        out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="8" fill="#c00" fill-opacity="0.85"/>')
        out.append(f'<text x="{px(x):.1f}" y="{py(y)+4:.1f}" font-size="11" fill="#fff" text-anchor="middle" font-weight="bold">{n}</text>')
        col, row = (n - 1) % 2, (n - 1) // 2
        out.append(f'<text x="{M + col * (Ln * S / 2)}" y="{base + 20 * row + 16}" font-size="13" fill="#222"><tspan fill="#c00" font-weight="bold">{n}</tspan>  {text}</text>')
    out.append("</svg>")
    path = OUT / f"{variant}_layout_annotated.svg"
    path.write_text("\n".join(out), encoding="utf-8")
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-b", "white", "-o", str(path.with_suffix(".png")), str(path)], check=True)
    return path


if __name__ == "__main__":
    for v in (sys.argv[1:] or ["OP-70", "OP-100", "OP-200"]):
        print(draw(v))
