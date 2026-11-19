# SPDX-License-Identifier: LicenseRef-OpenPatch
"""Annotated top view (SVG + PNG) of the cup pod, drawn to scale from the generator's layout.  X right (dock/tank front at the left), Y up (lane 2 on top)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

S = 19.0
M = 50


def draw(p: dict, L: dict, svg_path: Path) -> Path:
    c, dr, K = p["cup"], p["drive_nfp"], L["dock"]
    W, Ln, w = L["width"], L["length"], L["wall"]
    yr, xc = L["y_r"], L["xc"]
    px = lambda x: M + x * S
    py = lambda y: M + (W - y) * S
    els: list[str] = []

    def rect(x0, y0, x1, y1, fill, stroke="#333", op=1.0, dash=None, r=0.0, sw=1.0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<rect x="{px(x0):.1f}" y="{py(y1):.1f}" width="{(x1 - x0) * S:.1f}" height="{(y1 - y0) * S:.1f}" rx="{r * S:.1f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def circ(cx, cy, r, fill, stroke="#333", op=1.0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<circle cx="{px(cx):.1f}" cy="{py(cy):.1f}" r="{r * S:.1f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"{d}/>')

    def line(x0, y0, x1, y1, stroke="#333", wd=1.5, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        els.append(f'<line x1="{px(x0):.1f}" y1="{py(y0):.1f}" x2="{px(x1):.1f}" y2="{py(y1):.1f}" stroke="{stroke}" stroke-width="{wd}"{d}/>')

    rect(0, 0, Ln, W, "#f4f6f8", "#222", r=4.0, sw=1.5)
    rect(w, w, Ln - w, W - w, "#ffffff", "#aaa", r=3.1)
    line(0.9, L["lane2_y"][0] - 0.1, Ln - 0.9, L["lane2_y"][0] - 0.1, "#888", 1.0, "6,4")
    # dock at the right end of lane 1: pocket, plate path, head, clips, needle
    rect(K["x_bf"], yr - K["half"] - 0.4, Ln - w, yr + K["half"] + 0.4, "#e8f0ff", "#4a6a9a", op=0.5)
    rect(K["x_bf"], yr - K["half"], K["x_far"], yr + K["half"], "#ffffff", "#4a6a9a", op=0.9, dash="5,3")
    circ(K["x_d0"], yr, K["R"], "none", "#2a6a9a", dash="4,3")
    circ(K["x_d"], yr, K["R"], "#e8f6ff", "#2a6a9a", op=0.6)
    hh = c["dock"]["head"]
    rect(K["x_d"] - hh["base_l"] / 2, yr - hh["base_w"] / 2, K["x_d"] + hh["base_l"] / 2, yr + hh["base_w"] / 2, "none", "#7a5cc7", dash="3,3")
    for sg in (-1, 1):
        ya = yr + sg * (K["R"] + c["dock"]["clip"]["arm_inner_clr"])
        rect(K["x_tooth"], min(ya, ya + sg * 0.1), K["x_far"] - 0.15, max(ya, ya + sg * 0.1), "#b8c0c8", "#445", sw=2)
        rect(K["x_tooth"] - 0.3, yr + sg * 3.5 - 0.1, K["x_tooth"] + 0.3, yr + sg * 4.0 + 0.1, "#445", "#000")
    rect(K["x_d"] - 0.55, yr - 0.7, K["x_d"] + 0.55, yr + 0.7, "#ff7f00", "#703000")
    line(K["x_hub"][0], yr, K["x_tip"], yr, "#000", 1.6)
    rect(K["guard_dock"][0], yr - 0.7, K["guard_dock"][1], yr + 0.7, "#5ec8e8", "#046")
    for k, (fill, st) in {"board": ("#2e8b57", "#145a32"), "aux": ("#7fbf7f", "#145a32"), "io": ("#d09020", "#704000"), "side_a": ("#c0a060", "#604000"), "side_b": ("#c0a060", "#604000"), "battery": ("#3a5fcd", "#1a2f80"), "usb": ("#8a3fd0", "#40206a")}.items():
        b = L[k]
        rect(b["x"][0], b["y"][0], b["x"][1], b["y"][1], fill, st, op=0.45, dash="5,3", sw=1.5)
    # lane 1: tank, plunger (FULL), nut, seals, rod, collar/bush, gear B + magnet + TMAG, motor column
    rect(L["x_dry"], yr - L["res_w_out"] / 2, L["x_t0"], yr + L["res_w_out"] / 2, "#bfe8f2", "#2a7f96", op=0.75)
    rect(L["x_dry"], yr - L["bore_w"] / 2, L["x_in"], yr + L["bore_w"] / 2, "#e8f8fc", "#2a7f96", op=0.8, dash="3,2")
    xr, xf = L["x_pr"], L["x_pf_full"]
    rect(xr, yr - L["bore_w"] / 2 + 0.1, xf, yr + L["bore_w"] / 2 - 0.1, "#e0803a", "#a04a10", op=0.85)
    rect(xr, yr - 1.0, xf - c["plunger"]["front_wall"], yr + 1.0, "#3b2a1a", "#000", op=0.9)
    for a_, b_ in (c["plunger"]["ring_front_a"], c["plunger"]["ring_front_b"]):
        rect(xf - b_, yr - L["bore_w"] / 2 - 0.05, xf - a_, yr + L["bore_w"] / 2 + 0.05, "#dd2222", "#880000", op=0.9)
    rect(xr + c["plunger"]["nut_recess"], yr - 1.65, xr + L["nut_zone"], yr + 1.65, "#f0c040", "#806000")
    line(L["gear_b"][0], yr, L["x_tip"], yr, "#111", 3.0)
    rect(L["collar"][0], yr - 1.2, L["collar"][1], yr + 1.2, "#d4a017", "#7a5a00")
    rect(L["bush"][0], yr - 1.5, L["bush"][1], yr + 1.5, "#b0701c", "#5a3000")
    rect(L["gear_b"][0], yr - 2.7, L["gear_b"][1], yr + 2.7, "#f2d020", "#806000")
    rect(L["magnet"][0], yr - 1.0, L["magnet"][1], yr + 1.0, "#cc2222", "#660000")
    rect(L["tmag"][0], L["tmag_y"] - 1.4, L["tmag"][1], L["tmag_y"] + 1.4, "#ffd400", "#806000")
    rect(xc - 2.7, L["gear_a_y"][0], xc + 2.7, L["gear_a_y"][1], "#e8b000", "#806000")
    rect(xc - 1.0, L["gear_a_y"][1], xc + 1.0, L["boss_y"][0], "#444", "#222")
    rect(xc - 1.75, L["boss_y"][0], xc + 1.75, L["boss_y"][1], "#999", "#444")
    rect(xc - 3, L["gearhead_y"][0], xc + 3, L["gearhead_y"][1], "#b9bec6", "#444")
    rect(xc - 3, L["motor_y"][0], xc + 3, L["motor_y"][1], "#8a8f98", "#444")
    rect(xc - 1.3, L["rear_boss_y"][0], xc + 1.3, L["rear_boss_y"][1], "#666", "#333")
    circ(L["x_s"], L["y_s"], 1.0, "#f2a0c0", "#a03060", op=0.95)
    items = [
        (xc, (L["motor_y"][0] + L["motor_y"][1]) / 2, "Motor NFP-608-26.45 TRANSVERSE (axis Y), last element at the rear, spans both lanes", "#8a8f98"),
        (xc, L["gear_a_y"][0] + 1.1, "Gear A: miter bevel z16 on the motor shaft", "#e8b000"),
        (L["gear_b"][0] + 1.1, yr + 2.0, "Gear B: miter bevel z16 on the rod (only 2 gears)", "#f2d020"),
        ((L["gear_b"][1] + L["x_pr"]) / 2, yr, "Rod M1.6 x 0.35 ENDS at gear B, rotating, axially fixed (%.1f mm)" % L["rod_len"], "#111111"),
        ((xr + xf) / 2, yr + 4.0, "Plunger cup %.1f x 5.3, %.1f mm long, blind bore (drawn at FULL)" % (L["bore_w"] - 0.2, L["L_pl"]), "#e0803a"),
        (xr + 0.8, yr + 1.65, "Brass nut M1.6 in the hex pocket (rear of the cup)", "#f0c040"),
        (xf - 0.8, yr - L["bore_w"] / 2, "Two lip seals at the closed front end", "#dd2222"),
        ((L["x_dry"] + xr) / 2 + 3, yr - 3.5, "Tank %.1f x 5.5 bore, closed walls, NO slot, open dry rim" % L["bore_w"], "#7fd0e0"),
        (L["x_t0"] - 0.6, yr + 0.5, "Outlet through the front wall straight into the needle hub (+X)", "#1a6fd0"),
        (K["x_tip"] - 0.4, yr - 0.6, "30G needle (+X) with spring guard", "#000000"),
        (L["x_s"], L["y_s"], "Fill septum, UNDERSIDE of the front wall", "#f2a0c0"),
        (K["x_d"] + 1.5, yr + 2.5, "Dock: place-down pocket %.1f x %.1f, slide %.1f mm, head latched" % (K["pocket_len"], 2 * K["half"], K["slide"]), "#e07ac0"),
        (K["x_tooth"], yr + 4.3, "U-clip (301 FH 0.1 mm) arms + teeth in the dome notches", "#b8c0c8"),
        (K["x_d"], yr - 1.5, "Dock magnet in the head + dock hall above the pocket roof", "#ff7f00"),
        (sum(L["magnet"]) / 2, yr - 0.2, "Diametric magnet on gear B's rear face", "#cc2222"),
        (sum(L["tmag"]) / 2, L["tmag_y"], "TMAG5273 beside the magnet (0.5 mm gap), tiny sensor tab", "#ffd400"),
        (sum(L["battery"]["x"]) / 2, L["battery"]["y"][0] + 5, "Battery keep-out: Ampul 301030 (3.0 x 10 x 30, 90 mAh, PCM)", "#3a5fcd"),
        (sum(L["usb"]["x"]) / 2, sum(L["usb"]["y"]) / 2, "USB-C stacked ABOVE the front end of the cell (opening in the +Y long wall)", "#8a3fd0"),
        (sum(L["board"]["x"]) / 2, L["board"]["y"][1] - 1.5, "Main board keep-out above the battery", "#2e8b57"),
        (sum(L["aux"]["x"]) / 2, L["aux"]["y"][1] - 2.0, "Piezo / button / aux keep-out", "#7fbf7f"),
        (sum(L["io"]["x"]) / 2, sum(L["io"]["y"]) / 2, "Rear-corner keep-out: button, LED, buzzer, charger strip (full height)", "#d09020"),
        (sum(L["side_b"]["x"]) / 2, sum(L["side_b"]["y"]) / 2, "Beside the dock: piezo, button, LED, ICs (keep-out)", "#c0a060"),
        (L["bush"][0] + 0.5, yr - 1.5, "Collar + bush + printed rib (thrust bearing)", "#b0701c"),
    ]
    n_rows = (len(items) + 1) // 2
    H = int(W * S + 2 * M + 40 + 22 * n_rows)
    wpx = int(Ln * S + 2 * M)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{wpx}" height="{H}" viewBox="0 0 {wpx} {H}" font-family="Helvetica,Arial,sans-serif">', '<rect width="100%" height="100%" fill="#ffffff"/>',
           f'<text x="{M}" y="24" font-size="17" font-weight="bold">OpenPatch v0.1.0 cup pod {L["variant"]}: top view, {Ln:.1f} x {W:.1f} x {L["height"]:.1f} mm (lane 1 bottom, lane 2 top; motor at the rear/left)</text>',
           f'<text x="{M}" y="42" font-size="11" fill="#555">to scale; TEST ONLY, water only, never worn. Plunger at FULL. Keep-out boxes = reserved volumes (no PCB). Dock/head dimensions TODO-MEASURE (photo estimate). Dashed circle = head before the slide.</text>'] + els
    base = int(W * S + 2 * M + 8)
    for n, (x, y, text, col) in enumerate(items, 1):
        out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="8.5" fill="#c00" fill-opacity="0.9"/>')
        out.append(f'<text x="{px(x):.1f}" y="{py(y) + 4:.1f}" font-size="11" fill="#fff" text-anchor="middle" font-weight="bold">{n}</text>')
        cc, row = (n - 1) % 2, (n - 1) // 2
        x0 = M + cc * (Ln * S / 2)
        out.append(f'<rect x="{x0}" y="{base + 22 * row + 3}" width="12" height="12" fill="{col}" stroke="#333"/>')
        out.append(f'<text x="{x0 + 20}" y="{base + 22 * row + 14}" font-size="12" fill="#222"><tspan fill="#c00" font-weight="bold">{n}</tspan>  {text}</text>')
    out.append("</svg>")
    svg_path.write_text("\n".join(out), encoding="utf-8")
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-b", "white", "-o", str(svg_path.with_suffix(".png")), str(svg_path)], check=True)
    return svg_path
